"""The exported Modelo 100 declaration states the profile's identity where AEAT reads it.

A declarant-identity casilla takes its value from the profile, and the exported
declaration addresses the same binding by its dictionary field. This module
drives calculate, verify and export through the real CLI and reads the written
artefact: each identity value the calculation holds must appear at the position
the registry binding declares for it -- the XSD element path, or the attribute
of its parent element -- and nowhere else under another spelling.

The positions are read from the published registry, not written here, so a
binding that moves is followed and a renderer that writes elsewhere fails.
Real registry authority, real session backend; nothing is mocked.
"""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path
from typing import Any
from xml.etree.ElementTree import Element

import pytest
from defusedxml import ElementTree as DefusedElementTree

from ....adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from ....adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_cli_runtime_profile
from ....domain.calculations.registry.profile_bindings import ProfileProvider
from ....domain.calculations.registry.tests.published_authority import published_snapshot
from ....domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from ....tests.cli_envelope import require_schema_envelope
from .cli_runner import invoke_cached_cli
from .modelo_cli import create_modelo_work_unit_via_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_PROFILE_ID = "5b7d2e40-0000-4000-8000-00000000a7c2"
_LABEL = "Modelo 100 identity export position test profile"
_FILING_YEAR = 2025
_PERIOD = "0A"
#: What the profile below states for each identity casilla. Names are stored
#: as AEAT writes them, so the calculated and the exported spelling are one text.
_PROFILE_IDENTITY: dict[str, str] = {
    "DPNIF_D": "12345678Z",
    "DP_APENOM_D": "PEREZ GIL ANA",
    "ECIVIL": "4",
    "SEXO_D": "M",
    "TIPOTRIBUTACION": "1",
}
#: The command envelope redacts a tax identifier, so the calculation's held NIF
#: is compared through the artefact only.
_REDACTED_IN_ENVELOPE = frozenset({"DPNIF_D"})
_CALCULATE_FLAGS: tuple[str, ...] = (
    "--casilla", "0003=24000",
    "--binding", "renta-certificado-trabajo-retenciones=2400",
    "--binding", "renta-base-liquidable-negativa-general-anterior=0",
)  # fmt: skip


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_cli_runtime_profile(tmp_path=tmp_path, bucket_id=_PROFILE_ID, label=_LABEL) as profile:
        yield profile


def _seed_salaried_profile(runtime_profile: TestRuntimeProfile) -> None:
    record = create_user_profile_record(
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=(
            UserProfileFact(path="identity.tax_id", value="12345678Z"),
            UserProfileFact(path="identity.name", value="ANA"),
            UserProfileFact(path="identity.surnames", value="PEREZ GIL"),
            UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
            UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
            UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
            UserProfileFact(path="tax_residence.ccaa", value="madrid"),
            UserProfileFact(path="activities.description", value="salaried employment"),
            UserProfileFact(path="iva.regime", value="GENERAL"),
            UserProfileFact(path="iva.m303_regime_composition", value="general"),
            UserProfileFact(path="iva.redeme_enrolled", value=False),
            UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
            UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
            UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
            UserProfileFact(path="renta_taxpayer.sex", value="M"),
            UserProfileFact(path="renta_taxpayer.marital_status", value=Decimal("4")),
            UserProfileFact(path="renta_filing.declaration_type", value=Decimal("1")),
        ),
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label=_LABEL)


def _cli_json(*args: str) -> dict[str, Any]:
    result = invoke_cached_cli(["--format", "json", *args])
    assert result.exit_code == 0, result.output
    return require_schema_envelope(result.output)


def _official_positions() -> dict[str, tuple[str, str | None]]:
    """Each identity casilla's declared XSD element path and, when it is one, attribute."""
    revision = published_snapshot("100", filing_year=_FILING_YEAR, period=_PERIOD).revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    positions: dict[str, tuple[str, str | None]] = {}
    for casilla_id in _PROFILE_IDENTITY:
        binding_id = casillas[casilla_id].binding
        assert binding_id is not None, casilla_id
        provider = bindings[binding_id].provider
        assert isinstance(provider, ProfileProvider), casilla_id
        if provider.xsd_attribute is not None:
            positions[casilla_id] = (provider.xsd_path or "", provider.xsd_attribute)
        else:
            assert provider.xsd_path is not None, casilla_id
            positions[casilla_id] = (provider.xsd_path, None)
    return positions


def _value_at(root: Element, path: str, attribute: str | None) -> str | None:
    """Read one value at an XSD path below the declaration root, or at its attribute."""
    if attribute is None:
        element = root.find(f".{path}")
        return None if element is None else element.text
    carriers = [element for element in root.iter() if attribute in element.attrib]
    assert len(carriers) == 1, f"{attribute!r} must be carried by exactly one element"
    (carrier,) = carriers
    if path:
        assert root.find(f".{path}") is carrier, f"{attribute!r} is not carried by {path!r}"
    return carrier.attrib[attribute]


def test_each_profile_identity_value_is_exported_at_its_declared_position(
    runtime_profile: TestRuntimeProfile,
    tmp_path: Path,
) -> None:
    _seed_salaried_profile(runtime_profile)
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="100", filing_year=_FILING_YEAR, period=_PERIOD, revision=str(_FILING_YEAR)
    )
    calculated = _cli_json("app", "modelo", "work", "calculate", work_unit_id, *_CALCULATE_FLAGS)
    _cli_json("app", "modelo", "work", "verify", calculated["calculation_revision_id"])
    output = tmp_path / "modelo-100.xml"
    exported = _cli_json("app", "modelo", "export", work_unit_id, "--output", str(output))

    assert exported["format"] == "xml-dictionary"
    root = DefusedElementTree.fromstring(output.read_bytes())
    held = calculated["input_values_by_casilla_id"]
    assert set(_PROFILE_IDENTITY) <= set(held), "an identity casilla was not filled from the profile"
    for casilla_id, value in _PROFILE_IDENTITY.items():
        if casilla_id not in _REDACTED_IN_ENVELOPE:
            assert held[casilla_id] == value, casilla_id
    positions = _official_positions()
    for casilla_id, (path, attribute) in positions.items():
        assert _value_at(root, path, attribute) == _PROFILE_IDENTITY[casilla_id], (casilla_id, path, attribute)

    # Detector teeth on the same artefact: the name written one level off its
    # declared element is not found where AEAT reads it.
    name_path, _ = positions["DP_APENOM_D"]
    parent_path, _, leaf = name_path.rpartition("/")
    misplaced = DefusedElementTree.fromstring(output.read_bytes())
    parent = misplaced.find(f".{parent_path}")
    assert parent is not None
    name = parent.find(leaf)
    assert name is not None
    parent.remove(name)
    misplaced.append(name)
    assert _value_at(misplaced, name_path, None) is None
