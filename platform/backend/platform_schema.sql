-- Platform schema additions (owned by Person 4 / Web Platform).
--
-- Kept in its own file instead of db/schema.sql so it does not collide
-- with Person 1's ownership of the core DB schema. Applied additively
-- (CREATE TABLE IF NOT EXISTS) on backend startup — safe to run
-- against the existing blue_horizon.db without touching flight data.
--
-- These two tables are the target for the "Ticket-like system for
-- failure and recovery" and "Human-in-the-loop escalation" concerns
-- from the final project brief. The state_graph/ code (Persons 1/2/3)
-- is expected to INSERT into these tables (or call the equivalent
-- helper in platform/backend/graph_bridge.py) at the moment a graph
-- fails mid-node or pauses on a HITL condition. See
-- platform/API_CONTRACT.md for the exact call contract.

CREATE TABLE IF NOT EXISTS Tickets (
    ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Which graph/agent this came from, e.g. "aog_recovery",
    -- "flight_compensation", "crew_rescheduling".
    graph_name VARCHAR(100) NOT NULL,

    -- Identifies the specific run so it can be resumed from its
    -- last checkpoint once the ticket is resolved.
    run_id VARCHAR(100) NOT NULL,

    -- Which node the run was in when it failed.
    node_name VARCHAR(100),

    status VARCHAR(20) NOT NULL DEFAULT 'open'
        CHECK (status IN ('open', 'investigating', 'resolved')),

    -- Short machine-ish label, e.g. "tool_error", "schema_validation_failed",
    -- "unparseable_model_output".
    failure_type VARCHAR(100) NOT NULL,

    -- Human-readable description of what went wrong.
    description TEXT NOT NULL,

    -- Full JSON-serialized checkpoint state at the moment of failure,
    -- so an admin can inspect exactly what the run had collected.
    checkpoint_state TEXT NOT NULL,

    resolution_notes TEXT,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME,
    resolved_by VARCHAR(100)
);

CREATE TABLE IF NOT EXISTS HITLRequests (
    hitl_id INTEGER PRIMARY KEY AUTOINCREMENT,

    graph_name VARCHAR(100) NOT NULL,
    run_id VARCHAR(100) NOT NULL,
    node_name VARCHAR(100),

    status VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'approved', 'rejected')),

    -- Why the graph is not allowed to decide alone, e.g.
    -- "compensation_amount_exceeds_threshold", "cancels_flight",
    -- "confidence_below_bar".
    reason VARCHAR(200) NOT NULL,

    -- Human-readable summary of the decision being asked of the admin.
    summary TEXT NOT NULL,

    -- Full JSON-serialized checkpoint state at the pause point.
    checkpoint_state TEXT NOT NULL,

    -- Filled in by the admin when they act; the resumed graph run
    -- reads this back rather than proceeding blindly.
    decision_payload TEXT,
    decided_by VARCHAR(100),

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    decided_at DATETIME
);

CREATE TABLE IF NOT EXISTS RagDocuments (
    doc_id INTEGER PRIMARY KEY AUTOINCREMENT,

    title VARCHAR(200) NOT NULL,
    source_path VARCHAR(300),
    content TEXT NOT NULL,

    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    removed_at DATETIME
);
