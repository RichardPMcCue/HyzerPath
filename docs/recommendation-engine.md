# Recommendation engine

How the caddie turns a hole + your bag into a per-throw plan. Three stages plus
wind: **route the hole → break the route into real throws → pick a disc/shape
for each throw.** Routing and segmentation use your *reach*; the disc choice
uses the *range model* and *fairway tightness*.

All weights below are the live tuning constants in
[`backend/app/recommendation.py`](../backend/app/recommendation.py) and
[`backend/app/graph.py`](../backend/app/graph.py).

---

## Stage 1 — Routing: Dijkstra edge weights

`graph.py → compute_edge_weight`. Each edge's weight is **estimated throws +
penalties**, not raw distance:

```
weight = base + centerline_penalty + hazard_penalty
```

| Term | Formula | Why |
|---|---|---|
| `base` | `1.0`, or `edge.distance / reach` if the edge is longer than your reach | One throw = cost 1. An edge you can't cover in one throw costs proportionally more, so Dijkstra prefers routes you can execute. |
| `centerline_penalty` | `centerline_distance / fairway_width` (or `/100` if no width) | Nodes off the fairway centerline cost more, scaled by how wide the corridor is. |
| `hazard_penalty` | `num_hazards × MODE_HAZARD_PENALTY[mode]` | Per-mode trouble avoidance. |

`MODE_HAZARD_PENALTY`: conservative `1.5`, balanced `1.0`, aggressive `0.15`.
Safe routes *around* hazards; aggressive barely notices them.

---

## Player reach

`player_reach` — drives segmentation and the `base` edge weight above.

- `best_avg` = your longest disc's average.
- **conservative:** `best_avg × 0.9` (`MODE_FACTORS`)
- **balanced:** `best_avg × 1.0`
- **aggressive:** `max(best_max, best_avg)` — uses your *max* line, not average.

---

## Stage 2 — Segmentation: the lookahead

`plan_segments`. Walks the Dijkstra path and greedily jumps to the **furthest
node reachable in one throw**. A jump from node `i` to `j` is allowed only if
all hold:

1. `distance ≤ reach_limit` (wind-adjusted; balanced also multiplies the limit by `0.95`).
2. **Corridor deviation** ≤ `CORRIDOR_DEVIATION_FT[mode]` — how far the straight skip-line may stray from the fairway nodes it skips over: conservative `70 ft`, balanced `110 ft`, aggressive `∞`.
3. Not aggressive → the throw line can't pass *through* a drawn hazard polygon.
4. Conservative → can't skip past any edge tagged with a hazard.

> Conservative's deviation used to be `35 ft`, which forced extra sub-50 ft
> layups (it couldn't merge a weaving node chain into one throw). Loosened to `70`.

---

## Stage 3 — Per-segment disc + shape choice

### 3a. Throw role — `classify_throw`

- final & `≤66 ft` → **putt**; final & `>66` → **approach**
- non-final & `≥ 0.8 × reach` → **drive**; else **placement**

### 3b. Fairway tightness (0→1) — `fairway_tightness`

```
width_term = clamp((70 − width) / (70 − 25))     # OPEN_WIDTH 70, TIGHT_WIDTH 25
tree_term  = 1 − (nearest_tree_dist / 30)         # if a 'trees' polygon is within 30 ft of the line
tightness  = max(width_term, tree_term)
```

> Tightness uses **only explicitly-tagged width + tree polygons** — never the
> dynamic node-spacing estimate. That estimate measured the gap between path
> nodes (~30–40 ft) and made every hole read as a tunnel, which caused the
> "spike hyzer everywhere / always overstable disc" bug.

### 3c. The range model — `throw_effort`

Each disc covers a range from **avg (controlled)** to **max (max-effort,
lateral-heavy)**:

```
effort = 0                        if required ≤ avg          (controlled line)
       = (required−avg)/(max−avg) if avg < required ≤ max    (reaching toward max)
       > 1                        if required > max          (can't really cover it)
```

**Capability:** a disc competes if `max_carry ≥ required − 10 ft`
(`REACH_TOLERANCE_FT`). Any disc whose *max* reaches is in play, not just your
longest disc — the fix for "always the Dimension."

### 3d. The disc score — `score_disc` (higher wins)

```
score = distance_score + flight_score + control_score + effort_score + lateral_score
```

| Term | Formula | Decision |
|---|---|---|
| `distance_score` | `−max(0, avg − required) / 45` | **"Too much club."** Only penalizes a disc whose *average overshoots* the target — picks the right-sized disc, not the longest. (`OVER_DISC_FT = 45`) |
| `flight_score` | `−abs(net_stability − desired_stability)` | `net = turn + fade`. `desired = clamp(−normalized_finish / 15, −3..4)`. Matches the disc's bend to the corridor's bend. |
| `control_score` | `−speed × CONTROL_PENALTY[type]` | Approaches/putts want slow, accurate discs. drive `0`, placement `0.06`, approach `0.12`, putt `0.3`. |
| `effort_score` | `−(0.8 + tight_scale × 3.0 × tightness) × effort` | Max-effort throws are less reliable **always** (baseline `0.8`), and add lateral movement that hurts **only on tight fairways** (`W_EFFORT = 3.0`). |
| `lateral_score` | `−tight_scale × 0.5 × tightness × (|turn|+fade)` | On a tunnel, wide-flying discs are penalized; in the open it's ~free. (`W_LAT = 0.5`) |

`tight_scale = MODE_TIGHTNESS_SCALE[mode]`: conservative `1.3`, balanced `1.0`,
aggressive `0.4`. Aggressive shrugs off tunnel penalties; conservative leans
into control.

Plus an off-hand tiebreak: `−0.15 × (style_priority − 1)` so your primary hand
wins ties. Backhand and forehand are scored separately using each style's
measured distances.

### 3e. Shot shape — `derive_shot_shape` (coupled to the chosen disc)

Operates on the **normalized** finish angle (so forehand / left-handed throws
mirror correctly). `SHAPE_THRESHOLD = 12°`, `BIG_SHAPE_THRESHOLD = 40°`:

- finish `≤ −40°` → **spike_hyzer** if `distance ≤ 250` else **hyzer** (spike is a short touch shot only)
- finish `≤ −12°` → **hyzer**
- finish `≥ +12°` → **flex** if disc is overstable (`net ≥ +1`), else **turnover** (≥40°) / **anhyzer**
- straight corridor → **hyzer_flip** if disc is understable (`net ≤ −1`) and `effort > 0.2`, else **straight**

### 3f. Landing zone — `landing_zone_for`

- non-final → `fairway`
- putt → `c1` (≤33 ft) or `c2`
- final approach → aggressive `c1`, balanced/conservative `c2` (lay up to a par putt)

Circles: `C1 = 33 ft`, `C2 = 66 ft`, `C3 = 100 ft`.

---

## Wind (woven through all stages)

- `effective_throw_distance`: headwind `−3 ft/mph` (`HEADWIND_FT_PER_MPH`), tailwind `+1.5 ft/mph` (`TAILWIND_FT_PER_MPH`) — headwinds hurt more than tailwinds help.
- Crosswind shifts the finish angle `1.5°/mph` (`CROSSWIND_DRIFT_DEG_PER_MPH`), which can change the recommended shape.
- `wind_components` decomposes wind (via `cos`/`sin` of the angle to the throw bearing) into headwind + crosswind. Applied to reach (segmentation), carry (effort), and the displayed plays-like `effective_distance`.

---

## The five decisions to anchor on

1. **Three-stage pipeline:** route (Dijkstra) → segment (lookahead) → score discs. Every stage is mode-aware.
2. **Range model:** a disc is an `avg → max` band; capability is by max, effort is your position in the band. Reaching toward max = lateral movement = penalized on tight holes.
3. **Tightness from trees + explicit width only** — never node spacing (that was the headline bug).
4. **"Too-much-club"** distance term: penalize overshoot so the *right-sized* disc wins, not the longest.
5. **Mode = scoring intent**, not just distance: hazard penalty, reach (avg vs max), corridor tolerance, tightness scale, and landing-zone target all shift with conservative / balanced / aggressive.

---

## ELI5 / elevator pitch

For a non-technical audience, drop the math and use the caddie analogy:

> HyzerPath is a smart caddie for disc golf. You teach it two things: a map of
> each hole, and how far you personally throw each disc in your bag. Then for
> any hole it hands you a shot-by-shot plan — which disc to throw, how to shape
> the shot, and where to aim.
>
> The clever part is it plans around *you*, not some pro. It knows a hole isn't
> a straight line — there are trees, water, doglegs — so it finds the safest
> route you can actually pull off, like a GPS picking roads instead of a
> straight line through buildings. Then it picks the right disc for each shot
> the way a golfer picks the right club: a controlled disc for a tight,
> tree-lined gap, a bigger one when there's room to open up.
>
> And it has three modes — Safe, Balanced, and Send-it — so it plans
> differently depending on whether you want to protect your score or go for the
> big shot.

**Follow-ups:**

- *"How does it know the route?"* — Same math GPS uses to find the shortest drive, except "shortest" means fewest throws *you* can actually make, with a penalty for flying over trouble.
- *"What makes it personal?"* — It uses your own measured throw distances. Two players get totally different plans for the same hole.
- **One sentence:** It's Google Maps for a disc golf hole — it plans the smartest route to the basket using how far you actually throw each disc.
