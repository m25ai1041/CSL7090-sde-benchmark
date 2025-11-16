# Base image with Locust preinstalled
FROM locustio/locust:latest

# Set working directory inside the container
WORKDIR /tmp

# Copy your test file into the container
COPY locust.py /tmp/locust.py

# Expose Locust web UI port
EXPOSE 8089

# Expose worker/master port
EXPOSE 5557
EXPOSE 5558

# Sleep forever so the container stays alive
CMD ["sleep", "infinity"]