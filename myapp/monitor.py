import os
import logging
import psutil
import threading
class ResourceMonitor:
    def __init__(self, pmetrics, report_interval=5):
        self.pmetrics = pmetrics
        self.pid = os.getpid()
        self.process = psutil.Process(self.pid)
        self.report_interval = report_interval
        self.monitoring = True

    def _schedule_report(self):
        if not self.monitoring:
            return
        self.sample_and_report()
        threading.Timer(self.report_interval, self._schedule_report).start()

    def sample_and_report(self):
        try:
            cpu_usage = self.process.cpu_percent(interval=1)
            ram_usage = self.process.memory_info().rss / (1024 ** 2)  # Convert to MB

            self.pmetrics.app_cpu_usage.set(cpu_usage)
            self.pmetrics.app_ram_usage.set(ram_usage)

            logging.debug(f"CPU Usage: {cpu_usage}%, RAM Usage: {ram_usage} MB")
        except Exception as e:
            logging.error(f'Error in resource monitoring: {e}')

    def start_monitor(self):
        logging.debug("Starting resource monitor")
        self.monitoring = True
        self._schedule_report()

    def stop_monitor(self):
        self.monitoring = False