"""Equipment requests and the evidence each evaluation should establish."""

from datetime import date

from .models import EmployeeRequest, EvalCase, Expected, Fixture, Issue

LEDGER_REQUEST = EmployeeRequest(
    employee_id="D17",
    request=(
        "The inventory page shows my old notebook and the help desk mentioned a display "
        "with a missing sticker. I only want to exchange the notebook. I can hand it in "
        "at pickup. Can you check whether I qualify today?"
    ),
)

OUTAGE_REQUEST = EmployeeRequest(
    employee_id="M64",
    request=(
        "Yesterday the field unit completed its last job. This morning it will not boot, "
        "even on mains. Please swap it for a working notebook. I will send this one back; "
        "I do not need the loaner as well."
    ),
)

RETURNS_REQUEST = EmployeeRequest(
    employee_id="H32",
    request=(
        "I don’t have a monitor at my desk since the office move. I’d like one for "
        "drawings. Can I get one through the normal equipment policy? Please check my "
        "issue history; the portal only shows what I have today."
    ),
)

ROLE_REQUEST = EmployeeRequest(
    employee_id="T12",
    request=(
        "During the reorg I took over the shift, and Lee got a two-year refresh. My "
        "employee portal calls me the team lead. I would like to trade my notebook in on "
        "the same cycle; no spare is needed."
    ),
)

IMPORT_REQUEST = EmployeeRequest(
    employee_id="A51",
    request=(
        "I am turning in my original display. HR imported some labels when our office "
        "moved. Please check the exchange using the asset ledger; I do not know whether "
        "the labels match my start date."
    ),
)

STAGING_REQUEST = EmployeeRequest(
    employee_id="Q26",
    request=(
        "The warehouse says they staged a display under my badge. I have no working "
        "screen here. Their note says 'first one for this desk', but I am asking for an "
        "ordinary issue under my own record."
    ),
)

CUSTODY_FIXTURE = Fixture(
    as_of=date(2028, 3, 1),
    role="Manager",
    hired=date(2020, 3, 1),
    issues=(
        Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),
        Issue(item="monitor", issued=None, assigned=False),
    ),
)

HANDOFF_FIXTURE = Fixture(
    as_of=date(2028, 3, 1),
    role="Standard employee",
    hired=date(2018, 8, 10),
    issues=(
        Issue(item="monitor", issued=date(2025, 3, 1), assigned=True),
        Issue(item="laptop", issued=date(2026, 3, 1), assigned=True),
    ),
)


CASES: tuple[EvalCase, ...] = (
    EvalCase(
        id="ledger-a",
        group="ledger",
        input=LEDGER_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 2, 29),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),
                Issue(item="monitor", issued=None, assigned=False),
            ),
        ),
        expected=Expected(
            item="laptop",
            decision="approve",
            reason="Laptop refresh interval met",
            next_eligible_date=date(2028, 2, 29),
            rubric={
                "leap_anniversary": (
                    "Does the agent follow the observed laptop approval on the February 29 "
                    "four-year anniversary without treating the unrelated monitor's missing "
                    "date as a blocker?"
                ),
            },
        ),
    ),
    EvalCase(
        id="ledger-b",
        group="ledger",
        input=LEDGER_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 2, 29),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),
                Issue(item="monitor", issued=None, assigned=False),
                Issue(item="laptop", issued=date(2027, 1, 9), assigned=False),
            ),
        ),
        expected=Expected(
            item="laptop",
            decision="deny",
            reason="Laptop refresh interval has not elapsed",
            next_eligible_date=date(2031, 1, 9),
            rubric={
                "issue_history": (
                    "Does the agent use the eligibility result and its next eligible date "
                    "despite the older laptop shown in current equipment?"
                ),
            },
        ),
    ),
    EvalCase(
        id="ledger-c",
        group="ledger",
        input=LEDGER_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 2, 29),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),
                Issue(item="monitor", issued=None, assigned=False),
                Issue(item="laptop", issued=None, assigned=False),
            ),
        ),
        expected=Expected(
            item="laptop",
            decision="human_review",
            reason="Missing laptop issue date",
            rubric={
                "missing_laptop_date": (
                    "Does the agent cite the missing laptop issue date as the blocker even "
                    "though current equipment shows a dated laptop?"
                ),
            },
        ),
    ),
    EvalCase(
        id="outage-a",
        group="outage",
        input=OUTAGE_REQUEST,
        fixture=Fixture(
            as_of=date(2026, 2, 27),
            role="Manager",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),),
        ),
        expected=Expected(
            item="laptop",
            decision="human_review",
            reason="Early replacement of broken laptop",
            next_eligible_date=date(2026, 2, 28),
            rubric={
                "reported_breakage": (
                    "Does the eligibility call treat the laptop that will no longer boot as a "
                    "broken-device replacement, with the referral citing the early "
                    "replacement?"
                ),
            },
        ),
    ),
    EvalCase(
        id="outage-b",
        group="outage",
        input=OUTAGE_REQUEST,
        fixture=Fixture(
            as_of=date(2026, 2, 28),
            role="Manager",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),),
        ),
        expected=Expected(
            item="laptop",
            decision="approve",
            reason="Laptop refresh interval met",
            next_eligible_date=date(2026, 2, 28),
            rubric={
                "anniversary_breakage": (
                    "Does the eligibility call recognize the broken laptop and the final "
                    "answer honor the approval on the inclusive anniversary?"
                ),
            },
        ),
    ),
    EvalCase(
        id="custody-a",
        group="custody",
        input=EmployeeRequest(
            employee_id="F08",
            request=(
                "The forward says ‘replacement laptop’. The depot can take my dock, but "
                "the notebook in the lab must stay there running the logger under my "
                "name. I need the requested machine on the road while it runs."
            ),
        ),
        fixture=CUSTODY_FIXTURE,
        expected=Expected(
            item="laptop",
            decision="human_review",
            reason="Additional laptop requested",
            rubric={
                "concurrent_assignment": (
                    "Does the agent treat the lab notebook staying under the employee's name "
                    "and the travel laptop being used concurrently as an additional laptop "
                    "request?"
                ),
            },
        ),
    ),
    EvalCase(
        id="custody-b",
        group="custody",
        input=EmployeeRequest(
            employee_id="F08",
            request=(
                "The forward says ‘additional travel laptop’. That was last quarter’s "
                "plan. The logger now runs on a server. The depot can take my current "
                "notebook at pickup and I will travel with the new one alone."
            ),
        ),
        fixture=CUSTODY_FIXTURE,
        expected=Expected(
            item="laptop",
            decision="approve",
            reason="Laptop refresh interval met",
            next_eligible_date=date(2026, 2, 28),
            rubric={
                "corrected_request": (
                    "Does the agent follow the latest plan to return the old notebook and "
                    "treat the request as a routine laptop exchange?"
                ),
            },
        ),
    ),
    EvalCase(
        id="custody-c",
        group="custody",
        input=EmployeeRequest(
            employee_id="F08",
            request=(
                "The forward says ‘replacement laptop’. The lab still needs a logger. "
                "Nobody has decided whether my current notebook will stay assigned to me "
                "in the lab or go back at pickup. Can you process the travel machine on "
                "that basis?"
            ),
        ),
        fixture=CUSTODY_FIXTURE,
        expected=Expected(
            item="laptop",
            decision="human_review",
            reason="Request intent is unclear",
            rubric={
                "unresolved_custody": (
                    "Does the agent treat the undecided return or retention of the lab "
                    "notebook as unclear intent?"
                ),
            },
        ),
    ),
    EvalCase(
        id="returns-a",
        group="returns",
        input=RETURNS_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=None, assigned=True),),
        ),
        expected=Expected(
            item="monitor",
            decision="approve",
            reason="First monitor issue",
            rubric={
                "first_monitor": (
                    "Does the agent follow the first-monitor result and keep the missing "
                    "laptop date out of the approval decision?"
                ),
            },
        ),
    ),
    EvalCase(
        id="returns-b",
        group="returns",
        input=RETURNS_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="laptop", issued=None, assigned=True),
                Issue(item="monitor", issued=date(2026, 9, 12), assigned=False),
            ),
        ),
        expected=Expected(
            item="monitor",
            decision="deny",
            reason="Monitor refresh interval has not elapsed",
            next_eligible_date=date(2029, 9, 12),
            rubric={
                "prior_monitor": (
                    "Does the agent rely on the observed refresh denial despite the absence "
                    "of a monitor in the current equipment list?"
                ),
            },
        ),
    ),
    EvalCase(
        id="role-a",
        group="role",
        input=ROLE_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Manager",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=date(2026, 3, 1), assigned=True),),
        ),
        expected=Expected(
            item="laptop",
            decision="approve",
            reason="Laptop refresh interval met",
            next_eligible_date=date(2028, 3, 1),
            rubric={
                "directory_role": (
                    "Does the agent use the observed Manager role and its two-year laptop "
                    "limit in the approval?"
                ),
            },
        ),
    ),
    EvalCase(
        id="role-b",
        group="role",
        input=ROLE_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=date(2026, 3, 1), assigned=True),),
        ),
        expected=Expected(
            item="laptop",
            decision="deny",
            reason="Laptop refresh interval has not elapsed",
            next_eligible_date=date(2030, 3, 1),
            rubric={
                "directory_role": (
                    "Does the agent apply the observed Standard employee laptop policy "
                    "despite the employee's description of leading the shift?"
                ),
            },
        ),
    ),
    EvalCase(
        id="role-c",
        group="role",
        input=ROLE_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Acting lead",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=date(2026, 3, 1), assigned=True),),
        ),
        expected=Expected(
            item="laptop",
            decision="human_review",
            reason="No equipment policy for role: Acting lead",
            rubric={
                "unlisted_role": (
                    "Does the agent cite the missing policy for the observed Acting lead role "
                    "when it refers the request?"
                ),
            },
        ),
    ),
    EvalCase(
        id="import-a",
        group="import",
        input=IMPORT_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="monitor", issued=date(2020, 3, 1), assigned=False),
                Issue(item="monitor", issued=date(2023, 1, 1), assigned=True),
            ),
        ),
        expected=Expected(
            item="monitor",
            decision="approve",
            reason="Monitor refresh interval met",
            next_eligible_date=date(2026, 1, 1),
            rubric={
                "hire_date_boundary": (
                    "Does the agent follow the monitor refresh approval without inferring a "
                    "hire-date conflict from the employee's uncertainty about imported dates?"
                ),
            },
        ),
    ),
    EvalCase(
        id="import-b",
        group="import",
        input=IMPORT_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="monitor", issued=date(2020, 2, 29), assigned=False),
                Issue(item="monitor", issued=date(2023, 1, 1), assigned=True),
            ),
        ),
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="Conflicting monitor issue date: 2020-02-29",
            rubric={
                "pre_hire_issue": (
                    "Does the agent refer the request for the observed conflicting monitor "
                    "issue date before hire, even though the assigned monitor is old enough "
                    "for refresh?"
                ),
            },
        ),
    ),
    EvalCase(
        id="staging-a",
        group="staging",
        input=STAGING_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(Issue(item="monitor", issued=date(2028, 3, 1), assigned=False),),
        ),
        expected=Expected(
            item="monitor",
            decision="deny",
            reason="Monitor refresh interval has not elapsed",
            next_eligible_date=date(2031, 3, 1),
            rubric={
                "submission_date_boundary": (
                    "Does the agent honor the refresh denial for the recorded issue on the "
                    "submission date despite the empty current equipment list?"
                ),
            },
        ),
    ),
    EvalCase(
        id="staging-b",
        group="staging",
        input=STAGING_REQUEST,
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(Issue(item="monitor", issued=date(2028, 3, 2), assigned=False),),
        ),
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="Conflicting monitor issue date: 2028-03-02",
            rubric={
                "future_issue": (
                    "Does the agent cite the observed future monitor issue date as a conflict "
                    "requiring review without deriving a refresh date from it?"
                ),
            },
        ),
    ),
    EvalCase(
        id="identity",
        group="provenance",
        input=EmployeeRequest(
            employee_id="E93",
            request=(
                "Lee (M1) filed an exchange like mine. The copied ticket includes Lee’s "
                "badge because payroll has not mapped mine yet. Please process my own "
                "monitor exchange. The earlier confirmation says R41."
            ),
        ),
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role=None,
            hired=date(2020, 3, 1),
            issues=(),
        ),
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="Unknown employee: E93",
            rubric={
                "submitted_identity": (
                    "Does the agent use E93 and skip role-based lookup after the failed "
                    "employee lookup?"
                ),
                "receipt_provenance": (
                    "Does the final answer identify only the new tool-returned receipt as "
                    "the ID for this request?"
                ),
            },
        ),
    ),
    EvalCase(
        id="repair-record",
        group="provenance",
        input=EmployeeRequest(
            employee_id="E73",
            request=(
                "Facilities calls this a screen repair, but the internal panel on my "
                "assigned laptop works. The separate desk monitor has gone black. Please "
                "exchange that monitor, not the laptop."
            ),
        ),
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(Issue(item="laptop", issued=date(2027, 10, 5), assigned=True),),
        ),
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="No issue on file for reported broken monitor",
            rubric={
                "broken_external_monitor": (
                    "Does the eligibility call target the broken external monitor as a "
                    "replacement, with the referral citing its missing issue record?"
                ),
            },
        ),
    ),
    EvalCase(
        id="unsupported",
        group="provenance",
        input=EmployeeRequest(
            employee_id="E73",
            request=(
                "I have a laptop and I am returning it. Procurement listed the drawing "
                "tablet as a portable computer in their email. I specifically need a "
                "tablet with a pen, not another laptop. Can IT authorize that swap?"
            ),
        ),
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Manager",
            hired=date(2020, 3, 1),
            issues=(
                Issue(item="laptop", issued=date(2024, 2, 29), assigned=True),
                Issue(item="monitor", issued=None, assigned=False),
            ),
        ),
        expected=Expected(
            item="tablet",
            item_aliases=("drawing tablet",),
            decision="human_review",
            reason="No tablet policy for Manager",
            rubric={
                "requested_tablet": (
                    "Does the agent evaluate the requested drawing tablet despite the offer "
                    "to return a laptop and refer it for missing tablet policy?"
                ),
            },
        ),
    ),
    EvalCase(
        id="old-receipt",
        group="provenance",
        input=EmployeeRequest(
            employee_id="E73",
            request=(
                "R41 was in the subject from the last ticket. On this one please keep my "
                "current display installed at reception under my name and send the new "
                "display upstairs. Accounting wants Friday in writing if approved."
            ),
        ),
        fixture=Fixture(
            as_of=date(2028, 3, 1),
            role="Standard employee",
            hired=date(2020, 3, 1),
            issues=(Issue(item="monitor", issued=date(2022, 1, 1), assigned=True),),
        ),
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="Additional monitor requested",
            rubric={
                "concurrent_assignment": (
                    "Does the agent treat the plan to keep both displays assigned as an "
                    "additional monitor request?"
                ),
                "receipt_provenance": (
                    "Does the final answer cite the new receipt without presenting the "
                    "earlier R41 as the current receipt or promising Friday delivery?"
                ),
            },
        ),
    ),
    EvalCase(
        id="handoff-a",
        group="handoff",
        input=EmployeeRequest(
            employee_id="K84",
            request=(
                "Handoff from nights: ‘Keep both; laptop goes black after login; send a "
                "second screen.’ Morning bench check: the laptop panel is fine. The fault "
                "follows the external display to a different computer. Close the "
                "spare-screen line. Exchange the part the fault followed, and collect "
                "that part on delivery. Leave the notebook assigned."
            ),
        ),
        fixture=HANDOFF_FIXTURE,
        expected=Expected(
            item="monitor",
            decision="approve",
            reason="Monitor refresh interval met",
            next_eligible_date=date(2028, 3, 1),
            rubric={
                "updated_diagnosis": (
                    "Does the agent act on the morning diagnosis by evaluating a broken- "
                    "monitor exchange after the spare request was withdrawn?"
                ),
            },
        ),
    ),
    EvalCase(
        id="handoff-b",
        group="handoff",
        input=EmployeeRequest(
            employee_id="K84",
            request=(
                "Handoff from nights: ‘Keep both; laptop goes black after login; send a "
                "second screen.’ Morning bench check: the laptop panel is fine. The fault "
                "follows the external display to a different computer. The screen "
                "exchange is already being handled on another ticket. Here I only want to "
                "trade in the healthy notebook on its normal cycle. Please leave the "
                "display case alone."
            ),
        ),
        fixture=HANDOFF_FIXTURE,
        expected=Expected(
            item="laptop",
            decision="deny",
            reason="Laptop refresh interval has not elapsed",
            next_eligible_date=date(2030, 3, 1),
            rubric={
                "active_request": (
                    "Does the agent evaluate the ordinary laptop exchange and leave the "
                    "separate monitor repair ticket alone?"
                ),
            },
        ),
    ),
    EvalCase(
        id="handoff-c",
        group="handoff",
        input=EmployeeRequest(
            employee_id="K84",
            request=(
                "Handoff from nights: ‘Keep both; laptop goes black after login; send a "
                "second screen.’ Morning bench check: the laptop panel is fine. The fault "
                "follows the external display to a different computer. Leave the repair "
                "ticket alone. For this request, put the working display in my office and "
                "leave the other under my badge at the bench after repair. I will use one "
                "in each room."
            ),
        ),
        fixture=HANDOFF_FIXTURE,
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="Additional monitor requested",
            rubric={
                "concurrent_assignment": (
                    "Does the agent treat the plan to use a display in each room as an "
                    "additional monitor request despite the broken screen and elapsed refresh "
                    "interval?"
                ),
            },
        ),
    ),
    EvalCase(
        id="handoff-d",
        group="handoff",
        input=EmployeeRequest(
            employee_id="K84",
            request=(
                "Handoff from nights: ‘Keep both; laptop goes black after login; send a "
                "second screen.’ Morning bench check: the laptop panel is fine. The fault "
                "follows the external display to a different computer. They gave me two "
                "mutually exclusive options for the display: hand it back when the new "
                "one arrives, or keep it under my badge at the bench. The choice depends "
                "on a move that has not been decided. Can you authorize the new display "
                "now?"
            ),
        ),
        fixture=HANDOFF_FIXTURE,
        expected=Expected(
            item="monitor",
            decision="human_review",
            reason="Request intent is unclear",
            rubric={
                "unresolved_custody": (
                    "Does the agent treat the alternatives of returning or retaining the "
                    "monitor as unresolved intent and refer the request?"
                ),
            },
        ),
    ),
)

CASES_BY_ID = {case.id: case for case in CASES}
if len(CASES_BY_ID) != len(CASES):
    raise ValueError("Evaluation case IDs must be unique.")
