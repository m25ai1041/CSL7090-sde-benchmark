from locust import HttpUser, task, between, events
import json
import random
import time
from datetime import datetime

# Store metrics for analysis
metrics = {
    'response_times': [],
    'errors': {},
    'status_codes': {}
}

class ClassifierUser(HttpUser):
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        # Diverse test data for realistic testing
        self.reviews = [
            # Normal reviews
            "Excellent product! Highly recommend.",
            "Terrible quality, waste of money.",
            "Average, nothing special.",
            "",                      # empty string
            "     ",                 # whitespace only
            "Great! " * 100,         # very long repeated text
            # Mixed sentiment
            "The product is great but shipping was terrible.",
            "Good value but I had some minor problems.",
            "Fantastic features but I still feel unhappy with the performance.",
            45.6,              
            ]
    
    @task
    def classify(self):
        payload = {
            "customer_id": f"user-{random.randint(1, 1000)}",
            "review_text": random.choice(self.reviews)
        }
        
        start = time.time()
        response = self.client.post("/classify", json=payload, name="POST /classify")
        
        rt = (time.time() - start) * 1000
        metrics['response_times'].append(rt)
        metrics['status_codes'][response.status_code] = \
            metrics['status_codes'].get(response.status_code, 0) + 1
        
        if response.status_code == 200:
            try:
                result = response.json()
                if 'segment' not in result:
                    metrics['errors']['missing_classification'] = \
                        metrics['errors'].get('missing_classification', 0) + 1
            except json.JSONDecodeError:
                metrics['errors']['json_error'] = \
                    metrics['errors'].get('json_error', 0) + 1

@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Calculate and display key statistics"""
    print("\n" + "="*70)
    print("Perf Test Results Summary (REST)")
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
    print(f"  Throughput: {stats.total.current_rps:.2f} req/sec")
    
    print(f"\n RESPONSE TIME (ms):")
    print(f"  Mean: {stats.total.avg_response_time:.2f}")
    print(f"  Min: {stats.total.min_response_time:.2f}")
    print(f"  Max: {stats.total.max_response_time:.2f}")
    if n > 0:
        print(f"  P50 (Median): {rts[int(n*0.50)]:.2f}")
        print(f"  P95: {rts[int(n*0.95)]:.2f}")
        print(f"  P99: {rts[int(n*0.99)]:.2f}")
    
    print(f"\n STATUS CODES:")
    for code, count in sorted(metrics['status_codes'].items()):
        print(f"  {code}: {count:,} ({count/stats.total.num_requests*100:.1f}%)")
    
    if metrics['errors']:
        print(f"\n ERRORS:")
        for err, count in metrics['errors'].items():
            print(f"  {err}: {count}")
    
    print("\n" + "="*70)
    
    # Save for report
    result_data = {
        'total_requests': stats.total.num_requests,
        'total_failures': stats.total.num_failures,
        'success_rate': (1-stats.total.fail_ratio)*100,
        'throughput_rps': stats.total.current_rps,
        'response_time_mean': stats.total.avg_response_time,
        'response_time_min': stats.total.min_response_time,
        'response_time_max': stats.total.max_response_time,
        'status_codes': metrics['status_codes'],
        'errors': metrics['errors']
    }
    
    if n > 0:
        result_data['response_time_p50'] = rts[int(n*0.50)]
        result_data['response_time_p95'] = rts[int(n*0.95)]
        result_data['response_time_p99'] = rts[int(n*0.99)]
    
    with open('/tmp/results.json', 'a') as f:
        json.dump(result_data, f, indent=2)
    print("Results saved to: /tmp/results.json\n")