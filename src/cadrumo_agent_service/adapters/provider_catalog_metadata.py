"""Read the bundled agent's declared provider catalogue through its public offline function.

While no agent is ready the picker shows what the agent declares: the same
document its ``providers --declared --json`` command prints, read in process
from the wheel installed beside this one. That document says which lanes and
models exist, never whether a lane is configured, signed in or runnable here,
so it travels in an envelope a reader can tell apart from the served catalogue.
"""

from __future__ import annotations

import base64
import hashlib
from importlib import import_module
from importlib.metadata import PackageNotFoundError, distribution
from importlib.util import find_spec
from pathlib import Path
from types import ModuleType
from typing import Any, Final

from ..providers.application.ports import ProviderCatalogUnavailableError, ProviderCatalogUnavailableReason

DECLARED_CATALOG_MODULE: Final = "cadrumo_agent.providers.declared_catalog"
"""The agent's public module that renders its declared catalogue offline."""
DECLARED_CATALOG_KIND: Final = "declared"
"""The envelope kind of a declared catalogue; a served catalogue carries no ``kind``."""


def _cohort_module() -> ModuleType:
    """Refuse missing, editable or shadowed agent code before loading the declaration module."""
    try:
        agent = distribution("cadrumo-agent")
        application = distribution("cadrumo")
        base = Path(str(agent.locate_file(""))).resolve(strict=True)
        if base != Path(str(application.locate_file(""))).resolve(strict=True):
            raise ValueError("different_wheel_cohort")
        records = {str(item).replace("\\", "/"): item for item in agent.files or ()}
        for module_name in ("cadrumo_agent", DECLARED_CATALOG_MODULE):
            spec = find_spec(module_name)
            if spec is None or spec.origin is None:
                raise ValueError("agent_module_unavailable")
            path = Path(spec.origin).resolve(strict=True)
            relative = path.relative_to(base).as_posix()
            record = records.get(relative)
            if record is None or record.hash is None or record.hash.mode != "sha256":
                raise ValueError("agent_module_not_in_wheel")
            digest = base64.urlsafe_b64encode(hashlib.sha256(path.read_bytes()).digest()).rstrip(b"=").decode("ascii")
            if digest != record.hash.value:
                raise ValueError("agent_module_changed")
        return import_module(DECLARED_CATALOG_MODULE)
    except (PackageNotFoundError, ImportError, OSError, ValueError) as error:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.AGENT_NOT_FOUND) from error


def declared_catalog_envelope(document: object) -> dict[str, Any]:
    """Wrap the agent's declared catalogue document as the picker serves it.

    Raises:
        ProviderCatalogUnavailableError: When the document lists no providers array.
    """
    if not isinstance(document, dict) or not isinstance(document.get("providers"), list):
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED)
    return {"kind": DECLARED_CATALOG_KIND, "catalog": document}


def declared_provider_catalog_response() -> dict[str, Any]:
    """Return the agent's declared catalogue, as rendered by its public function, in its envelope.

    Nothing here reads a setting, a credential or a provider home, and no lane
    is probed: whether a lane can run is the served catalogue's answer.

    Raises:
        ProviderCatalogUnavailableError: When the installed agent is missing or
            not of this wheel cohort, or its document cannot be rendered.
    """
    module = _cohort_module()
    try:
        document = module.declared_provider_catalog().model_dump(mode="json")
    except Exception as error:
        raise ProviderCatalogUnavailableError(ProviderCatalogUnavailableReason.CATALOG_MALFORMED) from error
    return declared_catalog_envelope(document)


__all__ = [
    "DECLARED_CATALOG_KIND",
    "DECLARED_CATALOG_MODULE",
    "declared_catalog_envelope",
    "declared_provider_catalog_response",
]
