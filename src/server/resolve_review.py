"""Record a decision made by a human operator."""

import argparse
from pathlib import Path

from .database import initialize
from .models import InvalidField, ReviewAlreadyResolved, UnknownReview
from .services.reviews import resolve_review


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("equipment.sqlite3"))
    parser.add_argument("review_id")
    parser.add_argument("decision", choices=("approve", "deny"))
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--rationale", required=True)
    args = parser.parse_args()
    initialize(args.database)
    try:
        resolve_review(
            args.database, args.review_id, args.decision, args.reviewer, args.rationale
        )
    except (InvalidField, UnknownReview, ReviewAlreadyResolved) as error:
        parser.exit(1, f"{error}\n")
    print(f"{args.review_id}: {args.decision}")


if __name__ == "__main__":
    main()
