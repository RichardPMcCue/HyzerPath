"""Polygon fairway geometry.

A fairway is a stored GPS polygon; the playing line is DERIVED, not authored:
erode the region by a mode-dependent safety margin, then take the shortest
path inside it (visibility graph over the polygon's vertices, routed by the
same dijkstra that used to walk the hand-authored node chain). The erosion IS
the risk mode: conservative routes down the middle, aggressive hugs the
inside of doglegs.

All geometry runs in a local planar frame (feet, equirectangular around the
polygon's first vertex — the same 364000 ft/degree convention as utils.py and
the frontend's geo.ts). Holes are a few hundred feet across; projection error
is negligible.
"""
import math

from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.validation import make_valid

from app.graph import dijkstra

LAT_FT = 364000.0  # feet per degree of latitude

# Safety margin from the fairway edge, per play mode. If eroding by this much
# disconnects tee from basket, the margin steps down until a route exists —
# the margin that survives is the hole's honest "safe line" width.
MODE_EROSION_FT = {
    "conservative": 25.0,
    "balanced": 15.0,
    "aggressive": 5.0,
}
EROSION_STEP_FT = 5.0

# Clearance (distance to the fairway edge — a half-width) mapped to the
# engine's 0..1 tightness: at/under TIGHT it's a tunnel, at/over OPEN there's
# room to work the disc.
CLEAR_TIGHT_FT = 12.0
CLEAR_OPEN_FT = 35.0


def _largest(geom) -> Polygon:
    """Collapse make_valid/difference output to its biggest polygon piece."""
    if isinstance(geom, Polygon):
        return geom
    if isinstance(geom, MultiPolygon):
        return max(geom.geoms, key=lambda g: g.area)
    polys = [g for g in getattr(geom, "geoms", []) if isinstance(g, Polygon)]
    return max(polys, key=lambda g: g.area) if polys else Polygon()


class FairwayRegion:
    """The routable playing area of one hole, in the local feet frame."""

    def __init__(self, fairway_ring: list, hazard_rings: list = (), subtract_hazards: bool = False):
        """fairway_ring / hazard_rings are [[lat, lng], ...] open rings."""
        self.lat0, self.lng0 = float(fairway_ring[0][0]), float(fairway_ring[0][1])
        self._lng_ft = LAT_FT * math.cos(math.radians(self.lat0))

        poly = _largest(make_valid(Polygon([self._xy(p[0], p[1]) for p in fairway_ring])))
        if subtract_hazards:
            for ring in hazard_rings:
                if len(ring) >= 3:
                    hz = _largest(make_valid(Polygon([self._xy(p[0], p[1]) for p in ring])))
                    diff = poly.difference(hz)
                    # Only accept the cut if a dominant piece survives — a
                    # hazard that slices the fairway in two shouldn't erase
                    # half the hole from the map.
                    poly = _largest(diff)
        self.poly = poly

    # --- frame ---

    def _xy(self, lat: float, lng: float) -> tuple:
        return ((lng - self.lng0) * self._lng_ft, (lat - self.lat0) * LAT_FT)

    def _ll(self, x: float, y: float) -> tuple:
        return (self.lat0 + y / LAT_FT, self.lng0 + x / self._lng_ft)

    # --- queries ---

    def contains(self, lat: float, lng: float) -> bool:
        return self.poly.covers(Point(self._xy(lat, lng)))

    def clearance_ft(self, lat: float, lng: float) -> float:
        """Distance to the fairway edge (0 when outside the region)."""
        pt = Point(self._xy(lat, lng))
        if not self.poly.covers(pt):
            return 0.0
        return self.poly.boundary.distance(pt)

    def nearest_inside(self, lat: float, lng: float, depth_ft: float = 10.0) -> tuple:
        """Closest in-region point, pulled depth_ft past the edge when possible.
        Recovery-shot target for a lie outside the fairway."""
        inset = self.poly.buffer(-depth_ft)
        target_poly = inset if not inset.is_empty else self.poly
        target_poly = _largest(target_poly)
        pt = Point(self._xy(lat, lng))
        nearest = target_poly.exterior.interpolate(target_poly.exterior.project(pt))
        if target_poly.covers(pt):
            return (lat, lng)
        return self._ll(nearest.x, nearest.y)

    # --- routing ---

    def route(self, start: tuple, end: tuple, erosion_ft: float) -> list:
        """Shortest path start→end staying inside the eroded region, as
        [(lat, lng), ...] including the true start and end. Erosion steps down
        until a route exists; falls back to the straight line if even the raw
        region won't connect them (degenerate mapping)."""
        e = erosion_ft
        while e >= 0:
            path = self._route_at(start, end, e)
            if path is not None:
                return path
            e -= EROSION_STEP_FT
            if 0 < e < EROSION_STEP_FT:
                e = 0  # try the raw region last
        return [start, end]

    def _route_at(self, start: tuple, end: tuple, erosion_ft: float):
        # mitre join keeps eroded corners sharp (one vertex, one big turn)
        # instead of rounding them into arcs of tiny turns
        region = self.poly.buffer(-erosion_ft, join_style=2) if erosion_ft > 0 else self.poly
        if region.is_empty:
            return None
        # Snap endpoints into the region (tee pads live on concrete outside
        # the grass; the eroded region shrinks away from the basket).
        s_xy = Point(self._xy(*start))
        e_xy = Point(self._xy(*end))
        pieces = list(region.geoms) if isinstance(region, MultiPolygon) else [region]
        s_piece = min(pieces, key=lambda g: g.distance(s_xy))
        e_piece = min(pieces, key=lambda g: g.distance(e_xy))
        if s_piece is not e_piece:
            return None  # erosion split the corridor: step down
        region = s_piece

        def snap(pt: Point) -> Point:
            if region.covers(pt):
                return pt
            return region.exterior.interpolate(region.exterior.project(pt))

        s = snap(s_xy)
        t = snap(e_xy)

        # Visibility graph over region vertices (+ snapped endpoints). covers()
        # is tested against a hair-buffered region so segments along the
        # boundary don't fail on float noise.
        verts = [(s.x, s.y), (t.x, t.y)]
        verts += list(region.exterior.coords[:-1])
        for hole in region.interiors:
            verts += list(hole.coords[:-1])
        test_region = region.buffer(0.01)
        edges = []
        for i in range(len(verts)):
            for j in range(i + 1, len(verts)):
                seg = LineString([verts[i], verts[j]])
                if test_region.covers(seg):
                    w = seg.length
                    edges.append((i, j, w))
                    edges.append((j, i, w))
        path_ids = dijkstra(edges, 0, 1)
        if not path_ids:
            return None

        route_xy = [verts[i] for i in path_ids]
        route = [self._ll(x, y) for x, y in route_xy]
        # Keep the true endpoints: distance is measured from the real tee/lie
        # to the real basket, with the snapped points as intermediate steps.
        if route[0] != start:
            route.insert(0, start)
        if route[-1] != end:
            route.append(end)
        return _dedupe(route)

    # --- route measurement (planar frame) ---

    def route_length_ft(self, route: list) -> float:
        pts = [self._xy(lat, lng) for lat, lng in route]
        return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))

    def point_along_route(self, route: list, dist_ft: float) -> tuple:
        """Interpolated (lat, lng) at dist_ft along the route polyline."""
        pts = [self._xy(lat, lng) for lat, lng in route]
        remaining = max(0.0, dist_ft)
        for a, b in zip(pts, pts[1:]):
            seg = math.dist(a, b)
            if seg >= remaining and seg > 0:
                f = remaining / seg
                return self._ll(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            remaining -= seg
        return route[-1]

    def min_clearance_ft(self, a: tuple, b: tuple, samples: int = 5) -> float:
        """Tightest clearance along the straight throw line a→b."""
        best = None
        for k in range(1, samples + 1):
            f = k / samples
            lat = a[0] + (b[0] - a[0]) * f
            lng = a[1] + (b[1] - a[1]) * f
            c = self.clearance_ft(lat, lng)
            if best is None or c < best:
                best = c
        return best or 0.0

    def cumulative_ft(self, route: list) -> list:
        """Distance along the route at each vertex: [0, d1, ..., total]."""
        pts = [self._xy(lat, lng) for lat, lng in route]
        out = [0.0]
        for a, b in zip(pts, pts[1:]):
            out.append(out[-1] + math.dist(a, b))
        return out

    def min_clearance_along(self, route: list, d0: float, d1: float, step_ft: float = 25.0) -> float:
        """Tightest clearance following the route between distances d0..d1 —
        the honest corridor width for a throw that shapes around a bend."""
        best = None
        d = d0
        while True:
            lat, lng = self.point_along_route(route, min(d, d1))
            c = self.clearance_ft(lat, lng)
            if best is None or c < best:
                best = c
            if d >= d1:
                break
            d += step_ft
        return best or 0.0


def _dedupe(route: list) -> list:
    out = [route[0]]
    for p in route[1:]:
        if abs(p[0] - out[-1][0]) > 1e-9 or abs(p[1] - out[-1][1]) > 1e-9:
            out.append(p)
    return out


def corridor_ring(points_ll: list, half_width_ft: float = 30.0) -> list:
    """Buffer a chain of (lat, lng) points into an open polygon ring — the
    default fairway for holes that only have a tee and a basket mapped."""
    lat0, lng0 = float(points_ll[0][0]), float(points_ll[0][1])
    lng_ft = LAT_FT * math.cos(math.radians(lat0))
    xy = [((lng - lng0) * lng_ft, (lat - lat0) * LAT_FT) for lat, lng in points_ll]
    corridor = LineString(xy).buffer(half_width_ft).simplify(5.0)
    return [
        [lat0 + y / LAT_FT, lng0 + x / lng_ft]
        for x, y in corridor.exterior.coords[:-1]
    ]


def clearance_to_tightness(clearance_ft: float) -> float:
    """Map measured edge clearance (a half-width) to the engine's 0..1
    tightness: <=12 ft is a tunnel, >=35 ft is open."""
    t = (CLEAR_OPEN_FT - clearance_ft) / (CLEAR_OPEN_FT - CLEAR_TIGHT_FT)
    return max(0.0, min(1.0, t))
