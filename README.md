HyzerPath: Your Intelligent Disc Golf Caddie

Most disc golf apps tell you how far you are from the basket. HyzerPath tells you how to get there.

HyzerPath is a course-aware recommendation engine that models each hole as a series of segments, accounting for mandos, doglegs, gaps, elevation, and landing zones, then recommends the optimal sequence of throws from your bag based on your actual throw capabilities and real-time wind conditions. It doesn't just match distance to disc. It plans your route through the hole the way you think about it on the tee pad: what line, what disc, where to land, and what's left after that.

Built with Python and FastAPI. Integrates with the DiscIt API for disc flight data, weather APIs for live wind conditions, and optionally with TechDisc for measured throw metrics. Course data is community-contributed starting with Austin, TX area courses.


The key features are:
- dynamic bag tracker
- gps based throw distance calculator
- AI based throw recomendations based on path to Basket while on the course and your personal distances with each disc. 

# Full Stack setup:

- Backend: Python, FastAPI
- Database: PostgreSQL
- ORM: SQLAlchemy
- Frontend: SvelteKit + TypeScript
- Auth: OAuth via Google, session tokens
- Deployment: LXC on Proxmox, Cloudflare Tunnel
- CI/CD: GitHub Actions
- External APIs: DiscIt, weather API, Anthropic

# stack justification:

## Python Backend:

- Go would give you better raw performance and concurrency, but HyzerPath doesn't have a performance problem that justifies the cost. The recommendation engine is graph traversal and scoring logic - Python handles that cleanly. The AI query layer uses the Anthropic SDK which has a first-class Python client. The DiscIt integration, weather API, auth, and data modeling all land more naturally in Python.

## Frontend:

- React has a massive ecosystem but enormous boilerplate and a steep learning curve for someone who isn't writing JavaScript daily. Vue is better but still heavier than you need. SvelteKit gives you a mobile-first PWA with less framework fighting, cleaner component syntax, and a smaller mental overhead.

## API: 

- FastAPI specifically because it's async-native, generates OpenAPI docs automatically, and uses Python type hints and dataclasses natively

## running locally - Comming soon

