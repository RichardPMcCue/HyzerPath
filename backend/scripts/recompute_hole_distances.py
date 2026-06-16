"""Recompute holes.distance from their fairway node chains.

One-time maintenance after a change to the best-fit distance math; safe to
re-run any time (idempotent). Holes without a full tee→basket GPS chain are
left untouched by recompute_hole_geometry.

Usage: venv/bin/python scripts/recompute_hole_distances.py [--dry-run] [--hole-id N]
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402
from app.models import Hole  # noqa: E402
from app.routers.course import recompute_hole_geometry  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="report changes without saving")
    parser.add_argument("--hole-id", type=int, help="recompute a single hole")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Hole)
        if args.hole_id:
            query = query.filter(Hole.hole_id == args.hole_id)
        changed = 0
        for hole in query.all():
            old = hole.distance
            recompute_hole_geometry(db, hole)
            if hole.distance != old:
                changed += 1
                print(f"hole_id={hole.hole_id} #{hole.hole_number}: {old} -> {hole.distance}")
        if args.dry_run:
            db.rollback()
            print(f"dry run: {changed} hole(s) would change")
        else:
            db.commit()
            print(f"updated {changed} hole(s)")
    finally:
        db.close()


if __name__ == "__main__":
    main()
