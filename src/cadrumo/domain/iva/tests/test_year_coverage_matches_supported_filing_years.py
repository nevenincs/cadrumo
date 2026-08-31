"""Every exact-year-resolved IVA corpus must cover the master filing window.

Two IVA corpora are resolved by EXACT filing year and raise on a miss:
:func:`~domain.iva.iva_catalogue_years` (rate and regulation catalogue) and
:func:`~domain.iva.place_of_supply_years` (the provision establishing each
classification rule's placement). Neither falls back to an adjacent year, and
that refusal is deliberate -- an ungrounded placement has no provision behind
it, so answering anyway would manufacture one.

Coverage is DERIVED from the validity window each grounded record declares, not
read off a filename. These corpora were year-named files until the collapse onto
dated grounding; the years they resolve for are now the years their cited
provisions actually support, which is what the obligation was always about.

The registry declares ONE supported filing window, in
``aeat/legal/supported-filing-years.toml``, reached here through
:class:`~domain.calculations.registry.RegistryCatalogues`. A corpus that resolves
by exact year while covering less than that window is a silent hole: the product
claims a filing year it cannot ground.

This gate is therefore a hard fail, not an advisory, and it is on the PROPERTY
(every supported year resolves) rather than any tally of files -- a count would
encode a moment and then detect nothing.

**Closing a red here means GROUNDING the missing year against BOE or AEAT, or
formally narrowing the supported window.** It never means copying an adjacent
year's table, and -- now that spans are declared rather than implied by a
filename -- it never means widening a window either. A mirrored provision and a
widened window are the same fabricated citation wearing a legal reference, which
is the failure the grounding rules exist to prevent. The companion
provision-window gate holds every span inside the effective span of the article
it cites, so a widening that would turn this gate green reds that one instead.
"""

from __future__ import annotations

from collections.abc import Callable, Collection

import pytest

from ....core.directory_scan import scan_directory
from ....core.resources._boundary import bundled_path
from ...calculations.registry.loader import load_catalogue_file
from ..catalogue import iva_catalogue_years
from ..place_of_supply import place_of_supply_years

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Each exact-year-keyed IVA corpus, named by the registry directory it loads,
#: paired with the loader whose keys are its covered filing years.
_YEAR_KEYED_IVA_CORPORA: tuple[tuple[str, Callable[[], Collection[int]]], ...] = (
    ("aeat/iva/catalogues.toml", iva_catalogue_years),
    ("aeat/iva/place_of_supply.toml", place_of_supply_years),
)


def _supported_filing_years() -> tuple[int, ...]:
    """Return the registry's single declared supported filing window.

    Read through the canonical per-file catalogue loader over ``legal/`` rather
    than by constructing the whole validated authority. The subject here is one
    declaration, and coupling to full-registry validation would make an
    unrelated modelo's mid-edit surface as an opaque IVA coverage failure --
    masking this gate's real verdict behind someone else's red.

    Mirrors the shared-catalogue loader's own contract: the declaration is
    registry-wide and lives in exactly ONE file.
    """
    declarations = {
        path.name: catalogue.supported_filing_years.years
        for path in scan_directory(bundled_path("registry", "aeat", "legal"), pattern="*.toml")
        if (catalogue := load_catalogue_file(path)).supported_filing_years is not None
    }
    assert declarations, (
        "the registry declares no supported filing years; aeat/legal/ carries the one "
        "writable declaration and every year-keyed corpus is measured against it"
    )
    assert len(declarations) == 1, (
        f"supported filing years are declared in more than one legal catalogue file: "
        f"{sorted(declarations)}; the declaration is registry-wide and has exactly one home"
    )
    return tuple(next(iter(declarations.values())))


@pytest.mark.parametrize(
    ("corpus", "loader"), _YEAR_KEYED_IVA_CORPORA, ids=lambda value: getattr(value, "__name__", value)
)
def test_year_keyed_iva_corpus_covers_every_supported_filing_year(
    corpus: str,
    loader: Callable[[], Collection[int]],
) -> None:
    supported = _supported_filing_years()
    covered = set(loader())
    missing = sorted(year for year in supported if year not in covered)

    assert not missing, (
        f"{corpus} resolves by exact year but does not cover supported filing "
        f"year(s) {missing}; covered={sorted(covered)}, supported={list(supported)}. "
        "Ground the missing year(s) against BOE or AEAT, or narrow the supported "
        "window -- never mirror an adjacent year's table."
    )
