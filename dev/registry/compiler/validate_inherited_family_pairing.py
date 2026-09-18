"""Predecessor-edge validation for declaration families that are paired by a closure rule.

Every closure rule in :mod:`._validate_application_links` couples one
declaration family to the application surface that consumes it, and each rule
is evaluated against one already-materialised revision. That is the right
question to ask of a full-copy edition and the wrong one to ask of a delta
edition, because the two sides of a pair do not reach the successor the same
way: a family inherits under its own enrolment - keyed, scoped, period-scoped,
declinable through a retirement, a removal or a clearance - while the
application link inherits under its own. Nothing so far compares them.

This module asks the question the per-revision pass cannot: across one
predecessor edge, did a pair come apart? A capability surface that survives
over a family that went empty is a claim about what the edition can do with
nothing left behind it, and the per-revision rule stays quiet because it only
fires the other way round.

It also closes the neighbouring hole, on the same edge and for the same
reason: a family disposition is a legal claim that the modelo requires none of
a family for this edition. ``ModeloRevision`` refuses one that contradicts the
edition's own content, which leaves the case where the content was the
predecessor's and the successor's merge dropped it - the claim then reads as
law while the edition before it declares the opposite.

See Also:
    :func:`dev.registry.compiler._validate_application_links.validate_application_link_closure`
        The per-revision closure rules whose pairs this module carries across an edge.
"""

from __future__ import annotations

from cadrumo.domain.calculations.registry.keyed_families import family_spec
from cadrumo.domain.calculations.registry.revision_contracts import DeclaredPredecessor
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, ModeloRevision

from ._validate_application_links import _SIMPLE_APPLICATION_LINK_RULES

__all__ = ["inherited_family_pairing_failures"]


def inherited_family_pairing_failures(modelo: ModeloDefinition) -> tuple[str, ...]:
    """Return failures for pairs and dispositions broken across a predecessor edge.

    Only an edition with a resolved predecessor is examined: a root edition
    states every family itself, so nothing can have come apart on the way in.
    """
    failures: list[str] = []
    for revision in modelo.revisions.values():
        baseline_id = _family_baseline_id(revision)
        if baseline_id is None:
            continue
        baseline = modelo.revisions.get(baseline_id)
        if baseline is None:
            continue
        scope = f"modelo {modelo.id} revision {revision.id!r} inheriting from {baseline_id!r}"
        failures.extend(_broken_pair_failures(scope, revision, baseline))
        failures.extend(_contradicted_disposition_failures(scope, revision, baseline))
    return tuple(failures)


def _family_baseline_id(revision: ModeloRevision) -> str | None:
    """The edition this one's keyed families resolve against, mirroring the loader's choice.

    A declared predecessor is the semantic edge and takes precedence; a family
    storage baseline carries members without one. Either way the members the
    successor did not state arrive from here.
    """
    if isinstance(revision.predecessor, DeclaredPredecessor):
        return str(revision.predecessor.revision_id)
    if revision.family_storage_baseline is not None:
        return str(revision.family_storage_baseline)
    return None


def _member_count(revision: ModeloRevision, section: str) -> int:
    members = getattr(revision, section)
    spec = family_spec(section)
    if spec is not None and spec.singleton:
        return 1 if members else 0
    return len(members)


def _broken_pair_failures(scope: str, revision: ModeloRevision, baseline: ModeloRevision) -> tuple[str, ...]:
    """Refuse a surviving capability surface whose paired family emptied on this edge.

    The surface is what the product reads to decide the edition supports the
    workflow; the family is what the workflow consumes. A successor that keeps
    the first and loses the second declares a capability it cannot perform, and
    it does so without stating anything: the link arrived by inheritance and
    the family left through a mechanism of its own.

    Both sides are read after materialisation, so this compares what the two
    editions mean rather than what either happens to spell on disk.
    """
    surfaces = {link.surface for link in revision.application_links}
    failures: list[str] = []
    for section, surface, _message in _SIMPLE_APPLICATION_LINK_RULES:
        if surface not in surfaces:
            continue
        if _member_count(revision, section) or not _member_count(baseline, section):
            continue
        failures.append(
            f"{scope}: the predecessor declares {_member_count(baseline, section)} {section} member(s) and this "
            f"edition resolves to none, yet it still declares the {surface!r} application link that consumes "
            f"them; either carry the family across the edge or retire the {surface!r} surface with it, so the "
            "edition does not claim a capability nothing backs",
        )
    return tuple(failures)


def _contradicted_disposition_failures(
    scope: str,
    revision: ModeloRevision,
    baseline: ModeloRevision,
) -> tuple[str, ...]:
    """Refuse an inapplicability claim the predecessor's own declaration contradicts.

    A disposition says the law requires none of this family for this edition.
    Where the predecessor declares members of it, one of the two editions is
    wrong about the law, and which one is a grounded authoring decision rather
    than something the merge may pick silently. Retiring the members through
    the family's own withdrawal vocabulary states the same conclusion where a
    reader and the evolution record can both see it.
    """
    failures: list[str] = []
    for section in revision.family_dispositions:
        inherited = _member_count(baseline, section)
        if not inherited:
            continue
        failures.append(
            f"{scope}: declares family {section!r} not applicable, but the predecessor declares {inherited} "
            f"member(s) of it; a disposition is a claim about the law, so withdraw the predecessor's members "
            "explicitly rather than leaving two editions asserting the opposite",
        )
    return tuple(failures)
