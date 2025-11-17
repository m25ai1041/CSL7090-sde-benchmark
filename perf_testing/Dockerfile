# Base image with Locust preinstalled
FROM locustio/locust:latest

# Set working directory inside the container
WORKDIR /tmp

# Copy your test file into the container
COPY locust_REST.py /tmp/locust_REST.py
COPY locust_gRPC.py /tmp/locust_gRPC.py
COPY classifier.proto .

RUN pip install --upgrade pip setuptools grpcio grpcio-tools
RUN python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. classifier.proto

# Expose Locust web UI port
EXPOSE 8089

# Expose worker/master port
EXPOSE 5557
EXPOSE 5558

# Sleep forever so the container stays alive
CMD ["sleep", "infinity"]