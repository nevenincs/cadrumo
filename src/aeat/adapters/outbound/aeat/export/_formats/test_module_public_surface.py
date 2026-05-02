"""Public-surface lock for per-modelo schema modules.

Every ``modelo_{n}_{year}.py`` module must expose exactly the
canonical set of public names:

* Single-record schemas (Modelo 130): ``ENCODING``,
  ``RECORD_LENGTH``, ``RECORD_SPECS``, ``REQUIRED_HEADER_FIELDS``.
* Envelope schemas (Modelo 303, future 390): ``ENCODING``,
  ``ENVELOPE``, ``REQUIRED_HEADER_FIELDS``.

A generator change that smuggles in an extra top-level symbol (a
debug helper, cache, or side-effect callable) would make the schema
module's import behaviour unpredictable and leak the underscore-
prefix internal convention. These tests pin the surface so that
kind of drift fails at collection.

Implementation: each module's ``__all__`` and its non-underscore-
prefixed globals are both compared against the canonical set. The
``_SEGMENT_*`` constants the generator emits are underscore-
prefixed by design so they do not pollute the public surface; they
are internal building blocks for ``ENVELOPE``.
"""

from __future__ import annotations

from types import ModuleType

import pytest

from . import modelo_130_2024, modelo_130_2025, modelo_303_2024, modelo_303_2025

pytestmark = [pytest.mark.unit, pytest.mark.domain_outbound, pytest.mark.domain_export]


_RECORD_PUBLIC: frozenset[str] = frozenset({"ENCODING", "RECORD_LENGTH", "RECORD_SPECS", "REQUIRED_HEADER_FIELDS"})

_ENVELOPE_PUBLIC: frozenset[str] = frozenset({"ENCODING", "ENVELOPE", "REQUIRED_HEADER_FIELDS"})

#: Names that are imported-from-elsewhere in the module body but never
#: intended as part of the module's OWN public surface. Excluded from
#: the diff so we only assert on the module's authored exports.
_RE_EXPORTED_FROM_RECORD_SPEC: frozenset[str] = frozenset(
    {
        "DateFmt",
        "FicheroBoeEncoding",
        "FieldKind",
        "Justification",
        "RecordFieldSpec",
        "SegmentSpec",
        "SignedMode",
        "record_field",
        "validate_record_specs",
        "validate_segment_specs",
    }
)


def _authored_public_names(module: ModuleType) -> frozenset[str]:
    """Compute the module's authored public surface.

    Excludes (a) underscore-prefixed internals, (b) re-exports from
    ``_record_spec`` the module uses as building blocks, and (c) the
    ``annotations`` future-import symbol.

    Args:
        module: A schema module to introspect.

    Returns:
        The module's authored public name set.
    """
    raw = {n for n in dir(module) if not n.startswith("_")}
    raw -= _RE_EXPORTED_FROM_RECORD_SPEC
    raw -= {"annotations"}
    return frozenset(raw)


class TestRecordModulePublicSurface:
    """Public-surface checks for single-record schemas (Modelo 130)."""

    @pytest.mark.parametrize(
        "module",
        [modelo_130_2024, modelo_130_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_record_surface_matches_canonical(self, module: ModuleType) -> None:
        """Assert the module's authored public surface equals :data:`_RECORD_PUBLIC`."""
        authored = _authored_public_names(module)
        assert authored == _RECORD_PUBLIC, (
            f"{module.__name__} authored public surface drifted.\n"
            f"  expected: {sorted(_RECORD_PUBLIC)}\n"
            f"  actual:   {sorted(authored)}\n"
            f"  added:    {sorted(authored - _RECORD_PUBLIC)}\n"
            f"  removed:  {sorted(_RECORD_PUBLIC - authored)}"
        )

    @pytest.mark.parametrize(
        "module",
        [modelo_130_2024, modelo_130_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_record_all_matches_canonical(self, module: ModuleType) -> None:
        """Assert ``__all__`` equals :data:`_RECORD_PUBLIC`."""
        assert frozenset(module.__all__) == _RECORD_PUBLIC


class TestEnvelopeModulePublicSurface:
    """Public-surface checks for envelope schemas (Modelo 303 family)."""

    @pytest.mark.parametrize(
        "module",
        [modelo_303_2024, modelo_303_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_envelope_surface_matches_canonical(self, module: ModuleType) -> None:
        """Assert the module's authored public surface equals :data:`_ENVELOPE_PUBLIC`."""
        authored = _authored_public_names(module)
        assert authored == _ENVELOPE_PUBLIC, (
            f"{module.__name__} authored public surface drifted.\n"
            f"  expected: {sorted(_ENVELOPE_PUBLIC)}\n"
            f"  actual:   {sorted(authored)}\n"
            f"  added:    {sorted(authored - _ENVELOPE_PUBLIC)}\n"
            f"  removed:  {sorted(_ENVELOPE_PUBLIC - authored)}"
        )

    @pytest.mark.parametrize(
        "module",
        [modelo_303_2024, modelo_303_2025],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_envelope_all_matches_canonical(self, module: ModuleType) -> None:
        """Assert ``__all__`` equals :data:`_ENVELOPE_PUBLIC`."""
        assert frozenset(module.__all__) == _ENVELOPE_PUBLIC

    @pytest.mark.parametrize(
        "module",
        # Only generator-emitted modules own _SEGMENT_* constants. Clone
        # modules (e.g. modelo_303_2025) re-export ENVELOPE from their
        # source sibling without re-declaring the internals; the clone-
        # parity suite in test_modelo_303_2025.py covers them.
        [modelo_303_2024],
        ids=lambda m: m.__name__.rsplit(".", 1)[-1],
    )
    def test_envelope_segment_constants_match_tuple(self, module: ModuleType) -> None:
        """Assert ``_SEGMENT_{i}_{segment_id}`` constants align with ``ENVELOPE``.

        Every ``ENVELOPE`` entry must correspond to a
        ``_SEGMENT_{i}_{segment_id}`` module-level constant, and there
        must be no orphan constants not referenced in ``ENVELOPE``.
        This catches generator drift where the segment tuple and the
        internal constants fall out of sync (e.g. an accidental manual
        edit to ``ENVELOPE`` without regenerating).
        """
        segment_constants = {n for n in dir(module) if n.startswith("_SEGMENT_")}
        envelope = module.ENVELOPE
        # Count parity: one constant per envelope entry, no orphans.
        assert len(segment_constants) == len(envelope), (
            f"{module.__name__} has {len(segment_constants)} _SEGMENT_* constants "
            f"but {len(envelope)} entries in ENVELOPE. Either the generator "
            f"emitted orphan helpers or the tuple lost a slot."
        )
        # Identity parity: ENVELOPE[i] is the identical object stored at
        # ``_SEGMENT_{i}_{segment_id}`` — not a copy.
        for i, segment in enumerate(envelope):
            name = f"_SEGMENT_{i}_{segment.segment_id}"
            const = getattr(module, name, None)
            assert const is segment, (
                f"{module.__name__}.{name} is {const!r}, "
                f"but ENVELOPE[{i}] is {segment!r}. "
                "Generator convention broken — regenerate the module."
            )
