"""Source-jurisdiction validation paths for ``aeat app ledger add``."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest

from ._ledger_validation_support import _invoke, _set_profile_axis, open_bucket_session

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(autouse=True)
def _open_bucket_session(tmp_path: Path) -> Iterator[None]:
    with open_bucket_session(tmp_path):
        yield


def test_ledger_add_defaults_source_jurisdiction_to_es_for_resident_general(
    tmp_path: Path,
) -> None:
    """RESIDENT_IRPF / GENERAL: omitted --source-jurisdiction silently defaults to ES.

    LIRPF Art. 8 universal-base presumption: residents are taxed on
    worldwide income with a Spanish-source default. The default-ES path
    must not require operator action."""

    # Default profile is already RESIDENT_IRPF / GENERAL, so no fact mutation is needed.

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "office supplies",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["source_jurisdiction"] == "ES", payload


def test_ledger_add_refuses_when_source_jurisdiction_omitted_for_impatriado(
    tmp_path: Path,
) -> None:
    """RESIDENT_IRPF / IMPATRIADO: omitted --source-jurisdiction refused (Art. 93 LIRPF).

    The Beckham regime taxes Spanish-source income at the flat IRNR rate
    while excluding foreign-source from the base. A silent ES default
    would quietly include foreign-source amounts in the IRPF base -
    Art. 93.5 LIRPF segregation. Force operator to declare.

    The test mutates the profile through the canonical profile orchestration
    service so the ledger command sees the same stored facts it would read
    after the operator wizard updates the active profile."""

    _set_profile_axis("irpf.special_regime", "impatriado")
    _set_profile_axis("irpf.special_regime_start_date", "2023-01-01")

    result = _invoke(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "consulting",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    # The refusal key carries Beckham / Art. 93 anchoring.
    assert (
        "source-jurisdiction" in combined
        or "source_jurisdiction" in combined
        or "Beckham" in combined
        or "Art" in combined
        or "93" in combined
    ), combined


def test_ledger_add_refuses_when_source_jurisdiction_omitted_for_non_resident(
    tmp_path: Path,
) -> None:
    """NON_RESIDENT_IRNR: omitted --source-jurisdiction refused (TRLIRNR Art. 2/10).

    Non-residents file IRNR under RDLeg 5/2004; per-row jurisdiction is
    the authoritative provenance for the IRNR scope filter. Operator
    must declare it on every ledger entry - no silent default is safe
    because the IRNR base only admits Spanish-source income.

    The test mutates the profile through the canonical profile orchestration
    service so the ledger command sees the same stored facts it would read
    after the operator wizard updates the active profile."""

    # UE/EEE country chosen so ue_eee_status is True and the
    # TaxpayerProfile _check_representante_fiscal_required validator does
    # not fire; this lets the source-jurisdiction refusal surface cleanly
    # without provisioning the full TRLIRNR Art. 10 representante tuple.
    # The non-EU/EEA path (Argentina, Morocco) is tracked under the schema-
    # fix follow-up that resolves the representante_fiscal_nombre catalogue gap.
    _set_profile_axis("taxpayer_type.country_of_fiscal_residence", "FR")
    _set_profile_axis("taxpayer_type.fiscal_residency", "non_resident_irnr")

    result = _invoke(
        [
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "50.00",
            "--direction",
            "OUTGOING",
            "--description",
            "non-resident expense",
            # NO --source-jurisdiction
        ],
    )
    assert result.exit_code != 0, result.output
    combined = result.output or ""
    assert (
        "source-jurisdiction" in combined
        or "source_jurisdiction" in combined
        or "IRNR" in combined
        or "TRLIRNR" in combined
    ), combined


def test_ledger_add_honours_operator_source_jurisdiction_override_for_resident(
    tmp_path: Path,
) -> None:
    """Operator-supplied --source-jurisdiction is preserved verbatim regardless of profile.

    Resident IRPF / GENERAL operator may legitimately add a foreign-source
    row (e.g. dividendos de fuente extranjera). The default-ES rule must
    not override an explicit operator value."""

    result = _invoke(
        [
            "--format",
            "json",
            "app",
            "ledger",
            "add",
            "--date",
            "2026-04-15",
            "--amount",
            "100.00",
            "--direction",
            "INCOMING",
            "--description",
            "foreign dividend",
            "--source-jurisdiction",
            "FR",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)["result"]
    assert payload["transaction"]["source_jurisdiction"] == "FR", payload
