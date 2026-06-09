"""
Sayfos Protocol — LangChain tool-call interceptor.

Wraps a LangChain tool so that every invocation first passes through
the Sayfos verification pipeline.  If adjudication returns anything
other than ALLOW the call is blocked and a BlockedActionError is raised.

Requires: pip install sayfos-sdk[langchain]
"""

from __future__ import annotations

import functools
from typing import Any, Callable, Optional

from sayfos.core.models import ActionDeclaration, IntentVerificationRequest
from sayfos.core.enums import Verdict
from sayfos.verification.pipeline import SayfosPipeline


class BlockedActionError(RuntimeError):
    """Raised when Sayfos adjudication blocks a tool call."""

    def __init__(self, token):
        self.token = token
        super().__init__(
            f"Sayfos blocked action {token.action_ref}: "
            f"verdict={token.verdict.value} reason={token.reason_code}"
        )


class SayfosLangChainInterceptor:
    """
    Interceptor that runs Sayfos verification before every LangChain tool call.

    Usage::

        interceptor = SayfosLangChainInterceptor(pipeline=SayfosPipeline())

        @interceptor.guard
        @tool
        def send_payment(amount: float, recipient: str) -> str:
            ...
    """

    def __init__(self, pipeline: Optional[SayfosPipeline] = None):
        self.pipeline = pipeline or SayfosPipeline()

    def guard(self, fn: Callable) -> Callable:
        """Decorator: intercept a LangChain tool and verify before execution."""

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            declaration = self._build_declaration(fn, args, kwargs)
            request = IntentVerificationRequest(action=declaration)
            token = self.pipeline.evaluate(request)

            if token.verdict != Verdict.ALLOW:
                raise BlockedActionError(token)

            return fn(*args, **kwargs)

        return wrapper

    @staticmethod
    def _build_declaration(
        fn: Callable,
        args: tuple,
        kwargs: dict,
    ) -> ActionDeclaration:
        return ActionDeclaration(
            actor_type="langchain_tool",
            action_type=fn.__name__,
            target=getattr(fn, "__module__", ""),
            parameters={
                "args": [str(a) for a in args],
                "kwargs": {k: str(v) for k, v in kwargs.items()},
            },
        )
