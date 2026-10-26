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

    def is_nacimiento_adopcion_eligible(
        self,
        filing_year: int,
        *,
        context: FamilyFactResolutionContext,
    ) -> bool:
        """True when this descendant is inside the nacimiento/adopción window and cohabits.

        The Madrid nacimiento/adopción deducción (DL 1/2010 art. 4) requires both
        that the parent cohabits with the child ("Solo tendrán derecho a practicar
        la deducción los padres que convivan con los hijos nacidos o adoptados")
        and that the filing year falls inside the applicability window measured
        from the entry (nacimiento/adopción) year.
        """
        if not self.convive_con_contribuyente:
            return False
        return within_multi_year_applicability_window(
            self.entry_year(),
            filing_year,
            following_periods=context.integer("madrid-birth-adoption-following-periods"),
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
