import functools
from langfuse import observe as _lf_observe

def trace(name: str):
    def decorator(func):
        @functools.wraps(func)
        @_lf_observe(name=name)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        return wrapper
    return decorator