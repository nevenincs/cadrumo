"""Import-light namespace for user-facing entrypoints.

Concrete transports live in child packages, currently the Typer CLI under
:mod:`cli`. The root exports no commands and should remain a
marker so importing :mod:`entrypoints` does not initialise command trees,
locale catalogues, browser integrations, or storage sessions.

Entrypoints translate process-level concerns into application-facade calls. They
own presentation, command parsing, exit-code mapping, and terminal error
contracts; business decisions stay in :mod:`application` and
:mod:`domain`.

See Also:
    :mod:`cli`
        Typer transport that mounts the operator command tree.
    :mod:`application.operator_surface`
        Backend-owned command-surface contract consumed by entrypoint adapters.
    :mod:`core.json_contract`
        Shared success-envelope, schema registry, and notice-channel contract.
    :mod:`core.errors`
        Central error envelope and exit-code mapping used at transport
        boundaries.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._censal_review import (
        CensalReviewedFrontendResult as CensalReviewedFrontendResult,
    )
    from ._censal_review import run_censal_review as run_censal_review
    from ._operation_composition import (
        build_production_operation_registry as build_production_operation_registry,
    )
    from ._operation_composition import (
        compose_operation_dependencies as compose_operation_dependencies,
    )

__all__ = [
    "CensalReviewedFrontendResult",
    "build_production_operation_registry",
    "compose_operation_dependencies",
    "run_censal_review",
]


def __getattr__(name: str) -> object:
    """Resolve the production operation inventory without eager entrypoint loading."""
    if name == "build_production_operation_registry":
        from ._operation_composition import build_production_operation_registry

        return build_production_operation_registry
    if name == "compose_operation_dependencies":
        from ._operation_composition import compose_operation_dependencies

        return compose_operation_dependencies
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if name == "CensalReviewedFrontendResult":
        from ._censal_review import CensalReviewedFrontendResult

        return CensalReviewedFrontendResult
    if name == "run_censal_review":
        from ._censal_review import run_censal_review

        return run_censal_review
