from .mcp_app import mcp


@mcp.prompt()
def delay_announcement(
    flight_number: str,
    delay: str,
    reason: str,
    airport: str
):
    return f"""
Generate a professional passenger announcement.

Flight: {flight_number}

Delay Duration: {delay}

Reason: {reason}

Airport: {airport}

Keep it polite and under 120 words.
"""


@mcp.prompt()
def operations_report(
    flight_number: str,
    status: str,
    aircraft: str,
    crew: str,
    weather: str
):
    return f"""
Generate an Operations Control Report.

Flight: {flight_number}

Status: {status}

Aircraft: {aircraft}

Crew: {crew}

Weather: {weather}

Summarize operational risks.
"""


@mcp.prompt()
def maintenance_summary(
    tail_number: str,
    severity: str,
    engineer: str,
    status: str
):
    return f"""
Generate a maintenance summary.

Aircraft: {tail_number}

Severity: {severity}

Engineer: {engineer}

Status: {status}

Provide recommendations.
"""
