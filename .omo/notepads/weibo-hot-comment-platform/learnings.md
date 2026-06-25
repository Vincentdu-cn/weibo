# Learnings — weibo-hot-comment-platform

## 2025-06-25 Wave 1 Complete

### Project Structure
- Backend: `backend/app/` with `main.py`, `core/`, `api/`, `services/`, `models/`, `schemas/`
- Frontend: `frontend/src/` with `App.tsx`, `main.tsx`, `pages/`, `hooks/`, `types/`, `api/`
- Tests: `backend/tests/` — 90 tests all pass
- Python 3.13, pytest with asyncio mode=auto
- React 18 + Vite 5 + TypeScript 5 + vitest

### WeiboHttpClient API (Task 3)
- `_get(path: str, params: dict, cookie: str) -> dict` — GET with retry
- `_post(path: str, data: dict, cookie: str) -> dict` — POST with retry
- `_build_headers(cookie)` extracts XSRF-TOKEN from cookie string
- base_url = "https://weibo.com"
- 3 retries on httpx.HTTPError

### AntiDetectionEngine API (Task 5)
- `cookie_pool.get_monitor_cookie() -> str` — auto-rotates after 10 uses, auto-resets
- `cookie_pool.get_action_cookie(exclude_uids) -> str` — least-used, raises when exhausted
- `cookie_pool.mark_used(uid)` — increment use count
- `cookie_pool.add_cookie(uid, cookie_str, tier)` — tier="monitor"|"action"
- `wait_monitor()` — 10-30s delay
- `wait_action()` — 5-15s delay
- `wait_comment()` — 10-20s delay
- `get_user_agent()` — random Chrome 120-122 UA
- MAX_USES_PER_COOKIE = 10

### Schemas (Task 7)
- CommentDTO: id, weibo_comment_id, user_uid, user_name, content, like_count, rank, is_hot, is_team_member, created_at
- AccountDTO: id, weibo_uid, nickname, status, avatar_url
- AlertDTO: id, account_uid, comment_id, alert_type, message, status, comment_input, selected_account_ids
- StatsDTO: total_comments, team_hot_count, remaining_quota, elapsed_time, hot_ratio, team_online_count, pending_alerts, executed_actions
- WSMessage: type, data

### Models (Task 2)
- Account: id, weibo_uid, nickname, cookie_json, cookie_expires_at, status, avatar_url, created_at
- Comment: id, weibo_comment_id, weibo_post_id, user_uid, user_name, content, like_count, created_at, fetched_at
- CommentSnapshot: id, comment_id(FK), like_count, rank, is_hot, is_team_member, snapshot_at
- Alert: id, session_id(FK), account_uid, comment_id(FK), alert_type, message, status, created_at
- ActionLog: id, account_uid, action_type, target_comment_id, content, status, response, created_at
- CompetitionSession: id, target_weibo_url, target_weibo_mid, started_at, ended_at, total_comments, status

### WebSocket (Task 6)
- WSConnectionManager: connect, disconnect, broadcast, send_to_specific
- broadcast sends to all connected clients
- Frontend hook: `useWebSocket.ts` with auto-reconnect + heartbeat

### Key Weibo API Endpoints
- buildComments: `GET /ajax/statuses/buildComments?flow=0&is_reload=1&id={mid}&count=20&uid={uid}&max_id={max_id}`
- updateLike: `POST /ajax/statuses/updateLike` body: `{"object_id": str(comment_id), "object_type": "comment"}`
- destroyLike: `POST /ajax/statuses/destroyLike` same body
- comments/create: `POST /ajax/comments/create` body: `{"id": str(mid), "comment": content, ...}`
- comments/reply: `POST /ajax/comments/reply` body: `{"id": str(mid), "cid": str(comment_id), "comment": content, ...}`

### ActionExecutor API (Task 12)
- `ActionExecutor(client, anti_detection=None, db_session=None)` — extensible design for Task 13
- `like_comment(comment_id, cookie, uid="unknown") -> {"success": bool, "error_msg": str|None}`
  - POST `/ajax/statuses/updateLike` with `{"object_id": str(comment_id), "object_type": "comment"}`
  - Success: response JSON `ok` field > 0
  - Logs to ActionLog with action_type="like", status="success"|"failed"
- `batch_like(comment_id, cookies) -> [{"uid": str, "success": bool, "error_msg": str|None}]`
  - `cookies` is `list[tuple[str, str]]` of `(uid, cookie_str)` — uid needed for logging and return
  - Sequential execution with `wait_action()` between each like (N-1 delays for N cookies)
  - Does NOT parallelize — sequential + delays for anti-detection safety
  - Continues on individual failures (does not abort batch)
- `unlike_comment(comment_id, cookie, uid="unknown") -> {"success": bool, "error_msg": str|None}`
  - POST `/ajax/statuses/destroyLike` with same body as like
  - Logs to ActionLog with action_type="unlike"
- Internal `_do_action()` centralises shared like/unlike logic (POST, check ok, log, return)
- `db_session=None` → logging silently skipped (useful for testing without DB)
- Design extensible for Task 13: comment posting methods will be added to same file

### ActionExecutor Comment API (Task 13)
- `post_comment(weibo_mid, content, cookie, uid="unknown") -> {"success": bool, "comment_id": str|None, "error_msg": str|None}`
  - POST `/ajax/comments/create` with `{"id": str(mid), "comment": content, "pic_id": "", "is_repost": 0, "comment_ori": 0, "is_comment": 0}`
  - Success: `ok > 0` OR response contains `comment.id`
  - Extracts `comment_id` from `response["comment"]["id"]` if present
  - Logs to ActionLog with action_type="comment", target_comment_id="" (new comment)
  - **500-comment limit**: checks `CompetitionSession.total_comments >= 500` before posting; returns failure without API call
  - After success, increments `total_comments` by 1
- `reply_comment(weibo_mid, comment_id, content, cookie, uid="unknown") -> CommentResult`
  - POST `/ajax/comments/reply` with `{"id": str(mid), "cid": str(comment_id), "comment": content, ...}`
  - Same success check and return format as post_comment
  - Logs to ActionLog with action_type="reply", target_comment_id=str(comment_id)
  - Same 500-comment limit check
- `batch_comment(weibo_mid, content, cookies) -> [{"uid": str, "success": bool, "comment_id": str|None, "error_msg": str|None}]`
  - Sequential with `wait_comment()` (10-20s) between posts — NOT `wait_action()`
  - Checks 500-limit BEFORE each individual post (not just once at start)
  - Continues on individual failures
- Comment-specific internal helper `_do_comment()` separate from `_do_action()` because:
  1. Response includes `comment.id` which must be extracted
  2. Result format differs (has `comment_id` field)
  3. 500-comment limit check is comment-specific
- `_comment_limit_reached()` and `_increment_comment_count()` helpers for DB operations
- New constants: `_COMMENT_CREATE_PATH`, `_COMMENT_REPLY_PATH`, `_COMMENT_LIMIT=500`
- New type alias: `CommentResult = dict[str, Any]`
- 26 comment tests + 29 like tests = 55 ActionExecutor tests total (all pass)

### Dashboard Shell + Routing (Task 14)
- shadcn/ui initialized with `npx shadcn@latest init` (Radix + Nova preset)
- Components added: button, card, badge, alert, avatar, progress, tabs, skeleton, scroll-area, checkbox, textarea, input, select, separator, sheet, dialog, dropdown-menu, tooltip, sonner, form
- Dark OLED Design System tokens written to `frontend/src/globals.css`
  - Background: `#0A0E27` (Dark OLED), Foreground: `#F8FAFC`, Card: `#1E293B`
  - Primary: `#E11D48` (Weibo Red), Accent: `#3B82F6` (Blue)
  - Success: `#22C55E`, Destructive: `#EF4444`, Warning: `#F59E0B`
  - Border: `#334155`, Muted: `#334155`
- Typography: Inter + Noto Sans SC (Google Fonts via @import), JetBrains Mono for code
- Tailwind config extends: spacing `18` (4.5rem), z-index scale (base/dropdown/sticky/overlay/modal/toast), animation tokens (fade-in/slide-up/pulse-slow)
- Zustand store (`competitionStore.ts`): competition state (idle/running/paused/ended), weibo_url, session_id
- Layout component: sticky nav bar with ghost Button links, Badge for online status, Sheet for mobile nav
- DashboardPage: 4-zone grid (`grid-cols-[2fr_1fr_1fr] grid-rows-2 gap-6`), each zone wrapped in Card with Skeleton placeholders
- SetupPage: react-hook-form + zod URL validation, shadcn Form/Input/Button
- LoginPage: QR code placeholder area, Progress for login count, Badge for status, Skeleton account list
- ReplayPage: Select for session picker, Tabs for timeline/alerts/actions, Skeleton placeholders
- App.tsx: Routes wrapped in Layout component
- Test: `DashboardPage.test.tsx` with 5 tests (root + 4 zones), all pass
- Vitest setup: `src/test/setup.ts` imports `@testing-library/jest-dom/vitest`
- pytest async mode=auto — no need for @pytest.mark.asyncio
- Mock httpx via `unittest.mock.AsyncMock` and `patch.object`
- Mock asyncio.sleep in delay tests
- SQLite in-memory for model tests
- 119 total tests (90 Wave 1 + 29 Task 12)
- 159 total tests after Task 8 (+40 comment fetcher tests)

### CommentFetcher API (Task 8)
- `CommentFetcher(client: WeiboHttpClient, anti_detection: AntiDetectionEngine, db_session=None, hot_threshold=50)`
- `fetch_comments(post_url: str, max_pages=5) -> list[CommentDTO]` — main entry point
- `get_weibo_mid(url: str) -> str` — static method, converts Weibo URL to mid via base62 decode
- `fetch_comment_likes(comment_id: str) -> dict` — placeholder, returns `{"comment_id": comment_id}`
- API endpoint: `GET /ajax/statuses/buildComments` with params: `flow=0, is_reload=1, id={mid}, count=20, uid="", max_id={max_id}`
- Pagination stops when: `max_id == 0` OR `data` empty OR `max_pages` reached
- `wait_monitor()` called only between pages (not after last page)
- `is_hot = like_count >= hot_threshold` (default threshold 50)
- `is_team_member` always False (no team member list yet)
- `rank` starts at 1, continues across pages
- `_save_snapshots()` upserts Comment (find by weibo_comment_id, updates like_count) and always creates new CommentSnapshot
- DB session optional — `fetch_comments` works without it (no persistence)
- `CommentDTO.id` set to 0 (DB ID not assigned until persisted)

### Weibo URL → mid Algorithm (from WeiboSpider)
- Extract base62 string from URL path (strip protocol, domain, query params, trailing slash)
- Base62 alphabet: `0-9a-zA-Z` (62 chars)
- Algorithm: right-cut groups of 4 chars, reverse the list, decode each group via base62 → int, zero-pad intermediate groups to 7 digits, lstrip leading zeros from final result
- Known mapping: `z0JH2lOMb` → `5056360400000000`
- Handles edge cases: single char, short strings, pure numeric strings

### HotCommentAnalyzer API (Task 9)
- `HotConfig` dataclass: `top_n=50`, `min_likes=0`, `ranking_field="like_count"`, `flow_param=0`
- `HotCommentAnalyzer(config: Optional[HotConfig] = None)` — uses default config when None
- `analyze(comments: list[CommentDTO], team_uids: list[str]) -> list[CommentDTO]`:
  - Filters by `min_likes` (comments below threshold excluded from ranking)
  - Sorts by `ranking_field` descending (default: like_count)
  - Assigns `rank` starting at 1
  - Sets `is_hot = rank <= config.top_n`
  - Sets `is_team_member = user_uid in team_uids`
  - Mutates CommentDTO objects in-place (Pydantic models are mutable)
  - Returns the sorted+annotated list
- `get_team_hot_status(comments, team_uids) -> list[dict]`:
  - For each team UID, finds best-ranked (lowest rank number) comment
  - Returns `{uid, nickname, comment_id, rank, like_count, is_hot}`
  - No comment → `{uid, nickname: None, comment_id: None, rank: None, like_count: None, is_hot: False}`
- `detect_changes(prev_status, curr_status) -> dict`:
  - `entered_hot`: UIDs not hot before but hot now (includes new members)
  - `dropped_out`: UIDs hot before but not hot now (includes disappeared members)
  - `rank_changed`: `[{uid, prev_rank, curr_rank}]` for members still hot but rank changed
- No DB access needed — pure logic service
- 18 tests, all pass
- 195 total tests (177 pass + 18 new; 26 pre-existing failures in test_action_executor_comment.py unrelated)
- Note: `flow_param` stored for future Weibo `flow` integration but does not affect ranking logic
- Note: `min_likes` filters BEFORE ranking (excluded comments don't appear in results)

### TeamMemberTracker API (Task 10)
- `TeamMemberTracker(db_session: Any = None)` — optional DB session for Account table access
- `get_team_uids() -> list[str]`:
  - Queries Account table for `status="active"`, returns list of `weibo_uid` strings
  - Returns `[]` when no DB session or no active accounts
- `track_comments(comments: list[CommentDTO], team_uids: list[str]) -> dict[str, dict]`:
  - Input: pre-analyzed CommentDTO list (from HotCommentAnalyzer) + team UIDs
  - For each team member, finds best-ranked comment (lowest rank number)
  - Returns dict keyed by uid: `{uid: {nickname, comment_id, rank, like_count, is_hot, content, status, comment_count}}`
  - Members WITH a comment: `status="has_comment"`, `comment_count >= 1`
  - Members WITHOUT: `status="no_comment"`, all None except `is_hot=False`, `comment_count=0`
  - Non-team comments are ignored
  - `comment_count` tracks total comments by that member in the batch (not just the best one)
- `get_member_grid_data(team_uids: list[str], tracked: dict[str, dict]) -> list[dict]`:
  - Returns exactly 20 dashboard grid cards
  - Card keys: `{uid, nickname, avatar_url, current_rank, like_count, is_hot, comment_count, online_status}`
  - `nickname`: from Account model, falls back to tracked nickname (from comment user_name)
  - `avatar_url`: from Account model
  - `current_rank`: from tracked dict (renamed from `rank` to `current_rank` for grid)
  - `online_status`: "online" if Account.status=="active", "offline" otherwise
  - Pads to 20 with `{uid: None, nickname: None, ...}` empty slots
  - Truncates to 20 if more members
- `_get_account_info(uid: str) -> dict`:
  - Helper: queries Account by `weibo_uid`
  - Returns `{nickname, avatar_url, status}` or `{nickname: None, avatar_url: None, status: "unknown"}`
  - Returns unknown values when no DB session
- 22 tests, all pass
- 225 total tests (203 existing + 22 new), no regressions
- Design: DB-optional pattern — works without DB for pure logic tests, uses DB for account enrichment

### CompetitionManager + API + SetupPage (Task 21)
- `CompetitionManager(db_session, monitor_orchestrator=None)` — manages competition lifecycle
- `_COMMENT_LIMIT = 500` — hard cap, enforced in `can_post_comment()` and `increment_comment_count()`
- Methods:
  - `start_session(weibo_url, team_uids=None) -> CompetitionSession` — creates session, sets status="running", converts URL→mid via `CommentFetcher.get_weibo_mid()`
  - `pause_session() -> CompetitionSession` — status="paused"
  - `resume_session() -> CompetitionSession` — status="running"
  - `end_session() -> CompetitionSession` — status="ended", sets `ended_at`
  - `get_current_session() -> CompetitionSession | None`
  - `get_comment_count() -> int` — returns `total_comments` or 0
  - `get_remaining_quota() -> int` — `max(0, 500 - total_comments)`
  - `can_post_comment() -> bool` — `total_comments < 500`
  - `increment_comment_count() -> bool` — increments if under limit, returns False at limit
- URL→mid conversion: `CommentFetcher.__new__(CommentFetcher)` to avoid constructor side-effects, then call static `get_weibo_mid()`
- `MonitorOrchestrator` (T15) is optional — passed as `monitor_orchestrator=None` in tests
- API router (`backend/app/api/competition.py`): 5 endpoints
  - `POST /competition/start` — body: `{weibo_url, team_uids?}`, returns `{status, session_id}`
  - `POST /competition/pause` — returns `{status}`
  - `POST /competition/resume` — returns `{status}`
  - `POST /competition/end` — returns `{status, total_comments}`
  - `GET /competition/status` — returns `{status, session_id?, total_comments?, remaining_quota?, started_at?, target_weibo_url?}`
- Router uses module-level lazy singleton `_get_manager()` with `SessionLocal()`; `reset_manager()` exposed for test isolation
- `get_status()` returns `{"status": "idle"}` when no active session
- Frontend API client (`frontend/src/api/competition.ts`):
  - `startCompetition(weibo_url, team_uids?)` → `apiPost("/competition/start", ...)`
  - `pauseCompetition()` → `apiPost("/competition/pause", {})`
  - `resumeCompetition()` → `apiPost("/competition/resume", {})`
  - `endCompetition()` → `apiPost("/competition/end", {})`
  - `getCompetitionStatus()` → `apiGet("/competition/status")`
- SetupPage.tsx: react-hook-form + zod (URL must contain "weibo.com"), shadcn Form/Input/Checkbox/Label/Button/Card
  - Team member checkboxes with mock data (5 members), toggle selection
  - "开始比赛" button → `startCompetition()` → navigate `/dashboard`
  - "结束比赛" button → `getCompetitionStatus()` + `endCompetition()` → navigate `/replay`
  - sonner toast on error, loading states on both buttons
  - Integrates with `useCompetitionStore` (Zustand) — sets weibo_url, status, session_id
- 39 backend tests (TDD), 11 frontend tests — all pass
- 288 total backend tests (288 collected, all pass with `--ignore=tests/test_monitor_orchestrator.py`)
- tsc: 0 errors in new files (3 pre-existing errors in useQrLogin.ts/LoginPage.test.tsx unchanged)
- vitest: 11/11 pass

## 2025-06-25 Task 15: WebSocket Real-Time Integration (MonitorOrchestrator)

### Files Created
- `backend/app/services/monitor_orchestrator.py` — MonitorOrchestrator class
- `backend/app/api/monitor.py` — FastAPI router with 5 endpoints
- `backend/tests/test_monitor_orchestrator.py` — 44 TDD tests

### Files Modified
- `backend/app/main.py` — added `monitor_router` import + `include_router`

### MonitorOrchestrator API
- Constructor takes 9 params: `client, anti_detection, fetcher, analyzer, tracker, alert_engine, action_executor, ws_manager, db_session=None`
- `start_monitoring(weibo_url, interval=15)` — sets `_running=True`, stores `_weibo_url`, creates `asyncio.Task` in `_monitor_task`, records `_start_time`
- `stop_monitoring()` — sets `_running=False`, cancels `_monitor_task`, sets it to `None`
- `execute_alert_action(alert_id, comment_content, selected_account_ids)` — finds alert via `alert_engine.get_pending_alerts()` then DB fallback, gets cookies from Account table, calls `batch_like` + `batch_comment`, resolves alert, broadcasts `action_result`, returns result dict
- `get_stats()` — returns dict with: total_comments, team_hot_count, remaining_quota, elapsed_time, hot_ratio, team_online_count, pending_alerts, executed_actions

### Monitoring Loop (14-step pipeline)
1. `fetcher.fetch_comments(url)` → comments
2. `tracker.get_team_uids()` → team_uids
3. `analyzer.analyze(comments, team_uids)` → analyzed
4. `tracker.track_comments(analyzed, team_uids)` → tracked
5. `tracker.get_member_grid_data(team_uids, tracked)` → grid_data
6. `analyzer.get_team_hot_status(analyzed, team_uids)` → curr_status
7. `analyzer.detect_changes(prev_status, curr_status)` → changes
8. `alert_engine.process_changes(changes)` → new_alerts (async)
9. `ws_manager.broadcast("hot_comments_update", {"comments": top_N})`
10. `ws_manager.broadcast("member_status_update", grid_data)` — raw list, NOT wrapped in dict
11. `ws_manager.broadcast("stats_update", stats_dict)`
12. `ws_manager.broadcast("alert_new", {alert fields})` for each alert
13. `self._prev_status = curr_status`
14. `asyncio.sleep(interval)`

### API Endpoints
- `POST /api/monitor/start` — body: `{weibo_url, interval=15}` → `{status: "running"}`
- `POST /api/monitor/stop` → `{status: "stopped"}`
- `POST /api/alerts/{alert_id}/execute` — body: `{comment, account_ids}` → result dict
- `GET /api/alerts/pending` → list of alert dicts
- `GET /api/stats` → stats dict

### Key Learnings
- WSManager.broadcast signature: `broadcast(message_type: str, data: dict)` — two args, NOT a WSMessage object
- `member_status_update` broadcast sends raw `grid_data` list, not `{"grid_data": [...]}` — test expected direct list
- `execute_alert_action` always calls `batch_like` and `batch_comment` when alert found (no guards on comment_id/weibo_mid) — tests expect unconditional calls
- `batch_like(comment_id, cookies)` where cookies is `list[tuple[str, str]]` of (weibo_uid, cookie_json)
- `batch_comment(weibo_mid, content, cookies)` — same cookies format
- `_get_weibo_mid()` reads from CompetitionSession with `status="running"` — returns `""` when no DB
- `_get_cookies(account_ids)` queries Account table, returns `[(weibo_uid, cookie_json)]` tuples
- Stats: `_get_team_hot_count()` counts `is_hot=True` entries in `_prev_status`
- API router uses module-level `_orchestrator` singleton with `get_orchestrator()`/`set_orchestrator()` for test injection
- Test pattern for API: `monitor_module._orchestrator = mock_orch` before `TestClient(app)`
- TDD lesson: with `interval=0`, monitoring loop runs MANY iterations before `stop_monitoring()` — use `assert_called()` not `assert_called_once()`, and check `call_args_list[0]` for first-call args
- 332 total backend tests, all pass

## 2025-06-25 Task 22: API Validation Spike Tests

### Files Created
- `backend/tests/test_api_validation_spike.py` — 6 real API validation tests (SKIP without cookie)
- `.omo/evidence/task-22-latency.json` — created at runtime when tests run with cookies
- `.omo/evidence/task-22-hot-ranking.json` — created at runtime when tests run with cookies

### Test Design
- All tests gated by `WEIBO_TEST_COOKIE` env var via module-level `pytestmark = pytest.mark.skipif`
- 6 tests: buildComments fetch, like endpoint, comment create, comment reply, hot vs time ranking, multi-account concurrent
- Tests use `_TEST_BASE62_MID = "Mb15BDYR0"` — a well-known public Weibo post
- Multi-account test uses `WEIBO_TEST_COOKIE_2`, `WEIBO_TEST_COOKIE_3` env vars (skips if <2 cookies)
- Evidence files use merge-write pattern: `_write_evidence(filename, key, data)` reads existing JSON, adds key, writes back — allows multiple tests to contribute to same file
- Cleanup: comment create/reply tests attempt `POST /ajax/comments/destroy` as best-effort cleanup
- Test comments marked with `[API Spike Test]` prefix for identification
- Like test uses `>=` comparison (not `>`) because Weibo API may cache responses
- Hot vs time ranking test calls buildComments directly with `flow=1` for time sort (CommentFetcher hardcodes `flow=0`)
- All tests call `client.close()` in `finally` block to avoid resource leaks

### Key Patterns
- `pytestmark` at module level applies skip to ALL tests — no per-test decoration needed
- `asyncio_mode=auto` means async test functions just work — no `@pytest.mark.asyncio`
- Evidence directory: `Path(__file__).resolve().parents[2] / ".omo" / "evidence"` — resolves to project root
- `_get_cookie(index)` helper reads `WEIBO_TEST_COOKIE` for index 0, `WEIBO_TEST_COOKIE_{index+1}` for index >0
- Multi-account test uses `asyncio.gather()` for concurrent requests to observe rate limiting
- 338 total backend tests (332 existing + 6 new spike tests), 6 skipped without cookie, no regressions

## 2025-06-25 Task 24: Integration Tests + Anti-Detection Tuning

### Anti-Detection Parameter Changes
- `CookiePool.MAX_USES_PER_COOKIE`: 10 → 8 (stricter rate limiting)
- `DelayManager.monitor_delay()`: 10-30s → 12-35s
- `DelayManager.action_delay()`: 5-15s → 8-20s
- `DelayManager.comment_delay()`: 10-20s → 15-30s
- New: `DelayManager.cookie_switch_delay()` — 3-8s delay for cookie rotation
- New: `AntiDetectionEngine.wait_cookie_switch()` — delegates to `cookie_switch_delay()`

### Files Modified
- `backend/app/services/anti_detection.py` — parameter tuning + 2 new methods
- `backend/tests/test_anti_detection.py` — updated 5 assertions to match new ranges

### Files Created
- `backend/tests/test_integration.py` — 11 integration tests (10 test classes, 11 methods)

### Integration Test Coverage (11 tests)
1. **TestCompetitionLifecycle** — CompetitionManager full lifecycle (start/pause/resume/end) with real DB + mock MonitorOrchestrator delegation
2. **TestCommentQuotaEnforcement** — 500-comment hard limit: can_post_comment + increment_comment_count at boundary
3. **TestAlertEnginePersistence** — AlertEngine.process_changes creates Alert rows in DB for dropped_out/entered_hot/rank_drop
4. **TestAlertEngineResolve** — resolve_alert updates DB status to "confirmed"
5. **TestMonitorIterationWithRealAlertEngine** — Single monitoring iteration with real AlertEngine + real DB, verifies alerts persisted + WS broadcast
6. **TestExecuteAlertActionWithDB** — execute_alert_action fetches cookies from Account table, passes to batch_like
7. **TestActionExecutorDBLogging** — like_comment creates ActionLog row with correct fields
8. **TestActionExecutorCommentLimit** — post_comment blocked at 500 without API call
9. **TestCookieSwitchDelay** — wait_cookie_switch returns 3-8s range
10. **TestCookiePoolRotationAt8** (2 tests) — rotation after exactly 8 uses + wait_cookie_switch calls asyncio.sleep

### Test Results
- 371 passed, 6 skipped, 0 failures (full suite)
- Integration tests: 11/11 pass
- No regressions from anti-detection parameter changes
