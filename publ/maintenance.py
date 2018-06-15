""" Periodic maintenance tasks """

import os
import time

from . import config


class Maintenance:
    """ Container for periodic maintenance tasks """

    def __init__(self):
        self.tasks = {}

    def register(self, func, interval):
        self.tasks[func] = {'interval': interval}

    def run(self, force=False):
        now = time.time()
        for func, spec in self.tasks.items():
            if force or now >= spec.get('next_run', 0):
                func()
                spec['next_run'] = now + spec['interval']
