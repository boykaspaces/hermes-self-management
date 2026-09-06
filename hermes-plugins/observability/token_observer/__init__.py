"""Hermes token observer plugin entry point.

The implementation deliberately lives in ``observer.py`` so the collector can
be tested without importing Hermes itself.
"""

from .observer import get_observer
from .runtime_instrumentation import install_runtime_instrumentation


def register(ctx) -> None:
    install_runtime_instrumentation()
    observer = get_observer()
    ctx.register_hook("pre_api_request", observer.on_pre_api_request)
    ctx.register_hook("post_api_request", observer.on_post_api_request)
    ctx.register_hook("api_request_error", observer.on_api_request_error)
    ctx.register_hook("post_tool_call", observer.on_post_tool_call)
