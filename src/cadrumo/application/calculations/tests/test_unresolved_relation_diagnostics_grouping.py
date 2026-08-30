"""One absent source filing produces one advisory, not one per relation reading it.

Pure-function coverage over ``_unresolved_relation_diagnostics``: no secure
storage, no session, no registry snapshot — just the grouping logic against
hand-built :class:`RegistryFoldRequirement` rows, so the property is pinned
independently of any modelo-specific fixture. The Modelo 190 case the row
measured (ten annual-summary relations, one absent Modelo 111 source) is
reproduced at the shape level: several relations sharing one
``(source_modelo, filing_year, periods)`` key collapse to one diagnostic.
"""

from __future__ import annotations

import pytest

from ....core.casilla_id import validated_casilla_id
from ....domain.calculations.registry.relations import RegistryFoldRequirement
from .._relation_prefill import _unresolved_relation_diagnostics

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SOURCE_MODELO = "111"
_FILING_YEAR = 2025
_PERIODS = ("1T", "2T", "3T", "4T")
_LEGAL_REFS = ("ley-35-2006:art-99",)
_SOURCE_REFS = ("aeat-dr-190-2025",)


def _casilla(number: str):
    return validated_casilla_id(f"iva.retenciones.{number}", surface="test fixture")


def _requirement(*, relation_id: str, casilla: str, binding: str) -> RegistryFoldRequirement:
    return RegistryFoldRequirement(
        source_modelo=_SOURCE_MODELO,
        filing_year=_FILING_YEAR,
        periods=_PERIODS,
        source_casilla_ids=(_casilla(casilla),),
        relation_ids=(relation_id,),
        target_bindings=(binding,),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )


def test_ten_relations_over_one_absent_source_collapse_to_one_diagnostic() -> None:
    """The Modelo 190 shape: ten relations, one root cause, one advisory."""
    requirements = {
        f"modelo-190-rel-{index:02d}": _requirement(
            relation_id=f"modelo-190-rel-{index:02d}",
            casilla=f"fact-{index:02d}",
            binding=f"binding-{index:02d}",
        )
        for index in range(10)
    }

    diagnostics = _unresolved_relation_diagnostics(
        unresolved_relation_ids=frozenset(requirements),
        requirements_by_relation=requirements,
        resolver_id="relation_prefill",
    )

    assert len(diagnostics) == 1, "ten relations sharing one source must fold to one diagnostic"
    diagnostic = diagnostics[0]
    # The structured field is the machine-readable, un-elided membership: it
    # must carry every relation regardless of what the length-capped prose
    # `message` keeps, because a ten-member group can exceed the message cap.
    assert len(diagnostic.relation_ids) == 10
    assert diagnostic.relation_id == min(diagnostic.relation_ids)
    assert set(diagnostic.relation_ids) == set(requirements)
    assert "modelo 111 2025" in diagnostic.message
    assert "10 relation(s)" in diagnostic.message
    # The affected facts (what each relation reads) are named in prose, sorted
    # so the earliest ones survive any elision the length cap applies.
    for index in range(3):
        assert f"fact-{index:02d}" in diagnostic.message


def test_two_different_source_requirements_stay_two_diagnostics() -> None:
    """Grouping is by source coordinate, never a blanket collapse of everything unresolved."""
    same_source = {
        "rel-a": _requirement(relation_id="rel-a", casilla="fact-a", binding="binding-a"),
        "rel-b": _requirement(relation_id="rel-b", casilla="fact-b", binding="binding-b"),
    }
    different_year = RegistryFoldRequirement(
        source_modelo=_SOURCE_MODELO,
        filing_year=_FILING_YEAR + 1,
        periods=_PERIODS,
        source_casilla_ids=(_casilla("fact-c"),),
        relation_ids=("rel-c",),
        target_bindings=("binding-c",),
        legal_refs=_LEGAL_REFS,
        source_refs=_SOURCE_REFS,
    )
    requirements = {**same_source, "rel-c": different_year}

    diagnostics = _unresolved_relation_diagnostics(
        unresolved_relation_ids=frozenset(requirements),
        requirements_by_relation=requirements,
        resolver_id="relation_prefill",
    )

    assert len(diagnostics) == 2
    by_relation_count = sorted(len(d.relation_ids) for d in diagnostics)
    assert by_relation_count == [1, 2]


def test_a_relation_with_no_requirement_stays_its_own_diagnostic() -> None:
    """An orphan (no scoped requirement at all) has no source coordinate to group by."""
    diagnostics = _unresolved_relation_diagnostics(
        unresolved_relation_ids=frozenset({"orphan-rel"}),
        requirements_by_relation={},
        resolver_id="relation_prefill",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].relation_id == "orphan-rel"
    assert diagnostics[0].relation_ids == ()


def test_a_single_unresolved_relation_still_carries_its_id_in_both_fields() -> None:
    """The singular field stays populated even when grouping produces exactly one member."""
    requirement = _requirement(relation_id="solo-rel", casilla="fact-solo", binding="binding-solo")

    diagnostics = _unresolved_relation_diagnostics(
        unresolved_relation_ids=frozenset({"solo-rel"}),
        requirements_by_relation={"solo-rel": requirement},
        resolver_id="relation_prefill",
    )

    assert len(diagnostics) == 1
    assert diagnostics[0].relation_id == "solo-rel"
    assert diagnostics[0].relation_ids == ("solo-rel",)
