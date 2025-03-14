from docker.models.containers import Container
import os
from typing import Iterable, Optional, Tuple

from .waiting_utils import wait_container_is_ready
from .docker_client import DockerClient
from .exceptions import ContainerStartException
from .utils import setup_logger, inside_container, is_arm

logger = setup_logger(__name__)


class DockerContainer:
    """
    Basic container object to spin up Docker instances.

    .. doctest::

        >>> from testcontainers.core.container import DockerContainer
        >>> from testcontainers.core.waiting_utils import wait_for_logs

        >>> with DockerContainer("hello-world") as container:
        ...    delay = wait_for_logs(container, "Hello from Docker!")
    """

    def __init__(
        self, image: str, docker_client_kw: Optional[dict] = None, **kwargs
    ) -> None:
        self.env = {}
        self.ports = {}
        self.volumes = {}
        self.image = image
        self._docker = DockerClient(**(docker_client_kw or {}))
        self._container = None
        self._command = None
        self._name = None
        self._kwargs = kwargs

    def with_env(self, key: str, value: str) -> "DockerContainer":
        self.env[key] = value
        return self

    def with_bind_ports(self, container: int, host: int = None) -> "DockerContainer":
        self.ports[container] = host
        return self

    def with_exposed_ports(self, *ports: Iterable[int]) -> "DockerContainer":
        for port in ports:
            self.ports[port] = None
        return self

    def with_kwargs(self, **kwargs) -> "DockerContainer":
        self._kwargs = kwargs
        return self

    def maybe_emulate_amd64(self) -> "DockerContainer":
        if is_arm():
            return self.with_kwargs(platform="linux/amd64")
        return self

    def start(self) -> "DockerContainer":
        logger.info("Pulling image %s", self.image)
        docker_client = self.get_docker_client()
        self._container = docker_client.run(
            self.image,
            command=self._command,
            detach=True,
            environment=self.env,
            ports=self.ports,
            name=self._name,
            volumes=self.volumes,
            **self._kwargs
        )
        logger.info("Container started: %s", self._container.short_id)
        return self

    def stop(self, force=True, delete_volume=True) -> None:
        self.get_wrapped_container().remove(force=force, v=delete_volume)

    def __enter__(self) -> "DockerContainer":
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.stop()

    def __del__(self) -> None:
        """
        Try to remove the container in all circumstances
        """
        if self._container is not None:
            try:
                self.stop()
            except:  # noqa: E722
                pass

    def get_container_host_ip(self) -> str:
        # infer from docker host
        return self.get_docker_client().bridge_ip(self._container.id)

    @wait_container_is_ready()
    def get_exposed_port(self, port: int) -> str:
        return self.port

    def with_command(self, command: str) -> "DockerContainer":
        self._command = command
        return self

    def with_name(self, name: str) -> "DockerContainer":
        self._name = name
        return self

    def with_volume_mapping(
        self, host: str, container: str, mode: str = "ro"
    ) -> "DockerContainer":
        mapping = {"bind": container, "mode": mode}
        self.volumes[host] = mapping
        return self

    def get_wrapped_container(self) -> Container:
        return self._container

    def get_docker_client(self) -> DockerClient:
        return self._docker

    def get_logs(self) -> Tuple[str, str]:
        if not self._container:
            raise ContainerStartException(
                "Container should be started before getting logs"
            )
        return self._container.logs(stderr=False), self._container.logs(stdout=False)

    def exec(self, command) -> Tuple[int, str]:
        if not self._container:
            raise ContainerStartException(
                "Container should be started before executing a command"
            )
        return self.get_wrapped_container().exec_run(command)
