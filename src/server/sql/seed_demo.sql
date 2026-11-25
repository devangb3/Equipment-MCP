INSERT INTO employee (id, role, hired) VALUES
    ('M1', 'Manager', '2020-01-15'),
    ('S1', 'Standard employee', '2020-01-15'),
    ('M2', 'Manager', '2020-01-15'),
    ('S2', 'Standard employee', '2020-01-15');

INSERT INTO policy (role, item, years) VALUES
    ('Manager', 'monitor', 3),
    ('Manager', 'laptop', 2),
    ('Standard employee', 'monitor', 3),
    ('Standard employee', 'laptop', 4);

INSERT INTO equipment_issue (employee_id, item, issued, assigned) VALUES
    ('M1', 'laptop', '2020-05-10', 0),
    ('M1', 'laptop', '2024-05-10', 1),
    ('S1', 'laptop', '2024-05-10', 1),
    ('M2', 'laptop', NULL, 1),
    ('S2', 'monitor', '2024-02-29', 1);
