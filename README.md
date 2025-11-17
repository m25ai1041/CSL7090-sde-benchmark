# Microservice Performance Evaluation: REST vs. gRPC

This is a CSL7090 course project to implement and evaluate the performance comparison between two microservice communication protocols: **REST (HTTP/JSON)** and **gRPC (Protobuf)**.

This project builds two distinct services that perform the same core task but are built with different technology stacks. Both are containerized with Docker and designed to be deployed in a Kubernetes cluster for performance testing.



---

## Inspiration

This project is inspired from findings of the following research paper, focusing on the performance comparison between REST and gRPC.

* **Paper:** Performance Evaluation of Microservices Communication with REST, GraphQL, and gRPC
* **Journal:** International Journal of Electronics and Telecommunication

---

## Contents

* [Project Overview](#project-overview)
* [Architecture](#architecture)
* [How to Run the Experiment](#how-to-run-the-experiment)
    * [Prerequisites](#prerequisites)
    * [Step 1: Build Docker Images](#step-1-build-docker-images)
    * [Step 2: Deploy to Kubernetes](#step-2-deploy-to-kubernetes)
    * [Step 3: Run Performance Tests](#step-3-run-performance-tests)
* [Key Files in This Project](#key-files-in-this-project)
* [Contributors](#contributors)

---

## Project Overview

We are comparing two different implementations of a "Customer Review Classifier" service.

### 1. The "Baseline" Service (`baseline_api`)

This service represents a standard, common approach to building microservices.

* **Protocol:** REST (HTTP)
* **Server:** Flask + Gunicorn
* **Preprocessing:** A pure Python function (`preprocessor.py`).
* **Task:**
    1.  Receives a JSON request.
    2.  Cleans the text using the pure Python function.
    3.  Runs a mock ML inference model.
    4.  Inserts the new classification result into PostgreSQL table, Retrieves the most recent 5 classification records.
    5.  Return a JSON response with summarized history for the response, limited to the two most recent entries.

### 2. The "Optimized" Service (`optimized_api`)

This service is optimized for high performance by changing both the protocol and the code.

* **Protocol:** gRPC
* **Server:** Python `grpc_server`
* **Preprocessing:** A **Cython-compiled** C-extension (`optimizer.pyx`).
* **Task:**
    1.  Receives a gRPC (Protobuf) request.
    2.  Cleans the text using the **Cython-compiled function**.
    3.  Runs the *same* mock ML inference model.
    4.  Runs the *same*  db operations.
    4.  Returns a gRPC (Protobuf) response with *same* details.

---

## Architecture

This project is structured as a collection of independent microservices.


* `services/baseline_api/`: The Flask/Gunicorn REST API.
* `services/optimized_api/`: The gRPC/Cython API.
* `services/event_consumer/`: A Kafka consumer (for a full event-driven architecture). #WIP
* `shared/`: Contains the files used to build the optimized service, including `optimizer.pyx` (Cython source) and `classifier.proto` (gRPC contract).
* `load_testing/locust_REST.py`: Test script for REST micro-service.
* `load_testing/locust_gRPC.py`: Test script for gRPC micro-service.

---

## How to Run the Experiment

### Prerequisites

You must have the following tools installed and configured:

* [Docker](https://www.docker.com/)
* [Kubernetes](https://kubernetes.io/docs/setup/) (e.g., Minikube)
* [kubectl](https://kubernetes.io/docs/tasks/tools/)
* [Helm](https://helm.sh/docs/intro/install/)
* [Strimzi](https://strimzi.io/) for deploying the Kafka operator and Kafka cluster (for the `event_consumer` service).
* [Bitnami PostgreSQL](https://bitnami.com/stack/postgresql/helm)

### Step 1: Build Docker image and push to minikube

From the root of the service.
```bash
# Build the REST API
docker build  -f baseline_api/Dockerfile -t baseline-api:latest .
minikube image load baseline-api:latest

```



### Step 2: Deploy to Kubernetes

All micro services will be running in sde-benchmark namespace.
Deploy service using their Helm charts.
```bash
# Deploy the Baseline REST API and its Postgres DB
helm install baseline-api ./baseline-api -n sde-benchmark

```

### Step 3: Run Performance Tests

We will run the tests from inside the cluster to get the most accurate results, eliminating network bottlenecks.

#### A. Deploy the Test Pod

Build and deploy the Locust pod that we can exec into.
```bash
docker build  -f Dockerfile -t perf-locust:latest .
minikube image load perf-locust:latest
kubectl apply -f locust.yaml
```

#### B. Test the REST API - Baseline, similarly for - Optimized

Run the Locust test against the baseline-api service.
```bash
# Run the test
kubectl exec -it perf-locust-sde-benchmark -n sde-benchmark -- locust \
  -f /tmp/locust_REST.py \
  --headless \
  --users 25 \
  --spawn-rate 5 \
  --run-time 5m \
  --host http://baseline-api.sde-benchmark.svc.cluster.local:8000  \
  --html /tmp/baseline_REST.html
  --csv /tmp/baseline_REST

# Copy the report to your local machine
kubectl cp sde-benchmark/perf-locust-sde-benchmark:/tmp ./results
```

Now you can open html files in your browser.
This script will print statistics (RPS, Latency, etc.) directly to console.

---

## Key Files in This Project

* `services/baseline_api/rest_server.py`: The Flask server, which performs inference and writes to Postgres.
* `services/optimized_api/grpc_server.py`: The gRPC server, which imports and uses the Cython module.
* `shared/classifier.proto`: The gRPC "contract" that defines the API.
* `shared/optimizer.pyx`: The Cython source code for the optimized preprocessor.
* `shared/setup.py`: The build script used to compile the Cython code.
* `*/Dockerfile`: A multi-stage Dockerfile for each microservice.

---

## Contributors

* Muthumula Naresh (M25AI1026)
* Rami Reddy Elluru (M25AI1013)
* Rakshith Pai (M25AI1041)
