"""Obtain the provider catalog from cadrumo-agent, at run time.

Cadrumo keeps no list of providers. The agent reports the ones it supports with
its offline declaration command, which needs no gateway and no state home. This
module is the one place that names that invocation and the one place that runs
it: a change in the agent's command or document shape is made here and in the
domain parser, nowhere else.

The invocation runs in a minimal environment built from the operating-system
allow-list, so no provider key in the runtime's own environment reaches the
agent. A successful answer is kept for the source's lifetime; a failure is never
replaced by a stored copy.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from functools import cache
from pathlib import Path
from threading import Lock
from typing import Final, override

from cadrumo.core.errors.hierarchy import CoreValidationError
from cadrumo.core.logging import get_logger
from cadrumo_client.contracts.contracts import RefusalError

from ..host.controller import AgentHostError
from ..host.launch_environment import system_environment
from ..host.store_lifecycle import AgentInvocationRunner
from ..providers.application.ports import (
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    ProviderCatalogUnavailableReason,
)
from ..providers.domain.catalog import ProviderCatalog, parse_provider_catalog
from .agent_process import WindowsAgentInvocationRunner
from .agent_programs import AGENT_COMMAND_LINE, AgentProgramRefusalError, agent_image

_LOGGER = get_logger(__name__)

CATALOG_VERB: Final = ("providers", "--declared", "--json")
"""The agent's offline provider declaration, serving schema version 2."""
CATALOG_ARGUMENTS: Final = (*AGENT_COMMAND_LINE, *CATALOG_VERB)
CATALOG_TIMEOUT_SECONDS: Final = 30.0
CATALOG_OUTPUT_MAX_BYTES: Final = 256 * 1024


class AgentProviderCatalogSource(ProviderCatalogSource):
    """Run the agent's offline catalog command and parse what it prints."""

    def __init__(
        self,
        *,
        agent_source: str | None = None,
        received: Mapping[str, str] | None = None,
        runner: AgentInvocationRunner | None = None,
    ) -> None:
        """Bind the agent to run: the package's image, or the named development source tree."""
        self._runner: AgentInvocationRunner = WindowsAgentInvocationRunner() if runner is None else runner
        self._agent_source = agent_source
        self._received = os.environ if received is None else received
        self._lock = Lock()
        self._catalog: ProviderCatalog | None = None

    @override
    def catalog(self) -> ProviderCatalog:
        """Return the catalog the agent reports, running it once per source.

        Raises:
            ProviderCatalogUnavailableError: When the agent cannot be located or run, or its
                document is refused.
        """
        with self._lock:
            if self._catalog is None:
                self._catalog = self._fetch()
            return self._catalog

    def _fetch(self) -> ProviderCatalog:
        directory = Path(tempfile.gettempdir())
        try:
            image = agent_image(self._agent_source, agent_root=directory, received=self._received)
        except AgentProgramRefusalError as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND) from error
        try:
            completed = self._runner.run(
                executable=image.executable,
                arguments=CATALOG_ARGUMENTS,
                directory=image.directory,
                environment=system_environment(self._received),
                timeout=CATALOG_TIMEOUT_SECONDS,
                output_limit=CATALOG_OUTPUT_MAX_BYTES,
            )
        except (AgentHostError, OSError, RefusalError) as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED) from error
        if completed.status is None:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_TIMED_OUT)
        if completed.status != 0:
            _LOGGER.warning("agent provider catalog command failed status=%s", completed.status)
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_FAILED)
        if len(completed.standard_output) > CATALOG_OUTPUT_MAX_BYTES:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED)
        try:
            return parse_provider_catalog(completed.standard_output.decode("utf-8"))
        except (CoreValidationError, UnicodeDecodeError) as error:
            raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED) from error


@cache
def process_provider_catalog_source() -> AgentProviderCatalogSource:
    """Return the process's shared source, so one process runs the agent's declaration once."""
    return AgentProviderCatalogSource()


__all__ = ["CATALOG_ARGUMENTS", "AgentProviderCatalogSource", "process_provider_catalog_source"]
