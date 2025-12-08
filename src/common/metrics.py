#src/common/metrics.py

from his_mon import BaseMetrics
from prometheus_client import Summary, Counter

class BotMetrics(BaseMetrics):
    def __init__(self):
        super().__init__(app_name="trends_bot")
        
        # 커스텀 메트릭
        self.request_time = Summary('request_processing_seconds', 'Time spent processing request')
        self.completed_jobs = Counter('completed_jobs_total', 'Number of completed jobs')
        self.get_trend_data = Counter('get_trend_data_total', 'Number of get trend data')

metrics = BotMetrics()