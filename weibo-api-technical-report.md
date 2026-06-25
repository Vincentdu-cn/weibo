# Weibo API Landscape & Anti-Bot Technical Report

> **Research Date**: June 2026  
> **Sources**: Official Weibo Open Platform docs, GitHub open-source projects (WeiboClient, WeiboSpider, WeiboApis), Chinese technical blogs (CSDN), and live endpoint analysis

---

## Table of Contents

1. [Official API (open.weibo.com)](#1-official-api-openweibocom)
2. [Web API (weibo.com/ajax/)](#2-web-api-weibocomajax)
3. [Mobile API (m.weibo.cn)](#3-mobile-api-mweibocn)
4. [Anti-Bot Mechanisms](#4-anti-bot-mechanisms)
5. [Evasion Strategies](#5-evasion-strategies)
6. [Posting / Liking / Commenting Endpoints](#6-posting--liking--commenting-endpoints)
7. [Cookie & Session Management](#7-cookie--session-management)
8. [Header Construction](#8-header-construction)
9. [Reference Implementations](#9-reference-implementations)

---

## 1. Official API (open.weibo.com)

### 1.1 Authentication

Weibo's official API uses **OAuth 2.0**. All requests require an `access_token` obtained through the OAuth flow.

- **Token endpoint**: `https://api.weibo.com/oauth2/access_token`
- **Grant types**: `authorization_code` (web flow), `password` (deprecated), `client_credentials`
- **Token lifetime**: Typically 7 days (app-dependent), refreshable

### 1.2 Rate Limiting

Official API rate limits are **per-endpoint** and **tiered by application level**:

| App Level | Requests/day | Requests/hour |
|-----------|--------------|---------------|
| Basic     | ~1,000       | ~150          |
| Standard  | ~10,000      | ~1,000        |
| Advanced  | ~100,000+    | ~10,000+      |

Each endpoint has its own sub-limits. For example, `comments/show` may have a lower limit than `statuses/user_timeline`. See [接口访问频次权限](https://open.weibo.com/wiki/接口访问频次权限).

### 1.3 Comment Endpoints (Official)

#### Get Comments — `2/comments/show`

- **URL**: `GET https://api.weibo.com/2/comments/show.json`
- **Auth**: OAuth `access_token` (required)
- **Parameters**:

| Parameter | Required | Type   | Description |
|-----------|----------|--------|-------------|
| access_token | true | string | OAuth token |
| id        | true     | int64  | Weibo status ID |
| since_id | false    | int64  | Return comments newer than this ID |
| max_id   | false    | int64  | Return comments older than this ID |
| count    | false    | int    | Items per page (default 50, max 200) |
| page     | false    | int    | Page number (default 1) |
| filter_by_author | false | int | 0: all, 1: following only, 2: original author only |

**Example request**:
```
GET https://api.weibo.com/2/comments/show.json?access_token=2.00xxx&id=4987654321&count=50&page=1
```

**Response structure** (abbreviated):
```json
{
  "total_number": 1234,
  "comments": [
    {
      "created_at": "Wed Jun 01 00:50:25 +0800 2011",
      "id": 12438492184,
      "text": "评论内容",
      "source": "<a href=\"...\">新浪微博</a>",
      "mid": "202110601896455629",
      "user": { "id": 1404376560, "screen_name": "zaku", ... },
      "status": { "id": 11488058246, "text": "原微博", ... }
    }
  ]
}
```

**Source**: [Official docs](https://open.weibo.com/wiki/2/comments/show)

---

#### Create Comment — `2/comments/create`

- **URL**: `POST https://api.weibo.com/2/comments/create.json`
- **Auth**: OAuth (required)
- **Parameters**:

| Parameter | Required | Type   | Description |
|-----------|----------|--------|-------------|
| access_token | true | string | OAuth token |
| id        | true     | int64  | Weibo status ID to comment on |
| comment   | true     | string | Comment text (URL-encoded, max 140 Chinese chars) |
| comment_ori | false | int   | 0: don't comment original, 1: also comment original (default 0) |
| rip       | true     | string | Real user IP (e.g., `211.156.0.1`) |

**Note**: The `rip` parameter is mandatory — Weibo requires developers to report the real user IP.

**Source**: [Official docs](https://open.weibo.com/wiki/2/comments/create)

---

#### Reply to Comment — `2/comments/reply`

- **URL**: `POST https://api.weibo.com/2/comments/reply.json`
- **Auth**: OAuth (required)
- **Parameters**:

| Parameter | Required | Type   | Description |
|-----------|----------|--------|-------------|
| access_token | true | string | OAuth token |
| cid       | true     | int64  | Comment ID to reply to |
| id        | true     | int64  | Weibo status ID |
| comment   | true     | string | Reply text (URL-encoded, max 140 chars) |
| without_mention | false | int | 0: auto-add "@username", 1: don't (default 0) |
| comment_ori | false | int   | 0: don't comment original, 1: also comment original |
| rip       | true     | string | Real user IP |

**Source**: [Official docs](https://open.weibo.com/wiki/2/comments/reply)

---

#### Delete Comment — `2/comments/destroy`

- **URL**: `POST https://api.weibo.com/2/comments/destroy.json`
- **Auth**: OAuth (required)
- **Parameters**:

| Parameter | Required | Type   | Description |
|-----------|----------|--------|-------------|
| access_token | true | string | OAuth token |
| cid       | true     | int64  | Comment ID to delete (only own comments) |

**Source**: [Official docs](https://open.weibo.com/wiki/2/comments/destroy)

---

### 1.4 Official API Limitations

- **OAuth requirement**: Every endpoint requires user-level OAuth tokens — no anonymous access
- **App review**: Creating an app requires business verification and manual review
- **Scope restrictions**: Comment/post endpoints require elevated permissions not granted by default
- **Rate limits**: Strict per-endpoint limits make bulk operations impractical
- **rip parameter**: Developer must report real user IP — Weibo tracks this for anti-abuse

### 1.5 Other Key Official Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `2/statuses/show` | GET | Get a single weibo by ID |
| `2/statuses/user_timeline` | GET | Get a user's posts |
| `2/statuses/repost` | POST | Repost a weibo |
| `2/statuses/update` | POST | Post a new weibo |
| `2/statuses/upload` | POST | Post a weibo with image |
| `2/friendships/create` | POST | Follow a user |
| `2/favorites/create` | POST | Favorite a weibo |
| `2/comments/destroy_batch` | POST | Delete multiple comments |

---

## 2. Web API (weibo.com/ajax/)

The web AJAX API is the primary interface used by `weibo.com` in the browser. It requires **cookie-based authentication** (not OAuth) and the `x-xsrf-token` header. This is the most commonly scraped API for automation.

### 2.1 Get Comments (Web)

- **URL**: `GET https://weibo.com/ajax/statuses/buildComments`
- **Key Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `id`      | int  | Weibo status ID (mid) |
| `uid`     | int  | Current user ID |
| `flow`    | int  | **0**: hot order, **1**: time order |
| `is_reload` | int | 1 for reload |
| `is_show_bulletin` | int | 2 |
| `is_mix`  | int  | 0 for top-level, 1 for child comments |
| `max_id`  | int  | Pagination cursor (0 for first page) |
| `count`   | int  | Items per page (default 20) |
| `fetch_level` | int | 0 for top-level, 1 for child |

**Pagination**: The response includes a `max_id` field. Use it as the `max_id` parameter for the next page. When `max_id` is 0 or absent, the first page is returned.

**Child comments**: To get replies to a comment, use the same endpoint with:
```
is_mix=1&fetch_level=1&max_id=0&count=100
```

**Implementation reference** — WeiboSpider `comment.py`:
```python
# From: nghuyong/WeiboSpider - weibospider/spiders/comment.py
def get_comments_by_mid(self, mid, max_id=0, flow=0):
    url = "https://weibo.com/ajax/statuses/buildComments"
    params = {
        'flow': flow,
        'is_reload': 1,
        'id': mid,
        'is_show_bulletin': 2,
        'is_mix': 0,
        'max_id': max_id,
        'count': 20,
        'uid': self.uid
    }
    # ... fetch and parse response
    # Next page: response['max_id']
```

### 2.2 Get Likes (Web)

- **URL**: `GET https://weibo.com/ajax/statuses/likeShow`
- **Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `id`      | int  | Weibo status ID |
| `attitude_type` | int | 0 for likes |
| `attitude_enable` | int | 1 |
| `page`    | int  | Page number (starts at 1) |
| `count`   | int  | Items per page (default 10) |

### 2.3 Post Comment (Web)

- **URL**: `POST https://weibo.com/ajax/comments/create`
- **Body** (JSON):

```json
{
  "id": 4987654321,
  "comment": "评论内容",
  "pic_id": "",
  "is_repost": 0,
  "comment_ori": 0,
  "is_comment": 0
}
```

**Implementation reference** — WeiboClient `__init__.py`:
```python
# From: saermart/WeiboClient - weibo/__init__.py
def comment_tweet(self, tweet_id, content):
    url = "https://weibo.com/ajax/comments/create"
    data = {
        "id": tweet_id,
        "comment": content,
        "pic_id": "",
        "is_repost": 0,
        "comment_ori": 0,
        "is_comment": 0
    }
    return self._post(url, data=data)
```

### 2.4 Reply to Comment (Web)

- **URL**: `POST https://weibo.com/ajax/comments/reply`
- **Body** (JSON):

```json
{
  "id": 4987654321,
  "cid": 1234567890,
  "comment": "回复内容",
  "pic_id": "",
  "is_repost": 0,
  "comment_ori": 0,
  "is_comment": 0
}
```

**Implementation reference** — WeiboClient:
```python
def reply_to_comment(self, tweet_id, comment_id, content):
    url = "https://weibo.com/ajax/comments/reply"
    data = {
        "id": tweet_id,
        "cid": comment_id,
        "comment": content,
        "pic_id": "",
        "is_repost": 0,
        "comment_ori": 0,
        "is_comment": 0
    }
    return self._post(url, data=data)
```

### 2.5 Like / Unlike Tweet (Web)

- **Like**: `POST https://weibo.com/ajax/statuses/setLike`
- **Unlike**: `POST https://weibo.com/ajax/statuses/cancelLike`
- **Body** (JSON):

```json
{
  "id": 4987654321
}
```

**Implementation reference** — WeiboClient:
```python
def like_tweet(self, tweet_id):
    url = "https://weibo.com/ajax/statuses/setLike"
    data = {"id": str(tweet_id)}
    return self._post(url, data=data)

def unlike_tweet(self, tweet_id):
    url = "https://weibo.com/ajax/statuses/cancelLike"
    data = {"id": str(tweet_id)}
    return self._post(url, data=data)
```

### 2.6 Repost (Web)

- **URL**: `POST https://weibo.com/ajax/statuses/repost`
- **Alternative**: `POST https://weibo.com/ajax/statuses/normal_repost`
- **Body** (JSON):

```json
{
  "id": 4987654321,
  "comment": "转发理由",
  "pic_id": "",
  "share_id": 0,
  "isReEdit": false,
  "mode": 0
}
```

### 2.7 Delete Comment (Web)

- **URL**: `POST https://weibo.com/ajax/comments/destroy`
- **Body** (JSON):

```json
{
  "cid": 1234567890
}
```

### 2.8 Other Key Web AJAX Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ajax/profile/info` | GET | Get user profile info |
| `/ajax/statuses/mymblog` | GET | Get user's posts |
| `/ajax/statuses/show` | GET | Get single weibo details |
| `/ajax/friendships/create` | POST | Follow a user |
| `/ajax/friendships/destroy` | POST | Unfollow a user |
| `/ajax/favorites/create` | POST | Favorite a weibo |
| `/ajax/favorites/destroy` | POST | Unfavorite |
| `/ajax/profile/followContent` | GET | Get followers/following list |
| `/ajax/statuses/searchProfile` | GET | Search weibo posts |
| `/ajax/side/hotSearch` | GET | Get trending topics |

---

## 3. Mobile API (m.weibo.cn)

The mobile API is lighter and has historically had less aggressive anti-bot controls. It's widely used by scrapers.

### 3.1 Get Comments (Mobile)

- **URL**: `GET https://m.weibo.cn/comments/hotflow`
- **Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `id`      | int  | Weibo status ID |
| `mid`     | int  | Same as id (weibo mid) |
| `max_id`  | int  | Pagination cursor (omit for first page) |
| `max_id_type` | int | Pagination type indicator |

**Pagination mechanics**:
- First page: omit `max_id`, set `max_id_type=0`
- Response includes `max_id` and `max_id_type` for next page
- `max_id_type` changes periodically (approximately every 16 pages)
- When `max_id_type` changes, the parsing of `max_id` must also change

**Implementation reference** (found in GitHub search results):
```python
def fetch_comments_mobile(self, mid):
    url = "https://m.weibo.cn/comments/hotflow"
    params = {
        'id': mid,
        'mid': mid,
        'max_id_type': 0  # First page
    }
    # Subsequent pages:
    # params['max_id'] = response['data']['max_id']
    # params['max_id_type'] = response['data']['max_id_type']
```

### 3.2 Get Child Comments (Mobile)

- **URL**: `GET https://m.weibo.cn/comments/hotFlowChild`
- **Parameters**: Similar to `hotflow`, with additional `cid` (parent comment ID)

### 3.3 Get Likes (Mobile)

- **URL**: `GET https://m.weibo.cn/api/attitudes/show`
- **Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `id`      | int  | Weibo status ID |
| `page`    | int  | Page number |
| `count`   | int  | Items per page |

### 3.4 Get Reposts (Mobile)

- **URL**: `GET https://m.weibo.cn/api/statuses/repostTimeline`
- **Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `id`      | int  | Weibo status ID |
| `page`    | int  | Page number |
| `count`   | int  | Items per page |

### 3.5 Get User Posts (Mobile)

- **URL**: `GET https://m.weibo.cn/api/container/getIndex`
- **Parameters**:

| Parameter | Type | Description |
|-----------|------|-------------|
| `type`    | string | `uid` for user ID |
| `value`   | string | User ID |
| `containerid` | string | `107603{uid}` for posts |

### 3.6 Get Tweet Detail (Mobile)

- **URL**: `GET https://m.weibo.cn/statuses/show`
- **Parameters**: `id` (weibo ID)

---

## 4. Anti-Bot Mechanisms

### 4.1 Cookie-IP Binding

**Mechanism**: Weibo binds each session cookie to the IP address it was issued from. If a request comes from a different IP using the same cookie, the session is **immediately invalidated**.

**Implications**:
- Cannot use a single cookie across multiple proxy IPs
- Cookie pools must maintain 1:1 cookie-to-IP mapping
- Datacenter IPs (AWS, Aliyun) are often pre-flagged

### 4.2 Cookie Lifecycle Management

- Cookies have **short lifetimes** (measured in hours, not days)
- Abnormal behavior triggers **immediate cookie invalidation**
- Repeated violations result in **permanent account bans**
- The `SUB` cookie is the primary session token; `SUBP` is the profile token

### 4.3 Forced Login Wall

- Without login, only **5-10 items** are visible on most pages
- **90%+ of AJAX APIs** reject unauthenticated requests (return empty or error)
- Mobile site (`m.weibo.cn`) is slightly more lenient but still limits unauthenticated access

### 4.4 JavaScript Encryption

- Nearly all web API requests include **dynamically encrypted parameters**
- Key encrypted parameters: `_s`, `__wb_hash`
- The encryption algorithm is **obfuscated in client-side JS**
- The algorithm **changes every 3-6 months**, breaking reverse-engineered implementations
- Without the correct encrypted params, requests may be silently rejected or rate-limited more aggressively

### 4.5 Multi-Layer CAPTCHA

Weibo employs multiple CAPTCHA types, escalating based on suspicion level:

| Level | Type | Description |
|-------|------|-------------|
| 1     | Slider | Drag slider to match position |
| 2     | Text click | Click characters in specified order |
| 3     | Icon click | Click matching icons |
| 4     | Behavioral | Pixel-level mouse trajectory analysis |

**Detection**: CAPTCHAs are triggered based on:
- Request frequency from IP/cookie
- Behavioral patterns (too fast, too regular)
- Account age and trust score
- Geographic anomalies

### 4.6 Behavioral Analysis

Weibo monitors:
- **Browsing trajectory**: Navigation paths between pages
- **Dwell time**: Time spent on each page
- **Click frequency**: Rate of interactions
- **Scroll patterns**: Whether scrolling resembles human behavior
- **Session patterns**: Login time, session duration, geographic consistency

### 4.7 Request Frequency Limits

- **Per-IP rate limits**: Excessive same-type requests from one IP → temporary ban (typically 1-24 hours)
- **Per-cookie rate limits**: Too many requests with one cookie → cookie invalidation
- **Per-account rate limits**: Aggressive actions (mass following, mass commenting) → account restriction
- **Graduated response**: Warning → rate reduction → temporary block → permanent ban

### 4.8 Visitor Token System

For unauthenticated access, Weibo uses a **visitor token system**:

- `GET https://passport.weibo.com/visitor/genvisitor` — generates a visitor token
- The token is exchanged for temporary cookies (`SUB`, `SUBP`)
- Visitor tokens have very limited access and short lifetimes
- Frequent visitor token generation from the same IP is flagged

**Implementation reference** — WeiboClient `cookie.py`:
```python
# From: saermart/WeiboClient - weibo/cookie.py
def gen_visitor_cookies():
    """Generate visitor cookies via passport.weibo.com"""
    url = "https://passport.weibo.com/visitor/genvisitor"
    data = {
        "cb": "gen_callback",
        "fp": json.dumps({
            "os": "2",
            "browser": "Chrome128,0,0,0",
            "fonts": "undefined",
            "screenInfo": "1920*1080*24",
            "plugins": ""
        })
    }
    # POST to get visitor token, then exchange for cookies
    # ...
```

---

## 5. Evasion Strategies

### 5.1 Cookie Tiering

Categorize cookies by trust level and assign appropriate tasks:

| Tier | Usage | Max Requests | Lifetime |
|------|-------|-------------|----------|
| **High** | Comments, user info, posting | 5-10 per action type | 1-2 hours |
| **Medium** | Trending topics, search | 20-30 requests | 2-4 hours |
| **Low** | Auxiliary (profile pics, metadata) | 50+ requests | 4-8 hours |

### 5.2 Cookie Pool Management

```
┌──────────────────────────────────────────┐
│           Cookie Pool Manager             │
├──────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  │
│  │ Cookie A│  │ Cookie B│  │ Cookie C│  │
│  │ IP: 1.2 │  │ IP: 3.4 │  │ IP: 5.6 │  │
│  │ Uses: 3 │  │ Uses: 7 │  │ Uses: 1 │  │
│  └─────────┘  └─────────┘  └─────────┘  │
│                                          │
│  Health Check: Every 1 hour              │
│  Replenish: QR login when pool < 5       │
│  Max per cookie: 10 req or 1 hour        │
└──────────────────────────────────────────┘
```

**Key rules**:
- **Max 10 requests or 1 hour** per cookie before rotation
- **Auto-detect validity** hourly (test with a lightweight endpoint)
- **Auto-replenish** via QR code login when pool drops below threshold
- **Never reuse** a cookie from a different IP

### 5.3 Proxy Rotation

- **Maintain cookie-IP 1:1 binding**: Each cookie is permanently assigned to one proxy IP
- **Residential proxies** preferred over datacenter IPs
- **Sticky sessions**: Use the same proxy for the entire cookie lifetime
- **Proxy pool size**: Should be ≥ cookie pool size

**Implementation pattern**:
```python
class CookieProxyPair:
    def __init__(self, cookie, proxy):
        self.cookie = cookie  # dict of cookies
        self.proxy = proxy    # e.g., "http://user:pass@ip:port"
        self.request_count = 0
        self.created_at = time.time()
    
    def is_expired(self):
        return (self.request_count >= 10 or 
                time.time() - self.created_at > 3600)
```

### 5.4 Request Delay & Randomization

- **Base delay**: 2-5 seconds between requests
- **Random jitter**: Add ±1-3 seconds random offset
- **Burst avoidance**: Never make more than 3 consecutive requests without a longer pause
- **Page-level delays**: Observed in WeiboSpider:
```python
# From: nghuyong/WeiboSpider
time.sleep(self.sleep_time)  # Between pagination calls
```
- **Action delays**: For posting/commenting/liking, wait 30-120 seconds between actions
- **Time-of-day variation**: Reduce frequency during peak hours (19:00-23:00 CST)

### 5.5 User-Agent Rotation

**Implementation reference** — WeiboClient `header.py`:
```python
# From: saermart/WeiboClient - weibo/header.py
class FakeChromeUA:
    VERSIONS = [
        "128.0.0.0",
        "127.0.0.0",
        "126.0.0.0",
        "125.0.0.0",
    ]
    
    @classmethod
    def get_ua(cls):
        v = random.choice(cls.VERSIONS)
        return (f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                f"AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{v} Safari/537.36 Edg/{v}")
```

### 5.6 Behavioral Mimicry

- **Simulate browsing**: Before making API calls, "visit" a few normal pages
- **Mouse movement**: If using headless browsers, simulate human-like mouse trajectories
- **Referer chain**: Always set appropriate `Referer` header matching a real navigation path
- **Session warming**: Make a few GET requests to `weibo.com` before hitting AJAX endpoints

### 5.7 QR Code Login for Cookie Acquisition

QR code login is the safest method for bulk cookie acquisition:

```
1. GET  https://login.sina.com.cn/ssologin/getqrimage  → QR image + qrid
2. POLL https://login.sina.com.cn/ssologin/qrcode/check?qrid={qrid}
   → Returns "scanned" / "confirmed" status
3. On confirm → Exchange auth token for SUB/SUBP cookies
4. Bind cookie to current IP immediately
```

**Advantages**:
- No password transmission
- Each QR login creates a fresh session
- Can be automated with multiple accounts
- Sessions are independent (no cross-contamination)

---

## 6. Posting / Liking / Commenting Endpoints

### 6.1 Complete Endpoint Reference Table

| Action | Method | URL | Auth | Body Type |
|--------|--------|-----|------|-----------|
| Post weibo (text) | POST | `/ajax/statuses/update` | Cookie | JSON |
| Post weibo (with image) | POST | `/ajax/statuses/uploadPic` + `/ajax/statuses/update` | Cookie | Multipart + JSON |
| Comment on weibo | POST | `/ajax/comments/create` | Cookie | JSON |
| Reply to comment | POST | `/ajax/comments/reply` | Cookie | JSON |
| Delete comment | POST | `/ajax/comments/destroy` | Cookie | JSON |
| Like weibo | POST | `/ajax/statuses/setLike` | Cookie | JSON |
| Unlike weibo | POST | `/ajax/statuses/cancelLike` | Cookie | JSON |
| Repost weibo | POST | `/ajax/statuses/repost` | Cookie | JSON |
| Follow user | POST | `/ajax/friendships/create` | Cookie | JSON |
| Unfollow user | POST | `/ajax/friendships/destroy` | Cookie | JSON |
| Favorite weibo | POST | `/ajax/favorites/create` | Cookie | JSON |
| Unfavorite | POST | `/ajax/favorites/destroy` | Cookie | JSON |

### 6.2 Comment Creation — Detailed

**Endpoint**: `POST https://weibo.com/ajax/comments/create`

**Required headers**:
```
Content-Type: application/json;charset=UTF-8
x-xsrf-token: {from XSRF-TOKEN cookie}
x-requested-with: XMLHttpRequest
referer: https://weibo.com/u/{uid}
user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) ...
cookie: SUB=...; SUBP=...; XSRF-TOKEN=...
```

**Request body**:
```json
{
  "id": 4987654321,
  "comment": "这条微博很有意思",
  "pic_id": "",
  "is_repost": 0,
  "comment_ori": 0,
  "is_comment": 0
}
```

**Response** (success):
```json
{
  "id": 1234567890123456,
  "created_at": "Wed Jun 24 12:00:00 +0800 2026",
  "text": "这条微博很有意思",
  "user": { ... }
}
```

### 6.3 Like — Detailed

**Endpoint**: `POST https://weibo.com/ajax/statuses/setLike`

**Request body**:
```json
{
  "id": "4987654321"
}
```

**Response** (success):
```json
{
  "ok": 1,
  "attitude": { "id": 4987654321, "attitude": "like" }
}
```

### 6.4 Posting a New Weibo

**Endpoint**: `POST https://weibo.com/ajax/statuses/update`

**Request body**:
```json
{
  "content": "微博正文内容",
  "pic_id": "",
  "tag": 0,
  "isReEdit": false,
  "mode": 0,
  "location": "",
  "sub_topics": [],
  "text": "微博正文内容",
  "attitudes": [],
  "gif_ids": "",
  "pic_num": 0
}
```

**With image**: First upload via `POST /ajax/statuses/uploadPic` (multipart/form-data), receive `pic_id`, then include in `update` call.

---

## 7. Cookie & Session Management

### 7.1 Essential Cookies

| Cookie | Description | Lifetime |
|--------|-------------|----------|
| `SUB` | Primary session token | ~24 hours (varies) |
| `SUBP` | Profile/auth token | ~24 hours |
| `XSRF-TOKEN` | CSRF protection token | ~1 hour (rotates) |
| `ALF` | Auto-login flag | ~30 days |
| `SSOLoginState` | SSO login timestamp | Session |
| `_T_WM` | Mobile session token | Session |

### 7.2 XSRF-TOKEN Handling

The `XSRF-TOKEN` cookie must be sent as the `x-xsrf-token` header on every POST request:

```python
# From: cv-cat/WeiboApis - utils/weibo_utils.py
def get_common_headers(self, xsrf_token):
    return {
        'accept': 'application/json, text/plain, */*',
        'client-version': 'v2.46.7',
        'x-xsrf-token': xsrf_token,
        'x-requested-with': 'XMLHttpRequest',
        'user-agent': FakeChromeUA.get_ua(),
        'referer': f'https://weibo.com/u/{self.uid}',
        'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
    }
```

**Token rotation**: The `XSRF-TOKEN` cookie changes periodically. After each request, check the `Set-Cookie` headers for a new token and update your session.

### 7.3 Cookie Refresh Flow

```
1. Detect cookie expiry (API returns 302 to login or empty response)
2. Option A: QR code login → new SUB/SUBP cookies
3. Option B: Visitor token → limited access cookies
4. Option C: Auto-login using ALF cookie (if available)
5. Bind new cookies to current IP
6. Update cookie pool
```

### 7.4 QR Code Login Implementation

```python
import requests
import time

class WeiboQrLogin:
    def __init__(self):
        self.session = requests.Session()
    
    def get_qr_image(self):
        """Step 1: Get QR code image and qrid"""
        url = "https://login.sina.com.cn/ssologin/getqrimage"
        resp = self.session.get(url)
        qrid = resp.json().get('qrid')
        image_url = resp.json().get('image')
        return qrid, image_url
    
    def check_scan_status(self, qrid):
        """Step 2: Poll for scan status"""
        url = f"https://login.sina.com.cn/ssologin/qrcode/check?qrid={qrid}"
        resp = self.session.get(url)
        data = resp.json()
        # data['retcode']: 0=success, 50114001=waiting, 50114002=scanned
        return data
    
    def get_cookies(self, alt, qrid):
        """Step 3: Exchange alt for session cookies"""
        url = f"https://login.sina.com.cn/ssologin/qrcode/login?alt={alt}&qrid={qrid}"
        resp = self.session.get(url)
        # Extract SUB, SUBP, XSRF-TOKEN from response cookies
        return self.session.cookies.get_dict()
    
    def login(self):
        """Full QR login flow"""
        qrid, image_url = self.get_qr_image()
        print(f"Scan: {image_url}")
        
        while True:
            data = self.check_scan_status(qrid)
            if data['retcode'] == 0:
                # Success — get cookies
                alt = data['data']['alt']
                cookies = self.get_cookies(alt, qrid)
                return cookies
            time.sleep(2)
```

---

## 8. Header Construction

### 8.1 Complete Header Template

Based on analysis of `weibo_utils.py` from WeiboApis and `header.py` from WeiboClient:

```python
def build_headers(uid, xsrf_token, extra=None):
    headers = {
        # Core headers
        'accept': 'application/json, text/plain, */*',
        'accept-language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'content-type': 'application/json;charset=UTF-8',
        
        # Anti-bot headers
        'user-agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0'
        ),
        'x-xsrf-token': xsrf_token,
        'x-requested-with': 'XMLHttpRequest',
        
        # Context headers
        'referer': f'https://weibo.com/u/{uid}',
        'origin': 'https://weibo.com',
        
        # Client versioning
        'client-version': 'v2.46.7',
        
        # Chrome fingerprinting (sec-ch-ua)
        'sec-ch-ua': '"Chromium";v="128", "Not;A=Brand";v="24", '
                     '"Google Chrome";v="128", "Edge";v="128"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        
        # Sec-fetch
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
    }
    if extra:
        headers.update(extra)
    return headers
```

### 8.2 Key Header Notes

- **`x-xsrf-token`**: MUST match the `XSRF-TOKEN` cookie value exactly. Missing or mismatched → 403.
- **`referer`**: Must be a valid `weibo.com` URL. Missing referer → some endpoints return empty.
- **`client-version`**: Mimics the web client version. Update periodically to match the current `weibo.com` version.
- **`sec-ch-ua` headers**: These are Chrome client hints. They must be internally consistent (version numbers must match `user-agent`).
- **`x-requested-with: XMLHttpRequest`**: Required for AJAX endpoints. Without it, some endpoints return HTML instead of JSON.

---

## 9. Reference Implementations

### 9.1 Source Repositories Analyzed

| Repository | Stars | Focus | Key Files |
|-----------|-------|-------|-----------|
| [saermart/WeiboClient](https://github.com/saermart/WeiboClient) | ~2k | Full automation (comment, like, post, repost) | `weibo/__init__.py`, `weibo/api.py`, `weibo/cookie.py`, `weibo/header.py` |
| [nghuyong/WeiboSpider](https://github.com/nghuyong/WeiboSpider) | ~4k | Scrapy-based scraper (comments, tweets, users) | `weibospider/spiders/comment.py` |
| [cv-cat/WeiboApis](https://github.com/cv-cat/WeiboApis) | ~1k | Web API wrapper (user info, posts, search) | `apis/weibo_apis.py`, `utils/weibo_utils.py` |

### 9.2 Minimal Comment Bot Example

Combining all research findings:

```python
import requests
import time
import random
import json

class WeiboBot:
    def __init__(self, cookie_str, uid, proxy=None):
        self.uid = uid
        self.proxy = proxy
        self.session = requests.Session()
        
        # Parse cookies
        for pair in cookie_str.split(';'):
            key, _, value = pair.strip().partition('=')
            self.session.cookies.set(key, value, domain='.weibo.com')
        
        # Extract XSRF-TOKEN
        self.xsrf_token = self.session.cookies.get('XSRF-TOKEN', '')
        
        self.request_count = 0
    
    def _headers(self):
        return {
            'accept': 'application/json, text/plain, */*',
            'content-type': 'application/json;charset=UTF-8',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                          'AppleWebKit/537.36 Chrome/128.0.0.0 Safari/537.36',
            'x-xsrf-token': self.xsrf_token,
            'x-requested-with': 'XMLHttpRequest',
            'referer': f'https://weibo.com/u/{self.uid}',
            'origin': 'https://weibo.com',
        }
    
    def _post(self, url, data):
        # Rate limiting
        delay = random.uniform(3, 8)
        time.sleep(delay)
        
        resp = self.session.post(
            url,
            json=data,
            headers=self._headers(),
            proxies={'https': self.proxy} if self.proxy else None
        )
        
        # Update XSRF-TOKEN if rotated
        new_token = resp.cookies.get('XSRF-TOKEN')
        if new_token:
            self.xsrf_token = new_token
        
        self.request_count += 1
        return resp.json()
    
    def _get(self, url, params=None):
        delay = random.uniform(2, 5)
        time.sleep(delay)
        
        resp = self.session.get(
            url,
            params=params,
            headers=self._headers(),
            proxies={'https': self.proxy} if self.proxy else None
        )
        
        self.request_count += 1
        return resp.json()
    
    def comment(self, tweet_id, content):
        """Comment on a weibo post"""
        url = "https://weibo.com/ajax/comments/create"
        data = {
            "id": tweet_id,
            "comment": content,
            "pic_id": "",
            "is_repost": 0,
            "comment_ori": 0,
            "is_comment": 0
        }
        return self._post(url, data)
    
    def reply_comment(self, tweet_id, comment_id, content):
        """Reply to a comment"""
        url = "https://weibo.com/ajax/comments/reply"
        data = {
            "id": tweet_id,
            "cid": comment_id,
            "comment": content,
            "pic_id": "",
            "is_repost": 0,
            "comment_ori": 0,
            "is_comment": 0
        }
        return self._post(url, data)
    
    def like(self, tweet_id):
        """Like a weibo post"""
        url = "https://weibo.com/ajax/statuses/setLike"
        return self._post(url, {"id": str(tweet_id)})
    
    def unlike(self, tweet_id):
        """Unlike a weibo post"""
        url = "https://weibo.com/ajax/statuses/cancelLike"
        return self._post(url, {"id": str(tweet_id)})
    
    def get_comments(self, tweet_id, max_id=0, flow=0):
        """Fetch comments on a weibo post"""
        url = "https://weibo.com/ajax/statuses/buildComments"
        params = {
            'flow': flow,
            'is_reload': 1,
            'id': tweet_id,
            'is_show_bulletin': 2,
            'is_mix': 0,
            'max_id': max_id,
            'count': 20,
            'uid': self.uid
        }
        return self._get(url, params)
    
    def is_expired(self):
        """Check if this session should be rotated"""
        return self.request_count >= 10
    
    def delete_comment(self, comment_id):
        """Delete a comment"""
        url = "https://weibo.com/ajax/comments/destroy"
        return self._post(url, {"cid": comment_id})
```

### 9.3 Cookie Pool Manager Example

```python
import time
import random
from collections import deque

class CookiePool:
    def __init__(self, max_size=20):
        self.pool = deque(maxlen=max_size)
        self.max_requests = 10
        self.max_age = 3600  # 1 hour
    
    def add(self, cookie_str, uid, proxy):
        """Add a new cookie-proxy pair"""
        bot = WeiboBot(cookie_str, uid, proxy)
        self.pool.append({
            'bot': bot,
            'created_at': time.time(),
            'cookie': cookie_str,
            'proxy': proxy
        })
    
    def get(self):
        """Get a healthy bot from the pool"""
        self._cleanup()
        if not self.pool:
            raise Exception("Cookie pool empty — replenish needed")
        
        entry = random.choice(list(self.pool))
        return entry['bot']
    
    def _cleanup(self):
        """Remove expired entries"""
        now = time.time()
        while self.pool:
            entry = self.pool[0]
            if (entry['bot'].request_count >= self.max_requests or
                now - entry['created_at'] > self.max_age):
                self.pool.popleft()
            else:
                break
    
    def size(self):
        return len(self.pool)
    
    def health_check(self):
        """Test all cookies with a lightweight request"""
        healthy = []
        for entry in list(self.pool):
            try:
                # Lightweight test endpoint
                entry['bot']._get(
                    "https://weibo.com/ajax/profile/info",
                    params={'uid': entry['bot'].uid}
                )
                healthy.append(entry)
            except:
                pass  # Cookie is dead, don't keep it
        self.pool = deque(healthy, maxlen=self.pool.maxlen)
```

---

## 10. Summary & Architecture Recommendations

### 10.1 API Selection Matrix

| Use Case | Recommended API | Auth | Notes |
|----------|----------------|------|-------|
| Read comments | Web AJAX (`buildComments`) | Cookie | Most complete data, supports pagination |
| Read comments (fallback) | Mobile (`hotflow`) | Cookie/Visitor | Lighter anti-bot, but complex pagination |
| Read comments (bulk) | Official (`2/comments/show`) | OAuth | Rate limited but reliable |
| Post comments | Web AJAX (`comments/create`) | Cookie | Fastest, but highest ban risk |
| Like posts | Web AJAX (`setLike`) | Cookie | Low data, high volume |
| Post weibo | Web AJAX (`statuses/update`) | Cookie | Requires image upload for media posts |
| User profiles | Web AJAX (`profile/info`) | Cookie | Rich data, moderate rate limit |
| Bulk scraping | Mobile (`getIndex`) | Cookie/Visitor | Best for large-scale data collection |

### 10.2 Recommended Architecture

```
┌─────────────────────────────────────────────────┐
│                Task Queue (Redis)                │
│         (comments to post, likes to do)          │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Task Dispatcher                      │
│  - Rate limiting (per-cookie, per-IP)            │
│  - Task prioritization                           │
│  - Retry with backoff                            │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│           Cookie Pool Manager                     │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐           │
│  │Bot A │ │Bot B │ │Bot C │ │Bot D │  ...       │
│  │IP:1  │ │IP:2  │ │IP:3  │ │IP:4  │           │
│  └──────┘ └──────┘ └──────┘ └──────┘           │
│  - Auto-rotation (10 req / 1hr)                  │
│  - Health checks (hourly)                        │
│  - QR login replenishment                        │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│            Proxy Pool (Sticky Sessions)           │
│  - Residential proxies (preferred)               │
│  - 1:1 cookie-to-proxy binding                   │
│  - Geographic distribution                       │
└──────────────────────┬──────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────┐
│              Anti-Detection Layer                 │
│  - UA rotation                                    │
│  - Random delays (2-8s base + jitter)            │
│  - Behavioral simulation (pre-browse)            │
│  - CAPTCHA detection & alerting                   │
│  - XSRF-TOKEN auto-refresh                       │
└─────────────────────────────────────────────────┘
```

### 10.3 Critical Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| Cookie invalidation | Pool rotation, 10 req max per cookie |
| IP ban | Residential proxies, 1:1 binding |
| CAPTCHA trigger | Slow down, humanize behavior, CAPTCHA solving service |
| Account ban | Multiple accounts, never reuse banned IP |
| JS encryption changes | Monitor and update quarterly, fallback to official API |
| Rate limit | Per-endpoint tracking, adaptive throttling |

---

## Appendix A: Key Endpoint URL Reference

### Official API (OAuth)
```
GET  https://api.weibo.com/2/comments/show.json
POST https://api.weibo.com/2/comments/create.json
POST https://api.weibo.com/2/comments/reply.json
POST https://api.weibo.com/2/comments/destroy.json
GET  https://api.weibo.com/2/statuses/show.json
GET  https://api.weibo.com/2/statuses/user_timeline.json
POST https://api.weibo.com/2/statuses/repost.json
POST https://api.weibo.com/2/statuses/update.json
```

### Web AJAX (Cookie)
```
GET  https://weibo.com/ajax/statuses/buildComments
GET  https://weibo.com/ajax/statuses/likeShow
GET  https://weibo.com/ajax/statuses/show
GET  https://weibo.com/ajax/profile/info
GET  https://weibo.com/ajax/statuses/mymblog
POST https://weibo.com/ajax/comments/create
POST https://weibo.com/ajax/comments/reply
POST https://weibo.com/ajax/comments/destroy
POST https://weibo.com/ajax/statuses/setLike
POST https://weibo.com/ajax/statuses/cancelLike
POST https://weibo.com/ajax/statuses/repost
POST https://weibo.com/ajax/statuses/update
POST https://weibo.com/ajax/friendships/create
POST https://weibo.com/ajax/friendships/destroy
POST https://weibo.com/ajax/favorites/create
POST https://weibo.com/ajax/favorites/destroy
```

### Mobile API (Cookie/Visitor)
```
GET  https://m.weibo.cn/comments/hotflow
GET  https://m.weibo.cn/comments/hotFlowChild
GET  https://m.weibo.cn/api/attitudes/show
GET  https://m.weibo.cn/api/statuses/repostTimeline
GET  https://m.weibo.cn/api/container/getIndex
GET  https://m.weibo.cn/statuses/show
```

### Authentication Endpoints
```
POST https://login.sina.com.cn/ssologin/getqrimage       (QR image)
GET  https://login.sina.com.cn/ssologin/qrcode/check      (QR scan status)
GET  https://login.sina.com.cn/ssologin/qrcode/login      (QR login callback)
POST https://passport.weibo.com/visitor/genvisitor        (Visitor token)
```

---

## Appendix B: Source Code References

| Feature | Repository | File |
|---------|-----------|------|
| Comment posting | saermart/WeiboClient | `weibo/__init__.py` |
| Like/unlike | saermart/WeiboClient | `weibo/__init__.py` |
| Comment fetching (web) | nghuyong/WeiboSpider | `weibospider/spiders/comment.py` |
| Header construction | cv-cat/WeiboApis | `utils/weibo_utils.py` |
| UA rotation | saermart/WeiboClient | `weibo/header.py` |
| Cookie/visitor management | saermart/WeiboClient | `weibo/cookie.py` |
| API URL definitions | saermart/WeiboClient | `weibo/api.py` |
| Web API wrapper | cv-cat/WeiboApis | `apis/weibo_apis.py` |

---

*End of Report*
