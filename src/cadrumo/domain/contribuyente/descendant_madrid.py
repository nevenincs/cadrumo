"""Madrid nacimiento/adopción behavior for descendants."""

from __future__ import annotations

from decimal import Decimal

from ...core.descendant_relacion import ART_58_2_ENTITLING_RELACIONES
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

    def art_58_2_window_anchor_missing(
        self,
        filing_year: int,
        *,
        context: FamilyFactResolutionContext,
        dependencia_assimilation_available: bool = False,
    ) -> bool:
        """True when an entitling relación has no entry date, so the limb cannot fire.

        The recordable state the coherence validators deliberately allow: an
        operator may declare an adoption or an entitling acogimiento before they
        hold the inscription or resolución date. Art. 58.2's age-independent
        increase then cannot be granted, because the window has nothing to
        measure from — an UNDER-grant, which is the safe direction, but a silent
        one unless something says so.

        Reports only the state that changes an outcome, so the advisory it feeds
        stays worth reading. A relación the statute excludes from the limb has
        no anchor to be missing. A descendant who fails the Art. 58.1 non-income
        conditions — not cohabiting, or over 25 with no discapacidad — carries no
        mínimo for the increase to attach to, so a missing date costs them
        nothing; a 30-year-old adopted descendant is the false positive this limb
        exists to suppress. And a descendant already under three takes the
        increase through the ordinary limb regardless.

        What remains is the older cohabiting adopted or fostered child, who is
        exactly the household the age-independent sentence was written for and
        the one currently granted nothing.

        The income ceilings are deliberately NOT applied. They need registry
        figures this layer does not resolve, and an absent rentas figure is
        non-excluding anyway, so the residual over-report is a descendant whose
        declared rentas breach the ceiling — a narrow case that already carries
        its own advisory.

        *dependencia_assimilation_available* is forwarded to the household limb
        for the same reason it exists there: a non-cohabiting descendant reaching
        the mínimo through the economic-dependency assimilation carries a real
        mínimo for the increase to attach to, so a missing anchor costs them
        exactly what it costs a cohabiting one. Omitting it took the predicate's
        ``False`` default and answered "no anchor missing" for that household —
        an under-grant reported to nobody, which is the one thing this disclosure
        exists to prevent.
        """
        if self.relacion not in ART_58_2_ENTITLING_RELACIONES:
            return False
        if not self.meets_non_income_conditions(
            filing_year,
            context=context,
            dependencia_assimilation_available=dependencia_assimilation_available,
        ):
            return False
        if self.age_at_year_end(filing_year) < context.integer("lirpf-art-58-under-three-maximum-age"):
            return False
        return self.art_58_2_entry_date() is None

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
