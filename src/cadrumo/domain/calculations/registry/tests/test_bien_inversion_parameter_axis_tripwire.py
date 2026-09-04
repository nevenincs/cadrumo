"""Tripwire on the capital-goods regularisation figures' single-value shape.

LIVA arts. 107 and 109 fix a capital good's regularisation window, divisor, and
de-minimis threshold at the moment the good is ACQUIRED. The registry declares
them on the ``filing_period`` axis, which is the only axis any shipped parameter
uses, and that is sound only while each carries exactly ONE value per revision:
one value cannot express "this filing period, not that one" and so cannot apply
the wrong law to an old good.

A SECOND dated value would break that. It would read as "the figure changed from
filing period X", and for a good acquired before X the calculation would then
regularise on law that did not govern its acquisition -- silently, with no
refusal anywhere, because the resolver would find exactly one match and return
it. The defect is a declaration defect, so it is caught here at declaration time.

These tests therefore assert SHAPE, never a legal value: the figures live in the
registry precisely so that no Python file asserts what the law says. The day one
of them genuinely moves, this gate fails, and the work routes to a real
acquisition-axis declaration rather than to a second filing-period value.
"""

from __future__ import annotations

import pytest

from ..authority import ValidatedRegistryAuthority

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

#: Substring identifying the LIVA art-107/109 parameter family across revisions.
_FAMILY = "bien-inversion-"

#: Every modelo 303 revision. Modelo 390 is deliberately absent: its revisions
#: declare ``parameters`` not applicable, on the verified ground that the resumen
#: anual restates the periodic outcome and applies no figure of its own.
_REVISION_IDS = (
    "2022",
    "2023",
    "2024-hasta-08-y-2t",
    "2024-desde-09-y-3t",
    "2025",
    "2026-y-siguientes",
)

_EXPECTED_SLUGS = frozenset(
    {
        "ventana-anos-mueble",
        "ventana-anos-inmueble",
        "divisor-mueble",
        "divisor-inmueble",
        "regularizacion-umbral-puntos",
    },
)


def _family(authority: ValidatedRegistryAuthority, revision_id: str):
    """Return the art-107/109 parameters declared by one modelo 303 revision."""
    revision = authority.modelo("303").revisions[revision_id]
    return tuple(p for p in revision.parameters if _FAMILY in p.id)


@pytest.mark.parametrize("revision_id", _REVISION_IDS)
def test_every_revision_declares_the_whole_family(
    registry_authority: ValidatedRegistryAuthority,
    revision_id: str,
) -> None:
    """A revision that declares part of the family would resolve half the arithmetic."""
    declared = {p.id.split(_FAMILY, 1)[1] for p in _family(registry_authority, revision_id)}
    assert declared == _EXPECTED_SLUGS


@pytest.mark.parametrize("revision_id", _REVISION_IDS)
def test_each_figure_carries_exactly_one_filing_period_value(
    registry_authority: ValidatedRegistryAuthority,
    revision_id: str,
) -> None:
    """TEETH: a second dated value applies new law to a good acquired under the old.

    The failure message names the remedy rather than the symptom, because an
    author who has just added a second value is exactly the reader who needs it.
    """
    for parameter in _family(registry_authority, revision_id):
        assert len(parameter.values) == 1, (
            f"{parameter.id} in revision {revision_id} declares {len(parameter.values)} dated "
            "values. These figures are fixed at ACQUISITION (LIVA arts. 107, 109), not at "
            "filing, so a second filing-period value would regularise an old good on law "
            "that never governed it. Declare the change on an acquisition-keyed axis instead."
        )
        assert parameter.values[0].date_axis == "filing_period"


@pytest.mark.parametrize("revision_id", _REVISION_IDS)
def test_each_value_is_bounded_by_its_revision_window(
    registry_authority: ValidatedRegistryAuthority,
    revision_id: str,
) -> None:
    """An unbounded value would outlive the revision that grounds it."""
    revision = registry_authority.modelo("303").revisions[revision_id]
    for parameter in _family(registry_authority, revision_id):
        value = parameter.values[0]
        assert value.valid_from == revision.valid_from
        assert value.valid_to == revision.valid_to


def test_the_figures_are_identical_across_every_revision(
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """TEETH the other way: an unnoticed divergence between revisions.

    Compares revisions against EACH OTHER rather than against a literal, so the
    gate holds no legal value of its own and stays true if the law changes for
    every revision at once -- which is the only shape a change to a
    still-in-force article can lawfully take here.
    """
    per_revision = {
        rid: {p.id.split(_FAMILY, 1)[1]: p.values[0].value for p in _family(registry_authority, rid)}
        for rid in _REVISION_IDS
    }
    first, *rest = _REVISION_IDS
    for rid in rest:
        assert per_revision[rid] == per_revision[first], (
            f"revision {rid} declares different art-107/109 figures than {first}; "
            "a divergence here means one revision was updated and the others were not"
        )
