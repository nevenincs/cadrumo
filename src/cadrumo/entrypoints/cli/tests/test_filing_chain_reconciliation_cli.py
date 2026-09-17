"""A period chain reconciled with AEAT across pulls, amendments and overrides, through the CLI only.

Three consecutive Modelo 130 quarters of one synthetic taxpayer. AEAT's
register is a recorded in-memory transport installed at the composition
factory; capture, receipt parsing, reconciliation, observation layers,
calculation and the clean-state gate all run for real.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest

from ....core.period import Period
from ....core.time.clock import today_madrid
from ....domain.calculations.registry.tests.published_authority import (
    published_snapshot,
    published_supported_filing_years,
)
from ....tests.cli_envelope import require_schema_envelope, unwrap_envelope_notices
from ... import live_state_composition
from ._m130_source_support import seed_m130_income_transaction
from ._modelo_work_ux_support import operator_profile_facts
from ._recorded_sede_filed_port import (
    RecordedPresentation,
    RecordedSedeFiledDataPort,
    RecordedSedeRegister,
    justificante_number,
    madrid_instant,
)
from .cli_runner import invoke_cached_cli
from .modelo_cli import create_modelo_work_unit_via_cli
from .modelo_profile_seed import ProfileSeeder, seed_profile

__all__ = ["seed_profile"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TAX_ID = "12345678Z"


def _scenario_year() -> int:
    """The newest supported ejercicio whose third quarter is already fileable."""
    support = published_supported_filing_years()
    year = min(support.horizon, today_madrid().year - 1)
    assert support.admits_coordinate(year), (support, year)
    return year


def _m130_values(**values: str) -> dict[str, Decimal]:
    return {casilla_id.removeprefix("c"): Decimal(value) for casilla_id, value in values.items()}


def _quarter_values(*, ingresos: str, gastos: str, prior_payments: str, payment: str) -> dict[str, Decimal]:
    """A consistent M130 apartado I result: 20% of the net, minus earlier payments."""
    net = Decimal(ingresos) - Decimal(gastos)
    return {
        "saldo-negativo-fin-periodo": Decimal("0.00"),
        **_m130_values(
            c01=ingresos,
            c02=gastos,
            c03=str(net),
            c04=str((net * Decimal("0.20")).quantize(Decimal("0.01"))),
            c05=prior_payments,
            c06="0.00",
            c07=payment,
            c12=payment,
            c14=payment,
            c17=payment,
            c19=payment,
        ),
    }


@dataclass(slots=True)
class _Scenario:
    year: int
    register: RecordedSedeRegister
    output_root: Path

    def period(self, code: str) -> Period:
        return Period.from_year_and_code(self.year, code)

    def presentation(
        self,
        code: str,
        serial: int,
        values: Mapping[str, Decimal],
        *,
        month: int,
        tipo_solicitud: str | None = None,
    ) -> RecordedPresentation:
        csv = f"SYNTH{self.year}130{code}{serial:04d}"
        presented_at = madrid_instant(self.year, month, 15, 10)
        return RecordedPresentation(
            period=self.period(code),
            # The register row and its receipt share the Numero de justificante.
            expediente_id=justificante_number("130", csv, presented_at),
            csv=csv,
            presented_at=presented_at,
            casilla_values=values,
            total_a_ingresar=values["19"],
            tipo_solicitud=tipo_solicitud,
        )

    def pull(self, *presentations: RecordedPresentation, period: str | None = None) -> dict[str, Any]:
        self.register.holds(*presentations)
        period_args = ["--period", period] if period is not None else []
        result = invoke_cached_cli(
            [
                "--format", "json",
                "app", "live", "filed", "pull",
                "--modelo", "130", "--year", str(self.year),
                "--output-root", str(self.output_root),
                *period_args,
            ],
        )  # fmt: skip
        assert result.exit_code == 0, result.output
        return require_schema_envelope(result.stdout)

    def revision_id(self, code: str) -> str:
        return str(published_snapshot("130", filing_year=self.year, period=code).revision.id)


def _cli(*args: str) -> Any:
    result = invoke_cached_cli(["--format", "json", *args])
    return result


def _ok(*args: str) -> dict[str, Any]:
    result = _cli(*args)
    assert result.exit_code == 0, result.output
    return require_schema_envelope(result.stdout)


def _outcomes(payload: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["period"]["code"]: item for item in payload["reconciliations"]}


def _chain(year: int, code: str) -> list[dict[str, Any]]:
    listed = _ok("app", "modelo", "filing-record", "list", "--modelo", "130", "--include-superseded")
    return sorted(
        (record for record in listed["records"] if record["filing_year"] == year and record["period"]["code"] == code),
        key=lambda record: record["filed_at"],
    )


@pytest.fixture
def scenario(seed_profile: ProfileSeeder, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[_Scenario]:
    """A seeded synthetic taxpayer whose AEAT register is the recorded transport."""
    year = _scenario_year()
    seed_profile(
        label="operator",
        facts={
            **operator_profile_facts(activity_start_date=f"{year}-01-01"),
            "taxpayer_type.entity_type": "natural_person",
            "taxpayer_type.irpf_income_categories": "actividad_economica",
            "irpf.estimation_regime": "directa_normal",
        },
    )
    register = RecordedSedeRegister(modelo="130", tax_id=_TAX_ID, full_name="OPERATOR READINESS")

    def recorded_port(**_: object) -> RecordedSedeFiledDataPort:
        return RecordedSedeFiledDataPort(register)

    monkeypatch.setattr(live_state_composition, "build_filed_data_capture_port", recorded_port)
    yield _Scenario(year=year, register=register, output_root=tmp_path / "filed")


def test_filing_chain_reconciles_pulls_amendments_and_overrides(scenario: _Scenario) -> None:
    year = scenario.year
    q1_original = _quarter_values(ingresos="10000.00", gastos="4000.00", prior_payments="0.00", payment="1200.00")
    q2_original = _quarter_values(ingresos="20000.00", gastos="8000.00", prior_payments="1200.00", payment="1200.00")
    q1_original_entry = scenario.presentation("1T", 1, q1_original, month=4)
    q2_original_entry = scenario.presentation("2T", 2, q2_original, month=7)

    # 1. Both originals arrive from AEAT and are appended as confirmed.
    pulled = scenario.pull(q1_original_entry, q2_original_entry)
    outcomes = _outcomes(pulled)
    assert {code: item["outcome"] for code, item in outcomes.items()} == {"1T": "appended", "2T": "appended"}
    for code in ("1T", "2T"):
        (entry,) = _chain(year, code)
        assert (entry["origin"], entry["confirmation"], entry["declaration_kind"]) == ("aeat", "confirmada", "original")
        assert entry["filing_record_id"] == outcomes[code]["filing_record_id"]
    q1_confirmed_id = outcomes["1T"]["filing_record_id"]

    # 2. A local complementaria of 1T is pending and amends the confirmed original.
    amended = _ok(
        "app", "modelo", "work", "amend",
        "--from-filing-record", q1_confirmed_id,
        "--kind", "complementaria",
        "--reason", "income under-declared",
        *_set_flags(_quarter_values(ingresos="11000.00", gastos="4000.00", prior_payments="0.00", payment="1400.00")),
    )  # fmt: skip
    assert amended["confirmation"] == "pendiente"
    assert amended["amends_filing_record_id"] == q1_confirmed_id
    first_amendment_id = amended["filing_record_id"]

    q3_work_unit_id = create_modelo_work_unit_via_cli(
        modelo="130", filing_year=year, period="3T", revision=scenario.revision_id("3T")
    )
    seed_m130_income_transaction(amount=Decimal("30000.00"), filing_year=year, source_key="chain-q3")
    calculated = _ok(
        "app", "modelo", "work", "calculate", q3_work_unit_id,
        "--casilla", "06=0.00",
        "--binding", "irpf.previous_year_economic_activity_net_income=13000",
    )  # fmt: skip
    # Casilla 05 carries the pending 1T correction (1400) and the confirmed 2T payment (1200).
    assert Decimal(calculated["casilla_values"]["05"]) == Decimal("2600.00")
    first_chain = _chain(year, "1T")
    assert [(entry["status"], entry["confirmation"]) for entry in first_chain] == [
        ("supersedido", "confirmada"),
        ("vigente", "pendiente"),
    ]
    q3_target = ("--modelo", "130", "--year", str(year), "--period", "3T")
    blockers = _q3_dependency_blockers(q3_target)
    assert set(blockers) == {"1T"}
    assert "local_filing_missing_external_evidence" in blockers["1T"]
    assert _cli("app", "modelo", "work", "file", *q3_target).exit_code != 0

    # 3. A re-pull that only sees the 1T original confirms nothing new.
    repulled = scenario.pull(q1_original_entry, period="1T")
    assert [item["outcome"] for item in repulled["reconciliations"]] == ["already_recorded"]
    assert _chain(year, "1T")[-1]["confirmation"] == "pendiente"

    # 4. Amending again discards the unpresented correction and amends the confirmed original.
    q1_corrected = _quarter_values(ingresos="11500.00", gastos="4000.00", prior_payments="0.00", payment="1500.00")
    second = _ok(
        "app", "modelo", "work", "amend",
        "--from-filing-record", first_amendment_id,
        "--kind", "complementaria",
        "--reason", "further income found",
        *_set_flags(q1_corrected),
    )  # fmt: skip
    assert second["amends_filing_record_id"] == q1_confirmed_id
    by_id = {entry["filing_record_id"]: entry for entry in _chain(year, "1T")}
    assert by_id[first_amendment_id]["confirmation"] == "descartada"
    assert by_id[second["filing_record_id"]]["confirmation"] == "pendiente"

    # 5. AEAT now holds the matching complementaria: the pending entry is confirmed.
    q1_complementaria = scenario.presentation("1T", 3, q1_corrected, month=5, tipo_solicitud="complementaria")
    confirmed = scenario.pull(q1_original_entry, q1_complementaria, period="1T")
    assert sorted(item["outcome"] for item in confirmed["reconciliations"]) == ["already_recorded", "confirmed"]
    viewed = _ok("app", "modelo", "filing-record", "view", second["filing_record_id"])
    assert viewed["confirmation"] == "confirmada"
    assert viewed["aeat_register"]["expediente_id"] == q1_complementaria.expediente_id
    assert viewed["observation_layers"]["pending_local"] is None
    assert viewed["observation_layers"]["official"]["casilla_values"]["07"] == "1500.00"
    assert _q3_dependency_blockers(q3_target) == {}
    filed = _cli("app", "modelo", "work", "file", *q3_target)
    assert filed.exit_code == 0, filed.output
    q3_filed = require_schema_envelope(filed.stdout)
    assert q3_filed["confirmation"] == "pendiente"
    q3_values = {casilla_id: Decimal(value) for casilla_id, value in calculated["casilla_values"].items()}
    q3_presentation = scenario.presentation("3T", 4, q3_values, month=10)
    q3_pulled = scenario.pull(q3_presentation, period="3T")
    assert [item["outcome"] for item in q3_pulled["reconciliations"]] == ["confirmed"]
    assert q3_pulled["reconciliations"][0]["filing_record_id"] == q3_filed["filing_record_id"]


def _q3_dependency_blockers(target: tuple[str, ...]) -> dict[str, set[str]]:
    """Verify the target and return, per source 130 period, the clean-state blockers it reports."""
    verified = _cli("app", "modelo", "work", "verify", *target)
    print("VERIFY", verified.exit_code, verified.stdout[:6000])
    report = require_schema_envelope(verified.stdout)
    blockers: dict[str, set[str]] = {}
    for finding in report["findings"]:
        if finding["kind"] != "cross_period_dependency_unclean":
            continue
        (evidence,) = finding["action"]["evidence"]
        values = evidence["values"]
        if values["source_modelo"] == "130":
            blockers.setdefault(values["period"], set()).update(values["blocker_codes"].split("|"))
    if not blockers:
        assert report["granted_verificado_completo"] is True, report
    return blockers


def _set_flags(values: Mapping[str, Decimal]) -> list[str]:
    flags: list[str] = []
    for casilla_id, value in values.items():
        flags += ["--set", f"{casilla_id}={value}"]
    return flags


__all__ += ["unwrap_envelope_notices"]
