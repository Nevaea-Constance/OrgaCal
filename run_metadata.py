"""Record actual backend durations without changing callback contracts."""
from datetime import datetime, timezone
from functools import wraps
from time import perf_counter


def timed_state(index):
    def decorate(function):
        @wraps(function)
        def measured(*args, **kwargs):
            start = perf_counter()
            output = list(function(*args, **kwargs))
            if isinstance(output[index], dict):
                output[index] = {**output[index], 'runtime_ms': round((perf_counter() - start) * 1000, 3),
                                 'computed_at_utc': datetime.now(timezone.utc).isoformat()}
            return tuple(output)
        return measured
    return decorate
