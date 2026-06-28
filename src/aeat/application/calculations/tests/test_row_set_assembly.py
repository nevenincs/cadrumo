"""Contract tests for the row-set → typed observation assemblers.

Closes the loop between the pull adapter (which captures detail
rows as untyped ``RowSetCellEdit`` records) and the local-store
ingest path (which expects typed observations of the matching
domain shape). Each test exercises the assembler against
operator-typed cells loaded into a real ``ModeloRevision`` from
the registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import pytest

from ....core.resources import resources
from ....domain.calculations.registry._errors import RegistryValidationError
from .._row_set_assembly import (
    assemble_atribucion_observations,
    assemble_foreign_asset_observations,
    assemble_observations_for_grouping,
    assemble_refund_observations,
    assemble_related_party_observations,
    assemble_withholding_observations,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _Cell:
    """Structural stand-in for the pull adapter's RowSetCellEdit.

    The assemblers consume any object with ``binding`` / ``row_index`` /
    ``value`` attributes, so this lightweight dataclass keeps tests free
    of an outbound adapter import.
    """

    binding: str
    row_index: int
    value: Decimal | str | None


def _modelo(modelo_id: str, revision_id: str):
    return resources().modelos.get(modelo_id).revisions[revision_id]


def test_assemble_withholding_groups_two_perceptors_into_two_observations() -> None:
    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        _Cell("modelo-190-perceptor-row-nif", 1, "12345678A"),
        _Cell("modelo-190-perceptor-row-name", 1, "Perceptor One"),
        _Cell("modelo-190-perceptor-row-clave", 1, "A"),
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 1, Decimal("10000")),
        _Cell("modelo-190-perceptor-row-retencion-practicada", 1, Decimal("1500")),
        _Cell("modelo-190-perceptor-row-nif", 2, "87654321Z"),
        _Cell("modelo-190-perceptor-row-name", 2, "Perceptor Two"),
        _Cell("modelo-190-perceptor-row-clave", 2, "G"),
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 2, Decimal("30000")),
        _Cell("modelo-190-perceptor-row-retencion-practicada", 2, Decimal("5500")),
    )

    observations = assemble_withholding_observations(cells, revision, filing_year=2025)

    assert len(observations) == 2
    by_nif = {obs.perceptor_tax_id: obs for obs in observations}
    assert by_nif["12345678A"].clave == "A"
    assert by_nif["12345678A"].percibido_dinerario == Decimal("10000")
    assert by_nif["12345678A"].retencion_practicada == Decimal("1500")
    assert by_nif["12345678A"].country_code == "ES"
    assert by_nif["12345678A"].transaction_date == date(2025, 12, 31)
    assert by_nif["87654321Z"].clave == "G"
    assert by_nif["87654321Z"].percibido_dinerario == Decimal("30000")


def test_assemble_withholding_synthesizes_source_id_per_row() -> None:
    """Source ids are derivable so re-pulled rows reconcile back to the same identity."""

    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        _Cell("modelo-190-perceptor-row-nif", 1, "12345678A"),
        _Cell("modelo-190-perceptor-row-clave", 1, "A"),
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 1, Decimal("100")),
    )

    observations = assemble_withholding_observations(cells, revision, filing_year=2025)

    assert observations[0].source_id == "detalle:per_perceptor_clave:row-1"


def test_assemble_withholding_decimal_strings_coerce() -> None:
    """Operators may type values as strings; assembler coerces to Decimal."""

    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        _Cell("modelo-190-perceptor-row-nif", 1, "12345678A"),
        _Cell("modelo-190-perceptor-row-clave", 1, "A"),
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 1, "5000.55"),
        _Cell("modelo-190-perceptor-row-retencion-practicada", 1, "750.25"),
    )

    observations = assemble_withholding_observations(cells, revision, filing_year=2025)

    assert observations[0].percibido_dinerario == Decimal("5000.55")
    assert observations[0].retencion_practicada == Decimal("750.25")


def test_assemble_withholding_unknown_binding_silently_dropped() -> None:
    """A cell whose binding is not declared on the revision is ignored.

    This guards against pull-adapter races where a row-set declared in
    a prior revision sneaks into a later filing's pull. The known
    bindings still produce a valid observation; the unknown ones are
    discarded rather than crashing assembly.
    """

    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        _Cell("modelo-190-perceptor-row-nif", 1, "12345678A"),
        _Cell("modelo-190-perceptor-row-clave", 1, "A"),
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 1, Decimal("100")),
        _Cell("nonexistent-binding-id", 1, "ignored-value"),
    )

    observations = assemble_withholding_observations(cells, revision, filing_year=2025)

    assert len(observations) == 1
    assert observations[0].perceptor_tax_id == "12345678A"


def test_assemble_foreign_asset_parses_iso_acquisition_date() -> None:
    revision = _modelo("720", "2013-y-siguientes")
    cells = (
        _Cell("modelo-720-asset-row-class", 1, "C"),
        _Cell("modelo-720-asset-row-country", 1, "CH"),
        _Cell("modelo-720-asset-row-currency", 1, "CHF"),
        _Cell("modelo-720-asset-row-identifier", 1, "CH-iban-001"),
        _Cell("modelo-720-asset-row-acquisition-date", 1, "2020-01-15"),
        _Cell("modelo-720-asset-row-valuation", 1, Decimal("120000")),
    )

    observations = assemble_foreign_asset_observations(cells, revision, filing_year=2025)

    assert len(observations) == 1
    obs = observations[0]
    assert obs.country_code == "CH"
    assert obs.currency_code == "CHF"
    assert obs.acquisition_date == date(2020, 1, 15)
    assert obs.valuation_amount == Decimal("120000")


def test_assemble_atribucion_caps_share_percentage_at_validation() -> None:
    """An out-of-range share triggers the AtributionMemberObservation validator."""

    revision = _modelo("184", "2015-y-siguientes")
    cells = (
        _Cell("modelo-184-member-row-nif", 1, "12345678A"),
        _Cell("modelo-184-member-row-share", 1, Decimal("150")),
        _Cell("modelo-184-member-row-base-assigned", 1, Decimal("1000")),
    )

    with pytest.raises(RegistryValidationError, match=r"share_percentage must be within \[0, 100\]"):
        assemble_atribucion_observations(cells, revision, filing_year=2025)


def test_assemble_related_party_reads_operation_kind_and_method() -> None:
    revision = _modelo("232", "2018-y-siguientes")
    cells = (
        _Cell("modelo-232-related-party-row-nif", 1, "A12345678"),
        _Cell("modelo-232-related-party-row-name", 1, "Counter SL"),
        _Cell("modelo-232-related-party-row-country", 1, "ES"),
        _Cell("modelo-232-related-party-row-operation-kind", 1, "01"),
        _Cell("modelo-232-related-party-row-tpr-method", 1, "CUP"),
        _Cell("modelo-232-related-party-row-amount", 1, Decimal("50000")),
    )

    observations = assemble_related_party_observations(cells, revision, filing_year=2025)

    assert len(observations) == 1
    obs = observations[0]
    assert obs.counterparty_tax_id == "A12345678"
    assert obs.operation_kind_code == "01"
    assert obs.transfer_pricing_method_code == "CUP"
    assert obs.amount == Decimal("50000")


def test_assemble_refund_parses_iso_operation_date() -> None:
    revision = _modelo("360", "2010-y-siguientes")
    cells = (
        _Cell("modelo-360-refund-row-member-state", 1, "FR"),
        _Cell("modelo-360-refund-row-operation-kind", 1, "01"),
        _Cell("modelo-360-refund-row-operation-date", 1, "2025-06-15"),
        _Cell("modelo-360-refund-row-supplier-nif", 1, "FR-supplier-1"),
        _Cell("modelo-360-refund-row-amount", 1, Decimal("500")),
    )

    observations = assemble_refund_observations(cells, revision, filing_year=2025)

    assert len(observations) == 1
    obs = observations[0]
    assert obs.member_state_code == "FR"
    assert obs.operation_date == date(2025, 6, 15)
    assert obs.refund_amount == Decimal("500")


def test_assemble_returns_empty_for_empty_cells() -> None:
    revision = _modelo("190", "2024-y-siguientes")

    assert assemble_withholding_observations((), revision, filing_year=2025) == ()


def test_assemble_observations_for_grouping_dispatches_per_perceptor_clave() -> None:
    from ....domain.calculations.registry import WithholdingObservation

    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        _Cell("modelo-190-perceptor-row-nif", 1, "12345678A"),
        _Cell("modelo-190-perceptor-row-clave", 1, "A"),
    )

    source_kind, observations = assemble_observations_for_grouping(
        "per_perceptor_clave",
        cells,
        revision,
        filing_year=2025,
    )

    assert source_kind == "withholding"
    assert len(observations) == 1
    obs = observations[0]
    assert isinstance(obs, WithholdingObservation)
    assert obs.perceptor_tax_id == "12345678A"


def test_assemble_observations_for_grouping_dispatches_foreign_asset() -> None:
    revision = _modelo("720", "2013-y-siguientes")
    cells = (
        _Cell("modelo-720-asset-row-class", 1, "C"),
        _Cell("modelo-720-asset-row-country", 1, "CH"),
    )

    source_kind, observations = assemble_observations_for_grouping(
        "per_foreign_asset",
        cells,
        revision,
        filing_year=2025,
    )

    assert source_kind == "foreign_asset"
    assert len(observations) == 1


def test_assemble_observations_for_grouping_rejects_unknown_grouping() -> None:
    revision = _modelo("190", "2024-y-siguientes")
    with pytest.raises(RegistryValidationError, match="has no application-layer assembler"):
        assemble_observations_for_grouping(
            "operator_clave",  # invoice/counterpart grouping; no assembler
            (),
            revision,
            filing_year=2025,
        )


# ---------------------------------------------------------------------------
# F5 — non-fabrication: mandatory AEAT fields must not be silently defaulted
# (cross-domain-handoffs-swarm-audit 2026-05-16)
# ---------------------------------------------------------------------------


def test_assemble_withholding_missing_nif_raises_not_fabricates() -> None:
    """A row missing perceptor_tax_id raises RegistryValidationError, not a fabricated value.

    The assembler previously silently defaulted country_code to ``"ES"``,
    member_tax_id to ``"A"`` etc. via hard-coded fallback strings when
    the row did not supply them. This is an AEAT-required field; a
    fabricated value would produce a filing with a legally-invalid NIF.
    The fix (``_optional_text_kwarg``) omits the kwarg entirely when the
    row does not supply it, so the ``WithholdingObservation`` pydantic model
    rejects the malformed row and the assembler wraps the pydantic
    ``ValidationError`` into a ``RegistryValidationError``.

    If this test stops raising (the assembler silently returns an
    observation with a blank or fabricated NIF), the non-fabrication
    contract has regressed.
    """

    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        # Deliberately omit perceptor_tax_id — the model's min_length=1
        # constraint must surface, not be masked by a fabricated empty-string default.
        _Cell("modelo-190-perceptor-row-clave", 1, "A"),
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 1, Decimal("10000")),
    )

    with pytest.raises(RegistryValidationError, match="perceptor_tax_id"):
        assemble_withholding_observations(cells, revision, filing_year=2025)


def test_assemble_withholding_refuses_a_row_without_clave() -> None:
    """A percepcion row carrying no clave is refused, not defaulted to "A" (RET-1 #28).

    A defaulted clave silently mis-buckets the percepcion and corrupts the
    distinct-(perceptor, clave) count ("numero de registros de tipo 2", Modelo
    190/193 Diseno de Registros). The source must supply the real clave; a missing
    one is a data error, not a silent default.
    """
    revision = _modelo("190", "2024-y-siguientes")
    cells = (
        _Cell("modelo-190-perceptor-row-nif", 1, "12345678A"),
        _Cell("modelo-190-perceptor-row-name", 1, "Perceptor Sin Clave"),
        # No clave cell for row 1 - previously silently defaulted to "A".
        _Cell("modelo-190-perceptor-row-percibido-dinerario", 1, Decimal("10000")),
        _Cell("modelo-190-perceptor-row-retencion-practicada", 1, Decimal("1500")),
    )
    with pytest.raises(RegistryValidationError, match="no clave"):
        assemble_withholding_observations(cells, revision, filing_year=2025)
