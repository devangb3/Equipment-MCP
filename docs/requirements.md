# Equipment request requirements

## Request data

Each request covers one item and receives one decision. The employee supplies their ID, the item requested, and a reason in their own words. Someone requesting both a laptop and a monitor submits two requests.

The system records the submission date and looks up the employee’s current role, assigned equipment, and issue history for the requested item. SQLite stores synthetic employee records, equipment issues, role limits, and human reviews. Python applies the rules below.

## Refresh limits

| Current role | Monitor | Laptop |
| --- | --- | --- |
| Standard employee | Every 3 years | Every 4 years |
| Manager | Every 3 years | Every 2 years |

For a routine replacement, count calendar years from the most recent issue of the same item type to the submission date. The employee qualifies on the anniversary. For a February 29 issue, use February 28 when the anniversary year has no February 29.

## Decisions

Apply the human-review rules first. An employee can qualify for a replacement and still need review to keep a second device.

| Condition | Outcome | Example |
| --- | --- | --- |
| A fact needed for the decision is missing or conflicting. | **Human review.** | A manager requests a laptop refresh, but the assigned laptop has no issue date. Record the missing date as the reason. An unknown employee ID also requires review because the role and history cannot be verified. |
| The employee wants an additional device, an early replacement because a device broke, or an item outside the role’s policy. | **Human review.** | A second monitor to keep alongside a three-year-old monitor requires review. A broken manager laptop one day before its refresh date also requires review. A tablet has no listed limit and requires review. |
| The role covers the item and complete history confirms the employee has never received one. | **Approve** the first issue. | A standard employee with only a laptop on record can receive their first monitor. |
| A routine replacement falls on or after the refresh date. | **Approve.** | A manager issued a laptop on May 10, 2024 qualifies on May 10, 2026. |
| A routine replacement falls before the refresh date. | **Deny** and give the next eligible date. | For the same laptop, a routine request on May 9, 2026 is one day early. |

For every escalation, save the submitted employee ID, original request, and specific review reason in SQLite. Return the review ID to the employee so they can reference the case.
