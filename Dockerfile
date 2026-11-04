# syntax=docker/dockerfile:1
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt .
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi; \
    pip install --no-cache-dir -r requirements.txt
RUN useradd --uid 10001 --create-home qwoms && mkdir /data && chown qwoms:qwoms /data
COPY --chown=qwoms:qwoms app ./app
COPY --chown=qwoms:qwoms migrations ./migrations
COPY --chown=qwoms:qwoms alembic.ini .
USER qwoms
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
