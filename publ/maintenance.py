""" Periodic maintenance tasks """

import time


class Maintenance:
    """ Container for periodic maintenance tasks """

    def __init__(self):
        self.tasks = {}

    def register(self, func, interval):
        """ Registers a task to run periodically """
        self.tasks[func] = {'interval': interval}

    def run(self, force=False):
        """ Run all pending tasks; 'force' will run all tasks whether they're
        pending or not. """
        now = time.time()
        for func, spec in self.tasks.items():
            if force or now >= spec.get('next_run', 0):
                func()
                spec['next_run'] = now + spec['interval']
