from locust import HttpUser, task, between, events
import json
import random
import time
import os
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
            # Positive sentiment
            "Excellent product! Highly recommend.",
            "Great quality and fast shipping!",
            "Love it! Will buy again.",
            
            # Negative sentiment
            "Terrible quality, waste of money.",
            "Very disappointed with this purchase.",
            "Do not buy! Complete garbage.",
            
            # Neutral sentiment
            "Average, nothing special.",
            "It's okay, does what it's supposed to.",
            "Meh, could be better.",
            
            # Mixed sentiment
            "The product is great but shipping was terrible.",
            "Good value but I had some minor problems.",
            "Fantastic features but I still feel unhappy with the performance.",
            
            # Edge cases
            "",                      # Empty string
            "     ",                 # Whitespace only
            "a",                     # Single character
            "Great! " * 100,         # Very long repeated text (10000+ chars)
            "🎉😊👍",                 # Emojis
            "EXCELLENT PRODUCT!!!",  # All caps
            "45.6",                  # Numeric string
            "12345",                 # Pure numbers
        ]
    
    @task
    def classify(self):
        payload = {
            "customer_id": f"user-{random.randint(1, 1000)}",
            "review_text": random.choice(self.reviews)
        }
        
        start = time.time()
        response = self.client.post("/classify", json=payload, name="POST /classify", timeout=30)
        
        rt = (time.time() - start) * 1000
        metrics['response_times'].append(rt)
        metrics['status_codes'][response.status_code] = \
            metrics['status_codes'].get(response.status_code, 0) + 1
        
        # Validate response for 200 OK
        if response.status_code == 200:
            try:
                result = response.json()
                
                # Check for required fields (based on your Flask API)
                required_fields = ['classification', 'confidence', 'customer_id']
                for field in required_fields:
                    if field not in result:
                        metrics['errors'][f'missing_{field}'] = \
                            metrics['errors'].get(f'missing_{field}', 0) + 1
                
                # Validate confidence range
                if 'confidence' in result:
                    conf = result['confidence']
                    if not (0 <= conf <= 1):
                        metrics['errors']['invalid_confidence'] = \
                            metrics['errors'].get('invalid_confidence', 0) + 1
                
            except json.JSONDecodeError:
                metrics['errors']['json_error'] = \
                    metrics['errors'].get('json_error', 0) + 1
        
        elif response.status_code >= 400:
            # Track specific error types
            error_type = f'http_{response.status_code}'
            metrics['errors'][error_type] = \
                metrics['errors'].get(error_type, 0) + 1


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts - log configuration."""
    print("\n" + "="*70)
    print("Performance Test Starting (REST API)")
    print("="*70)
    print(f"Target: {environment.host}")
    print(f"Start Time: {datetime.now().isoformat()}")
    print("="*70 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Calculate and display key statistics"""
    print("\n" + "="*70)
    print("PERFORMANCE TEST RESULTS - REST API")
    print("="*70)
    
    stats = environment.stats
    
    if not metrics['response_times']:
        print(" No response times collected!")
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
        print(f"  P90: {rts[int(n*0.90)]:.2f}")
        print(f"  P95: {rts[int(n*0.95)]:.2f}")
        print(f"  P99: {rts[int(n*0.99)]:.2f}")
    
    print(f"\n STATUS CODES:")
    for code, count in sorted(metrics['status_codes'].items()):
        percentage = (count/stats.total.num_requests*100) if stats.total.num_requests > 0 else 0
        print(f"  {code}: {count:,} ({percentage:.1f}%)")
    
    if metrics['errors']:
        print(f"\n ERRORS:")
        for err, count in metrics['errors'].items():
            print(f"  {err}: {count}")
    
    print("\n" + "="*70)
    
    # Prepare results for saving
    result_data = {
        'test_type': 'REST_API',
        'timestamp': datetime.now().isoformat(),
        'target_host': environment.host,
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
        result_data['response_time_p90'] = rts[int(n*0.90)]
        result_data['response_time_p95'] = rts[int(n*0.95)]
        result_data['response_time_p99'] = rts[int(n*0.99)]
    
    # Save results (append to list for multiple test runs)
    results_file = '/tmp/results_REST.json'
    all_results = []
    
    if os.path.exists(results_file):
        try:
            with open(results_file, 'r') as f:
                all_results = json.load(f)
        except:
            all_results = []
    
    all_results.append(result_data)
    
    with open(results_file, 'w') as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n Results saved to: {results_file}\n")