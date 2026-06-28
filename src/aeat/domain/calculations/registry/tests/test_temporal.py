"""Focused unit tests for the temporal-revision-selection helper.

`select_revision` funnels every snapshot resolution. It has three
failure modes (no-match, ambiguous-selection, mismatching revision_id)
and four filter modes (filing_year, period, on= date window, and
revision_id). Indirect coverage exists through the snapshot suite,
but the committed registry is designed without overlapping revisions
so the `ambiguous revision selection` branch is never exercised in
the registry-load tests. A regression in the dedup check would
otherwise land silently.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import bundled_path
from .._errors import (
    AmbiguousRevisionSelectionError,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
)
from .._loader import load_registry_tree
from .._schema import ModeloDefinition
from .._temporal import select_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _committed_modelo_100() -> ModeloDefinition:
    modelos, _catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    return next(modelo for modelo in modelos if modelo.id == "100")


def test_select_revision_returns_the_matching_year_revision() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2025, period="0A")

    assert revision.id == "2025"


def test_select_revision_raises_when_no_revision_matches_year() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2099, period="0A")


def test_select_revision_raises_when_period_not_declared_by_selector() -> None:
    """Renta is annual-only — period='0A' is the lone declared period."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="3T")


def test_select_revision_honours_explicit_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    revision = select_revision(modelo, filing_year=2024, period="0A", revision_id="2024")

    assert revision.id == "2024"


def test_select_revision_rejects_mismatching_revision_id_filter() -> None:
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2024, period="0A", revision_id="not-a-real-id")


def test_select_revision_filters_by_on_date_outside_validity_window() -> None:
    """An on= date well before every revision's valid_from must surface
    as no-revision, not silently pick the closest revision."""
    modelo = _committed_modelo_100()

    with pytest.raises(RegistrySnapshotError, match="no revision for"):
        select_revision(modelo, filing_year=2025, period="0A", on=date(1900, 1, 1))


def test_select_revision_raises_on_ambiguous_selection() -> None:
    """The dedup check fires when two revisions both match the
    requested year + period (+ optional on= window). Forge a twin
    revision so the candidates list grows past length 1."""
    modelo = _committed_modelo_100()
    original = modelo.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(RegistrySnapshotError, match="ambiguous revision selection"):
        select_revision(mutated, filing_year=2025, period="0A")


def test_no_revision_raises_typed_subclass_with_structured_natural_key() -> None:
    """The no-candidate branch raises the typed subclass carrying the
    natural key as structured fields, not only inside the message.

    A consumer dispatches by ``except NoRevisionForPeriodError`` and reads
    ``modelo_id`` / ``filing_year`` / ``period`` / ``revision_id`` from the
    typed fields. The subclass is still catchable as the parent type, so
    every existing ``except RegistrySnapshotError`` site keeps working."""
    modelo = _committed_modelo_100()

    with pytest.raises(NoRevisionForPeriodError) as excinfo:
        select_revision(modelo, filing_year=2099, period="0A", revision_id="r9")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    assert err.filing_year == 2099
    assert err.period == "0A"
    assert err.revision_id == "r9"


def test_ambiguous_selection_raises_typed_subclass_with_candidate_ids() -> None:
    """The dedup branch raises the typed subclass carrying the candidate
    revision ids as a structured, sorted tuple — independent of the
    human-readable message wording (the whole point of the refactor).

    Designed so a rewording of the ``str()`` message would not change the
    assertion: the candidate ids are read from ``candidate_ids``, never
    parsed out of the message."""
    modelo = _committed_modelo_100()
    original = modelo.revisions["2025"]
    twin = original.model_copy(update={"id": "2025-twin"})
    mutated = modelo.model_copy(update={"revisions": {**modelo.revisions, twin.id: twin}})

    with pytest.raises(AmbiguousRevisionSelectionError) as excinfo:
        select_revision(mutated, filing_year=2025, period="0A")

    err = excinfo.value
    assert isinstance(err, RegistrySnapshotError)
    assert err.modelo_id == "100"
    # Sorted tuple of every matching revision id, read from the typed field.
    assert err.candidate_ids == ("2025", "2025-twin")
