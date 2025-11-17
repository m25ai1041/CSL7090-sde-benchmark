from locust import User, task, between, events
import grpc
import time
import json
import random
import os
from datetime import datetime
import classifier_pb2
import classifier_pb2_grpc


class GrpcClient:
    def __init__(self, host):
        self.channel = grpc.insecure_channel(host)
        self.stub = classifier_pb2_grpc.ClassifierStub(self.channel)

    def classify(self, payload):
        request = classifier_pb2.ClassificationRequest(
            customer_id=payload["customer_id"],
            review_text=payload["review_text"]
        )
        return self.stub.Classify(request, timeout=5)


metrics = {
    "response_times": [],
    "errors": {},
    "status_codes": {}
}


class GrpcClassifierUser(User):
    wait_time = between(0.1, 0.5)

    def on_start(self):
        self.client = GrpcClient(self.host)

        self.reviews = [
            "Excellent product! Highly recommend.",
            "Great quality and fast shipping!",
            "Love it! Will buy again.",
            "Terrible quality, waste of money.",
            "Very disappointed with this purchase.",
            "Do not buy! Complete garbage.",
            "Average, nothing special.",
            "It's okay, does what it's supposed to.",
            "Meh, could be better.",
            "The product is great but shipping was terrible.",
            "Good value but I had some minor problems.",
            "Fantastic features but I still feel unhappy.",
            "",
            "     ",
            "a",
            "Great! " * 100,
            "🎉😊👍",
            "EXCELLENT PRODUCT!!!",
            "45.6",
            "12345",
        ]

    @task
    def classify(self):
        payload = {
            "customer_id": f"user-{random.randint(1, 1000)}",
            "review_text": random.choice(self.reviews)
        }

        start = time.time()

        try:
            response = self.client.classify(payload)
            latency = (time.time() - start) * 1000

            # Locust success event
            events.request.fire(
                request_type="gRPC",
                name="Classify",
                response_time=latency,
                response_length=0,
                exception=None
            )

            # Metrics
            metrics["response_times"].append(latency)
            metrics["status_codes"]["200"] = metrics["status_codes"].get("200", 0) + 1

            # Field validation
            if not (response.segment and response.confidence >= 0):
                metrics["errors"]["missing_fields"] = metrics["errors"].get("missing_fields", 0) + 1

        except grpc.RpcError as e:
            latency = (time.time() - start) * 1000

            # Locust failure event
            events.request.fire(
                request_type="gRPC",
                name="Classify",
                response_time=latency,
                response_length=0,
                exception=e
            )

            metrics["response_times"].append(latency)
            code_obj = e.code()

            # Best-case: direct integer value
            if hasattr(code_obj, "value") and isinstance(code_obj.value, int):
                status = code_obj.value
            else:
                try:
                    status = int(str(code_obj).split("(")[1].split(",")[0])
                except:
                    status = -1

            status = str(status)

            metrics["status_codes"][status] = metrics["status_codes"].get(status, 0) + 1
            metrics["errors"][str(e.code())] = metrics["errors"].get(str(e.code()), 0) + 1


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    print("\n" + "="*70)
    print("Performance Test Starting (gRPC API)")
    print("="*70)
    print(f"Target: {environment.host}")
    print(f"Start Time: {datetime.now().isoformat()}")
    print("="*70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):

    print("\n" + "="*70)
    print("PERFORMANCE TEST RESULTS - gRPC API")
    print("="*70)

    stats = environment.stats

    if not metrics["response_times"]:
        print(" No response times collected!")
        return

    rts = sorted(metrics["response_times"])
    n = len(rts)

    print(f"\n KEY METRICS:")
    print(f"  Total Requests: {stats.total.num_requests:,}")
    print(f"  Total Failures: {stats.total.num_failures:,}")
    print(f"  Success Rate: {(1 - stats.total.fail_ratio) * 100:.2f}%")
    print(f"  Throughput: {stats.total.current_rps:.2f} req/sec")

    print(f"\n RESPONSE TIME (ms):")
    print(f"  Mean: {stats.total.avg_response_time:.2f}")
    print(f"  Min: {stats.total.min_response_time:.2f}")
    print(f"  Max: {stats.total.max_response_time:.2f}")
    print(f"  P50: {rts[int(n * 0.50)]:.2f}")
    print(f"  P90: {rts[int(n * 0.90)]:.2f}")
    print(f"  P95: {rts[int(n * 0.95)]:.2f}")
    print(f"  P99: {rts[int(n * 0.99)]:.2f}")

    print(f"\n STATUS CODES:")
    # Safe sorting: numeric first, unknown codes last
    def sort_key(kv):
        code = kv[0]
        return int(code) if code.lstrip("-").isdigit() else 9999

    for code, count in sorted(metrics["status_codes"].items(), key=sort_key):
        percent = (count / stats.total.num_requests * 100) if stats.total.num_requests > 0 else 0
        print(f"  {code}: {count:,} ({percent:.1f}%)")

    if metrics["errors"]:
        print(f"\n ERRORS:")
        for err, count in metrics["errors"].items():
            print(f"  {err}: {count}")

    print("\n" + "="*70)
    results_file = "/tmp/results_gRPC.json"
    all_results = []

    if os.path.exists(results_file):
        try:
            with open(results_file, "r") as f:
                all_results = json.load(f)
        except:
            all_results = []

    result_data = {
        "test_type": "GRPC_API",
        "timestamp": datetime.now().isoformat(),
        "target_host": environment.host,
        "total_requests": stats.total.num_requests,
        "total_failures": stats.total.num_failures,
        "success_rate": (1 - stats.total.fail_ratio) * 100,
        "throughput_rps": stats.total.current_rps,
        "response_time_mean": stats.total.avg_response_time,
        "response_time_min": stats.total.min_response_time,
        "response_time_max": stats.total.max_response_time,
        "response_time_p50": rts[int(n * 0.50)],
        "response_time_p90": rts[int(n * 0.90)],
        "response_time_p95": rts[int(n * 0.95)],
        "response_time_p99": rts[int(n * 0.99)],
        "status_codes": metrics["status_codes"],
        "errors": metrics["errors"]
    }

    all_results.append(result_data)

    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"\n Results saved to: {results_file}\n")
