# --- STAGE 1: The "Builder" ---
# This stage is identical to the optimised-api builder.
# It compiles all shared code.
FROM python:3.11-slim as builder
WORKDIR /app

RUN pip install --no-cache-dir cython grpcio-tools setuptools

COPY shared/setup.py .
COPY shared/optimizer.pyx .
COPY shared/classifier.proto .

# 1. Compile Cython
RUN python setup.py build_ext --inplace

# 2. Compile gRPC
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. classifier.proto


# --- STAGE 2: The "Final" Image ---
# This is the slim, production image for the consumer
FROM python:3.11-slim
WORKDIR /app

ENV PYTHONUNBUFFERED 1

# --- 1. Install Runtime Dependencies ---
# This service has different requirements
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# --- 2. Copy Shared Logic ---
COPY ../../shared/logging_config.py .

# --- 3. Copy Compiled Code from "Builder" Stage ---
# It needs the gRPC files to be a gRPC *client*
COPY --from=builder /app/classifier_pb2.py .
COPY --from=builder /app/classifier_pb2_grpc.py .
# It also needs the Cython file if it does any pre-processing
COPY --from=builder /app/*.so .

# --- 4. Copy Service-Specific Code ---
COPY src/event_consumer.py .

# Run the app
CMD ["python", "event_consumer.py"]