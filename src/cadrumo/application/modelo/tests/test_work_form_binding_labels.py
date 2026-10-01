"""Binding names follow declared relationships and the shared schema catalogues."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.modelo_work_progress_state import ModeloWorkProgressState
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.modelo_localization import binding_locale_key, resolve_modelo_localization
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.modelos.codes import ModeloCode
from ..work_form import build_modelo_work_form
from ..work_form_models import (
    ModeloFormBindingAddressV1,
    ModeloFormCasillaAddressV1,
    ModeloFormField,
    ModeloFormTextDisclosure,
    ModeloWorkForm,
    address_key,
)
from ..work_form_service import modelo_form_snapshot
from ..work_review import ModeloWorkProgress, ModeloWorkReview, build_modelo_work_review_casillas

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_DIRECT_ESTIMATION = "renta-modelo-100-estimacion-directa-es-normal"


def _form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    language: OutputLanguage,
    *,
    adjust: Callable[[RegistrySnapshot], RegistrySnapshot] | None = None,
) -> ModeloWorkForm:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = ModeloWorkReview(
        bucket_id="13000000-0000-4000-8000-000000000224",
        modelo=modelo,
        filing_year=year,
        period=period,
        registry_revision_id=snapshot.revision.id,
        work_unit_id="b" * 64,
        calculation_revision_id=None,
        lifecycle_state=None,
        verification_outcome=None,
        progress=ModeloWorkProgress(state=ModeloWorkProgressState.UNDEFINED),
        casillas=build_modelo_work_review_casillas(snapshot=snapshot, revision=None, operation=operation),
        findings=(),
        blockers=(),
    )
    if adjust is not None:
        snapshot = adjust(snapshot)
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=operation.form_layout(modelo, snapshot.revision.id),
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=language,
    )


def _binding_fields(form: ModeloWorkForm) -> list[ModeloFormField]:
    return [field for field in form.fields() if isinstance(field.address, ModeloFormBindingAddressV1)]


@pytest.mark.parametrize(
    ("language", "expected"),
    [
        (OutputLanguage.EN, "Additional data for box 0224"),
        (OutputLanguage.ES, "Dato adicional de la casilla 0224"),
        (OutputLanguage.CA, "Dada addicional de la casella 0224"),
        (OutputLanguage.HU, "Kiegészítő adat a(z) 0224. rovathoz"),
    ],
)
def test_the_binding_question_precedes_its_provider_and_fed_box_names(
    operation: PinnedAuthorityOperation, language: OutputLanguage, expected: str
) -> None:
    form = _form(operation, "100", 2024, "0A", language)
    field = next(
        field
        for field in _binding_fields(form)
        if isinstance(field.address, ModeloFormBindingAddressV1) and str(field.address.binding_id) == _DIRECT_ESTIMATION
    )

    provider = next(casilla for casilla in operation.revision("100", "2024").casillas if str(casilla.id) == "0168")
    assert field.label.text == lookup_translation(
        binding_locale_key("100", _DIRECT_ESTIMATION, "label"), locale=language.value
    )
    assert field.label.text != resolve_modelo_localization(provider.localization_keys, locale=language.value)
    assert field.label.text != expected
    assert field.box == "0168"
    assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_catalogue_names_reach_inputs_that_feed_no_box(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> None:
    form = _form(operation, "390", 2025, "0A", language)
    fields = _binding_fields(form)

    assert fields
    for field in fields:
        assert isinstance(field.address, ModeloFormBindingAddressV1)
        key = binding_locale_key("390", str(field.address.binding_id), "label")
        assert field.label.text == lookup_translation(key, locale=language.value)
        assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED
        assert str(field.address.binding_id) not in field.label.text


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_an_exact_duplicate_wire_input_keeps_one_named_casilla_address(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> None:
    fields = list(_form(operation, "360", 2025, "AD-HOC", language).fields())
    field = next(
        field
        for field in fields
        if isinstance(field.address, ModeloFormCasillaAddressV1)
        and str(field.address.casilla_id) == "decl.solicitante.nace-1"
    )
    casilla = next(
        casilla
        for casilla in operation.revision("360", "2010-y-siguientes").casillas
        if str(casilla.id) == "decl.solicitante.nace-1"
    )
    assert field.label.text == resolve_modelo_localization(casilla.localization_keys, locale=language.value)
    assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED
    assert not any(
        address_key(item.address) == ("binding", "modelo-360.page_01.actividad-nace-1-codigo") for item in fields
    )


@pytest.mark.parametrize(
    "axis,value", [("length", 4), ("offset", 800), ("record", "another-record"), ("data_type", CasillaDataType.INTEGER)]
)
def test_a_binding_without_the_exact_wire_identity_keeps_its_own_input(
    operation: PinnedAuthorityOperation, axis: str, value: int | str
) -> None:
    binding_id = "modelo-360.page_01.actividad-nace-1-codigo"

    def change_coordinate(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        bindings = tuple(
            binding.model_copy(update={"provider": binding.provider.model_copy(update={axis: value})})
            if str(binding.id) == binding_id
            else binding
            for binding in snapshot.revision.bindings
        )
        return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"bindings": bindings})})

    form = _form(operation, "360", 2025, "AD-HOC", OutputLanguage.EN, adjust=change_coordinate)
    assert {address_key(field.address) for field in form.fields()} >= {
        ("casilla", "decl.solicitante.nace-1"),
        ("binding", binding_id),
    }


def test_a_record_alias_with_two_typed_owners_keeps_the_binding_input(operation: PinnedAuthorityOperation) -> None:
    def make_record_ambiguous(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        layouts = tuple(
            layout.model_copy(
                update={
                    "records": (
                        *layout.records,
                        next(record for record in layout.records if record.record_type == "page_01").model_copy(
                            update={"id": "another-page-01"}
                        ),
                    )
                }
            )
            for layout in snapshot.revision.export_layouts
        )
        return snapshot.model_copy(
            update={"revision": snapshot.revision.model_copy(update={"export_layouts": layouts})}
        )

    form = _form(operation, "360", 2025, "AD-HOC", OutputLanguage.EN, adjust=make_record_ambiguous)
    assert any(
        address_key(field.address) == ("binding", "modelo-360.page_01.actividad-nace-1-codigo")
        for field in form.fields()
    )


def test_an_exact_wire_binding_with_an_independent_consumer_keeps_its_input(
    operation: PinnedAuthorityOperation,
) -> None:
    binding_id = "modelo-360.page_01.actividad-nace-1-codigo"

    def add_consumer(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        binding = next(binding for binding in snapshot.revision.bindings if str(binding.id) == binding_id)
        casillas = tuple(
            casilla.model_copy(update={"input_kind": InputKind.BOUND, "binding": binding.id})
            if str(casilla.id) == "decl.solicitante.nace-2"
            else casilla
            for casilla in snapshot.revision.casillas
        )
        assert any(str(casilla.id) == "decl.solicitante.nace-2" for casilla in casillas)
        return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"casillas": casillas})})

    form = _form(operation, "360", 2025, "AD-HOC", OutputLanguage.EN, adjust=add_consumer)
    assert any(address_key(field.address) == ("binding", binding_id) for field in form.fields())


def test_a_binding_inputs_printed_code_is_in_the_box_slot(
    operation: PinnedAuthorityOperation,
) -> None:
    fields = _binding_fields(_form(operation, "390", 2025, "0A", OutputLanguage.EN))
    field = next(field for field in fields if field.box == "K1")
    assert "K1" not in field.label.text
    assert "activity" in field.label.text.lower()


def test_unproven_envelope_inputs_remain_visible_and_honestly_unnamed(
    operation: PinnedAuthorityOperation,
) -> None:
    fields = _binding_fields(_form(operation, "369", 2025, "1T", OutputLanguage.EN))
    field = next(
        field
        for field in fields
        if isinstance(field.address, ModeloFormBindingAddressV1)
        and str(field.address.binding_id) == "modelo-369-union-fichero.tipo-y-cierre"
    )
    assert field.label.disclosure is ModeloFormTextDisclosure.UNNAMED
    assert field.box is None


def _direct_estimation_field(form: ModeloWorkForm) -> ModeloFormField:
    return next(
        field
        for field in _binding_fields(form)
        if isinstance(field.address, ModeloFormBindingAddressV1) and str(field.address.binding_id) == _DIRECT_ESTIMATION
    )


def test_the_binding_question_precedes_a_declared_owner_name(operation: PinnedAuthorityOperation) -> None:
    def add_owner(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        casillas = tuple(
            casilla.model_copy(update={"binding": _DIRECT_ESTIMATION}) if str(casilla.id) == "0001" else casilla
            for casilla in snapshot.revision.casillas
        )
        return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"casillas": casillas})})

    field = _direct_estimation_field(_form(operation, "100", 2024, "0A", OutputLanguage.EN, adjust=add_owner))
    owner = next(casilla for casilla in operation.revision("100", "2024").casillas if str(casilla.id) == "0001")
    assert field.label.text == lookup_translation(binding_locale_key("100", _DIRECT_ESTIMATION, "label"), locale="en")
    assert field.label.text != resolve_modelo_localization(owner.localization_keys, locale="en")
    assert field.box == "0001"


def test_missing_relationship_names_preserve_the_binding_question(operation: PinnedAuthorityOperation) -> None:
    def remove_provider_name(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        casillas = tuple(
            casilla.model_copy(update={"localization_keys": ()}) if str(casilla.id) == "0168" else casilla
            for casilla in snapshot.revision.casillas
        )
        return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"casillas": casillas})})

    field = _direct_estimation_field(
        _form(operation, "100", 2024, "0A", OutputLanguage.EN, adjust=remove_provider_name)
    )
    assert field.label.text == lookup_translation(binding_locale_key("100", _DIRECT_ESTIMATION, "label"), locale="en")
