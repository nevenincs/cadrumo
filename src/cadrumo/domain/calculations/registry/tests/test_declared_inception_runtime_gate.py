"""The published generation carries each modelo's inception into runtime selection.

Runtime selects through the point-loaded modelo directory, so the declaration
has to survive publication for the gate to hold there. Years are derived from
the published support envelope and each directory's own earliest edition.
"""

from __future__ import annotations

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from ..authority import bundled_indexed_authority
from ..errors import FilingYearOutsideSupportEnvelopeError, NoRevisionForPeriodError
from ..modelo_inception import DeclaredInception, ModeloInceptionField, UnauthoredBefore
from ..schema import SupportedFilingYearsCatalogue
from ..temporal import ModeloRevisionDirectory, select_revision_metadata

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


@pytest.mark.parametrize(
    "declaration",
    (
        DeclaredInception(filing_year=2023, legal_refs=("orden-hfp-886-2023:art-1",)),
        UnauthoredBefore(
            earliest_authored=2022,
            reason="Synthetic earlier-edition authoring debt",
            legal_refs=("orden-eha-3377-2011:art-1",),
        ),
    ),
)
def test_inception_references_survive_json_union_roundtrip(
    declaration: DeclaredInception | UnauthoredBefore,
) -> None:
    """Saved snapshots read the tagged declaration under strict JSON validation."""
    adapter = TypeAdapter(ModeloInceptionField)
    assert adapter.validate_json(declaration.model_dump_json()) == declaration
    if isinstance(declaration, UnauthoredBefore):
        # Complete saved rendering stores the member fields without the authored wrapper.
        flat = json.loads(declaration.model_dump_json())["unauthored"]
        assert adapter.validate_json(json.dumps(flat)) == declaration


@pytest.mark.parametrize("invalid_refs", (None, "orden-eha-3377-2011:art-1", [123]))
def test_inception_json_union_refuses_invalid_reference_shapes(invalid_refs: object) -> None:
    """Array normalization keeps strict reference admission intact."""
    payload = {
        "unauthored": {
            "earliest_authored": 2022,
            "reason": "Synthetic earlier-edition authoring debt",
            "legal_refs": invalid_refs,
        }
    }
    with pytest.raises(ValidationError):
        TypeAdapter(ModeloInceptionField).validate_json(json.dumps(payload))


def _published_directories() -> tuple[tuple[ModeloRevisionDirectory, ...], SupportedFilingYearsCatalogue]:
    with bundled_indexed_authority().operation() as operation:
        directories = tuple(operation.modelo_directory(modelo_id) for modelo_id in operation.modelo_ids())
        return directories, operation.supported_filing_years()


def _earliest_authored_year(directory: ModeloRevisionDirectory) -> int:
    firsts = [
        min(revision.period_selector.years) if revision.period_selector.years else revision.period_selector.year_from
        for revision in directory.revisions
    ]
    return min(year for year in firsts if year is not None)


def _earliest_periods(directory: ModeloRevisionDirectory) -> tuple[str, ...]:
    year = _earliest_authored_year(directory)
    return tuple(
        sorted(
            {
                str(period)
                for revision in directory.revisions
                if revision.period_selector.includes_year(year)
                for period in revision.period_selector.periods_for_year(year)
            }
        )
    )


def _with_inception(
    directory: ModeloRevisionDirectory, inception: DeclaredInception | UnauthoredBefore
) -> ModeloRevisionDirectory:
    return directory.model_copy(update={"modelo": directory.modelo.model_copy(update={"inception": inception})})


def test_published_selection_refuses_a_year_before_a_declared_inception() -> None:
    """Live declarations and a synthetic one on each late-starting modelo refuse through runtime metadata."""
    directories, support = _published_directories()
    late_starting = tuple(directory for directory in directories if _earliest_authored_year(directory) > support.floor)
    assert late_starting, "no published modelo starts after the support floor, so the gate has nothing to refuse"
    live = tuple(
        directory
        for directory in directories
        if isinstance(directory.modelo.inception, DeclaredInception)
        and directory.modelo.inception.filing_year > support.floor
    )
    synthetic = tuple(
        _with_inception(
            directory,
            DeclaredInception(
                filing_year=_earliest_authored_year(directory),
                legal_refs=directory.modelo.legal_refs[:1],
            ),
        )
        for directory in late_starting
    )

    for directory in live + synthetic:
        inception = directory.modelo.inception
        assert isinstance(inception, DeclaredInception)
        for period in _earliest_periods(directory):
            answered = select_revision_metadata(directory, filing_year=inception.filing_year, period=period)
            assert answered.period_selector.includes_year(inception.filing_year)
            for filing_year in range(support.floor, inception.filing_year):
                with pytest.raises(NoRevisionForPeriodError) as excinfo:
                    select_revision_metadata(directory, filing_year=filing_year, period=period)
                assert not isinstance(excinfo.value, FilingYearOutsideSupportEnvelopeError)
                assert excinfo.value.filing_year == filing_year


def test_published_selection_projects_below_an_unauthored_debt_declaration() -> None:
    """The unauthored arm gates nothing at runtime: the earliest edition answers the years below it."""
    directories, support = _published_directories()
    debts = tuple(
        directory
        for directory in directories
        if isinstance(directory.modelo.inception, UnauthoredBefore)
        and directory.modelo.inception.earliest_authored > support.floor
    )
    undeclared = tuple(
        directory.model_copy(update={"modelo": directory.modelo.model_copy(update={"inception": None})})
        for directory in directories
        if _earliest_authored_year(directory) > support.floor
    )
    assert debts or undeclared, "no published modelo starts after the support floor, so nothing is projected"

    for directory in debts + undeclared:
        earliest = _earliest_authored_year(directory)
        for period in _earliest_periods(directory):
            authored = select_revision_metadata(directory, filing_year=earliest, period=period)
            for filing_year in range(support.floor, earliest):
                assert select_revision_metadata(directory, filing_year=filing_year, period=period).id == authored.id
