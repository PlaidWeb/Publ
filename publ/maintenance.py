""" Periodic maintenance tasks """

import time
import typing


class Maintenance:
    """ Container for periodic maintenance tasks """

    def __init__(self, app: typing.Any):
        self.app = app
        self.tasks: typing.Dict[typing.Callable[[], None],
                                typing.Dict[str, float]] = {}

    def register(self, func: typing.Callable[[], None], interval: float):
        """ Registers a task to run periodically """
        self.tasks[func] = {'interval': interval}

    def run(self, force: bool = False):
        """ Run all pending tasks; 'force' will run all tasks whether they're
        pending or not. """
        with self.app.app_context():
            now = time.time()
            for func, spec in self.tasks.items():
                if force or now >= spec.get('next_run', 0):
                    func()
                    spec['next_run'] = now + spec['interval']
