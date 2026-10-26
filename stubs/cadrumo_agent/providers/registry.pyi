"""Every provider a run can name, and how its lane is reached."""

from collections.abc import Mapping
from typing import Final

from ..graph.enums import ExecutionLane
from .gateways import AnthropicGateway

class ProviderDescriptor:
    """The structural facts of one lane; only the fields the script reads are declared."""

    @property
    def display_name(self) -> str: ...
    @property
    def gateway(self) -> AnthropicGateway | None: ...

PROVIDERS: Final[Mapping[ExecutionLane, ProviderDescriptor]]
