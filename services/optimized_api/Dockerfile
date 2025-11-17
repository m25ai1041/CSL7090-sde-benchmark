FROM python:3.11-slim AS builder

WORKDIR /app

RUN pip install --no-cache-dir --upgrade pip
RUN pip install wheel

# Install build tools required for Cython + wheels
RUN apt-get update && apt-get install -y \
    build-essential \
    python3-dev \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip + wheel
RUN pip install --upgrade pip setuptools grpcio grpcio-tools

# Install Cython BEFORE building wheels
RUN pip install Cython

COPY optimized_api/requirements.txt .
COPY optimized_api/grpc_server.py .
COPY shared/setup.py .
COPY shared/model.py .
COPY shared/optimizer.pyx .
COPY shared/classifier.proto .
COPY shared/logging_config.py .
COPY shared/optimizer.pyx .
 
RUN pip wheel --no-cache-dir --wheel-dir=/wheels -r requirements.txt
RUN python setup.py build_ext --inplace

# Compile gRPC
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. classifier.proto

FROM python:3.11-slim

WORKDIR /app

ENV PYTHONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Create a non-root user for security
RUN addgroup --system nonroot && adduser --system --ingroup nonroot nonroot

COPY --from=builder /app .
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

USER nonroot

EXPOSE 50051

CMD ["python", "grpc_server.py"]