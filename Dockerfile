# ==========================================
# Stage 1: Builder (Build and compile dependencies)
# ==========================================
FROM python:3.10-slim AS builder

# Prevent Python from writing .pyc files and buffer stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build-time compiler dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create isolated virtual environment for dependencies
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Leverage Docker cache: copy dependency manifest first
COPY setup.py requirements.txt ./

# Install dependencies into virtual environment
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e .


# ==========================================
# Stage 2: Runner (Clean production runtime)
# ==========================================
FROM python:3.10-slim AS runner

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

WORKDIR /app

# Install runtime utilities only (omit build tools)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy compiled virtual environment from builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy application source code
COPY . .

# Security: run application as a non-privileged user
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app
USER appuser

# Expose default Streamlit port
EXPOSE 8501

# Health check to monitor Streamlit status
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Start Streamlit application
CMD ["streamlit", "run", "application.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.headless=true"]