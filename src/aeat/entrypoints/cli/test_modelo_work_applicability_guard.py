"""End-to-end CLI verification for the ``work create`` applicability guard.

Round-4 finding M4: ``modelo work create --modelo 202`` succeeded for a
natural person with no guard — the operator could provision a work unit
for a modelo their taxpayer model positively excludes, and the engine
would then be asked to run an Impuesto sobre Sociedades cuota for a
natural person.

These tests drive the real ``aeat`` CLI against an isolated encrypted
backend and pin the guard behaviour:

* a natural-person profile is refused a ``work create --modelo 202``
  (an Impuesto sobre Sociedades pago fraccionado);
* a legal-entity profile is refused a ``work create --modelo 100``
  (the IRPF Renta);
* the ``--allow-not-applicable`` escape hatch lets the refusal be
  bypassed deliberately, and the bypass is recorded in the payload;
* a modelo that does apply to the profile is still created normally —
  the guard does not over-block.

No mocks: the guard runs the real :func:`derive_modelo_applicability`
against the real persisted profile.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aeat.adapters.persistence.storage.sql import dispose_engine
from aeat.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture(autouse=True)
def _isolated_cli_backend(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    dispose_engine()
    monkeypatch.setenv("AEAT_SECRET_STORE_BACKEND", "unsecured")
    monkeypatch.setenv("AEAT_ALLOW_UNENCRYPTED", "1")
    monkeypatch.setenv("AEAT_DATABASE_URL", f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
    monkeypatch.setenv("AEAT_LOCAL_STORAGE_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("AEAT_TOKEN_DIR", str(tmp_path / "tokens"))
    monkeypatch.setenv("AEAT_RUNS_DIR", str(tmp_path / "runs"))
    monkeypatch.setenv("AEAT_FINANCIAL_TXS_DIR", str(tmp_path / "txs"))
    monkeypatch.setenv("AEAT_INVOICES_DIR", str(tmp_path / "invoices"))
    monkeypatch.setenv("AEAT_DRAFTS_DIR", str(tmp_path / "drafts"))
    try:
        yield tmp_path
    finally:
        dispose_engine()


def _create_natural_person() -> None:
    """Create a declared natural-person profile (autónomo)."""

    result = invoke_cached_cli(
        [
            "config", "profile", "create", "operator",
            "--quiet", "--accept-defaults",
            "--tax-id", "12345678Z",
            "--name", "Operator",
            "--activity", "design",
            "--entity-type", "natural_person",
            "--irpf-income-categories", "actividad_economica",
            "--irpf-estimation-regime", "directa_normal",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def _create_legal_entity() -> None:
    """Create a declared legal-entity profile (sociedad limitada)."""

    result = invoke_cached_cli(
        [
            "config", "profile", "create", "company",
            "--quiet", "--accept-defaults",
            "--tax-id", "B12345674",
            "--name", "Company",
            "--activity", "consulting",
            "--entity-type", "legal_entity",
            "--legal-entity-form", "sl",
        ]
    )  # fmt: skip
    assert result.exit_code == 0, result.output


def test_work_create_refuses_modelo_202_for_a_natural_person(
    _isolated_cli_backend: Path,
) -> None:
    """M4: a natural person is refused a Modelo 202 work unit.

    Modelo 202 is the Impuesto sobre Sociedades pago fraccionado — a
    natural person never files it. The guard consults the derived
    applicability and refuses the create cleanly rather than
    provisioning a work unit the engine could never calculate correctly.
    """

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", "2025", "--period", "1T",
            "--revision", "2025-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    # The refusal names the modelo and points at the escape hatch.
    assert "202" in result.output
    assert "--allow-not-applicable" in result.output


def test_work_create_refuses_modelo_100_for_a_legal_entity(
    _isolated_cli_backend: Path,
) -> None:
    """M4: a sociedad limitada is refused a Modelo 100 work unit.

    Modelo 100 is the IRPF Renta — a legal entity is an Impuesto sobre
    Sociedades contribuyente and never files it. The guard refuses the
    create."""

    _create_legal_entity()
    result = invoke_cached_cli(
        [
            "app", "modelo", "work", "create",
            "--modelo", "100", "--year", "2025", "--period", "0A",
            "--revision", "2023-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code != 0, result.output
    assert "Traceback" not in result.output
    assert "100" in result.output


def test_work_create_allow_not_applicable_bypasses_the_guard(
    _isolated_cli_backend: Path,
) -> None:
    """The ``--allow-not-applicable`` escape hatch lets an operator with
    a genuine reason override the refusal; the bypass is recorded in the
    create payload so the audit trail shows it was deliberate."""

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "202", "--year", "2025", "--period", "1T",
            "--revision", "2025-y-siguientes",
            "--allow-not-applicable",
        ]
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    # The work unit was provisioned, and the bypass is auditable.
    assert payload["status"] == "created"
    assert payload["applicability_guard_bypassed"] is True


def test_work_create_allows_an_applicable_modelo(
    _isolated_cli_backend: Path,
) -> None:
    """The guard does not over-block: a modelo that applies to the
    profile is created normally. An autónomo en estimación directa owes
    Modelo 130, so its work unit is provisioned without a refusal."""

    _create_natural_person()
    result = invoke_cached_cli(
        [
            "--format", "json",
            "app", "modelo", "work", "create",
            "--modelo", "130", "--year", "2025", "--period", "1T",
            "--revision", "2019-y-siguientes",
        ]
    )  # fmt: skip

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["status"] == "created"
    # The guard was not bypassed — the modelo genuinely applies.
    assert payload["applicability_guard_bypassed"] is False
