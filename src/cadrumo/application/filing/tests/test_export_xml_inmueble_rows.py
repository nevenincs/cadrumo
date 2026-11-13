"""Two let properties reach the Modelo 100 XML as two ``Inmueble`` elements, each with its own figures.

The rows come from real profile records and ledger rows through the production
``renta_inmueble`` resolver and are rendered by the real export, for every
supported year with its own edition. The expected figures are worked by hand:
the construction share of the acquisition cost (RIRPF art. 14), 3 per 100 of it
for a whole year, the rent less the expenses and the amortisation, and the
art. 23.2 reduction at the rate of the contract's regime.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from ....domain.calculations.registry.export_xml_dictionary import xml_dictionary_entries
from ....domain.calculations.registry.renta_inmueble_bindings import (
    RentaInmuebleOriginPart,
    renta_inmueble_columns,
    renta_inmueble_origin_columns,
)
from ....domain.contribuyente.arrendamiento_record import Inquilino, InquilinoEdad
from ....domain.contribuyente.inmueble_record import AdquisicionTitulo, InmuebleRecord, ValorCatastral
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.modelos.calculation_revision_operator_layer import ATTESTED_ZERO, RowCarryAttestation
from ....domain.submission.models import ModeloDraftStatus
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ...aggregation.renta_inmueble_resolver import RentaInmuebleSourceResolver, resolve_renta_inmueble_terms
from ...aggregation.retencion_soportada_repository import RetencionSoportadaPorts
from ...aggregation.source_mesh import CalculationSourceContext, CalculationSourceResolution
from ...aggregation.tests.ledger_source_mesh_support import BUCKET_ID, InMemoryTransactionCatalogueRepository
from ...aggregation.tests.renta_inmueble_support import (
    REFERENCIA_CATASTRAL,
    expense,
    inmueble,
    lease,
    monthly_rent,
    profile_facts,
)
from ...modelo.work_profile import ModeloWorkProfile
from ..draft_construction import build_draft
from ..export_xml_dictionary import render_xml_dictionary_layout
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from .export_support import filer_with_nothing_else

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_INMUEBLE = "DatosEconomicos/TomaDatosAmpliada/Inmuebles/Inmueble"
_RENT = Decimal("950.00")
_SECOND_RENT = Decimal("600.00")
_COMUNIDAD = Decimal("540.00")


class _NoWithholding:
    def load_records(self, ejercicio: int) -> tuple[()]:
        return ()


def _filing_years(operation: PinnedAuthorityOperation) -> tuple[int, ...]:
    """The supported years whose own Modelo 100 edition lets an export be built."""
    return tuple(
        year
        for year in operation.supported_filing_years().years
        if operation.reachable_authority_grade("100", filing_year=year, period="0A") is RegistryAuthorityGrade.FILING
    )


def _provider(operation: PinnedAuthorityOperation, year: int) -> RegistrySchemaAccessor:
    return build_runtime_schema_provider(
        filing_year=year,
        period=Period.from_year_and_code(year, "0A"),
        modelos=("100",),
        operation=operation,
    )


def _property(clave: int, year: int, amount: Decimal, total: Decimal, construccion: Decimal) -> InmuebleRecord:
    return inmueble(
        clave,
        ejercicio=year,
        adquisicion_titulo=AdquisicionTitulo.ONEROSA,
        fecha_adquisicion=date(year, 1, 1),
        importe_adquisicion=amount,
        gastos_tributos_adquisicion=Decimal(1000),
        valores_catastrales=(ValorCatastral(year=year, total=total, construccion=construccion),),
    )


def _resolve(
    operation: PinnedAuthorityOperation, provider: RegistrySchemaAccessor, year: int
) -> CalculationSourceResolution:
    first_day = date(year, 1, 1)
    facts = profile_facts(
        (
            _property(0, year, Decimal(99000), Decimal(80000), Decimal(64000)),
            _property(1, year, Decimal(50000), Decimal(40000), Decimal(30000)),
        ),
        (
            lease(0, start=first_day, zona_tensionada=False),
            lease(
                1,
                inmueble_clave=1,
                start=first_day,
                zona_tensionada=False,
                inquilinos=(Inquilino(nif="12345678Z", franja_edad=InquilinoEdad.OTRA, extranjero=False),),
            ),
        ),
    )
    transactions = (
        *monthly_rent(year, amount=_RENT),
        *monthly_rent(year, amount=_SECOND_RENT, lease_clave=1),
        expense("comunidad", concept="comunidad", amount=_COMUNIDAD, booked=date(year, 3, 10)),
    )
    return _resolution(operation, provider, year, facts, transactions)


def _resolution(
    operation: PinnedAuthorityOperation,
    provider: RegistrySchemaAccessor,
    year: int,
    facts: dict[str, str],
    transactions: tuple[Transaction, ...],
    statements: tuple[RowCarryAttestation, ...] = (),
) -> CalculationSourceResolution:
    repository = InMemoryTransactionCatalogueRepository(bucket_id=BUCKET_ID)
    repository.save(TransactionCatalogue.from_transactions(transactions))
    profile = ModeloWorkProfile(
        record=create_user_profile_record(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=BUCKET_ID,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X0001500M"),
                *(UserProfileFact(path=path, value=value) for path, value in facts.items()),
            ),
            context=operation.profile_create_context(),
        ),
        profile_decode_context=operation.profile_decode_context(),
    )
    return RentaInmuebleSourceResolver(
        transaction_repository=repository,
        retencion_soportada_ports=RetencionSoportadaPorts(repository=_NoWithholding()),
    ).resolve(
        CalculationSourceContext(
            bucket_id=BUCKET_ID,
            modelo="100",
            filing_year=year,
            period=Period.from_year_and_code(year, "0A"),
            revision=provider.get_snapshot("100").revision,
            profile=profile,
            caller_row_attestations=statements,
        )
    )


def _draft(provider: RegistrySchemaAccessor, year: int, resolution: CalculationSourceResolution) -> ModeloDraft:
    rows: dict[str, dict[str, ModeloInputScalar]] = {}
    for (binding_id, row_index), value in resolution.row_binding_values.items():
        rows.setdefault(str(binding_id), {})[str(row_index)] = value
    stated: dict[str, ModeloInputValue] = {
        **filer_with_nothing_else(provider),
        **{str(binding_id): value for binding_id, value in resolution.binding_values.items()},
        **rows,
    }
    amounts = {key: value for key, value in stated.items() if isinstance(value, Decimal)}
    bound_boxes = resolve_available_bound_inputs_by_casilla_id(provider.get_snapshot("100").revision, amounts)
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="X0001500M", display_name="DECLARANTE PRUEBA"),
        inputs={**bound_boxes, **stated},
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _field(element: Element, fields: dict[str | None, str], casilla: str) -> str | None:
    return element.findtext(fields[casilla])


def test_each_let_property_is_one_inmueble_element_with_its_own_net_chain_in_every_supported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    years = _filing_years(operation)
    assert years
    for year in years:
        provider = _provider(operation, year)
        layout = provider.get_snapshot("100").revision.export_layouts[0]
        fields = {
            entry.casilla_id: entry.field_id
            for entry in xml_dictionary_entries(
                layout,
                sources=provider.sources,
                source_payloads=provider.source_payloads,
                casillas=provider.get_snapshot("100").revision.casillas,
            )
            if f"/{_INMUEBLE}/" in entry.path
        }
        draft = _draft(provider, year, _resolve(operation, provider, year))
        payload = render_xml_dictionary_layout(
            layout, draft=draft, headers={}, aux_version="001", schema_provider=provider
        )

        first, second = ElementTree.fromstring(payload).findall(_INMUEBLE)
        rules = resolve_renta_inmueble_terms(
            modelo="100",
            revision_id=provider.get_snapshot("100").revision.id,
            devengo=date(year, 12, 31),
            operation=operation,
        ).reduction_rules
        legacy = date(year, 12, 31) < rules.regime_start or date(year, 1, 1) < rules.contract_cut_off
        rate = Decimal("0.60") if legacy else Decimal("0.50")
        # 100.000 x 80 % = 80.000 and 51.000 x 75 % = 38.250, each above its cadastral construction value.
        first_net = _RENT * 12 - _COMUNIDAD - Decimal("2400.00")
        second_net = _SECOND_RENT * 12 - Decimal("1147.50")
        first_reduced = first_net - (first_net * rate).quantize(Decimal("0.01"))
        second_reduced = second_net - (second_net * rate).quantize(Decimal("0.01"))

        assert _field(first, fields, "0102") == str(_RENT * 12), year
        assert _field(first, fields, "0125") == "80.00", year
        assert _field(first, fields, "0130") == "80000.00", year
        assert _field(first, fields, "0131") == "2400.00", year
        assert _field(first, fields, "0149") == str(first_net), year
        assert _field(first, fields, "0154") == str(first_reduced), year
        assert _field(second, fields, "0102") == str(_SECOND_RENT * 12), year
        assert _field(second, fields, "0125") == "75.00", year
        assert _field(second, fields, "0130") == "38250.00", year
        assert _field(second, fields, "0131") == "1147.50", year
        assert _field(second, fields, "0154") == str(second_reduced), year
        values = {value.casilla_id: value.value for value in draft.values}
        assert values["0156"] == first_reduced + second_reduced, year


def test_an_earlier_excess_reaches_anexo_c1_of_its_inmueble_with_the_holder_code_in_every_supported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    years = _filing_years(operation)
    assert years
    for year in years:
        provider = _provider(operation, year)
        revision = provider.get_snapshot("100").revision
        layout = revision.export_layouts[0]
        paths = {
            entry.casilla_id: entry.path.split(f"/{_INMUEBLE}/", 1)[1]
            for entry in xml_dictionary_entries(
                layout, sources=provider.sources, source_payloads=provider.source_payloads, casillas=revision.casillas
            )
            if f"/{_INMUEBLE}/" in entry.path
        }
        boxes = {binding.id: str(column.target_casilla_id) for binding, column in renta_inmueble_columns(revision)}
        origins = renta_inmueble_origin_columns(revision)
        start = date(year - 2, 1, 1)
        record = inmueble(
            0,
            ejercicio=year,
            fecha_adquisicion=date(year - 3, 6, 1),
            importe_adquisicion=Decimal(99000),
            gastos_tributos_adquisicion=Decimal(1000),
            valores_catastrales=(ValorCatastral(year=year, total=Decimal(80000), construccion=Decimal(64000)),),
            arrendado_desde=start,
        )
        facts = profile_facts((record,), (lease(0, start=start, zona_tensionada=False),))
        # Let since two ejercicios back: the newest origin year left 300 pending, the one before it nothing.
        newest, older = origins[RentaInmuebleOriginPart.OPENING][1], origins[RentaInmuebleOriginPart.OPENING][2]
        statements = (
            RowCarryAttestation(binding_id=newest.id, source_row_identity="inmueble:0", amount="300"),
            RowCarryAttestation(
                binding_id=older.id, source_row_identity="inmueble:0", amount=ATTESTED_ZERO, absent=True
            ),
        )
        resolution = _resolution(operation, provider, year, facts, monthly_rent(year, amount=_RENT), statements)
        payload = render_xml_dictionary_layout(
            layout, draft=_draft(provider, year, resolution), headers={}, aux_version="001", schema_provider=provider
        )
        (element,) = ElementTree.fromstring(payload).findall(_INMUEBLE)

        filed = {binding_id: element.findtext(paths[casilla]) for binding_id, casilla in boxes.items()}

        applied = origins[RentaInmuebleOriginPart.APPLIED][1].id
        carried = origins[RentaInmuebleOriginPart.CARRIED][1].id
        holder = next(
            binding.id for binding, column in renta_inmueble_columns(revision) if column.row_field == "anexo_c1_titular"
        )
        reference = next(
            binding.id
            for binding, column in renta_inmueble_columns(revision)
            if column.row_field == "anexo_c1_referencia_catastral"
        )
        # The XSD's tipo_Titular codes the declarant 2; the 300 applies whole, within the rent, and carries nothing on.
        assert filed[holder] == "2", year
        assert filed[reference] == REFERENCIA_CATASTRAL, year
        assert filed[newest.id] == "300.00", year
        assert filed[applied] == "300.00", year
        assert filed[carried] is None, year
        assert filed[older.id] is None, year
        assert element.findtext(paths["0103"]) == "300.00", year
        assert element.findtext(paths["0104"]) == "300.00", year
