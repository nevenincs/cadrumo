"""Production runtime helpers for :mod:`aeat.application.filing`.

Exposes concrete profile helpers used by the CLI and workflow surfaces.
The production schema provider is intentionally fail-closed until it is
backed by validated registry snapshots.

The filing runtime must not depend on
:mod:`aeat.application.filing.testing`; this module is the production
entry point that callers (CLI, workflow, services) construct profiles
and schema providers through.

Key entry points:

* :class:`FilingOperatorProfile` — pydantic v2 record satisfying the
  filing-profile Protocol.
* :func:`filing_profile_from_autonomo` — projects a domain
  :class:`aeat.domain.deadlines.AutonomoProfile` into the runtime
  profile shape.
* :func:`load_default_filing_profile` — loads the configured default
  profile JSON and returns a runtime profile.
* :func:`build_runtime_schema_provider` — rejects legacy static schema
  providers until registry-backed snapshots are available.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from ...domain.deadlines import AutonomoProfile, applies_to
from ...domain.filing import CasillaSchemaProvider
from ...domain.filing._errors import FilingBuilderError

_STRICT_FROZEN = ConfigDict(strict=True, frozen=True, extra="forbid")
_SUPPORTED_FILING_MODELOS: tuple[str, ...] = ("130", "303", "390")


class FilingOperatorProfile(BaseModel):
    """Concrete runtime implementation of the filing-profile Protocol.

    Strict, frozen pydantic v2 model satisfying the filing layer's
    profile Protocol. Constructed via
    :func:`filing_profile_from_autonomo` from a domain
    :class:`aeat.domain.deadlines.AutonomoProfile`.

    Attributes:
        tax_id: NIF / NIE of the filing operator.
        display_name: Human-readable label for the profile.
        applicable_modelos: Tuple of modelo codes (subset of
            ``("130", "303", "390")``) that the profile is liable for.
    """

    model_config = _STRICT_FROZEN

    tax_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    applicable_modelos: tuple[str, ...] = Field(default_factory=tuple)


def filing_profile_from_autonomo(
    profile: AutonomoProfile,
    *,
    display_name: str | None = None,
) -> FilingOperatorProfile:
    """Project an :class:`AutonomoProfile` into a :class:`FilingOperatorProfile`.

    Computes the ``applicable_modelos`` set by querying
    :func:`aeat.domain.deadlines.applies_to` for each supported modelo.

    Args:
        profile: Source domain profile.
        display_name: Optional friendly label; defaults to
            ``profile.tax_id``.

    Returns:
        A frozen :class:`FilingOperatorProfile`.
    """
    applicable = tuple(modelo for modelo in _SUPPORTED_FILING_MODELOS if applies_to(profile, modelo))
    return FilingOperatorProfile(
        tax_id=profile.tax_id,
        display_name=(display_name or profile.tax_id).strip(),
        applicable_modelos=applicable,
    )


def load_default_filing_profile(
    path: Path | None = None,
    *,
    display_name: str | None = None,
) -> FilingOperatorProfile:
    """Load the configured default profile JSON for runtime filing commands.

    Resolves ``path`` (or, when ``None``, the
    ``aeat_default_profile_path`` setting from
    :func:`aeat.core.config.load_settings`), validates the on-disk
    envelope via :func:`aeat.application.setup._env_writer.load_profile_envelope`,
    and projects it into a runtime :class:`FilingOperatorProfile`.

    Args:
        path: Override path to the profile JSON. Defaults to the
            value of ``AEAT_DEFAULT_PROFILE_PATH``.
        display_name: Optional friendly label propagated to the
            returned profile.

    Returns:
        The loaded :class:`FilingOperatorProfile`.

    Raises:
        FilingBuilderError: When no default profile is configured or when the
            resolved path does not exist on disk.
    """
    from ...core.config import load_settings

    settings = load_settings()
    target = path or settings.aeat_default_profile_path
    if target is None:
        raise FilingBuilderError(
            "no default filing profile configured; pass --profile PATH or set AEAT_DEFAULT_PROFILE_PATH"
        )
    if not target.exists():
        raise FilingBuilderError(f"default filing profile not found: {target}")
    from ..setup._env_writer import load_profile_envelope

    profile = load_profile_envelope(target)
    return filing_profile_from_autonomo(profile, display_name=display_name)


def build_runtime_schema_provider() -> CasillaSchemaProvider:
    """Reject legacy production filing schemas.

    Filing-grade draft creation must be backed by validated registry
    snapshots. The previous provider imported model-specific static
    builder schemas, which shadowed the central registry and allowed
    production calculation paths to run without legal-source closure.
    """

    raise FilingBuilderError(
        "runtime filing schema provider requires validated registry snapshots; "
        "legacy static filing schemas are disabled",
    )


__all__ = [
    "FilingOperatorProfile",
    "build_runtime_schema_provider",
    "filing_profile_from_autonomo",
    "load_default_filing_profile",
]
