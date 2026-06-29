"""Non-interactive `config profile create` across the taxpayer-type axis.

These tests exercise the real `aeat config profile create ... --quiet`
CLI surface for every entity type. They pin the behaviour that a legal
entity, an attribution entity, and a natural person can each be created
non-interactively without supplying spouse / personal-IRPF flags, that
each taxpayer-type flag populates its own wizard question, and that
a taxpayer with no economic activity is not forced to invent one.

No mocks: the runner drives the real Typer command, the real wizard
runtime, and the real encrypted-SQLite profile store.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....tests.cli_runner import invoke_cached_cli
from ....tests.secure_sql import isolated_profile_storage_root
from ._profile_cli_support import (
    create_quiet_profile as _create_profile,
)
from ._profile_cli_support import (
    edit_quiet_profile as _edit_profile,
)
from ._profile_cli_support import (
    profile_rows as _profile_rows,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _registered_profile_exists(name: str) -> bool:
    from ....application.workflow._profile_bucket_scan import read_profile_bucket

    return read_profile_bucket(name) is not None


def test_missing_entity_type_does_not_re_report_supplied_identity_flags() -> None:
    """A missing taxpayer type should not tell the operator to re-enter supplied names."""

    result = invoke_cached_cli(
        (
            "config",
            "profile",
            "create",
            "missing-entity-type",
            "--quiet",
            "--accept-defaults",
            "--tax-id",
            "12345678Z",
            "--name",
            "Irene",
            "--surnames",
            "Hardening",
            "--activity",
            "consultoria",
        ),
    )

    assert result.exit_code != 0, result.output
    assert "--entity-type" in result.output
    assert "--name" not in result.output
    assert "--surnames" not in result.output
    assert _registered_profile_exists("missing-entity-type") is False


def test_legal_entity_profile_creates_non_interactively_without_spouse_flags() -> None:
    """BLOCKER B1: a legal-entity profile must create under `--quiet`
    with no spouse flags. A sociedad limitada has no spouse, so the
    spouse / personal-IRPF questions must never be asked or demanded."""

    result = _create_profile(
        "webco",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        "B66012345",
        "--activity",
        "consultoria informatica",
    )

    assert result.exit_code == 0, result.output
    assert "Status\tcreated" in result.output
    rows = _profile_rows("webco")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"


def test_legal_entity_profile_create_refuses_missing_legal_form_before_registration() -> None:
    """A legal entity without a recognised legal form is not filing-grade."""

    result = _create_profile(
        "missing-form-co",
        "--entity-type",
        "legal_entity",
        "--tax-id",
        "B66012345",
        "--activity",
        "consultoria informatica",
    )

    assert result.exit_code != 0, result.output
    assert "--legal-entity-form" in result.output
    assert _registered_profile_exists("missing-form-co") is False


def test_non_resident_irnr_quiet_create_requires_country_before_registration() -> None:
    """A CLI-only IRNR profile cannot be saved without the residence country."""

    result = _create_profile(
        "irnr-no-country",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "capital_inmobiliario",
        "--fiscal-residency",
        "non_resident_irnr",
        "--tax-id",
        "X1234567L",
        "--iva-regime",
        "GENERAL",
    )

    assert result.exit_code != 0, result.output
    assert "--country-of-fiscal-residence" in result.output
    assert "taxpayer_type.country_of_fiscal_residence" not in result.output
    assert _registered_profile_exists("irnr-no-country") is False


def test_non_resident_irnr_create_guides_to_m210_discovery_not_work_create() -> None:
    """A successful IRNR profile must not point at unsupported local M210 work."""

    result = _create_profile(
        "marta-irnr",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "capital_inmobiliario",
        "--fiscal-residency",
        "non_resident_irnr",
        "--country-of-fiscal-residence",
        "FR",
        "--tax-id",
        "X1234567L",
        "--iva-regime",
        "GENERAL",
    )

    assert result.exit_code == 0, result.output
    assert "next\taeat app modelo describe 210" in result.output
    assert "next\taeat app modelo work create" not in result.output


def test_gb_legal_entity_irnr_quiet_create_requires_representante_before_registration() -> None:
    """GB is outside EU/EEA post-Brexit, so representante facts are a hard gate."""

    result = _create_profile(
        "gb-ltd",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--fiscal-residency",
        "non_resident_irnr",
        "--country-of-fiscal-residence",
        "GB",
        "--tax-id",
        "B66012345",
        "--activity",
        "consultoria internacional",
        "--iva-regime",
        "GENERAL",
    )

    assert result.exit_code != 0, result.output
    assert "--representante-fiscal-nif" in result.output
    assert "--representante-fiscal-nombre" in result.output
    assert "taxpayer_type.representante_fiscal_nif" not in result.output
    assert "taxpayer_type.representante_fiscal_nombre" not in result.output
    assert _registered_profile_exists("gb-ltd") is False


def test_legal_entity_profile_creates_with_explicit_no_spouse_flag() -> None:
    """BLOCKER B1: passing `--no-spouse-non-resident-irpf` explicitly
    must not change the legal-entity outcome — the spouse question is
    gated away, so the flag is simply inert, never a hard failure."""

    result = _create_profile(
        "webco-ltd",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        "B12345674",
        "--no-spouse-non-resident-irpf",
        "--activity",
        "asesoria",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("webco-ltd")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"


def test_legal_entity_form_flag_populates_the_legal_entity_form_field() -> None:
    """BLOCKER B2: `--legal-entity-form sl` must land in the
    legal-entity-form question, not be misrouted into the IRPF
    income-categories question. The value must round-trip to the
    stored `taxpayer_type.legal_entity_form` fact."""

    result = _create_profile(
        "sl-co",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        "B66012345",
        "--activity",
        "comercio",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("sl-co")
    assert rows["taxpayer_type.legal_entity_form"] == "sl"
    # The value must NOT have leaked into the IRPF income-category set.
    assert rows.get("taxpayer_type.irpf_income_categories", "") == ""


def test_legal_entity_profile_create_and_edit_exposes_legal_name() -> None:
    """Legal entities must be able to set the export-header filing name.

    Modelo 200/202 export headers require a legal filing name for entity-style
    declarations. The CLI must expose that profile fact directly; it must not
    force users to guess that display name or surnames should double as the
    legal entity name.
    """

    result = _create_profile(
        "legal-name-co",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        "B66012345",
        "--legal-name",
        "Initial Legal Name SL",
        "--activity",
        "asesoria",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("legal-name-co")
    assert rows["identity.legal_name"] == "Initial Legal Name SL"
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"

    edit = _edit_profile(
        "legal-name-co",
        "--legal-name",
        "Updated Legal Name SL",
    )

    assert edit.exit_code == 0, edit.output
    rows = _profile_rows("legal-name-co")
    assert rows["identity.legal_name"] == "Updated Legal Name SL"
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"


def test_edit_refuses_natural_person_branch_change_without_legal_name() -> None:
    """A branch-changing edit must not persist a legal entity without legal name."""

    result = _create_profile(
        "branch-to-legal",
        "--entity-type",
        "natural_person",
        "--tax-id",
        "12345678Z",
        "--name",
        "Branch",
        "--surnames",
        "Operator",
        "--activity",
        "consultoria",
    )
    assert result.exit_code == 0, result.output

    edit = _edit_profile(
        "branch-to-legal",
        "--entity-type",
        "legal_entity",
    )

    assert edit.exit_code != 0, edit.output
    assert "--legal-name" in edit.output
    rows = _profile_rows("branch-to-legal")
    assert rows["taxpayer_type.entity_type"] == "natural_person"
    assert rows["identity.name"] == "Branch"
    assert rows["identity.surnames"] == "Operator"


def test_edit_refuses_legal_entity_branch_change_without_surnames() -> None:
    """A branch-changing edit must not persist a natural person without surnames."""

    result = _create_profile(
        "branch-to-natural",
        "--entity-type",
        "legal_entity",
        "--legal-entity-form",
        "sl",
        "--tax-id",
        "B66012345",
        "--legal-name",
        "Branch Legal SL",
        "--activity",
        "asesoria",
    )
    assert result.exit_code == 0, result.output

    edit = _edit_profile(
        "branch-to-natural",
        "--entity-type",
        "natural_person",
        "--name",
        "Branch",
    )

    assert edit.exit_code != 0, edit.output
    assert "--surnames" in edit.output
    rows = _profile_rows("branch-to-natural")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["identity.legal_name"] == "Branch Legal SL"
    assert "identity.name" not in rows


def test_pure_landlord_profile_creates_without_activity() -> None:
    """DEFECT P1: a natural person whose only income is immovable
    capital (a pure landlord) has no actividad económica. The profile
    must create non-interactively with no `--activity` flag, and must
    not store a misleading `activities.description`."""

    result = _create_profile(
        "landlord",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "capital_inmobiliario",
        "--tax-id",
        "12345678Z",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("landlord")
    assert rows["taxpayer_type.entity_type"] == "natural_person"
    assert rows["taxpayer_type.irpf_income_categories"] == "capital_inmobiliario"
    # No invented economic activity is stored for a pure landlord.
    assert "activities.description" not in rows


def test_attribution_entity_profile_creates_without_spouse_flags() -> None:
    """An attribution entity (comunidad de bienes) also has no spouse;
    it must create non-interactively just like a legal entity."""

    result = _create_profile(
        "comunidad",
        "--entity-type",
        "attribution_entity",
        "--tax-id",
        "E12345674",
        "--activity",
        "arrendamiento conjunto",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("comunidad")
    assert rows["taxpayer_type.entity_type"] == "attribution_entity"


def test_activity_start_date_flag_stores_the_censo_alta_date() -> None:
    """Round-4 D1: `--activity-start-date` lands in the censo alta-date
    fact. The optional flag drives the deadline engine's
    pre-registration-obligation gate, so a 2026 registrant is not shown
    overdue 2025 returns."""

    result = _create_profile(
        "recent-autonomo",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "actividad_economica",
        "--tax-id",
        "87654321X",
        "--activity",
        "consultoria",
        "--activity-start-date",
        "2026-03-01",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("recent-autonomo")
    assert rows["censo.activity_start_date"] == "2026-03-01"


def test_profile_creates_without_activity_start_date_flag() -> None:
    """The censo alta date is optional: a profile created with no
    `--activity-start-date` flag must not carry the fact at all, so the
    deadline engine's pre-registration gate stays inert."""

    result = _create_profile(
        "no-alta-date",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "actividad_economica",
        "--tax-id",
        "12345678Z",
        "--activity",
        "fontaneria",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("no-alta-date")
    assert "censo.activity_start_date" not in rows


def test_natural_person_with_economic_activity_stores_the_activity() -> None:
    """A natural person who declares the economic-activity income
    category IS asked for `--activity`, and the supplied description is
    stored — the conditional gate opens the question, it is not removed."""

    result = _create_profile(
        "autonomo",
        "--entity-type",
        "natural_person",
        "--irpf-income-categories",
        "actividad_economica",
        "--tax-id",
        "87654321X",
        "--activity",
        "fontaneria epigrafe 151",
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows("autonomo")
    assert rows["activities.description"] == "fontaneria epigrafe 151"


@pytest.mark.parametrize(
    ("name", "tax_id", "activity", "ccaa", "expected_url"),
    (
        pytest.param("lourdes", "44444444A", "traductora", "pais_vasco", "sede.bizkaia.eus", id="pais_vasco"),
        pytest.param("navarrese", "44444445B", "agricultor", "navarra", "hacienda.navarra.es", id="navarra"),
    ),
)
def test_profile_create_refuses_foral_tax_residence_with_concierto_economico_redirect(
    name: str,
    tax_id: str,
    activity: str,
    ccaa: str,
    expected_url: str,
) -> None:
    """Foral tax residences must refuse AEAT profile creation with a legal redirect."""

    result = _create_profile(
        name,
        "--entity-type",
        "natural_person",
        "--tax-id",
        tax_id,
        "--activity",
        activity,
        "--tax-residence-ccaa",
        ccaa,
    )

    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")
    output = result.output or ""
    # Rich box rendering may line-wrap "Ley 12/2002" across two lines; assert
    # each token independently so the legal citation is definitely present.
    assert "12/2002" in output, f"Expected 12/2002 (Ley 12/2002) in foral refusal; got: {output!r}"
    assert expected_url in output, f"Expected foral URL {expected_url!r} in refusal; got: {output!r}"
