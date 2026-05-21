"""Non-interactive `config profile create` across the taxpayer-type axis.

These tests exercise the real `aeat config profile create ... --quiet`
CLI surface for every entity type. They pin the behaviour that a legal
entity, an attribution entity, and a natural person can each be created
non-interactively without supplying spouse / personal-IRPF flags, that
each W01 taxpayer-type flag populates its own wizard question, and that
a taxpayer with no economic activity is not forced to invent one.

No mocks: the runner drives the real Typer command, the real wizard
runtime, and the real encrypted-SQLite profile store.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from typer.testing import CliRunner

from aeat.entrypoints.cli import app as root_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_backend(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    from aeat.adapters.persistence.storage import get_master_key_provider
    from aeat.adapters.persistence.storage.sql.engine import dispose_engine

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'taxpayer-type.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    dispose_engine()
    try:
        with get_master_key_provider():
            yield
    finally:
        dispose_engine()


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
    assert "status\tcreated" in result.output
    rows = _profile_rows(runner, "webco")
    assert rows["taxpayer_type.entity_type"] == "legal_entity"


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
