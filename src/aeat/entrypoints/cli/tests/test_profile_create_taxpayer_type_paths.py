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
from typer.testing import CliRunner

from ....tests.secure_sql import isolated_profile_storage_root
from .. import app as root_app

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_profile_storage_root(tmp_path=tmp_path):
        yield


def _profile_rows(runner: CliRunner, name: str) -> dict[str, str]:
    """Run `config profile show NAME` and parse the tab-separated rows."""

    result = runner.invoke(root_app, ["config", "profile", "show", name])
    assert result.exit_code == 0, result.output
    rows: dict[str, str] = {}
    for line in result.output.splitlines():
        if "\t" not in line:
            continue
        key, _, value = line.partition("\t")
        rows[key.strip()] = value.strip()
    return rows


def _registered_profile_exists(name: str) -> bool:
    from ....application.workflow._profile_bucket_scan import read_profile_bucket

    return read_profile_bucket(name) is not None


def test_legal_entity_profile_creates_non_interactively_without_spouse_flags() -> None:
    """BLOCKER B1: a legal-entity profile must create under `--quiet`
    with no spouse flags. A sociedad limitada has no spouse, so the
    spouse / personal-IRPF questions must never be asked or demanded."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "webco",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--tax-id",
            "B66012345",
            "--activity",
            "consultoria informatica",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "Status\tcreated" in result.output
    rows = _profile_rows(runner, "webco")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"


def test_non_resident_irnr_quiet_create_requires_country_before_registration() -> None:
    """A CLI-only IRNR profile cannot be saved without the residence country."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "irnr-no-country",
            "--quiet",
            "--accept-defaults",
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
        ],
    )

    assert result.exit_code != 0, result.output
    assert "country_of_fiscal_residence" in result.output
    assert _registered_profile_exists("irnr-no-country") is False


def test_gb_legal_entity_irnr_quiet_create_requires_representante_before_registration() -> None:
    """GB is outside EU/EEA post-Brexit, so representante facts are a hard gate."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "gb-ltd",
            "--quiet",
            "--accept-defaults",
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
        ],
    )

    assert result.exit_code != 0, result.output
    assert "representante_fiscal_nif" in result.output
    assert "representante_fiscal_nombre" in result.output
    assert _registered_profile_exists("gb-ltd") is False


def test_legal_entity_profile_creates_with_explicit_no_spouse_flag() -> None:
    """BLOCKER B1: passing `--no-spouse-non-resident-irpf` explicitly
    must not change the legal-entity outcome — the spouse question is
    gated away, so the flag is simply inert, never a hard failure."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "webco-ltd",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--tax-id",
            "B12345674",
            "--no-spouse-non-resident-irpf",
            "--activity",
            "asesoria",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "webco-ltd")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"


def test_legal_entity_form_flag_populates_the_legal_entity_form_field() -> None:
    """BLOCKER B2: `--legal-entity-form sl` must land in the
    legal-entity-form question, not be misrouted into the IRPF
    income-categories question. The value must round-trip to the
    stored `taxpayer_type.legal_entity_form` fact."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "sl-co",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--legal-entity-form",
            "sl",
            "--tax-id",
            "B66012345",
            "--activity",
            "comercio",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "sl-co")
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

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "legal-name-co",
            "--quiet",
            "--accept-defaults",
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
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "legal-name-co")
    assert rows["identity.legal_name"] == "Initial Legal Name SL"
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"

    edit = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "edit",
            "legal-name-co",
            "--quiet",
            "--legal-name",
            "Updated Legal Name SL",
        ],
    )

    assert edit.exit_code == 0, edit.output
    rows = _profile_rows(runner, "legal-name-co")
    assert rows["identity.legal_name"] == "Updated Legal Name SL"
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"


def test_pure_landlord_profile_creates_without_activity() -> None:
    """DEFECT P1: a natural person whose only income is immovable
    capital (a pure landlord) has no actividad económica. The profile
    must create non-interactively with no `--activity` flag, and must
    not store a misleading `activities.description`."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "landlord",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "capital_inmobiliario",
            "--tax-id",
            "12345678Z",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "landlord")
    assert rows["taxpayer_type.entity_type"] == "natural_person"
    assert rows["taxpayer_type.irpf_income_categories"] == "capital_inmobiliario"
    # No invented economic activity is stored for a pure landlord.
    assert "activities.description" not in rows


def test_attribution_entity_profile_creates_without_spouse_flags() -> None:
    """An attribution entity (comunidad de bienes) also has no spouse;
    it must create non-interactively just like a legal entity."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "comunidad",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "attribution_entity",
            "--tax-id",
            "E12345674",
            "--activity",
            "arrendamiento conjunto",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "comunidad")
    assert rows["taxpayer_type.entity_type"] == "attribution_entity"


def test_activity_start_date_flag_stores_the_censo_alta_date() -> None:
    """Round-4 D1: `--activity-start-date` lands in the censo alta-date
    fact. The optional flag drives the deadline engine's
    pre-registration-obligation gate, so a 2026 registrant is not shown
    overdue 2025 returns."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "recent-autonomo",
            "--quiet",
            "--accept-defaults",
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
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "recent-autonomo")
    assert rows["censo.activity_start_date"] == "2026-03-01"


def test_profile_creates_without_activity_start_date_flag() -> None:
    """The censo alta date is optional: a profile created with no
    `--activity-start-date` flag must not carry the fact at all, so the
    deadline engine's pre-registration gate stays inert."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "no-alta-date",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            "12345678Z",
            "--activity",
            "fontaneria",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "no-alta-date")
    assert "censo.activity_start_date" not in rows


def test_natural_person_with_economic_activity_stores_the_activity() -> None:
    """A natural person who declares the economic-activity income
    category IS asked for `--activity`, and the supplied description is
    stored — the conditional gate opens the question, it is not removed."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "autonomo",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--irpf-income-categories",
            "actividad_economica",
            "--tax-id",
            "87654321X",
            "--activity",
            "fontaneria epigrafe 151",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "autonomo")
    assert rows["activities.description"] == "fontaneria epigrafe 151"


def test_profile_create_refuses_pais_vasco_with_concierto_economico_redirect() -> None:
    """Lourdes F1: `profile create ... --tax-residence-ccaa pais_vasco` must
    be refused with a clean non-zero exit citing the Concierto Económico
    (Ley 12/2002). No traceback; the operator must be redirected to the
    Hacienda Foral, not left with a Python stack trace."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "lourdes",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "44444444A",
            "--activity",
            "traductora",
            "--tax-residence-ccaa",
            "pais_vasco",
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")
    output = result.output or ""
    # Rich box rendering may line-wrap "Ley 12/2002" across two lines; assert
    # each token independently so the legal citation is definitely present.
    assert "12/2002" in output, f"Expected 12/2002 (Ley 12/2002) in foral refusal; got: {output!r}"
    assert "sede.bizkaia.eus" in output, f"Expected Bizkaia URL in foral refusal; got: {output!r}"


def test_profile_create_refuses_navarra_with_concierto_economico_redirect() -> None:
    """Lourdes F1: `--tax-residence-ccaa navarra` must produce the same
    foral-refusal as País Vasco — both are excluded from AEAT jurisdiction
    under the Concierto / Convenio Económico."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "navarrese",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "natural_person",
            "--tax-id",
            "44444445B",
            "--activity",
            "agricultor",
            "--tax-residence-ccaa",
            "navarra",
        ],
    )

    assert result.exit_code != 0
    assert "Traceback" not in (result.output or "")
    output = result.output or ""
    # Rich box rendering may line-wrap "Ley 12/2002" across two lines; assert
    # each token independently so the legal citation is definitely present.
    assert "12/2002" in output, f"Expected 12/2002 (Ley 12/2002) in foral refusal; got: {output!r}"
    assert "hacienda.navarra.es" in output, f"Expected Navarra URL in foral refusal; got: {output!r}"
