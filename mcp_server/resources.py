from .mcp_app import mcp
from .database import get_connection


# Policies

@mcp.resource("policy://flight-delay")
def flight_delay_policy():
    """
    Blue Horizon flight delay policy.
    """
    return """
Blue Horizon Flight Delay Policy

1. Delays under 30 minutes require no passenger notification.

2. Delays between 30 and 120 minutes require a delay announcement.

3. Delays above 2 hours require approval from the Operations Manager.

4. Flights delayed more than 4 hours should be evaluated for cancellation.
"""


@mcp.resource("policy://crew-duty")
def crew_duty_policy():
    """
    Crew duty regulations.
    """
    return """
Crew Duty Regulations

- A crew member cannot fly more than 8 hours per day.

- Minimum rest period is 10 hours.

- Backup crew must have availability = True.
"""


@mcp.resource("policy://maintenance")
def maintenance_policy():
    """
    Aircraft maintenance policy.
    """
    return """
Aircraft Maintenance Policy

Critical maintenance:
Aircraft cannot be assigned.

Minor maintenance:
Assignment requires engineer approval.

Completed maintenance:
Aircraft status changes to Available.
"""


# Flight Information

@mcp.resource("flight://{flight_number}")
def get_flight_status(flight_number: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT flight_id, flight_number, departure_time, arrival_time, status, aircraft_id
        FROM Flights
        WHERE flight_number = ?
    """, (flight_number,))

    flight = cursor.fetchone()
    conn.close()

    if not flight:
        return {"error": "Flight not found"}

    return dict(flight)


# Airport Weather

@mcp.resource("airport://{airport_id}/weather")
def check_weather(airport_id: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, weather, runway_status
        FROM Airports
        WHERE airport_id = ?
    """, (airport_id,))

    airport = cursor.fetchone()
    conn.close()

    if not airport:
        return {"error": "Airport not found"}

    return dict(airport)


# Available Aircraft

@mcp.resource("aircraft://available")
def get_available_aircraft():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT aircraft_id, tail_number, model, capacity, status
        FROM Aircraft
        WHERE status = 'Available'
    """)

    aircraft = cursor.fetchall()
    conn.close()

    return [dict(a) for a in aircraft]


# Available Crew

@mcp.resource("crew://available")
def get_available_crew():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT crew_id, name, role, hours_flown_today
        FROM Crew
        WHERE availability = 1
    """)

    crew = cursor.fetchall()
    conn.close()

    return [dict(c) for c in crew]


# Maintenance Reports

@mcp.resource("maintenance://reports")
def get_maintenance_reports():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT maintenance_id, aircraft_id, severity, status, engineer
        FROM Maintenance
    """)

    reports = cursor.fetchall()
    conn.close()

    return [dict(r) for r in reports]


# Flight Details

@mcp.resource("flight://{flight_number}/details")
def get_flight_full_details(flight_number: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            f.flight_number, f.status, f.departure_time, f.arrival_time,
            oa.name AS origin, da.name AS destination,
            a.tail_number, a.model, a.capacity
        FROM Flights f
        LEFT JOIN Airports oa ON f.origin_airport_id = oa.airport_id
        LEFT JOIN Airports da ON f.destination_airport_id = da.airport_id
        LEFT JOIN Aircraft a ON f.aircraft_id = a.aircraft_id
        WHERE f.flight_number = ?
    """, (flight_number,))

    result = cursor.fetchone()
    conn.close()

    if not result:
        return {"error": "Flight not found"}

    return dict(result)


# Delayed Flights
# FIXED: was missing conn.close() and a return statement entirely —
# this resource previously always returned None.

@mcp.resource("flights://delayed")
def get_delayed_flights():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT flight_number, departure_time, arrival_time, status
        FROM Flights
        WHERE status = 'Delayed'
        ORDER BY departure_time
    """)

    flights = cursor.fetchall()
    conn.close()

    return [dict(f) for f in flights]


# Today's Flights
# FIXED: removed unreachable dead code after the original return, and
# added an actual date filter — previously this returned ALL flights
# regardless of date despite the name/docstring.

@mcp.resource("flights://today")
def get_todays_flights():
    """
    Return today's flights with origin and destination airports.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            f.flight_number, oa.name AS origin, da.name AS destination,
            f.departure_time, f.arrival_time, f.status
        FROM Flights f
        JOIN Airports oa ON f.origin_airport_id = oa.airport_id
        JOIN Airports da ON f.destination_airport_id = da.airport_id
        WHERE DATE(f.departure_time) = DATE('now')
        ORDER BY f.departure_time
    """)

    flights = cursor.fetchall()
    conn.close()

    return [dict(flight) for flight in flights]
