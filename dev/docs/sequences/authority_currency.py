"""Refuse to execute ``cli-sequence`` frames against a stale registry authority.

Every executed frame reads the published registry authority the runner
resolves through
:func:`~cadrumo.domain.calculations.registry.authority.bundled_authority_descriptor_path`.
When that generation no longer records the live legal sources, an execution
yields values the current tree would not produce: a check reports
divergences that are not real, and a refresh commits them into the goldens as
the new truth. The engine therefore confirms currency before it executes
anything and refuses with the one command that repairs it, rather than
republishing on its own, which would mutate shared local state from inside a
docs command.
"""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import SequenceEngineError

if TYPE_CHECKING:
    from dev.registry.pipeline.authority_publication import AuthorityDatabaseCurrency

__all__ = [
    "PUBLISH_AUTHORITY_REMEDY",
    "authority_currency_refusal",
    "require_current_authority",
    "unavailable_authority_refusal",
]

#: The command that republishes the authority only when it is stale.
PUBLISH_AUTHORITY_REMEDY = "uv run --no-sync python -m dev.registry.pipeline publish-authority --if-stale"


def _refusal(reason: str) -> str:
    return (
        f"refusing to execute cli-sequence frames: {reason}. Executing against it would compare or record "
        f"values the current registry does not produce. Republish it with: {PUBLISH_AUTHORITY_REMEDY}"
    )


def authority_currency_refusal(currency: AuthorityDatabaseCurrency) -> str | None:
    """Return the refusal message for a non-current authority, ``None`` when current.

    Every status other than current refuses: a stale generation answers with
    old values, and an unreadable or unsupported one cannot prove it does not.
    """
    if currency.is_current:
        return None
    return _refusal(
        f"the registry authority at {currency.descriptor_path} is {currency.status.value} ({currency.detail})",
    )


def unavailable_authority_refusal(detail: str) -> str:
    """Return the refusal message for an authority descriptor that does not resolve."""
    return _refusal(f"no published registry authority resolves ({detail})")


@cache
def _descriptor_refusal(descriptor_path: Path) -> str | None:
    from cadrumo.core.resources.bundled_data import bundled_path
    from dev.registry.pipeline.authority_publication import authority_database_currency

    currency = authority_database_currency(
        descriptor_path,
        registry_root=bundled_path("registry", "aeat"),
        source_root=bundled_path(),
        profile_schema_path=bundled_path("registry", "cadrumo", "user_profile", "schema.toml"),
    )
    return authority_currency_refusal(currency)


def require_current_authority() -> None:
    """Refuse unless the authority the runner will read is current.

    The verdict is cached per descriptor for the life of the process: the
    comparison re-hashes the registry sources, and one engine run asks once.

    Raises:
        SequenceEngineError: When the descriptor does not resolve, or the
            generation it names is not current; the message names
            :data:`PUBLISH_AUTHORITY_REMEDY`.
    """
    from cadrumo.domain.calculations.registry.authority import bundled_authority_descriptor_path
    from cadrumo.domain.calculations.registry.errors import AuthorityDescriptorUnavailableError

    try:
        descriptor_path = bundled_authority_descriptor_path()
    except AuthorityDescriptorUnavailableError as exc:
        raise SequenceEngineError(unavailable_authority_refusal(str(exc))) from exc
    refusal = _descriptor_refusal(descriptor_path.resolve())
    if refusal is not None:
        raise SequenceEngineError(refusal)
