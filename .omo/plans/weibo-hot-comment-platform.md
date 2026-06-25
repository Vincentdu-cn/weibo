# 微博热评数据管理平台

## TL;DR

> **Quick Summary**: 构建一个本地运行的微博热评监控与半自动支援平台。20个组员扫码登录，实时监控指定微博的热评状态，当组员评论掉出热评时发出告警，人工确认后系统自动执行点赞/评论支援。包含4区域实时大屏和赛后复盘功能。
>
> **Deliverables**:
> - Python FastAPI 后端（微博API客户端、评论监控、告警引擎、操作执行器、WebSocket服务）
> - React 前端大屏（热评排行榜、组员状态网格、告警流、统计仪表盘）
> - QR扫码登录系统（20账号Cookie管理）
> - 防检测引擎（限速、随机延迟、Cookie轮换）
> - SQLite 数据持久化 + 赛后复盘模块
>
> **Estimated Effort**: XL
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Task 1 → 3 → 8 → 9 → 11 → 15 → 22 → F1-F4

---

## Context

### Original Request
参加微博抢热评比赛，约20人组队，每人各自账号。指定一条微博，在30分钟内让组内账号在该微博下的热评越多越好，总数不超过500条。需要数据管理平台实现评论获取、热评监控、ID池匹配、半自动评论/点赞、实时大屏和防机器人检测。

### Interview Summary
**Key Discussions**:
- 技术栈: Python FastAPI + React
- ID池: 组员微博UID（20个成员的Weibo UID）
- 认证: 扫码登录（QR码 + Cookie持久化）
- 自动操作: 半自动（告警→人工输入评论+选账号→自动执行）
- 评论内容: 手动输入（告警卡片内输入）
- 点赞策略: 选择账号点赞（手动选择哪些账号）
- 支援方式: 其他组员支援（A掉出→B/C/D给A点赞/评论）
- IP策略: 单IP + 严格限速
- 部署: 本地单机
- 比赛时长: 30分钟内
- 测试: TDD模式
- 大屏: 热评排行榜 + 组员状态网格 + 滚动告警流 + 统计仪表盘
- 复盘: 需要保存数据

**Research Findings**:
- 微博Web API端点已确认: buildComments(GET), comments/create(POST), comments/reply(POST), updateLike(POST,评论点赞)
- 参考项目nghuyong/WeiboSpider提供评论抓取模式，dataabc/weiboSpider提供防检测策略
- 两个参考项目都不支持写操作，需自行实现
- 防检测: Cookie-IP绑定、Cookie轮换(10次/Cookie)、随机延迟、XSRF-TOKEN
- Metis逆向发现: 评论点赞用updateLike(非setLike)，payload为{object_id, object_type:"comment"}

### Metis Review
**Identified Gaps** (addressed):
- 评论点赞端点: 通过逆向微博前端JS发现updateLike/destroyLike（非setLike/cancelLike）
- 验证spike需求: 计划包含Task 22验证真实API可用性
- 热评排序算法: 未知，计划中Task 9负责探索定义
- 20账号单IP可行性: Task 22验证spike中测试
- 评论可见性延迟: Task 22测量
- 监控账号vs操作账号分离: Task 5中设计Cookie池分层策略

---

## Work Objectives

### Core Objective
构建一个本地单机运行的微博热评监控与半自动支援平台，支持20个账号QR扫码登录、实时热评监控、半自动点赞/评论支援、4区域实时大屏和赛后数据复盘。

### Concrete Deliverables
- FastAPI后端: 微博API客户端、评论监控引擎、告警系统、操作执行器、WebSocket服务
- React前端: 登录页、4区域大屏、告警交互、统计面板
- QR登录系统: 20账号Cookie管理+持久化
- 防检测引擎: 限速+随机延迟+Cookie轮换+行为模拟
- SQLite数据库: 评论快照+操作日志+复盘数据
- 验证spike: 真实API端点验证+延迟测量

### Definition of Done
- [ ] 20个账号可通过QR码扫码登录并持久化Cookie
- [ ] 系统可获取指定微博的评论列表及每条评论的点赞数
- [ ] 系统实时监控热评排名，识别组员UID是否在热评中
- [ ] 组员评论掉出热评时，大屏弹出告警卡片
- [ ] 用户可在告警卡片内输入评论内容并选择支援账号
- [ ] 系统用选中账号执行点赞(updateLike)和评论(comments/create)
- [ ] 4区域大屏实时更新（WebSocket）
- [ ] 评论总数≤500条自动控制
- [ ] 赛后可查看历史数据复盘
- [ ] 请求间隔随机化，Cookie轮换，防机器人检测

### Must Have
- 微博QR扫码登录（20账号）
- buildComments API评论获取（含点赞数）
- 热评实时监控 + 组员UID匹配
- 半自动支援流程（告警→输入→选账号→执行）
- updateLike评论点赞 + comments/create发评论
- 4区域WebSocket实时大屏
- 防检测（限速+随机延迟+Cookie轮换）
- SQLite数据持久化 + 复盘
- 评论总数≤500控制
- TDD测试覆盖核心模块

### Must NOT Have (Guardrails)
- ❌ AI生成评论内容（只支持手动输入）
- ❌ 代理池/IP轮换（单IP+严格限速）
- ❌ 全自动操作（必须人工确认）
- ❌ 云部署/多机分布式（本地单机）
- ❌ 微博官方OAuth API对接（使用非官方ajax接口）
- ❌ 过度抽象/AI slop（如不必要的工厂模式、过度注释、通用化设计）
- ❌ 使用setLike给评论点赞（必须用updateLike）
- ❌ 超过500条评论（硬限制）
- ❌ 单个Cookie连续请求超过10次（防检测）

---

## Design System Specification

> **Sources**: shadcn/ui component library + ui-ux-pro-max design intelligence
> **Style**: Dark Mode Dashboard (OLED) + Real-Time Monitoring + Data-Dense BI
> **Rationale**: 比赛大屏在暗光环境使用, OLED暗色模式省电护眼, 实时监控需要告警色突出

### Tech Stack

- **UI Library**: shadcn/ui (Radix UI primitives, copy-paste components, owned code)
- **CSS Framework**: Tailwind CSS v4
- **Chart Library**: Recharts (LineChart for trends, already in plan)
- **Form**: react-hook-form + zod (for setup page, login)
- **Icons**: lucide-react (shadcn/ui default)
- **Toast**: sonner (shadcn/ui recommended)

### Installation (Task 14 responsibility)

```bash
cd frontend
npx shadcn@latest init  # Initialize shadcn/ui
npx shadcn@latest add button card table badge alert avatar progress tabs \
  skeleton scroll-area checkbox textarea input select separator sheet \
  dialog dropdown-menu tooltip sonner
```

### Color Tokens (globals.css)

> Based on ui-ux-pro-max: Financial Dashboard (#7) + Real-Time Monitoring (#31)
> Dark-first design for competition room big screen

```css
@layer base {
  :root {
    /* Base - Dark OLED */
    --background: 222.2 84% 4.9%;        /* #0A0E27 deep midnight */
    --foreground: 210 40% 98%;            /* #F8FAFC near-white text */
    --card: 222.2 47.4% 11.2%;           /* #1E293B card surface */
    --card-foreground: 210 40% 98%;
    --popover: 222.2 47.4% 11.2%;
    --popover-foreground: 210 40% 98%;

    /* Primary - Weibo Red (brand alignment) */
    --primary: 0 72.4% 50.6%;            /* #E11D48 weibo rose-red */
    --primary-foreground: 210 40% 98%;

    /* Secondary - Muted surface */
    --secondary: 217.2 32.6% 17.5%;      /* #334155 slate */
    --secondary-foreground: 210 40% 98%;

    /* Muted */
    --muted: 217.2 32.6% 17.5%;
    --muted-foreground: 215 20.2% 65.1%; /* #94A3B8 readable grey */

    /* Accent - Blue for data highlights */
    --accent: 217.2 91.5% 59.8%;         /* #3B82F6 blue */
    --accent-foreground: 210 40% 98%;

    /* Status Colors - Real-Time Monitoring */
    --destructive: 0 84.2% 60.2%;        /* #EF4444 critical alert red */
    --destructive-foreground: 210 40% 98%;
    --success: 142.1 70.6% 45.3%;        /* #22C55E normal/online green */
    --success-foreground: 210 40% 98%;
    --warning: 37.7 92.1% 50.3%;         /* #F59E0B warning amber */
    --warning-foreground: 222.2 47.4% 11.2%;

    /* Border & Ring */
    --border: 217.2 32.6% 17.5%;         /* #334155 */
    --input: 217.2 32.6% 17.5%;
    --ring: 0 72.4% 50.6%;               /* matches primary */

    --radius: 0.5rem;
  }
}
```

### Typography

> Source: ui-ux-pro-max typography.csv #25 (Chinese Simplified) + #5 (Minimal Swiss)
> Single versatile font for Chinese + Latin + numbers

```css
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
```

| Token | Font | Weight | Size | Usage |
|-------|------|--------|------|-------|
| `--font-heading` | Noto Sans SC, Inter | 600-700 | 1.5rem-3rem | 大屏区域标题 |
| `--font-body` | Noto Sans SC, Inter | 400 | 0.875rem-1rem | 正文、表格、列表 |
| `--font-mono` | JetBrains Mono | 400-500 | 0.75rem-0.875rem | UID、计数器、时间戳 |
| `--font-stat` | Inter (tabular-nums) | 700 | 2rem-4rem | 大数字（热评数、计时器） |

```css
/* Tailwind config */
fontFamily: {
  sans: ['Inter', 'Noto Sans SC', 'sans-serif'],
  mono: ['JetBrains Mono', 'monospace'],
}
/* Tabular numbers for stats */
.tabular-nums { font-variant-numeric: tabular-nums; }
```

### Spacing & Layout

> Source: ui-ux-pro-max styles.csv #28 (Data-Dense Dashboard) - compact 8-12px padding

| Token | Value | Usage |
|-------|-------|-------|
| `--space-xs` | 4px | Badge padding, icon gaps |
| `--space-sm` | 8px | Table cell padding, card inner gap |
| `--space-md` | 12px | Card padding, grid gap |
| `--space-lg` | 16px | Section gap, card header padding |
| `--space-xl` | 24px | Zone gap in 4-zone layout |
| `--space-2xl` | 32px | Page padding |

### Component Mapping (shadcn/ui → Platform UI)

> Each frontend task MUST use these exact shadcn/ui components.
> Source: shadcn-ui skill component categories

#### Task 14: Dashboard Shell + Routing

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Page layout | Custom grid `grid-cols-2 grid-rows-2 gap-6` | 4-zone big screen |
| Nav header | `Button` (ghost) + `Badge` | Logo + status |
| Mobile nav | `Sheet` (side="left") | Hamburger menu |
| Route indicator | `Tabs` (underline) | Setup / Dashboard / Replay |
| Loading | `Skeleton` | Pulse animation |

#### Task 16: Hot Comment Leaderboard

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Container | `Card` | `className="h-full"` |
| Header | `CardHeader` + `CardTitle` | "热评排行榜" |
| Table | `Table` + `TableHeader/Body/Row/Cell` | Rank, Avatar, Name, Likes, Status |
| Rank badge | `Badge` | variant: gold/silver/bronze for top 3 |
| Member avatar | `Avatar` + `AvatarImage/Fallback` | UID → avatar URL |
| Hot status | `Badge` | variant: `destructive` (hot), `secondary` (normal) |
| Like count | `span` with `tabular-nums font-mono` | Monospace numbers |
| Scroll | `ScrollArea` | `className="h-[calc(100%-3rem)]"` |

#### Task 17: Team Member Status Grid

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Container | `Card` | `className="h-full"` |
| Grid | `div` with `grid grid-cols-5 gap-2` | 20 members, 5x4 grid |
| Member cell | `Card` (inner) | `className="p-2 text-center"` |
| Avatar | `Avatar` + `AvatarFallback` | Initials or UID |
| Online dot | Custom `span` with `animate-pulse` | Green = online, Red = offline |
| Hot rank | `Badge` | variant: `destructive` if in hot, `outline` if not |
| Tooltip | `Tooltip` + `TooltipTrigger/Content` | Show UID + like count on hover |

#### Task 18: Alert Stream + Comment Input

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Container | `Card` | `className="h-full"` |
| Scroll list | `ScrollArea` | `className="h-full"` |
| Alert item | `Alert` | variant: `destructive` (urgent), `default` (info) |
| Alert title | `AlertTitle` | "组员X掉出热评!" |
| Alert desc | `AlertDescription` | "当前排名: #15, 点赞数: 234" |
| Comment input | `Textarea` | `placeholder="输入支援评论内容..."` |
| Account select | `Checkbox` (per account) + `Label` | Multi-select accounts |
| Support button | `Button` | variant: `default`, `disabled` until input + account |
| Action feedback | `sonner` toast | `toast.success("支援已执行")` / `toast.error("执行失败")` |
| Empty state | `div` with `text-muted-foreground` | "暂无告警, 监控中..." |

#### Task 19: Statistics Dashboard

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Container | `Card` | `className="h-full"` |
| Big number | `div` with `text-4xl font-bold tabular-nums` | Hot comment count |
| Progress bar | `Progress` | value = (comments / 500) * 100 |
| Progress color | `Progress` with conditional className | green <60%, amber <80%, red >80% |
| Timer | `div` with `font-mono text-2xl tabular-nums` | mm:ss format |
| Small cards | `Card` (mini) | 4 stat cards in a row |
| Stat icon | lucide-react icon | MessageSquare, Users, Bell, CheckCircle |
| Trend chart | Recharts `LineChart` | 30 data points, accent color line |

#### Task 20: Login & Cookie Management

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| QR display | `Card` + `img` | QR code centered |
| Status text | `Badge` | variant: `secondary` (waiting), `success` (scanned), `default` (success) |
| Account table | `Table` + rows | Avatar, Name, UID, Status, LastActive, Logout |
| Status dot | Custom `span` (green/red circle) | Cookie health |
| Progress | `Progress` | value = (logged_in / 20) * 100 |
| Logout button | `Button` (ghost, size=icon) | LogOut icon |
| Login progress | `Badge` | "已登录 X/20" |

#### Task 21: Setup Page

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Form | `Form` (react-hook-form) + `FormField` | Weibo URL input |
| URL input | `Input` | `placeholder="https://weibo.com/..."` |
| Start button | `Button` (size=lg) | "开始比赛" |
| End button | `Button` (variant=outlined, size=lg) | "结束比赛" |
| Member list | `Checkbox` list | Select team members |
| Validation | zod schema | URL format validation |

#### Task 23: Replay Page

| Platform Element | shadcn/ui Component | Props/Variant |
|-----------------|---------------------|---------------|
| Session select | `Select` + `SelectTrigger/Content/Item` | Choose session |
| Timeline slider | `Slider` | Scrub through time |
| Play controls | `Button` (icon) | Play/Pause/Forward |
| Tab switch | `Tabs` + `TabsList/Trigger/Content` | 时间线 / 告警 / 操作 |
| Timeline view | `Table` (snapshot per timestamp) | Rank, Name, Likes |
| Alert history | `Table` | Time, Member, Alert, Action |
| Action log | `Table` | Time, Account, Action, Result |
| Summary card | `Card` + `CardHeader/Content` | Key metrics |

### State Specifications (MANDATORY for all components)

> Source: ui-ux-pro-max ux-guidelines.csv #10 (Loading States), #28 (Focus States)

| State | Pattern | shadcn/ui Component |
|-------|---------|---------------------|
| **Loading** | `Skeleton` with `animate-pulse` | Replace real content with grey blocks |
| **Empty** | Centered `text-muted-foreground` text + icon | "暂无数据" / "暂无告警" |
| **Error** | `Alert` variant=`destructive` + retry `Button` | "加载失败, 点击重试" |
| **Success** | `sonner` `toast.success()` | Auto-dismiss after 3s |
| **Submitting** | `Button` with `disabled` + `Spinner` | "执行中..." text |
| **Focus** | `focus-visible:ring-2 focus-visible:ring-primary` | All interactive elements |
| **Hover** | `hover:bg-secondary/50` transition 200ms | Cards, table rows, buttons |

### Accessibility (WCAG AA minimum)

> Source: ui-ux-pro-max styles.csv #8 (Accessible & Ethical)

- All interactive elements: minimum 44x44px touch target
- Color contrast: 4.5:1 minimum (verified against dark bg tokens)
- Status indicators: never color-only — always include icon + text
  - Hot: red dot + "热评" badge + flame icon
  - Normal: grey dot + "正常" badge
  - Alert: red pulse + "告警" text + bell icon
- Keyboard: Tab navigation through all interactive elements, Enter/Space to activate
- Screen reader: `aria-label` on all icon-only buttons, `role="alert"` on alert items
- `prefers-reduced-motion`: disable `animate-pulse` on status dots
- Focus visible: `focus-visible:ring-2` on all inputs, buttons, checkboxes

### Z-Index Scale

> Source: ui-ux-pro-max ux-guidelines.csv #15 (Z-Index Management)

| Layer | Z-Index | Element |
|-------|---------|---------|
| Base | 0 | Card content, tables |
| Sticky header | 10 | Dashboard zone headers |
| Tooltip | 20 | Hover tooltips |
| Dropdown | 30 | Select dropdowns, menus |
| Sheet | 40 | Mobile nav sheet |
| Dialog | 50 | Confirmation dialogs |
| Toast | 60 | sonner toaster |
| Alert overlay | 70 | Critical alert popup (if needed) |

### Animation Tokens

> Source: ui-ux-pro-max ux-guidelines.csv #8 (Duration Timing), #9 (Reduced Motion)

| Token | Duration | Easing | Usage |
|-------|----------|--------|-------|
| `--anim-fast` | 150ms | ease-out | Hover states, button press |
| `--anim-normal` | 200ms | ease-out | Card transitions, tab switch |
| `--anim-slow` | 300ms | ease-in-out | Sheet open/close, dialog |
| `--anim-pulse` | 2s | ease-in-out infinite | Live status dots |
| `--anim-chart` | 400ms | ease-out | Chart data updates |

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Verification Strategy

> **ZERO HUMAN INTERVENTION** - ALL verification is agent-executed. No exceptions.

### Test Decision
- **Infrastructure exists**: NO（全新项目）
- **Automated tests**: YES (TDD)
- **Framework**: pytest (Python后端) + vitest (React前端)
- **TDD**: 每个任务遵循 RED (failing test) → GREEN (minimal impl) → REFACTOR

### QA Policy
Every task MUST include agent-executed QA scenarios.
Evidence saved to `.omo/evidence/task-{N}-{scenario-slug}.{ext}`.

- **Backend/API**: Use Bash (curl) - Send requests, assert status + response fields
- **Frontend/UI**: Use Playwright (playwright skill) - Navigate, interact, assert DOM, screenshot
- **Library/Module**: Use Bash (python REPL) - Import, call functions, compare output
- **WebSocket**: Use Bash (websocat/python) - Connect, receive messages, assert payload

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Start Immediately - foundation + scaffolding):
├── Task 1: Project scaffolding + config [quick]
├── Task 2: Database schema + models [quick]
├── Task 3: Weibo HTTP client core [quick]
├── Task 4: QR login module [deep]
├── Task 5: Anti-detection engine [deep]
├── Task 6: WebSocket infrastructure [quick]
└── Task 7: Shared types & API contracts [quick]

Wave 2 (After Wave 1 - core logic, MAX PARALLEL):
├── Task 8: Comment fetcher (depends: 3, 5) [deep]
├── Task 9: Hot comment analyzer (depends: 8) [deep]
├── Task 10: Team member tracker (depends: 9) [unspecified-high]
├── Task 11: Alert engine (depends: 10) [unspecified-high]
├── Task 12: Comment like executor (depends: 3, 5) [unspecified-high]
├── Task 13: Comment post executor (depends: 3, 5) [unspecified-high]
└── Task 14: Dashboard shell + routing (depends: 1, 7) [visual-engineering]

Wave 3 (After Wave 2 - UI + integration):
├── Task 15: WebSocket real-time integration (depends: 6, 8-13) [deep]
├── Task 16: Hot comment leaderboard (depends: 14, 15) [visual-engineering]
├── Task 17: Team member status grid (depends: 14, 15) [visual-engineering]
├── Task 18: Alert stream + comment input + account selector (depends: 14, 15) [visual-engineering]
├── Task 19: Statistics dashboard (depends: 14, 15) [visual-engineering]
├── Task 20: Login & cookie management page (depends: 4, 14) [visual-engineering]
└── Task 21: Comment count controller + competition workflow (depends: 2, 13, 14) [unspecified-high]

Wave 4 (After Wave 3 - validation + polish):
├── Task 22: API validation spike (depends: 3, 4, 8, 12, 13) [deep]
├── Task 23: Replay/review module (depends: 2, 14) [unspecified-high]
└── Task 24: Anti-detection tuning + integration testing (depends: 5, 8-13, 15-21) [deep]

Wave FINAL (After ALL tasks — 4 parallel reviews):
├── Task F1: Plan compliance audit (oracle)
├── Task F2: Code quality review (unspecified-high)
├── Task F3: Real manual QA (unspecified-high)
└── Task F4: Scope fidelity check (deep)
-> Present results -> Get explicit user okay

Critical Path: Task 1 → 3 → 8 → 9 → 11 → 15 → 22 → F1-F4
Parallel Speedup: ~65% faster than sequential
Max Concurrent: 7 (Waves 1 & 2)
```

### Dependency Matrix

| Task | Depends On | Blocks | Wave |
|------|-----------|--------|------|
| 1 | - | 7, 14 | 1 |
| 2 | - | 21, 23 | 1 |
| 3 | - | 8, 12, 13, 22 | 1 |
| 4 | - | 20, 22 | 1 |
| 5 | - | 8, 12, 13, 24 | 1 |
| 6 | - | 15 | 1 |
| 7 | 1 | 14 | 1 |
| 8 | 3, 5 | 9, 15, 22 | 2 |
| 9 | 8 | 10, 15 | 2 |
| 10 | 9 | 11, 15 | 2 |
| 11 | 10 | 15 | 2 |
| 12 | 3, 5 | 15, 22 | 2 |
| 13 | 3, 5 | 15, 21, 22 | 2 |
| 14 | 1, 7 | 16-21 | 2 |
| 15 | 6, 8-13 | 16-19, 24 | 3 |
| 16 | 14, 15 | 24 | 3 |
| 17 | 14, 15 | 24 | 3 |
| 18 | 14, 15 | 24 | 3 |
| 19 | 14, 15 | 24 | 3 |
| 20 | 4, 14 | 24 | 3 |
| 21 | 2, 13, 14 | 24 | 3 |
| 22 | 3, 4, 8, 12, 13 | - | 4 |
| 23 | 2, 14 | - | 4 |
| 24 | 5, 8-13, 15-21 | - | 4 |

### Agent Dispatch Summary

- **Wave 1**: 7 tasks - T1→`quick`, T2→`quick`, T3→`quick`, T4→`deep`, T5→`deep`, T6→`quick`, T7→`quick`
- **Wave 2**: 7 tasks - T8→`deep`, T9→`deep`, T10→`unspecified-high`, T11→`unspecified-high`, T12→`unspecified-high`, T13→`unspecified-high`, T14→`visual-engineering`
- **Wave 3**: 7 tasks - T15→`deep`, T16→`visual-engineering`, T17→`visual-engineering`, T18→`visual-engineering`, T19→`visual-engineering`, T20→`visual-engineering`, T21→`unspecified-high`
- **Wave 4**: 3 tasks - T22→`deep`, T23→`unspecified-high`, T24→`deep`
- **FINAL**: 4 tasks - F1→`oracle`, F2→`unspecified-high`, F3→`unspecified-high`, F4→`deep`

---

## TODOs

- [x] 1. Project Scaffolding + Config

  **What to do**:
  - 创建 monorepo 结构: `backend/` (FastAPI) + `frontend/` (React+Vite+TypeScript)
  - Backend: FastAPI 项目结构, `pyproject.toml` (pytest, httpx, aiohttp, sqlalchemy, pydantic, websockets), `backend/app/` 目录结构 (main.py, api/, core/, models/, services/, tests/)
  - Frontend: Vite + React + TypeScript, `package.json` (react, react-router-dom, recharts, zustand, antd), `src/` 目录结构 (components/, pages/, hooks/, stores/, types/, api/)
  - 配置文件: `.env.example`, `backend/app/core/config.py` (Settings类: 端口/数据库路径/轮询间隔/评论上限等)
  - 基础 `main.py`: FastAPI app 实例, CORS 中间件, `/health` 端点, WebSocket 端点占位
  - 基础 `App.tsx`: React Router 路由壳 (/, /login, /dashboard, /replay)
  - TDD: 先写 `test_health.py` 测试 `/health` 返回 200 + `{"status":"ok"}`

  **Must NOT do**:
  - 不安装不必要的依赖
  - 不创建过度复杂的目录结构
  - 不写业务逻辑代码

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准 FastAPI+React 脚手架, 纯配置和目录结构
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `customize-opencode`: 非opencode配置

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2-7)
  - **Blocks**: 7, 14
  - **Blocked By**: None (can start immediately)

  **References**:

  **Pattern References** (existing code to follow):
  - 无（全新项目）

  **API/Type References**:
  - `weibo-api-technical-report.md` - 微博API技术报告，包含所有端点和Headers

  **External References**:
  - FastAPI docs: `https://fastapi.tiangolo.com/tutorial/first-steps/` - FastAPI基础结构
  - Vite React docs: `https://vitejs.dev/guide/` - Vite+React项目创建

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_health.py` 创建
  - [ ] `pytest backend/tests/test_health.py` → PASS (1 test, 0 failures)

  **QA Scenarios**:

  ```
  Scenario: Backend health check
    Tool: Bash (curl)
    Preconditions: backend dependencies installed, virtualenv active
    Steps:
      1. cd backend && uvicorn app.main:app --port 8000 &
      2. sleep 2
      3. curl -s http://localhost:8000/health
      4. Assert HTTP 200, response body contains "ok"
    Expected Result: {"status":"ok"}
    Failure Indicators: Connection refused, 404, non-JSON response
    Evidence: .omo/evidence/task-1-health-check.txt

  Scenario: Frontend dev server starts
    Tool: Bash
    Preconditions: frontend dependencies installed
    Steps:
      1. cd frontend && npm run dev &
      2. sleep 3
      3. curl -s http://localhost:5173 | head -5
      4. Assert HTML response containing "<div id=\"root\">"
    Expected Result: HTML page with root div
    Failure Indicators: Connection refused, empty response, missing root div
    Evidence: .omo/evidence/task-1-frontend-dev.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(scaffold): project scaffolding + config`
  - Files: `backend/**, frontend/**, .env.example`
  - Pre-commit: `pytest backend/tests/ && cd frontend && npm run build`

- [x] 2. Database Schema + Models

  **What to do**:
  - 定义SQLAlchemy模型: `Account` (id, weibo_uid, nickname, cookie_json, cookie_expires_at, status, created_at), `Comment` (id, weibo_comment_id, weibo_post_id, user_uid, user_name, content, like_count, created_at, fetched_at), `CommentSnapshot` (id, comment_id, like_count, rank, is_hot, snapshot_at), `Alert` (id, account_id, comment_id, alert_type, message, status[pending/confirmed/executed/dismissed], created_at), `ActionLog` (id, account_id, action_type[like/comment/reply], target_comment_id, content, status, response, created_at), `CompetitionSession` (id, target_weibo_url, target_weibo_mid, started_at, ended_at, total_comments, status)
  - 创建 `backend/app/models/` 目录, 每个模型一个文件
  - 创建 `backend/app/core/database.py`: engine + session factory (SQLite, `data/weibo.db`)
  - 创建 alembic 迁移或 `init_db()` 函数自动建表
  - TDD: 先写 `test_models.py` 测试CRUD操作

  **Must NOT do**:
  - 不使用复杂的ORM关系（保持简单外键）
  - 不创建迁移框架（用init_db即可）
  - 不过度规范化

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准SQLAlchemy模型定义, 纯数据结构
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3-7)
  - **Blocks**: 21, 23
  - **Blocked By**: None

  **References**:

  **Pattern References**:
  - 无（全新项目）

  **External References**:
  - SQLAlchemy docs: `https://docs.sqlalchemy.org/en/20/orm/quickstart.html` - ORM模型定义

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_models.py` 创建
  - [ ] `pytest backend/tests/test_models.py` → PASS (all CRUD tests)

  **QA Scenarios**:

  ```
  Scenario: Database initialization
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. cd backend && python -c "from app.core.database import init_db; init_db()"
      2. ls data/weibo.db
      3. python -c "from app.core.database import SessionLocal; from app.models.account import Account; db=SessionLocal(); db.query(Account).count()"
    Expected Result: weibo.db exists, query returns 0 without error
    Failure Indicators: DB file missing, query raises exception
    Evidence: .omo/evidence/task-2-db-init.txt

  Scenario: CRUD operations on Account model
    Tool: Bash (python)
    Preconditions: database initialized
    Steps:
      1. python -c "
         from app.core.database import SessionLocal
         from app.models.account import Account
         db = SessionLocal()
         acc = Account(weibo_uid='123', nickname='test', cookie_json='{}', status='active')
         db.add(acc); db.commit()
         assert db.query(Account).count() == 1
         db.delete(acc); db.commit()
         assert db.query(Account).count() == 0
         print('CRUD OK')
         "
    Expected Result: "CRUD OK"
    Failure Indicators: Exception, count mismatch
    Evidence: .omo/evidence/task-2-crud.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(db): database schema + models`
  - Files: `backend/app/models/**, backend/app/core/database.py`

- [x] 3. Weibo HTTP Client Core

  **What to do**:
  - 创建 `backend/app/services/weibo_client.py`: WeiboHttpClient类
  - 基于 httpx.AsyncClient, 支持Cookie管理, 请求头构建
  - 核心方法: `_build_headers(cookie)` (XSRF-TOKEN, user-agent, referer, x-requested-with, sec-ch-ua), `_get(path, params, cookie)`, `_post(path, data, cookie)`
  - Cookie解析: 从cookie字符串中提取XSRF-TOKEN值, 设置为x-xsrf-token header
  - 错误处理: HTTP状态码检查, JSON解析, 微博错误码检查, 超时重试(3次)
  - 日志: 每次请求记录URL/状态码/耗时
  - TDD: 先写 `test_weibo_client.py` (mock httpx, 测试header构建, 错误处理)

  **Must NOT do**:
  - 不实现具体业务API (评论获取/点赞等在后续任务)
  - 不硬编码Cookie
  - 不使用requests库（用httpx异步）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: HTTP客户端封装, 标准模式
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-2, 4-7)
  - **Blocks**: 8, 12, 13, 22
  - **Blocked By**: None

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - Required Headers section, 完整header模板
  - `weibo-api-technical-report.md` - Cookie Management section, XSRF-TOKEN处理

  **Pattern References**:
  - `/tmp/weiboclient/weibo/header.py` - FakeChromeUA类, header构建参考
  - `/tmp/weiboapis/utils/weibo_utils.py` - get_common_headers()模板

  **External References**:
  - httpx docs: `https://www.python-httpx.org/async/` - 异步HTTP客户端

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_weibo_client.py` 创建
  - [ ] `pytest backend/tests/test_weibo_client.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Header construction with XSRF-TOKEN
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.services.weibo_client import WeiboHttpClient
         client = WeiboHttpClient()
         headers = client._build_headers('SUB=abc; XSRF-TOKEN=xyz123; SUBP=def')
         assert 'x-xsrf-token' in headers
         assert headers['x-xsrf-token'] == 'xyz123'
         assert 'user-agent' in headers
         assert 'x-requested-with' in headers
         print('Headers OK')
         "
    Expected Result: "Headers OK"
    Failure Indicators: Missing x-xsrf-token, wrong value, missing headers
    Evidence: .omo/evidence/task-3-headers.txt

  Scenario: Error handling on HTTP error
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         import pytest
         from app.services.weibo_client import WeiboHttpClient
         from unittest.mock import AsyncMock, patch
         client = WeiboHttpClient()
         # Mock httpx to return 403
         with patch.object(client, '_get') as mock_get:
             mock_get.side_effect = Exception('HTTP 403')
             try:
                 await client._get('/test', {}, 'fake_cookie')
                 print('FAIL: should have raised')
             except Exception:
                 print('Error handling OK')
         "
    Expected Result: "Error handling OK"
    Failure Indicators: No exception raised on error
    Evidence: .omo/evidence/task-3-error-handling.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(client): weibo HTTP client core`
  - Files: `backend/app/services/weibo_client.py, backend/tests/test_weibo_client.py`

- [x] 4. QR Login Module

  **What to do**:
  - 创建 `backend/app/services/qr_login.py`: WeiboQrLogin类
  - 实现微博QR登录流程:
    1. `get_qr_image()`: 调用 `https://login.sina.com.cn/sso/qrcode_image?entry=weibo&size=180&use_callback=1&callback=st02_1` 获取QR图片URL和qrid
    2. `check_login_status(qrid)`: 轮询 `https://login.sina.com.cn/sso/qrcode_login?entry=weibo&qrid={qrid}&callback=st02_2` 检查扫码状态
    3. 状态: `qr_awaiting` → `qr_scanned` → `qr_confirmed` → 登录成功获取Cookie
    4. `extract_cookies(redirect_url)`: 从登录成功后的redirect URL中提取Cookie (SUB, SUBP, XSRF-TOKEN等)
  - 创建 `backend/app/api/qr_login.py`: FastAPI路由
    - `GET /api/qr/generate` - 返回QR图片URL和session_id
    - `GET /api/qr/status/{session_id}` - 返回登录状态 (WebSocket推送状态变更)
  - Cookie持久化: 登录成功后保存到Account表 (weibo_uid从Cookie中解析, nickname通过API获取)
  - TDD: 先写 `test_qr_login.py` (mock HTTP响应, 测试状态流转)

  **Must NOT do**:
  - 不存储明文密码
  - 不在QR图片URL中暴露敏感信息
  - 不实现账密登录

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要逆向微博QR登录流程, 复杂的状态机, 涉及多个API端点
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-3, 5-7)
  - **Blocks**: 20, 22
  - **Blocked By**: None (depends on Task 2 models conceptually but can develop in parallel)

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - QR Login section, 完整QR登录流程
  - `weibo-api-technical-report.md` - Cookie Management section, Cookie提取

  **Pattern References**:
  - `/tmp/weiboclient/weibo/cookie.py` - Visitor cookie生成, passport.weibo.com流程参考
  - `/tmp/weiboclient/weibo/__init__.py` - Cookie管理参考

  **External References**:
  - 微博登录流程分析: CSDN博客关于sina SSO QR登录

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_qr_login.py` 创建
  - [ ] `pytest backend/tests/test_qr_login.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: QR generation API endpoint
    Tool: Bash (curl)
    Preconditions: backend running, database initialized
    Steps:
      1. curl -s http://localhost:8000/api/qr/generate | python -m json.tool
      2. Assert response contains "qr_image_url" and "session_id"
      3. Assert qr_image_url starts with "http"
    Expected Result: JSON with qr_image_url and session_id
    Failure Indicators: Missing fields, empty URL, non-JSON response
    Evidence: .omo/evidence/task-4-qr-generate.txt

  Scenario: QR status check - awaiting state
    Tool: Bash (curl)
    Preconditions: QR generated (session_id from previous scenario)
    Steps:
      1. curl -s http://localhost:8000/api/qr/status/{session_id} | python -m json.tool
      2. Assert response contains "status" field
      3. Assert status is "qr_awaiting" (no scan yet)
    Expected Result: {"status": "qr_awaiting"}
    Failure Indicators: Missing status, 404, exception
    Evidence: .omo/evidence/task-4-qr-status.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(auth): QR login module with cookie persistence`
  - Files: `backend/app/services/qr_login.py, backend/app/api/qr_login.py, backend/tests/test_qr_login.py`

- [x] 5. Anti-Detection Engine

  **What to do**:
  - 创建 `backend/app/services/anti_detection.py`: AntiDetectionEngine类
  - **Rate Limiter**: 每个Cookie最多10次请求, 超过自动切换Cookie; 全局请求间隔2-8秒+随机抖动
  - **Cookie Pool Manager**:
    - `CookiePool` 类: 管理所有账号Cookie, 分层 (monitor_tier: 1-2个账号用于读监控; action_tier: 其余账号用于写操作)
    - `get_monitor_cookie()`: 返回监控用Cookie (轮询使用, 避免单个账号请求过多)
    - `get_action_cookie(exclude_uids=[])`: 返回操作用Cookie (排除掉出热评的组员自己)
    - `mark_used(cookie)`: 标记Cookie已使用次数
    - `check_health(cookie)`: 验证Cookie是否有效 (调用简单API检查)
  - **Delay Manager**: 
    - `random_delay(min_s=2, max_s=8)`: 随机延迟
    - `action_delay()`: 操作后延迟 (更长, 5-15秒)
    - `monitor_delay()`: 监控轮询延迟 (较短, 10-30秒)
  - **Request Pattern Mimicry**:
    - 随机化请求顺序
    - 偶尔插入无意义请求 (模拟浏览行为)
    - User-Agent在3-5个Chrome UA中随机切换
  - TDD: 先写 `test_anti_detection.py` (测试限速逻辑, Cookie轮换, 延迟范围)

  **Must NOT do**:
  - 不使用代理IP
  - 不实现验证码自动破解
  - 不做过于复杂的指纹模拟

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 防检测策略设计需要深度思考, 涉及限速算法、Cookie状态机、随机化策略
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-4, 6-7)
  - **Blocks**: 8, 12, 13, 24
  - **Blocked By**: None

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - Anti-Bot Mechanisms section, 8种机制
  - `weibo-api-technical-report.md` - Evasion Strategies section, Cookie分层+轮换策略

  **Pattern References**:
  - dataabc/weiboSpider `spider.py:50-61` - 多层延迟系统 (random_wait_pages, random_wait_seconds, global_wait)
  - `/tmp/weiboclient/weibo/header.py` - FakeChromeUA类, UA轮换参考

  **External References**:
  - CSDN博客: 微博反爬机制详解

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_anti_detection.py` 创建
  - [ ] `pytest backend/tests/test_anti_detection.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Cookie rotation after 10 requests
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.services.anti_detection import CookiePool
         pool = CookiePool()
         pool.add_cookie('uid1', 'cookie1_str')
         pool.add_cookie('uid2', 'cookie2_str')
         # Get cookie 10 times - should always return same one
         for i in range(10):
             c = pool.get_monitor_cookie()
             assert c == 'cookie1_str'
         # 11th request should rotate to cookie2
         c = pool.get_monitor_cookie()
         assert c == 'cookie2_str'
         print('Rotation OK')
         "
    Expected Result: "Rotation OK"
    Failure Indicators: No rotation, wrong cookie returned
    Evidence: .omo/evidence/task-5-cookie-rotation.txt

  Scenario: Random delay within bounds
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         import time
         from app.services.anti_detection import DelayManager
         dm = DelayManager()
         for _ in range(20):
             start = time.time()
             dm.random_delay(1, 2)
             elapsed = time.time() - start
             assert 0.9 <= elapsed <= 2.5, f'Delay {elapsed} out of bounds'
         print('Delay OK')
         "
    Expected Result: "Delay OK"
    Failure Indicators: Delay out of bounds, no delay at all
    Evidence: .omo/evidence/task-5-delay.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(anti-detection): rate limiter + cookie pool + delay manager`
  - Files: `backend/app/services/anti_detection.py, backend/tests/test_anti_detection.py`

- [x] 6. WebSocket Infrastructure

  **What to do**:
  - 创建 `backend/app/services/ws_manager.py`: WebSocketConnectionManager类
  - 管理多个WebSocket连接 (大屏可能有多个tab)
  - `broadcast(message_type, data)`: 向所有连接广播消息
  - `send_to(connection_id, message)`: 向特定连接发送
  - 消息类型定义: `hot_comments_update`, `member_status_update`, `alert_new`, `alert_resolved`, `stats_update`, `action_result`
  - 创建 `backend/app/api/ws.py`: WebSocket路由 `/ws`
    - 连接时注册到manager
    - 接收心跳消息, 30秒无心跳断开
    - 断开时从manager注销
  - 创建 `frontend/src/hooks/useWebSocket.ts`: React hook
    - 自动连接/重连 (指数退避)
    - 消息分发 (根据type路由到不同回调)
    - 心跳发送 (每15秒)
  - TDD: 后端 `test_ws_manager.py` (测试广播/发送/连接管理)

  **Must NOT do**:
  - 不实现业务消息推送逻辑（在Task 15集成）
  - 不使用Socket.IO（用原生WebSocket）

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 标准WebSocket连接管理, 模式成熟
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-5, 7)
  - **Blocks**: 15
  - **Blocked By**: None

  **References**:

  **External References**:
  - FastAPI WebSocket docs: `https://fastapi.tiangolo.com/advanced/websockets/` - WebSocket端点
  - React WebSocket hook pattern: 常见useWebSocket模式

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_ws_manager.py` 创建
  - [ ] `pytest backend/tests/test_ws_manager.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: WebSocket connection and broadcast
    Tool: Bash (python)
    Preconditions: backend running
    Steps:
      1. python -c "
         import asyncio, websockets, json
         async def test():
             async with websockets.connect('ws://localhost:8000/ws') as ws:
                 await ws.send(json.dumps({'type': 'ping'}))
                 # Wait for broadcast
                 msg = await asyncio.wait_for(ws.recv(), timeout=5)
                 data = json.loads(msg)
                 assert 'type' in data
                 print('WS OK')
         asyncio.run(test())
         "
    Expected Result: "WS OK"
    Failure Indicators: Connection refused, timeout, no message type
    Evidence: .omo/evidence/task-6-websocket.txt

  Scenario: Multiple connections receive broadcast
    Tool: Bash (python)
    Preconditions: backend running
    Steps:
      1. Open 2 WebSocket connections to ws://localhost:8000/ws
      2. Trigger a broadcast via API endpoint
      3. Assert both connections receive the message
    Expected Result: Both connections receive same message
    Failure Indicators: Only one receives, message lost
    Evidence: .omo/evidence/task-6-multi-ws.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(ws): websocket infrastructure for real-time updates`
  - Files: `backend/app/services/ws_manager.py, backend/app/api/ws.py, frontend/src/hooks/useWebSocket.ts, backend/tests/test_ws_manager.py`

- [x] 7. Shared Types & API Contracts

  **What to do**:
  - 创建 `backend/app/schemas/`: Pydantic模型定义所有API请求/响应结构
    - `comment.py`: CommentDTO (id, weibo_comment_id, user_uid, user_name, content, like_count, rank, is_hot, is_team_member, created_at)
    - `account.py`: AccountDTO (id, weibo_uid, nickname, status, avatar_url)
    - `alert.py`: AlertDTO (id, account_id, comment_id, alert_type, message, status, comment_input, selected_account_ids)
    - `stats.py`: StatsDTO (total_comments, team_hot_count, remaining_quota, elapsed_time, hot_ratio)
    - `ws_message.py`: WSMessage (type, data, timestamp)
  - 创建 `frontend/src/types/`: TypeScript类型, 与Pydantic模型一一对应
    - `comment.ts`, `account.ts`, `alert.ts`, `stats.ts`, `ws-message.ts`
  - 创建 `frontend/src/api/client.ts`: API请求封装 (fetch wrapper, 错误处理, 类型安全)
  - TDD: 后端 `test_schemas.py` (测试序列化/反序列化)

  **Must NOT do**:
  - 不创建过度复杂的类型继承
  - 不使用代码生成工具

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: 类型定义文件, 纯数据结构
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1-6)
  - **Blocks**: 14
  - **Blocked By**: 1 (needs project structure)

  **References**:

  **External References**:
  - Pydantic docs: `https://docs.pydantic.dev/latest/` - 模型定义
  - TypeScript handbook: 类型定义

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_schemas.py` 创建
  - [ ] `pytest backend/tests/test_schemas.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Pydantic model serialization
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.schemas.comment import CommentDTO
         c = CommentDTO(
             id=1, weibo_comment_id='abc', user_uid='123',
             user_name='test', content='hello', like_count=5,
             rank=1, is_hot=True, is_team_member=False
         )
         d = c.model_dump()
         assert d['like_count'] == 5
         assert d['is_hot'] == True
         c2 = CommentDTO(**d)
         assert c2.content == 'hello'
         print('Schema OK')
         "
    Expected Result: "Schema OK"
    Failure Indicators: Serialization error, field mismatch
    Evidence: .omo/evidence/task-7-schemas.txt

  Scenario: TypeScript types compile
    Tool: Bash
    Preconditions: frontend dependencies installed
    Steps:
      1. cd frontend && npx tsc --noEmit
      2. Assert exit code 0
    Expected Result: No type errors
    Failure Indicators: Type errors, missing files
    Evidence: .omo/evidence/task-7-tsc.txt
  ```

  **Commit**: YES (groups with Wave 1)
  - Message: `feat(types): shared types and API contracts`
  - Files: `backend/app/schemas/**, frontend/src/types/**, frontend/src/api/client.ts, backend/tests/test_schemas.py`

- [x] 8. Comment Fetcher

  **What to do**:
  - 创建 `backend/app/services/comment_fetcher.py`: CommentFetcher类
  - 核心方法 `fetch_comments(weibo_mid, cookie, max_pages=5)`:
    - 调用 `GET https://weibo.com/ajax/statuses/buildComments?flow=0&is_reload=1&id={mid}&is_show_bulletin=2&is_mix=0&max_id={max_id}&count=20&uid={uid}`
    - flow=0: 热评排序; 解析返回JSON中 `data` 数组
    - 每条评论提取: id(评论ID), text(content), like_count(like_counts), user.id(user_uid), user.screen_name(user_name), created_at
    - 分页: 使用返回的 `max_id` 作为下一页参数, 最多 max_pages 页
    - 通过AntiDetectionEngine获取monitor_cookie, 请求间加入随机延迟
  - 方法 `fetch_comment_likes(comment_id, cookie)`: 获取评论点赞列表 (可选, 用于深度分析)
  - 方法 `get_weibo_mid(url)`: 从微博URL中提取mid (base62解码, 参考nghuyong的url_to_mid)
  - 保存评论快照到 CommentSnapshot 表
  - TDD: 先写 `test_comment_fetcher.py` (mock WeiboHttpClient, 测试分页逻辑, 数据解析)

  **Must NOT do**:
  - 不实现点赞/评论操作（在Tasks 12-13）
  - 不缓存评论数据（每次实时获取）
  - 不处理子评论/回复链（只获取一级评论）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 涉及微博API分页逻辑, 数据解析, mid转换算法
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 1)
  - **Parallel Group**: Wave 2 (with Tasks 9-14)
  - **Blocks**: 9, 15, 22
  - **Blocked By**: 3 (WeiboHttpClient), 5 (AntiDetectionEngine)

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - Web API section, buildComments端点参数详解
  - `backend/app/schemas/comment.py` - CommentDTO结构 (Task 7)

  **Pattern References**:
  - `/tmp/weibospider/weibospider/spiders/comment.py` - buildComments分页逻辑, max_id游标
  - `/tmp/weibospider/weibospider/common.py:45-50` - url_to_mid base62解码
  - `backend/app/services/weibo_client.py` - HTTP客户端_get方法 (Task 3)

  **External References**:
  - 微博buildComments API: 评论JSON结构

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_comment_fetcher.py` 创建
  - [ ] `pytest backend/tests/test_comment_fetcher.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Fetch comments with mock API
    Tool: Bash (python)
    Preconditions: backend dependencies installed, mock fixture available
    Steps:
      1. python -c "
         from unittest.mock import AsyncMock, patch
         from app.services.comment_fetcher import CommentFetcher

         fetcher = CommentFetcher()
         mock_response = {
             'data': [
                 {'id': 'c1', 'text': 'test comment', 'like_counts': 5,
                  'user': {'id': 'u1', 'screen_name': 'user1'},
                  'created_at': 'Wed Jun 24 10:00:00 +0800 2025'}
             ],
             'max_id': 0,
             'max_id_type': 0
         }
         with patch.object(fetcher, '_fetch_page', AsyncMock(return_value=mock_response)):
             comments = await fetcher.fetch_comments('mid123', 'fake_cookie')
             assert len(comments) == 1
             assert comments[0].like_count == 5
             assert comments[0].user_uid == 'u1'
             print('Fetch OK')
         "
    Expected Result: "Fetch OK"
    Failure Indicators: Parse error, missing fields, wrong count
    Evidence: .omo/evidence/task-8-fetch.txt

  Scenario: URL to mid conversion
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.services.comment_fetcher import CommentFetcher
         f = CommentFetcher()
         mid = f.get_weibo_mid('https://weibo.com/1234567890/Mb15BDYR0')
         assert mid is not None
         assert len(mid) > 0
         print(f'MID: {mid}')
         "
    Expected Result: Non-empty mid string
    Failure Indicators: None returned, empty string
    Evidence: .omo/evidence/task-8-mid.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(fetcher): comment fetcher with buildComments API`
  - Files: `backend/app/services/comment_fetcher.py, backend/tests/test_comment_fetcher.py`

- [x] 9. Hot Comment Analyzer

  **What to do**:
  - 创建 `backend/app/services/hot_analyzer.py`: HotCommentAnalyzer类
  - **热评定义探索**: 由于微博热评排序算法未知, 实现可配置的热评判定:
    - `HotConfig`: `top_n` (默认50), `min_likes` (默认0), `ranking_field` (默认like_count), `flow_param` (0=热评排序, 1=时间排序)
    - 使用 buildComments API的 flow=0 返回顺序作为热评排序参考
    - 如果API返回已按热度排序, 直接使用返回顺序作为rank
  - 方法 `analyze(comments, team_uids)`:
    - 输入: CommentFetcher获取的评论列表 + 组员UID列表
    - 为每条评论计算: rank (在评论列表中的位置), is_hot (rank <= top_n), is_team_member (user_uid in team_uids)
    - 返回: 排序后的评论列表 + 组员评论在热评中的位置
  - 方法 `get_team_hot_status(comments, team_uids)`:
    - 返回每个组员的状态: {uid, nickname, comment_id, rank, like_count, is_hot}
    - 如果组员有多条评论, 取排名最高的
  - 方法 `detect_changes(prev_status, curr_status)`:
    - 对比上次和当前的热评状态
    - 返回: 新进入热评的组员, 掉出热评的组员, 排名变化的组员
  - TDD: 先写 `test_hot_analyzer.py` (测试排序, 热评判定, 变化检测)

  **Must NOT do**:
  - 不实现评论获取逻辑（在Task 8）
  - 不假设热评算法（保持可配置）
  - 不做复杂的时间衰减计算

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 核心业务逻辑, 热评判定策略, 状态变化检测算法
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (after Task 8)
  - **Parallel Group**: Wave 2 (after Task 8 completes)
  - **Blocks**: 10, 15
  - **Blocked By**: 8

  **References**:

  **API/Type References**:
  - `backend/app/schemas/comment.py` - CommentDTO (Task 7)
  - `backend/app/schemas/stats.py` - StatsDTO (Task 7)

  **Pattern References**:
  - `backend/app/services/comment_fetcher.py` - fetch_comments返回的CommentDTO列表 (Task 8)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_hot_analyzer.py` 创建
  - [ ] `pytest backend/tests/test_hot_analyzer.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Hot comment ranking with team member detection
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.services.hot_analyzer import HotCommentAnalyzer
         from app.schemas.comment import CommentDTO

         comments = [
             CommentDTO(id=1, weibo_comment_id='c1', user_uid='team1', user_name='A', content='hi', like_count=10, rank=0, is_hot=False, is_team_member=False),
             CommentDTO(id=2, weibo_comment_id='c2', user_uid='other', user_name='B', content='yo', like_count=8, rank=0, is_hot=False, is_team_member=False),
             CommentDTO(id=3, weibo_comment_id='c3', user_uid='team2', user_name='C', content='hey', like_count=3, rank=0, is_hot=False, is_team_member=False),
         ]
         analyzer = HotCommentAnalyzer(top_n=2)
         result = analyzer.analyze(comments, ['team1', 'team2'])
         assert result[0].rank == 1
         assert result[0].is_hot == True
         assert result[0].is_team_member == True  # team1 is in hot
         assert result[2].is_hot == False
         print('Analysis OK')
         "
    Expected Result: "Analysis OK"
    Failure Indicators: Wrong ranking, wrong hot detection, team member flag missing
    Evidence: .omo/evidence/task-9-analyze.txt

  Scenario: Status change detection
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.services.hot_analyzer import HotCommentAnalyzer
         prev = [{'uid': 'team1', 'rank': 3, 'is_hot': True}, {'uid': 'team2', 'rank': 1, 'is_hot': True}]
         curr = [{'uid': 'team1', 'rank': 3, 'is_hot': True}, {'uid': 'team2', 'rank': 55, 'is_hot': False}]
         analyzer = HotCommentAnalyzer(top_n=50)
         changes = analyzer.detect_changes(prev, curr)
         assert 'team2' in [c['uid'] for c in changes['dropped_out']]
         print('Changes OK')
         "
    Expected Result: "Changes OK"
    Failure Indicators: No change detected, wrong classification
    Evidence: .omo/evidence/task-9-changes.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(analyzer): hot comment ranking and team member tracking`
  - Files: `backend/app/services/hot_analyzer.py, backend/tests/test_hot_analyzer.py`

- [x] 10. Team Member Tracker

  **What to do**:
  - 创建 `backend/app/services/member_tracker.py`: TeamMemberTracker类
  - 管理组员UID池: 从Account表加载已登录的组员UID列表
  - 方法 `get_team_uids()`: 返回所有已登录组员的微博UID列表
  - 方法 `track_comments(comments)`:
    - 输入: CommentFetcher获取的评论列表
    - 匹配评论的user_uid与组员UID
    - 返回: 每个组员的评论状态 {uid, nickname, comment_id, rank, like_count, is_hot, content}
    - 如果组员有多条评论, 取排名最高的
    - 如果组员没有评论, 标记 status='no_comment'
  - 方法 `get_member_grid_data()`:
    - 返回20个组员的状态卡片数据 (用于大屏组员状态网格)
    - 每个卡片: nickname, avatar_url, current_rank, like_count, is_hot, comment_count, online_status
  - WebSocket消息触发: 当组员状态变化时, 通过WSManager广播 `member_status_update`
  - TDD: 先写 `test_member_tracker.py`

  **Must NOT do**:
  - 不实现评论获取（依赖Task 8的输出）
  - 不实现告警逻辑（在Task 11）
  - 不做UI渲染

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 数据匹配逻辑, 状态管理, 中等复杂度
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (after Task 9)
  - **Parallel Group**: Wave 2 (after Task 9 completes)
  - **Blocks**: 11, 15
  - **Blocked By**: 9

  **References**:

  **Pattern References**:
  - `backend/app/services/hot_analyzer.py` - analyze方法返回的排序评论 (Task 9)
  - `backend/app/models/account.py` - Account模型, weibo_uid字段 (Task 2)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_member_tracker.py` 创建
  - [ ] `pytest backend/tests/test_member_tracker.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Team member comment matching
    Tool: Bash (python)
    Preconditions: backend dependencies installed, test data in DB
    Steps:
      1. python -c "
         from app.services.member_tracker import TeamMemberTracker
         from app.schemas.comment import CommentDTO

         comments = [
             CommentDTO(id=1, weibo_comment_id='c1', user_uid='uid_A', user_name='Alice', content='go!', like_count=5, rank=1, is_hot=True, is_team_member=False),
             CommentDTO(id=2, weibo_comment_id='c2', user_uid='uid_X', user_name='Stranger', content='nice', like_count=3, rank=2, is_hot=True, is_team_member=False),
         ]
         tracker = TeamMemberTracker()
         # Mock team UIDs
         tracker._team_uids = {'uid_A': 'Alice', 'uid_B': 'Bob'}
         status = tracker.track_comments(comments)
         assert 'uid_A' in status
         assert status['uid_A']['is_hot'] == True
         assert status['uid_B']['status'] == 'no_comment'
         print('Track OK')
         "
    Expected Result: "Track OK"
    Failure Indicators: No match, wrong status, missing member
    Evidence: .omo/evidence/task-10-track.txt

  Scenario: Member grid data structure
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from app.services.member_tracker import TeamMemberTracker
         tracker = TeamMemberTracker()
         tracker._team_uids = {'uid_A': 'Alice'}
         tracker._member_status = {'uid_A': {'rank': 5, 'is_hot': True, 'like_count': 10, 'comment_count': 2}}
         grid = tracker.get_member_grid_data()
         assert len(grid) >= 1
         assert grid[0]['nickname'] == 'Alice'
         assert grid[0]['is_hot'] == True
         print('Grid OK')
         "
    Expected Result: "Grid OK"
    Failure Indicators: Empty grid, missing fields
    Evidence: .omo/evidence/task-10-grid.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(tracker): team member comment tracking and status grid`
  - Files: `backend/app/services/member_tracker.py, backend/tests/test_member_tracker.py`

- [x] 11. Alert Engine

  **What to do**:
  - 创建 `backend/app/services/alert_engine.py`: AlertEngine类
  - 核心方法 `process_changes(changes)`:
    - 输入: HotCommentAnalyzer.detect_changes() 的输出
    - 当组员掉出热评 → 创建Alert记录 (status='pending', alert_type='dropped_out')
    - 当组员排名大幅下降(>10位) → 创建Alert (alert_type='rank_drop')
    - 当组员新进入热评 → 创建Info Alert (alert_type='entered_hot')
  - 方法 `get_pending_alerts()`: 返回所有pending状态的告警 (用于大屏展示)
  - 方法 `resolve_alert(alert_id, action='confirmed'|'dismissed')`: 更新告警状态
  - 方法 `attach_action(alert_id, comment_content, selected_account_ids)`:
    - 用户在告警卡片中输入评论内容 + 选择支援账号
    - 更新Alert: comment_input=content, selected_account_ids=[...], status='confirmed'
    - 触发操作执行器 (Task 12/13)
  - WebSocket触发: 新告警时广播 `alert_new`, 解决时广播 `alert_resolved`
  - TDD: 先写 `test_alert_engine.py`

  **Must NOT do**:
  - 不执行点赞/评论操作（在Tasks 12-13）
  - 不做UI渲染
  - 不自动触发操作（半自动, 需人工确认）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 状态机逻辑, 告警生成规则, 中等复杂度
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (after Task 10)
  - **Parallel Group**: Wave 2 (after Task 10 completes)
  - **Blocks**: 15
  - **Blocked By**: 10

  **References**:

  **Pattern References**:
  - `backend/app/services/hot_analyzer.py` - detect_changes输出结构 (Task 9)
  - `backend/app/models/alert.py` - Alert模型 (Task 2)
  - `backend/app/services/ws_manager.py` - broadcast方法 (Task 6)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_alert_engine.py` 创建
  - [ ] `pytest backend/tests/test_alert_engine.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Alert generation on drop out
    Tool: Bash (python)
    Preconditions: backend dependencies installed, DB initialized
    Steps:
      1. python -c "
         from app.services.alert_engine import AlertEngine
         engine = AlertEngine()
         changes = {
             'dropped_out': [{'uid': 'team1', 'prev_rank': 10, 'curr_rank': 60, 'comment_id': 'c1'}],
             'entered_hot': [],
             'rank_changed': []
         }
         alerts = engine.process_changes(changes)
         assert len(alerts) == 1
         assert alerts[0].alert_type == 'dropped_out'
         assert alerts[0].status == 'pending'
         print('Alert OK')
         "
    Expected Result: "Alert OK"
    Failure Indicators: No alert created, wrong type, wrong status
    Evidence: .omo/evidence/task-11-alert-gen.txt

  Scenario: Alert resolution with action attachment
    Tool: Bash (python)
    Preconditions: alert exists in DB
    Steps:
      1. python -c "
         from app.services.alert_engine import AlertEngine
         engine = AlertEngine()
         alert_id = engine.process_changes({
             'dropped_out': [{'uid': 'team1', 'comment_id': 'c1'}],
             'entered_hot': [], 'rank_changed': []
         })[0].id
         engine.attach_action(alert_id, '加油!', ['uid_B', 'uid_C'])
         from app.core.database import SessionLocal
         from app.models.alert import Alert
         db = SessionLocal()
         alert = db.query(Alert).get(alert_id)
         assert alert.status == 'confirmed'
         assert alert.comment_input == '加油!'
         print('Attach OK')
         "
    Expected Result: "Attach OK"
    Failure Indicators: Status not updated, content not saved
    Evidence: .omo/evidence/task-11-attach.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(alert): alert engine with drop-out detection`
  - Files: `backend/app/services/alert_engine.py, backend/tests/test_alert_engine.py`

- [x] 12. Comment Like Executor

  **What to do**:
  - 创建 `backend/app/services/action_executor.py`: ActionExecutor类 (含点赞和评论, 本任务实现点赞部分)
  - **点赞评论** `like_comment(comment_id, cookie)`:
    - 调用 `POST https://weibo.com/ajax/statuses/updateLike`
    - Body: `{"object_id": str(comment_id), "object_type": "comment"}`
    - ⚠️ 关键: 使用 updateLike (非setLike), object_type="comment"
    - 成功检查: response JSON中 `ok` 字段 > 0
    - 失败处理: ok=0 → 记录失败原因, 可能已点赞/评论删除/限流
  - **批量点赞** `batch_like(comment_id, cookies)`:
    - 接收多个Cookie (选中的支援账号), 依次点赞
    - 每次点赞之间通过AntiDetectionEngine加入随机延迟 (5-15秒)
    - 每个Cookie使用后标记used次数
    - 返回: [{uid, success, error_msg}] 列表
  - **取消点赞** `unlike_comment(comment_id, cookie)`:
    - `POST https://weibo.com/ajax/statuses/destroyLike` + 同body
  - 记录所有操作到ActionLog表
  - TDD: 先写 `test_action_executor_like.py` (mock HTTP, 测试updateLike调用, 批量逻辑, 错误处理)

  **Must NOT do**:
  - ❌ 不使用setLike给评论点赞 (必须用updateLike)
  - 不并行点赞（串行+延迟更安全）
  - 不实现评论发布（在Task 13）

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 涉及关键API调用, 错误处理, 批量操作逻辑
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 1, independent of Tasks 8-11)
  - **Parallel Group**: Wave 2 (with Tasks 8-11, 13-14)
  - **Blocks**: 15, 22
  - **Blocked By**: 3 (WeiboHttpClient), 5 (AntiDetectionEngine)

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - Web API section, updateLike/destroyLike端点
  - Metis发现: `POST /ajax/statuses/updateLike` + `{"object_id": comment_id, "object_type": "comment"}`

  **Pattern References**:
  - `backend/app/services/weibo_client.py` - _post方法 (Task 3)
  - `backend/app/services/anti_detection.py` - action_delay, get_action_cookie (Task 5)
  - `backend/app/models/action_log.py` - ActionLog模型 (Task 2)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_action_executor_like.py` 创建
  - [ ] `pytest backend/tests/test_action_executor_like.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Like comment API call structure
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from unittest.mock import AsyncMock, patch
         from app.services.action_executor import ActionExecutor

         executor = ActionExecutor()
         mock_response = {'ok': 1}
         with patch.object(executor.client, '_post', AsyncMock(return_value=mock_response)):
             result = await executor.like_comment('comment_123', 'fake_cookie')
             assert result['success'] == True
             # Verify correct endpoint was called
             executor.client._post.assert_called_once()
             args = executor.client._post.call_args
             assert 'updateLike' in args[0][0] or 'updateLike' in str(args)
             print('Like OK')
         "
    Expected Result: "Like OK"
    Failure Indicators: Wrong endpoint, wrong payload, success not detected
    Evidence: .omo/evidence/task-12-like.txt

  Scenario: Like failure handling (ok=0)
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from unittest.mock import AsyncMock, patch
         from app.services.action_executor import ActionExecutor

         executor = ActionExecutor()
         mock_response = {'ok': 0}
         with patch.object(executor.client, '_post', AsyncMock(return_value=mock_response)):
             result = await executor.like_comment('comment_123', 'fake_cookie')
             assert result['success'] == False
             assert 'error' in result
             print('Fail handling OK')
         "
    Expected Result: "Fail handling OK"
    Failure Indicators: Success=True on ok=0, no error message
    Evidence: .omo/evidence/task-12-like-fail.txt

  Scenario: Batch like with delays
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from unittest.mock import AsyncMock, patch
         from app.services.action_executor import ActionExecutor
         import time

         executor = ActionExecutor()
         mock_response = {'ok': 1}
         with patch.object(executor.client, '_post', AsyncMock(return_value=mock_response)):
             start = time.time()
             results = await executor.batch_like('c1', ['cookie_A', 'cookie_B', 'cookie_C'])
             elapsed = time.time() - start
             assert len(results) == 3
             assert all(r['success'] for r in results)
             # Should have delays between likes (at least a few seconds with mocked fast delays)
             print(f'Batch OK, {len(results)} likes')
         "
    Expected Result: 3 successful likes
    Failure Indicators: Wrong count, no delay, parallel execution
    Evidence: .omo/evidence/task-12-batch.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(executor): comment like executor with updateLike API`
  - Files: `backend/app/services/action_executor.py, backend/tests/test_action_executor_like.py`

- [x] 13. Comment Post Executor

  **What to do**:
  - 在 `backend/app/services/action_executor.py` 中添加评论发布方法 (延续Task 12的文件)
  - **发布评论** `post_comment(weibo_mid, content, cookie)`:
    - 调用 `POST https://weibo.com/ajax/comments/create`
    - Body: `{"id": str(weibo_mid), "comment": content, "pic_id": "", "is_repost": 0, "comment_ori": 0, "is_comment": 0}`
    - 成功检查: response JSON中 `ok` 字段 > 0, 或返回comment对象
    - 返回: {success, comment_id (新评论ID), error_msg}
  - **回复评论** `reply_comment(weibo_mid, comment_id, content, cookie)`:
    - 调用 `POST https://weibo.com/ajax/comments/reply`
    - Body: `{"id": str(weibo_mid), "cid": str(comment_id), "comment": content, ...}`
  - **批量评论**: 类似batch_like, 串行+延迟, 但评论间延迟更长 (10-20秒)
  - **评论计数**: 每次发布评论后, 检查CompetitionSession.total_comments, 如果≥500则拒绝
  - 记录到ActionLog表
  - TDD: 先写 `test_action_executor_comment.py`

  **Must NOT do**:
  - 不自动生成评论内容（手动输入）
  - 不并行发布评论
  - 不超过500条评论上限

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: API调用, 计数控制, 错误处理
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 1, independent of Tasks 8-12)
  - **Parallel Group**: Wave 2 (with Tasks 8-12, 14)
  - **Blocks**: 15, 21, 22
  - **Blocked By**: 3 (WeiboHttpClient), 5 (AntiDetectionEngine)

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - Web API section, comments/create + comments/reply端点

  **Pattern References**:
  - `backend/app/services/action_executor.py` - like_comment模式 (Task 12)
  - `backend/app/models/competition_session.py` - CompetitionSession模型 (Task 2)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_action_executor_comment.py` 创建
  - [ ] `pytest backend/tests/test_action_executor_comment.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Post comment API call
    Tool: Bash (python)
    Preconditions: backend dependencies installed
    Steps:
      1. python -c "
         from unittest.mock import AsyncMock, patch
         from app.services.action_executor import ActionExecutor

         executor = ActionExecutor()
         mock_response = {'ok': 1, 'comment': {'id': 'new_c1', 'text': 'test'}}
         with patch.object(executor.client, '_post', AsyncMock(return_value=mock_response)):
             result = await executor.post_comment('mid123', '加油!', 'fake_cookie')
             assert result['success'] == True
             assert result['comment_id'] == 'new_c1'
             print('Post OK')
         "
    Expected Result: "Post OK"
    Failure Indicators: Wrong endpoint, missing comment_id, success not detected
    Evidence: .omo/evidence/task-13-post.txt

  Scenario: Comment count limit enforcement
    Tool: Bash (python)
    Preconditions: DB with CompetitionSession at 499 comments
    Steps:
      1. Set CompetitionSession.total_comments = 499 in DB
      2. python -c "
         from app.services.action_executor import ActionExecutor
         executor = ActionExecutor()
         # First comment should succeed (499 -> 500)
         result1 = await executor.post_comment('mid', 'test', 'cookie')  # mock ok
         # Second comment should be rejected (500 -> 501 not allowed)
         result2 = await executor.post_comment('mid', 'test2', 'cookie')
         assert result2['success'] == False
         assert 'limit' in result2.get('error_msg', '').lower()
         "
    Expected Result: First succeeds, second rejected
    Failure Indicators: Both succeed, no limit check
    Evidence: .omo/evidence/task-13-limit.txt
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(executor): comment post executor with count limit`
  - Files: `backend/app/services/action_executor.py, backend/tests/test_action_executor_comment.py`

- [x] 14. Dashboard Shell + Routing

  **What to do**:
  - **shadcn/ui 初始化** (本任务负责, 后续所有前端任务依赖):
    - 运行 `npx shadcn@latest init` 初始化 shadcn/ui (选择: TypeScript, Default, CSS variables, src/)
    - 安装基础组件: `npx shadcn@latest add button card badge alert avatar progress tabs skeleton scroll-area checkbox textarea input select separator sheet dialog dropdown-menu tooltip sonner`
    - 将 **Design System Specification** 章节的 Color Tokens 写入 `frontend/src/globals.css` (替换 shadcn init 默认值)
    - 将 Typography (Inter + Noto Sans SC + JetBrains Mono) 字体导入写入 `frontend/src/globals.css`
    - 将 Spacing/Z-Index/Animation tokens 写入 `frontend/tailwind.config.ts` 的 theme.extend
    - 验证: `npx tsc --noEmit` 通过, shadcn 组件可导入
  - 创建 `frontend/src/pages/DashboardPage.tsx`: 大屏主页面布局
    - 4区域网格布局 (CSS Grid `grid-cols-[2fr_1fr_1fr] grid-rows-2 gap-6`):
      - 左上: 热评排行榜 (col-span-1, row-span-1)
      - 右上: 统计仪表盘 (col-span-1, row-span-1)
      - 左下: 组员状态网格 (col-span-1, row-span-1)
      - 右下: 滚动告警流 (col-span-1, row-span-1)
      - 中间: 操作区 (col-start-2, row-span-2, 告警卡片弹出区)
    - 使用 shadcn `Card` 包裹每个区域, `CardHeader` + `CardTitle` 作为区域标题
    - 使用 `Skeleton` 作为各区域占位符 (后续任务填充)
  - 创建 `frontend/src/pages/LoginPage.tsx`: 登录页 (QR码显示区 + 已登录账号列表)
    - 使用 shadcn `Card` 包裹, `Progress` 显示登录进度, `Badge` 显示状态
  - 创建 `frontend/src/pages/ReplayPage.tsx`: 复盘页 (时间轴 + 回放控制)
    - 使用 shadcn `Select` 选择会话, `Tabs` 切换视图
  - 创建 `frontend/src/pages/SetupPage.tsx`: 比赛设置页
    - 使用 shadcn `Input` + `Button`, react-hook-form + zod 验证URL
  - 创建 `frontend/src/stores/competitionStore.ts`: Zustand store (competition状态: idle/running/paused/ended)
  - 创建 `frontend/src/components/Layout.tsx`: 导航栏 + 路由出口
    - 使用 shadcn `Button` (ghost variant) 作为导航链接, `Badge` 显示在线状态
    - 移动端使用 `Sheet` (side="left") 作为抽屉导航
  - 路由: `/` → SetupPage, `/login` → LoginPage, `/dashboard` → DashboardPage, `/replay` → ReplayPage
  - TDD: vitest测试组件渲染

  **Must NOT do**:
  - 不实现具体区域内容（在Tasks 16-19）
  - 不实现WebSocket数据绑定（在Task 15）
  - 不做过于花哨的动画
  - 不偏离 Design System Specification 中的 color/typography/spacing tokens

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 前端布局, React组件, CSS Grid, 路由配置, shadcn/ui 初始化
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: shadcn/ui 组件安装、初始化、使用模式 (本任务负责全部 shadcn 初始化)

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 1)
  - **Parallel Group**: Wave 2 (with Tasks 8-13)
  - **Blocks**: 15-21 (所有前端任务依赖 shadcn/ui 初始化和 Design System tokens)
  - **Blocked By**: 1 (scaffolding), 7 (types)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification` — 完整设计令牌: Color Tokens, Typography, Spacing, Component Mapping, State Specs, Accessibility, Z-Index, Animation. **本任务负责将这些令牌写入 globals.css 和 tailwind.config.ts**
  - `shadcn-ui skill` — 组件安装命令 `npx shadcn@latest add <component>`, 组件分类, 使用模式

  **Pattern References**:
  - `frontend/src/types/` - TypeScript类型 (Task 7)
  - `frontend/src/api/client.ts` - API客户端 (Task 7)

  **External References**:
  - React Router docs: `https://reactrouter.com/` - 路由配置
  - shadcn/ui docs: `https://ui.shadcn.com/` - 组件文档
  - Tailwind CSS Grid: 大屏4区域布局参考

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `frontend/src/pages/__tests__/DashboardPage.test.tsx` 创建
  - [ ] `npx vitest run` → PASS

  **QA Scenarios**:

  ```
  Scenario: Dashboard page renders 4 zones
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev server running
    Steps:
      1. Navigate to http://localhost:5173/dashboard
      2. Wait for page load (selector: [data-testid="dashboard-root"])
      3. Assert element with data-testid="hot-comments-zone" exists
      4. Assert element with data-testid="member-status-zone" exists
      5. Assert element with data-testid="alert-stream-zone" exists
      6. Assert element with data-testid="stats-zone" exists
      7. Screenshot
    Expected Result: 4 zones visible in grid layout
    Failure Indicators: Missing zones, layout broken
    Evidence: .omo/evidence/task-14-dashboard-layout.png

  Scenario: Navigation between pages
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev server running
    Steps:
      1. Navigate to http://localhost:5173/
      2. Assert SetupPage visible (data-testid="setup-page")
      3. Click nav link to /login
      4. Assert LoginPage visible (data-testid="login-page")
      5. Click nav link to /dashboard
      6. Assert DashboardPage visible
    Expected Result: All pages navigable
    Failure Indicators: 404, blank page, missing nav
    Evidence: .omo/evidence/task-14-navigation.png
  ```

  **Commit**: YES (groups with Wave 2)
  - Message: `feat(ui): dashboard shell with 4-zone layout + routing`
  - Files: `frontend/src/pages/**, frontend/src/stores/**, frontend/src/components/Layout.tsx`

- [x] 15. WebSocket Real-Time Integration

  **What to do**:
  - 创建 `backend/app/services/monitor_orchestrator.py`: MonitorOrchestrator类
  - 核心循环 `start_monitoring(weibo_url, interval=15)`:
    - 每隔interval秒执行一次监控循环
    - 1. CommentFetcher.fetch_comments() 获取评论
    - 2. HotCommentAnalyzer.analyze() 分析热评
    - 3. HotCommentAnalyzer.detect_changes() 检测变化
    - 4. TeamMemberTracker.track_comments() 更新组员状态
    - 5. AlertEngine.process_changes() 处理告警
    - 6. WSManager.broadcast() 推送更新:
       - `hot_comments_update`: 热评列表
       - `member_status_update`: 组员状态
       - `stats_update`: 统计数据
       - `alert_new`: 新告警 (如有)
  - 方法 `stop_monitoring()`: 停止循环
  - 方法 `execute_alert_action(alert_id, comment_content, selected_account_ids)`:
    - 调用ActionExecutor执行用户确认的操作
    - 点赞: batch_like(comment_id, selected_cookies)
    - 评论: post_comment(weibo_mid, content, cookie) for each selected
    - 广播 `action_result` 消息
  - 创建 FastAPI 路由 `backend/app/api/monitor.py`:
    - `POST /api/monitor/start` - 开始监控 (body: weibo_url, interval)
    - `POST /api/monitor/stop` - 停止监控
    - `POST /api/alerts/{id}/execute` - 执行告警操作 (body: comment, account_ids)
    - `GET /api/alerts/pending` - 获取待处理告警
    - `GET /api/stats` - 获取统计数据
  - TDD: 先写 `test_monitor_orchestrator.py`

  **Must NOT do**:
  - 不实现具体UI组件
  - 不修改Wave 1-2的模块代码
  - 不实现自动触发操作（半自动, 由API触发）

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 核心编排逻辑, 连接所有模块, WebSocket消息流, 复杂状态管理
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: NO (after all Wave 2 tasks)
  - **Parallel Group**: Wave 3 (after Tasks 8-14 complete)
  - **Blocks**: 16-19, 24
  - **Blocked By**: 6 (WSManager), 8 (CommentFetcher), 9 (HotAnalyzer), 10 (MemberTracker), 11 (AlertEngine), 12 (LikeExecutor), 13 (CommentExecutor)

  **References**:

  **Pattern References**:
  - `backend/app/services/comment_fetcher.py` - fetch_comments (Task 8)
  - `backend/app/services/hot_analyzer.py` - analyze, detect_changes (Task 9)
  - `backend/app/services/member_tracker.py` - track_comments, get_member_grid_data (Task 10)
  - `backend/app/services/alert_engine.py` - process_changes, get_pending_alerts (Task 11)
  - `backend/app/services/action_executor.py` - like_comment, post_comment, batch_like (Tasks 12-13)
  - `backend/app/services/ws_manager.py` - broadcast (Task 6)
  - `backend/app/services/anti_detection.py` - get_monitor_cookie, monitor_delay (Task 5)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_monitor_orchestrator.py` 创建
  - [ ] `pytest backend/tests/test_monitor_orchestrator.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Start monitoring API
    Tool: Bash (curl)
    Preconditions: backend running, all services available
    Steps:
      1. curl -s -X POST http://localhost:8000/api/monitor/start \
           -H "Content-Type: application/json" \
           -d '{"weibo_url": "https://weibo.com/test/Mb15BDYR0", "interval": 15}'
      2. Assert response contains "status": "running"
      3. Wait 20 seconds
      4. curl -s http://localhost:8000/api/stats
      5. Assert stats response contains "total_comments" field
    Expected Result: Monitoring started, stats available
    Failure Indicators: API error, no stats after wait
    Evidence: .omo/evidence/task-15-monitor-start.txt

  Scenario: WebSocket receives hot_comments_update
    Tool: Bash (python)
    Preconditions: monitoring started
    Steps:
      1. Connect WebSocket to ws://localhost:8000/ws
      2. Wait up to 30 seconds for a message with type="hot_comments_update"
      3. Assert message contains "data" array
    Expected Result: Receive hot_comments_update message
    Failure Indicators: No message, wrong type, no data
    Evidence: .omo/evidence/task-15-ws-hot.txt

  Scenario: Execute alert action via API
    Tool: Bash (curl)
    Preconditions: alert exists in pending state
    Steps:
      1. curl -s -X POST http://localhost:8000/api/alerts/{alert_id}/execute \
           -H "Content-Type: application/json" \
           -d '{"comment": "加油!", "account_ids": [1, 2, 3]}'
      2. Assert response contains "status": "executed" or "partial"
      3. Assert ActionLog entries created
    Expected Result: Action executed, logs created
    Failure Indicators: API error, no action logs
    Evidence: .omo/evidence/task-15-execute.txt
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(orchestrator): real-time monitoring + WebSocket integration`
  - Files: `backend/app/services/monitor_orchestrator.py, backend/app/api/monitor.py, backend/tests/test_monitor_orchestrator.py`

- [x] 16. Hot Comment Leaderboard Component

  **What to do**:
  - 创建 `frontend/src/components/HotCommentLeaderboard.tsx`
  - 使用 shadcn/ui 组件构建 (参考 Design System → Component Mapping → Task 16):
    - 外层: `Card` (`className="h-full"`) + `CardHeader` + `CardTitle` ("热评排行榜")
    - 列表: `ScrollArea` (`className="h-[calc(100%-3rem)]"`) 包裹 `Table`
    - 表头: `TableHeader` → `TableRow` → 排名/头像/用户名/评论/点赞/状态
    - 数据行: `TableRow` → `TableCell` per column
    - 排名徽章: `Badge` — 前3名 gold/silver/bronze variant, 其余 `outline`
    - 用户头像: `Avatar` + `AvatarImage` (微博头像URL) + `AvatarFallback` (UID首字符)
    - 组员标记: `Badge` variant=`destructive` ("组员"), 非组员无标记
    - 点赞数: `span` with `font-mono tabular-nums` (等宽数字)
    - 热评状态: `Badge` variant=`destructive` (🔥热评), `secondary` (正常)
    - 空状态: `div` with `text-muted-foreground` ("暂无热评数据")
    - 加载状态: `Skeleton` 替换行内容
  - 实时显示热评排行榜:
    - 每行: 排名 | 头像 | 用户名 | 评论内容(截断) | 点赞数 | 是否组员标记
    - 组员评论高亮显示 (`bg-success/10 border-l-2 border-success`)
    - 排名变化动画 (上升 `text-success` + ↑箭头, 下降 `text-destructive` + ↓箭头)
    - 自动滚动到组员评论位置 (ScrollArea scrollTo)
  - 数据来源: WebSocket `hot_comments_update` 消息
  - 创建 `frontend/src/hooks/useHotComments.ts`: 从WebSocket消息中提取热评数据
  - 组件props: { comments: CommentDTO[], teamUids: string[] }
  - TDD: vitest测试组件渲染, 排序, 高亮

  **Must NOT do**:
  - 不实现评论获取逻辑
  - 不实现交互操作（只展示）
  - 不偏离 Design System color tokens (组员高亮用 `--success` 不用自定义绿色)
  - 不使用非 shadcn/ui 组件构建表格/卡片/徽章

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: React组件, shadcn/ui Table/Avatar/Badge, 列表渲染, 动画, 实时更新
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Table, Avatar, Badge, ScrollArea, Card 组件用法和props

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 14, 15)
  - **Parallel Group**: Wave 3 (with Tasks 17-21)
  - **Blocks**: 24
  - **Blocked By**: 14 (Dashboard shell + shadcn init), 15 (WS integration)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification → Component Mapping → Task 16` — 精确的 shadcn/ui 组件映射表 (Card, Table, Badge, Avatar, ScrollArea, Skeleton)
  - `本计划 → Design System Specification → Color Tokens` — 组员高亮用 `--success`, 热评用 `--destructive`
  - `本计划 → Design System Specification → State Specifications` — Loading (Skeleton), Empty (muted text)
  - `本计划 → Design System Specification → Typography` — 点赞数用 `font-mono tabular-nums`

  **Pattern References**:
  - `frontend/src/types/comment.ts` - CommentDTO类型 (Task 7)
  - `frontend/src/hooks/useWebSocket.ts` - WebSocket hook (Task 6)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `frontend/src/components/__tests__/HotCommentLeaderboard.test.tsx` 创建
  - [ ] `npx vitest run` → PASS

  **QA Scenarios**:

  ```
  Scenario: Leaderboard renders comments with team highlight
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev running, mock WS data
    Steps:
      1. Navigate to http://localhost:5173/dashboard
      2. Wait for [data-testid="hot-comments-zone"] to have child elements
      3. Assert at least 1 comment row exists (data-testid="comment-row")
      4. Assert team member row has class "team-member"
      5. Assert like count is visible
      6. Screenshot
    Expected Result: Leaderboard with comment rows, team members highlighted
    Failure Indicators: Empty list, no highlight, missing like count
    Evidence: .omo/evidence/task-16-leaderboard.png

  Scenario: Real-time update on WebSocket message
    Tool: Playwright (playwright skill)
    Preconditions: WS connected, monitoring running
    Steps:
      1. Note current comment count on leaderboard
      2. Wait for next monitoring cycle (~15s)
      3. Assert leaderboard content updated (comment count or order changed)
    Expected Result: Leaderboard updates without page refresh
    Failure Indicators: No update, stale data
    Evidence: .omo/evidence/task-16-realtime.png
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): hot comment leaderboard with real-time updates`
  - Files: `frontend/src/components/HotCommentLeaderboard.tsx, frontend/src/hooks/useHotComments.ts`

- [x] 17. Team Member Status Grid

  **What to do**:
  - 创建 `frontend/src/components/MemberStatusGrid.tsx`
  - 使用 shadcn/ui 组件构建 (参考 Design System → Component Mapping → Task 17):
    - 外层: `Card` (`className="h-full"`) + `CardHeader` + `CardTitle` ("组员状态")
    - 网格: `div` with `grid grid-cols-5 gap-2` (5列x4行 = 20组员)
    - 组员卡片: 内层 `Card` (`className="p-2 text-center"`)
    - 头像: `Avatar` + `AvatarImage` (微博头像) + `AvatarFallback` (UID首字)
    - 排名徽章: `Badge` variant=`destructive` (在热评中), `outline` (不在热评)
    - 点赞/评论数: `span` with `font-mono tabular-nums text-xs`
    - 状态指示灯: 自定义 `span` 圆点
      - 热评中: `bg-success animate-pulse` (绿色脉冲)
      - 掉出: `bg-destructive animate-pulse` (红色脉冲)
      - 未评论: `bg-muted-foreground` (灰色静态)
    - Tooltip: `Tooltip` + `TooltipTrigger` + `TooltipContent` — hover显示 UID + 完整点赞数
    - 空状态: `div` with `text-muted-foreground` ("暂无组员数据")
    - 加载状态: `Skeleton` 网格占位
  - 20个组员状态卡片网格 (5列x4行):
    - 每个卡片: 头像 | 昵称 | 当前排名 | 点赞数 | 评论数 | 状态指示灯
    - 掉出热评的卡片: `border-destructive` + 红色脉冲圆点
    - 在热评中的卡片: `border-success` + 绿色脉冲圆点
    - 点击卡片展开该组员的评论详情 (使用 shadcn `Dialog` 或内联展开)
  - 数据来源: WebSocket `member_status_update` 消息
  - 创建 `frontend/src/hooks/useMemberStatus.ts`: 从WebSocket消息提取组员状态
  - TDD: vitest测试渲染, 状态颜色

  **Must NOT do**:
  - 不实现告警交互（在Task 18）
  - 不实现账号选择
  - 不使用非 shadcn/ui 组件构建卡片/头像/徽章
  - 状态指示灯不能只用颜色 — 必须同时有图标或文字 (参考 Design System → Accessibility)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: React组件, shadcn/ui Card/Avatar/Badge/Tooltip, 网格布局, 状态指示器, 实时更新
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Card, Avatar, Badge, Tooltip 组件用法和props

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 14, 15)
  - **Parallel Group**: Wave 3 (with Tasks 16, 18-21)
  - **Blocks**: 24
  - **Blocked By**: 14 (Dashboard shell + shadcn init), 15 (WS integration)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification → Component Mapping → Task 17` — 精确的 shadcn/ui 组件映射表 (Card, Avatar, Badge, Tooltip)
  - `本计划 → Design System Specification → Color Tokens` — 状态色: `--success`(热评), `--destructive`(掉出), `--muted-foreground`(未评论)
  - `本计划 → Design System Specification → State Specifications` — Loading (Skeleton), Empty (muted text)
  - `本计划 → Design System Specification → Accessibility` — 状态指示灯不能只用颜色, 需配合图标/文字
  - `本计划 → Design System Specification → Animation Tokens` — `--anim-pulse` 用于状态圆点

  **Pattern References**:
  - `frontend/src/types/account.ts` - AccountDTO类型 (Task 7)
  - `frontend/src/hooks/useWebSocket.ts` - WebSocket hook (Task 6)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `frontend/src/components/__tests__/MemberStatusGrid.test.tsx` 创建
  - [ ] `npx vitest run` → PASS

  **QA Scenarios**:

  ```
  Scenario: Member grid renders 20 cards
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev running, mock data with 20 members
    Steps:
      1. Navigate to http://localhost:5173/dashboard
      2. Wait for [data-testid="member-status-zone"]
      3. Count elements with data-testid="member-card"
      4. Assert count == 20
      5. Assert each card has name, rank, like_count visible
      6. Screenshot
    Expected Result: 20 member cards in grid
    Failure Indicators: Wrong count, missing fields
    Evidence: .omo/evidence/task-17-grid.png

  Scenario: Dropped-out member flashes red
    Tool: Playwright (playwright skill)
    Preconditions: member with is_hot=false
    Steps:
      1. Navigate to dashboard
      2. Find member card with data-testid="member-card" that has class "dropped-out"
      3. Assert card has red border or background
    Expected Result: Dropped-out member visually distinct
    Failure Indicators: No visual distinction
    Evidence: .omo/evidence/task-17-dropped.png
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): team member status grid with live indicators`
  - Files: `frontend/src/components/MemberStatusGrid.tsx, frontend/src/hooks/useMemberStatus.ts`

- [x] 18. Alert Stream + Comment Input + Account Selector

  **What to do**:
  - 创建 `frontend/src/components/AlertStream.tsx`: 滚动告警流
    - 使用 shadcn/ui 组件 (参考 Design System → Component Mapping → Task 18):
      - 外层: `Card` (`className="h-full"`) + `CardHeader` + `CardTitle` ("告警流")
      - 滚动列表: `ScrollArea` (`className="h-full"`)
      - 告警条目: `Alert` — variant=`destructive` (紧急: 掉出热评), variant=`default` (信息: 排名下降)
      - 告警标题: `AlertTitle` ("组员X掉出热评!")
      - 告警描述: `AlertDescription` ("当前排名: #15, 点赞数: 234")
      - 空状态: `div` with `text-muted-foreground` ("暂无告警, 监控中...")
      - 加载状态: `Skeleton` 告警条目占位
    - 新告警从顶部滑入 (`animate-in slide-in-from-top`), 已解决的淡出 (`animate-out fade-out`)
    - 每条告警: 时间 | 组员名 | 告警类型 | 当前排名 | 展开按钮 (`Button` ghost size=icon)
    - 点击展开 → 显示告警卡片
  - 创建 `frontend/src/components/AlertCard.tsx`: 告警操作卡片
    - 使用 shadcn/ui 组件:
      - 容器: `Card` + `CardHeader` + `CardTitle` + `CardContent`
      - 组员信息: `Avatar` + `AvatarImage/Fallback` + `Badge` (当前排名)
      - 评论输入: `Textarea` (`placeholder="输入支援评论内容..."`, maxLength=140)
      - 字数统计: `span` with `text-muted-foreground text-xs` (x/140)
      - 账号选择: `Checkbox` + `Label` per account (显示昵称+状态点)
      - 执行按钮: `Button` — "点赞支援" (variant=outline), "评论支援" (variant=default), "两者都要" (variant=default)
      - 按钮 `disabled` 直到: 评论输入非空 AND 至少选1个账号
      - 执行中状态: `Button` with `disabled` + spinner text "执行中..."
      - 执行结果: `sonner` toast — `toast.success("支援已执行")` / `toast.error("执行失败: {msg}")`
    - 显示: 掉出热评的组员信息 + 评论内容 + 当前排名
    - 点击按钮 → POST /api/alerts/{id}/execute
  - 创建 `frontend/src/hooks/useAlerts.ts`: 从WebSocket消息提取告警 + API操作
  - 数据来源: WebSocket `alert_new` + `alert_resolved` + API `/api/alerts/pending`
  - TDD: vitest测试渲染, 输入, 选择, 提交

  **Must NOT do**:
  - 不自动提交（需手动点击按钮）
  - 不实现点赞/评论执行逻辑（调用API即可）
  - 不使用非 shadcn/ui 组件构建 Alert/Card/Textarea/Checkbox/Button
  - 不使用浏览器原生 alert/confirm — 用 sonner toast 反馈

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 复杂交互组件, shadcn/ui Alert/Card/Textarea/Checkbox/Button/sonner, 表单, 列表选择, 动画
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Alert, Card, Textarea, Checkbox, Button, Badge, ScrollArea, sonner toast 组件用法

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 14, 15)
  - **Parallel Group**: Wave 3 (with Tasks 16-17, 19-21)
  - **Blocks**: 24
  - **Blocked By**: 14 (Dashboard shell + shadcn init), 15 (WS integration)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification → Component Mapping → Task 18` — 精确的 shadcn/ui 组件映射表 (Alert, Card, Textarea, Checkbox, Button, Badge, ScrollArea, sonner)
  - `本计划 → Design System Specification → Color Tokens` — 告警色 `--destructive`, 警告色 `--warning`
  - `本计划 → Design System Specification → State Specifications` — Submitting (disabled+spinner), Success (sonner toast), Empty (muted text)
  - `本计划 → Design System Specification → Z-Index Scale` — Toast z-60, Alert z-70
  - `本计划 → Design System Specification → Animation Tokens` — `--anim-normal` 滑入淡出

  **Pattern References**:
  - `frontend/src/types/alert.ts` - AlertDTO类型 (Task 7)
  - `frontend/src/types/account.ts` - AccountDTO类型 (Task 7)
  - `frontend/src/api/client.ts` - API请求封装 (Task 7)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `frontend/src/components/__tests__/AlertStream.test.tsx` 创建
  - [ ] `frontend/src/components/__tests__/AlertCard.test.tsx` 创建
  - [ ] `npx vitest run` → PASS

  **QA Scenarios**:

  ```
  Scenario: Alert appears in stream
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev running, mock alert via WS
    Steps:
      1. Navigate to http://localhost:5173/dashboard
      2. Wait for [data-testid="alert-stream-zone"]
      3. Inject mock alert: {type: 'alert_new', data: {id: 1, alert_type: 'dropped_out', member_name: 'Alice'}}
      4. Assert alert item appears (data-testid="alert-item")
      5. Assert member name "Alice" is visible
    Expected Result: Alert appears in stream
    Failure Indicators: No alert shown, wrong name
    Evidence: .omo/evidence/task-18-alert-appear.png

  Scenario: Alert card with comment input and account selection
    Tool: Playwright (playwright skill)
    Preconditions: alert exists in stream
    Steps:
      1. Click expand button on alert item
      2. Assert AlertCard visible (data-testid="alert-card")
      3. Type "加油加油!" in textarea (data-testid="comment-input")
      4. Assert textarea value is "加油加油!"
      5. Check 2 account checkboxes (data-testid="account-checkbox")
      6. Click "评论支援" button (data-testid="comment-support-btn")
      7. Assert POST request sent (intercept network)
      8. Assert result message displayed
    Expected Result: Comment submitted with selected accounts
    Failure Indicators: No input, no checkboxes, no API call
    Evidence: .omo/evidence/task-18-alert-card.png
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): alert stream with comment input and account selector`
  - Files: `frontend/src/components/AlertStream.tsx, frontend/src/components/AlertCard.tsx, frontend/src/hooks/useAlerts.ts`

- [x] 19. Statistics Dashboard

  **What to do**:
  - 创建 `frontend/src/components/StatsDashboard.tsx`
  - 使用 shadcn/ui 组件构建 (参考 Design System → Component Mapping → Task 19):
    - 外层: `Card` (`className="h-full"`) + `CardHeader` + `CardTitle` ("统计仪表盘")
    - 大数字: `div` with `text-4xl font-bold tabular-nums text-foreground"` (组内热评数/总热评数)
    - 占比: `span` with `text-muted-foreground text-sm"` (占比%)
    - 进度条: shadcn `Progress` — value = (comments / 500) * 100
    - 进度条颜色: 条件 className — `text-success` (<300), `text-warning` (<400), `text-destructive` (≥400)
    - 计时器: `div` with `font-mono text-2xl tabular-nums"` (mm:ss格式)
    - 小卡片: 4个内层 `Card` (`className="p-3"`) 横向排列 (`grid grid-cols-4 gap-2`)
    - 小卡片图标: lucide-react icons (MessageSquare, Users, Bell, CheckCircle)
    - 小卡片数字: `div` with `text-2xl font-bold tabular-nums"`
    - 小卡片标签: `div` with `text-muted-foreground text-xs"`
    - 趋势图: Recharts `LineChart` (30数据点, 线条用 `hsl(var(--accent))`, 网格用 `hsl(var(--border))`)
    - 加载状态: `Skeleton` 替换数字和图表
  - 实时统计仪表盘:
    - 大数字: 组内热评数 / 总热评数 (占比%)
    - 进度条: 已用评论数 / 500上限 (绿<300, 黄<400, 红≥400)
    - 计时器: 比赛已用时 (mm:ss格式)
    - 小卡片: 总评论数, 组员在线数, 待处理告警数, 已执行操作数
    - 趋势图: 热评数量随时间变化 (recharts LineChart, 最近30个数据点)
  - 数据来源: WebSocket `stats_update` 消息 + API `/api/stats`
  - 创建 `frontend/src/hooks/useStats.ts`: 统计数据管理
  - TDD: vitest测试渲染, 数字显示, 进度条

  **Must NOT do**:
  - 不实现复杂的数据分析
  - 不做3D图表
  - 不使用非 shadcn/ui 组件构建 Card/Progress
  - 进度条颜色必须使用 Design System tokens (--success/--warning/--destructive), 不用自定义颜色

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 数据可视化, shadcn/ui Card/Progress, Recharts图表, 实时更新, tabular-nums排版
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Card, Progress, Skeleton 组件用法和props

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 14, 15)
  - **Parallel Group**: Wave 3 (with Tasks 16-18, 20-21)
  - **Blocks**: 24
  - **Blocked By**: 14 (Dashboard shell + shadcn init), 15 (WS integration)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification → Component Mapping → Task 19` — 精确的 shadcn/ui 组件映射表 (Card, Progress, Skeleton)
  - `本计划 → Design System Specification → Color Tokens` — 进度条色: `--success`/`--warning`/`--destructive`, 图表线: `--accent`
  - `本计划 → Design System Specification → Typography` — 大数字用 `font-bold tabular-nums`, 计时器用 `font-mono tabular-nums`
  - `本计划 → Design System Specification → State Specifications` — Loading (Skeleton)
  - `本计划 → Design System Specification → Animation Tokens` — `--anim-chart` 用于图表更新过渡

  **Pattern References**:
  - `frontend/src/types/stats.ts` - StatsDTO类型 (Task 7)
  - `frontend/src/hooks/useWebSocket.ts` - WebSocket hook (Task 6)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **External References**:
  - Recharts docs: `https://recharts.org/` - LineChart用法, 主题色配置

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `frontend/src/components/__tests__/StatsDashboard.test.tsx` 创建
  - [ ] `npx vitest run` → PASS

  **QA Scenarios**:

  ```
  Scenario: Stats dashboard shows key metrics
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev running, monitoring active
    Steps:
      1. Navigate to http://localhost:5173/dashboard
      2. Wait for [data-testid="stats-zone"]
      3. Assert element with data-testid="hot-comment-ratio" is visible
      4. Assert element with data-testid="comment-progress" is visible
      5. Assert element with data-testid="timer" is visible
      6. Screenshot
    Expected Result: All stats elements visible with data
    Failure Indicators: Missing elements, no data
    Evidence: .omo/evidence/task-19-stats.png

  Scenario: Comment progress bar color changes
    Tool: Playwright (playwright skill)
    Preconditions: mock stats with 450/500 comments
    Steps:
      1. Navigate to dashboard
      2. Find [data-testid="comment-progress"]
      3. Assert progress bar has red color class (near limit)
      4. Mock stats with 200/500
      5. Assert progress bar has green color class
    Expected Result: Color reflects proximity to limit
    Failure Indicators: No color change, wrong color
    Evidence: .omo/evidence/task-19-progress.png
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): statistics dashboard with progress and trend chart`
  - Files: `frontend/src/components/StatsDashboard.tsx, frontend/src/hooks/useStats.ts`

- [x] 20. Login & Cookie Management Page

  **What to do**:
  - 完善 `frontend/src/pages/LoginPage.tsx` (Task 14创建的壳)
  - 使用 shadcn/ui 组件构建 (参考 Design System → Component Mapping → Task 20):
    - QR码区: `Card` + `CardHeader` + `CardTitle` ("扫码登录") + `CardContent`
    - QR图片: `img` 居中 (`className="mx-auto rounded-lg"`)
    - 状态文字: `Badge` — variant=`secondary` ("等待扫码"), variant=`warning` ("已扫码"), variant=`success` ("登录成功")
    - 已登录账号列表: `Card` + `Table` + `TableHeader/Body/Row/Cell`
    - 表头: 头像 | 昵称 | UID | Cookie状态 | 最后活跃 | 操作
    - 头像列: `Avatar` + `AvatarImage/Fallback`
    - Cookie状态: 自定义 `span` 圆点 (`bg-success` 有效 / `bg-destructive` 过期) + 文字
    - 登出按钮: `Button` (variant=ghost, size=icon) with LogOut icon
    - 登录进度: `Badge` ("已登录 X/20") + `Progress` (value = logged_in/20*100)
    - 加载状态: `Skeleton` 替换QR图片和表格
  - QR码登录区:
    - 调用 `GET /api/qr/generate` 获取QR图片URL
    - 显示QR码图片 (img标签)
    - 显示状态: "等待扫码" → "已扫码,等待确认" → "登录成功"
    - WebSocket或轮询 `GET /api/qr/status/{session_id}` 获取状态
    - 登录成功后刷新已登录账号列表
  - 已登录账号列表:
    - 表格: 头像 | 昵称 | UID | Cookie状态(有效/过期) | 最后活跃时间 | 登出按钮
    - Cookie健康检查: 每个账号显示绿/红圆点 + 文字标签 (非仅颜色, 参考 Accessibility)
    - 进度: "已登录 X/20"
  - 创建 `frontend/src/hooks/useQrLogin.ts`: QR登录状态管理
  - 创建 `frontend/src/api/qr.ts`: QR登录API封装
  - TDD: vitest测试渲染, 状态流转

  **Must NOT do**:
  - 不实现账密登录
  - 不存储明文密码
  - 不使用非 shadcn/ui 组件构建 Card/Table/Avatar/Badge/Progress/Button
  - Cookie状态不能只用颜色 — 需配合文字标签 (参考 Design System → Accessibility)

  **Recommended Agent Profile**:
  - **Category**: `visual-engineering`
    - Reason: 前端页面, shadcn/ui Card/Table/Avatar/Badge/Progress, API交互, 状态管理
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Card, Table, Avatar, Badge, Progress, Button 组件用法和props

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 14)
  - **Parallel Group**: Wave 3 (with Tasks 16-19, 21)
  - **Blocks**: 24
  - **Blocked By**: 4 (QR login backend), 14 (Dashboard shell + shadcn init)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification → Component Mapping → Task 20` — 精确的 shadcn/ui 组件映射表 (Card, Table, Avatar, Badge, Progress, Button)
  - `本计划 → Design System Specification → Color Tokens` — 状态色: `--success`(有效), `--destructive`(过期)
  - `本计划 → Design System Specification → State Specifications` — Loading (Skeleton), Success (Badge)
  - `本计划 → Design System Specification → Accessibility` — Cookie状态需文字+颜色双重指示

  **Pattern References**:
  - `backend/app/api/qr_login.py` - QR API端点 (Task 4)
  - `frontend/src/types/account.ts` - AccountDTO (Task 7)
  - `frontend/src/api/client.ts` - API client (Task 7)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `frontend/src/pages/__tests__/LoginPage.test.tsx` 创建
  - [ ] `npx vitest run` → PASS

  **QA Scenarios**:

  ```
  Scenario: QR code display
    Tool: Playwright (playwright skill)
    Preconditions: backend running, frontend dev running
    Steps:
      1. Navigate to http://localhost:5173/login
      2. Wait for [data-testid="qr-image"]
      3. Assert img element has src attribute starting with "http"
      4. Assert "等待扫码" status text visible
      5. Screenshot
    Expected Result: QR code image displayed with status
    Failure Indicators: No image, no status, broken image
    Evidence: .omo/evidence/task-20-qr.png

  Scenario: Logged-in account list
    Tool: Playwright (playwright skill)
    Preconditions: 2 accounts in DB
    Steps:
      1. Navigate to /login
      2. Wait for [data-testid="account-list"]
      3. Assert 2 rows in account table (data-testid="account-row")
      4. Assert "已登录 2/20" text visible
      5. Assert each row has nickname and status indicator
    Expected Result: 2 accounts listed with progress
    Failure Indicators: Empty list, wrong count, missing fields
    Evidence: .omo/evidence/task-20-account-list.png
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(ui): login page with QR code and account management`
  - Files: `frontend/src/pages/LoginPage.tsx, frontend/src/hooks/useQrLogin.ts, frontend/src/api/qr.ts`

- [x] 21. Comment Count Controller + Competition Workflow

  **What to do**:
  - 创建 `backend/app/services/competition_manager.py`: CompetitionManager类
  - **评论计数控制**:
    - `increment_comment_count()`: 每次发评论后+1, 检查是否≥500
    - `get_remaining_quota()`: 返回 500 - total_comments
    - `can_post_comment()`: 返回 total_comments < 500
    - 在CompetitionSession表中更新 total_comments
  - **比赛工作流**:
    - `start_competition(weibo_url, team_uids)`: 创建CompetitionSession, 开始监控
    - `pause_competition()`: 暂停监控
    - `resume_competition()`: 恢复监控
    - `end_competition()`: 停止监控, 标记session结束
  - 创建 FastAPI 路由 `backend/app/api/competition.py`:
    - `POST /api/competition/start` - 开始比赛
    - `POST /api/competition/pause` - 暂停
    - `POST /api/competition/resume` - 恢复
    - `POST /api/competition/end` - 结束
    - `GET /api/competition/status` - 当前状态
  - 完善 `frontend/src/pages/SetupPage.tsx`:
    - 使用 shadcn/ui 组件 (参考 Design System → Component Mapping → Task 21):
      - 表单: react-hook-form `Form` + `FormField` + `FormItem` + `FormControl` + `FormMessage`
      - URL输入: `Input` (`placeholder="https://weibo.com/..."`, zod URL验证)
      - 组员列表: `Checkbox` + `Label` per member (显示昵称+UID)
      - "开始比赛" 按钮: `Button` (size=lg, variant=default) → POST /api/competition/start → 跳转 /dashboard
      - "结束比赛" 按钮: `Button` (size=lg, variant=outline) → POST /api/competition/end → 跳转 /replay
      - 提交中状态: `Button` disabled + "开始中..." text
      - 错误反馈: `sonner` toast.error()
  - TDD: 后端 `test_competition_manager.py`

  **Must NOT do**:
  - 不允许超过500条评论
  - 不实现自动恢复（暂停后需手动恢复）
  - 前端不使用非 shadcn/ui 组件构建 Form/Input/Button/Checkbox

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 状态管理, API路由, 计数控制, 前后端集成, shadcn/ui Form/Input/Button
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Form (react-hook-form集成), Input, Button, Checkbox 组件用法

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Tasks 14)
  - **Parallel Group**: Wave 3 (with Tasks 16-20)
  - **Blocks**: 24
  - **Blocked By**: 2 (Models), 13 (CommentExecutor), 14 (Dashboard shell + shadcn init)

  **References**:

  **Design System Reference**:
  - `本计划 → Design System Specification → Component Mapping → Task 21` — shadcn/ui 组件映射 (Form, Input, Button, Checkbox)
  - `本计划 → Design System Specification → State Specifications` — Submitting (disabled+text), Error (sonner toast)

  **Pattern References**:
  - `backend/app/models/competition_session.py` - CompetitionSession模型 (Task 2)
  - `backend/app/services/action_executor.py` - post_comment计数 (Task 13)
  - `backend/app/services/monitor_orchestrator.py` - start_monitoring (Task 15)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_competition_manager.py` 创建
  - [ ] `pytest backend/tests/test_competition_manager.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Start competition via API
    Tool: Bash (curl)
    Preconditions: backend running, 2+ accounts logged in
    Steps:
      1. curl -s -X POST http://localhost:8000/api/competition/start \
           -H "Content-Type: application/json" \
           -d '{"weibo_url": "https://weibo.com/test/Mb15BDYR0"}'
      2. Assert response contains "status": "running" and "session_id"
      3. curl -s http://localhost:8000/api/competition/status
      4. Assert status is "running"
    Expected Result: Competition started successfully
    Failure Indicators: API error, status not running
    Evidence: .omo/evidence/task-21-start.txt

  Scenario: Comment count limit enforcement
    Tool: Bash (python)
    Preconditions: CompetitionSession with total_comments=500
    Steps:
      1. python -c "
         from app.services.competition_manager import CompetitionManager
         mgr = CompetitionManager()
         assert mgr.can_post_comment() == False
         assert mgr.get_remaining_quota() == 0
         print('Limit OK')
         "
    Expected Result: "Limit OK"
    Failure Indicators: can_post returns True, quota not 0
    Evidence: .omo/evidence/task-21-limit.txt

  Scenario: Setup page flow
    Tool: Playwright (playwright skill)
    Preconditions: frontend dev running, accounts logged in
    Steps:
      1. Navigate to http://localhost:5173/
      2. Assert input field for Weibo URL visible (data-testid="weibo-url-input")
      3. Type "https://weibo.com/test/Mb15BDYR0"
      4. Assert "开始比赛" button visible (data-testid="start-competition-btn")
      5. Click button
      6. Assert URL changes to /dashboard
    Expected Result: Navigate from setup to dashboard
    Failure Indicators: No input, no button, no navigation
    Evidence: .omo/evidence/task-21-setup-flow.png
  ```

  **Commit**: YES (groups with Wave 3)
  - Message: `feat(competition): workflow management + comment count control`
  - Files: `backend/app/services/competition_manager.py, backend/app/api/competition.py, frontend/src/pages/SetupPage.tsx, backend/tests/test_competition_manager.py`

- [x] 22. API Validation Spike

  **What to do**:
  - 创建 `backend/tests/test_api_validation_spike.py`: 真实API验证测试
  - **前置条件**: 需要至少1个真实微博账号Cookie (通过QR登录获取)
  - 验证以下端点在真实环境中的可用性:
    1. `GET /ajax/statuses/buildComments` — 获取真实微博评论, 验证返回结构, 点赞数字段
    2. `POST /ajax/statuses/updateLike` — 对真实评论点赞, 验证返回ok>0, 检查点赞数变化
    3. `POST /ajax/comments/create` — 发布真实评论, 验证返回comment对象, 验证评论可见
    4. `POST /ajax/comments/reply` — 回复评论, 验证返回
  - **测量延迟**:
    - 评论可见性延迟: 发评论后轮询buildComments, 测量评论出现的时间
    - 点赞数更新延迟: 点赞后轮询buildComments, 测量like_count变化的时间
    - 记录到 `.omo/evidence/task-22-latency.json`
  - **20账号单IP验证**:
    - 用2-3个账号同时请求, 观察是否触发限流/验证码
    - 记录请求频率和响应时间
  - **热评排序探索**:
    - 对比 flow=0 (热评) 和 flow=1 (时间) 的返回顺序
    - 分析热评排序与点赞数的关系
    - 记录到 `.omo/evidence/task-22-hot-ranking.json`
  - ⚠️ 此任务需要真实微博账号, 如果没有可用账号则跳过真实测试, 记录为"需要赛前验证"

  **Must NOT do**:
  - 不大量发布真实评论（测试1-2条即可, 事后删除）
  - 不对他人微博进行大量操作
  - 不存储真实Cookie到代码库

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 需要实际调用微博API, 分析响应, 测量延迟, 探索未知排序算法
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 3)
  - **Parallel Group**: Wave 4 (with Tasks 23, 24)
  - **Blocks**: None (final validation)
  - **Blocked By**: 3 (WeiboHttpClient), 4 (QR login), 8 (CommentFetcher), 12 (LikeExecutor), 13 (CommentExecutor)

  **References**:

  **API/Type References**:
  - `weibo-api-technical-report.md` - 所有API端点文档
  - Metis发现: updateLike端点详情

  **Pattern References**:
  - `backend/app/services/weibo_client.py` - HTTP客户端 (Task 3)
  - `backend/app/services/comment_fetcher.py` - 评论获取 (Task 8)
  - `backend/app/services/action_executor.py` - 点赞/评论 (Tasks 12-13)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_api_validation_spike.py` 创建
  - [ ] `pytest backend/tests/test_api_validation_spike.py -v --tb=long` → PASS or SKIP (if no real account)

  **QA Scenarios**:

  ```
  Scenario: BuildComments API returns real comments
    Tool: Bash (python)
    Preconditions: at least 1 real Weibo cookie available (env: WEIBO_TEST_COOKIE)
    Steps:
      1. python -c "
         import os
         from app.services.comment_fetcher import CommentFetcher
         cookie = os.environ.get('WEIBO_TEST_COOKIE', '')
         if not cookie:
             print('SKIP: no test cookie')
             exit(0)
         fetcher = CommentFetcher()
         # Use a well-known public Weibo post
         comments = await fetcher.fetch_comments('Mb15BDYR0', cookie, max_pages=1)
         assert len(comments) > 0
         assert comments[0].weibo_comment_id is not None
         assert comments[0].like_count is not None
         print(f'Got {len(comments)} comments')
         "
    Expected Result: Real comments fetched with like counts
    Failure Indicators: API error, empty response, missing fields
    Evidence: .omo/evidence/task-22-buildcomments.json

  Scenario: Comment like endpoint works
    Tool: Bash (python)
    Preconditions: real cookie, a real comment to like
    Steps:
      1. Fetch comments to get a comment_id
      2. Like the comment using updateLike
      3. Assert response ok > 0
      4. Re-fetch comments, assert like_count increased
      5. Record latency between like and like_count update
    Expected Result: Like succeeds, count increases
    Failure Indicators: ok=0, count not updated, API error
    Evidence: .omo/evidence/task-22-like-test.json

  Scenario: Hot comment ranking analysis
    Tool: Bash (python)
    Preconditions: real cookie
    Steps:
      1. Fetch comments with flow=0 (hot order)
      2. Fetch same comments with flow=1 (time order)
      3. Compare orderings
      4. Record like_counts for each position in hot order
      5. Save analysis to evidence file
    Expected Result: Hot order differs from time order, correlation with likes
    Failure Indicators: Same order, no correlation
    Evidence: .omo/evidence/task-22-hot-ranking.json
  ```

  **Commit**: YES (groups with Wave 4)
  - Message: `test(spike): API validation spike with real endpoints`
  - Files: `backend/tests/test_api_validation_spike.py`

- [x] 23. Replay/Review Module

  **What to do**:
  - 创建 `backend/app/services/replay_service.py`: ReplayService类
  - 方法 `get_session_timeline(session_id)`:
    - 从CommentSnapshot表获取所有快照, 按时间排序
    - 返回: [{timestamp, comments: [{rank, uid, name, like_count, is_hot}]}]
  - 方法 `get_session_alerts(session_id)`:
    - 从Alert表获取该session的所有告警
  - 方法 `get_session_actions(session_id)`:
    - 从ActionLog表获取该session的所有操作
  - 方法 `get_session_summary(session_id)`:
    - 统计: 总评论数, 组内热评峰值, 热评占比变化, 操作成功率, 每个组员的表现
  - 创建 FastAPI 路由 `backend/app/api/replay.py`:
    - `GET /api/replay/sessions` - 列出所有比赛session
    - `GET /api/replay/{session_id}/timeline` - 时间线数据
    - `GET /api/replay/{session_id}/alerts` - 告警历史
    - `GET /api/replay/{session_id}/actions` - 操作历史
    - `GET /api/replay/{session_id}/summary` - 汇总报告
  - 完善 `frontend/src/pages/ReplayPage.tsx`:
    - 使用 shadcn/ui 组件 (参考 Design System → Component Mapping → Task 23):
      - Session选择: `Select` + `SelectTrigger` + `SelectContent` + `SelectItem` (选择比赛session)
      - 时间轴滑块: `Slider` (拖动查看不同时间点)
      - 播放控制: `Button` (ghost, size=icon) — Play/Pause/Forward (lucide icons)
      - Tab切换: `Tabs` + `TabsList` + `TabsTrigger` + `TabsContent`
        - Tab 1 "时间线": `Table` (每行: 排名/头像/用户名/点赞数/是否热评)
        - Tab 2 "告警历史": `Table` (每行: 时间/组员/告警类型/操作/结果)
        - Tab 3 "操作日志": `Table` (每行: 时间/账号/操作类型/目标/结果)
      - 汇总报告: `Card` + `CardHeader` + `CardTitle` ("比赛汇总") + `CardContent`
        - 统计数字用 `text-2xl font-bold tabular-nums`
        - 每个组员表现: `Avatar` + `Badge` (排名) + `span` (点赞/评论数)
      - 空状态: `div` with `text-muted-foreground` ("暂无回放数据")
      - 加载状态: `Skeleton` 替换表格内容
  - TDD: 后端 `test_replay_service.py`

  **Must NOT do**:
  - 不实现实时监控功能（这是回看模块）
  - 不做视频录制
  - 不使用非 shadcn/ui 组件构建 Select/Slider/Tabs/Table/Card

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: 数据查询, 时间线构建, 前后端集成, shadcn/ui Select/Slider/Tabs/Table
  - **Skills**: [`shadcn-ui`]
    - `shadcn-ui`: Select, Slider, Tabs, Table, Card, Avatar, Badge 组件用法

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 3)
  - **Parallel Group**: Wave 4 (with Tasks 22, 24)
  - **Blocks**: None
  - **Blocked By**: 2 (Models), 14 (Dashboard shell + shadcn init)

  **References**:

  **Design System Reference (CRITICAL)**:
  - `本计划 → Design System Specification → Component Mapping → Task 23` — 精确的 shadcn/ui 组件映射表 (Select, Slider, Tabs, Table, Card, Avatar, Badge)
  - `本计划 → Design System Specification → State Specifications` — Loading (Skeleton), Empty (muted text)
  - `本计划 → Design System Specification → Typography` — 统计数字用 `font-bold tabular-nums`

  **Pattern References**:
  - `backend/app/models/comment_snapshot.py` - CommentSnapshot模型 (Task 2)
  - `backend/app/models/alert.py` - Alert模型 (Task 2)
  - `backend/app/models/action_log.py` - ActionLog模型 (Task 2)
  - `backend/app/models/competition_session.py` - CompetitionSession模型 (Task 2)
  - `frontend/src/globals.css` - Design System tokens (Task 14 写入)

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_replay_service.py` 创建
  - [ ] `pytest backend/tests/test_replay_service.py` → PASS

  **QA Scenarios**:

  ```
  Scenario: Replay timeline API
    Tool: Bash (curl)
    Preconditions: DB with at least 1 completed session + snapshots
    Steps:
      1. curl -s http://localhost:8000/api/replay/sessions | python -m json.tool
      2. Assert at least 1 session in list
      3. curl -s http://localhost:8000/api/replay/{session_id}/timeline
      4. Assert response contains "timeline" array
      5. Assert each timeline entry has "timestamp" and "comments"
    Expected Result: Timeline data with snapshots
    Failure Indicators: Empty response, missing fields
    Evidence: .omo/evidence/task-23-timeline.txt

  Scenario: Replay page renders
    Tool: Playwright (playwright skill)
    Preconditions: DB with session data, frontend dev running
    Steps:
      1. Navigate to http://localhost:5173/replay
      2. Assert session selector visible (data-testid="session-select")
      3. Select a session
      4. Assert timeline slider visible (data-testid="timeline-slider")
      5. Assert 3 tabs visible: 时间线回放, 告警历史, 操作日志
      6. Click 告警历史 tab
      7. Assert alert history table visible
      8. Screenshot
    Expected Result: Replay page with session data
    Failure Indicators: Empty page, no tabs, no data
    Evidence: .omo/evidence/task-23-replay.png

  Scenario: Session summary report
    Tool: Bash (curl)
    Preconditions: completed session in DB
    Steps:
      1. curl -s http://localhost:8000/api/replay/{session_id}/summary
      2. Assert response contains: total_comments, peak_hot_count, hot_ratio, action_success_rate
      3. Assert member_performance array exists
    Expected Result: Summary with key metrics
    Failure Indicators: Missing metrics, empty response
    Evidence: .omo/evidence/task-23-summary.txt
  ```

  **Commit**: YES (groups with Wave 4)
  - Message: `feat(replay): session replay and review module`
  - Files: `backend/app/services/replay_service.py, backend/app/api/replay.py, frontend/src/pages/ReplayPage.tsx, backend/tests/test_replay_service.py`

- [x] 24. Anti-Detection Tuning + Integration Testing

  **What to do**:
  - 调优 `backend/app/services/anti_detection.py` (基于Task 22验证spike的发现):
    - 根据真实API延迟数据调整: monitor_delay范围, action_delay范围
    - 根据热评排序发现调整: 轮询频率, 分页深度
    - 根据单IP测试结果调整: Cookie轮换阈值, 请求间隔
  - 创建 `backend/tests/test_integration.py`: 端到端集成测试
    - 测试完整工作流: 登录 → 开始比赛 → 监控 → 告警 → 执行操作 → 结束 → 复盘
    - 使用mock微博API (mock WeiboHttpClient的所有方法)
    - 验证WebSocket消息流: hot_comments_update → member_status_update → alert_new → action_result
    - 验证评论计数: 模拟发500条评论, 验证第501条被拒绝
    - 验证Cookie轮换: 模拟10次请求后Cookie自动切换
  - 前端集成测试:
    - 使用Playwright测试完整UI流程: Setup → Login → Dashboard → Alert → Execute
    - 验证4区域同时更新
  - 性能测试:
    - 模拟20个账号同时在线
    - 验证WebSocket消息延迟 < 1秒
    - 验证监控循环完成时间 < 30秒

  **Must NOT do**:
  - 不修改核心业务逻辑（只调参和测试）
  - 不引入新的依赖

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: 集成测试设计, 参数调优, 端到端验证, 性能测试
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES (after Wave 3)
  - **Parallel Group**: Wave 4 (with Tasks 22-23)
  - **Blocks**: None (final validation)
  - **Blocked By**: 5 (AntiDetection), 8-13 (all core services), 15-21 (all UI + integration)

  **References**:

  **Pattern References**:
  - `.omo/evidence/task-22-latency.json` - 真实API延迟数据 (Task 22)
  - `.omo/evidence/task-22-hot-ranking.json` - 热评排序分析 (Task 22)
  - All Wave 1-3 modules

  **Acceptance Criteria**:

  **TDD**:
  - [ ] `backend/tests/test_integration.py` 创建
  - [ ] `pytest backend/tests/test_integration.py -v` → PASS

  **QA Scenarios**:

  ```
  Scenario: Full workflow integration test
    Tool: Bash (pytest)
    Preconditions: all modules implemented, mock API configured
    Steps:
      1. cd backend && pytest tests/test_integration.py -v --tb=long
      2. Assert all test cases pass:
         - test_login_flow
         - test_start_competition
         - test_monitoring_cycle
         - test_alert_generation
         - test_action_execution
         - test_comment_count_limit
         - test_cookie_rotation
         - test_end_competition
    Expected Result: All integration tests pass
    Failure Indicators: Any test fails
    Evidence: .omo/evidence/task-24-integration.txt

  Scenario: Full UI flow with Playwright
    Tool: Playwright (playwright skill)
    Preconditions: backend + frontend running, mock data available
    Steps:
      1. Navigate to http://localhost:5173/ (Setup page)
      2. Enter Weibo URL, click 开始比赛
      3. Assert redirect to /dashboard
      4. Wait for hot comments to appear (data-testid="comment-row")
      5. Wait for alert to appear (data-testid="alert-item")
      6. Click alert, type comment, select accounts, click support
      7. Assert action result displayed
      8. Click 结束比赛
      9. Assert redirect to /replay
      10. Assert replay data visible
      11. Screenshot final state
    Expected Result: Complete UI flow works end-to-end
    Failure Indicators: Any step fails, broken navigation
    Evidence: .omo/evidence/task-24-ui-flow.png

  Scenario: WebSocket message latency
    Tool: Bash (python)
    Preconditions: backend running, monitoring active
    Steps:
      1. Connect WebSocket
      2. Measure time between monitoring cycle start and WS message receipt
      3. Assert latency < 1000ms
    Expected Result: Messages arrive within 1 second
    Failure Indicators: Latency > 1s, messages lost
    Evidence: .omo/evidence/task-24-latency.txt
  ```

  **Commit**: YES (groups with Wave 4)
  - Message: `test(integration): end-to-end integration + anti-detection tuning`
  - Files: `backend/tests/test_integration.py, backend/app/services/anti_detection.py (tuned)`

---

## Final Verification Wave (MANDATORY — after ALL implementation tasks)

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle`
  Read the plan end-to-end. For each "Must Have": verify implementation exists (read file, curl endpoint, run command). For each "Must NOT Have": search codebase for forbidden patterns — reject with file:line if found. Check evidence files exist in .omo/evidence/. Compare deliverables against plan.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high`
  Run `pytest` + `tsc --noEmit` + linter. Review all changed files for: `as any`/`# type: ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check AI slop: excessive comments, over-abstraction, generic names.
  Output: `Build [PASS/FAIL] | Lint [PASS/FAIL] | Tests [N pass/N fail] | Files [N clean/N issues] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill)
  Start from clean state. Execute EVERY QA scenario from EVERY task — follow exact steps, capture evidence. Test cross-task integration. Test edge cases: cookie expiry, 500 limit, empty comment. Save to `.omo/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | Edge Cases [N tested] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep`
  For each task: read "What to do", read actual diff. Verify 1:1 — everything in spec was built, nothing beyond spec was built. Check "Must NOT do" compliance. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | Unaccounted [CLEAN/N files] | VERDICT`

---

## Commit Strategy

- **Wave 1**: `feat(scaffold): project scaffolding + foundation modules` - all Wave 1 files
- **Wave 2**: `feat(core): comment monitoring + action execution engine` - all Wave 2 files
- **Wave 3**: `feat(ui): real-time dashboard + alert interaction` - all Wave 3 files
- **Wave 4**: `feat(validation): API spike + replay + anti-detection tuning` - all Wave 4 files
- Pre-commit: `pytest && cd frontend && npm run build`

---

## Success Criteria

### Verification Commands
```bash
# Backend tests
cd backend && pytest --tb=short  # Expected: all tests PASS

# Frontend build
cd frontend && npm run build  # Expected: build succeeds, 0 errors

# API health check
curl http://localhost:8000/health  # Expected: {"status": "ok"}

# WebSocket connection
python -c "import websockets; asyncio.run(websockets.connect('ws://localhost:8000/ws'))"  # Expected: connects successfully

# Database exists
ls backend/data/weibo.db  # Expected: file exists
```

### Final Checklist
- [ ] All "Must Have" present
- [ ] All "Must NOT Have" absent
- [ ] All pytest tests pass
- [ ] Frontend builds without errors
- [ ] 20 accounts can QR login
- [ ] Comment monitoring works on real Weibo post
- [ ] Alert workflow functional (alert → input → select → execute)
- [ ] Dashboard updates in real-time
- [ ] Comment count ≤ 500 enforced
- [ ] Replay module shows historical data
