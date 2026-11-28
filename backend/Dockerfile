FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY requirements-inference.txt .
ARG INSTALL_TORCH=1
RUN if [ "$INSTALL_TORCH" = "1" ]; then pip install --no-cache-dir -r requirements-inference.txt --extra-index-url https://download.pytorch.org/whl/cpu; fi
COPY app ./app
RUN useradd -m dermai && mkdir -p /data /app/models && chown -R dermai /data /app/models
USER dermai
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=5 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/api/health/ready', timeout=4)" || exit 1
# --proxy-headers: behind nginx / a cloud load balancer, audit logs and the login limiter see the real client IP
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
