from prometheus_client import Summary, Counter

class PMetrics:
    def __init__(self):
        self.request_time = Summary('request_processing_seconds', 'Time spent processing request')
        self.completed_jobs = Counter('completed_jobs', 'Number of completed jobs')
        self.get_trend_data = Counter('get_trend_data', 'Number of get trend data')
        self.errors = Counter('errors', 'Number of errors')