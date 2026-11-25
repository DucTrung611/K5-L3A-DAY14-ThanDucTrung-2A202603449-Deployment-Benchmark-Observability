# Benchmark & Observability Report — Day 14

> Mọi con số lấy từ report JSON trong `reports/` (xem mục *Nguồn số liệu* cuối mỗi bảng). Phần số đo thăm dò không có file JSON được ghi rõ là "từ terminal".
> **Trạng thái:** mục 1, 2, 3 và Phụ lục A đã làm (CP7). Mục 4, 5, 6 làm ở CP8 (Docker stack), **chưa có số liệu**.

**Họ tên:** Than Duc Trung (MSSV 2A202603449)
**Ngày chạy:** 2026-11-25
**Môi trường:** Windows 11 Pro, AMD Ryzen 7 5700U (8 nhân / 16 luồng), RAM 15,4 GB. Python 3.11.5 trong virtualenv, agent chạy trực tiếp bằng `python app.py` (không Docker), `load_test.py` và `run_eval.py` chạy **trên cùng máy** với agent. Agent v1 ở cổng **8101**, v2 ở cổng **8102** (cổng 8001/8002 theo đề đang bị server của bài trước chiếm, nên trường `target` trong JSON ghi 8101/8102).

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Latency cơ bản của mock LLM ≈ 200 ms (p50 đo được 200–205 ms); 500 ms là khoảng 2,5 lần mức đó, đủ chặt để người dùng thấy nhanh nhưng chừa chỗ cho jitter. Đây cũng là ngưỡng mặc định của `load_test.py`. |
| Error rate `/ask` | < 2 % | Mock LLM cố ý lỗi ~1 % (`MOCK_ERROR_RATE`); đặt 2 % cho phép dao động ngẫu nhiên mà vẫn bắt được sự cố thật. Cũng là ngưỡng mặc định của `load_test.py`. |
| Accuracy trên golden dataset | ≥ 85 % | Khớp ngưỡng job CI ở Exercise 7.3; v2 ban đầu 91,3 % qua, v1 4,3 % không qua. (`run_eval.py` mặc định là 80 %.) |

Với p95, SLO đặt theo percentile chứ không theo trung bình, lý do ở mục 2.2.

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

Mỗi dòng là **một lần chạy duy nhất**, 300 request, agent v2 mặc định (`MOCK_SLOW_RATE=0.03`, `MOCK_ERROR_RATE=0.01`) trừ khi ghi khác. Chưa lặp lại để lấy trung bình, nên các con số có dao động giữa các lần chạy.

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 4,05 | 204,2 | 235,4 | 1712,4 | 0,33 % (1×503) | PASS |
| 10 | 39,30 | 199,9 | 443,0 | 1708,5 | 1,00 % (3×503) | PASS |
| 50 | 38,63 | 538,5 | 3925,7 | 5434,4 | 0,67 % (2×503) | **FAIL** (p95) |
| 100 | 37,17 | 1109,4 | 5759,4 | 7191,3 | 0,33 % (1×503) | **FAIL** (p95) |

*Nguồn:* `reports/load_v2_c1.json`, `load_v2_c10.json`, `load_v2_c50.json`, `load_v2_c100.json`. "SLO" là kết quả `slo.passed` trong JSON, gồm cả hai ngưỡng p95 ≤ 500 ms và error rate ≤ 2 %; hai dòng FAIL đều do p95.

**Nhận xét:** RPS **không** tăng tuyến tính theo concurrency.
- **Từ 1 lên 10** thì gần tuyến tính: 4,05 → 39,30 req/s (gấp 9,7 lần khi concurrency gấp 10 lần). Khớp định luật Little: RPS ≈ concurrency / latency trung bình = 10 / 0,253 s ≈ 39,5.
- **Từ 50 trở lên RPS đứng yên ở ~38 req/s** (38,63 và 37,17) dù concurrency tăng gấp đôi. Khi thông lượng không tăng mà số request đang chờ tăng, mỗi request phải xếp hàng lâu hơn: p50 từ 200 ms lên 539 ms và 1109 ms, p95 vọt lên 3,9 s và 5,8 s, vi phạm SLO. Kiểm tra bằng Little: 50 / 38,63 ≈ 1,29 s so với avg đo được 1036 ms (số đo phía client), cùng bậc.
- **Số đo thăm dò từ terminal** (không có file JSON đi kèm), để biết mức bão hòa đó nằm ở đâu:
  - Ở concurrency 20 với `MOCK_SLOW_RATE=0`, một client đạt tới **88,24 req/s** (`reports/load_v2_slow_0.json`), tức server xử lý được hơn 38 req/s.
  - Chạy **hai** `load_test.py` song song, mỗi cái concurrency 50: mỗi cái đạt 37,7 và 41,0 req/s (cộng ~79 req/s). Vậy mức ~38 req/s ở concurrency 50 và 100 là giới hạn **của một tiến trình load test**, chưa phải sức chứa tối đa của server.
  - Tôi thử giả thuyết "httpx chỉ giữ 20 kết nối keep-alive" bằng một bản sao `load_test.py` đặt `max_keepalive_connections` bằng concurrency: kết quả không đổi (38,3 so với 38,7 req/s ở c=50; 37,1 so với 36,3 ở c=100). **Giả thuyết bị bác bỏ; tôi chưa tìm ra nguyên nhân gốc** của mức bão hòa này.
- **Kết luận thận trọng:** dùng được để nói latency ở concurrency 1–10 ổn và SLO p95 được giữ; số ở concurrency 50 và 100 chủ yếu phản ánh hàng đợi phía generator trên cùng máy. Muốn đo sức chứa thật của agent thì phải dùng nhiều generator hoặc Locust (làm ở CP8, mục 5).

### 2.2 Tail latency

300 request, concurrency 20, restart v2 trước mỗi lần chạy.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) | RPS | Error rate |
|---|---|---|---|---|---|
| 0 | 221,6 | 469,4 | 506,1 | 88,24 | 0,00 % |
| 0.03 (mặc định) | 271,0 | 513,2 | 1726,5 | 55,96 | 0,67 % |
| 0.1 | 378,2 | 1701,7 | 1722,6 | 43,60 | 1,33 % |

*Nguồn:* `reports/load_v2_slow_0.json`, `load_v2_slow_0.03.json`, `load_v2_slow_0.1.json`.

**Nhận xét:**
- **p99 là chỉ số nhạy nhất với request chậm, tiếp theo là p95; avg kém nhạy nhất.** Khi tỉ lệ chậm từ 0 lên 3 %: avg tăng 22 % (221,6 → 271,0) trong khi p99 tăng gấp 3,4 lần (506,1 → 1726,5). Khi lên 10 %: avg tăng 71 % so với mức 0, còn p95 tăng gấp 3,6 lần (469,4 → 1701,7).
- **Vì sao p95 chưa nhúc nhích ở 3 %:** request chậm chiếm ~3 %, nằm trên đường p95 nên p95 chưa bị kéo lên nhiều (513 so với 469); nhưng chúng đã chiếm hết vùng p99 (≈1,7 s = khoảng 200 ms cơ bản + 1500 ms trễ thêm của `MOCK_SLOW_MS`). Ở 10 % thì chúng vượt qua đường p95 nên p95 cũng vọt lên 1,7 s. Mỗi percentile "thấy" tail ở một ngưỡng tỉ lệ khác nhau.
- **Vì sao SLO không nên đặt theo average:** trung bình trộn lẫn 97 % request nhanh với 3 % request rất chậm nên che giấu tail; ở 3 % avg chỉ 271 ms (trông ổn) trong khi cứ 100 người thì có ~3 người chờ ~1,7 s. SLO phải theo p95/p99 để phản ánh trải nghiệm của nhóm chậm nhất.
- **Độ tin cậy:** mỗi mức chỉ chạy một lần với 300 request, nên p99 dựa trên khoảng 3 mẫu cuối và dao động giữa các lần chạy. Lần chạy mặc định (`0.03`) cho p95 = 513 ms, **vượt** SLO 500 ms (FAIL) dù chỉ hơn 13 ms; ví dụ trong README cho p95 ≈ 202 ms ở cùng cấu hình. Ngay cả mức `0` cũng có p95 = 469 ms (p50 = 205 ms, max = 524 ms); tôi chưa điều tra nguyên nhân của đuôi này.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Golden dataset 23 câu, câu đúng khi trả lời chứa ≥ 60 % keyword mong đợi.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4,3 % (1/23) | 91,3 % (21/23) | **100 % (23/23)** |
| Avg tokens / câu | 56,2 | 109,0 | 113,7 |
| Tổng cost (USD) | 0,000392 | 0,000760 | 0,000790 |
| Cost / câu đúng (USD) | 0,00039195 | 0,00003619 | 0,00003436 |
| Quality gate | FAIL | PASS | PASS |

*Nguồn:* `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`. Cột "Quality gate" là `quality_gate.passed`: v1 chạy với ngưỡng mặc định 80 %; v2 so với baseline v1; v2 sau khi sửa chạy với `--min-accuracy 1.0` và `--baseline reports/eval_v2.json`.

**Những câu v2 trả lời sai ban đầu và cách sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| `security-02` ("JWT khác gì API key trong xác thực?") | `token`, `hết hạn`, `chữ ký` | Thêm entry `["jwt"]` vào cuối `KNOWLEDGE_BASE` (`develop/utils/mock_llm.py`): tài liệu nói API key là chuỗi cố định không tự hết hạn, JWT là token có chữ ký số kèm thời điểm hết hạn. Trước đó v2 không tìm thấy tài liệu nào nên trả lời chung chung. |
| `scaling-03` ("Kubernetes HPA scale dựa trên những chỉ số nào?") | `cpu`, `memory`, `custom metrics` | Thêm entry `["hpa", "autoscal"]` với tài liệu nêu HPA scale theo CPU, memory hoặc custom metrics. |

Sau khi sửa phải tắt rồi bật lại agent v2 (app không tự nạp lại code). Kết quả: `Câu được cải thiện: 2`, `Câu bị regression: 0`, `Quality gate (accuracy ≥ 100%, không regression): PASS`, exit code **0**. Tôi chọn từ khoá kích hoạt hẹp (`hpa`, `autoscal`, `jwt`) để các entry mới không "cướp" câu hỏi của entry khác; việc không có regression được xác nhận bằng `--baseline`, không phải giả định.

*Lưu ý:* chỉ sửa `develop/utils/mock_llm.py`. Bản `production/utils/mock_llm.py` (dùng cho stack Docker ở CP8) **chưa** được cập nhật.

**Quality gate chặn bản tệ hơn:** chạy eval cho v1 với `--baseline reports/eval_v2.json` (terminal, không lưu file):

```text
  Accuracy                     91.3%        4.3%    -87.0 điểm %
  ⚠️  Câu bị regression : 20 ['docker-01', 'docker-02', 'probe-01', ... 'cloud-01']
  Quality gate (accuracy ≥ 80%, không regression): ❌ FAIL
  exit code = 1
```

`run_eval.py` thoát với **exit code 1** khi accuracy dưới ngưỡng **hoặc** có regression, nên đặt nó trong CI thì job fail và PR không merge được. Job CI (Exercise 7.3, chưa thêm vào repo để tránh kích hoạt workflow ngoài ý muốn):

```yaml
# .github/workflows/eval.yml
name: quality-gate
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Run agent + eval
        working-directory: 06-lab-complete/benchmark-observability/develop
        run: |
          pip install -r requirements.txt
          AGENT_VERSION=v2 MOCK_ERROR_RATE=0 python app.py &
          sleep 3
          python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85
```

Để PR bị chặn thật, bật *branch protection* yêu cầu job `quality-gate` phải pass trước khi merge.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- **Chất lượng:** v2 (có retrieval) đúng 21/23 so với 1/23 của v1; sau khi bổ sung tài liệu thì 23/23.
- **Chi phí:** v2 tốn nhiều token hơn vì prompt dài hơn (có thêm tài liệu): 109,0 so với 56,2 token/câu (×1,94) và tổng cost 0,000760 so với 0,000392 USD (×1,94). Nhưng **trên mỗi câu trả lời đúng** thì v2 rẻ hơn khoảng **10,8 lần** (0,00003619 so với 0,00039195 USD), vì v1 trả tiền cho hầu hết các câu sai. Đây là lý do dùng "cost / câu đúng" thay vì "cost / câu" để so hai phiên bản.
- **Latency:** v2 thêm bước retrieval (~20 ms theo `MOCK_RETRIEVAL_MS`). Trong eval, p95 của v2 (1543 ms) thấp hơn v1 (1668 ms), nhưng **không nên rút ra kết luận về latency** từ đó: chỉ có 23 mẫu nên p95 do một hai request chậm quyết định (README cũng cảnh báo). Latency phải đo bằng load test (mục 2).

---

## 4. Observability stack (production)

Stack chạy bằng `docker compose -p k5-day14-observability up -d --build --scale agent=1` (agent × N + Nginx + Prometheus + Grafana + Jaeger + Locust), cùng máy với mục 2.

> **Lỗi gặp khi bật stack:** container `agent` restart liên tục với `ModuleNotFoundError: No module named 'uvicorn'`. Nguyên nhân: `Dockerfile` cài package bằng `pip install --user` rồi copy sang `/home/agent/.local`, nhưng user `agent` có home là `/app` nên Python tìm package ở `/app/.local`. Đã sửa bằng cách thêm `ENV PYTHONUSERBASE=/home/agent/.local` vào `production/Dockerfile` (cùng bẫy đã nêu ở Part 6).
>
> **Hai lỗi khi chạy lệnh Locust trong Git Bash (Windows):** (1) Git Bash tự đổi `/mnt/locust/locustfile.py` thành `C:/Program Files/Git/mnt/...`; phải đặt `MSYS_NO_PATHCONV=1`. (2) `docker compose run locust` tự bật thêm một agent (vì `deploy.replicas: 2`) làm hỏng phép đo "1 instance"; phải thêm `--no-deps`.

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải: [`screenshots/grafana-dashboard.png`](screenshots/grafana-dashboard.png) (3 instance, ~62 req/s, đủ 4 hàng panel)
- [x] Một trace chậm trong Jaeger: [`screenshots/jaeger-slow-trace.png`](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (span `chat` có event `exception`): [`screenshots/jaeger-error-trace.png`](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với 2 alert đang **firing** (`AgentHighErrorRate` giá trị 0,2024 và `AgentHighLatencyP95`): [`screenshots/prometheus-alert-firing.png`](screenshots/prometheus-alert-firing.png), chụp từ thí nghiệm A + B ở mục 4.2

Unit test cho alert rules: `promtool test rules alert_rules_test.yml` → `SUCCESS` (3 test case: error rate 10% phải firing, 1% không firing, instance down phải firing).

**Trả lời Exercise 7.4** (số lấy từ Prometheus khi chạy Locust 100 user vào 3 instance):
1. **p95 và avg:** p50 = 180 ms, avg = 239 ms, p95 = 296 ms. Avg cao hơn p50 vì có ~3 % request chậm (mock cộng 1500 ms), nhưng chúng chiếm dưới 5 % nên **chưa lọt vào p95**; chúng nằm ở p99 (Locust báo p99 = 1700 ms). Khoảng cách avg–p50 và p95–p99 cho thấy phân bố có đuôi dài, đúng ý nghĩa của tail latency ở mục 2.2.
2. **Nginx có chia đều không?** Có, gần đều: 3,15 / 4,00 / 3,92 req/s cho 3 instance, và 12 request liên tiếp chia 4 / 4 / 4 theo header `X-Served-By`.
3. **Vì sao input tokens/s (801) lớn hơn output tokens/s (426)?** Mỗi request gửi cả system prompt và tài liệu retrieval của v2 vào input, trong khi câu trả lời (output) ngắn hơn nhiều. Chi phí vì thế chủ yếu đến từ phía input.
4. **`curl http://localhost:8080/metrics` trả gì?** `HTTP/1.1 404 Not Found`. Nginx cố ý chặn `/metrics` ra ngoài (`location = /metrics { return 404; }`) vì metric lộ thông tin hệ thống; Prometheus scrape trực tiếp trong mạng nội bộ Docker.

### 4.2 Thí nghiệm "phá hệ thống"

Nền tải: Locust 30 user (spawn rate 5), 2 instance agent, chạy liên tục cả phiên. Giờ là giờ máy Windows, ghi bằng một script poll `GET /api/v1/alerts` của Prometheus mỗi 5 giây (`pending` = điều kiện đúng nhưng chưa đủ `for`). **Thời gian tính từ lúc tôi chạy `docker compose up -d` để áp dụng thay đổi** (khoảng 7 giây trước khi container mới lên).

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` (17:33:35) | `AgentHighErrorRate` (`for: 1m`): pending 17:34:16 (+41 s), **firing 17:35:16** | **1 phút 41 giây** (giá trị lúc firing ≈ 20 %, trang Alerts ghi 0,2024) | Error rate (stat chuyển đỏ), Requests/s theo status code (đường 503), trace lỗi trong Jaeger |
| B | thêm `MOCK_SLOW_RATE=0.3` (17:35:24, vẫn giữ A) | `AgentHighLatencyP95` (`for: 2m`): pending 17:36:07 (+43 s), **firing 17:38:02** | **2 phút 38 giây** (p95 lúc firing: 1,898 s) | Latency p50/p95/p99, stat Latency p95 |
| C | `LLM_MODEL=mock-llm-large` (17:41:22, từ đường cơ sở sạch) | `LLMCostBurnRateHigh` (`for: 2m`): pending 17:41:58 (+36 s), **firing 17:43:58** | **2 phút 36 giây** | Cost burn rate (USD/giờ), LLM latency p95 theo model |
| D | `docker pause` agent-1 (17:40:06) | `AgentInstanceDown` (`for: 30s`): pending 17:40:17 (+11 s), **firing 17:40:47**; sau `unpause` (17:41:07) tự giải lúc 17:41:12 | **41 giây** (giải trong 5 giây sau khi unpause) | Instances up (còn 1/2), Requests/s theo instance |
| E | `AGENT_VERSION=v1` (17:44:21) | **Không có alert mới** | không có | Retrieval hit ratio (panel), bảng "Phiên bản đang chạy" (v2 → v1) |

**Số đo kèm theo:**
- **A + B (ảnh `prometheus-alert-firing.png`):** hai alert cùng firing lúc 17:38:02. B được đo khi A còn hiệu lực nên không phải đo riêng; sau khi trả `.env` về mặc định, hai alert tắt lúc 17:39:52 (A) và 17:39:57 (B).
- **C:** burn rate 5 phút ở đường cơ sở 30 user (model small) là **$1,63/giờ**, dưới ngưỡng $2/giờ; sau khi đổi model, burn rate 1 phút lên **$32,73/giờ** (5 phút: $16,88/giờ), LLM p95 ≈ 497 ms; p95 `/ask` = 713 ms nên chưa vượt ngưỡng latency 1 s.
- **D, điều README dự đoán đã xảy ra:** trong 1 phút pause (10:40:06–10:41:05 UTC), Nginx ghi 872 response 200, 5 response 503 (lỗi ngẫu nhiên của mock) và **30 response 504** do instance bị pause không trả lời, trong khi error rate phía agent chỉ **0,50 %** (dưới ngưỡng 5 %). Lỗi 504 sinh ra ở Nginx nên không hề xuất hiện trong metric của agent. Đây là bài học "metric chỉ phản ánh những gì chính service đó nhìn thấy".
- **E:** sau khi đổi sang v1, p95 `/ask` là 199 ms, không có alert lỗi hay latency nào, trong khi chất lượng giảm mạnh (eval v1 chỉ 4,3 %). `LLMCostBurnRateHigh` vẫn còn firing lúc đó nhưng chỉ là dư âm của thí nghiệm C trong cửa sổ 5 phút (burn rate 5 phút lúc đó $10,76/giờ), **không phải do v1**.

**Lưu ý đo đạc:**
- Mỗi lần `docker compose up -d` tạo lại container, nên `AgentInstanceDown` luôn chuyển `pending` khoảng 10–15 giây rồi tự tắt (vì địa chỉ cũ còn nằm trong DNS service discovery). Nó không bao giờ đủ `for: 30s` để firing, nên không phải báo động giả; đây là nhiễu thoáng qua mà tôi bỏ qua trong bảng.
- Mỗi thí nghiệm chỉ chạy một lần; thời gian có thể lệch vài giây giữa các lần vì chu kỳ đánh giá rule là 5 giây và cửa sổ `rate(...[1m])`.
- **Đính chính:** trong lúc làm, tôi từng ghi nhận burn rate $3,9/giờ ở 30 user rồi kết luận ngưỡng $2/giờ luôn bị vượt ở đường cơ sở. Kết luận đó **sai**: cửa sổ 5 phút lúc đó còn chứa phần đuôi của tải 100 user trước đó. Đo lại trên đường cơ sở sạch cho $1,63/giờ, nên thí nghiệm C có ý nghĩa.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Metric hạ tầng (error rate, latency, up) chỉ cho biết agent *chạy* thế nào, không cho biết nó *trả lời đúng không*. v1 vẫn trả 200 nhanh và rẻ, chỉ là sai. Cách phát hiện:
1. **Eval trên golden dataset trước khi deploy** như quality gate trong CI (`run_eval.py` với `--baseline`): trong bài này nó bắt được v1 với 20 regression và exit code 1. Đây là chốt chặn chính.
2. **Đánh giá trên traffic thật:** lấy mẫu một phần câu trả lời và chấm bằng LLM-as-judge hoặc so sánh với đáp án đã biết, kèm tín hiệu từ người dùng (thumbs up/down, câu hỏi lặp lại).
3. **Metric chất lượng riêng cho agent:** panel *Retrieval hit ratio* mất đi khi chạy v1 (không còn bước retrieval); nên có alert khi hit ratio tụt hoặc khi metric này biến mất, và alert khi phiên bản (`agent_info`) đang chạy khác phiên bản dự kiến.
4. **Canary / shadow:** cho một phần nhỏ traffic chạy bản mới và so sánh chất lượng với bản cũ trước khi chuyển toàn bộ.

### 4.3 Debug bằng trace

Trace chậm nhất trong lần chạy `scale_1` (100 user vào 1 instance, lấy từ Jaeger API trong 1 500 trace gần nhất):

- `trace_id`: `15393f2de1b1bf42a1574923bc52e7fe`
- Tổng thời gian: **2490,8 ms** (`POST /ask`)
- Span chiếm nhiều thời gian nhất: **`chat mock-llm-small` = 1685,0 ms (67,7 %)**, với `gen_ai.usage.input_tokens=74`, `output_tokens=37`. Đây là LLM chậm, không phải code của agent.
- Các span khác: `agent.run` 1800,7 ms, `agent.retrieve_context` 115,4 ms (`retrieval.documents=1`).
- **Phần 690 ms nằm ngoài `agent.run`:** `POST /ask` dài 2490,8 ms nhưng `agent.run` chỉ 1800,7 ms, và trên ảnh Jaeger `agent.run` chỉ bắt đầu sau ~623 ms. Khoảng chờ này xảy ra **trước khi handler chạy**; khả năng cao là request xếp hàng khi 1 instance (giới hạn 0,5 CPU) đang quá tải với 100 user (panel Saturation lúc đó hiện 21 request đang xử lý). Đây là suy luận từ ảnh trace, tôi chưa đo trực tiếp thời gian xếp hàng.

Dòng log JSON có cùng `trace_id` (`docker compose -p k5-day14-observability logs agent | grep 15393f2d...`):

```json
{"ts": "2026-11-25T10:26:33.944279+00:00", "level": "INFO", "service": "observable-agent", "instance": "b7c74d9c0d97", "event": "llm_call", "trace_id": "15393f2de1b1bf42a1574923bc52e7fe", "span_id": "9a268689905a92b0", "request_id": "7593cdf5edb1", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 74, "output_tokens": 37, "cost_usd": 3.3e-05, "llm_ms": 1675.1}
{"ts": "2026-11-25T10:26:33.946684+00:00", "level": "INFO", "service": "observable-agent", "instance": "b7c74d9c0d97", "event": "http_request", "trace_id": "15393f2de1b1bf42a1574923bc52e7fe", "span_id": "9a268689905a92b0", "request_id": "7593cdf5edb1", "method": "POST", "route": "/ask", "status": 200, "ms": 2488.3}
```

Log báo `llm_ms: 1675.1` và `ms: 2488.3`, khớp với span `chat` (1685 ms) và tổng trace (2490,8 ms) trong Jaeger.

**Trace lỗi** (`error=true`): `fd839c79d767811dc942223eba8238d6`, `POST /ask` trả **503**, 407,4 ms. Span `chat mock-llm-small` có `error.type=upstream_unavailable` và event `exception`; span cha `agent.run` cũng ghi `exception`. Log tương ứng:

```json
{"ts": "2026-11-25T10:26:49.444733+00:00", "level": "INFO", "service": "observable-agent", "instance": "b7c74d9c0d97", "event": "llm_error", "trace_id": "fd839c79d767811dc942223eba8238d6", "span_id": "9358467d8adfd3f8", "request_id": "11a4c9ad9e2f", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

Trong số 1 500 trace Jaeger trả về có 14 trace có span lỗi; log agent ghi 69 dòng `llm_error` trong cả phiên.

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

Locust headless, 100 user, spawn rate 10, 2 phút, qua Nginx. Số liệu là dòng `/ask` trong `benchmark-results/scale_N_stats.csv` (bỏ dòng `/health`):

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 53,99 | 240 | 1400 | 1800 | 69 / 6 369 (1,08 %) |
| 3 | 59,66 | 200 | 300 | 1700 | 68 / 7 059 (0,96 %) |

*Nguồn:* `benchmark-results/scale_1_stats.csv`, `benchmark-results/scale_3_stats.csv`. Mỗi cấu hình chạy một lần.

**Giải thích kết quả:**
- **p95 cải thiện rõ rệt (1400 → 300 ms, giảm 79 %)** vì 1 instance (giới hạn 0,5 CPU) bị quá tải với 100 user: panel Saturation lúc đó hiện 21 request đang xử lý và có cả khoảng chờ trước `agent.run` (mục 4.3). Ba instance chia tải nên không còn xếp hàng; p50 cũng giảm từ 240 xuống 200 ms, xấp xỉ latency cơ bản của mock.
- **RPS chỉ tăng 10 % (53,99 → 59,66)** dù gấp ba số instance. Locust là mô hình *vòng kín*: mỗi user chờ 0,5–2 s giữa các request, nên 100 user tạo ra tối đa khoảng 100 / (1,25 + latency) ≈ 60–65 req/s dù server nhanh đến đâu. Tức thông lượng lúc này bị giới hạn bởi **lượng tải được tạo ra**, chưa phải bởi server; để thấy RPS tăng theo số instance phải dùng nhiều user hơn hoặc giảm thời gian chờ. Phần giải thích này là suy luận từ cách Locust hoạt động, tôi chưa chạy lại với số user lớn hơn để xác nhận.
- **p99 gần như không đổi (1800 → 1700 ms)** và **tỉ lệ lỗi vẫn ~1 %**: cả hai không phụ thuộc số instance. p99 ≈ 1,7 s chính là request "chậm bất thường" của mock LLM (`MOCK_SLOW_MS=1500` cho ~3 % request), còn ~1 % lỗi là `MOCK_ERROR_RATE` mặc định. Thêm instance không sửa được những thứ này.
- **Nút thắt:** khi 1 instance, nút thắt là **tài nguyên của instance** (CPU/hàng đợi) nên p95 vọt lên; khi 3 instance, nút thắt chuyển sang **độ trễ của LLM** (span `chat`, panel LLM latency), vốn không giảm khi scale. Muốn giảm p99 phải xử lý phía LLM (timeout, retry, hedging, model nhanh hơn) chứ không phải thêm instance.

---

## 6. Kết luận

**3 điều học được về benchmark & observability:**
1. **Trung bình che giấu đuôi, SLO phải theo percentile.** Khi 3 % request chậm, avg chỉ tăng 22 % nhưng p99 tăng gấp 3,4 lần (mục 2.2); và khi dùng Locust, p99 vẫn ≈ 1,7 s dù scale từ 1 lên 3 instance (mục 5): thêm instance sửa được hàng đợi (p95 1400 → 300 ms) nhưng không sửa được độ trễ của LLM.
2. **Metric chỉ phản ánh những gì chính service đó nhìn thấy.** Thí nghiệm D tạo 30 lỗi 504 ở Nginx mà error rate phía agent vẫn 0,50 %; thí nghiệm E làm chất lượng sụp từ 91,3 % xuống 4,3 % mà không alert nào kêu. Cần thêm giám sát ở tầng load balancer và chốt chặn chất lượng (eval trong CI).
3. **Phương pháp đo cũng có thể sai, phải kiểm chứng.** Trong bài này tôi gặp các lỗi: đọc file CSV khi Locust còn đang ghi dở; kết luận ngưỡng cost luôn bị vượt vì cửa sổ 5 phút còn dư âm của tải trước; nghi ngờ keep-alive là nút thắt của `load_test.py` rồi bị chính phép thử bác bỏ; và mức ~38 req/s ở concurrency cao vẫn **chưa tìm ra nguyên nhân**. Các số liệu trong báo cáo đều đã được đối chiếu lại với file gốc.

**Nếu đưa agent này lên production thật, tôi sẽ thêm:**
- **Alert theo tầng load balancer:** tỉ lệ 5xx/504 của Nginx và một synthetic probe từ bên ngoài, để bắt đúng loại sự cố của thí nghiệm D.
- **Alert p99** (không chỉ p95) và alert **bão hòa** (`agent_in_flight_requests`, CPU/memory của container), vì p95 chỉ chạm đuôi khi tỉ lệ chậm vượt 5 %.
- **Metric chất lượng:** retrieval hit ratio, tỉ lệ câu trả lời "không biết/chung chung", và điểm LLM-as-judge lấy mẫu; alert khi phiên bản agent đang chạy lệch dự kiến.
- **Cost:** đặt ngưỡng theo ngân sách ngày/tháng và dùng burn rate nhiều cửa sổ (ví dụ 5 phút và 1 giờ) thay cho một ngưỡng $/giờ cố định, vì ngưỡng $2/giờ hiện tại nằm sát mức vận hành bình thường ở 30 user ($1,63/giờ) và lệch ngay khi lưu lượng tăng.
- **Tracing có lấy mẫu** (ví dụ giữ 10 % và giữ toàn bộ trace lỗi/chậm) để giảm chi phí khi traffic lớn.

---

## Phụ lục A — Exercise 7.1: đọc metrics của agent

**Counter / Gauge / Histogram trong `/metrics` của agent v2** (sau một request):

| Loại | Ví dụ trong output | Vì sao thuộc loại này |
|---|---|---|
| Counter | `http_requests_total{method="POST",route="/ask",status="200"} 1.0`; `llm_tokens_total{model="mock-llm-small",type="input"} 91.0` | Chỉ tăng, dùng với `rate()`. |
| Gauge | `agent_in_flight_requests 0.0`; `agent_info{model="mock-llm-small",version="v2"} 1.0` | Lên xuống được (số request đang xử lý). |
| Histogram | `http_request_duration_seconds_bucket{le="0.3",...}`, `llm_request_duration_seconds_sum/count` | Chia giá trị vào bucket để tính percentile bằng `histogram_quantile()`. |

**Vì sao label `route` dùng `route.path` (template) mà không dùng URL thật?** Mỗi tổ hợp giá trị label là một time series. Nếu dùng URL thật, bot quét hàng nghìn URL lạ (`/wp-admin`, `/.env`, `/a1b2c3`...) sẽ tạo hàng nghìn series, Prometheus tốn RAM. Đã kiểm chứng: tôi gọi 5 URL lạ (`/wp-admin`, `/.env`, `/a1b2c3`, `/x9y8z7`, `/phpmyadmin`) và `/metrics` chỉ có **một** series:

```text
http_requests_total{method="GET",route="unmatched",status="404"} 5.0
```

**Metric mới `agent_question_length_chars`** (Histogram, `develop/app.py`) với các bucket 20, 50, 100, 200, 500, 1000, 2000 ký tự, gọi `QUESTION_LENGTH.observe(len(body.question))` ở đầu `ask()`. Gọi thử một câu hỏi 40 ký tự cho `agent_question_length_chars_count 1.0` và `agent_question_length_chars_sum 40.0`. Dùng Histogram thay vì label `length=...` vì độ dài có vô số giá trị, làm label sẽ bùng nổ cardinality.
