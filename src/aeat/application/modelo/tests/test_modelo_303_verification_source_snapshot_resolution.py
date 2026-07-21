"""Regression for the Modelo 303 ``verification_source`` snapshot-resolution failure (CDC W09.P41.S341).

A persona-simulation round observed a Modelo 303 registry-build failure whose
signature was the extraction-profile round-trip gate refusing the profile with
*"sets corpus_round_trip_verified = true but verification_source is not set"*.
The root cause was the pre-hardening registry loader cache serving a **partial**
view of a revision fragment while peer agents wrote registry TOML in the shared
worktree: a mid-write ``extraction_profiles`` fragment could be read with
``corpus_round_trip_verified = true`` already present but ``verification_source``
not yet written, tripping the round-trip gate at snapshot build.

Commit ``688ed6713`` ("fix(registry): harden loader cache against concurrent
writes") closed that root cause: the registry-tree fingerprint now recursively
covers every ``revisions/**/*.toml`` fragment (so an ``extraction_profiles``
fragment edit invalidates the cache), and a concurrent directory change during
fingerprinting fails loudly with *"retry after concurrent registry writes
settle"* rather than serving a partial. The M303 verification_source failure is
therefore a **verify-close**: it no longer reproduces at HEAD.

These tests pin the closed state at the application-facing resolution boundary
(the path the persona's verify flow used):

* ``test_m303_snapshot_resolves_extraction_profile_verification_source`` proves
  the committed M303 data, resolved through the production
  :class:`~domain.calculations.registry.ValidatedRegistryAuthority` with the
  loader caches cleared, validates cleanly and surfaces a well-formed extraction
  profile — every ``corpus_round_trip_verified`` ``declaracion_pdf`` profile
  carries a non-``None`` ``verification_source``. If a partial or mis-tagged
  profile ever reached the M303 snapshot again, ``validate_modelo`` would raise.

* ``test_m303_round_trip_gate_still_fires_on_the_partial_shape`` is the
  anti-tautology guard: it feeds the round-trip gate the exact partial shape the
  race produced (round-trip verified, ``verification_source = None``) against the
  real justificante corpus and asserts the gate still refuses it. Without this,
  the positive test above could pass vacuously if the gate were ever silenced.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.resources import bundled_path, resources
from ....domain.calculations.registry._loader import clear_fingerprint_cache
from ....domain.calculations.registry._schema_extraction import (
    ExtractionProfileDefinition,
    ExtractionTargetDefinition,
)
from ....domain.calculations.registry._validate_extraction_profiles import (
    validate_declaracion_pdf_round_trip_gate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_MODELO_303 = "303"

# Mirror ``RegistryValidator._justificante_corpus_root``: bundled_path() resolves
# to src/aeat/_data; the fixture tree lives one level up under tests/fixtures.
_JUSTIFICANTE_CORPUS_ROOT = bundled_path().resolve().parents[0] / "tests" / "fixtures" / "justificantes"


def test_m303_snapshot_resolves_extraction_profile_verification_source() -> None:
    """M303 validates and resolves a well-formed extraction profile at HEAD.

    Reproduces the persona's production resolution path with the loader caches
    cleared (the "fresh tmp_path with cleared registry caches" the step calls
    for): ``validate_modelo`` runs the registry validation that includes the
    extraction-profile round-trip gate, and the resolved revisions must carry a
    non-``None`` ``verification_source`` on every ``corpus_round_trip_verified``
    ``declaracion_pdf`` profile. A regressed partial/stale read would make
    ``validate_modelo`` raise ``RegistryValidationError`` here.
    """
    clear_fingerprint_cache()
    authority = resources().modelos.authority

    # Production validation path — runs the round-trip gate for M303. Must not raise.
    modelo = authority.validate_modelo(_MODELO_303)

    checked: list[str] = []
    for revision_id, revision in modelo.revisions.items():
        for profile in revision.extraction_profiles:
            if profile.surface != "declaracion_pdf" or not profile.corpus_round_trip_verified:
                continue
            checked.append(f"{revision_id}/{profile.id}")
            assert profile.verification_source is not None, (
                f"M303 revision {revision_id!r} extraction profile {profile.id!r} is "
                f"corpus_round_trip_verified but verification_source is None — the exact "
                f"partial-read shape that the pre-688ed6713 loader race surfaced at snapshot build"
            )

    assert checked, (
        "expected at least one corpus_round_trip_verified declaracion_pdf profile on M303; "
        "the regression is dormant if none is present"
    )


def test_m303_round_trip_gate_still_fires_on_the_partial_shape() -> None:
    """Anti-tautology guard: the round-trip gate still refuses the partial shape.

    The gate that would catch a regressed M303 partial must remain live. Feeding
    it the exact race-produced shape (``corpus_round_trip_verified = true`` with
    ``verification_source = None``) against the real justificante corpus must
    return the ``verification_source is not set`` refusal — otherwise the
    positive resolution test above is vacuous.
    """
    partial = ExtractionProfileDefinition(
        id="modelo-303-declaracion-pdf",
        surface="declaracion_pdf",
        artefact_kind="declaration_pdf",
        accepted_artefact_kinds=("declaration_pdf",),
        parser="aeat.adapters.inbound.declaracion.parser.parse",
        target_casillas=(
            ExtractionTargetDefinition(
                casilla_id="01",
                match_strategy="numeric_casilla",
                value_kind="amount",
            ),
        ),
        confidence="strict",
        corpus_round_trip_verified=True,
        verification_source=None,
        min_coverage=Decimal("1"),
        failure_semantics="fail_hard",
        legal_refs=("ley-37-1992:art-164",),
        source_refs=("aeat-manual",),
    )

    errors = validate_declaracion_pdf_round_trip_gate(
        "M303",
        _MODELO_303,
        partial,
        _JUSTIFICANTE_CORPUS_ROOT,
    )

    assert any("verification_source is not set" in error for error in errors), (
        f"round-trip gate must refuse a corpus_round_trip_verified profile with no "
        f"verification_source; got {errors!r}"
    )


def test_justificante_corpus_root_exists_so_the_guard_is_not_dormant() -> None:
    """The M303 justificante corpus must exist, or the guard silently no-ops.

    ``validate_declaracion_pdf_round_trip_gate`` only reaches its
    ``verification_source`` branch when a corpus fixture PDF exists for the
    modelo; without one it returns ``[]`` and the anti-tautology guard would pass
    vacuously.
    """
    fixture_dir = _JUSTIFICANTE_CORPUS_ROOT / _MODELO_303
    assert fixture_dir.is_dir() and any(fixture_dir.glob("*.pdf")), (
        f"no M303 justificante corpus PDF at {fixture_dir}; the round-trip gate guard is dormant"
    )
