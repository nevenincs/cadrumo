"""A stored household reaches the Modelo 100 XML as one Hijo or Ascendiente per row, at the fields its bindings declare.

The rows come from a real profile record through the production profile resolver and
are rendered by the real export, for every supported filing year with its own edition. The expected text
is the official form of each field: names in the uppercase ``tipo_ApeNom`` alphabet
and dates in the ``d/m/yyyy`` form of ``tipo_Fecha``. An ascendant stated without a
NIF is refused by the schema's own requirement rather than written with one invented.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from defusedxml import ElementTree

from cadrumo.domain.user_profile.values import create_user_profile_record

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.filing.protocols import ModeloInputScalar, ModeloInputValue
from ....domain.filing.schema import ModeloDraft
from ....domain.submission.models import ModeloDraftStatus
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact
from ...modelo.profile_binding import resolve_profile_sourced_bindings
from ..draft_construction import build_draft
from ..errors import ModeloApplicationError
from ..export_xml_dictionary import refuse_incomplete_xml_dictionary_payload, render_xml_dictionary_layout
from ..export_xml_value_limits import is_xml_required_content_refusal, refused_xml_boxes
from ..runtime import ModeloOperatorProfile, RegistrySchemaAccessor, build_runtime_schema_provider
from .export_support import filer_with_nothing_else

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_BUCKET = "0de41ce4-0000-4000-8000-000000000915"
_CLOCK = datetime(1980, 5, 21, 10, 0, tzinfo=UTC)
_CHILD = "DatosIdentificativos/Hijos/Hijo"
_ASCENDANT = "DatosIdentificativos/Ascendientes/Ascendiente"
_CHILD_NIF = "00000000T"
_ASCENDANT_NIF = "00000001R"


def _household(year: int, *, ascendant_nif: str | None) -> tuple[UserProfileFact, ...]:
    child = "renta_family.descendiente.0"
    parent = "renta_family.ascendiente.0"
    return (
        UserProfileFact(path="renta_family.descendientes_count", value="1"),
        UserProfileFact(path=f"{child}.birth_date", value=date(year - 9, 3, 14).isoformat()),
        UserProfileFact(path=f"{child}.nif", value=_CHILD_NIF),
        UserProfileFact(path=f"{child}.apellidos_nombre", value="Ortega Navarro Pablo"),
        UserProfileFact(path="renta_family.ascendientes_count", value="1"),
        UserProfileFact(path=f"{parent}.birth_date", value=date(year - 78, 1, 8).isoformat()),
        UserProfileFact(path=f"{parent}.apellidos_nombre", value="Navarro Gil Carmen"),
        *(() if ascendant_nif is None else (UserProfileFact(path=f"{parent}.nif", value=ascendant_nif),)),
    )


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


def _draft(
    operation: PinnedAuthorityOperation, provider: RegistrySchemaAccessor, year: int, *, ascendant_nif: str | None
) -> ModeloDraft:
    record = create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_BUCKET,
        facts=_household(year, ascendant_nif=ascendant_nif),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=operation.profile_create_context(),
    )
    resolution = resolve_profile_sourced_bindings(
        provider.get_snapshot("100"), bucket_id=_BUCKET, profile_record=record, operation=operation
    )
    rows: dict[str, dict[str, ModeloInputScalar]] = {}
    for (binding_id, row_index), value in resolution.row_binding_values.items():
        rows.setdefault(str(binding_id), {})[str(row_index)] = value
    inputs: dict[str, ModeloInputValue] = {**filer_with_nothing_else(provider), **rows}
    return build_draft(
        modelo="100",
        period=Period.from_year_and_code(year, "0A"),
        profile=ModeloOperatorProfile(tax_id="12345678Z", display_name="DECLARANTE PRUEBA"),
        inputs=inputs,
        schema_provider=provider,
    ).model_copy(update={"status": ModeloDraftStatus.APROBADO})


def _render(provider: RegistrySchemaAccessor, draft: ModeloDraft) -> bytes:
    return render_xml_dictionary_layout(
        provider.get_snapshot("100").revision.export_layouts[0],
        draft=draft,
        headers={},
        aux_version="001",
        schema_provider=provider,
    )


def test_each_household_row_is_written_at_its_declared_fields_in_every_supported_year(
    operation: PinnedAuthorityOperation,
) -> None:
    years = _filing_years(operation)
    assert years
    for year in years:
        provider = _provider(operation, year)
        root = ElementTree.fromstring(
            _render(provider, _draft(operation, provider, year, ascendant_nif=_ASCENDANT_NIF))
        )

        (child,) = root.findall(_CHILD)
        assert child.findtext("NIFDLG") == _CHILD_NIF, year
        assert child.findtext("APENOMDLG") == "ORTEGA NAVARRO PABLO", year
        assert child.findtext("FNACDLG") == f"14/3/{year - 9}", year
        (ascendant,) = root.findall(_ASCENDANT)
        assert ascendant.findtext("DNIASDLG") == _ASCENDANT_NIF, year
        assert ascendant.findtext("APENOMDLG_ASC") == "NAVARRO GIL CARMEN", year
        assert ascendant.findtext("ANOASDLG") == f"8/1/{year - 78}", year


def test_an_ascendant_without_a_nif_is_refused_for_the_nif_the_schema_requires(
    operation: PinnedAuthorityOperation,
) -> None:
    year = _filing_years(operation)[-1]
    provider = _provider(operation, year)
    draft = _draft(operation, provider, year, ascendant_nif=None)
    payload = _render(provider, draft)
    (ascendant,) = ElementTree.fromstring(payload).findall(_ASCENDANT)
    assert ascendant.find("DNIASDLG") is None

    with pytest.raises(ModeloApplicationError) as refused:
        refuse_incomplete_xml_dictionary_payload(
            provider.get_snapshot("100").revision.export_layouts[0],
            draft=draft,
            payload=payload,
            schema_provider=provider,
        )

    assert is_xml_required_content_refusal(refused.value)
    assert any(box.endswith("DNIASDLG") for box in refused_xml_boxes(refused.value)), refused_xml_boxes(refused.value)
