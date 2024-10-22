from fluent import sender
import time

class FLogger:
    def __init__(self, host, port=24224):
        self.fluent = sender.FluentSender('crawling', host=host, port=port)

    def log(self, tag, data):
        self.fluent.emit_with_time(tag, int(time.time()), data)