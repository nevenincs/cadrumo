from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....core.config import override_settings
from ....tests.inventory import FIXTURES_DIR
from ._runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope
from .cli_runner import invoke_cached_cli

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_CORPUS_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)
_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Ledger",
    "identity.surnames": "Corpus Reviewer",
    "activities.description": "design",
    "censo.activity_start_date": "2025-01-01",
    "tax_residence.jurisdiction_scope": "common_regime",
    "iva.regime": "GENERAL",
    "iva.m303_regime_composition": "general",
    "iva.redeme_enrolled": "false",
    "iva.cash_accounting_regime_enrolled": "false",
    "iva.voluntary_sii_enrolled": "false",
    "iva.hydrocarbon_deposit_advance_payment_deduction_entitled": "false",
}


@pytest.fixture(scope="module")
def _corpus_profile(tmp_path_factory: pytest.TempPathFactory) -> Iterator[NativeCliProfileFixture]:
    """Seed one encrypted profile through the real authenticated CLI worker."""
    with native_cli_profile_scope(tmp_path_factory.mktemp("ledger-corpus-review")) as profile:
        profile.register(label="native-ledger-corpus-review", facts=_PROFILE_FACTS)
        close_active_bucket_session()
        for name in _CORPUS_FILES:
            result = _invoke(profile, ["app", "ledger", "import", "--file", str(_CORPUS / name), "--provider", "csv"])
            assert result.exit_code == 0, f"{name}: {result.output}"
        yield profile


def _invoke(profile: NativeCliProfileFixture, args: list[str]) -> Result:
    """Invoke one command against the registered profile with human custody."""
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            ["--profile", profile.label, "--profile-secrets-stdin", *args],
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _list_payload(profile: NativeCliProfileFixture, *args: str) -> dict[str, Any]:
    listed = _invoke(profile, ["--format", "json", "app", "ledger", "list", *args])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload)


def _list_rows(profile: NativeCliProfileFixture) -> list[dict[str, Any]]:
    return _list_payload(profile)["rows"]


def _find(rows: list[dict[str, Any]], needle: str) -> dict[str, Any]:
    return next(row for row in rows if needle in row["description"])


def _set_group(profile: NativeCliProfileFixture, transaction_id: str, label: str) -> None:
    result = _invoke(profile, ["app", "ledger", "update", transaction_id, "--group", label])
    assert result.exit_code == 0, result.output


def test_review_renders_corpus(_corpus_profile: NativeCliProfileFixture) -> None:
    result = _invoke(_corpus_profile, ["app", "ledger", "review"])
    assert result.exit_code == 0, result.output


def test_operator_can_filter_income_vs_expense(_corpus_profile: NativeCliProfileFixture) -> None:
    rows = _list_rows(_corpus_profile)
    incoming = [row for row in rows if row.get("direction") == "INCOMING"]
    outgoing = [row for row in rows if row.get("direction") == "OUTGOING"]
    assert incoming and outgoing, (len(incoming), len(outgoing))
    assert all(row.get("business_classification") == "NOT_YET_PROCESSED" for row in rows)
    transfer_candidates = [
        row
        for row in rows
        if any(token in row["description"] for token in ("Transferencia", "Traspaso", "Top-Up", "Exchange"))
    ]
    assert transfer_candidates, "corpus must carry transfer candidates to reclassify"


def test_status_reports_active_ledger(_corpus_profile: NativeCliProfileFixture) -> None:
    result = _invoke(_corpus_profile, ["app", "ledger", "status"])
    assert result.exit_code == 0, result.output


def test_review_filter_by_period_and_status(_corpus_profile: NativeCliProfileFixture) -> None:
    by_period = _invoke(_corpus_profile, ["app", "ledger", "review", "--filter", "period=1T", "--filter", "year=2025"])
    assert by_period.exit_code == 0, by_period.output
    by_status = _invoke(_corpus_profile, ["app", "ledger", "review", "--filter", "status=pending"])
    assert by_status.exit_code == 0, by_status.output


def test_preflight_and_check_surface_missing_facts(_corpus_profile: NativeCliProfileFixture) -> None:
    preflight = _invoke(_corpus_profile, ["app", "ledger", "preflight", "--period", "1T", "--year", "2025"])
    assert preflight.exit_code == 0, preflight.output
    check = _invoke(_corpus_profile, ["app", "ledger", "check"])
    assert check.exit_code == 0, check.output


def test_list_paging_is_honest_and_never_silently_caps(_corpus_profile: NativeCliProfileFixture) -> None:
    full = _list_payload(_corpus_profile)
    total = full["total"]
    assert total > 20, "fixture should carry enough rows to page"
    assert full["truncated"] is False
    assert full["shown"] == total
    assert len(full["rows"]) == total

    page = _list_payload(_corpus_profile, "--limit", "10")
    assert page["total"] == total
    assert page["shown"] == 10
    assert len(page["rows"]) == 10
    assert page["truncated"] is True
    assert page["rows"] == full["rows"][:10]

    nxt = _list_payload(_corpus_profile, "--limit", "10", "--offset", "10")
    assert nxt["offset"] == 10
    assert nxt["rows"] == full["rows"][10:20]
    assert nxt["truncated"] is True

    seen: list[dict[str, Any]] = []
    off = 0
    while off < total:
        win = _list_payload(_corpus_profile, "--limit", "25", "--offset", str(off))
        seen.extend(win["rows"])
        off += 25
    assert seen == full["rows"]

    last_off = (total // 25) * 25
    tail = _list_payload(_corpus_profile, "--limit", "25", "--offset", str(last_off))
    assert tail["shown"] == total - last_off


def test_list_truncation_footer_states_the_full_total(_corpus_profile: NativeCliProfileFixture) -> None:
    total = _list_payload(_corpus_profile)["total"]
    listed = _invoke(_corpus_profile, ["app", "ledger", "list", "--limit", "5"])
    assert listed.exit_code == 0, listed.output
    assert str(total) in listed.output
    assert "1-5" in listed.output


def test_group_label_assign_filter_and_grouped_display(_corpus_profile: NativeCliProfileFixture) -> None:
    rows = _list_rows(_corpus_profile)
    a = _find(rows, "Material oficina Papeleria Gomez")
    b = _find(rows, "Comida de trabajo Restaurante El Olivo")
    _set_group(_corpus_profile, a["transaction_id"], "Proyecto Acme")
    _set_group(_corpus_profile, b["transaction_id"], "Proyecto Acme")

    filtered = _list_payload(_corpus_profile, "--group", "Proyecto Acme")
    ids = {row["transaction_id"] for row in filtered["rows"]}
    assert ids == {a["transaction_id"], b["transaction_id"]}
    assert all(row["group_label"] == "Proyecto Acme" for row in filtered["rows"])

    full = _list_payload(_corpus_profile)
    labels = {row["group_label"] for row in full["rows"]}
    assert "Proyecto Acme" in labels and None in labels

    grouped = _invoke(_corpus_profile, ["app", "ledger", "list", "--by-group"])
    assert grouped.exit_code == 0, grouped.output
    assert "# Proyecto Acme" in grouped.output


def test_unrelated_update_preserves_group_label(_corpus_profile: NativeCliProfileFixture) -> None:
    rows = _list_rows(_corpus_profile)
    row = _find(rows, "Material oficina Papeleria Gomez")
    _set_group(_corpus_profile, row["transaction_id"], "Q1 viajes")

    res = _invoke(_corpus_profile, ["app", "ledger", "update", row["transaction_id"], "--notes", "revisado"])
    assert res.exit_code == 0, res.output
    after = {listed["transaction_id"]: listed for listed in _list_rows(_corpus_profile)}[row["transaction_id"]]
    assert after["group_label"] == "Q1 viajes"

    cleared = _invoke(_corpus_profile, ["app", "ledger", "update", row["transaction_id"], "--group", ""])
    assert cleared.exit_code == 0, cleared.output
    final = {listed["transaction_id"]: listed for listed in _list_rows(_corpus_profile)}[row["transaction_id"]]
    assert final["group_label"] is None
