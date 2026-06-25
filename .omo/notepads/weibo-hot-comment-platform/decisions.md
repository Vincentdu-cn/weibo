# Decisions — weibo-hot-comment-platform

## Architecture
- Backend: FastAPI + SQLAlchemy + httpx (async)
- Frontend: React 18 + Vite + TypeScript + shadcn/ui + Zustand + React Router
- DB: SQLite (local single-machine)
- WebSocket: FastAPI native + frontend useWebSocket hook
- Anti-detection: Single IP, strict rate limiting, cookie rotation, UA rotation, random delays

## Weibo API
- Comment likes use `updateLike` (NOT setLike) with `object_type: "comment"`
- Hot comments: `buildComments?flow=0` (flow=0 = hot sort, flow=1 = time sort)
- Hot ranking algorithm unknown — keep configurable (HotConfig)
- url_to_mid: base62 decoding (reference: nghuyong/WeiboSpider)

## Execution Strategy
- 4 waves: Wave 1 (7 tasks done) -> Wave 2 (7 tasks) -> Wave 3 (7 tasks) -> Wave 4 (3 tasks) + Final (4 reviews)
- Wave 2 parallel batch: T8, T12, T14 (no dependencies between them)
- Wave 2 sequential chain: T8 -> T9 -> T10 -> T11
- Wave 2 sequential: T12 -> T13 (same file action_executor.py)
- Total comments <= 500 (enforced in CompetitionSession)
- Semi-automatic: alert -> human inputs comment + selects accounts -> system executes
