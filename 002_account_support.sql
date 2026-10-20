ALTER TABLE users ADD COLUMN must_change_password INTEGER NOT NULL DEFAULT 0 CHECK (must_change_password IN (0, 1));

CREATE TABLE support_tickets (
    id TEXT PRIMARY KEY,
    ticket_number TEXT NOT NULL UNIQUE,
    requested_by TEXT NOT NULL REFERENCES users(id),
    category TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'closed')),
    developer_reply TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    replied_at TEXT
);
CREATE INDEX support_tickets_requester ON support_tickets(requested_by, created_at);
CREATE INDEX support_tickets_status ON support_tickets(status, updated_at);
