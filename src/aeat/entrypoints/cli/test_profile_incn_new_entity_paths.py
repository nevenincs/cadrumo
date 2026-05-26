"""Non-interactive `config profile create` / `edit` for the INCN and
new-entity profile facts.

These tests exercise the real CLI surface for the two optional profile
facts added by the corporate-tax-runtime plan:

* `--incn-prior-12-months` — the importe neto de la cifra de negocios
  of the prior 12 months, a typed Decimal that gates the Modelo 202
  modality split at the 6.000.000 EUR threshold (LIS Art. 40.3).
* `--new-entity-first-two-profit-periods` — the LIS Art. 29
  first-two-profit-making-periods state that opts a newly-created
  legal entity into the 15 percent rate override.

Both facts are optional: an unset profile must not carry the fact at
all, so the downstream engine stays at INCOMPLETE (for the modality
gate) or on the otherwise-applicable rate (for the new-entity
override) instead of guessing.

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

    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'incn-new-entity.db').as_posix()}")
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


def test_incn_prior_12_months_flag_stores_the_decimal_fact() -> None:
    """The optional INCN figure of the prior 12 months lands in its own
    profile fact. Stored verbatim as a canonical decimal token so the
    Modelo 202 modality gate (6.000.000 EUR threshold, LIS Art. 40.3)
    can decide without re-parsing."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "incn-co",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--legal-entity-form",
            "sl",
            "--tax-id",
            "B66012345",
            "--activity",
            "asesoria",
            "--incn-prior-12-months",
            "7500000.00",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "incn-co")
    assert rows["taxpayer_type.incn_prior_12_months"] == "7500000.00"


def test_profile_creates_without_incn_flag_leaves_fact_unset() -> None:
    """The INCN is optional: a profile created with no
    `--incn-prior-12-months` flag must not carry the fact at all, so
    the downstream Modelo 202 modality gate stays at INCOMPLETE rather
    than guessing a modality."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "no-incn-co",
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
    rows = _profile_rows(runner, "no-incn-co")
    assert "taxpayer_type.incn_prior_12_months" not in rows


def test_new_entity_first_two_profit_periods_flag_stores_the_bool() -> None:
    """The optional LIS Art. 29 first-two-profit-periods state lands in
    its own profile fact. A positively-declared True opts the entity
    into the 15 percent new-entity rate override."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "new-co",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--legal-entity-form",
            "sl",
            "--tax-id",
            "B66012345",
            "--activity",
            "consultoria",
            "--new-entity-first-two-profit-periods",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "new-co")
    assert rows["taxpayer_type.new_entity_first_two_profit_periods"] == "true"


def test_profile_creates_without_new_entity_flag_records_false() -> None:
    """The new-entity state is opt-in: a profile created with neither
    `--new-entity-first-two-profit-periods` nor `--no-...` lands the
    CONFIRM widget's ``"false"`` default. The 15 percent override is
    triggered only by a positively-declared ``"true"``, so a stored
    ``"false"`` keeps the entity on the otherwise-applicable
    sub-form rate."""

    runner = CliRunner()
    result = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "no-new-co",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--legal-entity-form",
            "sl",
            "--tax-id",
            "B66012345",
            "--activity",
            "asesoria",
        ],
    )

    assert result.exit_code == 0, result.output
    rows = _profile_rows(runner, "no-new-co")
    assert rows.get("taxpayer_type.new_entity_first_two_profit_periods", "false") == "false"


def test_edit_patches_incn_and_new_entity_flags_onto_existing_profile() -> None:
    """`config profile edit --quiet` must patch the INCN and the
    new-entity state onto an existing profile without disturbing the
    other facts. Patch semantics, not a full rewrite."""

    runner = CliRunner()
    create = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "create",
            "edit-co",
            "--quiet",
            "--accept-defaults",
            "--entity-type",
            "legal_entity",
            "--legal-entity-form",
            "sl",
            "--tax-id",
            "B66012345",
            "--activity",
            "asesoria",
        ],
    )
    assert create.exit_code == 0, create.output

    edit = runner.invoke(
        root_app,
        [
            "config",
            "profile",
            "edit",
            "edit-co",
            "--quiet",
            "--incn-prior-12-months",
            "1234567.89",
            "--new-entity-first-two-profit-periods",
        ],
    )
    assert edit.exit_code == 0, edit.output

    rows = _profile_rows(runner, "edit-co")
    assert rows["taxpayer_type.incn_prior_12_months"] == "1234567.89"
    assert rows["taxpayer_type.new_entity_first_two_profit_periods"] == "true"
    # Other facts left untouched by the patch edit.
    assert rows["taxpayer_type.entity_type"] == "legal_entity"
    assert rows["taxpayer_type.legal_entity_form"] == "sl"
