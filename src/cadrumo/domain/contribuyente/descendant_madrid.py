"""Madrid nacimiento/adopción behavior for descendants."""

from __future__ import annotations

from decimal import Decimal

from .descendant_record import DescendantRecordBase
from .family_fact_context import FamilyFactResolutionContext
from .family_types import (
    within_multi_year_applicability_window,
)


class DescendantMadridMixin(DescendantRecordBase):
    """Madrid's autonomous deduction for a descendant."""

    def entry_year(self) -> int:
        """Calendar year of the nacimiento/adopción event, for the Madrid deducción window.

        Scoped to the autonomic nacimiento/adopción deducción and NOT to
        Art. 58.2, which counts from a different event for the same child: see
        :meth:`_entry_date` for why an acogimiento resolución moves one anchor
        and not the other, and :meth:`art_58_2_entry_date` for the state anchor.
        """
        return self._entry_date().year

    def is_within_entry_window(self, filing_year: int, *, following_periods: int) -> bool:
        """True when this descendant cohabits and *filing_year* falls in its entry window.

        The window opens in the nacimiento or adopción year and runs for
        *following_periods* periods after it, the number the deducción's own
        text sets. Cohabitation is required: the Madrid nacimiento/adopción
        deducción (DL 1/2010 art. 4) is for "los padres que convivan con los
        hijos nacidos o adoptados".
        """
        if not self.convive_con_contribuyente:
            return False
        return within_multi_year_applicability_window(
            self.entry_year(),
            filing_year,
            following_periods=following_periods,
        )

    def nacimiento_adopcion_prorrateo_share(self, *, context: FamilyFactResolutionContext) -> Decimal:
        """Return this descendant's share of the deducción after prorrateo.

        When the child cohabits with both parents and they file individually the
        Madrid manual splits the amount equally between the two declarations
        (the ``lirpf-art-61-shared-custody-proration-factor`` governed fact);
        otherwise the full amount accrues to this filer through the governed
        full-proration share fact.
        ``custodia_compartida`` is the profile signal for the shared-cohabitation
        case that triggers the ÷2 prorrateo.
        """
        if self.custodia_compartida:
            return context.decimal("lirpf-art-61-shared-custody-proration-factor")
        return context.decimal("madrid-nacimiento-adopcion-full-proration-share")
