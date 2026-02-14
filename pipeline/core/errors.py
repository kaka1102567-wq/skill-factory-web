"""Custom exceptions for the pipeline."""


class PipelineError(Exception):
    """Base pipeline exception."""
    pass


class PhaseError(PipelineError):
    def __init__(self, phase_id: str, message: str, retryable: bool = True):
        self.phase_id = phase_id
        self.retryable = retryable
        super().__init__(f"[{phase_id}] {message}")


class SeekersError(PipelineError):
    pass


class ClaudeAPIError(PipelineError):
    def __init__(self, message: str, status_code: int = 0, retryable: bool = True):
        self.status_code = status_code
        self.retryable = retryable
        super().__init__(message)


class ConfigError(PipelineError):
    pass


class PhaseNotImplementedError(PipelineError):
    """Phase not yet implemented — use mock fallback."""
    pass
