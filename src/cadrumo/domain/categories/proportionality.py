"""Proportionality and explainability primitives for category profiles.

Defines the closed enums and strict pydantic models that encode how
a spending category is deducted on the autónomo filings, plus the
citation chain back to the relevant authority that makes each rule
explainable. Every :class:`ProportionalityRule` carries at least one
:class:`CategoryCitation`; the consistency rules between
``kind``-specific fields (``fixed_pct``, ``default_ratio``,
``statutory_cap_*``) are enforced by the model validator.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from enum import StrEnum
from urllib.parse import urlsplit

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator

from ...core.citation_grounding import CitationGrounding
from ...core.external_constants import load_external_constants
from ...core.i18n import Translatable as tr
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.unit_proportion import UnitProportion
from ...core.url_validation import ANY_HTTP_URL_ADAPTER
from ...core.validity_window import ValidityWindow
from .errors import CategoryValidationError

#: The only scheme a citation may cite. Every AEAT and BOE surface the
#: shipped profiles reference publishes over TLS, so a non-``https``
#: citation is a downgrade rather than a legitimate authority.
_CITATION_SCHEME = "https"


class _ProportionalityStrictFrozenModel(BaseModel):
    """Shared strict immutable boundary model."""

    model_config = STRICT_FROZEN_CONFIG


def _require_translatable_text(value: tr, field_name: str) -> None:
    """Assert a translatable authority field contains non-blank text."""
    if not str(value).strip():
        raise CategoryValidationError(f"{field_name} must contain authoritative Spanish text")


def _authoritative_citation_origins() -> frozenset[str]:
    """Return the registered domains a category citation may cite.

    Derived from the canonical
    :class:`core.external_constants.AeatDomainSection` registry, which owns every
    AEAT / BOE hostname, so this module never restates a hostname literal
    and a domain rotation reaches citations automatically.
    """
    domains = load_external_constants().aeat.domains
    origins = {domains.host_suffix.lower()}
    for origin in (domains.boe, domains.legacy_www):
        host = urlsplit(origin).hostname
        if host is not None:
            origins.add(host.lower())
    return frozenset(origins)


def _host_is_authoritative(host: str, accepted: frozenset[str]) -> bool:
    """Return whether ``host`` is an accepted origin or a subdomain of one.

    Suffix matching is anchored on a dot boundary so a look-alike host such
    as ``evil-agenciatributaria.gob.es`` cannot pass by ending in the same
    characters as the real origin.
    """
    return any(host == origin or host.endswith(f".{origin}") for origin in accepted)


class CategoryCitationSource(StrEnum):
    """Allowed citation sources for explainable category profiles.

    Attributes:
        MANUAL_RENTA: AEAT *Manual práctico Renta*.
        MANUAL_IVA: AEAT *Manual práctico IVA*.
        LEY_IRPF: Ley del Impuesto sobre la Renta de las Personas
            Físicas.
        REGLAMENTO_IRPF: Reglamento del IRPF.
        AEAT_HELP: AEAT online help / portal text.
    """

    MANUAL_RENTA = "manual_renta"
    MANUAL_IVA = "manual_iva"
    LEY_IRPF = "ley_irpf"
    REGLAMENTO_IRPF = "reglamento_irpf"
    AEAT_HELP = "aeat_help"


#: Citation sources published as a dated ANNUAL EDITION, as opposed to a statute
#: whose reference year is its enactment. The distinction is what makes the
#: anti-mirror invariant precise rather than a year-sniffing heuristic: "Manual
#: práctico Renta 2025" names the edition read, while "Ley 35/2006" names when
#: the law was passed and says nothing about which filing year it covers.
ANNUAL_EDITION_CITATION_SOURCES: frozenset[CategoryCitationSource] = frozenset(
    {
        CategoryCitationSource.MANUAL_RENTA,
        CategoryCitationSource.MANUAL_IVA,
        CategoryCitationSource.AEAT_HELP,
    },
)

#: Citation sources that name a PROVISION rather than a dated publication. Their
#: windows are bounded by the provision's own effective span in the registry
#: legal catalogue, which makes a multi-year statutory citation a derived fact
#: instead of an author's confidence. Complete by construction against the enum:
#: a new source must land in one partition or the other, and the gate that reads
#: these sets reds if it lands in neither.
STATUTORY_CITATION_SOURCES: frozenset[CategoryCitationSource] = frozenset(
    set(CategoryCitationSource) - ANNUAL_EDITION_CITATION_SOURCES,
)

#: Matches the four-digit edition year in an annual publication's reference.
_EDITION_YEAR_PATTERN = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")


class CategoryCitation(_ProportionalityStrictFrozenModel):
    """Traceable citation backing one category or proportionality rule.

    Attributes:
        source: Originating :class:`CategoryCitationSource`.
        reference: Human-readable document reference (title,
            edition, BOE number).
        locator: Section, article, or page locator within the
            referenced document.
        url: Canonical URL where the citation can be checked. Constrained
            to an official AEAT or BOE origin over ``https`` -- see
            :meth:`_validate_authoritative_url`.
        quote: Verbatim Spanish from the bundled corpus, stored INLINE and never
            as a translation key. Verifying a quotation requires the literal
            text at the citation site; indirecting it means the record no longer
            carries its own evidence, whatever the key resolves to. Empty when,
            and only when, :attr:`grounding` is not ``VERIFIED``.
        grounding: Which of the three states this citation's evidence is in --
            read against the corpus, examined and refused, or unreachable
            because the cited document is not bundled.
        grounding_reason: Why no quotation is carried. Required when, and only
            when, :attr:`grounding` is not ``VERIFIED``.
        legal_ref: The registry legal-catalogue id of the provision cited.
            Required on a STATUTORY source and forbidden on an annual-edition
            one, so that every citation is bounded on exactly one axis: an
            edition-dated citation by the edition it names, a statutory one by
            the provision's own effective span. Leaving it optional would let an
            author widen a statutory window with nothing able to check it.
        valid_from: First date this citation is asserted to support the rule.
        valid_to: Last date, inclusive. Both bounds are required: the span is
            the claim, and a defaulted one would assert grounding nobody typed.
    """

    source: CategoryCitationSource
    reference: str = Field(min_length=1, max_length=256)
    locator: str = Field(min_length=1, max_length=256)
    url: AnyHttpUrl
    quote: str = Field(
        default="",
        description="Verbatim Spanish from the bundled corpus; empty only when grounding is not verified.",
    )
    grounding: CitationGrounding = Field(
        default=CitationGrounding.VERIFIED,
        description="Whether the quotation was verified against the corpus, refused, or is unreachable.",
    )
    grounding_reason: str = Field(
        default="",
        description="Why no quotation is carried; required when grounding is not verified.",
    )
    legal_ref: str | None = Field(
        default=None,
        min_length=1,
        description="Registry legal-catalogue id of the cited provision; statutory sources only.",
    )
    valid_from: date
    valid_to: date

    @property
    def window(self) -> ValidityWindow:
        """Return the closed span this citation is asserted over.

        Returns:
            The :class:`~core.validity_window.ValidityWindow` the two declared
            bounds describe.
        """
        return ValidityWindow(valid_from=self.valid_from, valid_to=self.valid_to)

    @field_validator("url", mode="after")
    @classmethod
    def _validate_authoritative_url(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        """Refuse a citation that does not resolve to an official origin.

        A citation is the operator's route back to the authority behind a
        deduction rule, so an arbitrary host is not a weaker citation --
        it is an unverifiable one. ``AnyHttpUrl`` alone accepts any host on
        either scheme, so the origin is constrained here against the
        canonical :class:`core.external_constants.AeatDomainSection` registry
        rather than against hostname literals restated in this module.
        """
        accepted = _authoritative_citation_origins()
        host = (value.host or "").lower()
        scheme = value.scheme.lower()
        if scheme != _CITATION_SCHEME or not _host_is_authoritative(host, accepted):
            raise CategoryValidationError(
                f"category citation url {str(value)!r} is not an official authority: "
                f"expected an {_CITATION_SCHEME} URL whose host is, or is a subdomain of, "
                f"one of {', '.join(sorted(accepted))}",
            )
        return value

    @model_validator(mode="after")
    def _validate_quote(self) -> CategoryCitation:
        self._validate_grounding_matches_its_evidence()
        # Constructing the window is the validation: an inverted span refuses
        # here, where the citation was written, rather than silently covering
        # no year at all downstream.
        _ = self.window
        self._validate_edition_year_bounds_the_window()
        self._validate_legal_ref_matches_the_source_kind()
        return self

    def _validate_grounding_matches_its_evidence(self) -> None:
        """Hold each grounding state to the evidence it claims.

        Unlike the check this replaced, both branches can fail. The old one
        asserted a translatable was non-empty AFTER the loader had already
        resolved it through a fallback that never yields an empty string, so it
        inspected the literal word "Quote", found it non-empty, and passed for
        all eighty-three citations in the corpus.

        The second branch matters as much as the first. The corpus-containment
        gate skips a non-verified citation by design, so candidate text parked
        there would never be read against anything while still reading as
        evidence to anyone who printed it.
        """
        where = f"CategoryCitation[{self.source.value}/{self.locator}]"
        if self.grounding is CitationGrounding.VERIFIED:
            if not self.quote.strip():
                raise CategoryValidationError(
                    f"{where}: a verified citation must carry its verbatim quotation",
                )
            if self.grounding_reason.strip():
                raise CategoryValidationError(
                    f"{where}: a verified citation must not carry a grounding reason",
                )
            return
        if not self.grounding_reason.strip():
            raise CategoryValidationError(
                f"{where}: a {self.grounding.value!r} citation must record WHY it carries no "
                "quotation, so that it reads as examined rather than merely unchecked",
            )
        if self.quote.strip():
            raise CategoryValidationError(
                f"{where}: a {self.grounding.value!r} citation must not carry a quotation; "
                "the containment gate skips this state, so the text would never be checked",
            )

    def _validate_legal_ref_matches_the_source_kind(self) -> None:
        """Every citation must be checkable on exactly one axis, never neither.

        A statutory citation carries no edition year to bound it, so without a
        provision id nothing can judge how far its window may reach and an
        author could widen it freely. An annual-edition citation is already
        bounded by the edition it names; giving it a provision id too would
        offer a second, looser axis to be judged on.
        """
        if self.source in STATUTORY_CITATION_SOURCES and self.legal_ref is None:
            raise CategoryValidationError(
                f"category citation from {self.source.value!r} cites a provision and must name it with "
                "legal_ref, so its validity window can be bounded by that provision's effective span "
                "rather than asserted",
            )
        if self.source in ANNUAL_EDITION_CITATION_SOURCES and self.legal_ref is not None:
            raise CategoryValidationError(
                f"category citation from {self.source.value!r} is bounded by the edition year it names; "
                f"it must not also carry legal_ref={self.legal_ref!r}",
            )

    def _validate_edition_year_bounds_the_window(self) -> None:
        """Refuse an annual-edition citation whose window reaches past its edition.

        THIS IS THE ANTI-MIRROR INVARIANT, and it is enforced here, at
        construction, rather than only in a gate: a corpus that refuses the
        shape cannot acquire it, whereas a gate can be run late or not at all.

        A citation naming an annual edition asserts that THAT edition supports
        the rule. Stretching its window over a neighbouring year converts a
        document nobody read into a grounding claim, which is precisely how the
        retired per-year mirror was produced -- its year-dated references were
        rewritten by string substitution from a reviewed year, so the copy
        asserted 41 times that a manual nobody opened said something.

        The edition year is required, not merely checked when present. An annual
        publication cited without an edition is unciteable in the first place,
        and leaving the year optional would hand an author a one-token escape
        from the invariant.
        """
        if self.source not in ANNUAL_EDITION_CITATION_SOURCES:
            return
        edition_years = {int(match.group()) for match in _EDITION_YEAR_PATTERN.finditer(self.reference)}
        if not edition_years:
            raise CategoryValidationError(
                f"category citation from {self.source.value!r} must name the edition year it was read "
                f"from in its reference, but reference={self.reference!r} carries none; an annual "
                "publication cited without an edition cannot be checked against its window",
            )
        outside = sorted(year for year in self.window.years() if year not in edition_years)
        if outside:
            raise CategoryValidationError(
                f"category citation reference={self.reference!r} names edition year(s) "
                f"{sorted(edition_years)} but its validity window reaches {outside}; read the source "
                "for those years and cite it, never widen an edition-dated citation to cover them",
            )


def parse_http_url(value: str) -> AnyHttpUrl:
    """Parse a string into a statically typed :class:`AnyHttpUrl`.

    Args:
        value: Raw HTTP / HTTPS URL string.

    Returns:
        A validated :class:`pydantic.AnyHttpUrl`.
    """
    return ANY_HTTP_URL_ADAPTER.validate_python(value)


class ProportionalityKind(StrEnum):
    """Supported proportionality kinds for downstream evaluator engines.

    Attributes:
        FULL_DEDUCTIBLE: Fully deductible against the activity.
        FIXED_PERCENTAGE: Deductible at a fixed percentage; requires
            ``fixed_pct``.
        USAGE_RATIO_PERSONAL: Deductible at a personal-usage ratio
            chosen by the taxpayer; may carry ``default_ratio``.
        USAGE_RATIO_HOME_AREA: Deductible at the home-office area
            ratio; may carry ``default_ratio``.
        STATUTORY_CAP: Capped by a statutory daily or annual limit;
            requires the matching ``statutory_cap_*`` fields.
        NON_DEDUCTIBLE: Not deductible against the activity.
    """

    FULL_DEDUCTIBLE = "full_deductible"
    FIXED_PERCENTAGE = "fixed_percentage"
    USAGE_RATIO_PERSONAL = "usage_ratio_personal"
    USAGE_RATIO_HOME_AREA = "usage_ratio_home_area"
    STATUTORY_CAP = "statutory_cap"
    NON_DEDUCTIBLE = "non_deductible"
    REQUIRES_EXCLUSIVE_USE = "requires_exclusive_use"


class StatutoryCapPeriod(StrEnum):
    """Supported statutory-cap accounting periods.

    Attributes:
        DAY: Cap applies per day.
        YEAR_PER_PERSON: Cap applies per year per covered person.
    """

    DAY = "day"
    YEAR_PER_PERSON = "year_per_person"


class StatutoryCapVariant(_ProportionalityStrictFrozenModel):
    """One legally distinct cap inside a statutory-cap rule, selected by a condition.

    The condition is what makes a variant a variant; the UNIT of the amount is
    incidental and the law uses both. RIRPF art. 9.A.3.a distinguishes con and sin
    pernocta and states DAILY amounts; LIRPF art. 30.2.5.a distinguishes a person with
    discapacidad from one without and states ANNUAL per-person amounts. Modelling only
    the daily unit is why the second provision could ship with one of its two limbs
    missing.

    Attributes:
        id: Stable identifier the calculation context selects on.
        label: Translation key for the human-readable label.
        statutory_cap_eur_per_day: A daily amount, for a rule capped per day.
        statutory_cap_eur: An annual amount, for a rule capped per period. Exactly
            one of the two is set: a variant carrying both would leave the unit to
            the call site, and a variant carrying neither caps nothing.
    """

    id: str = Field(min_length=1, max_length=64)
    label: tr = Field(description="Translation key for the human-readable label.")
    statutory_cap_eur_per_day: Decimal | None = Field(default=None, ge=Decimal("0"))
    statutory_cap_eur: Decimal | None = Field(default=None, ge=Decimal("0"))

    @model_validator(mode="after")
    def _validate_label(self) -> StatutoryCapVariant:
        _require_translatable_text(self.label, "statutory cap variant label")
        declared = (self.statutory_cap_eur_per_day is not None, self.statutory_cap_eur is not None)
        if not any(declared):
            raise CategoryValidationError(
                f"statutory cap variant {self.id!r} declares no amount; a variant that caps "
                "nothing cannot be selected for anything",
            )
        if all(declared):
            raise CategoryValidationError(
                f"statutory cap variant {self.id!r} declares both a daily and an annual amount; "
                "the unit must be fixed by the variant, not chosen at the call site",
            )
        return self

    @property
    def is_per_day(self) -> bool:
        """Return whether this variant's amount is a daily one.

        Returns:
            ``True`` when the variant carries :attr:`statutory_cap_eur_per_day`.
        """
        return self.statutory_cap_eur_per_day is not None


class StatutoryCapAmount(_ProportionalityStrictFrozenModel):
    """One year-bounded value of a statutory cap whose amount the law varies.

    Some statutory caps are fixed by the tax law and hold until it is amended --
    the 500 euro seguro de enfermedad limit of LIRPF art. 30.2.5.a is one. Others
    are fixed BY REFERENCE to a figure that moves every year: LIRPF art. 30.2.1
    caps the deductible mutualidad alternativa premium at the cuota maxima por
    contingencias comunes established "en cada ejercicio economico" in the RETA.

    A single :attr:`ProportionalityRule.statutory_cap_eur` cannot express the
    second kind. Encoding one year's figure -- or worse, a round number close to
    none of them -- silently applies it to every filing year, and the error is
    invisible because the value looks like a law-fixed constant. The registry
    shipped exactly that: a flat 15000 that matched no ejercicio at all.

    Attributes:
        value: The cap amount in euros for this span.
        valid_from: First date the amount applies.
        valid_to: Last date, inclusive. Both bounds required and closed, for the
            reasons :class:`~core.validity_window.ValidityWindow` documents.
    """

    value: Decimal = Field(ge=Decimal("0"))
    valid_from: date
    valid_to: date

    @property
    def window(self) -> ValidityWindow:
        """Return the closed span this amount applies over.

        Returns:
            The :class:`~core.validity_window.ValidityWindow` the bounds describe.
        """
        return ValidityWindow(valid_from=self.valid_from, valid_to=self.valid_to)

    @model_validator(mode="after")
    def _span_is_coherent(self) -> StatutoryCapAmount:
        _ = self.window
        return self


class ProportionalityRule(_ProportionalityStrictFrozenModel):
    """Deductibility and proportionality rule for one spending category.

    Attributes:
        kind: One of :class:`ProportionalityKind`.
        fixed_pct: Required when ``kind`` is
            :attr:`ProportionalityKind.FIXED_PERCENTAGE`; otherwise
            must be ``None``.
        default_ratio: Optional default usage ratio; only valid for
            usage-ratio kinds.
        statutory_multiplier: Optional statutory factor applied on
            top of the operator-chosen usage ratio. Only valid for
            usage-ratio kinds. The canonical example is the LIRPF
            Art. 30.2 rule 5 (Ley 6/2017, BOE-A-2017-12544) 0.30
            multiplier applied to suministros (utility) costs of
            the habitual vivienda when the operator deducts under
            estimacion directa: ``effective_deductible_pct =
            operator_chosen_ratio * statutory_multiplier``. When
            ``None`` no statutory factor is applied (equivalent to
            ``Decimal("1")``); the operator's chosen ratio is the
            effective deductible percentage.
        statutory_cap_eur_per_day: Daily statutory cap; only valid
            for :attr:`ProportionalityKind.STATUTORY_CAP`.
        statutory_cap_eur: Generic statutory cap amount; only valid
            for :attr:`ProportionalityKind.STATUTORY_CAP` and must
            be paired with :attr:`statutory_cap_period`.
        statutory_cap_period: :class:`StatutoryCapPeriod` that the
            generic cap applies over; required when
            :attr:`statutory_cap_eur` is set.
        statutory_cap_variants: Daily statutory caps selected by a
            legally relevant condition.
        statutory_cap_schedule: Dated amounts for a cap the law re-fixes each
            ejercicio. Mutually exclusive with the fixed
            :attr:`statutory_cap_eur`: a cap is either law-fixed or
            year-referenced, never both.
        citations: At least one :class:`CategoryCitation` proving
            the rule.
        notes: Translation key for the notes describing the rule.
    """

    kind: ProportionalityKind
    fixed_pct: UnitProportion | None = None
    default_ratio: UnitProportion | None = None
    statutory_multiplier: UnitProportion | None = None
    statutory_cap_eur_per_day: Decimal | None = Field(default=None, ge=Decimal("0"))
    statutory_cap_eur: Decimal | None = Field(default=None, ge=Decimal("0"))
    statutory_cap_period: StatutoryCapPeriod | None = None
    statutory_cap_variants: tuple[StatutoryCapVariant, ...] = Field(default_factory=tuple)
    statutory_cap_schedule: tuple[StatutoryCapAmount, ...] = Field(default_factory=tuple)
    citations: tuple[CategoryCitation, ...] = Field(default_factory=tuple)
    notes: tr = Field(description="Translation key for the notes describing the rule.")

    @model_validator(mode="after")
    def _validate_shape(self) -> ProportionalityRule:
        if not self.citations:
            raise CategoryValidationError("proportionality rules require at least one citation")
        _require_translatable_text(self.notes, "proportionality rule notes")
        self._validate_fixed_percentage_invariants()
        self._validate_usage_ratio_invariants()
        if self.kind is ProportionalityKind.STATUTORY_CAP:
            self._validate_statutory_cap_invariants()
        else:
            self._reject_statutory_cap_fields_outside_cap_kind()
        return self

    def _validate_fixed_percentage_invariants(self) -> None:
        """``fixed_pct`` is required for FIXED_PERCENTAGE rules and forbidden elsewhere."""
        if self.kind is ProportionalityKind.FIXED_PERCENTAGE and self.fixed_pct is None:
            raise CategoryValidationError("fixed_percentage rules require fixed_pct")
        if self.kind is not ProportionalityKind.FIXED_PERCENTAGE and self.fixed_pct is not None:
            raise CategoryValidationError("fixed_pct is only valid for fixed_percentage rules")

    def _validate_usage_ratio_invariants(self) -> None:
        """``default_ratio`` and ``statutory_multiplier`` are only valid on usage-ratio rules."""
        is_usage_ratio = self.kind in {
            ProportionalityKind.USAGE_RATIO_HOME_AREA,
            ProportionalityKind.USAGE_RATIO_PERSONAL,
        }
        if not is_usage_ratio and self.default_ratio is not None:
            raise CategoryValidationError("default_ratio is only valid for usage_ratio rules")
        if not is_usage_ratio and self.statutory_multiplier is not None:
            raise CategoryValidationError(
                "statutory_multiplier is only valid for usage_ratio rules",
            )

    def _validate_statutory_cap_invariants(self) -> None:
        """STATUTORY_CAP rules require exactly one cap mode and a coherent (eur, period) pair."""
        has_daily_cap = self.statutory_cap_eur_per_day is not None
        has_scheduled_cap = bool(self.statutory_cap_schedule)
        has_variant_caps = bool(self.statutory_cap_variants)
        # A bare period is only a cap MODE of its own when nothing else claims it.
        # A dated schedule and an annual variant set both legitimately declare the
        # period the per-person amount applies over, and counting that as a second
        # mode would refuse two shapes the law actually uses.
        has_generic_cap = self.statutory_cap_eur is not None or (
            self.statutory_cap_period is not None and not has_scheduled_cap and not has_variant_caps
        )
        if not (has_daily_cap or has_generic_cap or has_variant_caps or has_scheduled_cap):
            raise CategoryValidationError("statutory_cap rules require a cap amount")
        mode_count = sum((has_daily_cap, has_generic_cap, has_variant_caps, has_scheduled_cap))
        if mode_count > 1:
            raise CategoryValidationError("statutory cap rules must use one cap mode")
        if has_scheduled_cap:
            if self.statutory_cap_period is None:
                raise CategoryValidationError("statutory_cap_schedule requires statutory_cap_period")
            self._reject_contradictory_scheduled_caps()
        elif has_variant_caps:
            # Annual variants already required the period above; a daily variant set
            # needs none, and neither shape carries a flat statutory_cap_eur.
            pass
        else:
            if self.statutory_cap_eur is None and self.statutory_cap_period is not None:
                raise CategoryValidationError("statutory_cap_period requires statutory_cap_eur")
            if self.statutory_cap_eur is not None and self.statutory_cap_period is None:
                raise CategoryValidationError("statutory_cap_eur requires statutory_cap_period")
        variant_ids = [variant.id for variant in self.statutory_cap_variants]
        if len(set(variant_ids)) != len(variant_ids):
            raise CategoryValidationError("statutory cap variant ids must be unique")
        if self.statutory_cap_variants:
            units = {variant.is_per_day for variant in self.statutory_cap_variants}
            if len(units) > 1:
                raise CategoryValidationError(
                    "statutory cap variants must agree on their unit; mixing a daily variant with "
                    "an annual one leaves the resolver to guess which the rule is capped in",
                )
            if not next(iter(units)) and self.statutory_cap_period is None:
                raise CategoryValidationError(
                    "annual statutory cap variants require statutory_cap_period, which is the "
                    "period the per-person amount applies over",
                )

    def _reject_contradictory_scheduled_caps(self) -> None:
        """Two different amounts covering one filing year is a contradiction.

        Silently taking the first or the last would make the applied cap depend
        on authoring order, which is the class of defect a dated schedule exists
        to remove.
        """
        seen: dict[int, Decimal] = {}
        for amount in self.statutory_cap_schedule:
            for year in amount.window.years():
                if year in seen and seen[year] != amount.value:
                    raise CategoryValidationError(
                        f"statutory_cap_schedule declares two different amounts for {year}: "
                        f"{seen[year]} and {amount.value}",
                    )
                seen[year] = amount.value

    def cap_amount_for_year(self, year: int) -> Decimal | None:
        """Return the statutory cap amount in force for ``year``.

        Returns:
            The scheduled amount covering ``year`` when the cap is
            year-referenced, the flat :attr:`statutory_cap_eur` when it is
            law-fixed, and ``None`` when this rule carries neither.
        """
        for amount in self.statutory_cap_schedule:
            if amount.window.covers_year(year):
                return amount.value
        return self.statutory_cap_eur if not self.statutory_cap_schedule else None

    def _reject_statutory_cap_fields_outside_cap_kind(self) -> None:
        """Every statutory-cap field is forbidden on non-STATUTORY_CAP kinds."""
        if self.statutory_cap_eur_per_day is not None:
            raise CategoryValidationError("statutory_cap_eur_per_day is only valid for statutory_cap rules")
        if self.statutory_cap_eur is not None:
            raise CategoryValidationError("statutory_cap_eur is only valid for statutory_cap rules")
        if self.statutory_cap_period is not None:
            raise CategoryValidationError("statutory_cap_period is only valid for statutory_cap rules")
        if self.statutory_cap_variants:
            raise CategoryValidationError("statutory_cap_variants are only valid for statutory_cap rules")
        if self.statutory_cap_schedule:
            raise CategoryValidationError("statutory_cap_schedule is only valid for statutory_cap rules")


def effective_usage_ratio(rule: ProportionalityRule, chosen_ratio: Decimal) -> Decimal:
    """Return the legally-effective deductible percentage for ``chosen_ratio``.

    Applies the rule's ``statutory_multiplier`` on top of the operator-
    chosen usage ratio. Only meaningful for usage-ratio kinds; raises
    when called on a non-usage-ratio rule (the caller is responsible
    for routing rules to the right evaluator).

    Args:
        rule: A :class:`ProportionalityRule` of a usage-ratio kind.
        chosen_ratio: The operator's stored usage ratio (typically
            derived from censo ``office_m2 / total_m2`` for HOME_AREA
            kinds, or a personal-use proportion for PERSONAL kinds).

    Returns:
        ``chosen_ratio * (rule.statutory_multiplier or Decimal("1"))``.

    Raises:
        CategoryValidationError: When ``rule.kind`` is not a usage-ratio kind.
    """
    if rule.kind not in {
        ProportionalityKind.USAGE_RATIO_HOME_AREA,
        ProportionalityKind.USAGE_RATIO_PERSONAL,
    }:
        raise CategoryValidationError(
            f"effective_usage_ratio is only valid for usage_ratio rules; got {rule.kind}",
        )
    multiplier = rule.statutory_multiplier if rule.statutory_multiplier is not None else Decimal("1")
    return chosen_ratio * multiplier
