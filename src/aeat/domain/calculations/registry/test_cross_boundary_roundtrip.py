"""Strict cross-domain roundtrip tests.

Every test asserts a deeply-populated pydantic model survives a JSON
round-trip with byte-for-byte structural equality. Tests are deliberately
strict and fail-fast: when the typed schema does not yet carry a field
that the boundary needs, the test fails with a typed pydantic error or
an AttributeError. There are no xfail markers, no ``skip`` calls, no
mocks, no tautological re-derivations.

A test that fails today is a measurement that the structural work it
describes has not landed yet. A test that passes today is a measurement
that the typed schema preserves identity across the boundary.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import get_type_hints

import pytest

from ...filing._schema import FilingDraft, FilingDraftStatus, FilingValue, FilingValueKind
from ...modelos._calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from ._bindings import (
    CasillaObservation,
    RegistryFilingObservation,
)
from ._schema import LiveCrossReferenceDecision

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


# ---------------------------------------------------------------------------
# Calculation runtime observations
# ---------------------------------------------------------------------------


def test_casilla_observation_full_roundtrip() -> None:
    """Every typed field on a CasillaObservation survives JSON round-trip.

    Populates every optional field (formula_id, operand_refs, operand_values,
    legal_refs, source_refs) with non-trivial content so JSON round-trip
    failure is detectable by strict equality alone.
    """

    original = CasillaObservation(
        casilla_id="iva.resultado-regimen-general",
        value=Decimal("12345.67"),
        formula_id="iva.formula.resultado",
        operand_refs=("iva.devengado", "iva.deducible"),
        operand_values=(Decimal("20000.00"), Decimal("7654.33")),
        legal_refs=("LIVA.art-21", "LIVA.art-94"),
        source_refs=("BOE.LIVA.1992", "AEAT.IVA.2025"),
    )

    roundtripped = CasillaObservation.model_validate_json(original.model_dump_json())

    assert roundtripped == original
    # Deep-data witnesses: each tuple element must survive shape and order.
    assert roundtripped.operand_refs == original.operand_refs
    assert roundtripped.operand_values == original.operand_values
    assert roundtripped.legal_refs == original.legal_refs
    assert roundtripped.source_refs == original.source_refs


def test_registry_filing_observation_preserves_observation_tuple() -> None:
    """``RegistryFilingObservation.observations`` is the canonical typed envelope.

    A round-trip must preserve every typed ``CasillaObservation`` in the
    tuple. Any boundary that dropped the typed envelope and serialized only
    the ``casilla_values`` mapping would fail this test because the inverse
    mapping would lose ``formula_id`` / ``operand_refs`` / ``legal_refs`` /
    ``source_refs``.
    """

    original = RegistryFilingObservation(
        modelo="303",
        filing_year=2025,
        period="1T",
        observations=(
            CasillaObservation(
                casilla_id="iva.devengado",
                value=Decimal("20000.00"),
                formula_id=None,
                operand_refs=(),
                operand_values=(),
                legal_refs=("LIVA.art-21",),
                source_refs=("BOE.LIVA.1992",),
            ),
            CasillaObservation(
                casilla_id="iva.resultado-regimen-general",
                value=Decimal("12345.67"),
                formula_id="iva.formula.resultado",
                operand_refs=("iva.devengado", "iva.deducible"),
                operand_values=(Decimal("20000.00"), Decimal("7654.33")),
                legal_refs=("LIVA.art-94",),
                source_refs=("AEAT.IVA.2025",),
            ),
        ),
    )

    roundtripped = RegistryFilingObservation.model_validate_json(
        original.model_dump_json(),
    )

    assert roundtripped == original
    # The computed casilla_values view derives from observations; the
    # roundtrip must preserve the underlying observations, not just the view.
    assert len(roundtripped.observations) == 2
    assert all(isinstance(o, CasillaObservation) for o in roundtripped.observations)
    assert roundtripped.observations[1].formula_id == "iva.formula.resultado"
    assert roundtripped.observations[1].operand_values == (
        Decimal("20000.00"),
        Decimal("7654.33"),
    )


# ---------------------------------------------------------------------------
# Schema-level structural assertions
#
# These tests probe the type of declared fields directly rather than
# instances. They fail when a regressed field has not been re-typed yet.
# ---------------------------------------------------------------------------


def test_live_cross_reference_decision_oracle_id_is_typed() -> None:
    """``LiveCrossReferenceDecision.oracle_id`` must be the ``OracleId`` typed alias.

    Fails today because the field is declared as ``str | None``. When the
    oracle-id typing work lands and the field becomes
    ``OracleId | None``, this test passes.
    """

    hints = get_type_hints(LiveCrossReferenceDecision, include_extras=True)
    oracle_hint = hints.get("oracle_id")
    assert oracle_hint is not None, "oracle_id field is absent from LiveCrossReferenceDecision"
    rendered = repr(oracle_hint)
    # OracleId is an Annotated[str, Field(...)] alias declared in _ids.py.
    # The repr must reference the alias, not bare str.
    assert "OracleId" in rendered, (
        f"LiveCrossReferenceDecision.oracle_id is {rendered!r}; "
        "expected the OracleId typed alias from _ids.py"
    )


def test_filing_draft_carries_typed_subject_identity() -> None:
    """``FilingDraft`` must carry a typed ``subject_tax_id`` field.

    Fails today because only ``profile_tax_id: str`` exists on the model.
    The structural intent recorded in the linkage-audit inventory is that
    the filing-grade subject identity is a typed value object propagated
    from the profile substrate, not a bare ``str``.
    """

    hints = get_type_hints(FilingDraft, include_extras=True)
    assert "subject_tax_id" in hints, (
        "FilingDraft has no subject_tax_id field. "
        "Identity propagation through the filing chain is not wired."
    )


def test_filing_draft_snapshot_ref_replaces_schema_version() -> None:
    """``FilingDraft`` participates in ``draft_id`` hash via a typed snapshot reference.

    Fails today because ``schema_version: str`` is still in the hash basis.
    A bare-string ``schema_version`` cannot be re-resolved against the
    registry; a typed ``snapshot_ref`` (modelo + revision + filing year +
    period + content hash) can.
    """

    hints = get_type_hints(FilingDraft, include_extras=True)
    assert "snapshot_ref" in hints, (
        "FilingDraft has no snapshot_ref field. "
        "The hash basis still relies on the bare-string schema_version."
    )


# ---------------------------------------------------------------------------
# Filing-draft roundtrip
# ---------------------------------------------------------------------------


def test_filing_draft_full_roundtrip() -> None:
    """A FilingDraft with a values tuple survives JSON round-trip strictly.

    Establishes the baseline that the existing filing-draft schema is
    JSON-serializable end-to-end. When ``subject_tax_id`` / ``snapshot_ref``
    are added, this test will need the new fields populated; if the model
    starts losing fields during the migration, this test will fail.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    original = FilingDraft(
        draft_id="f" * 64,
        modelo="303",
        period="2025Q1",
        profile_tax_id="12345678Z",
        status=FilingDraftStatus.DRAFT,
        values=(
            FilingValue(
                casilla_id="iva.devengado",
                value=Decimal("20000.00"),
                kind=FilingValueKind.LITERAL,
                source="user-supplied",
            ),
            FilingValue(
                casilla_id="iva.deducible",
                value=Decimal("7654.33"),
                kind=FilingValueKind.LITERAL,
                source="user-supplied",
            ),
            FilingValue(
                casilla_id="iva.resultado-regimen-general",
                value=Decimal("12345.67"),
                kind=FilingValueKind.COMPUTED,
                source="computed from iva.devengado - iva.deducible",
                formula_trace=("iva.devengado", "iva.deducible"),
            ),
        ),
        binding_values=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
        notes="",
    )

    roundtripped = FilingDraft.model_validate_json(original.model_dump_json())

    assert roundtripped == original
    assert tuple(v.casilla_id for v in roundtripped.values) == tuple(
        v.casilla_id for v in original.values
    )
    assert tuple(v.value for v in roundtripped.values) == tuple(
        v.value for v in original.values
    )
    # formula_trace MUST survive round-trip: the test fails if any
    # boundary erases the computation provenance.
    computed = next(
        v for v in roundtripped.values if v.kind is FilingValueKind.COMPUTED
    )
    assert computed.formula_trace == ("iva.devengado", "iva.deducible")


def test_filing_draft_subject_tax_id_validates_at_boundary() -> None:
    """``FilingDraft.subject_tax_id`` runs the AEAT NIF/NIE/CIF checksum.

    A malformed identifier must raise a pydantic ValidationError at
    construction time, not surface downstream as a silent typed-str.
    """

    import pytest as _pytest
    from pydantic import ValidationError

    now = datetime.now(UTC).replace(microsecond=0)
    common_kwargs = dict(
        draft_id="f" * 64,
        modelo="303",
        period="2025Q1",
        profile_tax_id="12345678Z",
        status=FilingDraftStatus.DRAFT,
        values=(),
        binding_values=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
    )

    # 12345678Z is a valid Spanish NIF (checksum letter for 12345678 is Z).
    valid = FilingDraft(subject_tax_id="12345678Z", **common_kwargs)
    assert valid.subject_tax_id == "12345678Z"

    # Same digits with a wrong checksum letter must fail at validation.
    with _pytest.raises(ValidationError):
        FilingDraft(subject_tax_id="12345678A", **common_kwargs)


def test_filing_draft_snapshot_ref_full_roundtrip() -> None:
    """A populated ``RegistrySnapshotRef`` survives strict JSON round-trip on FilingDraft."""

    from ._schema import RegistrySnapshotRef

    now = datetime.now(UTC).replace(microsecond=0)
    ref = RegistrySnapshotRef(
        modelo="303",
        revision_id="2025-y-siguientes",
        filing_year=2025,
        period="1T",
    )
    original = FilingDraft(
        draft_id="f" * 64,
        modelo="303",
        period="2025Q1",
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=ref,
        status=FilingDraftStatus.DRAFT,
        values=(),
        binding_values=(),
        findings=(),
        created_at=now,
        updated_at=now,
        schema_version="schema-2025-1",
    )

    roundtripped = FilingDraft.model_validate_json(original.model_dump_json())

    assert roundtripped == original
    assert roundtripped.snapshot_ref == ref
    assert roundtripped.subject_tax_id == "12345678Z"


def test_calculation_revision_carries_typed_observations() -> None:
    """``CalculationRevision`` must persist the typed observation envelope.

    The engine emits provenance-rich entries; the persistence boundary
    historically kept only the flat ``casilla_values`` mapping and
    dropped operand_refs / operand_values / legal_refs / source_refs.
    A round-trip test asserts the typed envelope survives JSON
    serialization without value loss.
    """

    now = datetime.now(UTC).replace(microsecond=0)
    observation = CasillaObservation(
        casilla_id="iva.resultado-regimen-general",
        value=Decimal("12345.67"),
        formula_id="iva.formula.resultado",
        operand_refs=("iva.devengado", "iva.deducible"),
        operand_values=(Decimal("20000.00"), Decimal("7654.33")),
        legal_refs=("LIVA.art-94",),
        source_refs=("AEAT.IVA.2025",),
    )
    work_unit_id = "b" * 64
    casilla_values = {"iva.resultado-regimen-general": Decimal("12345.67")}
    revision = CalculationRevision(
        calculation_revision_id=derive_calculation_revision_id(
            work_unit_id=work_unit_id,
            inputs_snapshot={},
            binding_overrides={},
            casilla_values=casilla_values,
        ),
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.DRAFT,
        casilla_values=casilla_values,
        observations=(observation,),
        created_at=now,
        updated_at=now,
    )

    roundtripped = CalculationRevision.model_validate_json(revision.model_dump_json())

    assert roundtripped == revision
    assert roundtripped.observations == (observation,)
    assert roundtripped.observations[0].operand_refs == observation.operand_refs
    assert roundtripped.observations[0].operand_values == observation.operand_values
