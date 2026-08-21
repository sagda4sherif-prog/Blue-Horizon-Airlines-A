from contextlib import contextmanager
from typing import Literal

from .database import get_connection
from mcp.types import SamplingMessage, TextContent
from mcp.server.fastmcp import Context
from .elicitation import confirm_cancel_flight
from .mcp_app import mcp
from .schemas import (
    CancelFlightInput,
    AssignAircraftInput,
    AssignBackupCrewInput,
)
from .notifications import (
    SessionState,
    authenticate_manager,
    deauthenticate_manager,
)
from .tool_registry import tool_registry


DecisionType = Literal[
    "Cancel Flight",
    "Reschedule Flight",
    "Assign Backup Aircraft",
    "Assign Backup Crew",
    "Delay Flight",
    "Continue Operations",
]


@contextmanager
def db():
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def auth_error():
    if not SessionState.is_manager_authenticated():
        return {
            "error": "This action requires an authenticated session. Call authenticate_manager first."
        }


def get_employee(conn, employee_id, roles=None):
    employee = conn.execute(
        "SELECT role FROM Employees WHERE employee_id = ?",
        (employee_id,)
    ).fetchone()

    if not employee:
        return None, {"error": "Employee not found"}

    if roles and employee["role"] not in roles:
        return None, {"error": "Unauthorized"}

    return employee, None


def get_flight(conn, flight_id):
    flight = conn.execute(
        """
        SELECT flight_id, flight_number, aircraft_id, status
        FROM Flights
        WHERE flight_id = ?
        """,
        (flight_id,)
    ).fetchone()

    if not flight:
        return None, {"error": "Flight not found"}

    return flight, None


@mcp.tool()
def assign_aircraft(data: AssignAircraftInput):
    if error := auth_error():
        return error

    with db() as conn:
        flight, error = get_flight(conn, data.flight_id)
        if error:
            return error

        if flight["status"] in ("Cancelled", "Completed"):
            return {"error": "Cannot assign aircraft to this flight"}

        _, error = get_employee(
            conn,
            data.employee_id,
            ("Operations Manager", "Dispatcher")
        )
        if error:
            return error

        aircraft = conn.execute(
            """
            SELECT aircraft_id, status
            FROM Aircraft
            WHERE aircraft_id = ?
            """,
            (data.aircraft_id,)
        ).fetchone()

        if not aircraft:
            return {"error": "Aircraft not found"}

        if aircraft["status"] != "Available":
            return {"error": "Aircraft is not available"}

        if flight["aircraft_id"] and flight["aircraft_id"] != data.aircraft_id:
            conn.execute(
                "UPDATE Aircraft SET status = 'Available' WHERE aircraft_id = ?",
                (flight["aircraft_id"],)
            )

        conn.execute(
            "UPDATE Flights SET aircraft_id = ? WHERE flight_id = ?",
            (data.aircraft_id, data.flight_id)
        )

        conn.execute(
            """
            INSERT INTO AircraftAssignments
            (flight_id, aircraft_id, assigned_at, assignment_reason)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'Operational Assignment')
            """,
            (data.flight_id, data.aircraft_id)
        )

        conn.execute(
            "UPDATE Aircraft SET status = 'Assigned' WHERE aircraft_id = ?",
            (data.aircraft_id,)
        )

        conn.execute(
            """
            INSERT INTO FlightEvents
            (flight_id, event_type, severity, description, reported_at, status)
            VALUES (
                ?, 'Aircraft Assigned', 'Low',
                'Replacement aircraft assigned by operations.',
                CURRENT_TIMESTAMP, 'Closed'
            )
            """,
            (data.flight_id,)
        )

        return {
            "success": True,
            "message": "Aircraft assigned successfully"
        }


@mcp.tool()
def assign_backup_crew(data: AssignBackupCrewInput):
    if error := auth_error():
        return error

    with db() as conn:
        flight, error = get_flight(conn, data.flight_id)
        if error:
            return error

        if flight["status"] in ("Cancelled", "Completed"):
            return {"error": "Cannot assign crew to this flight"}

        _, error = get_employee(
            conn,
            data.employee_id,
            ("Operations Manager", "Dispatcher")
        )
        if error:
            return error

        crew = conn.execute(
            """
            SELECT availability, hours_flown_today
            FROM Crew
            WHERE crew_id = ?
            """,
            (data.crew_id,)
        ).fetchone()

        if not crew:
            return {"error": "Crew member not found"}

        if not crew["availability"]:
            return {"error": "Crew member unavailable"}

        if crew["hours_flown_today"] >= 8:
            return {"error": "Crew exceeded duty hours"}

        assigned = conn.execute(
            """
            SELECT 1
            FROM FlightCrew
            WHERE flight_id = ? AND crew_id = ?
            """,
            (data.flight_id, data.crew_id)
        ).fetchone()

        if assigned:
            return {"error": "Crew already assigned"}

        conn.execute(
            "INSERT INTO FlightCrew (flight_id, crew_id) VALUES (?, ?)",
            (data.flight_id, data.crew_id)
        )

        conn.execute(
            """
            INSERT INTO CrewAssignments
            (flight_id, crew_id, assigned_at, assignment_status)
            VALUES (?, ?, CURRENT_TIMESTAMP, 'Active')
            """,
            (data.flight_id, data.crew_id)
        )

        conn.execute(
            "UPDATE Crew SET availability = 0 WHERE crew_id = ?",
            (data.crew_id,)
        )

        conn.execute(
            """
            INSERT INTO FlightEvents
            (flight_id, event_type, severity, description, reported_at, status)
            VALUES (
                ?, 'Backup Crew Assigned', 'Low',
                'Backup crew assigned by Flight Operations.',
                CURRENT_TIMESTAMP, 'Closed'
            )
            """,
            (data.flight_id,)
        )

        return {
            "success": True,
            "message": "Backup crew assigned successfully"
        }


@mcp.tool()
def reschedule_flight(
    flight_id: int,
    new_departure,
    new_arrival,
    employee_id: int
):
    if error := auth_error():
        return error

    if new_departure >= new_arrival:
        return {"error": "Arrival time must be after departure time"}

    with db() as conn:
        flight, error = get_flight(conn, flight_id)
        if error:
            return error

        if flight["status"] in ("Cancelled", "Completed"):
            return {"error": "Flight cannot be rescheduled"}

        _, error = get_employee(
            conn,
            employee_id,
            ("Operations Manager", "Dispatcher")
        )
        if error:
            return error

        conn.execute(
            """
            UPDATE Flights
            SET departure_time = ?,
                arrival_time = ?,
                status = 'Rescheduled'
            WHERE flight_id = ?
            """,
            (new_departure, new_arrival, flight_id)
        )

        conn.execute(
            """
            INSERT INTO FlightEvents
            (flight_id, event_type, severity, description, reported_at, status)
            VALUES (
                ?, 'Flight Rescheduled', 'Medium',
                'Flight schedule updated by Operations Control.',
                CURRENT_TIMESTAMP, 'Closed'
            )
            """,
            (flight_id,)
        )

        return {
            "success": True,
            "message": "Flight rescheduled successfully"
        }


@mcp.tool()
async def cancel_flight(data: CancelFlightInput, ctx: Context):
    if error := auth_error():
        return error

    with db() as conn:
        flight, error = get_flight(conn, data.flight_id)
        if error:
            return error

        if flight["status"] == "Cancelled":
            return {"error": "Flight already cancelled"}

        if flight["status"] == "Completed":
            return {"error": "Completed flight cannot be cancelled"}

        _, error = get_employee(
            conn,
            data.employee_id,
            ("Operations Manager",)
        )
        if error:
            return error

        try:
            confirmed = await confirm_cancel_flight(
                ctx,
                flight["flight_number"],
                data.reason
            )
        except Exception as exc:
            return {"error": str(exc)}

        if not confirmed:
            return {"error": "Cancellation not confirmed"}

        conn.execute(
            "UPDATE Flights SET status = 'Cancelled' WHERE flight_id = ?",
            (data.flight_id,)
        )

        conn.execute(
            """
            INSERT INTO FlightEvents
            (flight_id, event_type, severity, description, reported_at, status)
            VALUES (
                ?, 'Flight Cancelled', 'High', ?,
                CURRENT_TIMESTAMP, 'Closed'
            )
            """,
            (data.flight_id, data.reason)
        )

        return {
            "success": True,
            "message": "Flight cancelled successfully"
        }


@mcp.tool()
def complete_maintenance(maintenance_id: int, employee_id: int):
    if error := auth_error():
        return error

    with db() as conn:
        maintenance = conn.execute(
            """
            SELECT maintenance_id, aircraft_id, status
            FROM Maintenance
            WHERE maintenance_id = ?
            """,
            (maintenance_id,)
        ).fetchone()

        if not maintenance:
            return {"error": "Maintenance record not found"}

        if maintenance["status"] == "Completed":
            return {"error": "Maintenance already completed"}

        _, error = get_employee(
            conn,
            employee_id,
            ("Maintenance Engineer", "Operations Manager")
        )
        if error:
            return error

        conn.execute(
            """
            UPDATE Maintenance
            SET status = 'Completed'
            WHERE maintenance_id = ?
            """,
            (maintenance_id,)
        )

        conn.execute(
            """
            UPDATE Aircraft
            SET status = 'Available'
            WHERE aircraft_id = ?
            """,
            (maintenance["aircraft_id"],)
        )

        conn.execute(
            """
            INSERT INTO FlightEvents
            (flight_id, event_type, severity, description, reported_at, status)
            SELECT
                flight_id,
                'Maintenance Completed',
                'Low',
                'Aircraft maintenance completed.',
                CURRENT_TIMESTAMP,
                'Closed'
            FROM Flights
            WHERE aircraft_id = ?
            LIMIT 1
            """,
            (maintenance["aircraft_id"],)
        )

        return {
            "success": True,
            "message": "Maintenance completed successfully"
        }


@mcp.tool()
async def create_operation_decision(
    flight_id: int,
    employee_id: int,
    decision: DecisionType,
    reason: str,
    ctx: Context
):
    if error := auth_error():
        return error

    with db() as conn:
        _, error = get_flight(conn, flight_id)
        if error:
            return error

        _, error = get_employee(
            conn,
            employee_id,
            ("Operations Manager", "Dispatcher")
        )
        if error:
            return error

        risk = ""

        try:
            result = await ctx.session.create_message(
                messages=[
                    SamplingMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Flight: {flight_id}\n"
                                f"Decision: {decision}\n"
                                f"Reason: {reason}\n"
                                "Assess the operational risk in 2-3 sentences."
                            ),
                        ),
                    )
                ],
                max_tokens=200,
            )

            if result.content.type == "text":
                risk = result.content.text

        except Exception as exc:
            risk = f"(risk assessment unavailable: {exc})"

        conn.execute(
            """
            INSERT INTO OperationDecisions
            (flight_id, employee_id, decision, reason, risk_assessment, created_at)
            VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (flight_id, employee_id, decision, reason, risk)
        )

        return {
            "success": True,
            "message": "Operation decision recorded",
            "risk_assessment": risk,
        }


@mcp.tool()
def send_notification(flight_id: int, recipient: str, message: str):
    with db() as conn:
        _, error = get_flight(conn, flight_id)
        if error:
            return error

        conn.execute(
            """
            INSERT INTO Notifications
            (flight_id, recipient, message, sent_at, status)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, 'Pending')
            """,
            (flight_id, recipient, message)
        )

        return {
            "success": True,
            "message": "Notification created"
        }


@mcp.tool()
async def resolve_operational_issue(
    flight_id: int,
    employee_id: int,
    issue_type: str,
    decision: DecisionType,
    reason: str,
    ctx: Context
):
    if decision == "Cancel Flight":
        result = await cancel_flight(
            CancelFlightInput(
                flight_id=flight_id,
                employee_id=employee_id,
                reason=reason
            ),
            ctx
        )

    elif decision == "Assign Backup Aircraft":
        with db() as conn:
            aircraft = conn.execute(
                """
                SELECT aircraft_id
                FROM Aircraft
                WHERE status = 'Available'
                LIMIT 1
                """
            ).fetchone()

        if not aircraft:
            return {"error": "No available aircraft"}

        result = assign_aircraft(
            AssignAircraftInput(
                flight_id=flight_id,
                aircraft_id=aircraft["aircraft_id"],
                employee_id=employee_id
            )
        )

    elif decision == "Assign Backup Crew":
        with db() as conn:
            crew = conn.execute(
                """
                SELECT crew_id
                FROM Crew
                WHERE availability = 1
                  AND hours_flown_today < 8
                LIMIT 1
                """
            ).fetchone()

        if not crew:
            return {"error": "No available crew"}

        result = assign_backup_crew(
            AssignBackupCrewInput(
                flight_id=flight_id,
                crew_id=crew["crew_id"],
                employee_id=employee_id
            )
        )

    elif decision == "Continue Operations":
        result = {
            "success": True,
            "message": "Operations continued"
        }

    else:
        return {
            "error": "Reschedule and Delay require additional parameters."
        }

    if "error" in result:
        return result

    decision_result = await create_operation_decision(
        flight_id,
        employee_id,
        decision,
        reason,
        ctx
    )

    if "error" in decision_result:
        return decision_result

    return {
        "success": True,
        "issue_type": issue_type,
        "decision": decision,
        "reason": reason
    }


@mcp.tool()
async def generate_operations_report(ctx: Context):
    with db() as conn:
        flights = conn.execute(
            """
            SELECT
                flight_id,
                flight_number,
                destination_airport_id,
                aircraft_id
            FROM Flights
            WHERE status NOT IN ('Completed', 'Cancelled')
            ORDER BY flight_id
            """
        ).fetchall()

    report = []

    for i, flight in enumerate(flights, 1):
        with db() as conn:
            aircraft = conn.execute(
                """
                SELECT tail_number, model, status
                FROM Aircraft
                WHERE aircraft_id = ?
                """,
                (flight["aircraft_id"],)
            ).fetchone()

            crew = conn.execute(
                """
                SELECT c.name, c.role
                FROM Crew c
                JOIN FlightCrew fc
                    ON c.crew_id = fc.crew_id
                WHERE fc.flight_id = ?
                """,
                (flight["flight_id"],)
            ).fetchall()

            weather = conn.execute(
                """
                SELECT weather, runway_status
                FROM Airports
                WHERE airport_id = ?
                """,
                (flight["destination_airport_id"],)
            ).fetchone()

        report.append({
            "flight_number": flight["flight_number"],
            "aircraft": dict(aircraft) if aircraft else None,
            "crew": [dict(c) for c in crew],
            "destination_weather": dict(weather) if weather else None
        })

        await ctx.report_progress(
            progress=i,
            total=len(flights),
            message=f"Processed flight {flight['flight_number']}"
        )

    return {
        "success": True,
        "flights_processed": len(flights),
        "report": report
    }


# --------------------------------------------------------------------
# Runtime tool catalogue
# --------------------------------------------------------------------

tool_registry.add_to_catalog(
    "authenticate_manager",
    authenticate_manager,
)

tool_registry.add_to_catalog(
    "deauthenticate_manager",
    deauthenticate_manager,
)

tool_registry.add_to_catalog(
    "assign_aircraft",
    assign_aircraft,
)

tool_registry.add_to_catalog(
    "assign_backup_crew",
    assign_backup_crew,
)

tool_registry.add_to_catalog(
    "reschedule_flight",
    reschedule_flight,
)

tool_registry.add_to_catalog(
    "cancel_flight",
    cancel_flight,
)

tool_registry.add_to_catalog(
    "complete_maintenance",
    complete_maintenance,
)

tool_registry.add_to_catalog(
    "create_operation_decision",
    create_operation_decision,
)

tool_registry.add_to_catalog(
    "send_notification",
    send_notification,
)

tool_registry.add_to_catalog(
    "resolve_operational_issue",
    resolve_operational_issue,
)

tool_registry.add_to_catalog(
    "generate_operations_report",
    generate_operations_report,
)