# PLAN — Day 14: Deployment, Benchmark & Observability

> Kế hoạch cá nhân, bám theo [CHECKPOINTS.md](CHECKPOINTS.md), [RUBRIC.md](RUBRIC.md), [SUBMISSION.md](SUBMISSION.md).
> Tổng thô 120 điểm, đạt khi quy ra ≥ 70/100 (tương đương 84/120). **Part 6 = 60 điểm, ưu tiên số 1.**

## 0. Quy tắc làm việc

- [ ] Chạy Python trong **WSL2** (`python -c "import os; print(os.name)"` phải in `posix`). Nếu không, graceful shutdown luôn ⚠️ và không bao giờ `PASS 12/12`.
- [ ] Kẹt quá 10 phút ở một mốc: ghi lỗi lại, đi tiếp mốc sau. Không để CP1–CP4 lấn giờ CP5.
- [ ] **Không commit `.env`, API key, token** (−10 điểm, kể cả trong lịch sử commit). Chỉ commit `.env.example`.
- [ ] **Không sửa `check_production_ready.py`** (Part 6 bị 0 điểm).
- [ ] Mọi số liệu trong `BENCHMARK_REPORT.md` phải khớp file JSON/CSV đã nộp, nếu không mục Part 7 đó bị 0.
- [ ] Số MB, output curl, thời gian alert: đều là số tự đo, không chép từ README.
- [ ] Nếu dùng AI: ghi vào mục **AI log** trong `MISSION_ANSWERS.md` (xem [RULES.md](RULES.md)).
- [ ] Che token/API key trước khi dán output hoặc chụp ảnh.

## 1. Bản đồ điểm

| Hạng mục | Điểm | Checkpoint | Bằng chứng |
|---|---:|---|---|
| Part 1 | 8 | CP1 | `MISSION_ANSWERS.md` |
| Part 2 | 8 | CP2 | `MISSION_ANSWERS.md` (số MB đo được) |
| Part 3 | 8 | CP6 | URL public + so sánh railway/render + Cloud Run |
| Part 4 | 8 | CP3 | output 401 / 200 / 429 |
| Part 5 | 8 | CP4 | `MISSION_ANSWERS.md` |
| **Part 6** | **60** | CP5, CP6 | `PASS 12/12`, `DEPLOYMENT.md`, ảnh |
| Part 7 load test & SLO | 4 | CP7 | bảng 4 mức concurrency + so sánh `MOCK_SLOW_RATE` |
| Part 7 eval & quality gate | 5 | CP7 | v1 vs v2, đạt 23/23, không regression |
| Part 7 observability stack | 4 | CP8 | ảnh Grafana có tải |
| Part 7 tracing | 3 | CP8 | ảnh trace chậm, `trace_id` khớp log |
| Part 7 alerts & chaos | 4 | CP8 | ảnh ≥ 2 alert firing, thời gian |

## 2. Lịch tổng thể

| Giờ | CP | Việc | Thời gian |
|---|---|---|---:|
| 0:00 | CP0 | Setup | 10' |
| 0:10 | CP1 | Part 1 | 20' |
| 0:30 | CP2 | Part 2 | 30' |
| 1:00 | CP3 | Part 4 | 25' |
| 1:25 | CP4 | Part 5 | 20' |
| 1:50 | CP5 | **Part 6 → PASS 12/12** | 60' |
| 2:50 | CP6 | Deploy cloud (Part 3) | 25' |
| 3:15 | CP7 | Part 7 Bước 1 | 45' |
| Sau lab | CP8 | Part 7 Bước 2 + đóng gói | trước deadline |

---

## CP0 — Setup (10')

- [ ] Repo đã đổi tên đúng mẫu `K5-L3A-DAY14-HoVaTen-MSSV-Deployment-Benchmark-Observability`, để **Public**.
- [ ] `python --version` ≥ 3.11, `docker compose version`, `docker run --rm hello-world` chạy được.
- [ ] Đọc mục *Lưu ý khi làm bài* trong [README.md](README.md) (11 điểm khác biệt K5).
- [ ] Tạo sẵn `MISSION_ANSWERS.md` với các mục: Part 1–5, output script chấm, AI log.
- [ ] Tạo thư mục `screenshots/`.

## CP1 — Part 1: Localhost vs Production (20')

Thư mục: `01-localhost-vs-production/`

- [ ] Ex 1.1: đọc `develop/app.py`, liệt kê **≥ 5 anti-pattern** kèm số dòng (hardcode key, port cố định, debug, không health check, không shutdown…).
- [ ] Ex 1.2: chạy bản develop, gọi bằng query: `curl -X POST "http://localhost:8000/ask?question=Hello"` (không dùng JSON, sẽ bị 422). Ghi kết quả.
- [ ] Ex 1.3: chạy bản production (`cp .env.example .env`), điền bảng so sánh Config / Health check / Logging / Shutdown kèm cột "Tại sao quan trọng".
- [ ] Tắt server cũ trước khi bật bản khác (cùng cổng 8000).
- [ ] **Tự kiểm tra:** chỉ ra 1 anti-pattern ở `develop/app.py` mà `production/app.py` đã sửa, kèm dòng code.

## CP2 — Part 2: Docker (30')

Thư mục: `02-docker/`. **Build từ gốc repo.**

- [ ] Ex 2.1: trả lời 4 câu (base image, workdir, vì sao COPY requirements trước, CMD vs ENTRYPOINT).
- [ ] Ex 2.2:
  ```bash
  docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
  docker run -p 8000:8000 my-agent:develop
  curl -X POST "http://localhost:8000/ask?question=What is Docker?"
  docker images my-agent:develop
  ```
- [ ] Ex 2.3: build `my-agent:advanced` (`-f 02-docker/production/Dockerfile`), ghi **MB develop vs production và % chênh lệch** (số tự đo).
- [ ] Ex 2.4: `touch 02-docker/production/.env.local`, chạy compose có `-p` riêng, vẽ sơ đồ service, test `/health` và `/ask` qua Nginx.
- [ ] **Hiểu:** multi-stage giảm dung lượng ở đâu; vì sao `COPY requirements.txt` đứng trước `COPY . .`.
- [ ] `docker compose -p <tên> down` khi xong.

## CP3 — Part 4: API Security (25')

Thư mục: `04-api-gateway/`

- [ ] Ex 4.1: `AGENT_API_KEY=secret-key-123 python app.py` (develop). Test không key, sai key, đúng key. Trả lời: key check ở đâu, sai key thì sao, rotate thế nào.
- [ ] Ex 4.2: tắt bản develop, chạy `production`, cài requirements. Lấy token ở `POST /auth/token` với `student` / `demo123`.
- [ ] Ex 4.3: đọc `rate_limiter.py` (thuật toán, limit 10 req/phút, bypass admin thế nào). Chạy vòng lặp 20 lần, **thấy 429**.
- [ ] Ex 4.4: đọc `cost_guard.py`, giải thích cách làm cost guard.
- [ ] Dán output `curl -i` cho 401 / 200 / 429 (che token).
- [ ] **Hiểu:** rate limit bảo vệ tốc độ, cost guard bảo vệ tiền.

## CP4 — Part 5: Scaling & Reliability (20')

Thư mục: `05-scaling-reliability/`

- [ ] Ex 5.1–5.2: đọc `develop/app.py` (health, ready, graceful shutdown), thử gửi SIGTERM khi đang có request.
- [ ] Ex 5.3: giải thích vì sao state trong RAM hỏng khi nhiều instance.
- [ ] Ex 5.4–5.5:
  ```bash
  touch 05-scaling-reliability/production/.env.local
  cd 05-scaling-reliability/production
  docker compose -p k5-day14-scaling up -d --build --scale agent=3
  python test_stateless.py          # cổng 8080, POST /chat
  docker compose -p k5-day14-scaling down
  ```
- [ ] Giải thích kết quả `test_stateless.py`.
- [ ] **Hiểu:** `/health` (liveness) khác `/ready` (readiness) ở đâu.

---

## CP5 — Part 6: Final Project (60') → `PASS 12/12`

Thư mục: `06-lab-complete/` (làm tại chỗ). **Chạy `python check_production_ready.py --static-only` sau mỗi bước.**

Thứ tự làm (theo gợi ý của README Part 6):

| # | File | Việc | Tiêu chí |
|---|---|---|---|
| 1 | `app/main.py` | `GET /health` luôn 200, không phụ thuộc Redis | Health |
| 2 | `app/config.py` | Đọc env: `PORT`, `ENVIRONMENT`, `AGENT_API_KEY`, `REDIS_URL`, `RATE_LIMIT_PER_MINUTE` (int), `DAILY_BUDGET_USD` (float). Không hard-code secret | Config |
| 3 | `.env.example` | Liệt kê **đủ** biến (không ghi secret thật); `.env` có trong `.gitignore` | Config |
| 4 | `app/main.py` | `JsonFormatter`: mọi dòng log của app là 1 JSON hợp lệ (ts, level, event, ms…) | Logging |
| 5 | `app/auth.py` | `APIKeyHeader(name="X-API-Key", auto_error=False)`, thiếu/sai → **401** (không dùng `Header(...)` vì sẽ ra 422) | API key |
| 6 | `app/redis_client.py` + `/ready` | Kết nối Redis, `redis_healthy()`; Redis lỗi → **503** | Readiness |
| 7 | `app/rate_limiter.py` | Sliding window 60s bằng sorted set: `ZREMRANGEBYSCORE` → `ZCARD` → vượt thì **429** + `Retry-After: 60` → `ZADD` + `EXPIRE`. Key theo API key. State trong Redis, không dict RAM (Dockerfile chạy 2 worker, script restart agent) | Rate limit |
| 8 | `app/cost_guard.py` | `check_budget()` → **402** khi tổng ≥ `DAILY_BUDGET_USD`; `record_cost()` tính theo giá token, `INCRBYFLOAT` | Cost guard |
| 9 | `app/main.py` `/ask` | Nối: `Depends(verify_api_key)` → `check_rate_limit` → `check_budget` → LLM → `record_cost`. Input sai trả lỗi rõ ràng, **không lộ stack trace** (5 điểm) | Functional |
| 10 | `app/main.py` | Graceful shutdown: dùng `lifespan`. Nếu tự đăng ký handler SIGTERM thì **gọi lại handler cũ** của uvicorn | Shutdown |
| 11 | `Dockerfile` | Multi-stage (builder + runtime), `python:3.11-slim`, user non-root, `HEALTHCHECK` gọi `/health`, < 500 MB, `CMD ["sh","-c","exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]`. Nếu `pip install --user` thì đặt `PYTHONUSERBASE`. Container phải khởi động được khi không có Redis | Docker |
| 12 | `.dockerignore` | Loại `.env`, `__pycache__`, `venv` | .dockerignore |
| 13 | `docker-compose.yml` | Service `agent` (build từ Dockerfile, `REDIS_URL=redis://redis:6379/0`, `depends_on: redis`, `env_file` với `required: false`) + `redis:7-alpine` có healthcheck | Compose |
| 14 | `railway.toml` hoặc `render.yaml` | Railway: builder `DOCKERFILE`, `healthcheckPath = "/health"`. Render: `type: web`, `healthCheckPath: /health`, secret dùng `generateValue` / `sync: false` | Public URL ready |

**Cuối CP5:**
- [ ] `python check_production_ready.py --skip-docker` xanh hết.
- [ ] `python check_production_ready.py` (đầy đủ, có Docker) báo **`PASS 12/12`**.
- [ ] Dán phần "📋 Checklist Deliverable" của output vào `MISSION_ANSWERS.md`.
- [ ] **Hiểu:** vì sao `/health` trả 200 khi Redis chết còn `/ready` trả 503.

**Bẫy hay gặp:**
- `Header(...)` bắt buộc → FastAPI trả 422 thay vì 401.
- Handler SIGTERM không gọi lại handler cũ → uvicorn không bao giờ tắt.
- `pip install --user` mà quên `PYTHONUSERBASE` → container crash khi chạy non-root.
- Rate limit lưu dict RAM → fail khi 2 worker hoặc sau restart.
- Chạy Python Windows → shutdown luôn ⚠️.

## CP6 — Part 3: Cloud Deployment (25')

Deploy **thư mục `06-lab-complete/`** (không deploy app mẫu).

- [ ] Chọn Railway **hoặc** Render làm nền tảng chính.
  - Railway: `cd 06-lab-complete && railway up` (CLI cài bằng `npm`).
  - Render: push GitHub → New → Blueprint; `render.yaml` nằm trong thư mục con nên phải tự khai báo Redis.
- [ ] Tạo **Redis trên nền tảng**, đặt `REDIS_URL` cho service agent.
- [ ] Đặt `AGENT_API_KEY` bằng biến môi trường trên nền tảng (không ghi trong code).
- [ ] Tự kiểm tra 4 lệnh (xem CHECKPOINTS CP6): `/health` 200, `/ready` 200, `/ask` không key 401, có key 200.
- [ ] `python check_production_ready.py --public-url <URL>`.
- [ ] Viết `DEPLOYMENT.md` (URL, lệnh test, biến môi trường đã đặt) theo mục 3 của [DAY14_DELIVERY_CHECKLIST.md](DAY14_DELIVERY_CHECKLIST.md).
- [ ] Ảnh `screenshots/dashboard.png`, `running.png`, `test.png` (che key).
- [ ] `MISSION_ANSWERS.md` Part 3: URL, so sánh `railway.toml` vs `render.yaml` (khác chỗ nào, vì sao) → lấy 3 điểm "nền tảng còn lại".
- [ ] Exercise 3.3: đọc `cloudbuild.yaml` + `service.yaml`, viết 3–5 dòng về pipeline CI/CD (1 điểm, không cần GCP).

## CP7 — Part 7 Bước 1: Benchmark local (45')

Thư mục: `06-lab-complete/benchmark-observability/develop/`

- [ ] Từ gốc repo, tạo báo cáo một lần: `cp -n 06-lab-complete/benchmark-observability/BENCHMARK_REPORT_TEMPLATE.md BENCHMARK_REPORT.md`.
- [ ] `pip install -r requirements.txt`; chạy v1 (`AGENT_VERSION=v1 PORT=8001 python app.py`) và v2 (`AGENT_VERSION=v2 PORT=8002 python app.py`).
- [ ] **Ex 7.1:** xem `/metrics`, tìm 1 ví dụ Counter, Gauge, Histogram; trả lời vì sao label `route` dùng `route.path` (cardinality). Thêm metric `agent_question_length_chars` (Histogram).
- [ ] **Ex 7.2 — Load test 4 mức concurrency:**
  ```bash
  for c in 1 10 50 100; do
    python load_test.py --url http://localhost:8002 --requests 300 --concurrency "$c" --out "reports/load_v2_c${c}.json"
  done
  ```
- [ ] **So sánh `MOCK_SLOW_RATE`** (restart v2 mỗi lần): `0`, `0.03`, `0.1`, mỗi lần `--requests 300 --concurrency 20`, lưu `reports/load_v2_slow_0.json`, `..._0.03.json`, `..._0.1.json`.
- [ ] Giải thích: vì sao avg tăng nhẹ mà p99 tăng vọt; SLO nên đặt theo chỉ số nào.
- [ ] **Ex 7.3 — Eval:**
  ```bash
  python eval/run_eval.py --url http://localhost:8001 --out reports/eval_v1.json
  python eval/run_eval.py --url http://localhost:8002 --out reports/eval_v2.json --baseline reports/eval_v1.json
  ```
- [ ] Đọc `missing_keywords` trong `eval_v2.json` (v2 sai 2 câu: `scaling-03`, `security-02`), thêm vào `KNOWLEDGE_BASE` trong `develop/utils/mock_llm.py`, **tắt rồi bật lại v2** (app không tự nạp code), rồi:
  ```bash
  python eval/run_eval.py --url http://localhost:8002 --min-accuracy 1.0 --baseline reports/eval_v2.json --out reports/eval_v2_fixed.json
  ```
  Cần thấy `Quality gate ... ✅ PASS` (23/23, 0 regression).
- [ ] Viết job CI (`.github/workflows/eval.yml`) hoặc giải thích dùng exit code của `run_eval.py` để chặn merge.
- [ ] Điền `BENCHMARK_REPORT.md` phần đã có số liệu.
- [ ] **Hiểu:** vì sao SLO theo p95/p99; vì sao "cost / câu đúng" tốt hơn "cost / câu".

## CP8 — Part 7 Bước 2: Observability + đóng gói (sau lab)

Thư mục: `06-lab-complete/benchmark-observability/production/`. Luôn dùng `-p k5-day14-observability`.

- [ ] Bật stack, **bắt đầu bằng 1 instance:**
  ```bash
  docker compose -p k5-day14-observability up -d --build --scale agent=1
  ```
- [ ] Mở Locust (8089) chạy 30 users / ramp 5; mở Grafana (3000), chụp `grafana-dashboard.png` **khi có tải**. Trả lời 4 câu Ex 7.4 (p95 vs avg, Nginx chia đều, input vs output tokens/s, `/metrics` qua 8080 trả gì).
- [ ] **Jaeger** (16686): trace chậm nhất (span nào chiếm nhiều thời gian nhất, số ms) → `jaeger-slow-trace.png`; trace lỗi (`error=true`, event `exception`) → `jaeger-error-trace.png`. Lấy `trace_id` từ `docker compose -p ... logs agent | grep llm_error`, chép dòng log JSON và tìm lại trace.
- [ ] **Alerts:** chạy `promtool test rules`. Làm **≥ 2** thí nghiệm (vd A `MOCK_ERROR_RATE=0.2`, C `LLM_MODEL=mock-llm-large`), ghi **thời gian từ lúc đổi đến lúc alert firing**. Chụp **một ảnh** trang Alerts thấy ≥ 2 alert cùng firing → `prometheus-alert-firing.png`. Trả `.env` về như cũ, `docker unpause` nếu có pause.
- [ ] Trả lời câu Ex 7.6: vì sao đổi sang v1 không alert nào firing.
- [ ] **Benchmark scale (Locust headless để có CSV):**
  ```bash
  docker compose -p k5-day14-observability run --rm locust -f /mnt/locust/locustfile.py --host http://nginx --headless -u 100 -r 10 -t 2m --csv /mnt/results/scale_1
  docker compose -p k5-day14-observability up -d --scale agent=3
  # chờ ~15s rồi chạy lại với --csv /mnt/results/scale_3
  ```
- [ ] Chụp ảnh và chép log **trước** khi `docker compose -p k5-day14-observability down -v`.

## Đóng gói và nộp

Cấu trúc đích (xem [SUBMISSION.md](SUBMISSION.md)):

```
├── MISSION_ANSWERS.md
├── DEPLOYMENT.md
├── BENCHMARK_REPORT.md
├── reports/                 # load_v2_c{1,10,50,100}, load_v2_slow_{0,0.03,0.1}, eval_v1, eval_v2, eval_v2_fixed
├── benchmark-results/       # scale_1_stats.csv, scale_3_stats.csv
├── screenshots/             # dashboard, running, test, grafana-dashboard, jaeger-slow-trace, jaeger-error-trace, prometheus-alert-firing (.png)
└── 06-lab-complete/
```

```bash
mkdir -p reports benchmark-results
cp -r 06-lab-complete/benchmark-observability/develop/reports/. reports/
cp -r 06-lab-complete/benchmark-observability/production/benchmark-results/. benchmark-results/
```

**Checklist cuối:**
- [ ] Tên repo đúng mẫu, Public, mở link ở cửa sổ ẩn danh không 404.
- [ ] `python check_production_ready.py` (đầy đủ) báo `PASS 12/12`.
- [ ] `MISSION_ANSWERS.md` đủ Part 1–5 + output script chấm + AI log.
- [ ] `DEPLOYMENT.md` có URL chạy được (4 lệnh ở CP6).
- [ ] `BENCHMARK_REPORT.md` điền đủ, số khớp JSON/CSV; có đủ `reports/`, `benchmark-results/`, 7 ảnh.
- [ ] `git log --all --oneline -- '*.env' '.env'` không in gì.
- [ ] Không có email, số điện thoại trong bài.
- [ ] Commit cuối **trước 23h59 (GMT+7)** ngày lab; nộp **link repo** trên LMS (không nộp zip).

## Thứ tự ưu tiên nếu thiếu thời gian

1. **CP5** (60 điểm): `PASS 12/12`.
2. **CP6** (URL public, tính ở cả Part 3 và Part 6).
3. **CP7** eval + load test (9 điểm).
4. CP1–CP4 (32 điểm, phần lớn chỉ là chạy ví dụ và trả lời câu hỏi).
5. CP8 (15 điểm, làm sau giờ lab nhưng phải trước deadline).
