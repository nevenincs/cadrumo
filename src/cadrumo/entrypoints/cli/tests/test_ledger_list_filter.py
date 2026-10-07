"""`aeat app ledger list --filter` real-behaviour suite.

Drives the real CLI against the isolated profile + hand-authored ledger-corpus
fixture and asserts that ``ledger list --filter KEY=VALUE`` narrows the listing
through the same typed :class:`LedgerReviewFilterSpec` that ``ledger review``
uses. Before this verb the only ``ledger list`` controls were paging
(``--limit``/``--offset``) and the organisational ``--group`` label, forcing an
operator to dump the whole ledger and grep; these tests lock the filter axes
(period incl. bare-year, classification, text) and the parse-error surface.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from click.testing import Result

from ....adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ....adapters.persistence.storage.master_key.active_session import close_active_bucket_session
from ....application.ledger.list_query import LedgerTransactionListQuery, query_ledger_transaction_list
from ....application.review.filter import LedgerReviewFilterSpec
from ....application.user_profile import profile_summary
from ....application.user_profile.login_session import authenticate_profile_for_invocation, resolve_login_target
from ....core.config import override_settings
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.transactions.models import TransactionCatalogue
from ....tests.inventory import FIXTURES_DIR
from ...ledger_action_composition import compose_ledger_action_ports
from .cli_runner import invoke_cached_cli
from .runtime_profile_cli_fixture import NativeCliProfileFixture, native_cli_profile_scope

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="requires native Windows profile workers"),
]

_CORPUS = FIXTURES_DIR / "financial" / "ledger-corpus"
_FILES = (
    "bbva-business-eur.csv",
    "caixabank-personal.csv",
    "revolut-multi.csv",
    "n26-savings.csv",
)


_PROFILE_FACTS = {
    "taxpayer_type.entity_type": "natural_person",
    "identity.name": "Ledger",
    "identity.surnames": "Filter Reader",
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
    """Import the ledger corpus once for the file.

    Every test here only lists; none writes to the ledger. Importing four CSVs
    per test spent most of the file's runtime rebuilding a world no test
    changed. The real CLI worker is kept alive for the module, and every
    invocation uses the registered profile's actual password.
    """
    with native_cli_profile_scope(tmp_path_factory.mktemp("ledger-list-filter")) as profile:
        profile.register(label="native-ledger-filter-corpus", facts=_PROFILE_FACTS)
        assert profile.label is not None
        close_active_bucket_session()
        for name in _FILES:
            result = _invoke_cli(
                profile,
                ["app", "ledger", "import", "--file", str(_CORPUS / name), "--provider", "csv"],
            )
            assert result.exit_code == 0, f"{name}: {result.output}"
        yield profile


def _invoke_cli(profile: NativeCliProfileFixture, args: list[str]) -> Result:
    """Invoke a profile-bound command through human password admission."""
    assert profile.label is not None
    close_active_bucket_session()
    with override_settings(cadrumo_cli_reveal_identifiers=True):
        result = invoke_cached_cli(
            ["--profile", profile.label, "--profile-secrets-stdin", *args],
            input=json.dumps({"profile_passphrase": profile.passphrase}),
        )
    assert profile.passphrase not in result.output
    return result


def _list_rows(profile: NativeCliProfileFixture, *filters: str) -> list[dict[str, Any]]:
    args = ["--format", "json", "app", "ledger", "list"]
    for clause in filters:
        args += ["--filter", clause]
    listed = _invoke_cli(profile, args)
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def _list_rows_with_options(profile: NativeCliProfileFixture, *args: str) -> list[dict[str, Any]]:
    listed = _invoke_cli(profile, ["--format", "json", "app", "ledger", "list", *args])
    assert listed.exit_code == 0, listed.output
    payload = json.loads(listed.output)
    return payload.get("result", payload).get("rows", [])


def test_list_without_filter_returns_full_ledger(_corpus_profile: NativeCliProfileFixture) -> None:
    """The unfiltered baseline lists the whole operating-scale corpus."""
    assert len(_list_rows(_corpus_profile)) >= 500


def test_period_filter_narrows_to_one_year(_corpus_profile: NativeCliProfileFixture) -> None:
    """A year-qualified annual period filter scopes the listing to that year only.

    The corpus is cross-year; a ``period=0A`` + ``year=YYYY`` filter must return a strict,
    non-empty subset of the full ledger, and every returned row's date must fall
    in that year — proving the filter actually applies rather than passing the
    full set through.
    """
    full = _list_rows(_corpus_profile)
    years = sorted({str(r["date"])[:4] for r in full})
    assert len(years) >= 2, f"corpus must span >=2 years to exercise the year filter, got {years}"
    target = years[0]
    filtered = _list_rows(_corpus_profile, "period=0A", f"year={target}")
    assert filtered, f"period=0A + year={target} must match the rows dated in {target}"
    assert len(filtered) < len(full), "a single-year filter must be a strict subset of the cross-year ledger"
    assert all(str(r["date"]).startswith(target) for r in filtered)


def test_period_year_options_match_filter_clauses(_corpus_profile: NativeCliProfileFixture) -> None:
    """Convenience ``--period/--year`` flags route through the same typed filter as ``--filter``."""
    full = _list_rows(_corpus_profile)
    target = sorted({str(r["date"])[:4] for r in full})[0]

    option_rows = _list_rows_with_options(_corpus_profile, "--period", "0A", "--year", target)
    filter_rows = _list_rows(_corpus_profile, "period=0A", f"year={target}")

    assert {row["full_id"] for row in option_rows} == {row["full_id"] for row in filter_rows}
    assert option_rows, "period/year options must match the same non-empty annual subset as --filter"


def test_year_option_without_period_preserves_typed_refusal(_corpus_profile: NativeCliProfileFixture) -> None:
    """Bare ``--year`` exposes one canonical refusal in every locale."""
    for locale in ("ca", "en", "es", "hu"):
        result = _invoke_cli(
            _corpus_profile,
            ["--language", locale, "--format", "json", "app", "ledger", "list", "--year", "2025"],
        )

        assert result.exit_code != 0
        document = json.loads(result.output)
        error = document["error"]
        assert error["code"] == "REFUSED_REVIEW_FILTER_PARSE"
        assert error["category"] == "REFUSED"
        assert error["context"] == {
            "key": "period",
            "raw_token": "<redacted>",
            "reason": "ledger-period-year-pairing",
            "safe_token": "<redacted>",
        }
        action = error["action"]
        assert action["failed_condition_id"] == "cli.ledger.filter.valid"
        assert action["evidence"] == [
            {
                "condition_id": "cli.ledger.filter.valid",
                "evidence_id": "cli.ledger.filter.valid.observation",
                "provenance": "runtime_observation",
                "values": {"ledger_filter_valid": False, "reason": "ledger-period-year-pairing"},
            },
        ]
        assert action["action"] is None
        assert action["conditionality"] == "not_applicable"
        assert action["no_recovery_outcome"] == "operator_decision"


def test_year_filter_without_period_refuses_with_typed_no_recovery(_corpus_profile: NativeCliProfileFixture) -> None:
    """A partial period predicate stays typed without reconstructed guidance."""
    result = _invoke_cli(_corpus_profile, ["app", "ledger", "list", "--filter", "year=2026"])

    assert result.exit_code != 0
    assert 'action.failed_condition_id: "cli.ledger.filter.valid"' in result.output
    assert '"ledger_filter_valid":false' in result.output
    assert '"reason":"ledger-period-year-pairing"' in result.output
    assert "action.action: null" in result.output
    assert 'action.no_recovery_outcome: "operator_decision"' in result.output


def test_classification_filter_narrows_to_one_class(_corpus_profile: NativeCliProfileFixture) -> None:
    """A classification filter returns only rows of that business class.

    On import every row lands NOT_YET_PROCESSED, so filtering to that class
    returns the full ledger and filtering to BUSINESS (none yet) returns empty —
    proving the classification predicate discriminates rather than no-opping.
    """
    # The shared LedgerReviewFilterSpec validates the classification value
    # against the BusinessClassification enum, whose members are UPPERCASE
    # (NOT_YET_PROCESSED / BUSINESS / ...), so the filter value is uppercase —
    # the same contract `ledger review --filter classification=` already uses.
    full = _list_rows(_corpus_profile)
    not_processed = _list_rows(_corpus_profile, "classification=NOT_YET_PROCESSED")
    assert len(not_processed) == len(full)
    assert all(r.get("business_classification") == "NOT_YET_PROCESSED" for r in not_processed)
    business = _list_rows(_corpus_profile, "classification=BUSINESS")
    assert business == [], "no row is classified BUSINESS on raw import, so the filter must return empty"


def test_text_filter_matches_description_substring(_corpus_profile: NativeCliProfileFixture) -> None:
    """A text filter returns only rows whose description carries the needle."""
    full = _list_rows(_corpus_profile)
    needle = "Transferencia"
    expected = [r for r in full if needle.casefold() in r["description"].casefold()]
    assert expected, "corpus must carry at least one 'Transferencia' row to exercise the text filter"
    filtered = _list_rows(_corpus_profile, f"text={needle}")
    assert {r["full_id"] for r in filtered} == {r["full_id"] for r in expected}


def test_combined_filters_compose_as_intersection(_corpus_profile: NativeCliProfileFixture) -> None:
    """Two filter clauses compose: the result is the intersection of both."""
    full = _list_rows(_corpus_profile)
    target_year = sorted({str(r["date"])[:4] for r in full})[0]
    combined = _list_rows(_corpus_profile, "period=0A", f"year={target_year}", "classification=NOT_YET_PROCESSED")
    year_only = _list_rows(_corpus_profile, "period=0A", f"year={target_year}")
    # Every raw-import row is NOT_YET_PROCESSED, so the classification clause is a
    # no-op intersection here: combined == year_only, and both are a strict
    # subset of the full ledger.
    assert {r["full_id"] for r in combined} == {r["full_id"] for r in year_only}
    assert len(combined) < len(full)


def test_direction_filter_narrows_to_one_money_flow(_corpus_profile: NativeCliProfileFixture) -> None:
    """A ``direction`` filter returns only rows of that money-flow direction.

    The corpus carries both incoming (credits) and outgoing (debits) rows. A
    ``direction=incoming`` filter must return a strict, non-empty subset of the
    full ledger whose every row is incoming, and the incoming + outgoing subsets
    must partition the directional rows — proving the CLI forwards the parsed
    direction into the shared query rather than passing the full set through.
    The lowercase value exercises the case-insensitive parse the shared spec
    added for the natural ``incoming`` / ``outgoing`` operator spelling.
    """
    full = _list_rows(_corpus_profile)
    directions = {r["direction"] for r in full}
    assert {"INCOMING", "OUTGOING"} <= directions, f"corpus must carry both directions, got {directions}"

    incoming = _list_rows(_corpus_profile, "direction=incoming")
    outgoing = _list_rows(_corpus_profile, "direction=outgoing")
    assert incoming, "direction=incoming must match the credited rows"
    assert outgoing, "direction=outgoing must match the debited rows"
    assert len(incoming) < len(full), "a single-direction filter must be a strict subset of the full ledger"
    assert all(r["direction"] == "INCOMING" for r in incoming)
    assert all(r["direction"] == "OUTGOING" for r in outgoing)
    # The two directional subsets are disjoint and exactly cover the full set's
    # INCOMING/OUTGOING rows (the corpus has no INTERNAL_TRANSFER on raw import).
    expected_incoming = {r["full_id"] for r in full if r["direction"] == "INCOMING"}
    assert {r["full_id"] for r in incoming} == expected_incoming


def test_direction_filter_uppercase_value_matches_too(_corpus_profile: NativeCliProfileFixture) -> None:
    """The canonical uppercase enum value resolves identically to lowercase.

    ``direction=INCOMING`` (the raw :class:`TransactionDirection` member value)
    and ``direction=incoming`` must select the same rows, confirming the
    case-insensitive parse accepts both the natural operator spelling and the
    canonical form rather than silently rejecting one.
    """
    lower = {r["full_id"] for r in _list_rows(_corpus_profile, "direction=incoming")}
    upper = {r["full_id"] for r in _list_rows(_corpus_profile, "direction=INCOMING")}
    assert lower == upper
    assert lower, "direction filter must match a non-empty incoming set"


def test_unknown_filter_key_is_rejected(_corpus_profile: NativeCliProfileFixture) -> None:
    """An out-of-catalogue filter key fails loudly at the CLI boundary.

    The unknown key is refused with a non-zero exit (it does not silently
    pass through and list every row). The offending token's exact rendering is
    governed by the shared error-boundary box layout, so this asserts the typed
    failed condition rather than the echoed substring: a bare exit-code check
    would also be satisfied by an unrelated failure, which is the way this test
    could pass while the filter catalogue stopped refusing.
    """
    result = _invoke_cli(_corpus_profile, ["app", "ledger", "list", "--filter", "bogus=1"])

    assert result.exit_code != 0
    assert 'action.failed_condition_id: "cli.ledger.filter.valid"' in result.output


def test_malformed_filter_token_is_rejected(_corpus_profile: NativeCliProfileFixture) -> None:
    """A ``--filter`` token without ``=`` is a parse error, not a silent pass."""
    result = _invoke_cli(_corpus_profile, ["app", "ledger", "list", "--filter", "period"])

    assert result.exit_code != 0
    assert 'action.failed_condition_id: "cli.ledger.filter.valid"' in result.output


def test_period_filter_combined_shape_refuses_with_typed_no_recovery(
    _corpus_profile: NativeCliProfileFixture,
) -> None:
    """A combined period token is redacted and carries no invented action."""
    combined_period = "2026Q1"
    result = _invoke_cli(
        _corpus_profile,
        ["app", "ledger", "list", "--filter", f"period={combined_period}", "--filter", "year=2026"],
    )

    assert result.exit_code != 0
    assert 'action.failed_condition_id: "cli.ledger.filter.valid"' in result.output
    assert '"ledger_filter_valid":false' in result.output
    assert '"reason":"invalid-value-ledger-period"' in result.output
    assert "action.action: null" in result.output
    assert 'action.no_recovery_outcome: "operator_decision"' in result.output


def test_a_filtered_list_reads_the_ledger_once(
    _corpus_profile: NativeCliProfileFixture,
    authority_operation: PinnedAuthorityOperation,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The listing and its review filter share one read of the stored catalogue.

    Both halves used to load it, which decrypted and validated every stored
    row twice per filtered listing. The CLI worker journey above covers the
    actual runtime boundary; this assertion observes the shared application
    selector directly, where a parent-process repository probe is meaningful.
    """
    assert _corpus_profile.label is not None
    bucket_id = resolve_login_target(_corpus_profile.label).bucket_id
    close_active_bucket_session()
    login = authenticate_profile_for_invocation(
        name=_corpus_profile.label,
        passphrase_callback=lambda: _corpus_profile.passphrase,
        profile_decode_context=authority_operation.profile_decode_context(),
    )
    assert login.bucket_id == bucket_id

    loads: list[str] = []
    load = TransactionCatalogueRepository.load

    def counting(self: TransactionCatalogueRepository) -> TransactionCatalogue:
        loads.append(self.bucket_id)
        return load(self)

    monkeypatch.setattr(TransactionCatalogueRepository, "load", counting)
    try:
        page = query_ledger_transaction_list(
            LedgerTransactionListQuery(spec=LedgerReviewFilterSpec.from_strings(("classification=NOT_YET_PROCESSED",))),
            bucket_id=bucket_id,
            ports=compose_ledger_action_ports(bucket_id=bucket_id, operation=authority_operation),
        )
        assert page.results, "the corpus must reach the filter, or a single read proves nothing"
        assert loads == [bucket_id]
    finally:
        close_active_bucket_session()


def test_a_listing_observes_the_profile_inventory_once(
    _corpus_profile: NativeCliProfileFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The session gate, the active-bucket resolver, the profile label and the
    sandbox notice all ask which profiles exist; a read-only command answers
    them from one observation of the store.
    """
    observed: list[object] = []
    observe = profile_summary._observe_summary_inventory

    def counting(root: Path) -> profile_summary.ProfileSummaryInventory:
        observed.append(root)
        return observe(root)

    monkeypatch.setattr(profile_summary, "_observe_summary_inventory", counting)
    rows = _list_rows(_corpus_profile)

    assert rows, "the listing must reach its profile-bound rendering, or one observation proves nothing"
    assert len(observed) == 1
