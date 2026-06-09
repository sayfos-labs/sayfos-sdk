"""
Sayfos Protocol — Dify plugin/tool interceptor.

Wraps a Dify tool or plugin callable so that every invocation
first passes through the Sayfos verification pipeline.

Dify tools are typically registered via plugin manifests and
executed through a sandboxed callable.  This interceptor can
be used as a decorator or as a callable wrapper.

Requires: pip install sayfos-sdk dify-plugin-sdk (if available)
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from sayfos.core.models import ActionDeclaration, IntentVerificationRequest
from sayfos.core.enums import Verdict
from sayfos.verification.pipeline import ConfigurablePipeline


class BlockedActionError(RuntimeError):
    """Raised when Sayfos adjudication blocks a tool call."""

    def __init__(self, token):
        self.token = token
        super().__init__(
            f"Sayfos blocked action {token.action_ref}: "
            f"verdict={token.verdict.value} reason={token.reason_code}"
        )


class SayfosDifyInterceptor:
    """
    Interceptor for Dify tool/plugin invocations.

    Usage::

        interceptor = SayfosDifyInterceptor()

        # As decorator
        @interceptor.guard
        def dify_tool_handler(params: dict) -> dict:
            ...

        # As callable wrapper (for plugin manifests)
        guarded = interceptor.wrap(my_dify_tool_callable)
    """

    def __init__(self, pipeline: Optional[ConfigurablePipeline] = None):
        self.pipeline = pipeline or ConfigurablePipeline()

    def guard(self, fn: Callable) -> Callable:
        """Decorator for Dify tool handlers."""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            declaration = self._build_declaration(fn, args, kwargs)
            request = IntentVerificationRequest(action=declaration)
            token = self.pipeline.evaluate(request)

            if token.verdict != Verdict.ALLOW:
                raise BlockedActionError(token)

            return fn(*args, **kwargs)

        return wrapper

    def wrap(self, fn: Callable) -> Callable:
        """Wrap an existing callable (non-decorator pattern)."""
        return self.guard(fn)

    @staticmethod
    def _build_declaration(
        fn: Callable,
        args: tuple,
        kwargs: dict,
    ) -> ActionDeclaration:
        return ActionDeclaration(
            actor_type="dify_plugin",
            action_type=getattr(fn, "__name__", "unknown_tool"),
            target=getattr(fn, "__module__", ""),
            parameters={
                "args": [str(a) for a in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()},
            },
        )
