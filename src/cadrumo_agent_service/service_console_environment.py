"""The console environment of the signed-in profile: provider homes and the agent's workspace.

The desktop host starts its console kind with this answer merged over the
console's own environment, so the provider programs a person runs there use
the same provider homes and the same workspace as the profile's agent. The
answer names locations only. A provider keeps its credentials inside its home,
and nothing here opens a home, so no credential, session, receipt or key can
enter the answer.

Each answer carries an opaque revision, a digest of exactly what it names. The
answer for no signed-in profile names nothing and has a revision of its own, so
a reader that compares revisions sees every sign-in, sign-out and profile change.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final

from cadrumo.core.storage_taxonomy import StorageCategory
from cadrumo.core.storage_taxonomy_locations import storage_location

from .adapters.agent_programs import AgentProgramRefusalError, profile_agent_root, profile_agent_workspace
from .adapters.console_provisioning import LAYOUT_MODULE, SIGN_IN_MODULE, provider_homes
from .adapters.provider_catalog_metadata import agent_cohort_module
from .providers.application.ports import ProviderCatalogUnavailableError

if TYPE_CHECKING:
    from uuid import UUID

CONSOLE_ENVIRONMENT_KIND: Final = "console_environment"
"""The kind of an answer to the ``console_environment`` read."""
REFUSED_NAME_PREFIXES: Final = ("CADRUMO_", "PYTHON", "AEAT_", "FINANCIAL_")
"""Name classes the console's own filter clears; an answer never carries one."""
_REVISION_DOMAIN: Final = b"cadrumo.console-environment.v1\0"


def console_provider_homes(agent_root: Path) -> dict[str, str]:
    """Return the provider homes the installed agent derives under ``agent_root``.

    Raises:
        ProviderCatalogUnavailableError: When the installed agent is missing or
            not of this wheel cohort.
    """
    return provider_homes(
        agent_root, layout=agent_cohort_module(LAYOUT_MODULE), sign_ins=agent_cohort_module(SIGN_IN_MODULE)
    )


def admissible_name(name: str) -> bool:
    """Whether a console may carry ``name``: an ASCII variable name outside every refused class."""
    upper = name.upper()
    return (
        name.isascii()
        and name.replace("_", "a").isalnum()
        and not name[:1].isdigit()
        and not upper.startswith(REFUSED_NAME_PREFIXES)
    )


def console_environment_answer(environment: Mapping[str, str], working_directory: Path | None) -> dict[str, Any]:
    """Return the answer naming ``environment`` and ``working_directory``, with its revision."""
    kept = {name: value for name, value in sorted(environment.items()) if admissible_name(name)}
    directory = None if working_directory is None else str(working_directory)
    stated = json.dumps({"environment": kept, "working_directory": directory}, sort_keys=True, separators=(",", ":"))
    return {
        "kind": CONSOLE_ENVIRONMENT_KIND,
        "environment": kept,
        "working_directory": directory,
        "revision": hashlib.sha256(_REVISION_DOMAIN + stated.encode("utf-8")).hexdigest(),
    }


def no_profile_answer() -> dict[str, Any]:
    """Return the answer while no profile is signed in: nothing named, and its own revision."""
    return console_environment_answer({}, None)


def _outside_buckets(storage_root: Path, directory: Path) -> bool:
    buckets = (storage_root / storage_location(StorageCategory.BUCKETS).subpath).resolve()
    return not directory.resolve().is_relative_to(buckets)


def profile_console_environment(
    storage_root: Path,
    profile_id: UUID,
    *,
    homes: Callable[[Path], Mapping[str, str]],
) -> dict[str, Any]:
    """Return the console environment of ``profile_id``, or a refusal when it cannot be named.

    The working directory is the profile's agent workspace, which lies in the
    profile's agent directory and never inside a bucket's custody tree.
    """
    try:
        agent_root = profile_agent_root(storage_root, profile_id)
        workspace = profile_agent_workspace(agent_root)
        named = homes(agent_root)
    except (AgentProgramRefusalError, ProviderCatalogUnavailableError, OSError, ValueError):
        return {"kind": "refused", "code": "console_environment_unavailable"}
    if not _outside_buckets(storage_root, workspace):
        return {"kind": "refused", "code": "console_environment_unavailable"}
    return console_environment_answer(named, workspace)


def answer_console_environment(
    storage_root: Path,
    *,
    closing: bool,
    lease: Callable[[], Any],
) -> dict[str, Any]:
    """Answer the ``console_environment`` read for the lease current now.

    A lease that changes while the answer is read is answered as no profile:
    the reader asks again on the change, and never receives the earlier profile's values.
    """
    if closing:
        return {"kind": "refused", "code": "service_stopping"}
    current = lease()
    if current is None:
        return no_profile_answer()
    answer = profile_console_environment(storage_root, current.profile_id, homes=console_provider_homes)
    return answer if lease() == current else no_profile_answer()


__all__ = [
    "CONSOLE_ENVIRONMENT_KIND",
    "REFUSED_NAME_PREFIXES",
    "admissible_name",
    "answer_console_environment",
    "console_environment_answer",
    "console_provider_homes",
    "no_profile_answer",
    "profile_console_environment",
]
