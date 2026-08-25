"""Real-census tests for the CLI action disposition representation."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from pathlib import Path

import pytest

from ..quality.cli_action_census import CandidateRecord, current_census
from ..quality.cli_action_census_dispositions import (
    DEFAULT_DISPOSITIONS_PATH,
    CandidateDisposition,
    CandidateKey,
    DispositionRole,
    DispositionValidationError,
    ExclusionGrounding,
    checked_in_current_dispositions,
    current_exception_override_observations,
    current_tree_dispositions,
    load_authored_message_exclusions,
    load_dispositions,
    main,
    render_dispositions,
    validate_dispositions,
    validate_exception_override_owners,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def candidates() -> tuple[CandidateRecord, ...]:
    """Use the real live census, never a reimplemented candidate model."""
    records = current_census()
    assert records, "the current tree must contain real action-guidance census candidates"
    return records


def _disposition(
    candidate: CandidateRecord,
    *,
    role: DispositionRole = DispositionRole.PRODUCER,
    reason: str = "The current source role was directly observed by the canonical census.",
) -> CandidateDisposition:
    return CandidateDisposition(key=CandidateKey.from_candidate(candidate), role=role, reason=reason)


def _write_rows(path: Path, rows: tuple[CandidateDisposition, ...]) -> tuple[CandidateDisposition, ...]:
    path.write_text(render_dispositions(rows), encoding="utf-8")
    return load_dispositions(path)


def test_disposition_roles_are_the_closed_campaign_taxonomy() -> None:
    """Only the accepted adjudication roles can enter a serialized ledger."""
    assert {role.value for role in DispositionRole} == {
        "canonical_owner",
        "producer",
        "transformer",
        "renderer",
        "validator",
        "test",
        "excluded",
    }


def test_toml_round_trip_preserves_all_five_real_census_identity_fields(
    tmp_path: Path,
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """The checked-in format keeps a real source identity rather than line locators."""
    source = candidates[0]
    expected = _disposition(source, role=DispositionRole.CANONICAL_OWNER)

    parsed = _write_rows(tmp_path / "dispositions.toml", (expected,))

    assert parsed == (expected,)
    assert parsed[0].key == CandidateKey.from_candidate(source)
    assert validate_dispositions((source,), parsed) == parsed


def test_current_tree_ledger_exactly_matches_the_mechanical_live_census() -> None:
    """A new site, changed identity, or retired row fails the checked-in current-tree join."""
    candidates = current_census()
    rows = load_dispositions(DEFAULT_DISPOSITIONS_PATH)

    assert checked_in_current_dispositions() == rows
    assert current_tree_dispositions(candidates) == rows


def test_current_tree_ledger_rejects_a_mutated_unadjudicated_candidate() -> None:
    """Adding one live candidate cannot inherit a nearby ledger row's adjudication."""
    candidates = current_census()
    rows = load_dispositions(DEFAULT_DISPOSITIONS_PATH)
    unadjudicated = CandidateRecord(
        path="src/cadrumo/application/overview/_data_prep.py",
        enclosing_symbol="_work_unit_step",
        role="producer",
        alias="next_action",
        action_identity="declare_next_action('operator.unreviewed')",
        line=1,
        column=0,
    )

    with pytest.raises(DispositionValidationError, match="missing disposition for current census candidate"):
        validate_dispositions((*candidates, unadjudicated), rows)


def test_current_tree_adjudication_fails_closed_for_an_unrecognized_action_alias() -> None:
    """A scanner-discovered alias cannot be silently classified by a nearby known shape."""
    candidate = CandidateRecord(
        path="src/cadrumo/application/overview/_data_prep.py",
        enclosing_symbol="_work_unit_step",
        role="producer",
        alias="unreviewed_action_field",
        action_identity="declare_next_action('operator.unreviewed')",
        line=1,
        column=0,
    )

    with pytest.raises(DispositionValidationError, match="has no disposition rule"):
        current_tree_dispositions((candidate,))


def test_action_identity_preserves_source_whitespace_but_rejects_whitespace_only_values(
    tmp_path: Path,
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """AST identities are exact source values, unlike normalized symbol fields."""
    source = replace(candidates[0], action_identity="  aeat app ledger list  ")
    expected = _disposition(source, role=DispositionRole.PRODUCER)
    path = tmp_path / "spaced-identity.toml"

    parsed = _write_rows(path, (expected,))

    assert parsed == (expected,)
    assert validate_dispositions((source,), parsed) == parsed

    path.write_text(
        render_dispositions((expected,)).replace(
            'action_identity = "  aeat app ledger list  "', 'action_identity = "   "'
        ),
        encoding="utf-8",
    )
    with pytest.raises(DispositionValidationError, match="missing or empty 'action_identity'"):
        load_dispositions(path)


def test_complete_reconciliation_rejects_missing_and_duplicate_current_rows(
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """One real candidate cannot cover either an omitted or a duplicated peer."""
    first, second = candidates[:2]
    first_row = _disposition(first)

    with pytest.raises(DispositionValidationError) as missing:
        validate_dispositions((first, second), (first_row,))
    assert "missing disposition for current census candidate" in str(missing.value)
    assert CandidateKey.from_candidate(second).render() in str(missing.value)

    with pytest.raises(DispositionValidationError) as duplicate:
        validate_dispositions((first,), (first_row, first_row))
    assert "duplicate current disposition" in str(duplicate.value)


def test_reconciliation_rejects_a_stale_serialized_candidate_key(
    tmp_path: Path,
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """A source change cannot inherit an old opinion through a partial key."""
    source = candidates[0]
    stale_key = replace(CandidateKey.from_candidate(source), action_identity="<stale-action-identity>")
    parsed = _write_rows(
        tmp_path / "stale.toml",
        (CandidateDisposition(key=stale_key, role=DispositionRole.PRODUCER, reason="Deliberate stale-row probe."),),
    )

    with pytest.raises(DispositionValidationError) as stale:
        validate_dispositions((source,), parsed)
    assert "stale disposition has no current census candidate" in str(stale.value)
    assert "missing disposition for current census candidate" in str(stale.value)


def test_loader_reports_an_unrecognized_role_alongside_other_row_errors(
    tmp_path: Path,
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """Malformed rows fail loudly and collectively instead of silently disappearing."""
    document = render_dispositions((_disposition(candidates[0]),)).replace(
        'role = "producer"',
        'role = "unrecognized"',
    )
    document = document.replace(
        'reason = "The current source role was directly observed by the canonical census."',
        'reason = ""',
    )
    path = tmp_path / "invalid-role.toml"
    path.write_text(document, encoding="utf-8")

    with pytest.raises(DispositionValidationError) as invalid:
        load_dispositions(path)
    assert "unrecognized disposition role 'unrecognized'" in str(invalid.value)
    assert "missing or empty 'reason'" in str(invalid.value)


def test_loader_rejects_schema_drift_and_unknown_fields_at_every_scope(
    tmp_path: Path,
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """The ledger version and every TOML scope remain closed against silent drift."""
    document = render_dispositions((_disposition(candidates[0]),))
    document = document.replace("[meta]\n", "unknown_top_level = true\n\n[meta]\n")
    document = document.replace("schema_version = 3", "schema_version = 4\nunknown_meta = true")
    document = document.replace(
        'reason = "The current source role was directly observed by the canonical census."',
        'reason = "The current source role was directly observed by the canonical census."\nunknown_row = true',
    )
    path = tmp_path / "schema-drift.toml"
    path.write_text(document, encoding="utf-8")

    with pytest.raises(DispositionValidationError) as invalid:
        load_dispositions(path)
    messages = invalid.value.errors
    assert messages == tuple(sorted(messages))
    assert str(invalid.value).splitlines() == list(messages)
    assert any("schema_version must be 3" in message for message in messages)
    assert any("unrecognized top-level field(s): unknown_top_level" in message for message in messages)
    assert any("[meta]: unrecognized field(s): unknown_meta" in message for message in messages)
    assert any("unrecognized field(s): unknown_row" in message for message in messages)

    with pytest.raises(DispositionValidationError) as repeated:
        load_dispositions(path)
    assert repeated.value.errors == messages


def test_checked_in_authored_message_exclusion_is_an_exact_source_fingerprint() -> None:
    """The lone non-registry root call is not a broad path exemption."""
    exclusions = load_authored_message_exclusions(DEFAULT_DISPOSITIONS_PATH)

    assert len(exclusions) == 1
    (exclusion,) = exclusions
    assert exclusion.fingerprint.startswith("src/cadrumo/core/errors/__init__.py|CadrumoError.__init__|")
    assert "unregistered base" in exclusion.reason


def test_reconciliation_rejects_duplicate_census_input(
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """A duplicated scanner row cannot disappear behind one disposition record."""
    source = candidates[0]

    with pytest.raises(DispositionValidationError, match="census emitted duplicate candidate key"):
        validate_dispositions((source, source), (_disposition(source),))


def test_excluded_rows_require_symbol_function_and_grounded_reason(
    tmp_path: Path,
    candidates: tuple[CandidateRecord, ...],
) -> None:
    """An exclusion names the real source alias and enclosing function, never a line."""
    source = next(candidate for candidate in candidates if "." in candidate.enclosing_symbol)
    excluded = CandidateDisposition(
        key=CandidateKey.from_candidate(source),
        role=DispositionRole.EXCLUDED,
        reason="This source site is a documentation-only alias and cannot produce an operator action.",
        exclusion=ExclusionGrounding(symbol=source.alias, enclosing_function=source.enclosing_symbol),
    )
    parsed = _write_rows(tmp_path / "excluded.toml", (excluded,))

    assert validate_dispositions((source,), parsed) == parsed

    missing_grounding = replace(excluded, exclusion=None)
    with pytest.raises(DispositionValidationError, match="requires symbol and enclosing_function grounding"):
        validate_dispositions((source,), (missing_grounding,))

    wrong_symbol = replace(
        excluded,
        exclusion=ExclusionGrounding(symbol="other_symbol", enclosing_function=source.enclosing_symbol),
    )
    with pytest.raises(DispositionValidationError, match="does not match candidate alias"):
        validate_dispositions((source,), (wrong_symbol,))

    wrong_function = replace(
        excluded,
        exclusion=ExclusionGrounding(symbol=source.alias, enclosing_function="other_function"),
    )
    with pytest.raises(DispositionValidationError, match="does not match candidate enclosing_symbol"):
        validate_dispositions((source,), (wrong_function,))

    non_excluded_with_grounding = replace(excluded, role=DispositionRole.PRODUCER)
    with pytest.raises(DispositionValidationError, match="only excluded dispositions may carry exclusion grounding"):
        validate_dispositions((source,), (non_excluded_with_grounding,))


def test_checked_in_exception_override_owners_cover_each_live_physical_observation() -> None:
    """The current tree proves the retired exception override shape is absent."""
    rows = load_dispositions(DEFAULT_DISPOSITIONS_PATH)
    observations = validate_exception_override_owners(rows)
    owner_rows = tuple(row for row in rows if row.exception_observations)
    observed_fingerprints = Counter((observation.key, observation.fingerprint) for observation in observations)
    ledger_fingerprints = Counter(
        (row.key, fingerprint) for row in owner_rows for fingerprint in row.exception_observations
    )

    assert {observation.key for observation in observations} == {row.key for row in owner_rows}
    assert observed_fingerprints == ledger_fingerprints
    assert observations == ()
    assert owner_rows == ()
    assert current_exception_override_observations() == observations


def test_current_owner_gate_rejects_a_retired_exception_owner() -> None:
    """A mutation cannot reintroduce metadata for the absent override shape."""
    rows = load_dispositions(DEFAULT_DISPOSITIONS_PATH)
    target = rows[0]
    changed = (replace(target, exception_observations=("selector|constructor_keyword|suggestion|<stale>|1",)),)

    with pytest.raises(DispositionValidationError, match="stale exception override owner"):
        validate_exception_override_owners(changed)


def test_current_exception_override_census_fails_closed_on_unreadable_invalid_and_undecodable_source(
    tmp_path: Path,
) -> None:
    """Filesystem source failures cannot silently shrink the live blast radius."""
    source_root = tmp_path / "src/cadrumo"
    source_root.mkdir(parents=True)

    unreadable = source_root / "unreadable.py"
    unreadable.mkdir()
    with pytest.raises(DispositionValidationError, match=r"cannot read src/cadrumo/unreadable\.py:"):
        current_exception_override_observations(root=tmp_path)
    unreadable.rmdir()

    undecodable = source_root / "undecodable.py"
    undecodable.write_bytes(b"\xff")
    with pytest.raises(
        DispositionValidationError, match=r"cannot decode src/cadrumo/undecodable\.py: UnicodeDecodeError"
    ):
        current_exception_override_observations(root=tmp_path)
    undecodable.unlink()

    invalid = source_root / "invalid.py"
    invalid.write_text("def invalid(:\n", encoding="utf-8")
    with pytest.raises(DispositionValidationError, match=r"cannot parse src/cadrumo/invalid\.py: SyntaxError"):
        current_exception_override_observations(root=tmp_path)


def test_missing_ledger_path_fails_the_checked_in_and_cli_entrypoints(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The default-ledger contract never turns an absent file into empty coverage."""
    missing_path = tmp_path / DEFAULT_DISPOSITIONS_PATH.name
    assert not missing_path.exists()

    with pytest.raises(DispositionValidationError, match="cannot read disposition ledger"):
        checked_in_current_dispositions(path=missing_path)

    assert main(["--current-tree", "--dispositions", str(missing_path)]) == 1
    assert "cannot read disposition ledger" in capsys.readouterr().out
