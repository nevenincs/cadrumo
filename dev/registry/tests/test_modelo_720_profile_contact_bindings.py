"""Modelo 720's two contact bindings keep the official slots and read the contact profile."""

from decimal import Decimal

import pytest

from cadrumo.application.modelo.profile_binding import resolve_profile_binding_channels
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.profile_bindings import ProfileProvider

from ..compiler.loader import load_modelo_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_contact_providers_preserve_the_grounded_optional_export_slots() -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "720"))
    assert modelo.revisions
    for revision, (suffix, profile_key, offset, length) in (
        (revision, slot)
        for revision in modelo.revisions.values()
        for slot in (
            ("telefono-contacto", "contact.contact_person_phone", 59, 9),
            ("nombre-contacto", "contact.contact_person_name", 68, 40),
        )
    ):
        binding_id = f"modelo-720.type_1.{suffix}"
        binding = next(binding for binding in revision.bindings if binding.id == binding_id)
        assert isinstance(binding.provider, ProfileProvider)
        assert binding.provider.profile_key == profile_key
        assert binding.value.channel is BindingValueChannel.TEXT
        assert "aeat-dr-720" in binding.source_refs
        (field,) = tuple(
            field
            for layout in revision.export_layouts
            for record in layout.records
            for field in record.fields
            if field.binding == binding_id
        )
        assert (field.offset, field.length) == (offset, length)
        assert field.required is False


def test_candidate_contact_text_uses_existing_string_channel_without_a_formula(
    operation: PinnedAuthorityOperation,
) -> None:
    modelo = load_modelo_directory(bundled_path("registry", "aeat", "modelos", "720"))
    assert modelo.revisions
    for revision in modelo.revisions.values():
        bindings = tuple(
            binding
            for binding in revision.bindings
            if binding.id in {"modelo-720.type_1.telefono-contacto", "modelo-720.type_1.nombre-contacto"}
        )
        assert len(bindings) == 2
        resolved = resolve_profile_binding_channels(
            bindings,
            {
                "contact.contact_person_phone": Decimal("900000000"),
                "contact.contact_person_name": "Contacto Prueba Berta",
            },
            caller_binding_ids=frozenset(),
            formula_date_consumed=frozenset(),
            enum_bindings=frozenset(),
        )
        assert resolved.enum_values == {
            "modelo-720.type_1.telefono-contacto": "900000000",
            "modelo-720.type_1.nombre-contacto": "Contacto Prueba Berta",
        }
        assert resolved.decimal_values == {}
