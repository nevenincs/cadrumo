"""Two carry advisories on one calculate must be distinguishable by context alone.

This CLI's operator is an autonomous agent, and the contract directs it to route on
structured notice fields rather than parse prose. Before this gate the projection
built a context of only ``reason``, ``source_kind`` and ``resolver_id`` — three
values that are IDENTICAL across every carry advisory on a revision. Two advisories
about two different casillas were therefore indistinguishable except by their
free-text message, which made the typed channel typed in shape only.

The chain under test is both production functions in sequence: the resolver's own
diagnostic builder, then the shipped notice projection. Nothing is reconstructed
here — a copied context dict would assert the test author's idea of the projection
rather than the projection.

Real registry authority, real diagnostics, real projection. No mock, stub, fake,
skip or xfail.
"""

from __future__ import annotations

import pytest

from ....application.calculations.relation_prefill import _absent_bound_carry_diagnostics
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.relations import relation_source_requirements
from .._modelo_rendering import source_diagnostic_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CODE = "modelo.work.calculate.source_advisory"


def _m200_bound_carry_diagnostics():
    """Build the real absent-bound-carry diagnostics for the Modelo 200 self-carries.

    Requirements come from the loaded authority rather than being hand-built, so a
    registry change that alters a carry's source coordinates flows into this gate
    instead of being masked by a fixture.
    """
    snapshot = bundled_authority().snapshot("200", filing_year=2025, period="0A")
    requirements_by_relation = {
        relation_id: requirement
        for requirement in relation_source_requirements(
            snapshot.revision,
            filing_year=snapshot.filing_year,
            period=snapshot.period,
        )
        for relation_id in requirement.relation_ids
    }
    target_binding = {relation.id: relation.target_binding for relation in snapshot.revision.relations}
    self_carries = frozenset(
        relation.id
        for relation in snapshot.revision.relations
        if relation.source_modelo == "200" and relation.id in requirements_by_relation
    )
    assert len(self_carries) >= 2, (
        "this gate needs at least two same-modelo carries on the M200 revision to compare; "
        f"found {sorted(self_carries)}"
    )
    return _absent_bound_carry_diagnostics(
        unresolved_relation_ids=self_carries,
        requirements_by_relation=requirements_by_relation,
        relation_target_binding=target_binding,
        resolver_id="relation_prefill",
    )


def test_carry_advisories_are_distinguishable_by_notice_context_alone() -> None:
    """Every carry advisory's notice context differs from every other's.

    Asserted on the context mapping only, with the message discarded, because the
    message is exactly the channel an automated operator is told not to parse. If
    the contexts collide, the notices are unroutable however different their prose.
    """
    diagnostics = _m200_bound_carry_diagnostics()
    notices = [source_diagnostic_notice(diagnostic, code=_CODE) for diagnostic in diagnostics]

    contexts = [tuple(sorted((notice.context or {}).items())) for notice in notices]
    assert len(set(contexts)) == len(contexts), (
        "two carry advisories share an identical notice context and cannot be told apart "
        f"without parsing prose; contexts were {contexts}"
    )


def test_carry_advisory_context_carries_the_routable_subject() -> None:
    """The context names the binding, the relation and the source, not just the reason.

    Gated on the subject being PRESENT and matching the diagnostic it came from,
    rather than on a fixed key list, so adding a further structured field cannot
    break this while removing the routable subject does.
    """
    diagnostics = _m200_bound_carry_diagnostics()
    for diagnostic in diagnostics:
        context = source_diagnostic_notice(diagnostic, code=_CODE).context or {}
        assert context["relation_id"] == diagnostic.relation_id
        assert context["binding_id"] == diagnostic.binding_id
        assert context["reason"] == str(diagnostic.reason)
        assert context["source_kind"] == diagnostic.source_kind


def test_the_remedy_reaches_structured_notice_context() -> None:
    """A diagnostic's non-command remedy remains machine-readable.

    The wizard call site previously built its own context and dropped the remedy
    entirely, so an operator on that path never saw what to do. Both call sites now
    share this projection, and this pins the field it was losing.
    The remedy remains guidance, not a fully materialized command target.
    """
    diagnostics = _m200_bound_carry_diagnostics()
    remedied = [d for d in diagnostics if d.remedy]
    assert remedied, "the absent-bound-carry diagnostics must carry a remedy for this gate to bite"
    for diagnostic in remedied:
        notice = source_diagnostic_notice(diagnostic, code=_CODE)
        context = notice.context
        assert context is not None
        assert context["remedy"] == diagnostic.remedy
        assert notice.action is None


def test_absent_subjects_are_omitted_rather_than_written_blank() -> None:
    """A key is absent when the diagnostic has no such subject, never present-and-empty.

    Absence has to mean "no such subject" rather than "the subject is blank", or a
    consumer routing on the key cannot distinguish the two.
    """
    diagnostics = _m200_bound_carry_diagnostics()
    for diagnostic in diagnostics:
        context = source_diagnostic_notice(diagnostic, code=_CODE).context or {}
        assert all(value for value in context.values()), f"a context value is empty: {context}"
        if diagnostic.casilla_id is None:
            assert "casilla_id" not in context
