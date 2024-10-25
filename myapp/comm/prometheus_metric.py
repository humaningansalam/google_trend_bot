from prometheus_client import Summary, Counter, Gauge

class PMetrics:
    def __init__(self):
        self.request_time = Summary('request_processing_seconds', 'Time spent processing request')
        self.completed_jobs = Counter('completed_jobs', 'Number of completed jobs')
        self.get_trend_data = Counter('get_trend_data', 'Number of get trend data')
        self.errors = Counter('errors', 'Number of errors')
        self.app_cpu_usage = Gauge('app_cpu_usage', 'Description of CPU usage')
        self.app_ram_usage = Gauge('app_ram_usage', 'Description of RAM usage')