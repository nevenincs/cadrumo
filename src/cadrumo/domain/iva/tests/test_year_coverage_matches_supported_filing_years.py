"""Every exact-year-keyed IVA corpus must cover the master filing window.

Two IVA corpora are resolved by EXACT year key and raise on a miss:
:func:`~domain.iva.load_iva_catalogues` (rate and regulation catalogue) and
:func:`~domain.iva._place_of_supply.load_place_of_supply_rules` (the provision
establishing each classification rule's placement). Neither falls back to an
adjacent year, and that refusal is deliberate -- an ungrounded placement has no
provision behind it, so answering anyway would manufacture one.

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
year's table: a mirrored provision is a fabricated citation wearing a legal
reference, which is the failure the grounding rules exist to prevent.
"""

from __future__ import annotations

from collections.abc import Callable, Collection

import pytest

from ...calculations.registry.authority import bundled_authority
from .. import load_iva_catalogues, load_place_of_supply_rules

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Each exact-year-keyed IVA corpus, named by the registry directory it loads,
#: paired with the loader whose keys are its covered filing years.
_YEAR_KEYED_IVA_CORPORA: tuple[tuple[str, Callable[[], Collection[int]]], ...] = (
    ("aeat/iva/catalogues", load_iva_catalogues),
    ("aeat/iva/place_of_supply", load_place_of_supply_rules),
)


def _supported_filing_years() -> tuple[int, ...]:
    """Return the registry's single declared supported filing window."""
    declaration = bundled_authority().catalogues.supported_filing_years
    assert declaration is not None, (
        "the registry declares no supported filing years; "
        "aeat/legal/supported-filing-years.toml is the one writable declaration "
        "and every year-keyed corpus is measured against it"
    )
    return tuple(declaration.years)


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
