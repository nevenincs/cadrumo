"""Replay joins for encrypted row-source identities."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from ....core.aggregation import BindingSourceKind
from ....core.period import Period
from ....domain.calculations.registry.schema_references import RegistrySnapshotRef
from ....domain.calculations.registry.tests.authored_editions import (
    filing_year_envelope,
    newest_authored_edition,
    revision_covering,
)
from ....domain.calculations.row_source_identity import RowSourceIdentity
from ....domain.filing.schema import (
    ModeloBindingValue,
    ModeloDraft,
    ModeloValueKind,
    compute_modelo_draft_id,
    registry_schema_version,
)
from ....domain.modelos.calculation_revision import CalculationRevision
from ....domain.modelos.errors import ModeloValidationError
from ....domain.submission.models import ModeloDraftStatus
from ..row_source_identity_replay import (
    attach_revision_row_source_identities,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_RAW_IDENTITY = "opaque-inventory-activity-canary"
_DIGEST = "a" * 64


_YEAR = newest_authored_edition("100")
_REVISION = str(revision_covering("100", _YEAR).id)


def _binding(
    binding_id: str,
    *,
    row_index: int,
    source: BindingSourceKind = BindingSourceKind.INVENTORY,
) -> ModeloBindingValue:
    return ModeloBindingValue(
        binding_id=binding_id,
        value=Decimal("100.00"),
        kind=ModeloValueKind.COMPUTED,
        source=source,
        legal_refs=("ley-35-2006:art-30",),
        source_refs=("aeat-renta-2025-manual",),
        row_index=row_index,
    )


def _flag(binding_id: str, *, row_index: int, value: bool) -> ModeloBindingValue:
    return _binding(binding_id, row_index=row_index).model_copy(update={"value": value})


def _draft(binding_values: tuple[ModeloBindingValue, ...]) -> ModeloDraft:
    period = Period.from_year_and_code(_YEAR, "0A")
    snapshot = RegistrySnapshotRef(modelo="100", revision_id=_REVISION, modelo_year=_YEAR, period="0A")
    draft_id = compute_modelo_draft_id(
        modelo="100",
        period=period,
        profile_tax_id="12345678Z",
        snapshot_ref=snapshot,
        values=(),
        binding_values=binding_values,
    )
    now = datetime(filing_year_envelope().horizon, 8, 23, tzinfo=UTC)
    return ModeloDraft(
        draft_id=draft_id,
        modelo="100",
        period=period,
        profile_tax_id="12345678Z",
        subject_tax_id="12345678Z",
        snapshot_ref=snapshot,
        status=ModeloDraftStatus.BORRADOR,
        values=(),
        binding_values=binding_values,
        created_at=now,
        updated_at=now,
        schema_version=registry_schema_version(modelo="100", revision_id=_REVISION),
    )


def _identity(*, fingerprint: str = _DIGEST) -> RowSourceIdentity:
    return RowSourceIdentity(
        source_kind=BindingSourceKind.INVENTORY,
        source_row_identity=_RAW_IDENTITY,
        fingerprint=fingerprint,
    )


def _revision(
    *,
    rows: Mapping[str, Mapping[str, str]],
    identities: Mapping[tuple[str, int], RowSourceIdentity],
) -> CalculationRevision:
    return CalculationRevision.model_construct(
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo="100",
            revision_id=_REVISION,
            modelo_year=_YEAR,
            period="0A",
        ),
        row_binding_values=rows,
        row_source_identities=identities,
    )


def test_replay_attaches_exact_coordinate_without_exposing_raw_identity() -> None:
    draft = _draft((_binding("inventory-0181", row_index=1),))
    revision = _revision(
        rows={"inventory-0181": {"1": "100"}},
        identities={("inventory-0181", 1): _identity()},
    )

    replayed = attach_revision_row_source_identities(draft=draft, revision=revision)

    assert replayed.binding_values[0].row_source_identity == _identity()
    assert replayed.draft_id != draft.draft_id
    public = f"{replayed.model_dump()!r} {replayed.model_dump_json()}"
    assert _RAW_IDENTITY not in public


def test_replay_compares_a_flag_row_in_the_form_persistence_stores_it() -> None:
    draft = _draft((_flag("flag-column", row_index=1, value=True), _flag("flag-column-off", row_index=1, value=False)))
    revision = _revision(rows={"flag-column": {"1": "1"}, "flag-column-off": {"1": "0"}}, identities={})

    replayed = attach_revision_row_source_identities(draft=draft, revision=revision)

    assert [value.value for value in replayed.binding_values] == [True, False]


def test_replay_refuses_a_flag_row_whose_persisted_value_is_the_other_flag() -> None:
    draft = _draft((_flag("flag-column", row_index=1, value=True),))
    revision = _revision(rows={"flag-column": {"1": "0"}}, identities={})

    with pytest.raises(ModeloValidationError, match="does not match persisted revision row"):
        attach_revision_row_source_identities(draft=draft, revision=revision)


def test_replay_preserves_unidentified_m720_rows() -> None:
    row = _binding(
        "modelo-720-asset-row-valuation",
        row_index=1,
        source=BindingSourceKind.FOREIGN_ASSET,
    )
    replayed = attach_revision_row_source_identities(
        draft=_draft((row,)),
        revision=_revision(rows={row.binding_id: {"1": "100"}}, identities={}),
    )

    assert replayed.binding_values[0].row_source_identity is None


def test_replay_refuses_missing_and_orphan_coordinates() -> None:
    draft = _draft((_binding("inventory-0181", row_index=1),))
    with pytest.raises(ModeloValidationError, match="missing a revision row coordinate"):
        attach_revision_row_source_identities(
            draft=draft,
            revision=_revision(rows={"inventory-0181": {"2": "100"}}, identities={}),
        )
    with pytest.raises(ModeloValidationError, match="orphan revision coordinate"):
        attach_revision_row_source_identities(
            draft=draft,
            revision=_revision(
                rows={"inventory-0181": {"1": "100"}},
                identities={("inventory-0181", 2): _identity()},
            ),
        )


def test_replay_refuses_source_substitution_without_identity_canaries() -> None:
    draft = _draft(
        (_binding("inventory-0181", row_index=1, source=BindingSourceKind.FOREIGN_ASSET),),
    )
    revision = _revision(
        rows={"inventory-0181": {"1": "100"}},
        identities={("inventory-0181", 1): _identity()},
    )

    with pytest.raises(ValueError) as exc_info:
        attach_revision_row_source_identities(draft=draft, revision=revision)

    rendered = f"{exc_info.value!s} {exc_info.value!r}"
    assert _RAW_IDENTITY not in rendered
    assert _DIGEST not in rendered


def test_replay_refuses_same_coordinate_value_and_preattached_identity_substitution() -> None:
    revision = _revision(
        rows={"inventory-0181": {"1": "100"}},
        identities={("inventory-0181", 1): _identity()},
    )
    substituted_value = _binding("inventory-0181", row_index=1).model_copy(
        update={"value": Decimal("999.00")},
    )
    with pytest.raises(ModeloValidationError, match="value does not match persisted revision row"):
        attach_revision_row_source_identities(draft=_draft((substituted_value,)), revision=revision)

    substituted_identity = _binding("inventory-0181", row_index=1).model_copy(
        update={
            "row_source_identity": RowSourceIdentity(
                source_kind=BindingSourceKind.INVENTORY,
                source_row_identity="different-opaque-identity",
                fingerprint="b" * 64,
            ),
        },
    )
    with pytest.raises(ModeloValidationError, match="substituted attached identity") as exc_info:
        attach_revision_row_source_identities(draft=_draft((substituted_identity,)), revision=revision)
    assert "different-opaque-identity" not in str(exc_info.value)


def test_replay_order_and_hash_are_deterministic_and_identity_sensitive() -> None:
    rows = (
        _binding("inventory-0182", row_index=1),
        _binding("inventory-0177", row_index=1),
    )
    identities = {
        ("inventory-0182", 1): _identity(),
        ("inventory-0177", 1): _identity(),
    }
    revision = _revision(
        rows={"inventory-0182": {"1": "100"}, "inventory-0177": {"1": "100"}},
        identities=identities,
    )

    first = attach_revision_row_source_identities(draft=_draft(rows), revision=revision)
    second = attach_revision_row_source_identities(draft=_draft(tuple(reversed(rows))), revision=revision)
    changed = attach_revision_row_source_identities(
        draft=_draft(rows),
        revision=_revision(
            rows=revision.row_binding_values,
            identities={**identities, ("inventory-0182", 1): _identity(fingerprint="b" * 64)},
        ),
    )

    assert first.draft_id == second.draft_id
    assert changed.draft_id != first.draft_id
