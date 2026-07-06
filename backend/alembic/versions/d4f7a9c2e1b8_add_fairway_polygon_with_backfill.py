"""add fairway_polygon to holes and backfill from the node chain

Every existing hole's landing-zone chain is converted to a polygon by
buffering the chain line 30 ft (the display corridor the app already drew),
and the hole's distance is recomputed from the derived route through it.
Self-contained on purpose: only shapely + app.fairway (which imports nothing
from the app's schema/recommendation cycle).

Revision ID: d4f7a9c2e1b8
Revises: c7f1a3e8d2b5
Create Date: 2026-07-02 12:00:00.000000

"""
import json
import math
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd4f7a9c2e1b8'
down_revision: Union[str, Sequence[str], None] = 'c7f1a3e8d2b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

HALF_WIDTH_FT = 30.0  # buffered corridor half-width, matches the old display default
LAT_FT = 364000.0


def upgrade() -> None:
    op.add_column('holes', sa.Column('fairway_polygon', sa.Text(), nullable=True))

    from shapely.geometry import LineString
    from app.fairway import FairwayRegion, MODE_EROSION_FT

    bind = op.get_bind()
    hole_ids = [r[0] for r in bind.execute(sa.text("SELECT hole_id FROM holes"))]
    for hole_id in hole_ids:
        rows = bind.execute(sa.text(
            "SELECT node_type, sequence, latitude, longitude FROM hole_nodes "
            "WHERE hole_id = :h AND latitude IS NOT NULL AND longitude IS NOT NULL "
            "AND is_fairway = :t ORDER BY sequence"
        ), {"h": hole_id, "t": True}).fetchall()
        if len(rows) < 2:
            continue

        lat0, lng0 = float(rows[0][2]), float(rows[0][3])
        lng_ft = LAT_FT * math.cos(math.radians(lat0))
        xy = [((r[3] - lng0) * lng_ft, (r[2] - lat0) * LAT_FT) for r in rows]

        # simplify(5ft) trims the buffer's rounded-cap vertex noise so derived
        # visibility graphs stay small
        corridor = LineString(xy).buffer(HALF_WIDTH_FT).simplify(5.0)
        ring = [
            [lat0 + y / LAT_FT, lng0 + x / lng_ft]
            for x, y in corridor.exterior.coords[:-1]  # open ring, like hazards
        ]
        params = {"h": hole_id, "p": json.dumps(ring)}

        tee = next((r for r in rows if r[0] == "tee"), None)
        basket = next((r for r in rows if r[0] == "basket"), None)
        if tee is not None and basket is not None:
            region = FairwayRegion(ring)
            route = region.route(
                (tee[2], tee[3]), (basket[2], basket[3]),
                MODE_EROSION_FT["balanced"],
            )
            params["d"] = round(region.route_length_ft(route))
            bind.execute(sa.text(
                "UPDATE holes SET fairway_polygon = :p, distance = :d WHERE hole_id = :h"
            ), params)
        else:
            bind.execute(sa.text(
                "UPDATE holes SET fairway_polygon = :p WHERE hole_id = :h"
            ), params)


def downgrade() -> None:
    op.drop_column('holes', 'fairway_polygon')
