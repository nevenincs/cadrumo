"""Real endpoint and immutable contribution proofs for M303 sectors."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....application.aggregation import (
    IvaDifferentiatedDeductionContribution,
    resolve_iva_differentiated_deduction_contributions,
)
from .....application.aggregation._iva_ledger import IvaLedgerProrrataApportionment, IvaLedgerSectorApportionment
from .....core.filing_projection_ref import (
    M303DifferentiatedDeductionProjectionField,
    M303DifferentiatedDeductionProjectionRef,
)
from .....core.iva_deduction_fact import IvaDeductionEvidenceAuthority, IvaDeductionFactKind
from .....core.prorrata_register import (
    ProrrataProvisionalProvenance,
    ProrrataRegisterRegime,
    SectorDiferenciadoLetra,
)
from .....core.resources.bundled_data import bundled_path
from .....domain.bienes_inversion.register import (
    BienesInversionSectorContribution,
    BienInversionKind,
    RegistroRegularizacionResult,
    RegistroRegularizacionRow,
)
from .....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from .....domain.iva.flow import IvaFlowDirection
from .....domain.iva.prorrata import InputClassification
from .....domain.iva.schema import IvaCategory, IvaLedgerObservationRole, IvaRateKind
from .....domain.prorrata_register.register import ProrrataRegister, ProrrataRegisterEntry, SectorDefinition
from ..corpus_catalogue import resolve_record_design_binary
from ..errors import RegistryValidationError
from ..ledger_iva_bindings import IvaLedgerObservation
from ..loader import load_catalogue_file
from ..m303_differentiated_deduction_projection import (
    project_m303_differentiated_deduction_rows,
)
from ..record_design import extract_record_design
from ..schema_input_kind import InputKind
from ..snapshot import build_snapshot
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_DESIGNS = (
    ("aeat-dr-303-2023", 2023, "2023", 228),
    ("aeat-dr-303-2024-early", 2024, "2024-early", 228),
    ("aeat-dr-303-2024-late", 2024, "2024-late", 228),
    ("aeat-dr-303-2025", 2025, "2025", 228),
    ("aeat-dr-303-2026", 2026, "2026", 233),
)


def _revision():
    modelo, catalogues = _committed_modelo("303")
    return build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="4T").revision


def _projection_refs() -> tuple[M303DifferentiatedDeductionProjectionRef, ...]:
    return tuple(
        M303DifferentiatedDeductionProjectionRef(
            projection_kind="m303_differentiated_deduction",
            slot=slot,
            field=field,
            casilla_id=str(700 + (slot - 1) * 18 + field_index),
        )
        for slot in range(1, 3)
        for field_index, field in enumerate(M303DifferentiatedDeductionProjectionField)
    )


def _register(*, percentage_b: Decimal = Decimal("60")) -> ProrrataRegister:
    definitions = (
        SectorDefinition(sector_id="a", letra=SectorDiferenciadoLetra.A, member_activity_codes=("4711",)),
        SectorDefinition(sector_id="b", letra=SectorDiferenciadoLetra.B, member_activity_codes=("6820",)),
    )
    entries = tuple(
        ProrrataRegisterEntry(
            ejercicio=2025,
            sector_id=sector_id,
            regime=ProrrataRegisterRegime.GENERAL,
            especial_transition=None,
            provisional_percentage=percentage,
            provisional_provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        )
        for sector_id, percentage in (("a", Decimal("80")), ("b", percentage_b))
    )
    return ProrrataRegister(entries=entries, sector_definitions=definitions)


def _contributions() -> tuple[IvaDifferentiatedDeductionContribution, ...]:
    kinds = tuple(
        kind for kind in IvaDeductionFactKind if kind is not IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
    )
    return tuple(
        IvaDifferentiatedDeductionContribution(
            sector_id=sector_id,
            deduction_fact_kind=kind,
            source_ledger_ids=(f"ledger-{sector_id}-{index}",),
            base_amount=Decimal(index * 100 + slot),
            deducible_iva_amount=Decimal(index * 10 + slot),
        )
        for slot, sector_id in enumerate(("a", "b"), 1)
        for index, kind in enumerate(kinds, 1)
    )


def _observation(
    ledger_id: str,
    *,
    sector_id: str | None = "a",
    kind: IvaDeductionFactKind = IvaDeductionFactKind.DOMESTIC_CURRENT,
    classification: InputClassification | None = InputClassification.COMMON,
) -> IvaLedgerObservation:
    return IvaLedgerObservation(
        ledger_id=ledger_id,
        transaction_date=date(2025, 10, 1),
        category=IvaCategory.DOMESTIC_GENERAL,
        rate_kind=IvaRateKind.GENERAL,
        flow_direction=IvaFlowDirection.SOPORTADO,
        base_amount=Decimal("100"),
        iva_amount=Decimal("20"),
        input_classification=classification,
        prorrata_sector_id=sector_id,
        deduction_fact_kind=kind,
        deduction_provenance=IvaDeductionClassificationProvenance(
            authority=(
                IvaDeductionEvidenceAuthority.BIENES_INVERSION_REGISTER
                if kind is IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION
                else IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE
            ),
            source_locator=f"invoice:{ledger_id}",
            evidence_digest="a" * 64,
        ),
        observation_role=IvaLedgerObservationRole.SETTLEMENT,
    )


def _apportionment(
    *, regime: ProrrataRegisterRegime = ProrrataRegisterRegime.GENERAL
) -> IvaLedgerProrrataApportionment:
    return IvaLedgerProrrataApportionment(
        percentage=Decimal("50"),
        provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
        sector_apportionments=(IvaLedgerSectorApportionment(sector_id="a", percentage=Decimal("50"), regime=regime),),
    )


def test_all_36_endpoints_are_projection_only_and_fixed_to_two_rows() -> None:
    endpoints = tuple(
        item
        for item in _revision().casillas
        if tuple(item.section[:3]) == ("iva", "deducciones", "sectores_diferenciados")
    )
    assert tuple(str(item.id) for item in endpoints) == tuple(str(number) for number in range(700, 736))
    assert all(item.input_kind is InputKind.PROJECTION_ONLY for item in endpoints)
    assert all(item.formula is None and item.binding is None and not item.alternate_bindings for item in endpoints)


@pytest.mark.parametrize(("source_ref", "filing_year", "epoch", "first_offset"), _DESIGNS)
def test_real_dp30305_geometry_is_exact_for_every_revision(
    source_ref: str, filing_year: int, epoch: str, first_offset: int
) -> None:
    catalogues = load_catalogue_file(bundled_path("registry", "aeat", "legal", "iva.toml"))
    resolved = resolve_record_design_binary(
        bundled_path(), catalogues.sources, source_ref=source_ref, filing_year=filing_year, design_epoch=epoch
    )
    sheet = next(item for item in extract_record_design(resolved.path).accept_partial() if item.name == "DP30305")
    fields = sheet.fields[30:66]
    assert tuple(field.offset for field in fields) == tuple(first_offset + 17 * index for index in range(36))
    assert all(field.length == 17 for field in fields)
    assert (
        tuple(f"[{number}]" in field.description for number, field in zip(range(700, 736), fields, strict=True))
        == (True,) * 36
    )


def test_apportioned_contributions_and_regularisation_project_once() -> None:
    regularisation = RegistroRegularizacionResult(
        regularizacion_year=2025,
        rows=(
            RegistroRegularizacionRow(
                identifier="asset-a",
                kind=BienInversionKind.MUEBLE,
                prorrata_sector_id="a",
                prorrata_anio_pct=Decimal("80"),
                result=None,
            ),
            RegistroRegularizacionRow(
                identifier="asset-b",
                kind=BienInversionKind.MUEBLE,
                prorrata_sector_id="b",
                prorrata_anio_pct=Decimal("60"),
                result=None,
            ),
        ),
        proposed_casilla_43=Decimal("12"),
        computed_count=2,
        pending_percentage_count=0,
        sector_contributions=(
            BienesInversionSectorContribution(asset_id="asset-a", prorrata_sector_id="a", amount=Decimal("5")),
            BienesInversionSectorContribution(asset_id="asset-b", prorrata_sector_id="b", amount=Decimal("7")),
        ),
    )
    projection = project_m303_differentiated_deduction_rows(
        projection_refs=_projection_refs(),
        register=_register(),
        ejercicio=2025,
        contributions=_contributions(),
        regularisation_result=regularisation,
    )
    assert tuple((row.slot, row.sector_id, row.percentage) for row in projection) == (
        (1, "a", Decimal("80")),
        (2, "b", Decimal("60")),
    )
    assert tuple(str(item.projection_ref.casilla_id) for row in projection for item in row.endpoints) == tuple(
        str(number) for number in range(700, 736)
    )
    assert projection[0].endpoints[-2].value == Decimal("5")
    assert projection[0].endpoints[-1].value == sum(
        (item.deducible_iva_amount for item in _contributions() if item.sector_id == "a"), Decimal("5")
    )


def test_projection_refuses_incomplete_or_double_consumed_sources() -> None:
    contributions = _contributions()
    with pytest.raises(RegistryValidationError, match="incomplete apportioned source"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(), register=_register(), ejercicio=2025, contributions=contributions[:-1]
        )
    with pytest.raises(RegistryValidationError, match="double-consumed"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(),
            register=_register(),
            ejercicio=2025,
            contributions=(*contributions, contributions[0]),
        )


def test_canonical_aggregation_emits_apportioned_sector_kind_contributions() -> None:
    provenance = IvaDeductionClassificationProvenance(
        authority=IvaDeductionEvidenceAuthority.INVOICE_EVIDENCE,
        source_locator="invoice:sector-a",
        evidence_digest="a" * 64,
    )
    observations = tuple(
        IvaLedgerObservation(
            ledger_id=f"input-{index}",
            transaction_date=date(2025, 10, index),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("100"),
            iva_amount=Decimal("20"),
            input_classification=classification,
            prorrata_sector_id="a",
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=provenance,
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        )
        for index, classification in enumerate(
            (InputClassification.EXCLUSIVELY_DEDUCTIBLE, InputClassification.COMMON), 1
        )
    )
    apportioned = resolve_iva_differentiated_deduction_contributions(
        _revision(),
        observations,
        apportionment=IvaLedgerProrrataApportionment(
            percentage=Decimal("50"),
            provenance=ProrrataProvisionalProvenance.CARRIED_PRIOR_DEFINITIVA,
            sector_apportionments=(
                IvaLedgerSectorApportionment(
                    sector_id="a", percentage=Decimal("50"), regime=ProrrataRegisterRegime.ESPECIAL
                ),
            ),
        ),
    )
    domestic = next(
        item
        for item in apportioned
        if item.sector_id == "a" and item.deduction_fact_kind is IvaDeductionFactKind.DOMESTIC_CURRENT
    )
    assert domestic.base_amount == Decimal("200")
    assert domestic.deducible_iva_amount == Decimal("30")


@pytest.mark.parametrize(
    ("observations", "message"),
    (
        ((_observation("same"), _observation("same")), "duplicate ledger identity"),
        ((_observation("missing", sector_id=None),), "missing or unknown sectors"),
        ((_observation("unknown", sector_id="unknown"),), "missing or unknown sectors"),
    ),
)
def test_canonical_aggregation_refuses_unattributable_duplicate_and_wrong_owner_rows(
    observations: tuple[IvaLedgerObservation, ...], message: str
) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_iva_differentiated_deduction_contributions(_revision(), observations, apportionment=_apportionment())


def test_especial_common_use_must_be_explicit() -> None:
    with pytest.raises(ValueError, match="common-use classification must be explicit"):
        resolve_iva_differentiated_deduction_contributions(
            _revision(),
            (_observation("implicit-common", classification=None),),
            apportionment=_apportionment(regime=ProrrataRegisterRegime.ESPECIAL),
        )


def test_wrong_owner_regularisation_cannot_become_a_ledger_observation() -> None:
    with pytest.raises(ValueError, match="emitted only by the bienes-inversion owner"):
        _observation("wrong-owner", kind=IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION)


def test_projector_refuses_reused_source_ledger_across_kinds() -> None:
    contributions = list(_contributions())
    contributions[1] = contributions[1].model_copy(update={"source_ledger_ids": contributions[0].source_ledger_ids})
    with pytest.raises(RegistryValidationError, match="source ledgers are double-consumed"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(), register=_register(), ejercicio=2025, contributions=contributions
        )


def test_projector_refuses_wrong_owner_contribution_even_when_structurally_forged() -> None:
    contributions = list(_contributions())
    contributions[0] = contributions[0].model_copy(
        update={"deduction_fact_kind": IvaDeductionFactKind.INVESTMENT_GOODS_REGULARISATION}
    )
    with pytest.raises(RegistryValidationError, match="cannot enter the ordinary deduction contribution channel"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(), register=_register(), ejercicio=2025, contributions=contributions
        )


@pytest.mark.parametrize(
    ("entry", "message"),
    (
        (
            ProrrataRegisterEntry(
                ejercicio=2025, sector_id="a", regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None
            ),
            "no applicable regime",
        ),
        (
            ProrrataRegisterEntry(
                ejercicio=2025, sector_id="a", regime=ProrrataRegisterRegime.GENERAL, especial_transition=None
            ),
            "no resolved percentage",
        ),
    ),
)
def test_projector_refuses_inactive_or_percentage_less_active_sector(
    entry: ProrrataRegisterEntry, message: str
) -> None:
    register = _register().model_copy(update={"entries": (entry, _register().entry_for(2025, sector_id="b"))})
    with pytest.raises(RegistryValidationError, match=message):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(), register=register, ejercicio=2025, contributions=_contributions()
        )


def test_projector_refuses_unlinked_and_duplicate_regularisation_assets() -> None:
    row = RegistroRegularizacionRow(
        identifier="asset-a",
        kind=BienInversionKind.MUEBLE,
        prorrata_sector_id="a",
        prorrata_anio_pct=Decimal("80"),
        result=None,
    )
    unlinked = RegistroRegularizacionResult(
        regularizacion_year=2025,
        rows=(row,),
        proposed_casilla_43=Decimal("1"),
        computed_count=1,
        pending_percentage_count=0,
        sector_contributions=(
            BienesInversionSectorContribution(asset_id="asset-x", prorrata_sector_id="a", amount=Decimal("1")),
        ),
    )
    with pytest.raises(RegistryValidationError, match="no canonical asset row"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(),
            register=_register(),
            ejercicio=2025,
            contributions=_contributions(),
            regularisation_result=unlinked,
        )
    duplicated = RegistroRegularizacionResult(
        regularizacion_year=2025,
        rows=(row,),
        proposed_casilla_43=Decimal("2"),
        computed_count=2,
        pending_percentage_count=0,
        sector_contributions=(
            BienesInversionSectorContribution(asset_id="asset-a", prorrata_sector_id="a", amount=Decimal("1")),
            BienesInversionSectorContribution(asset_id="asset-a", prorrata_sector_id="a", amount=Decimal("1")),
        ),
    )
    with pytest.raises(RegistryValidationError, match="double-consumed"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(),
            register=_register(),
            ejercicio=2025,
            contributions=_contributions(),
            regularisation_result=duplicated,
        )


def test_projector_refuses_regularisation_asset_sector_mismatch() -> None:
    result = RegistroRegularizacionResult(
        regularizacion_year=2025,
        rows=(
            RegistroRegularizacionRow(
                identifier="asset-a",
                kind=BienInversionKind.MUEBLE,
                prorrata_sector_id="a",
                prorrata_anio_pct=Decimal("80"),
                result=None,
            ),
        ),
        proposed_casilla_43=Decimal("1"),
        computed_count=1,
        pending_percentage_count=0,
        sector_contributions=(
            BienesInversionSectorContribution(asset_id="asset-a", prorrata_sector_id="b", amount=Decimal("1")),
        ),
    )
    with pytest.raises(RegistryValidationError, match="asset and contribution sectors differ"):
        project_m303_differentiated_deduction_rows(
            projection_refs=_projection_refs(),
            register=_register(),
            ejercicio=2025,
            contributions=_contributions(),
            regularisation_result=result,
        )
