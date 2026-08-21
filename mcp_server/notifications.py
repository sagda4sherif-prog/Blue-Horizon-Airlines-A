"""
Notification helpers for Blue Horizon Flight Operations.
"""

from mcp.server.fastmcp import Context
from mcp.types import ToolListChangedNotification

from .mcp_app import mcp
from .database import get_connection


# --------------------------------------------------------------------
# Event payload helpers
# These are NOT MCP tools.
# They only build notification payloads used by send_notification().
# --------------------------------------------------------------------

def flight_cancelled(flight_number: str):
    return {
        "event": "flight.cancelled",
        "message": "Flight cancelled successfully.",
        "flight_number": flight_number,
    }


def flight_rescheduled(flight_number: str):
    return {
        "event": "flight.rescheduled",
        "message": "Flight rescheduled successfully.",
        "flight_number": flight_number,
    }


def aircraft_assigned(
    flight_number: str,
    aircraft_id: int
):
    return {
        "event": "aircraft.assigned",
        "message": "Aircraft assigned successfully.",
        "flight_number": flight_number,
        "aircraft_id": aircraft_id,
    }


def backup_crew_assigned(
    flight_number: str,
    crew_id: int
):
    return {
        "event": "crew.assigned",
        "message": "Backup crew assigned successfully.",
        "flight_number": flight_number,
        "crew_id": crew_id,
    }


def maintenance_completed(
    maintenance_id: int
):
    return {
        "event": "maintenance.completed",
        "message": "Maintenance completed successfully.",
        "maintenance_id": maintenance_id,
    }


def operation_decision_recorded(
    decision_id: int
):
    return {
        "event": "operation.decision.recorded",
        "message": "Operation decision recorded successfully.",
        "decision_id": decision_id,
    }


def notification_sent(
    recipient: str
):
    return {
        "event": "notification.sent",
        "message": "Notification sent successfully.",
        "recipient": recipient,
    }


# --------------------------------------------------------------------
# Session state
# --------------------------------------------------------------------

class SessionState:

    authenticated_manager_id : int | None = None

    @classmethod
    def is_manager_authenticated(cls):
        return cls.authenticated_manager_id is not None


# --------------------------------------------------------------------
# Authentication Tool
# --------------------------------------------------------------------

@mcp.tool()
async def authenticate_manager(
    employee_id: int,
    ctx: Context
):
    """
    Authenticate an Operations Manager.
    Enables privileged write tools.
    """

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT role
        FROM Employees
        WHERE employee_id=?
    """, (employee_id,))

    employee = cursor.fetchone()

    conn.close()

    if not employee:
        return {
            "success": False,
            "error": "Employee not found"
        }

    if employee["role"] != "Operations Manager":
        return {
            "success": False,
            "error": "Only Operations Managers may authenticate."
        }

    SessionState.authenticated_manager_id = employee_id

    await notify_tools_changed(ctx)

    return {
        "success": True,
        "message": "Manager authenticated successfully."
    }


# --------------------------------------------------------------------
# Helper
# --------------------------------------------------------------------

@mcp.tool()
async def deauthenticate_manager(ctx: Context):
    """
    Log out the currently authenticated Operations Manager.
    Disables privileged write tools again.
    """

    SessionState.authenticated_manager_id = None

    await notify_tools_changed(ctx)

    return {
        "success": True,
        "message": "Manager logged out."
    }
# --------------------------------------------------------------------
# MCP Notification
# --------------------------------------------------------------------

async def notify_tools_changed(
    ctx: Context
):
    """
    Notify the client that the available tool list changed.
    """

    await ctx.session.send_notification(
        ToolListChangedNotification(
            method="notifications/tools/list_changed"
        )
    )
