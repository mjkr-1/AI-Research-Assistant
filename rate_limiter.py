import json
import os
import threading
import time
from collections import deque


class RateLimiter:
    def __init__(self, max_calls, period, state_file=None):
        self.max_calls = max_calls
        self.period = period
        self.state_file = state_file
        self._timestamps = deque()
        self._lock = threading.Lock()
        if state_file:
            self._load()

    def _load(self):
        if not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                timestamps = json.load(f)
            now = time.time()
            self._timestamps = deque(
                t for t in timestamps if now - t < self.period
            )
        except (json.JSONDecodeError, OSError, TypeError):
            self._timestamps = deque()

    def _persist(self):
        if not self.state_file:
            return
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(list(self._timestamps), f)
        except OSError:
            pass

    def _prune(self):
        now = time.time()
        while self._timestamps and now - self._timestamps[0] >= self.period:
            self._timestamps.popleft()

    def try_acquire(self):
        with self._lock:
            self._prune()
            if len(self._timestamps) >= self.max_calls:
                return False
            self._timestamps.append(time.time())
            self._persist()
            return True

    def wait(self, poll_interval=1.0):
        while not self.try_acquire():
            time.sleep(poll_interval)

    @property
    def remaining(self):
        with self._lock:
            self._prune()
            return max(0, self.max_calls - len(self._timestamps))

    def __enter__(self):
        self.wait()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


if __name__ == "__main__":
    daily = RateLimiter(max_calls=200, period=86400, state_file="rate_state.json")
    print(f"Daily requests remaining: {daily.remaining}")
    with daily:
        print("Slot acquired")
