# ============================================================
# Production Dockerfile — multi-stage, slim, non-root
#
#   builder : cài dependencies vào một virtualenv (/opt/venv)
#   runtime : chỉ copy virtualenv + code sang image sạch, không có pip cache / build tools
#
# Dùng virtualenv thay cho `pip install --user` để khỏi dính bẫy PYTHONUSERBASE:
# user non-root chỉ cần PATH trỏ tới /opt/venv/bin là tìm thấy mọi package.
# ============================================================

# ── Stage 1: builder ─────────────────────────────────────────
FROM python:3.11-slim AS builder

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

RUN python -m venv /opt/venv

# Copy requirements TRƯỚC code để layer cài dependencies được cache khi chỉ sửa code
COPY requirements.txt .
RUN /opt/venv/bin/pip install -r requirements.txt


# ── Stage 2: runtime ─────────────────────────────────────────
FROM python:3.11-slim AS runtime

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# User non-root
RUN groupadd --system app && useradd --system --gid app --home-dir /app --shell /usr/sbin/nologin app

WORKDIR /app

COPY --from=builder /opt/venv /opt/venv
COPY --chown=app:app app ./app
COPY --chown=app:app utils ./utils

USER app

EXPOSE 8000

# Liveness: /health không phụ thuộc Redis nên container khởi động được kể cả khi chưa có Redis
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://localhost:%s/health' % os.getenv('PORT', '8000'), timeout=3)"

# `exec` để uvicorn thay thế shell và làm PID 1: nhận SIGTERM từ `docker stop` và tắt êm.
# Lắng nghe theo biến PORT do platform (Railway/Render) cấp, mặc định 8000.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
