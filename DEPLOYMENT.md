# Deployment Information

## Public URL
https://ai-agent-qext.onrender.com

## Platform
Render (Blueprint từ `06-lab-complete/render.yaml`): web service Docker `ai-agent` + Key Value (Redis) `agent-redis`, cả hai ở gói Free, cùng workspace.

> Gói Free tắt service sau 15 phút không có request; request đầu tiên sau đó mất khoảng 1 phút để khởi động lại. Nếu lệnh đầu tiên báo lỗi hoặc timeout, gọi `/health` một lần rồi chạy lại.

## Test Commands

### Health check (không cần key)
```bash
curl https://ai-agent-qext.onrender.com/health
# Expected: HTTP 200, JSON có "status": "ok"
```

### Readiness (Redis kết nối được)
```bash
curl -i https://ai-agent-qext.onrender.com/ready
# Expected: HTTP 200 {"ready": true}   (503 nếu Redis không kết nối được)
```

### API test, không có key
```bash
curl -i -X POST https://ai-agent-qext.onrender.com/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: HTTP 401
```

### API test, có key
```bash
curl -X POST https://ai-agent-qext.onrender.com/ask \
  -H "X-API-Key: $AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "test", "question": "Hello"}'
# Expected: HTTP 200 {"question": "...", "answer": "...", "cost_usd": ...}
```

### Kết quả đã chạy (ngày 2026-11-25)
Chạy từ Git Bash, chỉ in mã HTTP, key nhập bằng `read -s` nên không hiện ra:

| Lệnh | Mong đợi | Kết quả |
|---|---|---|
| `GET /health` | 200 | **200** |
| `GET /ready` | 200 | **200** |
| `POST /ask` không key | 401 | **401** |
| `POST /ask` có key | 200 | **200** |

Thêm: `python check_production_ready.py --static-only --public-url https://ai-agent-qext.onrender.com` báo `✅ Public URL: GET .../health → 200`.

## Environment Variables Set
Khai báo trong `06-lab-complete/render.yaml`, **không có giá trị secret nào trong code hay repo**:

| Biến | Nguồn giá trị |
|---|---|
| `AGENT_API_KEY` | Render tự sinh (`generateValue: true`); xem trong dashboard → Environment |
| `REDIS_URL` | Tự lấy từ Key Value `agent-redis` (`fromService`, địa chỉ nội bộ) |
| `ENVIRONMENT` | `production` |
| `RATE_LIMIT_PER_MINUTE` | `10` |
| `DAILY_BUDGET_USD` | `1.0` |
| `PORT` | Render tự cấp; `CMD` trong Dockerfile lắng nghe theo `${PORT:-8000}` |

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
