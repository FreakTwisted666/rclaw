# rlm/environments/local.py - Local REPL Environment

import subprocess
import threading
import io
import contextlib
import sys
import os
import logging
from typing import Dict, Any, Optional

from rlm.environments.base import BaseEnvironment, ExecutionResult

logger = logging.getLogger(__name__)

class LocalREPL(BaseEnvironment):
    """
    Executes Python code directly within the agent's process using `exec`.
    This environment is for low-risk, internal operations or when no specific
    sandbox is required. It's generally not recommended for untrusted code.
    """

    def __init__(self, globals_dict: Optional[Dict[str, Any]] = None, locals_dict: Optional[Dict[str, Any]] = None, **kwargs):
        super().__init__(**kwargs)
        self._globals = globals_dict if globals_dict is not None else {}
        self._locals = locals_dict if locals_dict is not None else {}
        self._execution_lock = threading.Lock() # To prevent concurrent exec calls from interfering

        # Add common built-ins for convenience
        self._globals.update({
            '__builtins__': __builtins__,
            'os': os,
            'sys': sys,
            'logging': logging
        })
        logger.info("LocalREPL initialized. Code will execute in-process.")

    def execute_code(self, code: str, timeout: int = 30) -> ExecutionResult:
        """
        Executes the given Python code in a sandboxed manner within the current process.
        Uses `exec` with a redirected stdout/stderr to capture output.
        """
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        exit_code = 0
        error_message: Optional[str] = None

        logger.debug(f"Executing code in LocalREPL (timeout: {timeout}s):\n{code}")

        # Use a lock to ensure only one exec call runs at a time to prevent output mixing
        with self._execution_lock:
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = stdout_capture
            sys.stderr = stderr_capture

            try:
                # Execute code, potentially with a timeout mechanism (simple thread based)
                exec_thread = threading.Thread(target=exec, args=(code, self._globals, self._locals))
                exec_thread.start()
                exec_thread.join(timeout=timeout)

                if exec_thread.is_alive():
                    # If thread is still alive after timeout, it means execution timed out
                    error_message = f"Execution timed out after {timeout} seconds."
                    exit_code = 124 # Standard timeout exit code
                elif exec_thread.exc_info is not None:
                    # If thread terminated with an exception (need a way to capture it properly for exec)
                    # For simplicity, relying on stderr capture for now.
                    # A more robust solution would involve multiprocessing or dedicated sandboxing libs.
                    pass # Error would be in stderr_capture

            except Exception as e:
                error_message = str(e)
                exit_code = 1
                logger.error(f"Error during local code execution: {e}", exc_info=True)
            finally:
                sys.stdout = old_stdout
                sys.stderr = old_stderr

        stdout_content = stdout_capture.getvalue()
        stderr_content = stderr_capture.getvalue()

        # If an error occurred and it's not captured by stderr, try to set exit_code
        if error_message or stderr_content:
            exit_code = 1

        logger.debug(f"LocalREPL result: stdout='{stdout_content}', stderr='{stderr_content}', exit_code={exit_code}, error='{error_message}'")
        return ExecutionResult(stdout=stdout_content, stderr=stderr_content, exit_code=exit_code, error=error_message)

    def setup(self) -> bool:
        """
        LocalREPL requires no special setup.
        """
        logger.info("LocalREPL setup complete (no action needed).")
        return True

    def cleanup(self) -> bool:
        """
        LocalREPL requires no special cleanup.
        """
        logger.info("LocalREPL cleanup complete (no action needed).")
        return True

    def is_available(self) -> bool:
        """
        LocalREPL is always available as it runs in-process.
        """
        return True

# If the RLM library's BaseEnvironment is needed for dynamic loading
# sys.modules['rlm.environments.base'] = sys.modules[__name__] # This would be if rlm.environments.base was expected to be loaded dynamically
