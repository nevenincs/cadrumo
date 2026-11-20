"""Run an observed ``-m`` child's module only when the checkout's load census declares it.

The census is the finite set of governed modules a checkout declares, so the
module the child bootstrap runs is one the import gate can resolve. A module it
does not declare is refused rather than run unobserved by that authority.
"""

from __future__ import annotations

import runpy
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from typing import Final

from cadrumo.tests.module_target_inventory import MetadataTargetSetError, load_all_target_sets

from .observation import active_observation

#: The census of the ``cadrumo`` root, relative to the checkout.
PRODUCT_CENSUS: Final = "dev/quality/metadata/import_load_targets.cadrumo.json"
#: The censuses of every other governed root, which together stay within the gate's closed-set bound.
SUPPORT_CENSUSES: Final = (
    "dev/quality/metadata/import_load_targets.cadrumo_agent_service.json",
    "dev/quality/metadata/import_load_targets.cadrumo_client.json",
    "dev/quality/metadata/import_load_targets.cadrumo_mcp.json",
    "dev/quality/metadata/import_load_targets.cadrumo_runtime.json",
    "dev/quality/metadata/import_load_targets.dev.json",
    "dev/quality/metadata/import_load_targets.docs.json",
)


class CensusRefusalError(LookupError):
    """Raised when the checkout's census does not declare an observed child's module, or cannot be read."""


def run_census_module(root: Path, module: str) -> None:
    """Run ``module`` as ``__main__`` when the census of the checkout ``root`` declares it.

    The census admits the launch and is no input of the program, so its reads
    are kept out of the observation. A later root's census is read only when the
    earlier ones do not declare ``module``.

    Raises:
        CensusRefusalError: The census does not declare ``module``, or cannot be read; nothing ran.
    """
    observation = active_observation()
    quiet: Callable[[], AbstractContextManager[None]] = nullcontext if observation is None else observation.suspended
    try:
        with quiet():
            product = load_all_target_sets(PRODUCT_CENSUS, repository=root)
    except MetadataTargetSetError as error:
        raise CensusRefusalError(f"the module census of {root} cannot be read: {error}") from error
    for product_module in product:
        if product_module == module:
            runpy.run_module(product_module, run_name="__main__", alter_sys=True)
            return
    for partition in SUPPORT_CENSUSES:
        try:
            with quiet():
                support = load_all_target_sets(partition, repository=root)
        except MetadataTargetSetError as error:
            raise CensusRefusalError(f"the module census of {root} cannot be read: {error}") from error
        for support_module in support:
            if support_module == module:
                runpy.run_module(support_module, run_name="__main__", alter_sys=True)
                return
    raise CensusRefusalError(f"the module census of {root} does not declare {module!r}")
