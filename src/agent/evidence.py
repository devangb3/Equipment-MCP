"""Ground equipment actions and decisions in the observations for one request."""

from dataclasses import dataclass

from server.models.requests import Eligibility

from .foundry import AgentError, Item


@dataclass
class Evidence:
    eligibility: Eligibility | None = None
    role: str | None = None
    policy_seen: bool = False
    review_id: str | None = None

    def verified_response(self) -> str:
        e = self.eligibility
        if e is None:
            raise AgentError("Draft reached before checking eligibility.")
        if e.decision == "human_review":
            if not self.review_id:
                raise AgentError("Draft reached before a confirmed referral.")
            return f"Referred for human review ({self.review_id}). {e.reason}."
        if not self.policy_seen:
            raise AgentError(
                "Draft reached before verifying the employee's role policy."
            )
        if e.decision == "deny":
            if e.next_eligible_date is None:
                raise AgentError("Denial lacks a next eligible date.")
            return f"Denied. {e.reason}. Next eligible date: {e.next_eligible_date}."
        return f"Approved. {e.reason}."

    def bind(self, name: str, args: Item, employee_id: str, request: str) -> None:
        if name == "get_policy_limits":
            if not self.role or args.get("role") != self.role:
                raise AgentError("Policy lookup requires the observed employee role.")
        else:
            args["employee_id"] = employee_id
        if name == "flag_for_human_review":
            if not self.eligibility or self.eligibility.decision != "human_review":
                raise AgentError(
                    "Referral requires a human-review eligibility decision."
                )
            args.update(request=request, reason=self.eligibility.reason)

    def record(self, name: str, result: Item) -> None:
        if name == "check_request_eligibility":
            self.eligibility = (
                None if "error" in result else Eligibility.model_validate(result)
            )
        elif name == "flag_for_human_review":
            receipt = result.get("result")
            if not isinstance(receipt, str) or not receipt.strip():
                raise AgentError("Review tool returned no case ID.")
            self.review_id = receipt
        elif name == "get_employee_info":
            role = result.get("role")
            self.role = role if isinstance(role, str) else None
            self.policy_seen = False
        elif name == "get_policy_limits":
            self.policy_seen = "error" not in result
