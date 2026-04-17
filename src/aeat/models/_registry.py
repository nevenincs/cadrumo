"""Registry assembly for the modelo inventory.

Imports every ``_entries/modelo_*.py`` module, collects its
module-level ``ENTRY`` object, and freezes the result as the public
:data:`MODELO_REGISTRY` mapping. Structural invariants are enforced at
import time via :func:`_finalise_registry`; any violation raises
:class:`aeat.models._errors.RegistryIntegrityError` and aborts package
import.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from ..deadlines import (
    AutonomoProfile,
    DeadlineEngine,
    ModeloIdentifier,
    Schedule,
)
from ..logging import get_logger
from ._categories import TaxpayerProfile
from ._codes import ModeloCode
from ._entries import (
    modelo_036,
    modelo_037,
    modelo_100,
    modelo_111,
    modelo_115,
    modelo_123,
    modelo_130,
    modelo_131,
    modelo_180,
    modelo_190,
    modelo_193,
    modelo_200,
    modelo_202,
    modelo_232,
    modelo_303,
    modelo_347,
    modelo_349,
    modelo_369,
    modelo_390,
    modelo_720,
    modelo_840,
)
from ._errors import RegistryIntegrityError, UnknownModeloError
from ._metadata import ModeloMetadata

_LOG = get_logger(__name__)


_ENTRIES: tuple[ModeloMetadata, ...] = (
    modelo_036.ENTRY,
    modelo_037.ENTRY,
    modelo_100.ENTRY,
    modelo_111.ENTRY,
    modelo_115.ENTRY,
    modelo_123.ENTRY,
    modelo_130.ENTRY,
    modelo_131.ENTRY,
    modelo_180.ENTRY,
    modelo_190.ENTRY,
    modelo_193.ENTRY,
    modelo_200.ENTRY,
    modelo_202.ENTRY,
    modelo_232.ENTRY,
    modelo_303.ENTRY,
    modelo_347.ENTRY,
    modelo_349.ENTRY,
    modelo_369.ENTRY,
    modelo_390.ENTRY,
    modelo_720.ENTRY,
    modelo_840.ENTRY,
)


def _check_caps_into(entries: Mapping[ModeloCode, ModeloMetadata]) -> None:
    """Validate every ``caps_into`` reference resolves inside ``entries``.

    Args:
        entries: The assembled registry mapping.

    Raises:
        RegistryIntegrityError: If any entry's ``caps_into`` points at
            a :class:`ModeloCode` that is not a key of ``entries``.
    """
    for code, metadata in entries.items():
        target = metadata.caps_into
        if target is None:
            continue
        if target not in entries:
            raise RegistryIntegrityError(f"modelo {code.value} caps_into {target.value} which is not in the registry")


def _check_submission_portal(entries: Mapping[ModeloCode, ModeloMetadata]) -> None:
    """Validate every ``submission_portal`` round-trips through the portal registry.

    When :attr:`ModeloMetadata.submission_portal` is non-``None``, it
    must resolve inside :data:`aeat.portals.PORTAL_REGISTRY` and the
    portal's ``related_modelo`` must equal the modelo's own code. This
    closes the cross-reference round-trip at import time and is the
    type-level replacement for the free-form hint string shipped in
    the first cut of this registry.

    Args:
        entries: The assembled registry mapping.

    Raises:
        RegistryIntegrityError: If any ``submission_portal`` points at
            an unknown portal, or the portal's ``related_modelo`` does
            not match the modelo's code.
    """
    # Local import to avoid a circular module-level dependency with
    # aeat.portals (which itself imports aeat.models.ModeloCode). The
    # import is routed through the public package root so it exercises
    # the lazy __getattr__ surface, keeping us on the documented API.
    from ..portals import PORTAL_REGISTRY

    for code, metadata in entries.items():
        portal = metadata.submission_portal
        if portal is None:
            continue
        try:
            portal_metadata = PORTAL_REGISTRY[portal]
        except KeyError as exc:
            raise RegistryIntegrityError(
                f"modelo {code.value} submission_portal {portal.value!r} is not in PORTAL_REGISTRY"
            ) from exc
        if portal_metadata.related_modelo is not code:
            related = portal_metadata.related_modelo.value if portal_metadata.related_modelo is not None else None
            raise RegistryIntegrityError(
                f"modelo {code.value} submission_portal {portal.value!r} has "
                f"related_modelo {related!r} (expected {code.value!r})"
            )


def _finalise_registry(
    entries: tuple[ModeloMetadata, ...],
) -> Mapping[ModeloCode, ModeloMetadata]:
    """Assemble the frozen registry mapping and enforce every invariant.

    Args:
        entries: The per-entry ``ENTRY`` objects loaded from
            :mod:`aeat.models._entries`.

    Returns:
        A :class:`types.MappingProxyType` from :class:`ModeloCode` to
        :class:`ModeloMetadata`, frozen and complete.

    Raises:
        RegistryIntegrityError: If any structural invariant fails.
    """
    materialised: dict[ModeloCode, ModeloMetadata] = {}
    for entry in entries:
        if entry.code in materialised:
            raise RegistryIntegrityError(f"duplicate registry entry for modelo {entry.code.value}")
        materialised[entry.code] = entry
    missing = set(ModeloCode) - set(materialised)
    if missing:
        missing_values = sorted(m.value for m in missing)
        raise RegistryIntegrityError(f"registry is missing entries for modelos: {missing_values}")
    extra = set(materialised) - set(ModeloCode)
    if extra:
        extra_values = sorted(m.value for m in extra)
        raise RegistryIntegrityError(f"registry contains unknown modelos: {extra_values}")
    for key, metadata in materialised.items():
        if metadata.code is not key:
            raise RegistryIntegrityError(f"entry for {key.value} has mismatched code {metadata.code.value}")
    _check_caps_into(materialised)
    _check_submission_portal(materialised)
    _LOG.info("loaded %d modelo entries", len(materialised))
    return MappingProxyType(materialised)


MODELO_REGISTRY: Mapping[ModeloCode, ModeloMetadata] = _finalise_registry(_ENTRIES)


def get_modelo(code: ModeloCode | str) -> ModeloMetadata:
    """Return the registry entry for a modelo.

    Accepts either a :class:`ModeloCode` member or the canonical
    three-character string representation. Any failure — unknown
    code, failed coercion — raises :class:`UnknownModeloError`.

    Args:
        code: A :class:`ModeloCode` member or its string value.

    Returns:
        The authoritative :class:`ModeloMetadata` for ``code``.

    Raises:
        UnknownModeloError: If ``code`` is not a registered modelo.
    """
    if isinstance(code, ModeloCode):
        member = code
    else:
        try:
            member = ModeloCode(code)
        except ValueError as exc:
            raise UnknownModeloError(code) from exc
    try:
        return MODELO_REGISTRY[member]
    except KeyError as exc:
        raise UnknownModeloError(member.value) from exc


def modelos_for_profile(profile: TaxpayerProfile) -> tuple[ModeloMetadata, ...]:
    """Return every modelo that applies to a taxpayer profile.

    Includes both mandatory and optional applicability. The result is
    sorted by :class:`ModeloCode` value for deterministic output.

    Args:
        profile: The :class:`TaxpayerProfile` to query.

    Returns:
        A tuple of matching :class:`ModeloMetadata` entries.
    """
    matches = [
        metadata
        for metadata in MODELO_REGISTRY.values()
        if profile in metadata.applicability.mandatory_profiles or profile in metadata.applicability.optional_profiles
    ]
    matches.sort(key=lambda m: m.code.value)
    return tuple(matches)


class _InProcessCatalogue:
    """Minimal :class:`aeat.deadlines.ModeloCatalogueLoader` implementation.

    Built from :class:`ModeloCode.__members__` so the deadline engine
    can treat every registry modelo as a known identifier without a
    hard import cycle.
    """

    def known_modelos(self) -> tuple[ModeloIdentifier, ...]:
        """Return the registry's modelo identifiers for the deadline engine."""
        return tuple(ModeloIdentifier(code.value) for code in ModeloCode)

    def is_known(self, modelo: ModeloIdentifier) -> bool:
        """Return whether ``modelo`` is one of the registered modelos."""
        return str(modelo) in {code.value for code in ModeloCode}


def year_plan(year: int, profile: AutonomoProfile) -> Schedule:
    """Resolve the full filing :class:`Schedule` for a year and profile.

    Thin wrapper around
    :meth:`aeat.deadlines.DeadlineEngine.compute`. The wrapper does not
    narrow the returned obligations; callers (notably the CLI) filter
    by profile-level applicability themselves.

    Args:
        year: The target fiscal year.
        profile: The :class:`aeat.deadlines.AutonomoProfile` the
            deadline engine resolves obligations for.

    Returns:
        The :class:`aeat.deadlines.Schedule` produced by the deadline
        engine for ``year`` and ``profile``.
    """
    engine = DeadlineEngine(_InProcessCatalogue())
    return engine.compute(profile, year=year)
