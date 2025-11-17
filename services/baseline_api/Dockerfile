FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --upgrade pip
RUN pip install wheel

COPY baseline_api/requirements.txt .
COPY baseline_api/rest_server.py .
COPY shared/logging_config.py .
COPY shared/model.py .
COPY shared/preprocessor.py .
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt

FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN addgroup --system nonroot && adduser --system --ingroup nonroot nonroot

COPY --from=builder /app .
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

# Set permissions
USER nonroot

# Expose the port the app runs on
EXPOSE 8000

CMD ["gunicorn", "--workers=4", "--bind", "0.0.0.0:8000", "rest_server:app"]