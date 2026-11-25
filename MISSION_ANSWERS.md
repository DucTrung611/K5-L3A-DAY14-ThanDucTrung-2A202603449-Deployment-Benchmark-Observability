# MISSION_ANSWERS — Day 14

> Họ tên: Than Duc Trung · MSSV: 2A202603449 · Lớp: K5-L3A

---

## Part 1: Localhost vs Production

### Exercise 1.1 — Anti-pattern trong `01-localhost-vs-production/develop/app.py`

| # | Anti-pattern | Dòng | Vì sao nguy hiểm |
|---|---|---|---|
| 1 | **API key hardcode** `OPENAI_API_KEY = "sk-hardcoded-..."` | 17 | Push lên GitHub là lộ key ngay, và key nằm mãi trong lịch sử commit. |
| 2 | **Connection string có mật khẩu hardcode** `DATABASE_URL = "postgresql://admin:password123@..."` | 18 | Cùng loại lỗi với #1; còn gắn cứng DB `localhost`, không đổi được giữa dev/staging/prod. |
| 3 | **Không quản lý config**: `DEBUG = True`, `MAX_TOKENS = 500` cố định | 21–22 | Muốn đổi phải sửa code và build lại; không tách được config theo môi trường. |
| 4 | **`print()` thay cho logging**, không có level hay cấu trúc | 33, 38 | Không lọc/parse được trong hệ thống gom log (Datadog, Loki…). |
| 5 | **Log ra secret**: `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | 34 | Key lọt vào log, ai đọc được log là lấy được key. Đã thấy thật trong output server (xem 1.2). |
| 6 | **Không có health check** (`/health`, `/ready`) | 42–43 | Platform không biết agent chết hay còn sống để restart; LB không biết lúc nào được route traffic. Thực tế `GET /health` trả **404**. |
| 7 | **Port cố định** `port=8000` | 52 | Railway/Render inject `PORT` qua env; app không đọc nên không nhận được traffic. |
| 8 | **`host="localhost"`** | 51 | Chỉ nhận kết nối từ chính máy đó; trong container thì bên ngoài không vào được (phải là `0.0.0.0`). |
| 9 | **`reload=True`** | 53 | Chế độ debug, theo dõi file thay đổi, không dùng cho production. |
| 10 | **Không xử lý shutdown** (không lifespan, không SIGTERM) | — | Bị tắt đột ngột thì request đang chạy bị cắt ngang. |

### Exercise 1.2 — Chạy bản develop

Gọi đúng cú pháp K5 (`question` truyền qua query, không phải JSON):

```text
$ curl -i -X POST "http://localhost:8001/ask?question=Hello"
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Gửi JSON như trong `CODE_LAB.md` thì bị **422**, đúng như README K5 cảnh báo:

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 422 Unprocessable Entity

{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

**Quan sát — nó chạy, nhưng chưa production-ready.** Log của server phơi bày ngay hai lỗi đã nêu ở 1.1:

```text
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this      <-- secret nằm trong log
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. ...
```

```text
$ curl -s -o /dev/null -w '%{http_code}' http://localhost:8001/health
404                                                          <-- không có health check
```

> **Ghi chú môi trường (Windows):** lần chạy đầu `POST /ask?question=Hello` trả **500**. Nguyên nhân không phải lỗi của bài: `print()` ghi tiếng Việt ra console Windows (mã hoá cp1252) nên phát sinh `UnicodeEncodeError: 'charmap' codec can't encode character 'đ'`. Đặt `PYTHONUTF8=1` thì hết lỗi (hoặc chạy trong WSL2). Chính việc dùng `print()` thay vì logging cũng góp phần làm lỗi này xảy ra.

### Exercise 1.3 — So sánh develop và production

Chạy bản production (`PORT=8002 python app.py`):

```text
GET  /health  -> {"status":"ok","uptime_seconds":3.7,"version":"1.0.0","environment":"development","timestamp":"..."}
GET  /ready   -> {"ready":true}                      [200]
POST /ask  {"question":"Hello"} -> {"question":"Hello","answer":"...","model":"gpt-4o-mini"}   [200]
POST /ask  {}                   -> {"detail":"question field is required"}                    [422]
```

| Feature | Basic (`develop`) | Advanced (`production`) | Tại sao quan trọng? |
|---|---|---|---|
| **Config** | Hardcode trong code (`app.py:17-22`) | Đọc từ env qua `config.py` (`Settings`, `os.getenv`) | Cùng một image chạy được ở dev/staging/prod chỉ bằng đổi env; secret không nằm trong repo (12-Factor III). |
| **Secrets** | Key + mật khẩu DB trong code, còn in ra log | `OPENAI_API_KEY`, `AGENT_API_KEY` từ env; log không in secret (`app.py:110`) | Tránh lộ key khi push GitHub hoặc đọc log. |
| **Health check** | Không có (`/health` → 404) | `GET /health` (liveness) và `GET /ready` (readiness, 503 khi chưa sẵn sàng) | Platform restart container chết; load balancer chỉ gửi traffic vào instance đã sẵn sàng. |
| **Logging** | `print()` | `logging` + `json.dumps({...})` theo `event` (`app.py:111`) | Log có cấu trúc, máy parse được; không lẫn secret. |
| **Shutdown** | Đột ngột, không lifespan | `lifespan` + handler SIGTERM (`app.py:39-67`, `180-189`) | Hoàn thành request đang chạy, đóng kết nối rồi mới thoát. |
| **Host / Port** | `localhost:8000` cố định, `reload=True` | `0.0.0.0` và `PORT` từ env, `reload` chỉ khi `DEBUG=true` (`app.py:194-198`) | Container nhận được kết nối ngoài; Railway/Render inject `PORT`. |
| **Validation** | Không | `validate()` fail fast: thiếu `AGENT_API_KEY` ở production thì raise (`config.py:37-46`) | Thà lỗi lúc khởi động còn hơn chạy sai cấu hình. |

> **Quan sát thêm khi chạy thật:** bản production khai báo log dạng JSON (`format='{"time":...}'`, `app.py:28-32`), nhưng trong output server **không thấy dòng JSON nào** của app (không có `startup`, `agent_request`…). Lý do: `config.py` gọi `logging.warning(...)` lúc import (`settings.validate()`), việc này tự cấu hình root logger với mặc định, nên `logging.basicConfig(...)` ở `app.py` chạy sau bị bỏ qua (cả format lẫn level INFO). Bài học: cấu hình logging phải làm **một lần, trước mọi thứ khác**; đây cũng là lý do Part 6 yêu cầu tự viết formatter và kiểm tra bằng script.

### Checkpoint 1 — tự kiểm tra

- **Hardcode secret nguy hiểm vì:** repo public hoặc lịch sử commit là lộ key vĩnh viễn (xoá file không đủ, phải thu hồi key), và key còn bị in ra log.
- **Một anti-pattern ở `develop/app.py` mà `production/app.py` đã sửa:**
  - develop `app.py:17` — `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"`
  - production `config.py:27` — `openai_api_key: str = field(default_factory=lambda: os.getenv("OPENAI_API_KEY", ""))`
- **Health check:** `/health` cho biết process còn sống (platform restart nếu không); `/ready` cho biết đã sẵn sàng nhận traffic (LB loại instance chưa sẵn sàng).
- **Graceful shutdown:** khi nhận SIGTERM, ngừng nhận request mới, xử lý xong request đang chạy rồi mới thoát; không bị cắt ngang.

---

## Part 2: Docker

> Build từ **gốc repo** (Dockerfile `COPY` theo đường dẫn tính từ gốc). Cổng 8000 trên máy đang bị server của Part 1 chiếm nên khi chạy container develop tôi map `-p 8010:8000`; kết quả không đổi.

### Exercise 2.1 — Đọc `02-docker/develop/Dockerfile`

1. **Base image:** `python:3.11` (dòng 8), bản Python đầy đủ, nặng (~1 GB).
2. **Working directory:** `/app` (`WORKDIR /app`, dòng 11).
3. **Vì sao `COPY requirements.txt` trước:** Docker cache theo từng layer. Dependencies ít đổi còn code đổi liên tục. Copy `requirements.txt` và `pip install` trước thì layer cài thư viện được cache, sửa code chỉ build lại từ layer `COPY app.py` trở xuống. Nếu `COPY . .` trước thì mỗi lần sửa 1 dòng code là cài lại toàn bộ thư viện.
4. **CMD vs ENTRYPOINT:**
   - `CMD` là lệnh/đối số **mặc định**, bị ghi đè dễ dàng khi `docker run <image> <lệnh khác>`.
   - `ENTRYPOINT` là chương trình **cố định** của container; đối số của `docker run` được nối vào sau nó, muốn thay phải dùng `--entrypoint`.
   - Thường dùng `ENTRYPOINT` cho chương trình chính và `CMD` cho đối số mặc định. Bài này chỉ dùng `CMD ["python", "app.py"]` (exec form, nên `python` là PID 1 và nhận được SIGTERM).

### Exercise 2.2 — Build và chạy bản develop

```text
$ docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
$ docker run -d --name k5-dev -p 8010:8000 my-agent:develop
$ curl -i -X POST "http://localhost:8010/ask?question=What%20is%20Docker%3F"
HTTP/1.1 200 OK
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Log trong container: `Uvicorn running on http://0.0.0.0:8000` và `POST /ask?question=... 200 OK`. Bản container này nhận `question` qua **query** như bản develop ở Part 1.

### Exercise 2.3 — Multi-stage build

```text
$ docker build -f 02-docker/production/Dockerfile -t my-agent:advanced .
$ docker images
REPOSITORY:TAG        SIZE
my-agent:advanced     163MB
my-agent:develop      1.15GB
```

Số byte đo bằng `docker image inspect`:

| Image | Bytes | Kích thước |
|---|---:|---:|
| `my-agent:develop` (single-stage, `python:3.11`) | 1 154 311 927 | **≈ 1 154 MB** |
| `my-agent:advanced` (multi-stage, `python:3.11-slim`) | 162 882 434 | **≈ 163 MB** |

**Giảm 85,9 %** (nhỏ hơn khoảng **7,1 lần**), và dưới ngưỡng 500 MB mà Part 6 yêu cầu.

- **Stage 1 (builder):** `python:3.11-slim` + `gcc`, `libpq-dev` để biên dịch, rồi `pip install --user` vào `/root/.local`. Stage này **không dùng để deploy**.
- **Stage 2 (runtime):** `python:3.11-slim` sạch; chỉ `COPY --from=builder /root/.local` (kết quả đã cài), code và `utils/`. Tạo user `appuser` **non-root**, có `HEALTHCHECK`, chạy `uvicorn --workers 2`.
- **Vì sao nhỏ hơn:**
  1. Base `-slim` thay vì bản đầy đủ (phần lớn chênh lệch nằm ở đây).
  2. `gcc`, `libpq-dev`, cache `apt`, build tools nằm ở stage builder và **bị bỏ lại**, không vào image cuối.
  3. `--no-cache-dir` không giữ cache pip.
- **Lưu ý:** `COPY` `.local` vào `/home/appuser/.local` và đặt `PATH` để non-root tìm thấy package. Đây chính là chỗ Part 6 dễ lỗi nếu quên `PYTHONUSERBASE`.

### Exercise 2.4 — Docker Compose stack

```text
$ touch 02-docker/production/.env.local        # file rỗng, đã nằm trong .gitignore
$ docker compose -p k5-day14-docker up -d --build

SERVICE   IMAGE                   STATUS                  PORTS
agent     k5-day14-docker-agent   Up (health: starting)   8000/tcp                       <- không publish ra host
nginx     nginx:alpine            Up                      0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
qdrant    qdrant/qdrant:v1.9.0    Up (healthy)            6333-6334/tcp
redis     redis:7-alpine          Up (healthy)            6379/tcp
```

**Sơ đồ kiến trúc** (mạng bridge `internal`):

```
                     Internet / curl
                           │  :80, :443
                           ▼
                 ┌───────────────────┐
                 │  nginx (alpine)   │  rate limit 10 r/s/IP (burst 20 → 429)
                 │  reverse proxy/LB │  security headers, ẩn version
                 └─────────┬─────────┘
                           │ http://agent:8000   (upstream agent_backend)
                           ▼
                 ┌───────────────────┐
                 │  agent (FastAPI)  │  uvicorn, 2 workers, non-root
                 └──────┬─────┬──────┘
         REDIS_URL      │     │      QDRANT_URL
   redis://redis:6379   ▼     ▼   http://qdrant:6333
              ┌─────────────┐ ┌──────────────┐
              │ redis:7     │ │ qdrant v1.9  │
              │ cache/state │ │ vector DB    │
              └─────────────┘ └──────────────┘
              volume redis_data   volume qdrant_data
```

- **Services:** `agent`, `redis`, `qdrant`, `nginx`.
- **Giao tiếp:** các service nằm chung network `internal` nên gọi nhau bằng **tên service** qua DNS của Docker (`redis`, `qdrant`, `agent`). Chỉ **nginx** publish cổng ra host; `agent`, `redis`, `qdrant` không mở cổng ra ngoài.
- **Thứ tự khởi động:** `agent` có `depends_on` với `condition: service_healthy` cho `redis` và `qdrant`, nên chỉ chạy khi hai dịch vụ đó healthy; `nginx` `depends_on` agent.
- **Ghi chú:** `main.py` của agent trong stack này **chưa dùng Redis hay Qdrant** (chỉ có biến môi trường `REDIS_URL`, `QDRANT_URL`); hai service chỉ minh hoạ kiến trúc đầy đủ.

Test qua Nginx (cổng 80):

```text
$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":6.7,"version":"2.0.0","timestamp":"2026-11-25T08:41:55.870707"}

$ curl -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

Header bảo mật (`X-Frame-Options`, ...) và `Server: nginx` (không lộ version) chứng tỏ request đi qua Nginx. Log agent có `GET /health 200` và dòng JSON `{"event": "request", "q_len": 21}`. Bản này (`main.py`) nhận **JSON body**, khác bản develop nhận query.

Dọn dẹp: `docker compose -p k5-day14-docker down -v`.

### Checkpoint 2 — tự kiểm tra

- **Multi-stage giảm dung lượng ở đâu:** bỏ toolchain biên dịch (`gcc`, `libpq-dev`, cache apt) ở stage builder, chỉ mang kết quả đã cài sang runtime `-slim`. Số đo của tôi: 1 154 MB → 163 MB (−85,9 %).
- **Vì sao `COPY requirements.txt` đứng trước `COPY . .`:** để layer cài dependencies được cache; chỉ khi `requirements.txt` đổi mới cài lại.
- **Debug container:** `docker logs <tên>`, `docker exec -it <tên> sh`, `docker compose -p <tên> logs agent`, `docker compose -p <tên> ps`.
- Số MB ở trên là số tôi tự đo bằng `docker images` và `docker image inspect` (Docker tính theo đơn vị thập phân).

## Part 3: Cloud Deployment

_(chưa làm)_

## Part 4: API Security

> Chạy trên cổng riêng (8020, 8021) để tránh cổng 8000. Token đã được che; tài khoản dùng là `student` / `demo123` (10 request/phút) theo README K5.

### Exercise 4.1 — API Key authentication (`04-api-gateway/develop/app.py`)

- **Key được check ở đâu?** Trong hàm `verify_api_key` (`app.py:39-54`), đọc header `X-API-Key` bằng `APIKeyHeader(auto_error=False)`, rồi so với `API_KEY` lấy từ env `AGENT_API_KEY` (`app.py:35`). Endpoint `/ask` được bảo vệ nhờ `Depends(verify_api_key)` (`app.py:70`); `/` và `/health` để public.
- **Sai key thì sao?**
  - **Thiếu** header → `401 Unauthorized`.
  - **Sai** key → `403 Forbidden` (không phải 401). Part 6 yêu cầu cả hai trường hợp đều **401**, nên khi tự làm phải gộp lại.
- **Rotate key thế nào?** Key nằm ở biến môi trường, nên đổi giá trị `AGENT_API_KEY` trên nền tảng rồi restart/redeploy; không cần sửa code. Muốn không gián đoạn thì cho phép **nhiều key cùng lúc** trong thời gian chuyển đổi (key cũ + key mới), rồi thu hồi key cũ. Bản mẫu chỉ có một key nên đổi là key cũ chết ngay.
- **Lỗi trong chính bản mẫu:** giá trị mặc định `"demo-key-change-in-production"` (`app.py:35`) và `print(f"API Key: {API_KEY}")` (`app.py:91`) in key ra console; so sánh `!=` không phải so sánh thời gian hằng số (`secrets.compare_digest` an toàn hơn).

Kết quả chạy thật (`AGENT_API_KEY=secret-key-123`):

```text
$ curl -i -X POST $B/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

$ curl -i -X POST $B/ask -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

$ curl -i -X POST $B/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}

$ curl -o /dev/null -w '%{http_code}' $B/health        # public
200
```

### Exercise 4.2 — JWT authentication (`04-api-gateway/production/`)

**Luồng JWT** (`auth.py`):

1. Client gửi `POST /auth/token` với username/password → `authenticate_user` kiểm tra (sai → 401) → `create_token` ký bằng `HS256` với `SECRET_KEY` (lấy từ env `JWT_SECRET`), payload `sub` (user), `role`, `iat`, `exp` (+60 phút) (`auth.py:35-43`).
2. Client gửi token trong header `Authorization: Bearer <token>`.
3. `verify_token` (`auth.py:46-67`) giải mã và kiểm tra chữ ký **mà không cần tra database**: thiếu token → 401, token hết hạn → 401, token giả/sai chữ ký → **403**.
4. Endpoint dùng `username` + `role` trong token để áp rate limit và budget.

```text
$ curl -s -X POST $B/auth/token -H "Content-Type: application/json" -d '{"username":"student","password":"demo123"}'
{"access_token": "eyJhbGciOiJI...<masked>", "token_type": "bearer", "expires_in_minutes": 60, ...}

$ curl -i -X POST $B/auth/token ... -d '{"username":"student","password":"x"}'
HTTP/1.1 401 Unauthorized        {"detail":"Invalid credentials"}

$ curl -i -X POST $B/ask -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'      # không token
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

$ curl -i -X POST $B/ask -H "Authorization: Bearer abc.def.ghi" ...                              # token giả
HTTP/1.1 403 Forbidden           {"detail":"Invalid token."}

$ curl -i -X POST $B/ask -H "Authorization: Bearer <masked>" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
x-content-type-options: nosniff
x-frame-options: DENY
referrer-policy: strict-origin-when-cross-origin
{"question":"Explain JWT","answer":"...","usage":{"requests_remaining":9,"budget_remaining_usd":2.1e-05}}
```

**Quan sát:** code có `del response.headers["server"]` để ẩn thông tin server (`app.py:84-85`) nhưng response vẫn có `server: uvicorn`, vì uvicorn thêm header này **sau** khi middleware chạy. Muốn ẩn thật phải chạy uvicorn với `--no-server-header`.

### Exercise 4.3 — Rate limiting (`rate_limiter.py`)

- **Algorithm:** **sliding window** dạng log: mỗi user có một `deque` các timestamp; mỗi request xoá timestamp cũ hơn 60 giây rồi đếm; nếu đã đủ limit thì từ chối (`rate_limiter.py:35-62`). (Comment trong file ghi "Sliding Window Counter" nhưng thực chất là sliding window *log*, vì lưu từng timestamp.)
- **Limit:** user **10 request/phút**, admin **100 request/phút** (`rate_limiter.py:86-87`).
- **Bypass cho admin:** không bypass hoàn toàn, mà chọn limiter theo role: `limiter = rate_limiter_admin if role == "admin" else rate_limiter_user` (`app.py:141`). Admin (`teacher`) có hạn mức 100/phút.
- **Hạn chế:** state nằm trong **RAM của từng process**. Chạy 2 worker hoặc nhiều instance thì mỗi cái đếm riêng (limit thực tế nhân lên), và restart thì mất sạch. Vì vậy Part 6 yêu cầu lưu trong **Redis**.

Vòng lặp 12 request liên tiếp (request 1 ở bước 4.2 đã dùng 1 lượt):

```text
req  2 -> 200      ...      req 10 -> 200      (10 request đầu đều 200)
req 11 -> 429
req 12 -> 429

$ curl -i ... (request tiếp theo)
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: <unix timestamp>
retry-after: 56
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":56}}
```

Đúng 10 request đầu qua, request thứ 11 bị chặn và có `Retry-After` cho client biết phải chờ bao lâu. Thêm:

```text
$ curl $B/me/usage -H "Authorization: Bearer <masked>"
{"user_id":"student","requests":10,"input_tokens":40,"output_tokens":316,"cost_usd":0.000196,"budget_usd":1.0,"budget_remaining_usd":0.999804,...}
admin (teacher) /ask        -> 200
student gọi /admin/stats    -> 403   (chỉ role admin)
```

### Exercise 4.4 — Cost guard

**Đọc `cost_guard.py`:**
- Mỗi user có `UsageRecord` đếm token theo ngày; giá `$0.00015 / 1K input` và `$0.0006 / 1K output`.
- `check_budget()` chạy **trước** khi gọi LLM: vượt ngân sách **toàn hệ thống** ($10/ngày) → `503`; vượt ngân sách **user** ($1/ngày) → **`402 Payment Required`**; đạt 80% thì chỉ log cảnh báo.
- `record_usage()` chạy **sau** khi gọi LLM để cộng chi phí.
- Hạn chế: state trong RAM (mất khi restart, không chia sẻ giữa instance).

Gọi trực tiếp `CostGuard` với ngân sách nhỏ ($0.0005) để thấy 402 (chạm $1/ngày qua API với mock token là không thực tế):

```text
call 1: OK   cost=$0.000375 / $0.0005
call 2: OK   cost=$0.000750 / $0.0005        <- đã vượt mức nhưng vẫn được qua
call 3: HTTP 402  {'error': 'Daily budget exceeded', 'used_usd': 0.00075, 'budget_usd': 0.0005, 'resets_at': 'midnight UTC'}
```

Quan sát: vì **kiểm tra trước, ghi nhận sau**, request cuối có thể làm vượt ngân sách một lần (call 2) rồi các request sau mới bị chặn. Chấp nhận được với ngân sách mềm; muốn chặn cứng phải **đặt chỗ (reserve)** chi phí ước tính trước khi gọi.

**Cách làm với Redis** (đề bài 4.4, đồng bộ giữa mọi instance, tự reset theo tháng nhờ key chứa tháng):

```python
import redis
from datetime import datetime

r = redis.Redis()

def check_budget(user_id: str, estimated_cost: float) -> bool:
    key = f"budget:{user_id}:{datetime.now().strftime('%Y-%m')}"
    new_total = r.incrbyfloat(key, estimated_cost)      # atomic: cộng rồi đọc kết quả
    if new_total > 10:
        r.incrbyfloat(key, -estimated_cost)             # hoàn lại phần vừa đặt chỗ
        return False
    r.expire(key, 32 * 24 * 3600)                       # tự dọn sau ~32 ngày
    return True
```

So với lời giải gợi ý trong `CODE_LAB.md` (đọc `get` rồi `incrbyfloat` ở hai lệnh tách rời), bản trên dùng `INCRBYFLOAT` làm một bước atomic. Hai request đồng thời không còn cùng thấy "còn budget" rồi cùng vượt. Với Part 6, key nên theo **ngày** (`DAILY_BUDGET_USD`) và trả `HTTPException(402)` thay vì `bool`.

### Checkpoint 3 — tự kiểm tra

- **Rate limit vs cost guard:** rate limit bảo vệ **tốc độ** (chống spam/DoS, chia đều tài nguyên: 11 request/phút → 429); cost guard bảo vệ **tiền** (chặn khi tổng chi phí vượt ngân sách → 402). Cần cả hai vì một user có thể gọi chậm (qua rate limit) nhưng gửi prompt rất dài làm cháy ngân sách, hoặc gọi nhanh nhưng prompt rẻ.
- **401 vs 403:** 401 = chưa xác thực (thiếu/hết hạn credential); 403 = đã xác thực nhưng không có quyền (token giả, role không đủ). Riêng bài Part 6 quy ước key thiếu **hoặc** sai đều là 401.
- **Thấy được 429 bằng vòng lặp curl của chính mình:** có (request 11 và 12 ở trên).
- **Việc cần làm cho Part 6:** chuyển rate limiter và cost guard từ RAM sang **Redis** (sliding window bằng sorted set, `INCRBYFLOAT`), key theo API key.

## Part 5: Scaling & Reliability

> Bản develop của Part 5 đã có sẵn `/health`, `/ready` và graceful shutdown, nên Ex 5.1–5.2 là **đọc + chạy thử + giải thích**, không tự viết lại (theo `CHECKPOINTS.md`). Tôi chạy trên cổng 8030/8031 để không đụng cổng 8000.

### Exercise 5.1 — Health checks (`05-scaling-reliability/develop/app.py`)

```text
$ curl -i http://localhost:8030/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":2.8,"version":"1.0.0","environment":"development","timestamp":"...","checks":{"memory":{"status":"ok","used_percent":56.2}}}

$ curl -i http://localhost:8030/ready
HTTP/1.1 200 OK
{"ready":true,"in_flight_requests":1}
```

| | `/health` (liveness, `app.py:104-144`) | `/ready` (readiness, `app.py:147-168`) |
|---|---|---|
| Câu hỏi | Process còn **sống** không? | Đã **sẵn sàng nhận traffic** chưa? |
| Dựa vào | Bản thân process (ở đây kiểm tra bộ nhớ qua `psutil`) | Cờ `_is_ready` (đặt `True` sau khi khởi động xong, `False` khi shutdown) và các dependency (DB, Redis) |
| Khi lỗi | Trả non-200 → platform **restart container** | Trả **503** → load balancer **ngừng gửi traffic** vào instance này, nhưng không restart |
| Ví dụ | Process treo, deadlock | Đang nạp model, Redis chưa kết nối, đang shutdown |

Vì sao tách đôi: một instance có thể **sống nhưng chưa sẵn sàng** (đang khởi động hoặc mất Redis). Nếu chỉ có một endpoint thì hoặc restart oan một instance khoẻ, hoặc gửi traffic vào instance chưa dùng được. Quy ước Part 6 cũng thế: `/health` luôn 200 kể cả khi Redis chết, còn `/ready` trả 503.

`in_flight_requests: 1` chính là request `/ready` đang xử lý (middleware đếm cả nó).

### Exercise 5.2 — Graceful shutdown

Windows không gửi được SIGTERM cho process Python, nên tôi chạy bản develop trong **container Linux** (`python:3.11-slim`, mount thư mục `develop/`). Request `/ask` mất ~3 giây (mock LLM có delay 3s); tôi gửi **SIGTERM sau 1 giây**, khi request đang xử lý:

```text
SIGTERM lúc 15:59:26.641                       <- docker kill -s TERM
{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
-> request đang chạy kết thúc: HTTP 200 sau 3.05s

Exited (0) 3 seconds ago      ExitCode=0

--- log container ---
INFO:     Shutting down                                           <- nhận SIGTERM, ngừng nhận kết nối mới
INFO:     ... "POST /ask?question=Long%20task HTTP/1.1" 200 OK    <- request đang chạy vẫn hoàn tất
INFO:     Waiting for application shutdown.
... 🔄 Graceful shutdown initiated...                              <- lifespan shutdown (đặt _is_ready=False, chờ in-flight)
... ✅ Shutdown complete
INFO:     Finished server process [1]
... Received signal 15 — uvicorn will handle graceful shutdown
```

**Kết luận:** request đang chạy **không bị cắt** (200 sau đủ 3 giây dù SIGTERM đến lúc 1 giây) và process thoát với **exit code 0**.

Cách hoạt động (`app.py`):
1. **Ngừng nhận request mới:** uvicorn bắt SIGTERM và ngừng accept kết nối.
2. **Hoàn thành request đang chạy:** uvicorn chờ chúng xong (`timeout_graceful_shutdown=30`, `app.py:198`); middleware `track_requests` đếm `_in_flight_requests` (`app.py:72-81`).
3. **Dọn dẹp:** phần sau `yield` trong `lifespan` đặt `_is_ready=False` và chờ tối đa 30 giây cho đến khi hết request đang xử lý (`app.py:54-66`).
4. **Thoát:** exit code 0.

**Quan sát:** dòng `Received signal 15` do `handle_sigterm` tự đăng ký (`app.py:186`) xuất hiện **sau** `Shutdown complete`. Tức là uvicorn dùng handler của nó để tắt rồi mới gọi lại handler cũ. Nó khớp với lưu ý ở Part 6: nếu tự đăng ký handler SIGTERM thì không được chặn đường tắt của uvicorn.

### Exercise 5.3 — Stateless design (`05-scaling-reliability/production/app.py`)

Bản này **đã stateless**: không giữ conversation trong biến toàn cục, mọi session lưu trong Redis:
- `save_session` dùng `SETEX session:<id> 3600 <json>` (TTL 1 giờ); `load_session` đọc lại bằng `GET` (`app.py:59-73`).
- `append_to_history` đọc → thêm message → ghi lại, giữ tối đa 20 message (`app.py:76-90`).
- Mỗi instance mang `INSTANCE_ID` riêng và trả `served_by` để thấy rõ ai phục vụ.

**Vì sao state trong RAM hỏng khi scale:** mỗi instance có bộ nhớ riêng. Request 1 của user A tới instance 1 (lưu history trong RAM instance 1); request 2 tới instance 2 thì **không thấy** history → hội thoại đứt. Đưa state ra Redis dùng chung thì instance nào cũng đọc được; instance chết cũng không mất dữ liệu.

**Điểm yếu còn lại trong code mẫu** (đọc code, tôi chưa chạy thử riêng phần này):
- Có **fallback sang dict trong RAM** nếu Redis không có (`app.py:42-45`). Nó làm app vẫn chạy nhưng **âm thầm mất tính stateless**; sau scale ra nhiều instance sẽ lỗi khó thấy. Ở production nên fail rõ ràng (cho `/ready` trả 503) thay vì fallback.
- `append_to_history` là **đọc → sửa → ghi** không nguyên tử: hai request đồng thời cùng session có thể ghi đè nhau. Dùng `RPUSH`/`LTRIM` của Redis (list) sẽ nguyên tử.

### Exercise 5.4 — Load balancing (Nginx + 3 instance)

```text
$ touch .env.local        # file rỗng, đã trong .gitignore
$ docker compose -p k5-day14-scaling up -d --build --scale agent=3

NAME                       STATUS                PORTS
k5-day14-scaling-agent-1   Up (healthy)          8000/tcp
k5-day14-scaling-agent-2   Up (healthy)          8000/tcp
k5-day14-scaling-agent-3   Up (healthy)          8000/tcp
k5-day14-scaling-nginx-1   Up                    0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   Up (healthy)          6379/tcp
```

10 request riêng lẻ qua `http://localhost:8080/chat`, đếm theo header `X-Served-By` (địa chỉ container phục vụ):

```text
      3 172.19.0.3:8000
      4 172.19.0.4:8000
      3 172.19.0.5:8000
```

Nginx chia **gần đều** giữa 3 instance (round-robin: 3/4/3). Cổng ra ngoài chỉ có Nginx (`8080`); các agent không publish cổng.

**Dừng một instance (chết giữa chừng):** `docker stop k5-day14-scaling-agent-1`, rồi gửi 8 request cùng một session:

```text
      4 instance-452777  storage= redis
      4 instance-bb714d  storage= redis       <- chỉ còn 2 instance phục vụ, không request nào lỗi
```

Cấu hình `proxy_next_upstream error timeout http_503` (`nginx.conf:23-24`) cho Nginx thử instance khác khi một instance lỗi. Tôi không kiểm chứng riêng cơ chế retry; kết quả đo được là cả 8 request đều thành công.

> **Lưu ý khi scale thêm:** `upstream` dùng `server agent:8000`, Nginx phân giải tên **một lần lúc khởi động** (khối `resolver` không tác dụng với `upstream` tĩnh). Instance thêm sau đó có thể không được dùng cho đến khi Nginx reload. Đây là suy luận từ cấu hình, tôi chưa thử scale thêm khi đang chạy. Stack Part 7 giải quyết chuyện này bằng `server agent:8000 resolve` (theo README).

### Exercise 5.5 — Test stateless

```text
$ python test_stateless.py
Session ID: 0ef62cb7-b3de-425a-a734-6f2f40589586

Request 1: [instance-452777]   What is Docker?
Request 2: [instance-bb714d]   Why do we need containers?
Request 3: [instance-bc4d54]   What is Kubernetes?
Request 4: [instance-452777]   How does load balancing work?
Request 5: [instance-bb714d]   What is Redis used for?

Total requests: 5
Instances used: {'instance-bb714d', 'instance-bc4d54', 'instance-452777'}
✅ All requests served despite different instances!

--- Conversation History ---
Total messages: 10          <- 5 câu hỏi x (user + assistant)
✅ Session history preserved across all instances via Redis!
```

**Giải thích:** 5 request trong cùng một session được **3 instance khác nhau** phục vụ (round-robin), nhưng `GET /chat/<session>/history` trả đủ **10 message** (5 user + 5 assistant) theo đúng thứ tự. Lý do: không instance nào giữ history trong RAM; tất cả đọc/ghi cùng một khoá `session:<id>` trong Redis.

Kiểm tra trực tiếp trong Redis: key `session:<id>` có kiểu `string` (JSON), TTL còn **3599 giây** (đặt 3600 giây bằng `SETEX`). Trong lần dừng instance, history của session tăng lên **18 message** (1 + 8 lượt, mỗi lượt gồm user và assistant) và không mất, dù một instance đã chết giữa chừng.

> Script K5 chỉ gửi 5 câu rồi đọc history, **không tự tắt instance nào** (khác mô tả trong `CODE_LAB.md`). Phần tắt instance ở trên là tôi làm riêng.

Dọn dẹp: `docker compose -p k5-day14-scaling down -v`.

### Checkpoint 4 — tự kiểm tra

- **Liveness vs readiness:** `/health` trả lời "process còn sống không" (sai thì **restart**); `/ready` trả lời "nhận traffic được chưa" (sai thì **bỏ khỏi load balancer**, không restart).
- **Vì sao state trong RAM hỏng khi nhiều instance:** mỗi instance có RAM riêng, request kế tiếp có thể rơi vào instance khác và không thấy state; đưa state vào Redis để mọi instance dùng chung.
- **Graceful shutdown:** nhận SIGTERM → ngừng nhận request mới → xong request đang chạy → thoát exit code 0. Đã chứng minh bằng số liệu: request 3 giây vẫn trả 200 dù SIGTERM đến ở giây thứ 1.
- **Stateless chạy được:** 5 request / 3 instance khác nhau / 10 message còn nguyên.

## Part 6: Output `check_production_ready.py`

### Kết quả chấm (bản đầy đủ, có Docker, chạy trên Linux)

```text
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Số đo chi tiết từ script: image **183 MB** (build 50 giây), `docker stop` thoát **exit code 0 trong 1,1 giây**, 429 xuất hiện sau đúng 5 request thành công (`RATE_LIMIT_PER_MINUTE=5`), restart agent vẫn bị 429 (state nằm trong Redis), 402 ở request đầu tiên khi budget ≈ 0, 16 dòng log đều là JSON hợp lệ.

> **Cách chạy:** máy Windows này chưa có distro WSL Linux (chỉ có `docker-desktop`), mà trên Windows script đánh dấu *Graceful shutdown* là ⚠️ (không gửi được SIGTERM). Vì vậy kết quả trên là chạy **đúng script gốc, không sửa**, trong một container Linux (`python:3.11-slim`, `os.name == posix`) dùng Docker của máy qua socket. Chạy riêng trên Windows cho kết quả 11/12 (mục ⚠️ duy nhất là Graceful shutdown). **TODO trước khi nộp:** chạy lại trong WSL2 thật (cài Ubuntu) và dán output đó thay cho khối trên.

### Những quyết định thiết kế chính

| Việc | Cách làm | Lý do |
|---|---|---|
| `/health` vs `/ready` | `/health` luôn 200, không đụng Redis; `/ready` ping Redis, lỗi thì 503 (`main.py`) | Mất Redis không nên làm platform restart agent (restart không sửa được Redis); nhưng LB phải ngừng gửi traffic vào instance không dùng được. |
| Redis client | `redis.from_url(...)` tạo lười, không ping lúc import (`redis_client.py`) | Container phải khởi động được khi chưa có Redis. |
| API key | `APIKeyHeader(auto_error=False)` + `secrets.compare_digest`; thiếu/sai/chưa cấu hình → 401 (`auth.py`) | `Header(...)` bắt buộc sẽ ra 422; so sánh hằng số tránh lộ key qua timing; chưa cấu hình key thì từ chối hết (fail closed). |
| Rate limit | Sorted set `ratelimit:<băm key>`: `ZREMRANGEBYSCORE` → `ZADD` → `ZCARD` → `EXPIRE` trong một giao dịch MULTI/EXEC; vượt thì `ZREM` lại request đó và trả 429 kèm `Retry-After` tính từ request cũ nhất (`rate_limiter.py`) | Thêm rồi mới đếm trong một giao dịch nên 2 worker không cùng vượt giới hạn; request bị từ chối không chiếm chỗ; không lưu API key thật trong Redis. |
| Cost guard | Key `cost:<YYYY-MM-DD UTC>`, `INCRBYFLOAT` nguyên tử, TTL 2 ngày; `check_budget` trước, `record_cost` sau; ≥ `DAILY_BUDGET_USD` → 402 (`cost_guard.py`) | Reset theo ngày nhờ key chứa ngày; nhiều worker cộng đồng thời không mất số. Chấp nhận request cuối có thể vượt ngân sách một chút (đã nêu ở Part 4). |
| Lỗi Redis khi gọi `/ask` | Handler toàn cục `RedisError` → 503 `"Service temporarily unavailable (Redis)."` (`main.py`) | Không lộ stack trace; fail closed thay vì bỏ qua rate limit/cost guard. |
| Validation | Pydantic: `question` 1–2000 ký tự, không toàn khoảng trắng; handler gom lỗi thành `{"detail","errors":[{field,message}]}` → 422 | Lỗi rõ ràng, không lộ nội dung request lẫn stack trace. Lỗi không lường trước → 500 `"Internal server error"`, chi tiết chỉ ghi vào log. |
| Logging | `JsonFormatter` + logger `agent` cấu hình **một lần ở dòng đầu `main.py`**, `propagate=False` (`logging_config.py`) | Rút kinh nghiệm Part 1: có code khác gọi `logging` trước thì `basicConfig` bị bỏ qua. `ensure_ascii` mặc định để không lỗi trên console cp1252. Không log nội dung câu hỏi, chỉ log độ dài. |
| Graceful shutdown | Dùng `lifespan` của FastAPI; **không** tự đăng ký handler SIGTERM (`main.py`) | uvicorn tự ngừng nhận kết nối, chờ request đang chạy, rồi thoát; tự đăng ký handler dễ chặn đường tắt này. |
| Dockerfile | 2 stage; builder tạo virtualenv `/opt/venv`, runtime copy venv + code; user `app` non-root; `HEALTHCHECK`; `CMD ["sh","-c","exec uvicorn ... --port ${PORT:-8000} --workers 2"]` | Virtualenv tránh bẫy `PYTHONUSERBASE` của `pip install --user`; `exec` để uvicorn là PID 1 và nhận SIGTERM. |
| Compose | Nội suy `${AGENT_API_KEY:-}`... từ file `.env` thay vì `env_file: required: false` | Máy này dùng Compose v2.23; `required: false` chỉ có từ v2.24. Cách nội suy chạy trên mọi phiên bản và không lỗi khi thiếu `.env`. |

### Kiểm tra thủ công (ngoài script chấm)

`docker compose up --build` với `HOST_PORT=8100` (key đặt qua biến môi trường, không ghi vào file):

```text
/health -> {"status":"ok","environment":"development","uptime_seconds":1.7}
/ready  -> {"ready":true}
POST /ask thiếu key -> 401     sai key -> 401
POST /ask đúng key  -> 200 {"question":"What is deployment?","answer":"Deployment là quá trình ...","cost_usd":2.01e-05}

Input sai (đều 422, không stack trace):
  {}                  -> {"detail":"Invalid request body","errors":[{"field":"question","message":"Field required"}]}
  {"question":""}     -> ... "String should have at least 1 character"
  {"question":"   "}  -> ... "Value error, question must not be blank"
  not json            -> ... "JSON decode error"
  question 2001 ký tự -> ... "String should have at most 2000 characters"

Rate limit = 6/phút:  200 200 200 200 200 429 429   (cộng 1 request 200 trước đó = 6 request qua)
  HTTP/1.1 429 Too Many Requests
  retry-after: 57
  {"detail":"Rate limit exceeded: 6 requests per 60s. Retry in 57s."}

Dừng Redis:
  /health -> 200
  /ready  -> 503 {"detail":"Redis is not reachable"}
  /ask    -> 503 {"detail":"Service temporarily unavailable (Redis)."}
```

**Hạn chế đã biết:**
- Khi container Redis bị dừng, `/ready` và `/ask` mất **~8 giây** mới trả 503 (log ghi `ms: 8007`). Phần chờ nằm ở bước phân giải DNS của tên `redis` thất bại, nằm ngoài `socket_connect_timeout=2`. Khi Redis từ chối kết nối (như script chấm kiểm tra) thì trả ngay. Chưa xử lý vì không ảnh hưởng tiêu chí.
- Thời gian dùng cho rate limit lấy từ `time.time()` của từng instance; nhiều instance lệch đồng hồ thì cửa sổ 60 giây lệch theo. Dùng `TIME` của Redis sẽ chính xác hơn.
- `render.yaml` **chưa kiểm chứng** trên Render thật (loại `keyvalue`, `rootDir`...); sẽ kiểm tra ở CP6 nếu chọn Render. `railway.toml` cũng mới qua kiểm tra tĩnh của script, chưa deploy.

## AI log

- Dùng Claude Code để đọc mã nguồn, chạy bản develop/production của Part 1 và soạn nháp mục Part 1. Các output curl và log ở trên là kết quả chạy thật trên máy.
