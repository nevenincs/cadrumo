"""Lineage totality over the bundled corpus, excepted only by the ledger's per-row refusals.

Every successor-edition casilla row must carry lineage or declare its kind of
none; the rows that do neither are admitted only by name, one ledger refusal
per row. The gate fails on an unresolved row the ledger does not name and on a
ledger entry whose row no longer needs it. The teeth are shown on the real
corpus and ledger: dropping one real entry exposes its row, and naming a row
that already carries lineage is reported stale.
"""

from __future__ import annotations

import collections
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_authority
from cadrumo.domain.calculations.registry.casilla_lineage_totality import (
    CasillaRowKey,
    lineage_totality,
    unresolved_successor_rows,
)
from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ..analysis.casilla_lineage_ledger import LedgerRefusal, load_ledger_refusals
from ..analysis.corpus import bundled_modelo_ids

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SHOWN = 20


@pytest.fixture(scope="module")
def corpus() -> tuple[ModeloDefinition, ...]:
    authority = bundled_authority()
    return tuple(authority.modelo(modelo_id) for modelo_id in bundled_modelo_ids())


@pytest.fixture(scope="module")
def ledger() -> Mapping[CasillaRowKey, LedgerRefusal]:
    return load_ledger_refusals()


def _describe(label: str, keys: tuple[CasillaRowKey, ...]) -> str:
    by_modelo = collections.Counter(key.modelo for key in keys)
    shown = "\n  ".join(f"{key.modelo} {key.revision} {key.casilla}" for key in keys[:_SHOWN])
    return f"{len(keys)} {label} by modelo {dict(sorted(by_modelo.items()))}; first {_SHOWN}:\n  {shown}"


def test_every_unresolved_successor_row_is_refused_by_name_in_the_ledger(
    corpus: tuple[ModeloDefinition, ...],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> None:
    report = lineage_totality(corpus, ledger.keys())
    problems = []
    if report.uncovered:
        problems.append(_describe("unresolved rows the ledger does not name", report.uncovered))
    if report.stale:
        problems.append(_describe("ledger refusals whose row no longer needs one", report.stale))
    assert report.is_total, "\n".join(problems)


def test_dropping_one_real_ledger_refusal_exposes_its_row(
    corpus: tuple[ModeloDefinition, ...],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> None:
    baseline = lineage_totality(corpus, ledger.keys())
    dropped = min(ledger)
    report = lineage_totality(corpus, set(ledger) - {dropped})
    assert set(report.uncovered) - set(baseline.uncovered) == {dropped}
    assert report.stale == baseline.stale


def test_a_refusal_naming_a_row_that_carries_lineage_is_stale(
    corpus: tuple[ModeloDefinition, ...],
    ledger: Mapping[CasillaRowKey, LedgerRefusal],
) -> None:
    unresolved = {key for modelo in corpus for key in unresolved_successor_rows(modelo)}
    resolved = next(
        CasillaRowKey(modelo=modelo.id, revision=str(revision.id), casilla=str(casilla.id))
        for modelo in corpus
        for revision in modelo.revisions.values()
        for casilla in revision.casillas
        if casilla.continuidad_origin is not None
        and CasillaRowKey(modelo=modelo.id, revision=str(revision.id), casilla=str(casilla.id)) not in unresolved
    )
    baseline = lineage_totality(corpus, ledger.keys())
    report = lineage_totality(corpus, {*ledger, resolved})
    assert set(report.stale) - set(baseline.stale) == {resolved}
    assert report.uncovered == baseline.uncovered


_ENTRY = 'modelo = "123"\nrevision = "2024"\ncasilla = "07"\ncategory = "role_absent"\nreason = "{reason}"\n'


def test_the_ledger_reader_admits_a_well_formed_refusal(tmp_path: Path) -> None:
    path = tmp_path / "ledger.toml"
    path.write_text("[[refusal]]\n" + _ENTRY.format(reason="no role"), encoding="utf-8")
    assert set(load_ledger_refusals(path)) == {CasillaRowKey(modelo="123", revision="2024", casilla="07")}


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
