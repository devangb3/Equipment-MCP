CREATE TABLE employee (
    id TEXT PRIMARY KEY,
    role TEXT NOT NULL,
    hired TEXT NOT NULL
);

CREATE TABLE equipment_issue (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL REFERENCES employee(id),
    item TEXT NOT NULL,
    issued TEXT,
    assigned INTEGER NOT NULL CHECK (assigned IN (0, 1))
);

CREATE TABLE policy (
    role TEXT NOT NULL,
    item TEXT NOT NULL,
    years INTEGER NOT NULL CHECK (years > 0),
    PRIMARY KEY (role, item)
);

CREATE TABLE human_review (
    id INTEGER PRIMARY KEY,
    employee_id TEXT NOT NULL,
    request TEXT NOT NULL,
    reason TEXT NOT NULL,
    submitted TEXT NOT NULL
);
