"""The preflight revision resolver refuses on an ambiguous filing year.

A filing year AEAT re-laid out mid-course is covered by more than one registry
revision, so the year-only selector refuses rather than picking one. This surface
already handled that refusal before the split campaign began, and this module
EXERCISES it rather than asserting it from a reading of the code.

That distinction is the point. A surface that looks handled is repeatedly what
turned out not to be: a notice that read as wired had no caller, a box-number
marker that read as matching covered under one percent of a modelo, and a record
declared required was never written by the writer. Read-then-conclude is how all
three survived. So this asserts the refusal by raising the domain error through the
real resolver seam and observing what the surface does with it.
"""

from __future__ import annotations

import pytest

from .....core import Period
from cadrumo.domain.calculations.registry.errors import AmbiguousRevisionSelectionError
from .....tests.attribute_scope import scoped_attribute
from .. import _profile_inspect
from .._profile_inspect import _resolve_preflight_revision_id

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_an_ambiguous_filing_year_refuses_and_names_both_candidate_revisions() -> None:
    """The refusal must name the candidates, not emit a bare error.

    The candidate ids ride on the typed ``candidate_ids`` field, so the surface lists
    them without parsing a human-readable message. Asserting they reach the refusal's
    context is what proves the typed channel is actually consumed -- a surface could
    catch the error and drop them, which reads identically at the catch site.
    """
    from .....application import modelo as _modelo_module

    def _ambiguous(**_kwargs: object) -> str:
        raise AmbiguousRevisionSelectionError(
            modelo_id="303",
            candidate_ids=("2024-desde-09", "2024-hasta-08"),
            filing_year=2024,
            reason="mid-year AEAT design boundary",
        )

    with (
        scoped_attribute(_modelo_module, "resolve_registry_revision_for_work_target", _ambiguous),
        pytest.raises(_profile_inspect._CliRefusedBoundaryError) as raised,
    ):
        _resolve_preflight_revision_id(modelo="303", period=Period.from_year_and_code(2024, "3T"), revision_id=None)

    refusal = raised.value
    assert refusal.translated_message == "cli.config.profile.preflight_revision_ambiguous", (
        "the refusal must use the ambiguity key rather than the unresolved-revision one; the two "
        "conditions have different remedies and an operator told the wrong one acts on the wrong thing"
    )
    context = refusal.context or {}
    candidates = str(context.get("candidates", ""))
    for candidate in ("2024-hasta-08", "2024-desde-09"):
        assert candidate in candidates, (
            f"the refusal does not name candidate revision {candidate!r}, so an operator cannot tell "
            f"which revisions collide and the typed candidate_ids channel is not being consumed: {context}"
        )


def test_the_ambiguity_refusal_is_distinguishable_from_the_no_revision_refusal() -> None:
    """POSITIVE CONTROL for the assertion above.

    Without this, the previous test passes for a surface that raises the ambiguity key
    unconditionally -- including for a filing year that resolves no revision at all,
    which is the opposite condition with the opposite remedy. Proving the two paths
    diverge is what makes the first assertion about ambiguity rather than about "some
    refusal happened".
    """
    from .....application import modelo as _modelo_module
    from cadrumo.domain.calculations.registry.errors import NoRevisionForPeriodError

    def _unresolved(**_kwargs: object) -> str:
        raise NoRevisionForPeriodError(modelo_id="303", filing_year=1999, period="3T", revision_id=None)

    with (
        scoped_attribute(_modelo_module, "resolve_registry_revision_for_work_target", _unresolved),
        pytest.raises(_profile_inspect._CliRefusedBoundaryError) as raised,
    ):
        _resolve_preflight_revision_id(modelo="303", period=Period.from_year_and_code(1999, "3T"), revision_id=None)

    assert raised.value.translated_message == "cli.config.profile.preflight_revision_unresolved", (
        "an unresolvable filing year must not surface the AMBIGUOUS refusal; if both conditions "
        "produce one message the ambiguity assertion above proves nothing"
    )
