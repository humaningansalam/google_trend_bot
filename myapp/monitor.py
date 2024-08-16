import os
import logging
import psutil
from prometheus_client import Gauge
import time

class ResourceMonitor:
    def __init__(self, report_interval=5):
        self.app_cpu_usage = Gauge('app_cpu_usage', 'Description of CPU usage')
        self.app_ram_usage = Gauge('app_ram_usage', 'Description of RAM usage')
        self.pid = os.getpid()
        self.process = psutil.Process(self.pid)
        self.report_interval = report_interval
        self.monitoring = True

    def sample_and_report(self):
        try:
            cpu_usage = self.process.cpu_percent(interval=1)
            ram_usage = self.process.memory_info().rss / (1024 ** 2)  # MB 단위로 변환

            self.app_cpu_usage.set(cpu_usage)
            self.app_ram_usage.set(ram_usage)

            logging.debug(f"CPU Usage: {cpu_usage}%, RAM Usage: {ram_usage} MB")
        except Exception as e:
            logging.error(f'Error in resource monitoring: {e}')

    def start_monitor(self):
        logging.debug("Starting resource monitor")
        while self.monitoring:
            self.sample_and_report()
            time.sleep(self.report_interval)

    def stop_monitor(self):
        self.monitoring = False