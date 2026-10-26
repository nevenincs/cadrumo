"""Lineage totality over the bundled corpus, partitioned by modelo and excepted only by the ledger.

Every successor-edition casilla row must carry lineage or declare its kind of
none; the rows that do neither are admitted only by name, one ledger refusal
per row. The gate fails on an unresolved row the ledger does not name and on a
ledger entry whose row no longer needs it.

The corpus is compiled one modelo at a time, so a modelo that will not load
stops only itself. That is also the shape in which a hole could open: judged
against a corpus missing a modelo, the plain totality rule reads that modelo's
rows as neither uncovered nor needed and slides towards green. The gate
therefore judges only the modelos it could load, names the rest as unjudged,
withholds their ledger entries from both sides, and is never green while the
unjudged list is non-empty.

Every sample below is drawn from an entry that actually COVERS an unresolved row
of a modelo that actually LOADED. Both qualifications are load-bearing: an entry
of an unjudged modelo is withheld and dropping it changes nothing, and an entry
that is already stale is not covering anything to lose. Either would leave a
control that cannot fail, which is how this control was destroyed before.
"""

from __future__ import annotations

import collections
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    CasillaRowKey,
    unresolved_successor_rows,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..analysis.casilla_lineage_ledger import LedgerRefusal, load_ledger_refusals
from ..analysis.casilla_lineage_partition import (
    LineageTotalityState,
    load_partitioned_corpus,
    partitioned_lineage_totality,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PLANTED = "999"
_PLANTED_REASON = "planted: no revisions found in revisions/"


@pytest.fixture(scope="module")
def partition() -> tuple[dict[str, ModeloDefinition], dict[str, str]]:
    return load_partitioned_corpus()


@pytest.fixture(scope="module")
def ledger() -> Mapping[CasillaRowKey, LedgerRefusal]:
    return load_ledger_refusals()


@pytest.fixture(scope="module")
def covering(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> Mapping[str, frozenset[CasillaRowKey]]:
    """Per judged modelo, the ledger entries that currently cover one of its unresolved rows."""
    loaded, _ = partition
    found = {
        modelo_id: frozenset(set(unresolved_successor_rows(definition)) & set(ledger))
        for modelo_id, definition in loaded.items()
    }
    return {modelo_id: keys for modelo_id, keys in found.items() if keys}


def _victim(covering: Mapping[str, frozenset[CasillaRowKey]]) -> str:
    """The judged modelo whose loss the ledger would feel most, so every control below can fail."""
    assert covering, (
        "no ledger refusal covers an unresolved row of a modelo this run could load; "
        "every control in this module would be vacuous"
    )
    return max(sorted(covering), key=lambda modelo: len(covering[modelo]))


def test_every_unresolved_successor_row_is_refused_by_name_in_the_ledger(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> None:
    """The whole judgement, including the unjudged list, is printed on every run and asserted green."""
    loaded, unjudged = partition
    report = partitioned_lineage_totality(loaded, unjudged, ledger.keys())
    # Printed unconditionally: the unjudged list is the one fact a reader must not have to
    # deduce from a pass, and pytest shows this section whenever the assertion below fails.
    print(report.describe())
    assert report.state is LineageTotalityState.TOTAL, report.describe()
    assert report.is_green


def test_dropping_one_real_ledger_refusal_of_a_judged_modelo_exposes_its_row(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
    covering: Mapping[str, frozenset[CasillaRowKey]],
) -> None:
    """The drop-one control, drawn from a modelo that loaded and an entry that covers a row."""
    loaded, unjudged = partition
    victim = _victim(covering)
    assert victim in loaded, f"sample modelo {victim} did not load; the drop-one control would be vacuous"
    assert victim not in unjudged, f"sample modelo {victim} is unjudged; the drop-one control would be vacuous"
    dropped = min(covering[victim])

    baseline = partitioned_lineage_totality(loaded, unjudged, ledger.keys())
    report = partitioned_lineage_totality(loaded, unjudged, set(ledger) - {dropped})
    assert set(report.uncovered) - set(baseline.uncovered) == {dropped}
    assert report.stale == baseline.stale
    assert not report.is_green


def test_a_refusal_naming_a_row_that_carries_lineage_is_stale(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> None:
    loaded, unjudged = partition
    corpus = tuple(loaded.values())
    unresolved = {key for modelo in corpus for key in unresolved_successor_rows(modelo)}
    resolved = next(
        CasillaRowKey(modelo=modelo.id, revision=str(revision.id), casilla=str(casilla.id))
        for modelo in corpus
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if casilla.continuidad_origin is not None
        and CasillaRowKey(modelo=modelo.id, revision=str(revision.id), casilla=str(casilla.id)) not in unresolved
    )
    baseline = partitioned_lineage_totality(loaded, unjudged, ledger.keys())
    report = partitioned_lineage_totality(loaded, unjudged, {*ledger, resolved})
    assert set(report.stale) - set(baseline.stale) == {resolved}
    assert report.uncovered == baseline.uncovered


def test_a_modelo_that_cannot_be_loaded_is_reported_unjudged_and_its_rows_withheld_not_dropped(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
    covering: Mapping[str, frozenset[CasillaRowKey]],
) -> None:
    """The hole this partition closes, planted on the real corpus.

    Dropping a modelo from the corpus is exactly what a load failure does. The
    unpartitioned rule reads its rows as needing nothing and its ledger entries
    as stale; the partitioned one names it unjudged, withholds its entries from
    both sides, and refuses to go green.
    """
    loaded, unjudged = partition
    victim = _victim(covering)
    baseline = partitioned_lineage_totality(loaded, unjudged, ledger.keys())
    assert victim not in baseline.unjudged, "the control must start with the victim judged"

    planted_loaded = {modelo: definition for modelo, definition in loaded.items() if modelo != victim}
    planted_unjudged = {**unjudged, victim: _PLANTED_REASON}
    report = partitioned_lineage_totality(planted_loaded, planted_unjudged, ledger.keys())

    assert victim in report.unjudged
    assert victim not in report.judged
    assert not report.is_green, "a judgement with an unjudged modelo is never green"
    # Withheld, not dropped: every one of the victim's entries moves to the withheld side,
    # and neither the uncovered nor the stale side gains or invents anything.
    victims_entries = {key for key in ledger if key.modelo == victim}
    assert set(report.withheld) - set(baseline.withheld) == victims_entries
    assert set(report.uncovered) == {key for key in baseline.uncovered if key.modelo != victim}
    assert set(report.stale) == {key for key in baseline.stale if key.modelo != victim}
    assert victim in report.describe()


def test_a_judgement_total_over_what_it_loaded_is_still_not_green_while_one_modelo_is_unjudged(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    covering: Mapping[str, frozenset[CasillaRowKey]],
) -> None:
    """Partial is never green, shown where the judged side is exactly total.

    Judged over one modelo and an exception set naming exactly its unresolved
    rows, the report is total. The same judgement with one modelo unjudged is
    ``partial_with_unjudged``: nothing judged failed, and it is still not green,
    because an unjudged modelo is an absence of evidence.
    """
    loaded, _ = partition
    victim = _victim(covering)
    one = {victim: loaded[victim]}
    exact = set(unresolved_successor_rows(loaded[victim]))
    assert exact, f"modelo {victim} has no unresolved row; this control would be vacuous"

    total = partitioned_lineage_totality(one, {}, exact)
    assert total.state is LineageTotalityState.TOTAL, total.describe()
    assert total.is_green

    partial = partitioned_lineage_totality(one, {_PLANTED: _PLANTED_REASON}, exact)
    assert partial.uncovered == total.uncovered
    assert partial.stale == total.stale
    assert partial.unjudged == (_PLANTED,)
    assert partial.state is LineageTotalityState.PARTIAL_WITH_UNJUDGED
    assert not partial.is_green
    assert _PLANTED in partial.describe()


def test_an_unjudged_modelo_does_not_soften_a_real_failure(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    covering: Mapping[str, frozenset[CasillaRowKey]],
) -> None:
    """A judged failure outranks an unjudged modelo, so partial never masks not-total."""
    loaded, _ = partition
    victim = _victim(covering)
    one = {victim: loaded[victim]}
    exact = set(unresolved_successor_rows(loaded[victim]))
    dropped = min(exact)
    report = partitioned_lineage_totality(one, {_PLANTED: _PLANTED_REASON}, exact - {dropped})
    assert report.state is LineageTotalityState.NOT_TOTAL
    assert dropped in report.uncovered
    assert report.unjudged == (_PLANTED,)
    assert not report.is_green


def test_the_report_names_every_unjudged_modelo_whatever_its_state(
    partition: tuple[dict[str, ModeloDefinition], dict[str, str]],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> None:
    """The unjudged list is in the prose on every run, so no pass or failure hides it."""
    loaded, unjudged = partition
    report = partitioned_lineage_totality(loaded, unjudged, ledger.keys())
    described = report.describe()
    assert "unjudged modelos:" in described
    assert all(modelo in described for modelo in report.unjudged)
    assert collections.Counter(report.unjudged) == collections.Counter(sorted(unjudged))


_ENTRY = 'modelo = "123"\nrevision = "2024"\ncasilla = "07"\ncategory = "role_absent"\nreason = "{reason}"\n'
_CARRIED = 'carried_from_previous_run = true\ncarried_reason = "modelo 123 did not compile"\ncarried_runs = 3\n'


def test_the_ledger_reader_admits_a_well_formed_refusal(tmp_path: Path) -> None:
    path = tmp_path / "ledger.toml"
    path.write_text("[[refusal]]\n" + _ENTRY.format(reason="no role"), encoding="utf-8")
    entries = load_ledger_refusals(path)
    assert set(entries) == {CasillaRowKey(modelo="123", revision="2024", casilla="07")}
    only = next(iter(entries.values()))
    assert not only.carried_from_previous_run
    assert only.last_judged is None


def test_a_carried_refusal_is_distinguishable_from_a_freshly_judged_one(tmp_path: Path) -> None:
    """A carried entry says so, dates its last real judgement, and counts its carries."""
    path = tmp_path / "ledger.toml"
    fresh = "[[refusal]]\n" + _ENTRY.format(reason="no role")
    carried = (
        "[[refusal]]\n"
        + _ENTRY.format(reason="no role").replace('casilla = "07"', 'casilla = "08"')
        + _CARRIED
        + 'last_judged = "2026-09-01T08:00:00Z"\n'
    )
    path.write_text(fresh + "\n" + carried, encoding="utf-8")
    entries = load_ledger_refusals(path)
    judged = entries[CasillaRowKey(modelo="123", revision="2024", casilla="07")]
    borne = entries[CasillaRowKey(modelo="123", revision="2024", casilla="08")]
    assert (judged.carried_from_previous_run, judged.last_judged, judged.carried_runs) == (False, None, 0)
    assert borne.carried_from_previous_run
    assert borne.last_judged == "2026-09-01T08:00:00Z"
    assert borne.carried_runs == 3
    assert borne.carried_reason == "modelo 123 did not compile"


def test_the_ledger_reader_refuses_a_carried_refusal_that_dates_nothing(tmp_path: Path) -> None:
    """A carried entry with no last_judged asserts something about no corpus state in particular."""
    path = tmp_path / "ledger.toml"
    path.write_text("[[refusal]]\n" + _ENTRY.format(reason="no role") + _CARRIED, encoding="utf-8")
    with pytest.raises(ValueError, match="has no last_judged"):
        load_ledger_refusals(path)


def test_the_ledger_reader_refuses_a_refusal_without_a_reason(tmp_path: Path) -> None:
    path = tmp_path / "ledger.toml"
    path.write_text("[[refusal]]\n" + _ENTRY.format(reason=" "), encoding="utf-8")
    with pytest.raises(ValueError, match="has no reason"):
        load_ledger_refusals(path)


def test_the_ledger_reader_refuses_a_row_named_twice(tmp_path: Path) -> None:
    path = tmp_path / "ledger.toml"
    entry = "[[refusal]]\n" + _ENTRY.format(reason="no role")
    path.write_text(entry + "\n" + entry, encoding="utf-8")
    with pytest.raises(ValueError, match="a second time"):
        load_ledger_refusals(path)
