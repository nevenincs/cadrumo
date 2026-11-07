"""The governed domiciliación rule against the published Calendario del Contribuyente.

``derive_payment_cutoff`` ignores a window's authored ``payment_cutoff_on`` and
applies only Orden EHA/1658/2009 art. 3.2 and Anexo II with AEAT's dated
practice, as the registry declares them. Every authored retention window (Modelos
111, 115 and 123) is compared with the cutoff the bundled Calendario of its year
publishes, read by :mod:`.retencion_deadline_support` independently of the
registry. A change to the rule that newly departs from, or newly agrees with, a
published date fails here.
"""

from __future__ import annotations

from typing import Final

import pytest

from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.deadlines.domiciliation_cutoff import DerivedPaymentCutoff, derive_payment_cutoff
from dev.registry.compiler.authority import compiled_bundled_authority

from .retencion_deadline_support import expected_cutoff

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_RETENCION_MODELOS: Final = ("111", "115", "123")


def test_the_domiciliation_rule_reproduces_every_published_retention_cutoff_but_the_named_discrepancy() -> None:
    compared = 0
    departures: dict[str, tuple[str, str]] = {}
    with bundled_indexed_authority().operation() as operation:
        for filing_year in filing_year_envelope().years:
            for modelo in _RETENCION_MODELOS:
                for _, _, window in compiled_bundled_authority().deadline_windows(filing_year, modelos=(modelo,)):
                    if window.payment_cutoff_on is None:
                        continue
                    published = expected_cutoff(window.filing_year, window.period.registry_token)
                    assert published is not None, window.id
                    derived = derive_payment_cutoff(modelo, window, operation=operation)
                    assert isinstance(derived, DerivedPaymentCutoff), (window.id, derived)
                    compared += 1
                    if derived.cutoff_on != published:
                        departures[window.id] = (published.isoformat(), derived.cutoff_on.isoformat())

    assert compared > 0
    # The one expected discrepancy. Calendario del Contribuyente 2026, p. 54, and
    # the 2026 domiciliación page publish "2M 26: 1 al 16 de marzo" for Modelo 111,
    # with filing to Friday 20 March. The Anexo II day, Sunday 15 March, is
    # replaced by the latest business day leaving three business days before the
    # close, Tuesday 17 (18, 19, 20): BOE-A-2025-23702 lists no Madrid inhábil day
    # from 16 to 20 March 2026, no Orden amended art. 3.2 after Orden HAC/241/2025,
    # and the same calendar publishes Tuesday 17 for 1M 26 and 10M 26, whose
    # weekdays fall identically. The authored 16 March stays authoritative.
    assert departures == {"modelo-111-2026-02": ("2026-03-16", "2026-03-17")}, departures
