"""Tests for :func:`~cadrumo.application.registry.diff_registry_revisions`.

Grounds the diff against *real* revision pairs shipped in the bundled registry
-- the Modelo 303 pair spanning its 2023 rulebook change (``2022``
and ``2023``) and, for the legal-grounding dimension, the two Modelo 180
revisions (``2019-2022`` and the one Orden HFP/1284/2023 approved). Every
expected count and identifier below was read off the registry TOML tree, never
hand-computed from a synthetic fixture, so the diff is proven against real,
known rulebook changes rather than values manufactured by the test author.

Choosing an anchor
------------------
Reading the expectations off the tool's own output is how this module was first
written, and it is exactly how a *defect* becomes a pinned expectation. The
prorrata percentage formula was once asserted here as a changed formula. It was
never a rulebook change: the two revisions declared different no-volume-data
branches -- 0 against 100 -- because the older one carried a defect that zeroed
a fully-taxable trader's deduction. Correcting it made the two revisions agree,
the anchor vanished, and this module red. The formula had no unique claim on
any tracked dimension either; it duplicated coverage a surviving anchor already
had.

So an anchor now has to earn its place by being STRUCTURALLY FORCED, not merely
observed to differ:

* ``modelo-303-iva-cuota-devengada-total`` differs because the 2023 revision
  sums a casilla the 2009 revision does not have. That casilla is reported as
  added by the same diff, and the assertion below reads the coupling rather
  than restating the identifier -- a total that sums a new summand cannot be
  identical across the pair, so convergence would require deleting a real 2023
  casilla.
* ``modelo-303-iva-resultado`` differs in ``legal_refs`` because each revision
  cites the orden that approved its own form version. Two ordenes published
  sixteen years apart do not converge.
* ``modelo-180-base-total`` / ``modelo-180-retenciones-total`` differ in
  ``legal_refs`` ALONE, adding Orden HFP/1284/2023. They are the only witness
  in the bundled registry for that dimension: strike the ``legal_refs``
  comparison out of the diff and no Modelo 303 assertion notices, because the
  M303 formulas that differ in ``legal_refs`` also differ in expression.

The rounding dimension has no witness at all. No revision pair in the bundled
registry diverges in rounding alone, so that comparison is unproven here and a
reader must not take the checks below as covering it. Fabricating a divergence
to close the gap would be inventing a rulebook change; the honest statement is
that the witness does not exist yet.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.calculations.registry import (
    ModeloRevision,
    NoRevisionForPeriodError,
    RegistrySnapshotError,
    bundled_authority,
)
from .. import RegistryApplicationInputError, diff_registry_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Modelo 303's 2023 rulebook change: "2022" covers filing years
# 2022 and "2023" covers 2023 alone, the modelo having since split again
# for 2024 onward. These are the modelo's real, declared revision boundaries --
# not synthetic fixtures.
_M303_PRE_YEAR = 2022
_M303_POST_YEAR = 2023

# Modelo 180's two real revisions, split by Orden HFP/1284/2023.
_M180_PRE_YEAR = 2022
_M180_POST_YEAR = 2023


def _revision_pair(modelo: str, from_year: int, to_year: int) -> tuple[ModeloRevision, ModeloRevision]:
    """Return both revisions of ``modelo`` straight from the registry authority.

    Read through the authority rather than through the diff report, so an
    assertion about what the diff SHOULD have found is grounded in the registry
    itself and not in the diff's own projection of it.
    """
    authority = bundled_authority()
    return (
        authority.snapshot(modelo, filing_year=from_year, period="1T" if modelo == "303" else "0A").revision,
        authority.snapshot(modelo, filing_year=to_year, period="1T" if modelo == "303" else "0A").revision,
    )


def _formula_fingerprint(revision: ModeloRevision) -> dict[str, tuple[dict[str, object], frozenset[str], str]]:
    """Return ``{formula_id: (expression, legal_refs, rounding)}`` for one revision.

    The three dimensions the diff declares it tracks, read off the schema.
    """
    return {
        formula.id: (
            formula.expression.model_dump(mode="json"),
            frozenset(formula.legal_refs),
            str(formula.rounding),
        )
        for formula in revision.formulas
    }


def _referenced_casilla_ids(expression: object) -> set[str]:
    """Return every casilla id an expression projection reads, at any depth."""
    found: set[str] = set()
    if not isinstance(expression, dict):
        return found
    casilla_id = expression.get("casilla_id")
    if isinstance(casilla_id, str):
        found.add(casilla_id)
    arguments = expression.get("args")
    if isinstance(arguments, list):
        for argument in arguments:
            found |= _referenced_casilla_ids(argument)
    return found


def test_diff_registry_revisions_reports_no_change_within_one_revision() -> None:
    """Two years covered by the same declared revision report no changes."""
    report = diff_registry_revisions("303", from_year=2015, to_year=2020)

    assert report.same_revision is True
    assert report.from_revision_id == report.to_revision_id == "2022"
    assert report.added_casillas == ()
    assert report.removed_casillas == ()
    assert report.renumbered_casillas == ()
    assert report.added_formulas == ()
    assert report.changed_formulas == ()
    assert report.added_bindings == ()


def test_diff_registry_revisions_resolves_the_real_m303_revision_boundary() -> None:
    """2022 and 2023 resolve to the two real, distinct M303 revisions."""
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    assert report.same_revision is False
    assert report.from_revision_id == "2022"
    assert report.to_revision_id == "2023"


def test_diff_registry_revisions_surfaces_real_added_casillas() -> None:
    """The 2023 M303 revision adds real casillas absent from 2022.

    ``iva.autoconsumo.promotor.base`` / ``iva.autoconsumo.promotor.cuota`` are
    the real property-developer self-consumption casillas the 2023 revision
    introduces; they do not exist under ``2022``.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    added_ids = {casilla.id for casilla in report.added_casillas}
    assert "iva.autoconsumo.promotor.base" in added_ids
    assert "iva.autoconsumo.promotor.cuota" in added_ids
    # Every added casilla is genuinely absent from the "from" revision and
    # genuinely present in the "to" revision -- not a renumbering artefact.
    assert report.removed_casillas == ()
    assert report.renumbered_casillas == ()


def test_diff_registry_revisions_surfaces_a_formula_that_gained_a_new_summand() -> None:
    """The devengada total differs BECAUSE the 2023 revision sums a new casilla.

    The strongest anchor available: the assertion reads the coupling instead of
    restating the identifier.  The 2023 revision introduces the property
    developer self-consumption cuota, the same diff reports that casilla as
    added, and the total that sums it therefore cannot match the older
    revision's.  Making the two agree would mean deleting a real 2023 casilla,
    which is why this anchor does not decay the way an observed-to-differ one
    does.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    devengada = next(
        formula for formula in report.changed_formulas if formula.id == "modelo-303-iva-cuota-devengada-total"
    )
    assert devengada.target_casilla_id == "iva.cuota-devengada-total"

    added_casilla_ids = {casilla.id for casilla in report.added_casillas}
    new_summands = _referenced_casilla_ids(devengada.to_expression) - _referenced_casilla_ids(devengada.from_expression)

    assert new_summands & added_casilla_ids, (
        "the devengada total is reported as changed, but none of the casillas it gained "
        f"({sorted(new_summands)}) is one the same diff reports as added "
        f"({sorted(added_casilla_ids)}) -- the anchor has lost the structural reason it was chosen"
    )
    assert "iva.autoconsumo.promotor.cuota" in new_summands


def test_diff_registry_revisions_surfaces_a_formula_that_dropped_a_superseded_orden() -> None:
    """The resultado formula stops citing the orden that approved the 2008 form.

    Orden EHA/3786/2008 approved the form the 2009 revision belongs to and
    binds nothing in the 2023 one, so the citation is dropped rather than
    converged: a dated, separately published orden is not something a later
    correction reinstates.

    The mirror-image half -- a formula GAINING the orden that approved its own
    later form -- is not asserted here.  Orden HAC/819/2024 grounds the two
    2024 revisions, and the year-keyed diff entry point cannot address a filing
    year that carries a mid-year design boundary, so that witness is currently
    unreachable through this surface.  The addition direction is covered
    instead by the Modelo 180 pair below, which is the bundled registry's
    isolated ``legal_refs`` witness.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    resultado = next(formula for formula in report.changed_formulas if formula.id == "modelo-303-iva-resultado")

    assert resultado.target_casilla_id == "iva.resultado"
    assert "orden-eha-3786-2008:art-1" in set(resultado.from_legal_refs) - set(resultado.to_legal_refs)


def test_diff_registry_revisions_surfaces_a_formula_that_changed_only_its_legal_grounding() -> None:
    """Modelo 180's totals differ in ``legal_refs`` ALONE, and only this notices.

    Both M303 formulas that differ in ``legal_refs`` also differ in expression,
    so deleting the ``legal_refs`` comparison from the diff leaves every M303
    assertion green while the diff has silently stopped tracking a dimension it
    documents.  The M180 pair is the bundled registry's only witness: Orden
    HFP/1284/2023 regrounds the two declaration totals without touching a
    single operand.
    """
    report = diff_registry_revisions("180", from_year=_M180_PRE_YEAR, to_year=_M180_POST_YEAR)

    changed = {formula.id: formula for formula in report.changed_formulas}
    assert {"modelo-180-base-total", "modelo-180-retenciones-total"} <= set(changed)

    for formula_id in ("modelo-180-base-total", "modelo-180-retenciones-total"):
        diff = changed[formula_id]
        assert diff.from_expression == diff.to_expression, (
            f"{formula_id} was chosen as the legal-grounding witness because its expression is "
            "untouched; it now differs in expression too, so it no longer isolates the dimension"
        )
        assert set(diff.to_legal_refs) - set(diff.from_legal_refs) == {"orden-hfp-1284-2023:art-7"}


def test_diff_registry_revisions_classifies_every_changed_formula_as_changed() -> None:
    """A changed formula is never reported as a spurious add/remove pair.

    The claim the module makes about the whole set rather than about one
    anchor: every reported change names a formula present in BOTH revisions,
    appears in neither the added nor the removed list, and genuinely differs in
    a tracked dimension when the two revisions are read straight off the
    registry authority instead of out of the diff's own projection.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)
    from_revision, to_revision = _revision_pair("303", _M303_PRE_YEAR, _M303_POST_YEAR)
    before = _formula_fingerprint(from_revision)
    after = _formula_fingerprint(to_revision)

    changed_ids = {formula.id for formula in report.changed_formulas}
    assert changed_ids, "the M303 revision pair must surface at least one changed formula"
    assert changed_ids <= set(before) & set(after), (
        f"changed formulas absent from one revision: {sorted(changed_ids - (set(before) & set(after)))}"
    )
    assert changed_ids.isdisjoint(report.added_formulas)
    assert changed_ids.isdisjoint(report.removed_formulas)

    undifferentiated = sorted(formula_id for formula_id in changed_ids if before[formula_id] == after[formula_id])
    assert undifferentiated == [], (
        f"the diff reported {undifferentiated} as changed while the registry declares them identical "
        "in expression, legal_refs and rounding"
    )


def test_diff_registry_revisions_stays_silent_on_a_formula_both_revisions_share() -> None:
    """A formula identical in all three tracked dimensions is NOT reported.

    The silence half.  Without it a diff that reported every common formula as
    changed would satisfy every firing assertion above.  The prorrata
    percentage is the concrete anchor, and it is one for a legal reason rather
    than an observed one: LIVA art. 102 was last amended before this revision
    window opens and art. 104's later amendment leaves its fraction and
    rounding paragraph untouched, so the same rule binds both windows and the
    two revisions are supposed to declare it identically.  This formula used to
    be asserted as CHANGED, which is what pinned the older revision's defect in
    place until it was corrected.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)
    from_revision, to_revision = _revision_pair("303", _M303_PRE_YEAR, _M303_POST_YEAR)
    before = _formula_fingerprint(from_revision)
    after = _formula_fingerprint(to_revision)

    prorrata = "modelo-303-iva-prorrata-porcentaje"
    assert before[prorrata] == after[prorrata], (
        "both revisions must declare the prorrata percentage identically; the applicable "
        "LIVA articles are unamended across the two windows"
    )

    changed_ids = {formula.id for formula in report.changed_formulas}
    assert prorrata not in changed_ids

    shared = {formula_id for formula_id in set(before) & set(after) if before[formula_id] == after[formula_id]}
    assert shared, "the vacuity floor: the pair must share at least one identical formula"
    assert shared.isdisjoint(changed_ids), (
        f"the diff reported formulas the registry declares identical: {sorted(shared & changed_ids)}"
    )


def test_diff_registry_revisions_surfaces_real_added_bindings() -> None:
    """Bindings introduced by the 2023 revision that had no counterpart in 2022."""
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    added_ids = {binding.id for binding in report.added_bindings}
    assert "modelo-303-autoconsumo-promotor-base" in added_ids
    assert report.removed_bindings == ()


def test_diff_registry_revisions_surfaces_real_added_parameters() -> None:
    """Rate parameters the 2023 transitional reduced-rate regime introduces.

    The two ``dr303`` transitional rate percentages carry the 5.00 and 7.50
    values that only exist because a temporary reduced rate was in force for
    part of the window the 2023 revision covers.  The 2009 revision has no such
    parameter to declare, so the addition is forced by the rulebook rather than
    read off the diff's own output.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    assert "m303-dr303-154-transitional-rate-percent" in report.added_parameters
    assert "m303-dr303-166-transitional-rate-percent" in report.added_parameters
    assert report.removed_parameters == ()


def test_diff_registry_revisions_surfaces_real_changed_casilla_legal_refs() -> None:
    """Casillas present in both revisions whose declared legal_refs set changed."""
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    assert "iva.resultado" in report.changed_casilla_legal_refs


def test_diff_registry_revisions_refuses_a_year_no_revision_covers() -> None:
    """A filing year outside every declared revision's period selector is refused,
    naming the modelo's declared revision ids rather than silently blanking.
    """
    with pytest.raises(RegistryApplicationInputError) as excinfo:
        diff_registry_revisions("303", from_year=1999, to_year=_M303_POST_YEAR)

    message = str(excinfo.value)
    assert excinfo.value.context is not None
    assert "1999" in message or excinfo.value.context.get("filing_year") == 1999


def test_diff_registry_revisions_applies_the_canonical_validity_window_and_retains_context() -> None:
    """The 2023 revision cannot be used before its real 2023 effective date.

    The domain selector owns the date test and raises its structured year-only
    error. Diffing adds the command-specific list of available revisions without
    replacing that cause with a second candidate-selection implementation.
    """
    with pytest.raises(RegistryApplicationInputError) as excinfo:
        diff_registry_revisions(
            "303",
            from_year=_M303_POST_YEAR,
            to_year=_M303_POST_YEAR,
            as_of=date(2022, 12, 31),
        )

    assert excinfo.value.context is not None
    assert excinfo.value.context["filing_year"] == _M303_POST_YEAR
    assert excinfo.value.context["available_revisions"] == ", ".join(
        sorted(bundled_authority().modelo("303").revisions),
    )
    cause = excinfo.value.__cause__
    assert isinstance(cause, NoRevisionForPeriodError)
    assert cause.period == "year"


def test_diff_registry_revisions_refuses_an_unknown_modelo() -> None:
    with pytest.raises(RegistrySnapshotError):
        diff_registry_revisions("999-nonexistent", from_year=2020, to_year=2023)
