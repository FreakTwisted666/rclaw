# rlm/environments/docker.py - Docker REPL Environment

import docker
import os
import io
import logging
from typing import Dict, Any, Optional

from rlm.environments.base import BaseEnvironment, ExecutionResult

logger = logging.getLogger(__name__)

class DockerREPL(BaseEnvironment):
    """
    Executes Python code inside a Docker container for enhanced isolation.
    Requires Docker to be installed and the Docker daemon to be running.
    """
    DEFAULT_IMAGE = "python:3.11-slim"
    DEFAULT_CONTAINER_NAME = "rlmclaw_docker_repl"
    DEFAULT_WORK_DIR = "/app" # Working directory inside the container

    def __init__(self, image: str = DEFAULT_IMAGE,
                 container_name: str = DEFAULT_CONTAINER_NAME,
                 mount_path: Optional[str] = None, # Host path to mount into container
                 read_only_mount: bool = False,
                 **kwargs):
        super().__init__(**kwargs)
        self.image = image
        self.container_name = container_name
        self.mount_path = mount_path
        self.read_only_mount = read_only_mount
        self.client: Optional[docker.DockerClient] = None
        self.container: Optional[docker.models.containers.Container] = None

        logger.info(f"DockerREPL initialized with image: {self.image}, container name: {self.container_name}")

    def _get_docker_client(self) -> Optional[docker.DockerClient]:
        """Gets a Docker client instance, handling common errors."""
        try:
            return docker.from_env()
        except docker.errors.DockerException as e:
            logger.error(f"Could not connect to Docker daemon: {e}")
            return None

    def setup(self) -> bool:
        """
        Ensures the Docker container is running and ready.
        Pulls the image if it doesn't exist and starts/restarts the container.
        """
        self.client = self._get_docker_client()
        if not self.client:
            return False

        try:
            # Check if container already exists
            try:
                self.container = self.client.containers.get(self.container_name)
                # If container is stopped, try to start it
                if self.container.status != 'running':
                    logger.info(f"Existing container '{self.container_name}' found, but not running. Starting...")
                    self.container.start()
                    self.container.wait(condition='running', timeout=30) # Wait until it's running
            except docker.errors.NotFound:
                logger.info(f"Container '{self.container_name}' not found. Creating and starting...")
                
                volumes = {}
                if self.mount_path and os.path.exists(self.mount_path):
                    volumes[self.mount_path] = {
                        'bind': self.DEFAULT_WORK_DIR,
                        'mode': 'ro' if self.read_only_mount else 'rw'
                    }
                    logger.info(f"Mounting host path {self.mount_path} to container {self.DEFAULT_WORK_DIR} with mode {'ro' if self.read_only_mount else 'rw'}")
                else:
                    logger.warning(f"Mount path '{self.mount_path}' not found or not specified. Container will not have external mount.")

                self.container = self.client.containers.run(
                    image=self.image,
                    name=self.container_name,
                    command=f'tail -f /dev/null', # Keep container running
                    detach=True,
                    auto_remove=False, # Keep for debugging/reuse
                    working_dir=self.DEFAULT_WORK_DIR,
                    volumes=volumes,
                    # Add more security options if needed, e.g., network_mode='none'
                )
                logger.info(f"Container '{self.container_name}' started successfully with ID: {self.container.id}")

            # Verify container is running
            self.container.reload()
            if self.container.status != 'running':
                logger.error(f"Failed to ensure Docker container '{self.container_name}' is running. Status: {self.container.status}")
                return False

            return True

        except docker.errors.ImageNotFound:
            logger.error(f"Docker image '{self.image}' not found locally. Attempting to pull...")
            try:
                self.client.images.pull(self.image)
                return self.setup() # Retry setup after pulling image
            except docker.errors.DockerException as e:
                logger.error(f"Failed to pull Docker image '{self.image}': {e}")
                return False
        except docker.errors.APIError as e:
            logger.error(f"Docker API error during setup for '{self.container_name}': {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during DockerREPL setup: {e}")
            return False

    def cleanup(self) -> bool:
        """
        Stops and removes the Docker container.
        """
        if self.container:
            try:
                logger.info(f"Stopping and removing Docker container '{self.container_name}'...")
                self.container.stop(timeout=10)
                self.container.remove()
                self.container = None
                logger.info(f"Container '{self.container_name}' stopped and removed.")
                return True
            except docker.errors.APIError as e:
                logger.error(f"Docker API error during cleanup for '{self.container_name}': {e}")
                return False
            except Exception as e:
                logger.error(f"Unexpected error during DockerREPL cleanup: {e}")
                return False
        return True

    def is_available(self) -> bool:
        """
        Checks if Docker daemon is accessible and the container is running.
        """
        self.client = self._get_docker_client()
        if not self.client:
            return False
        try:
            self.client.ping() # Check if daemon is responsive
            if self.container:
                self.container.reload()
                return self.container.status == 'running'
            # If container not initialized, assume available if daemon is up
            return True
        except Exception as e:
            logger.error(f"Docker daemon not available: {e}")
            return False

    def execute_code(self, code: str, timeout: int = 30) -> ExecutionResult:
        """
        Executes the given Python code inside the running Docker container.
        """
        if not self.container or self.container.status != 'running':
            return ExecutionResult(error="Docker container not running. Call setup() first.")

        # Construct the command to execute Python code
        # Wrap code in a file and execute to handle multi-line and larger scripts
        script_name = "rlm_script.py"
        # Using a single-line command for exec_run for simplicity.
        # For complex code, writing to a file in the container and then executing it is safer.
        # This current approach works for smaller snippets, but might have issues with quotes/multiline.
        # A better approach would be to `put_archive` the script.
        # For now, let's use a base64 encoded approach to avoid quoting issues.
        
        # Base64 encode the script to avoid shell quoting issues
        import base64
        encoded_code = base64.b64encode(code.encode('utf-8')).decode('utf-8')
        
        # Command to decode and execute the script inside the container
        # This will write the code to a file and then execute it
        cmd = f"bash -c 'echo {encoded_code} | base64 -d > {self.DEFAULT_WORK_DIR}/{script_name} && python {self.DEFAULT_WORK_DIR}/{script_name}'"

        try:
            # Execute the command in the container
            exec_result = self.container.exec_run(
                cmd=cmd,
                workdir=self.DEFAULT_WORK_DIR,
                stream=False, # Wait for completion
                demux=True, # Separate stdout/stderr
                # Setting detach=False (default) will block until command finishes
            )

            stdout = exec_result.output.decode('utf-8') if exec_result.output else ""
            stderr = exec_result.stream.decode('utf-8') if exec_result.stream else "" # stream for stderr
            exit_code = exec_result.exit_code if exec_result.exit_code is not None else 1

            # Cleanup the temporary script (optional, but good practice)
            # self.container.exec_run(cmd=f"rm {self.DEFAULT_WORK_DIR}/{script_name}")

            logger.debug(f"DockerREPL result: stdout='{stdout}', stderr='{stderr}', exit_code={exit_code}")
            return ExecutionResult(stdout=stdout, stderr=stderr, exit_code=exit_code)

        except docker.errors.APIError as e:
            logger.error(f"Docker API error during code execution: {e}")
            return ExecutionResult(error=str(e), exit_code=1)
        except Exception as e:
            logger.error(f"Unexpected error during DockerREPL execute_code: {e}")
            return ExecutionResult(error=str(e), exit_code=1)

# Note: For this module to be dynamically loadable by the main engine,
# ensure it's in the Python path and its name (docker.py) matches the
# expected import string (e.g., from_rlm_environments_docker_import_DockerREPL).
# This is handled by RLM's expected dynamic loading mechanisms.
