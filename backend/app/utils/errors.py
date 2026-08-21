"""Domain-specific exception hierarchy.

These exceptions are used to distinguish transient/expected failures
(which may be retried) from unexpected programming errors.
"""

from __future__ import annotations


class ResearchPilotError(Exception):
    """Base class for all ResearchPilot errors."""

    #: Whether this error is safe to retry (transient by nature).
    retryable: bool = False
    #: HTTP status code used when this error surfaces at the API boundary.
    http_status: int = 500

    def __init__(self, message: str, *, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail

    @property
    def error_type(self) -> str:
        return self.__class__.__name__


class ToolError(ResearchPilotError):
    """A tool failed to execute."""

    retryable = True
    http_status = 502


class ToolTimeoutError(ToolError):
    """A tool exceeded its bounded timeout."""

    retryable = True
    http_status = 504


class LLMError(ResearchPilotError):
    """An LLM call failed."""

    retryable = True
    http_status = 502


class ValidationError(ResearchPilotError):
    """Input or structured-output validation failed. Never retried."""

    retryable = False
    http_status = 400


class ExternalServiceError(ResearchPilotError):
    """An external service (OpenAI, Langfuse) returned an error."""

    retryable = True
    http_status = 502
