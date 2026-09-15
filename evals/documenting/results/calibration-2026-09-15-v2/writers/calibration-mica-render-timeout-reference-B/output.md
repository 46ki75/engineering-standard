# Mica Export Gateway 2.6 rendering reference

Mica renders one PDF synchronously from a stored template and record. Application developers can set a request-level rendering deadline within the ceiling configured by service operators. Callers should handle binary PDF success bodies separately from JSON error responses.

## Endpoint and authentication

Send `POST /v2/render` with these headers:

```http
Content-Type: application/json
Authorization: Bearer <token>
```

The token requires the `render:write` scope. The JSON body must contain exactly two required string fields, `template_id` and `record_id`:

```json
{"template_id":"invoice-v4","record_id":"inv_2048"}
```

Success returns HTTP 200 with `Content-Type: application/pdf` and the PDF bytes as the body. Documented validation and timeout errors return JSON objects containing a single `error` string.

## Service configuration and limits

The optional integer settings reside in `/etc/mica/gateway.yaml`.

| Setting | Default | Inclusive range | Purpose |
| --- | --- | --- | --- |
| `render_timeout_ms` | 15000 milliseconds | 1000–60000 milliseconds | Default rendering deadline and maximum request-level deadline |
| `max_input_bytes` | 262144 bytes | 1024–1048576 bytes | Maximum UTF-8 request body size before JSON parsing |

This configuration explicitly selects the defaults:

```yaml
render_timeout_ms: 15000
max_input_bytes: 262144
```

The body-size limit measures UTF-8 bytes, not characters or the generated PDF. An oversized body returns HTTP 413 with `{"error":"input_too_large"}`.

The settings are independent: changing either setting does not alter the other setting’s limits.

## Request-level timeout

The optional `X-Mica-Timeout-Ms` header accepts a whole decimal integer in milliseconds. HTTP header names are case-insensitive.

- If the header is absent, the effective timeout is the configured `render_timeout_ms`.
- If supplied, the value must be at least 1000 and no greater than the configured `render_timeout_ms`.

A request can shorten the configured deadline but cannot extend it. With `render_timeout_ms: 15000`:

| Header | Result |
| --- | --- |
| Omitted | Uses a 15000-millisecond deadline |
| `X-Mica-Timeout-Ms: 8000` | Uses an eight-second deadline |
| `X-Mica-Timeout-Ms: 45000` | Returns HTTP 400 with `{"error":"timeout_exceeds_limit"}`; does not permit 45 seconds of rendering |

## Deadline and error behavior

The rendering clock starts only after authentication and body validation and ends when the PDF is ready. Network upload and response transfer time are excluded, so a client-side network timeout measures a different interval.

| Condition | HTTP status | JSON response |
| --- | --- | --- |
| Request body exceeds `max_input_bytes` | 413 | `{"error":"input_too_large"}` |
| Timeout header is noninteger or outside the global 1000–60000 range | 400 | `{"error":"invalid_timeout"}` |
| Timeout header is within the global range but above the configured `render_timeout_ms` | 400 | `{"error":"timeout_exceeds_limit"}` |
| Rendering exceeds the effective deadline | 504 | `{"error":"render_timeout"}` |

Exceeding the effective deadline stops the renderer. The timeout response does not contain a partial PDF. Check the HTTP status before deciding whether to parse JSON or consume PDF bytes.

## Reloading configuration

After editing the file, run:

```sh
micactl reload --file /etc/mica/gateway.yaml
```

The command validates the entire configuration file:

- A successful reload exits zero and applies the new settings to requests admitted after reload completion.
- An invalid file produces a nonzero exit and retains the previous settings.

**Timeout behavior for requests already rendering during a hot reload is undocumented.** The specification establishes neither whether those requests retain their admission-time timeout nor whether they adopt a changed `render_timeout_ms`.

When predictable timing matters, drain active renders before reloading a changed timeout. This operating practice avoids the unresolved case; it is not evidence of how in-flight requests otherwise behave.