"""The two rate-slot refusals must reach the operator as keys, never as English.

:func:`cadrumo.domain.invoices.iva_rate_percentage` refuses on two conditions
that must never share a message: the bundled registry does not REACH the date
for that tier (a limit of our coverage), and the slot's rate was genuinely not
IN FORCE for that tier on that date (a statement about Spanish law). Saying the
second when the first is true sends a filer to correct a figure that was right.

Both once carried that distinction in an authored English f-string, which meant
a Catalan, Spanish or Hungarian session lost it entirely at every boundary that
renders ``str(exc)``. The distinction now rides the refusal's key and its
``rate_registry_covers_date`` machine fact, so it survives translation.

The assertion here is an ABSENCE: with no authored positional message,
``str(exc)`` degrades to the key. A sentence re-added beside the key resolves
to identical localised text through
:func:`cadrumo.core.errors.resolve_error_message` and so hides from every
key-and-context assertion in the suite -- but it cannot hide from this one.
"""

from __future__ import annotations

from datetime import date

import pytest

from ...iva import IvaRateNotFoundError
from .. import IvaRate, iva_rate_percentage

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

#: Inside every ES tier's coverage. RATE_2 stood only October-December 2024, so
#: this date reaches the legality branch rather than the coverage branch.
_COVERED_BUT_OUT_OF_WINDOW = date(2024, 6, 1)


def test_not_in_force_refusal_carries_no_authored_sentence() -> None:
    """A covered date with an out-of-window rate takes the legality branch."""
    with pytest.raises(IvaRateNotFoundError) as caught:
        iva_rate_percentage(IvaRate.RATE_2, _COVERED_BUT_OUT_OF_WINDOW)

    assert str(caught.value) == "errors.iva.rate_slot_not_in_force"


@pytest.mark.parametrize(
    "key",
    ("errors.iva.rate_registry_coverage_gap", "errors.iva.rate_slot_not_in_force"),
)
def test_every_rate_slot_refusal_key_resolves_to_real_text(key: str) -> None:
    """A key that never landed in a catalogue must fail, not render bare."""
    from ....core.config import override_settings
    from ....core.i18n import tr

    for language in ("en", "es", "ca", "hu"):
        with override_settings(cadrumo_output_language=language):
            rendered = tr(key)
        assert rendered != key, f"{key} is unauthored in {language}"
        assert rendered.strip()
