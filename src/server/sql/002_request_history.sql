-- Existing review IDs become submission IDs, preserving all R-number references.
ALTER TABLE human_review RENAME TO submitted_request;
ALTER TABLE submitted_request ADD COLUMN item TEXT;
ALTER TABLE submitted_request ADD COLUMN intent TEXT;
ALTER TABLE submitted_request ADD COLUMN policy_outcome TEXT NOT NULL DEFAULT 'human_review'
    CHECK (policy_outcome IN ('approve', 'deny', 'human_review'));
ALTER TABLE submitted_request ADD COLUMN next_eligible_date TEXT;

CREATE VIEW human_review AS
SELECT id, employee_id, request, reason, submitted
FROM submitted_request WHERE policy_outcome = 'human_review';

CREATE TABLE review_decision (
    request_id INTEGER PRIMARY KEY REFERENCES submitted_request(id),
    decision TEXT NOT NULL CHECK (decision IN ('approve', 'deny')),
    reviewer TEXT NOT NULL CHECK (length(trim(reviewer)) > 0),
    rationale TEXT NOT NULL CHECK (length(trim(rationale)) > 0),
    decided_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TRIGGER require_review_case BEFORE INSERT ON review_decision
WHEN NOT EXISTS (SELECT 1 FROM human_review WHERE id = NEW.request_id)
BEGIN
    SELECT RAISE(ABORT, 'Submission has no human review case');
END;

CREATE VIEW request_history AS
SELECT s.id AS request_id, s.employee_id, s.request, s.item, s.intent, s.submitted,
       s.policy_outcome, s.reason AS policy_reason, s.next_eligible_date,
       CASE WHEN s.policy_outcome = 'human_review' THEN 'R' || s.id END AS review_id,
       d.decision AS human_decision, d.reviewer, d.rationale, d.decided_at,
       COALESCE(d.decision, CASE WHEN s.policy_outcome = 'human_review'
                                 THEN 'pending_review' ELSE s.policy_outcome END) AS status
FROM submitted_request AS s
LEFT JOIN review_decision AS d ON d.request_id = s.id;
