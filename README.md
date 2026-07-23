# HyzerPath

![Python](https://img.shields.io/badge/Python-3.12-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-green)
![SvelteKit](https://img.shields.io/badge/SvelteKit-2-orange)
![TypeScript](https://img.shields.io/badge/TypeScript-5-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white)
![Tests](https://img.shields.io/badge/tests-101%20passing-brightgreen)
![Live](https://img.shields.io/badge/live-hp.rmccue.dev-brightgreen)
![License](https://img.shields.io/badge/license-MIT-blue)

HyzerPath is an intelligent disc golf caddie. It models each hole as a fairway polygon, derives the optimal playing line from tee to basket with computational geometry, and recommends specific discs from the player's bag for each throw based on their personal measured throw distances. It is live at [hp.rmccue.dev](https://hp.rmccue.dev).

## Tech stack

**Backend**
- Python, FastAPI
- PostgreSQL, SQLAlchemy, Alembic
- Google OAuth, JWT auth

**Frontend**
- SvelteKit 2, Svelte 5, TypeScript
- Tailwind CSS v4
- MapLibre GL, PWA

**Infrastructure**
- nginx, Cloudflare Tunnel
- Self-hosted LXC container, CI/CD via GitHub Actions

**External APIs**
- Open-Meteo (real-time wind data, no auth required)
- DiscIt API (disc flight number database, write-through PostgreSQL cache)

## How it works

Each hole is a fairway polygon drawn on a satellite map, plus real physical points: tee, basket, mandos, and hazard areas (OB, water, trees). There is no hand-authored path — the playing line is derived from the shape of the fairway itself.

To plan a hole, the engine carves hazards out of the playable area, shrinks it by a safety margin set by the play mode (conservative routes down the middle, aggressive hugs the inside of doglegs), then finds the shortest path through what remains with a visibility graph and Dijkstra. If the margin pinches the fairway shut, it backs off until a route exists — that surviving margin is the hole's honest tightness.

The engine then walks the line into individual throws — a flight can shape around a bend but never wrap a hard corner — and scores every disc per throw on distance fit, the shape the corridor demands, and measured clearance to the fairway edge, evaluating both backhand and forehand from the player's per-style distances. Each throw returns a disc, a shot shape, a landing target on the map, and a goal set by the play mode — from a safe par putt to a Circle 1 birdie look.

Throw distances come from the player: a field measuring mode records GPS start and end points per throw, tagged backhand or forehand, feeding the per-disc, per-style averages the engine reads. Wind from Open-Meteo is folded into effective distance at round start.

![HyzerPath architecture](docs/architecture.png)

## Key engineering decisions

- **Fairway as a polygon, line as geometry.** Course mappers draw the playable area; the route, hole length, doglegs, and tightness are all derived from the shape. Nothing to keep consistent by hand, and a whole class of chain-mapping bugs is structurally impossible.
- **Risk mode as erosion.** One geometric parameter — how far the route stays from the fairway edge — replaces a pile of per-mode penalty constants, and degrades honestly on tight holes.
- **Fairway-aware disc selection.** Disc choice weighs measured corridor clearance against each disc's lateral movement and reach, so a tunnel gets a controllable disc and an open hole the longer one.
- **Recovery shots.** A lie outside the fairway is detected geometrically and the first recommendation becomes a pitch-out back into play.
- **Structured JSON logging.** Logs are emitted as JSON to stdout and captured by systemd, with request method, path, status, and latency on every line.
- **Fixed-window rate limiter without Redis.** The deploy endpoint uses a small in-memory limiter, enough for a single-process server and one less service to run.

## Local development

Backend:
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend:
```bash
cd frontend
npm install
npm run dev
```

## Project status

Deployed and live at [hp.rmccue.dev](https://hp.rmccue.dev). Seeded with test course data. GPS-based round tracking is functional and the recommendation engine is fairway-aware with risk-mode landing targets.
