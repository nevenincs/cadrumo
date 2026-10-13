"""The exact execution mode each external provider lane is served under."""

from ..control.infra_config import AcpBackend
from ..graph.enums import ExecutionLane

def external_execution_mode(provider: ExecutionLane, acp_backend: AcpBackend) -> str: ...
