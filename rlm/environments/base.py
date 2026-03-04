# rlm/environments/base.py - Base Environment Interface

from abc import ABC, abstractmethod
from typing import Dict, Any

class ExecutionResult:
    """
    Represents the result of code execution in an environment.
    """
    def __init__(self, stdout: str = "", stderr: str = "", exit_code: int = 0, error: Optional[str] = None):
        self.stdout = stdout
        self.stderr = stderr
        self.exit_code = exit_code
        self.error = error # General error message if execution itself failed (e.g., environment not available)

    def is_success(self) -> bool:
        """Checks if the execution was successful (exit code 0 and no environment error)."""
        return self.exit_code == 0 and self.error is None

    def __str__(self):
        status = "SUCCESS" if self.is_success() else "FAILED"
        output = f"Exit Code: {self.exit_code}\n"
        if self.stdout:
            output += f"STDOUT:\n{self.stdout}\n"
        if self.stderr:
            output += f"STDERR:\n{self.stderr}\n"
        if self.error:
            output += f"ERROR: {self.error}\n"
        return f"Execution {status}:\n{output}"

class BaseEnvironment(ABC):
    """
    Abstract base class for all RLMClaw execution environments.
    Defines the interface for running code in isolated contexts.
    """

    def __init__(self, **kwargs):
        """
        Initializes the environment with specific configuration.
        """
        pass

    @abstractmethod
    def execute_code(self, code: str, timeout: int = 30) -> ExecutionResult:
        """
        Executes the given Python code within the environment.

        Args:
            code: The Python code to execute.
            timeout: Maximum time in seconds to wait for code execution.

        Returns:
            An ExecutionResult object containing stdout, stderr, and exit code.
        """
        pass

    @abstractmethod
    def setup(self) -> bool:
        """
        Performs any necessary setup for the environment (e.g., starting a container).
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def cleanup(self) -> bool:
        """
        Performs any necessary cleanup for the environment.
        Returns True on success, False otherwise.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Checks if the environment is currently available and ready for use.
        """
        pass
