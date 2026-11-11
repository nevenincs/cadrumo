"""Binding names follow declared relationships and the shared schema catalogues."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import lookup_translation
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.modelo_localization import binding_locale_key, resolve_modelo_localization
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.calculations.registry.schema_form_layouts import FormLayoutDefinition
from ....domain.calculations.registry.tests.authored_editions import (
    filing_grade_exercises,
    filing_year_envelope,
    revision_covering,
)
from ....domain.modelos.codes import ModeloCode
from ..work_form import build_modelo_work_form
from ..work_form_field_vocabulary import (
    ModeloFormBindingAddressV1,
    ModeloFormTextDisclosure,
)
from ..work_form_models import (
    ModeloFormField,
    ModeloWorkForm,
)
from ..work_form_service import modelo_form_snapshot
from .work_form_fixture import uncalculated_review

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_YEAR_390 = filing_grade_exercises("390")[-1]
"""The newest exercise whose Modelo 390 edition reaches filing grade."""


def _form(
    operation: PinnedAuthorityOperation,
    modelo: str,
    year: int,
    code: str,
    language: OutputLanguage,
    *,
    adjust: Callable[[RegistrySnapshot], RegistrySnapshot] | None = None,
    adjust_layout: Callable[[FormLayoutDefinition], FormLayoutDefinition] | None = None,
) -> ModeloWorkForm:
    period = Period.from_year_and_code(year, code)
    revision_id = str(operation.revision_for_context(modelo, filing_year=year, period=code).id)
    snapshot = modelo_form_snapshot(operation, ModeloCode(modelo), year, period, revision_id)
    review = uncalculated_review(snapshot, operation, modelo=modelo, filing_year=year, period=period)
    if adjust is not None:
        snapshot = adjust(snapshot)
    layout = operation.form_layout(modelo, snapshot.revision.id)
    if adjust_layout is not None:
        assert layout is not None
        layout = adjust_layout(layout)
    return build_modelo_work_form(
        review=review,
        snapshot=snapshot,
        layout=layout,
        revision=None,
        permitted_surface=None,
        entered_casilla_ids=None,
        overridden_binding_ids=None,
        language=language,
    )


def _binding_fields(form: ModeloWorkForm) -> list[ModeloFormField]:
    return [field for field in form.fields() if isinstance(field.address, ModeloFormBindingAddressV1)]


@pytest.mark.parametrize("language", tuple(OutputLanguage))
def test_catalogue_names_reach_inputs_that_feed_no_box(
    operation: PinnedAuthorityOperation,
    language: OutputLanguage,
) -> None:
    form = _form(operation, "390", _YEAR_390, "0A", language)
    fields = _binding_fields(form)

    assert fields
    for field in fields:
        assert isinstance(field.address, ModeloFormBindingAddressV1)
        key = binding_locale_key("390", str(field.address.binding_id), "label")
        assert field.label.text == lookup_translation(key, locale=language.value)
        assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED
        assert str(field.address.binding_id) not in field.label.text


def test_a_binding_inputs_printed_code_is_in_the_box_slot(
    operation: PinnedAuthorityOperation,
) -> None:
    fields = _binding_fields(_form(operation, "390", _YEAR_390, "0A", OutputLanguage.EN))
    field = next(field for field in fields if field.box == "K1")
    assert "K1" not in field.label.text
    assert "activity" in field.label.text.lower()


def test_an_unproven_manual_input_remains_visible_and_honestly_unnamed(
    operation: PinnedAuthorityOperation,
) -> None:
    binding_id = "synthetic-unproven-envelope-input"
    template_id = ""

    def add_unproven_input(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        nonlocal template_id
        template = next(
            binding
            for binding in snapshot.revision.bindings
            if isinstance(binding.provider, ManualInputProvider) and binding.provider.record is not None
        )
        assert isinstance(template.provider, ManualInputProvider)
        template_id = str(template.id)
        unproven = template.model_copy(
            update={
                "id": binding_id,
                "provider": template.provider.model_copy(update={"record": "synthetic-unproven-record"}),
            }
        )
        return snapshot.model_copy(
            update={
                "revision": snapshot.revision.model_copy(update={"bindings": (*snapshot.revision.bindings, unproven)})
            }
        )

    def place_unproven_input(layout: FormLayoutDefinition) -> FormLayoutDefinition:
        encoded = layout.model_dump_json()
        needle = json.dumps(template_id)
        assert template_id and needle in encoded
        return FormLayoutDefinition.model_validate_json(encoded.replace(needle, json.dumps(binding_id)))

    fields = _binding_fields(
        _form(
            operation,
            "390",
            _YEAR_390,
            "0A",
            OutputLanguage.EN,
            adjust=add_unproven_input,
            adjust_layout=place_unproven_input,
        )
    )
    field = next(
        field
        for field in fields
        if isinstance(field.address, ModeloFormBindingAddressV1) and str(field.address.binding_id) == binding_id
    )
    assert field.label.disclosure is ModeloFormTextDisclosure.UNNAMED
    assert field.box is None


def test_the_generated_envelope_closing_tag_is_not_a_manual_question(operation: PinnedAuthorityOperation) -> None:
    fields = _binding_fields(_form(operation, "369", filing_year_envelope().horizon, "1T", OutputLanguage.EN))
    assert fields
    assert all(
        not isinstance(field.address, ModeloFormBindingAddressV1)
        or str(field.address.binding_id) != "modelo-369-union-fichero.tipo-y-cierre"
        for field in fields
    )


def _catalogued_manual_binding(
    operation: PinnedAuthorityOperation,
) -> tuple[str, str]:
    """A manual input of the newest filing-grade Modelo 390 with a catalogue name and a providing box."""
    snapshot = modelo_form_snapshot(
        operation,
        ModeloCode("390"),
        _YEAR_390,
        Period.from_year_and_code(_YEAR_390, "0A"),
        str(operation.revision_for_context("390", filing_year=_YEAR_390, period="0A").id),
    )
    form = _form(operation, "390", _YEAR_390, "0A", OutputLanguage.EN)
    field = next(field for field in _binding_fields(form) if field.box == "K1")
    assert isinstance(field.address, ModeloFormBindingAddressV1)
    binding_id = str(field.address.binding_id)
    binding = next(item for item in snapshot.revision.bindings if str(item.id) == binding_id)
    assert isinstance(binding.provider, ManualInputProvider)
    return binding_id, str(binding.provider.casilla_id)


def _field_for(form: ModeloWorkForm, binding_id: str) -> ModeloFormField:
    return next(
        field
        for field in _binding_fields(form)
        if isinstance(field.address, ModeloFormBindingAddressV1) and str(field.address.binding_id) == binding_id
    )


def test_the_binding_question_precedes_a_declared_owner_name(operation: PinnedAuthorityOperation) -> None:
    binding_id, provider_id = _catalogued_manual_binding(operation)
    owner = next(
        casilla
        for casilla in operation.revision("390", str(revision_covering("390", _YEAR_390).id)).casillas
        if str(casilla.id) != provider_id and casilla.localization_keys
    )

    def add_owner(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        casillas = tuple(
            casilla.model_copy(update={"binding": binding_id}) if casilla.id == owner.id else casilla
            for casilla in snapshot.revision.casillas
        )
        return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"casillas": casillas})})

    field = _field_for(_form(operation, "390", _YEAR_390, "0A", OutputLanguage.EN, adjust=add_owner), binding_id)
    expected = lookup_translation(binding_locale_key("390", binding_id, "label"), locale="en")
    assert field.label.text == expected
    assert field.label.text != resolve_modelo_localization(owner.localization_keys, locale="en")
    assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED


def test_missing_relationship_names_preserve_the_binding_question(operation: PinnedAuthorityOperation) -> None:
    binding_id, provider_id = _catalogued_manual_binding(operation)

    def remove_provider_name(snapshot: RegistrySnapshot) -> RegistrySnapshot:
        casillas = tuple(
            casilla.model_copy(update={"localization_keys": ()}) if str(casilla.id) == provider_id else casilla
            for casilla in snapshot.revision.casillas
        )
        return snapshot.model_copy(update={"revision": snapshot.revision.model_copy(update={"casillas": casillas})})

    field = _field_for(
        _form(operation, "390", _YEAR_390, "0A", OutputLanguage.EN, adjust=remove_provider_name), binding_id
    )
    assert field.label.text == lookup_translation(binding_locale_key("390", binding_id, "label"), locale="en")
    assert field.label.disclosure is ModeloFormTextDisclosure.LOCALIZED
