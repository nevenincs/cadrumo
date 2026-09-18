"""Runtime schema projection holds at every bundled modelo x revision coordinate.

The sweep requests each authored revision at the rung it declares, so it reads
the development compiler's validated authority rather than the published
generation. It stays inside the registry's own supported-year envelope: the
floor is a hard gate that refuses a request below it however completely the
corpus authors that year, so a coordinate the product will not answer is not a
coordinate this sweep can project.
"""

from __future__ import annotations

import pytest

from cadrumo.application.filing.runtime import collection_from_snapshot
from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.calculations.registry.validate_revision_identity import revision_reference_identity_failures

from ..compiler.authority import admitted_revision_id, compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _revision_validation_years(revision: ModeloRevision) -> tuple[int, ...]:
    selector = revision.period_selector
    if selector.years:
        return tuple(sorted(selector.years))
    assert selector.year_from is not None, f"revision {revision.id!r} has no validation year"
    years = {selector.year_from}
    if selector.year_to is not None:
        years.add(selector.year_to)
    return tuple(sorted(years))


def test_runtime_projection_rejects_ambiguous_casilla_refs_for_every_bundled_schema_coordinate() -> None:
    """Reference identity and runtime projection must hold at EVERY bundled coordinate.

    The subject here -- ambiguous revision references, casilla projection
    fidelity, dangling formula inputs -- is a structural property of a compiled
    revision. It applies at every rung of authority, not only at filing grade,
    so the sweep must stay universal across all bundled modelo x revision
    coordinates.

    Each snapshot is therefore requested at the rung the revision itself
    DECLARES, not at the snapshot boundary's strict default. Requesting the
    default would make this sweep silently skip every revision that declares
    ``calculation`` or ``applicability`` -- exactly the revisions whose
    structure nothing else here would then check. ``expected == projected`` at
    the end is what proves no coordinate was dropped.

    The companion assertion below keeps the relaxation honest: a revision below
    filing grade must still REFUSE a filing-grade request, so admitting it here
    at its declared rung cannot be mistaken for a filing capability claim.
    """
    authority = compiled_bundled_authority()
    support = authority.supported_filing_years()
    expected: list[str] = []
    projected: list[str] = []
    offences: list[str] = []

    for modelo in authority.modelos:
        for revision in modelo.revisions.values():
            revision_contexts: list[str] = []
            declared_grade = revision.authority_grade
            # An absent declaration is no claim at all and cannot satisfy even
            # the applicability floor, so a bundled revision must declare one.
            assert declared_grade is not None, f"bundled revision {modelo.id}/{revision.id} declares no authority grade"
            for filing_year in _revision_validation_years(revision):
                if not support.admits_filing_year(filing_year):
                    # Outside the product's hard gates, so every request below
                    # is refused by the envelope rather than answered; the
                    # revision is still authored and remains a storage baseline.
                    continue
                for period in revision.period_selector.periods:
                    context = f"{modelo.id}/{revision.id}/{filing_year}/{period}"
                    expected.append(context)
                    revision_contexts.append(context)
                    snapshot = authority.snapshot(
                        modelo.id,
                        filing_year=filing_year,
                        period=period,
                        revision_id=revision.id,
                        grade=declared_grade,
                    )
                    assert snapshot.revision.authority_grade == declared_grade
                    if declared_grade is not RegistryAuthorityGrade.FILING:
                        # Admitting the revision at its own rung above must not
                        # have made it admissible at the filing rung.
                        with pytest.raises(RegistryValidationError):
                            admitted_revision_id(
                                authority,
                                modelo.id,
                                filing_year=filing_year,
                                period=period,
                                revision_id=revision.id,
                                grade=RegistryAuthorityGrade.FILING,
                            )
                    identity_failures = revision_reference_identity_failures(
                        f"runtime projection {context}",
                        snapshot.revision,
                    )
                    assert identity_failures == (), (
                        f"bundled runtime schema coordinate {context} has ambiguous revision refs: "
                        f"{identity_failures!r}"
                    )
                    collection = collection_from_snapshot(snapshot)
                    assert collection.schema_version == f"registry:{modelo.id}:{revision.id}"
                    source_ids = tuple(sorted(casilla.id for casilla in snapshot.revision.casillas))
                    projected_ids = tuple(schema.casilla_id for schema in collection.all())
                    if projected_ids != source_ids:
                        offences.append(
                            f"{context}: projected runtime casillas differ from revision ids "
                            f"source={source_ids!r} projected={projected_ids!r}",
                        )
                    projected_id_set = frozenset(projected_ids)
                    dangling_formula_input_casilla_ids = {
                        schema.casilla_id: tuple(
                            input_id
                            for input_id in schema.formula_input_casilla_ids
                            if input_id not in projected_id_set
                        )
                        for schema in collection.all()
                        if schema.formula_input_casilla_ids
                    }
                    dangling_formula_input_casilla_ids = {
                        casilla_id: missing
                        for casilla_id, missing in dangling_formula_input_casilla_ids.items()
                        if missing
                    }
                    if dangling_formula_input_casilla_ids:
                        offences.append(
                            f"{context}: dangling formula input casilla ids {dangling_formula_input_casilla_ids!r}",
                        )
                    projected.append(context)
            assert revision_contexts or not any(
                support.admits_filing_year(year) for year in _revision_validation_years(revision)
            ), f"bundled revision produced no runtime projection contexts: {modelo.id}/{revision.id}"

    assert expected, "the envelope admitted no bundled coordinate at all, so this sweep proves nothing"
    assert projected == expected, f"bundled runtime projection coverage lost contexts: {expected!r} -> {projected!r}"
    assert not offences, "ambiguous runtime casilla schema projection:\n  " + "\n  ".join(offences)
