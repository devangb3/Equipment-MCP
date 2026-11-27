import asyncio
import json

from agent.foundry import Item
from agent.refinement import FEEDBACK, REVISE, reflect


def test_revisions_keep_feedback_and_recheck_the_latest_draft() -> None:
    replies = iter(
        [
            "Remove the delivery promise.",
            "Approved.",
            "Explain the reason.",
            "Approved as a first issue.",
            "CONFIRM",
        ]
    )
    calls = []

    async def respond(
        prompt: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        context = json.loads(str(history[0]["content"]))
        calls.append((prompt, context, tools))
        return [
            {
                "type": "message",
                "content": [{"type": "output_text", "text": next(replies)}],
            }
        ]

    answer = asyncio.run(
        reflect(
            "My first monitor",
            "Ships today.",
            "Approved. First issue.",
            respond,
            lambda _: None,
        )
    )

    assert (
        answer,
        [p for p, _, _ in calls],
        [t for _, _, t in calls],
        calls[-1][1],
    ) == (
        "Approved as a first issue.",
        [FEEDBACK, REVISE, FEEDBACK, REVISE, FEEDBACK],
        [[], [], [], [], []],
        {
            "request": "My first monitor",
            "verified_decision": "Approved. First issue.",
            "attempts": [
                {"draft": "Ships today.", "feedback": "Remove the delivery promise."},
                {"draft": "Approved.", "feedback": "Explain the reason."},
                {"draft": "Approved as a first issue."},
            ],
        },
    )


def test_persistently_rejected_revisions_return_verified_decision() -> None:
    calls = []

    async def respond(
        prompt: str, history: list[Item], tools: list[Item]
    ) -> list[Item]:
        calls.append(prompt)
        text = "Correct the review ID to R1." if prompt == FEEDBACK else "Review R2."
        return [{"type": "message", "content": [{"type": "output_text", "text": text}]}]

    answer = asyncio.run(
        reflect("Second laptop", "Approved.", "Review R1.", respond, lambda _: None)
    )

    assert (answer, calls) == ("Review R1.", [FEEDBACK, REVISE] * 3 + [FEEDBACK])
