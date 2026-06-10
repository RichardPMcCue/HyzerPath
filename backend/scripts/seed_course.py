"""Seed a demo course with GPS-mapped holes laid out in a loop around a center point.

Usage (from backend/, venv active or via venv/bin/python):
    venv/bin/python scripts/seed_course.py --name "Zilker" --city Austin --state TX \
        --lat 30.2669 --lng -97.7729 --holes 18

Reads DATABASE_URL from backend/.env like the app does. Idempotent-ish: refuses
to run if a course with the same name already exists.
"""
import argparse
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal  # noqa: E402  (needs sys.path tweak first)
from app.models import Course, Hole, HoleNode, HoleEdge  # noqa: E402

FT_PER_DEG_LAT = 364000.0


def offset(lat: float, lng: float, bearing_deg: float, dist_ft: float):
    """Move dist_ft from (lat,lng) along bearing (0 = north, 90 = east)."""
    rad = math.radians(bearing_deg)
    dy = math.cos(rad) * dist_ft
    dx = math.sin(rad) * dist_ft
    return (
        lat + dy / FT_PER_DEG_LAT,
        lng + dx / (FT_PER_DEG_LAT * math.cos(math.radians(lat))),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", required=True)
    parser.add_argument("--city", default="")
    parser.add_argument("--state", default="")
    parser.add_argument("--address", default="")
    parser.add_argument("--lat", type=float, required=True)
    parser.add_argument("--lng", type=float, required=True)
    parser.add_argument("--holes", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducible layouts")
    args = parser.parse_args()

    random.seed(args.seed)
    db = SessionLocal()
    try:
        if db.query(Course).filter(Course.name == args.name).first():
            print(f"Course '{args.name}' already exists — aborting.")
            sys.exit(1)

        course = Course(
            name=args.name, city=args.city, state=args.state,
            address=args.address, total_par=0, is_approved=True,
        )
        db.add(course)
        db.flush()

        # Walk a loop: each hole plays roughly along the loop direction with
        # jitter, the next tee is a short walk from the previous basket.
        cursor_lat, cursor_lng = args.lat, args.lng
        total_par = 0
        for i in range(args.holes):
            loop_bearing = (360.0 / args.holes) * i
            bearing = (loop_bearing + random.uniform(-25, 25)) % 360
            length = random.randint(220, 480)
            par = 3 if length < 400 else 4
            total_par += par

            tee_lat, tee_lng = cursor_lat, cursor_lng
            pin_lat, pin_lng = offset(tee_lat, tee_lng, bearing, length)

            hole = Hole(
                course_id=course.course_id, hole_number=i + 1, par=par,
                distance=length, elevation=0, is_approved=True,
            )
            db.add(hole)
            db.flush()

            tee = HoleNode(
                hole_id=hole.hole_id, node_type="tee", sequence=0, label="Tee",
                latitude=tee_lat, longitude=tee_lng, is_fairway=True,
            )
            basket = HoleNode(
                hole_id=hole.hole_id, node_type="basket", sequence=1, label="Basket",
                latitude=pin_lat, longitude=pin_lng, is_fairway=True,
            )
            db.add_all([tee, basket])
            db.flush()
            db.add(HoleEdge(
                from_node_id=tee.hole_node_id, to_node_id=basket.hole_node_id,
                distance=length,
            ))

            # Next tee: ~80ft past this basket along the loop
            cursor_lat, cursor_lng = offset(pin_lat, pin_lng, loop_bearing + 90, 80)

        course.total_par = total_par
        db.commit()
        print(f"Created '{args.name}' (course_id={course.course_id}): "
              f"{args.holes} holes, par {total_par}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
