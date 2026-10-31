"""Authored shapes that differ from the declared form geometry stop publication."""

from __future__ import annotations

import dataclasses
from datetime import date
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.form_codes import resolve_form_codes
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.prorrata_register_catalogue import resolve_prorrata_register_catalogue

from ...compiler import fact_providers
from ...compiler import validate_form_geometry as geometry
from ...compiler import validator as registry_validator
from ...compiler.validate_form_geometry import (
    modelo_geometry_failures,
    prorrata_catalogue_failures,
    validate_form_geometry,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain, pytest.mark.usefixtures("governed_fact_scope")]


@pytest.fixture
def _one_layout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(geometry, "derive_export_layouts_from_bindings", lambda revision: revision.layouts)


def _codes() -> Any:
    return resolve_form_codes("form-row-codes")


def _modelo(*, prefix_fields: int, tipo_renta: tuple[str, ...] | None) -> Any:
    header = SimpleNamespace(prefix_fields=(None,) * prefix_fields)
    layout = SimpleNamespace(auxiliary_envelope_header=header)
    window = SimpleNamespace(tipo_renta_scope=tipo_renta)
    revision = SimpleNamespace(layouts=(layout,), deadline_windows=(window,))
    return SimpleNamespace(id="000", revisions={"rev": revision})


def test_the_bundled_catalogues_have_the_declared_shape() -> None:
    assert validate_form_geometry(()) == ()


def test_the_compiled_registry_has_the_declared_geometry(_worker_compiled_authority: Any) -> None:
    modelos = _worker_compiled_authority.modelos
    assert validate_form_geometry(modelos) == ()


def test_only_a_provider_free_partial_candidate_may_omit_geometry(
    _worker_compiled_authority: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalogues = _worker_compiled_authority.catalogues
    without_geometry = catalogues.facts.model_copy(
        update={"facts": {key: fact for key, fact in catalogues.facts.facts.items() if key != "form-row-codes"}}
    )
    authority = CandidateFactAuthority(without_geometry, catalogues.require_supported_filing_years())
    with validating_governed_facts(authority):
        assert fact_providers.FACT_PROVIDER_REGISTRATIONS
        with pytest.raises(RegistryValidationError, match=r"form-row-codes.*not registered"):
            validate_form_geometry(())
        monkeypatch.setattr(fact_providers, "FACT_PROVIDER_REGISTRATIONS", ())
        assert validate_form_geometry(()) == ()


def test_a_present_malformed_geometry_fact_is_not_treated_as_absent(
    _worker_compiled_authority: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalogues = _worker_compiled_authority.catalogues
    original = catalogues.facts.facts["form-row-codes"]
    variant = original.variants[0]
    payload = variant.payload
    duplicate = payload.model_copy(update={"entries": (*payload.entries, payload.entries[0])})
    malformed = original.model_copy(update={"variants": (variant.model_copy(update={"payload": duplicate}),)})
    facts = catalogues.facts.model_copy(update={"facts": {**catalogues.facts.facts, "form-row-codes": malformed}})
    authority = CandidateFactAuthority(facts, catalogues.require_supported_filing_years())
    monkeypatch.setattr(fact_providers, "FACT_PROVIDER_REGISTRATIONS", ())
    with validating_governed_facts(authority), pytest.raises(ValidationError, match="keys must be unique"):
        validate_form_geometry(())


def test_an_expired_geometry_fact_is_not_treated_as_absent(
    _worker_compiled_authority: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    catalogues = _worker_compiled_authority.catalogues
    original = catalogues.facts.facts["form-row-codes"]
    variant = original.variants[0].model_copy(update={"valid_to": date(2022, 1, 2)})
    expired = original.model_copy(update={"variants": (variant,)})
    facts = catalogues.facts.model_copy(update={"facts": {**catalogues.facts.facts, "form-row-codes": expired}})
    authority = CandidateFactAuthority(facts, catalogues.require_supported_filing_years())
    monkeypatch.setattr(fact_providers, "FACT_PROVIDER_REGISTRATIONS", ())
    with validating_governed_facts(authority), pytest.raises(RegistryValidationError):
        validate_form_geometry(())
    validator = registry_validator.RegistryValidator(catalogues.model_copy(update={"facts": facts}))
    monkeypatch.setattr(validator, "_validate_registry_modelos", lambda _modelos: [])
    monkeypatch.setattr(registry_validator, "validate_registry_scope", lambda _modelos: ())
    with validating_governed_facts(authority), pytest.raises(RegistryValidationError):
        validator.validate_registry(())


def test_a_prorrata_catalogue_of_another_size_is_refused() -> None:
    catalogue = resolve_prorrata_register_catalogue()
    assert prorrata_catalogue_failures(catalogue, _codes()) == []
    short = dataclasses.replace(catalogue, sector_letters=catalogue.sector_letters[:-1])
    assert any("sector_letters" in failure for failure in prorrata_catalogue_failures(short, _codes()))


@pytest.mark.usefixtures("_one_layout")
def test_an_auxiliary_header_of_another_size_is_refused() -> None:
    declared = int(_codes().code("aeat.aux.prefix_fields"))
    assert modelo_geometry_failures((_modelo(prefix_fields=declared, tipo_renta=None),), _codes()) == []
    failures = modelo_geometry_failures((_modelo(prefix_fields=declared - 1, tipo_renta=None),), _codes())
    assert any("auxiliary header" in failure for failure in failures)


@pytest.mark.usefixtures("_one_layout")
def test_a_deadline_code_of_another_width_is_refused() -> None:
    declared = int(_codes().code("aeat.aux.prefix_fields"))
    width = next(iter(_codes().codes("m210.tipo_renta_digits")))
    wrong = "1" * (int(width) + 1)
    failures = modelo_geometry_failures((_modelo(prefix_fields=declared, tipo_renta=(wrong,)),), _codes())
    assert any("deadline code" in failure for failure in failures)
