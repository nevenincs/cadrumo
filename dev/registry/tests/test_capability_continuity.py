"""Real-behaviour tests for the capability continuity screen.

The screen's whole value is separating a capability a revision DROPPED from one
it deliberately renounced by declaring less authority. Confusing them would make
a stub read like a regression.

Both conditions are proven on copies of real revisions carrying a constructed
loss, so the proofs do not depend on the shipped registry staying defective: a
corpus whose every loss had been repaired must leave the screen's detection
proven, not vacuous.
"""

from __future__ import annotations

import dataclasses

import pytest

from cadrumo.core.authority_grade import RegistryAuthorityGrade
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from dev.registry.compiler.authority import compiled_bundled_authority

from ..analysis.capability_continuity import (
    GRADE_LADDER,
    KINDS,
    declared_capabilities,
    modelo_findings,
    screen_authority,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: A filing-grade modelo whose consecutive filing revisions keep every
#: capability, and the later revision of that pair. The earlier one declares a
#: typed envelope with a product-identity requirement, so removing the layout
#: removes three capabilities at once.
_ENVELOPE_MODELO = "303"
_ENVELOPE_PREDECESSOR = "2025"
_ENVELOPE_REVISION = "2026-y-siguientes"

#: A second clean modelo, whose later revision loses only its deadline windows.
_DEADLINE_MODELO = "180"
_DEADLINE_PREDECESSOR = "2019-2022"
_DEADLINE_REVISION = "2023-y-siguientes"

#: What a revision stops declaring when its export layouts are removed: the
#: layout itself and the envelope that lives inside it, with the envelope's
#: product-identity requirement.
_LAYOUT_BORNE = frozenset({"export_layout", "typed_filing_envelope", "product_identity_requirement"})


def _authority_with_revision(
    authority: ValidatedRegistryAuthority, *, modelo_id: str, revision_id: str, update: dict[str, object]
) -> ValidatedRegistryAuthority:
    """Return a copy of ``authority`` whose one revision carries ``update``.

    The revision is copied through the typed model the loader produces, and the
    copy is a real authority object rather than something standing in for one,
    so the screen walks exactly the surface it walks in production. Its caches
    start empty so nothing validated against the shipped registry is credited
    to the constructed one.
    """
    definition = authority.modelo(modelo_id)
    revision = definition.revisions[revision_id].model_copy(update=update)
    planted = definition.model_copy(update={"revisions": {**definition.revisions, revision_id: revision}})
    modelos = tuple(planted if modelo.id == planted.id else modelo for modelo in authority.modelos)
    return dataclasses.replace(
        authority,
        modelos=modelos,
        _modelos_by_id={modelo.id: modelo for modelo in modelos},
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
    )


def _renounced_layout(authority: ValidatedRegistryAuthority) -> ValidatedRegistryAuthority:
    """Modelo 303's later filing revision, demoted to applicability and stripped of its layout.

    The shape of a deliberate stub: the claim shrinks and the capability goes
    with it.
    """
    return _authority_with_revision(
        authority,
        modelo_id=_ENVELOPE_MODELO,
        revision_id=_ENVELOPE_REVISION,
        update={"export_layouts": (), "authority_grade": RegistryAuthorityGrade.APPLICABILITY},
    )


def test_a_capability_lost_while_the_grade_holds_is_a_regression() -> None:
    """A typed envelope dropped between two filing-grade revisions is a regression.

    The shape that motivated this screen: the later revision keeps its layout
    and its grade and spells the envelope away, so nothing about the claim got
    smaller. Constructed on a copy of a clean modelo by removing the later
    revision's envelope. Both the envelope and the product-identity requirement
    it carried must be reported, and only those, each as a loss at the same
    grade.
    """
    authority = compiled_bundled_authority()
    assert modelo_findings(authority, modelo_id=_ENVELOPE_MODELO) == (), "the constructed loss must be the only one"
    revision = authority.modelo(_ENVELOPE_MODELO).revisions[_ENVELOPE_REVISION]
    layout = revision.export_layouts[0]
    assert layout.filing_envelope is not None, "the later revision must declare the envelope it loses"

    planted = _authority_with_revision(
        authority,
        modelo_id=_ENVELOPE_MODELO,
        revision_id=_ENVELOPE_REVISION,
        update={"export_layouts": (layout.model_copy(update={"filing_envelope": None}), *revision.export_layouts[1:])},
    )
    findings = modelo_findings(planted, modelo_id=_ENVELOPE_MODELO)

    assert sorted((f.revision, f.predecessor, f.kind, f.capability) for f in findings) == [
        (_ENVELOPE_REVISION, _ENVELOPE_PREDECESSOR, "capability_lost_at_same_grade", "product_identity_requirement"),
        (_ENVELOPE_REVISION, _ENVELOPE_PREDECESSOR, "capability_lost_at_same_grade", "typed_filing_envelope"),
    ]
    assert all("filing to filing" in f.detail for f in findings)


def test_a_capability_lost_with_the_grade_is_not_called_a_regression() -> None:
    """A layout dropped into an applicability-grade stub is reported as renounced.

    Constructed on a copy of a clean modelo: its later filing revision is demoted
    to applicability and loses its layout, which is what a deliberate placeholder
    between two filing revisions looks like. Every capability that went must be
    reported, each under the renounced kind and none as a regression, because
    reporting it beside a real regression would put an oversight and an
    intention under one name.
    """
    authority = compiled_bundled_authority()
    predecessor = authority.modelo(_ENVELOPE_MODELO).revisions[_ENVELOPE_PREDECESSOR]
    assert declared_capabilities(predecessor) >= _LAYOUT_BORNE, "the predecessor must declare what the stub loses"
    assert modelo_findings(authority, modelo_id=_ENVELOPE_MODELO) == (), "the constructed loss must be the only one"

    findings = modelo_findings(_renounced_layout(authority), modelo_id=_ENVELOPE_MODELO)

    assert sorted((f.revision, f.predecessor, f.kind, f.capability) for f in findings) == sorted(
        (_ENVELOPE_REVISION, _ENVELOPE_PREDECESSOR, "capability_lost_with_grade", capability)
        for capability in _LAYOUT_BORNE
    )
    assert all("filing to applicability" in f.detail for f in findings)


def test_both_conditions_occur_and_the_screen_separates_them() -> None:
    """A screen reporting one kind for everything would order nothing.

    One constructed loss of each kind, in two modelos: a renounced layout, and a
    deadline window dropped while the grade holds. The screen must report each
    under its own kind and nothing else across both modelos.
    """
    authority = compiled_bundled_authority()
    for modelo_id in (_ENVELOPE_MODELO, _DEADLINE_MODELO):
        assert modelo_findings(authority, modelo_id=modelo_id) == (), f"modelo {modelo_id} must start clean"

    planted = _authority_with_revision(
        _renounced_layout(authority),
        modelo_id=_DEADLINE_MODELO,
        revision_id=_DEADLINE_REVISION,
        update={"deadline_windows": ()},
    )
    findings = screen_authority(planted, (_ENVELOPE_MODELO, _DEADLINE_MODELO))

    assert {f.kind for f in findings} == set(KINDS)
    assert sorted((f.modelo, f.revision, f.predecessor, f.kind, f.capability) for f in findings) == sorted(
        [
            *(
                (_ENVELOPE_MODELO, _ENVELOPE_REVISION, _ENVELOPE_PREDECESSOR, "capability_lost_with_grade", capability)
                for capability in _LAYOUT_BORNE
            ),
            (
                _DEADLINE_MODELO,
                _DEADLINE_REVISION,
                _DEADLINE_PREDECESSOR,
                "capability_lost_at_same_grade",
                "deadline_window",
            ),
        ]
    )
    deadline = next(f for f in findings if f.modelo == _DEADLINE_MODELO)
    assert "filing to filing" in deadline.detail


def test_capabilities_are_directional_and_exclude_counts() -> None:
    """A revision with fewer casillas is not thereby weaker.

    Counting anything would report every revision that trimmed a field, burying
    the cases where something stopped being expressible at all.
    """
    authority = compiled_bundled_authority()
    revision = authority.modelo("322").revisions["2024-2025"]
    declared = declared_capabilities(revision)
    assert declared, "the fixture revision declares nothing, so this proves nothing"
    assert all(isinstance(item, str) for item in declared)
    assert "typed_filing_envelope" in declared


def test_the_grade_ladder_matches_the_shipped_enum() -> None:
    """The order comparison rests on the enum's own ladder, not a second spelling."""
    assert tuple(member.value for member in RegistryAuthorityGrade) == GRADE_LADDER
