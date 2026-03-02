# ── Backend Dockerfile ───────────────────────────────────────────────────────
# Multi-stage build keeps the final image lean.
# Stage 1: install all dependencies into a virtual-env layer.
# Stage 2: copy only the venv + app code — no build tools in production image.

# ── Stage 1: builder ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools needed by some Python packages (e.g. PyMuPDF) and Tesseract for OCR
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first so Docker can cache this layer.
COPY requirements.txt .

# Install dependencies with retry and timeout
RUN pip install --no-cache-dir --prefix=/install \
    --default-timeout=100 \
    --index-url https://pypi.org/simple \
    -r requirements.txt || \
    (sleep 10 && pip install --no-cache-dir --prefix=/install \
    --default-timeout=100 \
    --index-url https://pypi.org/simple \
    -r requirements.txt)

# ── Stage 2: runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Install Tesseract OCR required for pytesseract fallback
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*


# Copy installed packages from builder stage.
COPY --from=builder /install /usr/local

# Copy application source.
COPY . .

# Create writable directories for uploaded and output PDFs.
RUN mkdir -p uploads outputs

# Railway injects PORT at runtime; default to 8000 locally.
ENV PORT=8000

# Expose the port so Docker/Railway knows which port to route to.
EXPOSE ${PORT}

# ─── Start command ────────────────────────────────────────────────────────────
# --host 0.0.0.0  → required on Railway (default 127.0.0.1 won't be reachable)
# --port $PORT    → reads Railway's injected PORT env var
# --workers 1     → single worker avoids asyncio.Queue being split across procs
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT --workers 1"]
