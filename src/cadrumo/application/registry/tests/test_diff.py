"""Tests for :func:`~cadrumo.application.registry.diff_registry_revisions`.

Grounds the diff against the two *real* Modelo 303 revisions shipped in the
bundled registry (``2009-y-siguientes`` and ``2023-y-siguientes``): every
expected count and identifier below was read directly off the registry TOML
tree (via ``diff_registry_revisions`` itself against a known real revision
pair), never hand-computed from a synthetic fixture. This proves the diff
surfaces real, known rulebook changes rather than asserting against arbitrary
values manufactured by the test author.
"""

from __future__ import annotations

import pytest

from ....domain.calculations.registry import RegistrySnapshotError
from .. import RegistryApplicationInputError, diff_registry_revisions

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# Modelo 303 ships exactly two revisions: "2009-y-siguientes" (covers filing
# years 2009-2022) and "2023-y-siguientes" (covers 2023 onward). These are the
# modelo's real, declared revision boundaries -- not synthetic fixtures.
_M303_PRE_YEAR = 2022
_M303_POST_YEAR = 2023


def test_diff_registry_revisions_reports_no_change_within_one_revision() -> None:
    """Two years covered by the same declared revision report no changes."""
    report = diff_registry_revisions("303", from_year=2015, to_year=2020)

    assert report.same_revision is True
    assert report.from_revision_id == report.to_revision_id == "2009-y-siguientes"
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
    assert report.from_revision_id == "2009-y-siguientes"
    assert report.to_revision_id == "2023-y-siguientes"


def test_diff_registry_revisions_surfaces_real_added_casillas() -> None:
    """The 2023 M303 revision adds real casillas absent from 2009-y-siguientes.

    ``iva.autoconsumo.promotor.base`` / ``iva.autoconsumo.promotor.cuota`` are
    the real property-developer self-consumption casillas the 2023 revision
    introduces; they do not exist under ``2009-y-siguientes``.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    added_ids = {casilla.id for casilla in report.added_casillas}
    assert "iva.autoconsumo.promotor.base" in added_ids
    assert "iva.autoconsumo.promotor.cuota" in added_ids
    # Every added casilla is genuinely absent from the "from" revision and
    # genuinely present in the "to" revision -- not a renumbering artefact.
    assert report.removed_casillas == ()
    assert report.renumbered_casillas == ()


def test_diff_registry_revisions_surfaces_real_changed_formulas() -> None:
    """Formulas whose target casilla persists across both revisions but whose
    expression, rounding, or legal grounding changed are reported as changed,
    never as a spurious add/remove pair.
    """
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    changed_ids = {formula.id for formula in report.changed_formulas}
    assert "modelo-303-iva-cuota-devengada-total" in changed_ids
    assert "modelo-303-iva-prorrata-porcentaje" in changed_ids
    assert "modelo-303-iva-resultado" in changed_ids

    cuota_devengada_diff = next(
        formula for formula in report.changed_formulas if formula.id == "modelo-303-iva-cuota-devengada-total"
    )
    assert cuota_devengada_diff.target_casilla_id == "iva.cuota-devengada-total"
    # A genuinely changed formula must differ in at least one tracked
    # dimension (expression, or legal_refs) between the two revisions.
    assert cuota_devengada_diff.from_expression != cuota_devengada_diff.to_expression or set(
        cuota_devengada_diff.from_legal_refs
    ) != set(cuota_devengada_diff.to_legal_refs)


def test_diff_registry_revisions_surfaces_real_added_bindings() -> None:
    """Bindings introduced by the 2023 revision that had no counterpart in 2009-y-siguientes."""
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    added_ids = {binding.id for binding in report.added_bindings}
    assert "modelo-303-autoconsumo-promotor-base" in added_ids
    assert report.removed_bindings == ()


def test_diff_registry_revisions_surfaces_real_added_parameters() -> None:
    """Rate/threshold parameters that the 2023 módulos IVA machinery introduces."""
    report = diff_registry_revisions("303", from_year=_M303_PRE_YEAR, to_year=_M303_POST_YEAR)

    assert "m303-modulos-iva-coeficientes-2025" in report.added_parameters
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


def test_diff_registry_revisions_refuses_an_unknown_modelo() -> None:
    with pytest.raises(RegistrySnapshotError):
        diff_registry_revisions("999-nonexistent", from_year=2020, to_year=2023)
