# APIs & HTTP — Supplement

> Added by Megamind. This is not from your original notes. Reference tables for status codes and method properties, how API authentication actually works, CORS, and the OWASP API Security Top 10.

## HTTP status codes

| Code | Name | When you see it |
|---|---|---|
| 200 | OK | Successful GET/PUT/PATCH |
| 201 | Created | Successful POST that created a resource (often with a `Location` header) |
| 204 | No Content | Success with no body (common for DELETE) |
| 301 / 308 | Moved Permanently | URL changed for good (308 keeps the method) |
| 302 / 307 | Found / Temporary Redirect | Temporary move (307 keeps the method) |
| 304 | Not Modified | Cached copy is still valid (ETag / If-None-Match) |
| 400 | Bad Request | Malformed input, validation failed |
| 401 | Unauthorized | Not authenticated: missing or invalid credentials |
| 403 | Forbidden | Authenticated but not allowed |
| 404 | Not Found | Resource does not exist (also used to hide resources) |
| 405 | Method Not Allowed | e.g. DELETE on a read-only endpoint |
| 409 | Conflict | State conflict (duplicate, version mismatch) |
| 415 | Unsupported Media Type | Wrong `Content-Type` |
| 422 | Unprocessable Content | Well-formed but semantically invalid |
| 429 | Too Many Requests | Rate limit hit (check `Retry-After`) |
| 500 | Internal Server Error | Unhandled server bug |
| 502 | Bad Gateway | Proxy got a bad response upstream |
| 503 | Service Unavailable | Overloaded / maintenance |
| 504 | Gateway Timeout | Upstream took too long |

Pentest tip: a 403 vs 404 difference on the same path can reveal that a hidden resource exists.

## Safe and idempotent methods

| Method | Safe (no state change) | Idempotent (repeat = same result) | Typical use |
|---|---|---|---|
| GET | Yes | Yes | Read |
| HEAD | Yes | Yes | Headers only |
| OPTIONS | Yes | Yes | Capabilities / CORS preflight |
| PUT | No | Yes | Replace a whole resource |
| DELETE | No | Yes | Remove |
| PATCH | No | Not guaranteed | Partial update |
| POST | No | No | Create / trigger an action |

Idempotency matters for retries: a client can safely retry PUT/DELETE after a timeout, but retrying POST may create duplicates (APIs solve this with an `Idempotency-Key` header).

## API authentication methods

- **API key** — a static secret sent in a header (`X-API-Key: ...`). Identifies the *application*, not a user. Easy to leak; rotate and scope them.
- **Basic auth** — `Authorization: Basic base64(user:pass)`. Base64 is encoding, not encryption, so it is only acceptable over HTTPS.
- **Bearer token / JWT** — `Authorization: Bearer <token>`. A JWT is `header.payload.signature` (each part Base64URL-encoded). The server verifies the signature and expiry (`exp`) without a session lookup. Common JWT attacks: `alg: none` accepted, weak HMAC secret brute-forced, RS256→HS256 algorithm confusion, missing expiry checks, sensitive data in the (readable) payload.
- **OAuth 2.0** — delegated authorization: a user lets an app act on their behalf without sharing their password. Roles: resource owner, client, authorization server, resource server. Main flows:
  - *Authorization Code + PKCE* — web, mobile and SPA apps (the recommended default).
  - *Client Credentials* — machine-to-machine, no user.
  - *Implicit* and *Password* grants — deprecated.
- **OpenID Connect (OIDC)** — an identity layer on top of OAuth 2.0 that adds an **ID token** (a JWT describing who the user is). OAuth = authorization, OIDC = authentication.

## REST design principles

- Resources are nouns, methods are verbs: `GET /users/42`, not `GET /getUser?id=42`.
- Stateless: every request carries everything needed (token, parameters).
- Use plural collections and nesting for relationships: `/users/42/orders`.
- Filter, sort and paginate with query parameters: `/orders?status=paid&sort=-date&page=2&limit=20`.
- Version the API: `/v1/...` or a header.
- Return proper status codes and a consistent error body.

**REST vs GraphQL vs gRPC:** REST uses many endpoints and HTTP semantics, and is easy to cache. GraphQL has one endpoint where the client picks exact fields (no over/under-fetching); watch for introspection leaks and deeply nested query DoS. gRPC uses Protocol Buffers over HTTP/2: fast and strongly typed, mostly service-to-service.

## CORS (Cross-Origin Resource Sharing)

Browsers enforce the **Same-Origin Policy**: JavaScript from `https://a.com` cannot read responses from `https://b.com` unless b.com allows it with headers such as:

```http
Access-Control-Allow-Origin: https://a.com
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST
```

"Non-simple" requests (custom headers, PUT/DELETE, JSON content type) trigger a **preflight** `OPTIONS` request first.

Misconfigurations to test: reflecting any `Origin` back together with `Allow-Credentials: true`, trusting `null` origin, weak regex (`evil-a.com` matching `a.com`). CORS is not a server-side access control: it only controls what browsers let scripts read.

## OWASP API Security Top 10 (2023)

| # | Risk | One-line idea |
|---|---|---|
| API1 | Broken Object Level Authorization (BOLA/IDOR) | Change `/orders/1001` to `/orders/1002` and read someone else's data |
| API2 | Broken Authentication | Weak login, token or reset flows |
| API3 | Broken Object Property Level Authorization | Mass assignment (`"isAdmin": true`) or excessive data exposure |
| API4 | Unrestricted Resource Consumption | No rate/size limits, so DoS or cost explosion |
| API5 | Broken Function Level Authorization | A normal user can call admin endpoints |
| API6 | Unrestricted Access to Sensitive Business Flows | Automating purchases, sign-ups or votes at scale |
| API7 | Server-Side Request Forgery | API fetches attacker-supplied URLs |
| API8 | Security Misconfiguration | Verbose errors, open CORS, missing hardening |
| API9 | Improper Inventory Management | Forgotten old versions (`/v1`) and debug endpoints |
| API10 | Unsafe Consumption of APIs | Blindly trusting third-party API responses |
