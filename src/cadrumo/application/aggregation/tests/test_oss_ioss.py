"""Real-behaviour tests for the OSS / IOSS application aggregator.

Tests are grounded in three external authorities:

* The BOE-published Spanish IVA rate registry
  (``registry/aeat/iva/rates.toml``), itself anchored to Ley 37/1992
  and Council Directive 2006/112/EC. The rates the tests assert
  against (DE general 19 %, FR general 20 %) come from the registry,
  not from the test author.
* The Real Decreto-ley 7/2021 + Orden HAC/610/2021 transposing the
  EU 2021 OSS / IOSS package into Spanish law. The transposition is
  what fixes "destination Member State rate" as the legal anchor for
  every supply filed under the Esquema Unión.
* LIVA art. 163 unvicies (Esquema Unión), 163 octiesdecies (Esquema
  Exterior), and 163 quinvicies (Esquema Importación). The three
  articles share the destination-MS-rate operative rule the wrapper
  enforces.

No test computes the expected outcome by re-applying the wrapper's
own formula to a hand-picked base / rate; every accept / reject
expectation is derived from the published DE / FR / IT rate in the
substrate registry. Boundary tests guard against parallel
implementations and unauthorised CLI surfaces.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.ledger_bindings import OssIossLedgerObservation
from cadrumo.domain.calculations.registry.schema import ModeloRevision

from ....core.directory_scan import scan_directory
from ....core.resources import resources
from ....domain.iva import (
    EUMemberState,
    InvoiceKind,
    IvaRateKind,
    IvaRateNotFoundError,
    OssIossRegime,
    TransactionKind,
)
from ....tests import REPO_ROOT
from .. import (
    OssIossLedgerCandidate,
    aggregate_oss_ioss_bindings,
    validate_oss_ioss_observation,
    validate_oss_ioss_observations,
)
from ..errors import AggregationValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


_SUPPLY_DATE = date(2025, 7, 15)


@cache
def _modelo_369_union_revision() -> ModeloRevision:
    modelo = resources().modelos.get("369")
    return modelo.revisions["esquema-union"]


def _candidate(
    *,
    ledger_id: str = "ledger-1",
    transaction_date: date = _SUPPLY_DATE,
    regime: OssIossRegime = OssIossRegime.UNION_SCHEME,
    destination: EUMemberState = EUMemberState.DE,
    rate_kind: IvaRateKind = IvaRateKind.GENERAL,
    direction: InvoiceKind = InvoiceKind.ISSUED,
    transaction_kind: TransactionKind = TransactionKind.OSS_UNION_SERVICES,
    base: Decimal = Decimal("100"),
    iva: Decimal = Decimal("19"),
) -> OssIossLedgerCandidate:
    return OssIossLedgerCandidate(
        ledger_id=ledger_id,
        transaction_date=transaction_date,
        regime=regime,
        destination_member_state=destination,
        rate_kind=rate_kind,
        invoice_direction=direction,
        transaction_kind=transaction_kind,
        base_amount=base,
        iva_amount=iva,
    )


# ---------------------------------------------------------------------------
# Candidate schema
# ---------------------------------------------------------------------------


def test_candidate_is_strict_and_frozen_and_rejects_extras() -> None:
    """The candidate's ``model_config`` declares
    ``strict=True``, ``frozen=True``, and ``extra="forbid"``. Extras
    must fail validation; mutation after construction must raise."""

    from pydantic import ValidationError

    candidate = _candidate()
    with pytest.raises(ValidationError, match=r"Extra inputs are not permitted"):
        OssIossLedgerCandidate.model_validate(
            {
                "ledger_id": "ledger-1",
                "transaction_date": _SUPPLY_DATE,
                "regime": OssIossRegime.UNION_SCHEME,
                "destination_member_state": EUMemberState.DE,
                "rate_kind": IvaRateKind.GENERAL,
                "invoice_direction": InvoiceKind.ISSUED,
                "transaction_kind": TransactionKind.OSS_UNION_SERVICES,
                "base_amount": Decimal("100"),
                "iva_amount": Decimal("19"),
                "unknown_axis": "extra-value",
            },
        )
    with pytest.raises(ValidationError, match=r"frozen|Instance is frozen"):
        candidate.base_amount = Decimal("200")


def test_candidate_rejects_negative_amounts() -> None:
    """The wrapper does not represent refunds via negative base / IVA;
    upstream classifiers must flip the line into a separate Esquema
    flow."""

    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=r"base_amount|greater than"):
        _candidate(base=Decimal("-1"))
    with pytest.raises(ValidationError, match=r"iva_amount|greater than"):
        _candidate(iva=Decimal("-1"))


# ---------------------------------------------------------------------------
# validate_oss_ioss_observation — IVA rate validation
# ---------------------------------------------------------------------------


def test_validation_accepts_candidate_matching_destination_de_general_rate() -> None:
    """DE general rate is 19 % per ``registry/aeat/iva/rates.toml``
    (anchored to the German UStG and Council Directive 2006/112/EC).
    Base 100 EUR with IVA 19 EUR satisfies the destination-MS rate."""

    candidate = _candidate(
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("19"),
    )
    observation = validate_oss_ioss_observation(candidate)
    assert isinstance(observation, OssIossLedgerObservation)
    assert observation.ledger_id == candidate.ledger_id
    assert observation.base_amount == Decimal("100")
    assert observation.iva_amount == Decimal("19")


def test_validation_accepts_candidate_matching_destination_fr_general_rate() -> None:
    """FR general rate is 20 % per the substrate registry. Base 100 EUR
    with IVA 20 EUR satisfies the destination-MS rate. The wrapper
    must accept any of the 27 registered Member States, not just
    Germany."""

    candidate = _candidate(
        destination=EUMemberState.FR,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("20"),
    )
    observation = validate_oss_ioss_observation(candidate)
    assert observation.destination_member_state is EUMemberState.FR
    assert observation.iva_amount == Decimal("20")


def test_validation_rejects_candidate_with_iva_off_by_six_euros_on_destination_de() -> None:
    """A line declaring 25 EUR IVA on base 100 EUR for destination DE
    is inconsistent with DE's 19 % general rate. The wrapper rejects
    the line so the registry resolver never aggregates the bad
    data."""

    candidate = _candidate(
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("25"),
    )
    with pytest.raises(AggregationValidationError, match=r"iva|rate|tolerance|drift"):
        validate_oss_ioss_observation(candidate)


def test_validation_rejects_zero_iva_when_destination_rate_is_non_zero() -> None:
    """An OSS Unión services line marked at general rate must carry
    non-zero IVA in any Member State whose general rate is non-zero.
    Zero IVA on a 100 EUR base at DE general 19 % is a hard
    blocker."""

    candidate = _candidate(
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("0"),
    )
    with pytest.raises(AggregationValidationError, match=r"iva|zero|rate|drift|tolerance"):
        validate_oss_ioss_observation(candidate)


def test_validation_accepts_one_cent_rounding_drift() -> None:
    """Ledger amounts are persisted at 2 dp; a one-cent drift between
    the derived and persisted IVA is rounding noise, not a data
    quality blocker. Base 100 EUR at DE 19 % = 19 EUR exactly, so a
    persisted 19.01 EUR is within the one-cent tolerance."""

    candidate = _candidate(
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("19.01"),
    )
    observation = validate_oss_ioss_observation(candidate)
    assert observation.iva_amount == Decimal("19.01")


def test_validation_rejects_beyond_tolerance_drift() -> None:
    """A two-cent drift (19.02 instead of 19.00 expected) exceeds the
    one-cent tolerance and the wrapper must reject."""

    candidate = _candidate(
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("19.02"),
    )
    with pytest.raises(AggregationValidationError, match=r"iva|tolerance|drift|exceed"):
        validate_oss_ioss_observation(candidate)


def test_validation_attaches_diagnostic_context_to_the_error() -> None:
    """The raised :class:`AggregationValidationError` must carry a
    structured context payload pointing at the offending ledger row
    so the modelo orchestrator can surface a humane error to the
    operator."""

    candidate = _candidate(
        ledger_id="line-bad-iva",
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("25"),
    )
    with pytest.raises(AggregationValidationError, match=r"oss_ioss|mismatches|destination_rate") as exc_info:
        validate_oss_ioss_observation(candidate)
    context = exc_info.value.context
    assert context is not None
    assert context["ledger_id"] == "line-bad-iva"
    assert context["destination_member_state"] == "de"
    assert context["rate_kind"] == "general"
    assert context["base_amount"] == "100"
    assert context["persisted_iva_amount"] == "25.00"
    assert context["expected_iva_amount"] == "19.00"


def test_validation_raises_rate_not_found_for_pre_registry_date() -> None:
    """When the supply date is before any registered rate window, the
    substrate raises :class:`IvaRateNotFoundError`. The wrapper
    must propagate that signal — the line cannot be aggregated
    without an applicable rate."""

    candidate = _candidate(
        transaction_date=date(1900, 1, 1),
        destination=EUMemberState.DE,
        rate_kind=IvaRateKind.GENERAL,
        base=Decimal("100"),
        iva=Decimal("19"),
    )
    with pytest.raises(IvaRateNotFoundError, match=r"DE|1900|rate"):
        validate_oss_ioss_observation(candidate)


# ---------------------------------------------------------------------------
# validate_oss_ioss_observations — batch fast-fail
# ---------------------------------------------------------------------------


def test_batch_validation_returns_observations_in_input_order() -> None:
    """The batch helper preserves input order so downstream
    aggregators can reason about line-stable processing."""

    candidates = [
        _candidate(ledger_id="a", iva=Decimal("19")),
        _candidate(ledger_id="b", iva=Decimal("19")),
        _candidate(ledger_id="c", iva=Decimal("19")),
    ]
    observations = validate_oss_ioss_observations(candidates)
    assert tuple(o.ledger_id for o in observations) == ("a", "b", "c")


def test_batch_validation_raises_on_first_offending_candidate() -> None:
    """A bad line in the middle of the batch fails the whole batch.
    The wrapper does not partially-aggregate around bad data."""

    candidates = [
        _candidate(ledger_id="a", iva=Decimal("19")),
        _candidate(ledger_id="b", iva=Decimal("99")),  # bad
        _candidate(ledger_id="c", iva=Decimal("19")),
    ]
    with pytest.raises(AggregationValidationError, match=r"iva|tolerance|drift|exceed"):
        validate_oss_ioss_observations(candidates)


# ---------------------------------------------------------------------------
# aggregate_oss_ioss_bindings — full pipeline against the Modelo 369 registry
# ---------------------------------------------------------------------------


def test_aggregator_routes_validated_observations_to_the_registry() -> None:
    """End-to-end: validated candidates land in the Modelo 369
    Esquema Unión binding for DE services issued by an autónomo and
    the resolver returns the published-rate-weighted sum."""

    revision = _modelo_369_union_revision()
    candidates = [
        _candidate(ledger_id="a", base=Decimal("100"), iva=Decimal("19")),
        _candidate(ledger_id="b", base=Decimal("200"), iva=Decimal("38")),
    ]
    result = aggregate_oss_ioss_bindings(revision, candidates)
    # Both candidates must contribute to the DE-services binding's
    # aggregate. Inclusion is pinned by requiring the aggregate to
    # exceed the larger single-candidate value.
    aggregated = result["modelo-369-union-de-services-21pct"]
    assert aggregated > Decimal("38"), (
        f"DE-services aggregate = {aggregated} not greater than max single candidate 38; only one candidate contributed"
    )


def test_aggregator_rejects_when_any_candidate_fails_rate_validation() -> None:
    """The aggregator never reaches the registry resolver when even
    one candidate disagrees with the destination rate. The Modelo
    369 calculation revision never persists an aggregate over bad
    data."""

    revision = _modelo_369_union_revision()
    candidates = [
        _candidate(ledger_id="a", base=Decimal("100"), iva=Decimal("19")),
        _candidate(ledger_id="b", base=Decimal("200"), iva=Decimal("99")),  # bad
    ]
    with pytest.raises(AggregationValidationError, match=r"iva|tolerance|drift|exceed"):
        aggregate_oss_ioss_bindings(revision, candidates)


def test_aggregator_returns_zero_when_no_candidates_match_a_binding() -> None:
    """The Modelo 369 Esquema Unión revision still emits a value for
    every binding even when no candidates match (zero is the natural
    aggregation of an empty set under sum). The resolver's own
    coverage of this case is exercised here through the application
    wrapper to confirm the pipeline does not short-circuit on an
    empty match."""

    revision = _modelo_369_union_revision()
    candidates = [
        _candidate(
            ledger_id="a",
            destination=EUMemberState.IT,  # not the DE binding's selector
            base=Decimal("100"),
            iva=Decimal("22"),  # IT general = 22 %
        ),
    ]
    result = aggregate_oss_ioss_bindings(revision, candidates)
    assert result["modelo-369-union-de-services-21pct"] == Decimal("0")


# ---------------------------------------------------------------------------
# Boundary regression guards
# ---------------------------------------------------------------------------


def test_no_parallel_oss_ioss_aggregator_exists() -> None:
    """The application aggregator at
    ``src/cadrumo/application/aggregation/_oss_ioss.py`` is the sole
    surface that consumes
    :func:`resolve_ledger_oss_aggregation_binding_values` outside the
    registry's own tests. Any other module that hand-rolls an OSS /
    IOSS aggregation pipeline competes with the canonical wrapper and
    must be removed."""

    source_root = REPO_ROOT / "src" / "cadrumo"
    canonical = source_root / "application" / "aggregation" / "_oss_ioss.py"
    forbidden_pattern = "resolve_ledger_oss_aggregation_binding_values"
    offenders: list[Path] = []
    for py_file in scan_directory(source_root, pattern="*.py", recursive=True):
        if py_file.name.startswith("test_"):
            continue
        if py_file == canonical:
            continue
        # Tests under domain/calculations/registry/ legitimately
        # exercise the resolver directly; that path is skipped above.
        # Same for the bindings modules that define / re-export the resolver.
        if py_file.name in {"_bindings.py", "_ledger_bindings.py"} and "calculations" in py_file.parts:
            continue
        if py_file.name == "__init__.py" and py_file.parent.name == "registry":
            continue
        text = py_file.read_text(encoding="utf-8")
        if forbidden_pattern in text:
            offenders.append(py_file)
    assert offenders == [], (
        "Parallel OSS/IOSS aggregation surfaces detected outside the canonical "
        "`cadrumo.application.aggregation._oss_ioss` module: "
        + ", ".join(str(p.relative_to(source_root)) for p in offenders)
    )


def test_no_cli_root_oss_or_ioss_verb_is_registered() -> None:
    """OSS / IOSS has no operator-facing CLI verb. Consumption is
    via ``aeat app modelo calculate``. The CLI tree must not
    register an ``oss``, ``ioss``, ``cadrumo oss``, ``cadrumo ioss``,
    ``app iva oss``, or ``app iva ioss`` command."""

    cli_root = REPO_ROOT / "src" / "cadrumo" / "entrypoints" / "cli"
    forbidden_command_names = (
        '"oss"',
        '"ioss"',
        "'oss'",
        "'ioss'",
        'name="oss"',
        'name="ioss"',
    )
    offenders: dict[Path, list[str]] = {}
    for py_file in scan_directory(cli_root, pattern="*.py", recursive=True):
        if py_file.name.startswith("test_"):
            continue
        text = py_file.read_text(encoding="utf-8")
        hits = [needle for needle in forbidden_command_names if needle in text]
        if hits:
            offenders[py_file] = hits
    assert offenders == {}, "CLI tree registers a forbidden OSS/IOSS verb: " + ", ".join(
        f"{p.relative_to(cli_root)} ({hits})" for p, hits in offenders.items()
    )
