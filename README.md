# HyzerPath: Your Intelligent Disc Golf Caddie

Most disc golf apps tell you how far you are from the basket. HyzerPath tells you how to get there.

HyzerPath is a course-aware recommendation engine that models each hole as a series of segments, accounting for mandos, doglegs, gaps, elevation, and landing zones, then recommends the optimal sequence of throws from your bag based on your actual throw capabilities and real-time wind conditions. It doesn't just match distance to disc. It plans your route through the hole the way you think about it on the tee pad: what line, what disc, where to land, and what's left after that.

Built with Python and FastAPI. Integrates with the DiscIt API for disc flight data, weather APIs for live wind conditions, and optionally with TechDisc for measured throw metrics. Course data is community-contributed starting with Austin, TX area courses.

## Key Features

- Dynamic bag management with automatic flight number lookup
- GPS-based throw distance calculation
- AI-powered throw recommendations based on hole pathing, real-time conditions, and your personal throw data

## Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI |
| Database | PostgreSQL |
| ORM | SQLAlchemy |
| Frontend | SvelteKit + TypeScript |
| Auth | OAuth via Google, session tokens |
| Deployment | LXC on Proxmox, Cloudflare Tunnel |
| CI/CD | GitHub Actions |
| External APIs | DiscIt, Weather API, Anthropic |

## Stack Justification

### Python Backend

I considered Go since it would give better raw performance and concurrency, but this app doesn't have the kind of performance demands that justify it. The recommendation engine is mostly graph traversal and scoring logic, Python handles that fine. The Anthropic SDK has a first-class Python client and all the external integrations (DiscIt, weather, auth) just land more naturally in Python. No reason to make this harder than it needs to be.

### SvelteKit Frontend

React's boilerplate and ecosystem overhead felt like overkill. Vue is better but still more than I need. SvelteKit lets me build a mobile-first PWA with cleaner syntax and less framework fighting. I want to spend my time on the actual product, not wrestling with frontend tooling.

### FastAPI

Async-native, auto-generates OpenAPI docs, and leans on Python type hints which I'm already using everywhere else. It just fits. The API is the backbone of this whole project so I wanted something that stays out of the way and lets me move fast.

## Running Locally

Coming soon.
