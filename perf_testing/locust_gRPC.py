from locust import task, between, events
from locust_grpc import GrpcUser

import classifier_pb2
import classifier_pb2_grpc

import random
import time
import json

# Store metrics for analysis
metrics = {
    'response_times': [],
    'errors': {},
    'status_codes': {}
}


class ClassifierUser(GrpcUser):
    """
    gRPC version of the REST user.
    Same layout and logic as your original REST locust file.
    """
    wait_time = between(0.1, 0.5)
    stub_class = classifier_pb2_grpc.ClassifierStub

    def on_start(self):
        # Same test data as your REST script
        self.reviews = [
            "Excellent product! Highly recommend.",
            "Terrible quality, waste of money.",
            "Average, nothing special.",
            "",
            "     ",
            "Great! " * 100,
            "The product is great but shipping was terrible.",
            "Good value but I had some minor problems.",
            "Fantastic features but I still feel unhappy with the performance.",
            45.6,           # invalid
        ]

    @task
    def classify(self):
        review = random.choice(self.reviews)

        # gRPC only accepts strings → convert bad types
        if not isinstance(review, str):
            review = str(review)

        request = classifier_pb2.ClassificationRequest(
            customer_id=f"user-{random.randint(1, 1000)}",
            review_text=review
        )

        start = time.time()

        try:
            response = self.stub.Classify(request)
            rt = (time.time() - start) * 1000
            metrics['response_times'].append(rt)

            # Treat as status 200
            metrics['status_codes'][200] = metrics['status_codes'].get(200, 0) + 1

            # Check response dict (same behavior as REST)
            if not response.segment:
                metrics['errors']['missing_fields'] = \
                    metrics['errors'].get('missing_fields', 0) + 1

        except Exception as e:
            rt = (time.time() - start) * 1000
            metrics['response_times'].append(rt)

            metrics['status_codes'][500] = metrics['status_codes'].get(500, 0) + 1

            err = type(e).__name__
            metrics['errors'][err] = metrics['errors'].get(err, 0) + 1


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Calculate and display key statistics"""
    print("\n" + "="*70)
    print("Perf Test Results Summary (gRPC)")
    print("="*70)

    stats = environment.stats

    if not metrics['response_times']:
        print("No response times collected!")
        return

    rts = sorted(metrics['response_times'])
    n = len(rts)

    print(f"\n KEY METRICS:")
    print(f"  Total Requests: {stats.total.num_requests:,}")
    print(f"  Total Failures: {stats.total.num_failures:,}")
    print(f"  Success Rate: {(1-stats.total.fail_ratio)*100:.2f}%")

    print(f"\n RESPONSE TIME (ms):")
    print(f"  Mean: {sum(rts)/n:.2f}")
    print(f"  Min:  {min(rts):.2f}")
    print(f"  Max:  {max(rts):.2f}")
    print(f"  P50:  {rts[int(n*0.50)]:.2f}")
    print(f"  P95:  {rts[int(n*0.95)]:.2f}")
    print(f"  P99:  {rts[int(n*0.99)]:.2f}")

    print(f"\n STATUS CODES:")
    for code, count in sorted(metrics['status_codes'].items()):
        print(f"  {code}: {count:,}")

    if metrics['errors']:
        print("\n ERRORS:")
        for err, count in metrics['errors'].items():
            print(f"  {err}: {count}")

    print("\n" + "="*70)

    # Save for report (same structure as REST)
    result_data = {
        'total_requests': stats.total.num_requests,
        'total_failures': stats.total.num_failures,
        'success_rate': (1-stats.total.fail_ratio)*100,
        'throughput_rps': stats.total.current_rps,
        'errors': metrics['errors'],
        'status_codes': metrics['status_codes'],
        'response_time_mean': sum(rts)/n,
        'response_time_min': min(rts),
        'response_time_max': max(rts),
        'response_time_p50': rts[int(n*0.50)],
        'response_time_p95': rts[int(n*0.95)],
        'response_time_p99': rts[int(n*0.99)]
    }

    with open('/tmp/results.json', 'a') as f:
        json.dump(result_data, f, indent=2)

    print("Results saved to: /tmp/results.json\n")
