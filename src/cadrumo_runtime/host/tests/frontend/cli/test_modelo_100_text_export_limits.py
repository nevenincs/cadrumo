"""Ordinary profile text exports through the real CLI, and text the XSD cannot hold refuses by its box.

An operator types names in mixed case with accents, while the official schema spells
its alphabet in capitals. This module drives calculate, verify and export through the
real CLI against the real registry, so nothing here stands in for the export route.
The name's alphabet is read from the bundled XSD, never from the code under test.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from defusedxml import ElementTree as DefusedElementTree

from cadrumo.adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from cadrumo.adapters.persistence.profile.tests.retencion_soportada_seed import seed_payer_certificate
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.application.user_profile.tests.persona_profile_facts import persona_facts_beneath
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.core.retencion_soportada import RetencionSoportadaClase
from cadrumo.core.type_adapters import STRICT_STR_KEYED_MAPPING_ADAPTER
from cadrumo.domain.calculations.registry.tests.authored_editions import newest_authored_edition, revision_covering
from cadrumo.domain.user_profile.tests.profile_creation_authority import profile_creation_context_for_test
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, create_user_profile_record
from cadrumo.entrypoints.cli.tests.modelo_cli import create_modelo_work_unit_via_cli
from cadrumo.tests.cli_envelope import require_schema_envelope

from .cli_runner import invoke_cached_cli
from .runtime_profile_backend import runtime_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("operation")]

_LABEL = "Modelo 100 text export limits test profile"
_FILING_YEAR = newest_authored_edition("100")
_PERIOD = "0A"
_XSD = "{http://www.w3.org/2001/XMLSchema}"
_NAME_PATH = "./DatosIdentificativos/Declarante/DP_APENOM_D"
_CALCULATE_FLAGS: tuple[str, ...] = (
    "--casilla",
    "0003=24000",
    "--binding",
    "renta-base-liquidable-negativa-general-anterior=0",
    "--binding",
    "renta-base-liquidable-negativa-general-em4-pendiente-inicio=0",
    "--binding",
    "renta-base-liquidable-negativa-general-em3-pendiente-inicio=0",
    "--binding",
    "renta-base-liquidable-negativa-general-em2-pendiente-inicio=0",
)


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with runtime_cli_profile(tmp_path=tmp_path, label=_LABEL) as profile:
        yield profile


def _seed(runtime_profile: TestRuntimeProfile, *, name: str, surnames: str, certificate: bool = True) -> None:
    record = create_user_profile_record(
        profile_id=runtime_profile.bucket_id,
        setup_state=ProfileSetupState.COMPLETE,
        facts=persona_facts_beneath(
            (
                UserProfileFact(path="identity.tax_id", value="12345678Z"),
                UserProfileFact(path="identity.name", value=name),
                UserProfileFact(path="identity.surnames", value=surnames),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="trabajo"),
                UserProfileFact(path="activities.description", value="salaried employment"),
                UserProfileFact(path="renta_taxpayer.birth_date", value="1985-06-15"),
                UserProfileFact(path="renta_taxpayer.sex", value="M"),
                UserProfileFact(path="renta_taxpayer.marital_status", value=Decimal("4")),
                UserProfileFact(path="renta_filing.declaration_type", value=Decimal("1")),
            ),
            without=("irpf.estimation_regime", "censo.activity_start_date"),
        ),
        context=profile_creation_context_for_test(),
    )
    seed_test_profile_record(record, root=runtime_profile.storage_root, label=_LABEL)
    if certificate:
        # The profile declares only salary income: the one payer certificate credits 0596 and the
        # other two credit classes are proven zero by the declared categories.
        seed_payer_certificate(
            operation=published_authority_operation(),
            taxpayer_tax_id="12345678Z",
            ejercicio=_FILING_YEAR,
            payer_tax_id="B00010082",
            income_class=RetencionSoportadaClase.TRABAJO,
            retencion=Decimal("2400"),
            importe_integro_dinerario=Decimal("24000"),
        )


def _name_pattern() -> str:
    files = Path(bundled_path("corpus", "aeat_official", "disenos_registro", "modelo_100", "files"))
    (xsd,) = files.glob(f"*-100-esquema-xsd-ejercicio-{_FILING_YEAR}-*.xsd")
    root = DefusedElementTree.parse(xsd).getroot()
    assert root is not None
    for simple_type in root.iter(f"{_XSD}simpleType"):
        if simple_type.get("name") == "tipo_ApeNom":
            facet = simple_type.find(f"{_XSD}restriction/{_XSD}pattern")
            assert facet is not None
            return str(facet.get("value"))
    pytest.fail("the bundled XSD declares no tipo_ApeNom")


def _calculated_work_unit() -> tuple[str, str]:
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="100", filing_year=_FILING_YEAR, period=_PERIOD, revision=str(revision_covering("100", _FILING_YEAR).id)
    )
    calculated = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id, *_CALCULATE_FLAGS]
    )
    assert calculated.exit_code == 0, calculated.output
    revision_id = require_schema_envelope(calculated.output)["calculation_revision_id"]
    assert isinstance(revision_id, str)
    return work_unit_id, revision_id


def _verified_work_unit() -> str:
    work_unit_id, revision_id = _calculated_work_unit()
    verified = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "verify", revision_id])
    assert verified.exit_code == 0, verified.output
    return work_unit_id


def _assert_refused_naming_the_box(surnames: str, tmp_path: Path) -> None:
    """Verification refuses the name by its box, and the export of that work then writes nothing."""
    work_unit_id, revision_id = _calculated_work_unit()
    output = tmp_path / "modelo-100.xml"

    verified = invoke_cached_cli(["--format", "json", "app", "modelo", "work", "verify", revision_id])
    exported = invoke_cached_cli(["app", "modelo", "export", work_unit_id, "--output", str(output)])

    for result in (verified, exported):
        assert result.exit_code != 0
        assert "application.filing" not in result.output
        assert surnames not in result.output
        assert surnames.upper() not in result.output
    assert "DP_APENOM_D" in verified.output
    assert not output.exists()


def _json_error(output: str) -> dict[str, object]:
    envelope = STRICT_STR_KEYED_MAPPING_ADAPTER.validate_json(output)
    return STRICT_STR_KEYED_MAPPING_ADAPTER.validate_python(envelope["error"])


def test_a_stored_surname_past_the_profile_bound_refuses_new_work_naming_the_fact(
    runtime_profile: TestRuntimeProfile,
) -> None:
    surnames = "Pérez" * 80
    _seed(runtime_profile, name="Ana", surnames=surnames)

    result = invoke_cached_cli(
        [
            "--format",
            "json",
            "app",
            "modelo",
            "work",
            "create",
            "--modelo",
            "100",
            "--year",
            str(_FILING_YEAR),
            "--period",
            _PERIOD,
            "--revision",
            str(revision_covering("100", _FILING_YEAR).id),
        ]
    )

    assert result.exit_code != 0
    error = _json_error(result.output)
    assert error["code"] == "REFUSED_PROFILE_SCHEMA_VALIDATION", error
    assert error["category"] == "REFUSED", error
    assert "Apellidos" in str(error["message"]), error
    assert "256" in str(error["message"]), error
    assert surnames not in result.output


def test_a_surname_stored_past_the_bound_after_work_began_refuses_calculate_naming_the_fact(
    runtime_profile: TestRuntimeProfile,
) -> None:
    _seed(runtime_profile, name="Ana", surnames="Pérez Núñez")
    work_unit_id = create_modelo_work_unit_via_cli(
        modelo="100", filing_year=_FILING_YEAR, period=_PERIOD, revision=str(revision_covering("100", _FILING_YEAR).id)
    )
    surnames = "Pérez" * 80
    _seed(runtime_profile, name="Ana", surnames=surnames, certificate=False)

    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "work", "calculate", work_unit_id, *_CALCULATE_FLAGS]
    )

    assert result.exit_code != 0
    error = _json_error(result.output)
    assert error["code"] == "REFUSED_PROFILE_SCHEMA_VALIDATION", error
    assert error["category"] == "REFUSED", error
    assert "Apellidos" in str(error["message"]), error
    assert "256" in str(error["message"]), error
    assert surnames not in result.output


@pytest.mark.parametrize("surnames_length", [77, 252])
def test_a_name_past_the_official_box_refuses_verification_and_export_naming_the_box(
    runtime_profile: TestRuntimeProfile, tmp_path: Path, surnames_length: int
) -> None:
    """Composed with a space and ``ANA``, these make the 81 and 256 character ends of the range."""
    surnames = "P" * surnames_length
    _seed(runtime_profile, name="Ana", surnames=surnames)

    _assert_refused_naming_the_box(surnames, tmp_path)


def test_a_mixed_case_accented_name_exports_in_capitals(runtime_profile: TestRuntimeProfile, tmp_path: Path) -> None:
    _seed(runtime_profile, name="José María", surnames="Pérez Núñez")
    output = tmp_path / "modelo-100.xml"

    result = invoke_cached_cli(
        ["--format", "json", "app", "modelo", "export", _verified_work_unit(), "--output", str(output)]
    )

    assert result.exit_code == 0, result.output
    root = DefusedElementTree.fromstring(output.read_bytes())
    assert root.findtext(_NAME_PATH) == "PÉREZ NÚÑEZ JOSÉ MARÍA"


def test_a_name_no_case_can_make_valid_refuses_verification_naming_it_and_writes_nothing(
    runtime_profile: TestRuntimeProfile, tmp_path: Path
) -> None:
    surnames = "Pérez Gil 5"
    assert re.fullmatch(_name_pattern(), f"{surnames} ANA".upper()) is None
    _seed(runtime_profile, name="Ana", surnames=surnames)

    _assert_refused_naming_the_box(surnames, tmp_path)
