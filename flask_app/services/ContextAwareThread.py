from flask import current_app
import threading

class ContextAwareThread(threading.Thread):
    def __init__(self, target, args):
        self.target = target
        self.args = args
        self.app_context = current_app._get_current_object()
        super().__init__()

    def run(self):
        with self.app_context.app_context():
            self.target(*self.args)
