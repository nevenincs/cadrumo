"""Drive the employee, employee-autonomo and payer personas through an installed ``aeat`` executable.

Every product write is a public CLI command run as a fresh process. The expected figures come from
:mod:`personas`, which works them by hand from the law and the forms' instructions, and the journey compares
each calculated credit with them. Each persona must reach complete verification and a local export of its
annual Modelo 100. Nothing is sent to AEAT.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from collections.abc import Iterable, Mapping, Sequence
from contextlib import AbstractContextManager, ExitStack
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import IndexedRegistryAuthority
from cadrumo.domain.calculations.registry.authority_store import AUTHORITY_DESCRIPTOR_FILENAME
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.domain.calculations.registry.bindings_previous_filing import PreviousFilingProvider
from dev.acceptance.installed_cli import InstalledCli, profile_create_args

from .cli_journey import (
    JourneyError,
    attest_no_withholding,
    command_result,
    create_m130_work,
    imputation_criterion_args,
    ingest_income_fixture,
)
from .personas import (
    ACTIVITY_HOLDER_INPUT,
    ACTIVITY_KEY_INPUT,
    FREELANCER,
    WORK_HOLDER_INPUT,
    AutonomoOracle,
    EmployeeOracle,
    EmployerCertificate,
    build_autonomo_oracle,
    build_employee_oracle,
    build_payer_oracle,
    build_payer_side,
)
from .scenario import money

_ACTOR: Final[str] = "persona-acceptance"
_M100_ANNUAL_PERIOD: Final[str] = "0A"
_NORMAL_MODALITY_BINDING: Final[str] = "renta-modelo-100-estimacion-directa-es-normal"
_ACTIVITY_CHAIN_CASILLAS: Final[tuple[str, ...]] = ("0171", "0180", "0218", "0220", "0224")
_CREDIT_CASILLAS: Final[tuple[str, ...]] = ("0596", "0597", "0598", "0599", "0603", "0604", "0609")
_ACTIVITY_INVENTORY: Final[str] = "actividad-servicios"
#: Last year's return: an activity yield above the 130 minoracion and no negative bases left to carry.
_PRIOR_RETURN_ROWS: Final[Mapping[str, Decimal]] = {
    "0224": Decimal("50000.00"),
    "1384": Decimal(),
    "1387": Decimal(),
    "1390": Decimal(),
    "1391": Decimal(),
}


@dataclass(frozen=True, slots=True)
class PersonaEvidence:
    """Compact machine-readable result of one persona journey."""

    persona: str
    year: int
    credits: dict[str, str]
    verification_granted: bool
    export_size: int
    export_sha256: str
    commands: int
    blocker: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-safe representation."""
        return dict[str, object](asdict(self))


@dataclass(frozen=True, slots=True)
class JourneyEdition:
    """What the pinned authority says about the persona's filing year, read once before the journey starts."""

    prior_year_supported: bool
    """Whether the year before is inside the support envelope, so that its return can be imported at all."""
    m100_binding_sources: Mapping[str, BindingSourceKind]
    """Each binding the selected annual Modelo 100 revision declares, with the kind of source it reads."""
    m100_prior_return_casillas: Mapping[str, str]
    """The ``previous_filing`` bindings that read last year's Modelo 100, each with the casilla it reads."""

    def manual_bindings(self, *assignments: tuple[str, str]) -> tuple[str, ...]:
        """Return ``--binding`` options only for assignments this edition takes as the operator's own input.

        A binding the edition derives from another source, such as the profile, is not the operator's to state.
        """
        return _binding_options(
            (binding, value)
            for binding, value in assignments
            if self.m100_binding_sources.get(binding) is BindingSourceKind.MANUAL_INPUT
        )

    def prior_return_bindings(self, rows: Mapping[str, Decimal]) -> tuple[str, ...]:
        """State last year's figures directly when no earlier return can be held.

        At the envelope's floor the product cannot hold last year's return, so the bindings that would read it
        stay unresolved until the operator states them. The journey states the same figures it imports in
        every other year, and refuses an edition that reads a casilla it has no figure for.
        """
        if self.prior_year_supported:
            return ()
        unknown = sorted(set(self.m100_prior_return_casillas.values()) - set(rows))
        if unknown:
            raise JourneyError(f"the edition reads last year's casillas {unknown}, which the persona does not state")
        return _binding_options(
            (binding, f"{rows[casilla]:.2f}") for binding, casilla in sorted(self.m100_prior_return_casillas.items())
        )


def _binding_options(assignments: Iterable[tuple[str, str]]) -> tuple[str, ...]:
    return tuple(item for binding, value in assignments for item in ("--binding", f"{binding}={value}"))


def read_journey_edition(authority_root: Path, *, year: int) -> JourneyEdition:
    """Read the envelope and the selected Modelo 100 revision for ``year`` from the installed authority."""
    authority = IndexedRegistryAuthority(authority_root.resolve(strict=True) / AUTHORITY_DESCRIPTOR_FILENAME)
    try:
        with authority.operation() as operation:
            # The binding set is a calculation input, so a year projected from another edition answers too.
            revision = operation.snapshot(
                "100", filing_year=year, period=_M100_ANNUAL_PERIOD, grade=RegistryAuthorityGrade.CALCULATION
            ).revision
            bindings = revision_bindings_by_id(revision)
            return JourneyEdition(
                prior_year_supported=operation.supported_filing_years().admits_filing_year(year - 1),
                m100_binding_sources={binding_id: binding.source for binding_id, binding in bindings.items()},
                m100_prior_return_casillas={
                    binding_id: str(casilla)
                    for binding_id, binding in bindings.items()
                    if isinstance(binding.provider, PreviousFilingProvider)
                    and str(binding.provider.source_modelo) == "100"
                    for casilla in (
                        (binding.provider.source_casilla_id,)
                        if binding.provider.source_casilla_id is not None
                        else binding.provider.source_casilla_ids
                    )
                },
            )
    finally:
        authority.close()


def _create_profile(
    cli: InstalledCli, *, year: int, categories: str, regime: str, activity_start: str, criterion: bool
) -> None:
    """Create and complete the persona's profile, declaring its income classes and regime.

    ``criterion`` also declares the cobros y pagos imputation criterion of the ejercicio. Only a taxpayer with
    activity income declares one: it prints the cash election in casilla 0169, which opens the activity block
    of the return and so asks for the activity key an employee does not have.
    """
    arguments = list(profile_create_args(year))
    arguments[arguments.index("--irpf-estimation-regime") + 1] = regime
    arguments[arguments.index("--activity-start-date") + 1] = activity_start
    # The command takes one --irpf-income-categories option per category.
    position = arguments.index("--irpf-income-categories")
    arguments[position : position + 2] = [
        item for category in categories.split(",") for item in ("--irpf-income-categories", category)
    ]
    payload = json.dumps(
        {"passphrase": cli.passphrase, "passphrase_confirmation": cli.passphrase}, separators=(",", ":")
    )
    cli.run(
        (
            *arguments,
            *(imputation_criterion_args(year) if criterion else ()),
        ),
        authenticated=False,
        stdin_payload=payload,
        command="config profile create",
    )
    cli.run(("config", "profile", "complete-setup"))


def _import_official_return(
    cli: InstalledCli, *, directory: Path, modelo: str, year: int, period: str, rows: Sequence[tuple[str, Decimal]]
) -> None:
    """Import a return filed outside Cadrumo as the AEAT register entry the taxpayer holds."""
    created = command_result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                modelo,
                "--year",
                str(year),
                "--period",
                period,
                "--by",
                _ACTOR,
            )
        )
    )
    manifest = directory / f"modelo-{modelo}-{year}-{period}-register.csv"
    manifest.write_text(
        "casilla_code;value\n" + "".join(f"{code};{value:.2f}\n" for code, value in rows), encoding="utf-8"
    )
    imported = cli.run(
        (
            "app",
            "modelo",
            "filing-record",
            "import",
            str(created["work_unit_id"]),
            "--evidence-kind",
            "aeat_csv_register",
            "--evidence-id",
            f"CADRUMOSYNTHETIC{year}M{modelo}{period}",
            "--file",
            str(manifest),
            "--by",
            _ACTOR,
        ),
        allow_error=True,
    )
    if imported.get("status") == "error":
        raise JourneyError(
            f"Modelo {modelo} {period} register import refused: {json.dumps(imported.get('error'), default=str)[:900]}"
        )


def _carry_prior_year(cli: InstalledCli, *, directory: Path, year: int, edition: JourneyEdition) -> None:
    """Bring in last year's return: no negative bases to carry and an activity yield above the 130 minoracion.

    A year below the support envelope is refused at every grade, so at the envelope's floor there is no
    earlier return the product can hold; the calculation then takes the same figures as stated bindings.
    """
    if not edition.prior_year_supported:
        return
    _import_official_return(
        cli, directory=directory, modelo="100", year=year - 1, period="0A", rows=tuple(_PRIOR_RETURN_ROWS.items())
    )


def _record_certificate(
    cli: InstalledCli, *, directory: Path, year: int, certificate: EmployerCertificate, income_class: str
) -> None:
    """Record one payer's certificate file through the registered operation."""
    file = directory / f"certificate-{certificate.payer_tax_id}-{income_class}.pdf"
    file.write_bytes(f"%PDF-1.4 synthetic certificate {certificate.payer_tax_id} {income_class}".encode())
    recorded = cli.run(
        (
            "app",
            "ledger",
            "retencion-soportada",
            "record",
            certificate.payer_tax_id,
            "--ejercicio",
            str(year),
            "--income-class",
            income_class,
            "--origin",
            "payer_certificate",
            "--retencion",
            f"{certificate.retencion:.2f}",
            "--ingreso-a-cuenta",
            f"{certificate.ingreso_a_cuenta:.2f}",
            "--ingreso-a-cuenta-repercutido",
            f"{certificate.ingreso_a_cuenta_repercutido:.2f}",
            "--importe-integro",
            f"{certificate.importe_integro:.2f}",
            "--valoracion-especie",
            f"{certificate.valoracion_especie:.2f}",
            "--certificate-file",
            str(file),
        ),
        allow_error=True,
    )
    if recorded.get("status") == "error":
        raise JourneyError(f"certificate record refused: {json.dumps(recorded.get('error'), default=str)[:900]}")


def _record_no_existencias(cli: InstalledCli, *, directory: Path, year: int) -> None:
    """Record that the persona's service activity held no existencias in the ejercicio.

    The stock variation of casillas 0177 and 0182 is the difference between the existencias iniciales and
    finales, and casilla 0181 the purchases of mercaderias (Manual practico de Renta 2025, parte 1, pp. 422
    and 425). A service activity that holds no stock opens the book at zero, records no movement, and closes
    it on its movements with the statement that shows it, so all three are zero on evidence, never by default.
    """
    cli.run(
        (
            "app",
            "ledger",
            "inventory",
            "create",
            _ACTIVITY_INVENTORY,
            "--year",
            str(year),
            "--valuation-method",
            "fifo",
            "--opening-stock",
            "0",
        )
    )
    statement = directory / f"no-existencias-{year}.pdf"
    statement.write_bytes(f"%PDF-1.4 synthetic statement: no existencias held in {year}".encode())
    stored = command_result(cli.run(("app", "ledger", "inventory", "evidence-add", str(statement))))
    reference = {"reference": str(stored["reference"])}
    digest = str(stored["content_digest"])
    facts = directory / f"no-existencias-{year}.json"
    facts.write_text(
        json.dumps(
            {
                "decision_id": f"no-existencias-{year}",
                "authority": "movement_derived",
                "reason": "The service activity held no existencias at any time in the ejercicio.",
                "decision_evidence": [
                    {"reference": reference, "role": "authority_reconciliation", "content_digest": digest}
                ],
                "prior_evidence": [{"reference": reference, "content_digest": digest}],
            }
        ),
        encoding="utf-8",
    )
    recorded = cli.run(
        (
            "app",
            "ledger",
            "inventory",
            "closing-value-record",
            _ACTIVITY_INVENTORY,
            "--year",
            str(year),
            "--file",
            str(facts),
        ),
        allow_error=True,
    )
    if recorded.get("status") == "error":
        raise JourneyError(f"closing value refused: {json.dumps(recorded.get('error'), default=str)[:900]}")


def _calculate_annual(
    cli: InstalledCli, *, year: int, inputs: Sequence[str], extra: Sequence[str] = ()
) -> dict[str, Any]:
    created = command_result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "create",
                "--modelo",
                "100",
                "--year",
                str(year),
                "--period",
                "0A",
                "--revision",
                str(year),
                "--by",
                _ACTOR,
            )
        )
    )
    work_id = str(created["work_unit_id"])
    calculation = command_result(
        cli.run(
            (
                "app",
                "modelo",
                "work",
                "calculate",
                work_id,
                *inputs,
                *extra,
                "--by",
                _ACTOR,
            )
        )
    )
    return {"work_id": work_id, "calculation": calculation}


def _require_credits(calculation: dict[str, Any], expected: dict[str, Decimal]) -> dict[str, str]:
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError("Modelo 100 returned no casilla map")
    actual = {
        casilla: f"{money(Decimal(str(values[casilla]))):.2f}" for casilla in _CREDIT_CASILLAS if casilla in values
    }
    wanted = {casilla: f"{money(value):.2f}" for casilla, value in expected.items()}
    observed = {casilla: actual.get(casilla, "<unresolved>") for casilla in wanted}
    if observed != wanted:
        raise JourneyError(f"credit oracle mismatch: expected {wanted}, got {observed}")
    return actual


def _verify_and_export(
    cli: InstalledCli, *, work_id: str, calculation: dict[str, Any], output: Path
) -> tuple[bool, bytes]:
    """Require complete verification, naming each blocking finding when it is withheld, then export locally."""
    document = cli.run(
        ("app", "modelo", "work", "verify", str(calculation["calculation_revision_id"]), "--by", _ACTOR),
        allow_error=True,
    )
    verification = document.get("result")
    if not isinstance(verification, dict) or verification.get("granted_verificado_completo") is not True:
        findings = verification.get("findings") if isinstance(verification, dict) else None
        blocking = sorted(
            json.dumps(item, default=str)[:700]
            for item in findings or ()
            if isinstance(item, dict) and item.get("severity") == "blocking"
        )
        raise JourneyError(f"Modelo 100 did not verify complete; blocking findings: {blocking}")
    cli.run(("app", "modelo", "export", work_id, "--output", str(output), "--by", _ACTOR))
    return True, output.read_bytes()


def run_employee(cli: InstalledCli, *, year: int, directory: Path, edition: JourneyEdition) -> PersonaEvidence:
    """The employee: certified work withholding, an attested movable-capital class, verified and exported."""
    oracle = build_employee_oracle()
    _create_profile(
        cli,
        year=year,
        categories="trabajo,capital_mobiliario",
        regime="directa_normal",
        activity_start=f"{year - 2}-01-01",
        criterion=False,
    )
    _carry_prior_year(cli, directory=directory, year=year, edition=edition)
    for certificate in oracle.certificates:
        _record_certificate(cli, directory=directory, year=year, certificate=certificate, income_class="trabajo")
    attest_no_withholding(cli, year=year, income_class="capital_mobiliario")
    annual = _calculate_annual(
        cli,
        year=year,
        inputs=("--casilla", WORK_HOLDER_INPUT, *_casilla_inputs(oracle)),
        extra=(
            *_zero_relations(),
            *edition.manual_bindings((_NORMAL_MODALITY_BINDING, "1")),
            *edition.prior_return_bindings(_PRIOR_RETURN_ROWS),
        ),
    )
    _require_no_maternity_deduction(annual["calculation"])
    credits = _require_credits(
        annual["calculation"],
        {
            "0596": oracle.work_credit,
            "0597": Decimal(),
            "0598": Decimal(),
            "0599": Decimal(),
            "0603": Decimal(),
            "0604": Decimal(),
            "0609": oracle.work_credit,
        },
    )
    granted, exported = _verify_and_export(
        cli,
        work_id=annual["work_id"],
        calculation=annual["calculation"],
        output=directory / f"modelo-100-{year}-employee.xml",
    )
    return _evidence("employee", year, credits, granted, exported, cli)


def _casilla_inputs(oracle: EmployeeOracle) -> tuple[str, ...]:
    return tuple(item for code, value in oracle.salary_casillas for item in ("--casilla", f"{code}={value:.2f}"))


def _require_no_maternity_deduction(calculation: dict[str, Any]) -> None:
    """A taxpayer without children has no maternity deduction, whatever figures the edition asked for."""
    values = calculation.get("casilla_values")
    if not isinstance(values, dict):
        raise JourneyError("Modelo 100 returned no casilla map")
    if "0611" in values and money(Decimal(str(values["0611"]))) != 0:
        raise JourneyError(f"Modelo 100 maternity deduction is not zero: {values['0611']}")


def _zero_relations() -> tuple[str, ...]:
    """State the pagos fraccionados of Modelos 130 and 131 as the zero a filer without those modelos holds."""
    return (
        "--relation",
        "renta-modelo-130-pagos-fraccionados=0",
        "--relation",
        "renta-modelo-131-pagos-fraccionados=0",
    )


def _quarters(cli: InstalledCli, *, year: int, directory: Path, oracle: AutonomoOracle) -> None:
    """Calculate each quarter from the ledger, then import the return the taxpayer filed for it."""
    for quarter in oracle.quarters:
        work_id = create_m130_work(cli, year=year, period=quarter.period)
        calculation = command_result(cli.run(("app", "modelo", "work", "calculate", work_id, "--by", _ACTOR)))
        values = calculation.get("casilla_values")
        if not isinstance(values, dict):
            raise JourneyError(f"Modelo 130 {quarter.period} returned no casilla map")
        boxes = ("01", "02", "06", "07")
        unresolved = [code for code in boxes if code not in values]
        if unresolved:
            raise JourneyError(f"Modelo 130 {quarter.period} left boxes unresolved: {', '.join(unresolved)}")
        observed = tuple(f"{money(Decimal(str(values[code]))):.2f}" for code in boxes)
        expected = tuple(
            f"{amount:.2f}"
            for amount in (
                quarter.cumulative_income,
                quarter.casilla_02,
                quarter.cumulative_withholding,
                quarter.result,
            )
        )
        if observed != expected:
            raise JourneyError(
                f"Modelo 130 {quarter.period} boxes 01, 02, 06 and 07 oracle mismatch: "
                f"expected {expected}, got {observed}"
            )
        # The register entry states the quarter as the taxpayer filed it, by the hand-worked figures.
        rows = [
            ("01", quarter.cumulative_income),
            ("02", quarter.casilla_02),
            ("06", quarter.cumulative_withholding),
            ("07", quarter.result),
            ("saldo-negativo-fin-periodo", Decimal()),
            ("18", Decimal()),
            ("19", quarter.result),
        ]
        _import_official_return(cli, directory=directory, modelo="130", year=year, period=quarter.period, rows=rows)


def run_employee_autonomo(
    cli: InstalledCli, *, year: int, directory: Path, edition: JourneyEdition, payer_side: bool = False
) -> PersonaEvidence:
    """The employee-autonomo, and with ``payer_side`` the same taxpayer also paying a freelancer."""
    oracle = build_payer_oracle(year) if payer_side else build_autonomo_oracle(year)
    _create_profile(
        cli,
        year=year,
        categories="trabajo,actividad_economica",
        regime="directa_simplificada",
        activity_start=f"{year - 2}-03-01",
        criterion=True,
    )
    attest_no_withholding(cli, year=year, income_class="arrendamiento_inmueble_urbano_actividad")
    _carry_prior_year(cli, directory=directory, year=year, edition=edition)
    _record_no_existencias(cli, directory=directory, year=year)
    ingest_income_fixture(cli, year=year, income=oracle.income, expenses=oracle.expenses)
    _record_certificate(cli, directory=directory, year=year, certificate=oracle.employer, income_class="trabajo")
    _quarters(cli, year=year, directory=directory, oracle=oracle)
    if payer_side:
        _practise_withholding_as_payer(cli, year=year)
    annual = _calculate_annual(
        cli,
        year=year,
        inputs=(
            "--casilla",
            WORK_HOLDER_INPUT,
            "--casilla",
            f"0003={oracle.employer.importe_integro:.2f}",
            "--casilla",
            ACTIVITY_HOLDER_INPUT,
            "--casilla",
            ACTIVITY_KEY_INPUT,
        ),
        extra=(
            *edition.manual_bindings((_NORMAL_MODALITY_BINDING, "0")),
            *edition.prior_return_bindings(_PRIOR_RETURN_ROWS),
        ),
    )
    _require_no_maternity_deduction(annual["calculation"])
    credits = _require_credits(
        annual["calculation"],
        {
            "0596": oracle.employer.pago_a_cuenta,
            "0597": Decimal(),
            "0598": Decimal(),
            "0599": oracle.activity_withholding,
            "0603": Decimal(),
            "0604": oracle.pagos_fraccionados,
            "0609": oracle.total_pagos_a_cuenta,
        },
    )
    values = annual["calculation"]["casilla_values"]
    persona = "payer" if payer_side else "employee_autonomo"
    unresolved = sorted(code for code in _ACTIVITY_CHAIN_CASILLAS if code not in values)
    if unresolved:
        # The credits equal their oracles, but the activity yield the return needs is not ready to be read, so
        # the return can be neither verified nor exported. Report that rather than a verdict on the credits.
        return _evidence(
            persona, year, credits, False, b"", cli, blocker=f"activity chain unresolved: {', '.join(unresolved)}"
        )
    net = f"{money(Decimal(str(values['0224']))):.2f}"
    if net != f"{oracle.activity_net_income:.2f}":
        raise JourneyError(
            f"Modelo 100 simplified net income oracle mismatch: expected {oracle.activity_net_income}, got {net}"
        )
    granted, exported = _verify_and_export(
        cli,
        work_id=annual["work_id"],
        calculation=annual["calculation"],
        output=directory / f"modelo-100-{year}-{persona}.xml",
    )
    return _evidence(persona, year, credits, granted, exported, cli)


def _practise_withholding_as_payer(cli: InstalledCli, *, year: int) -> None:
    """Record the freelancer's invoice and aggregate its withholding into the first Modelo 111.

    The aggregation feeds the payer-side store. That store is the freelancer's credit to claim, so it
    must leave the persona's own annual credits where the oracle puts them.
    """
    fee = build_payer_side(year)
    invoice_date = f"{year}-02-10"
    paid = f"{year}-02-20"
    iva = money(fee.base * Decimal("0.21"))
    net = fee.base + iva - fee.retention
    transaction = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "add",
                "--date",
                paid,
                "--amount",
                f"{fee.base + iva:.2f}",
                "--direction",
                "OUTGOING",
                "--description",
                "Synthetic freelancer fee",
                "--classification",
                "BUSINESS",
                "--category-id",
                "asesoria_fiscal",
                "--taxable-base",
                f"{fee.base:.2f}",
                "--iva-rate",
                "0.21",
                "--iva-amount",
                f"{iva:.2f}",
                "--iva-category",
                "domestic_general",
                "--source-jurisdiction",
                "ES",
                "--idempotency-key",
                f"freelancer-{year}-1t",
            )
        )
    )
    invoice = command_result(
        cli.run(
            (
                "app",
                "ledger",
                "invoice",
                "add",
                "--kind",
                "received",
                "--counterparty-name",
                "Synthetic Freelancer",
                "--counterparty-nif",
                FREELANCER,
                "--invoice-number",
                f"FREELANCER-{year}-1T",
                "--invoice-date",
                invoice_date,
                "--taxable-base",
                f"{fee.base:.2f}",
                "--iva-rate",
                "21",
                "--country-code",
                "ES",
                "--retention-rate",
                str(fee.rate),
                "--retention-amount",
                f"{fee.retention:.2f}",
                "--iva-category",
                "domestic_general",
            )
        )
    )
    cli.run(("app", "ledger", "link", str(transaction["transaction_id"]), "--invoice-id", str(invoice["invoice_id"])))
    request = {
        "invoice_id": str(invoice["invoice_id"]),
        "income_kind": "professional",
        "scheme": "actividades_profesionales",
        "recipient_tax_status": "resident",
        "recipient_tax_regime": "irpf",
        "payment_event_id": f"payment-freelancer-{year}",
        "payment_occurred_on": paid,
        "allocation_id": f"allocation-freelancer-{year}",
        "allocated_base": f"{fee.base:.2f}",
        "allocated_withholding": f"{fee.retention:.2f}",
        "allocated_settlement": f"{net:.2f}",
        "idempotency_key": f"withholding-freelancer-{year}",
        # The payer's annual summary (Modelo 190) line for the same payment: clave G, subclave 01.
        "modelo_190_detail": {
            "source_id": str(invoice["invoice_id"]),
            "source_allocation_id": f"allocation-freelancer-{year}",
            "perceptor_tax_id": FREELANCER,
            "perceptor_legal_name": "Synthetic Freelancer",
            "transaction_date": paid,
            "clave": "G",
            "subclave": "01",
            "province_code": "28",
            "territorial_deduction_clave": 0,
            "percibido_dinerario": f"{fee.base:.2f}",
            "retencion_practicada": f"{fee.retention:.2f}",
            "incapacity_cash_perception": "0.00",
            "incapacity_cash_withholding": "0.00",
            "incapacity_kind_value": "0.00",
            "incapacity_kind_ingreso_a_cuenta": "0.00",
            "incapacity_kind_repercutido": "0.00",
            "foral_retention_estatal": "0.00",
            "foral_retention_navarra": "0.00",
            "foral_retention_araba": "0.00",
            "foral_retention_gipuzkoa": "0.00",
            "foral_retention_bizkaia": "0.00",
            "base_retenciones": f"{fee.base:.2f}",
            "porcentaje_retencion": "15.00",
        },
    }
    cli.run(
        (
            "app",
            "modelo",
            "aggregate",
            "--modelo",
            fee.modelo,
            "--year",
            str(year),
            "--period",
            fee.period,
            "--received-invoice-retencion",
            json.dumps(request, separators=(",", ":"), sort_keys=True),
        )
    )


def _evidence(
    persona: str,
    year: int,
    credits: dict[str, str],
    granted: bool,
    exported: bytes,
    cli: InstalledCli,
    *,
    blocker: str | None = None,
) -> PersonaEvidence:
    return PersonaEvidence(
        persona=persona,
        year=year,
        credits=credits,
        verification_granted=granted,
        export_size=len(exported),
        export_sha256=hashlib.sha256(exported).hexdigest(),
        commands=len(cli.commands),
        blocker=blocker,
    )


def run_persona(
    persona: str,
    *,
    executable: Path,
    authority_root: Path,
    storage_root: Path,
    output_dir: Path,
    year: int,
    runtime_scope: AbstractContextManager[object] | None = None,
) -> PersonaEvidence:
    """Run one persona in a fresh secure store and return its receipt."""
    if storage_root.exists() and any(storage_root.iterdir()):
        raise JourneyError(f"storage root must be fresh and empty: {storage_root}")
    storage_root.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    edition = read_journey_edition(authority_root, year=year)
    with ExitStack() as resources:
        if runtime_scope is not None:
            resources.enter_context(runtime_scope)
        cli = InstalledCli(
            executable, storage_root=storage_root, authority_root=authority_root, passphrase=secrets.token_urlsafe(32)
        )
        if persona == "employee":
            return run_employee(cli, year=year, directory=output_dir, edition=edition)
        return run_employee_autonomo(
            cli, year=year, directory=output_dir, edition=edition, payer_side=persona == "payer"
        )


def main(argv: Sequence[str] | None = None) -> int:
    """Run one persona and write its evidence receipt."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--authority-root", required=True, type=Path)
    parser.add_argument("--storage-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--year", required=True, type=int)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--persona", choices=("employee", "employee_autonomo", "payer"), required=True)
    args = parser.parse_args(argv)
    evidence = run_persona(
        args.persona,
        executable=args.cli,
        authority_root=args.authority_root,
        storage_root=args.storage_root,
        output_dir=args.output_dir,
        year=args.year,
    )
    rendered = json.dumps(evidence.to_dict(), indent=2, sort_keys=True)
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(f"{rendered}\n", encoding="utf-8", newline="\n")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
