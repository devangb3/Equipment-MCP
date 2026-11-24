# Equipment request requirements

## Request data

Each request is for one item. The system makes one decision. The employee supplies their ID, the item requested, and a reason in their own words. Someone requesting both a laptop and a monitor submits two requests.

The system records the submission date. It looks up the employee's current role, assigned equipment, and issue history for the requested item. SQLite stores synthetic employee records, equipment issues, role limits, and human reviews. Python applies the rules below.

## Refresh limits

| Current role | Monitor | Laptop |
| --- | --- | --- |
| Standard employee | Every 3 years | Every 4 years |
| Manager | Every 3 years | Every 2 years |

For a routine replacement, count calendar years from the most recent issue of the same item type to the submission date. The employee qualifies on the anniversary. For a February 29 issue, use February 28 when the anniversary year has no February 29.

## Decisions

| Condition | Outcome | Example |
| --- | --- | --- |
| A fact needed for the decision is missing or conflicting. | Human review. | A manager requests a laptop refresh, but the assigned laptop has no issue date. Record the missing date as the reason. An unknown employee ID also requires human review because the role and history cannot be verified. |
| The employee wants an additional device, an early replacement because a device broke, or an item outside the role's policy. | Human review. | A second monitor to keep alongside a three-year-old monitor requires human review. A broken manager laptop one day before its refresh date also requires human review. A tablet has no listed limit and requires human review. |
| The role's policy lists the item, and complete issue history shows the employee has never received one. | Approve the first issue. | A standard employee with only a laptop on record can receive their first monitor. |
| The submission date for a routine replacement is on or after the refresh date. | Approve. | A manager whose laptop was issued on May 10, 2024 qualifies on May 10, 2026. |
| The submission date for a routine replacement is before the refresh date. | Deny the request and return the next eligible date. | For the same laptop, a routine request on May 9, 2026 is one day early. |

For every human review, save the submitted employee ID, the original request, and the specific reason in SQLite. Return the review ID. The employee uses that ID to reference the case.
