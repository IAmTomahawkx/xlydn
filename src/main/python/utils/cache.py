"""
Licensed under the Open Software License version 3.0
"""
import time

class TimedCache(dict):
    def __init__(self, seconds: int)-> None:
        self._timeout = seconds
        super().__init__()

    def _verify_cache(self):
        now = time.monotonic()
        to_delete = [v for (v, (i, t)) in self.items() if now > (t + self._timeout)]
        for item in to_delete:
            del self[item]

    def __contains__(self, item):
        self._verify_cache()
        return super().__contains__(item)

    def __getitem__(self, item):
        self._verify_cache()
        v = super().__getitem__(item)
        return v[0]

    def __setitem__(self, key, value):
        super().__setitem__(key, (value, time.monotonic()))

