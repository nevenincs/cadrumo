"""Compile the invoice-extraction prompt from the authorities that own its numbers.

The prompt is an ARTEFACT, not a literal: a digit-free template plus values
resolved at compile time from the registry surfaces that already own them.

Why that matters more here than anywhere else. ``aeat-registry-authority-flow``
forbids inlining an AEAT rate, threshold or regulatory code as a Python literal,
because those values are versioned by filing year plus revision and a literal
bakes one year's law into the call site. A prompt is the least-audited place in
the codebase for such a literal to hide: nothing type-checks it, no gate reads
it, and a stale ``21`` would keep steering a reading model long after the
registry moved.

Where each number comes from:

* IVA rates: :func:`~domain.iva.load_iva_rate_table`, the dated legal-grade
  authority over ``registry/aeat/iva/rates.toml``. Every record whose effective
  window OVERLAPS the requested :class:`~core.Period` is enumerated, not the
  single record in force on one chosen day -- RD-ley 4/2024 stepped part of the
  reducido and super-reducido tiers mid-year, so a one-date read would omit a
  rate the period's documents genuinely print.
* Retención rates: :func:`~domain.transactions.statutory_activity_retencion_rates`,
  the RIRPF art. 95 parameters under ``registry/aeat/legal/``.
* The no-printed-tax vocabulary: :data:`~domain.iva.NO_PRINTED_TAX_IVA_CATEGORIES`,
  derived from the canonical :class:`~domain.iva.IvaCategory` closed set.

**Shape is a design constraint.** The target is the lowest-bound vision-capable
model, so the prompt is enumerated bullets and per-field micro-guidance, never
prose. A closed enumeration turns an inference problem into a selection problem
and is cheaper than any explanation of it.

**Every field is asked for twice: once as a value, once as an anchor.** The value
arrives in the form its contract row declares; the anchor is the substring exactly
as the document printed it. Keeping both is what lets a later check verify that
the anchor occurs in the document AND that the value equals the deterministic
parse of the anchor -- a value with no anchor can only be taken on trust. Where
the two would be byte-identical the check is weaker, so the contract deliberately
keeps them distinct: ``IVA (21%)`` yields the value ``21`` and the anchor ``21%``.

**The enumeration is a hint, never a constraint.** Documents in scope are
international; a German invoice prints 19 %, which is not a Spanish registered
rate. The rate line therefore says what Spain registers *and* that a foreign
document may print something else, because a model told "the rate is one of
these" would otherwise coerce 19 to 21 -- fabricating the exact class of figure
the null-over-guess rule exists to prevent.

See Also:
    :data:`~llm._invoice_field_contract.INVOICE_FIELD_CONTRACTS`
        The single field-form declaration whose rows become the field lines.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        The other derivation from that same declaration.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ..core import STRICT_FROZEN_CONFIG, Period
from ..core.hashing import sha256_hex
from ._invoice_field_contract import (
    ANCHOR_KEY_SUFFIX,
    INVOICE_FIELD_CONTRACTS,
    anchor_key_for_field,
)
from ._models import PromptDefinition, PromptRegistry

if TYPE_CHECKING:
    from collections.abc import Iterable

__all__ = [
    "INVOICE_EXTRACTION_PROMPT_ID",
    "INVOICE_EXTRACTION_PROMPT_VERSION",
    "PROMPT_TEMPLATE",
    "CompiledInvoiceExtractionPrompt",
    "build_invoice_extraction_prompt",
    "default_extraction_period",
    "invoice_extraction_prompt_registry",
    "template_numeric_literals",
]

_FINGERPRINT_LENGTH: Final[int] = 12

INVOICE_EXTRACTION_PROMPT_ID: Final[str] = "ledger-invoice-extraction"
"""Registry id of the pre-substitution extraction template."""

INVOICE_EXTRACTION_PROMPT_VERSION: Final[int] = 1
"""Version of the registered template.

Bumped when the template's INSTRUCTIONS change -- a new field, a changed rule, a
different response shape -- never when the values substituted into it move. The
two are different facts and are carried separately:
:attr:`CompiledInvoiceExtractionPrompt.template_version` says which instructions
were issued, and :attr:`CompiledInvoiceExtractionPrompt.fingerprint` says which
compiled text a model actually received. An integer cannot express the second,
which is why registering the template does not replace the fingerprint.
"""

# The only digits the template may carry: a standards identifier, not a
# regulatory value. Allowlisted as a whole token with its reason stated, per
# `aeat-quality-gates` -- keyed by token, never by line number.
_NON_NUMERIC_TOKEN_ALLOWLIST: Final[tuple[str, ...]] = ("ISO-4217",)

_NUMERIC_LITERAL_RE: Final[re.Pattern[str]] = re.compile(r"\d+(?:[.,]\d+)?")

PROMPT_TEMPLATE: Final[str] = """\
You are reading one invoice document. It may be written in any language and laid \
out in any way. Identify each field by what it MEANS, not by matching a label.

Rules:
- Copy each value EXACTLY as printed. Never calculate, infer, estimate, convert, \
translate, reformat or guess any value.
- If a field is not printed in the document, its value is null. Emitting null is \
always correct when you are not certain; never substitute a plausible value for a \
missing one.
- Change a printed value only where that field's own rule below says so.

Fields:
{field_lines}

Anchors:
- For every field above, also return a second key named after it with the suffix \
"{anchor_suffix}", holding that value's substring copied EXACTLY as printed in the \
document -- keeping any percent sign, currency symbol, separators and spacing the \
field's own rule told you to drop.
- The field carries the value; its anchor carries the printed form. When a field is \
null its anchor is null too.
- Never write an anchor that does not appear in the document.

Rates:
- VAT/IVA rates registered in Spain for this period: {iva_rates}.
- Withholding (retencion) rates fixed by Spanish law: {retencion_rates}. Most \
invoices withhold nothing; then both retencion fields are null. It is printed as \
a deduction, so it may appear negative or in parentheses.
- A document issued outside Spain may print a rate on neither list. Copy the \
printed rate; never move it onto a listed one.
- Some documents carry no tax at all ({zero_cuota_reasons}). Then the rate and \
the tax amount are both null. Never supply a rate the document does not print.

Return ONLY one JSON object with exactly these keys (no other text):
{json_skeleton}
"""


class CompiledInvoiceExtractionPrompt(BaseModel):
    """One compiled prompt together with the authority values that produced it.

    The compiled values are carried alongside the text rather than only baked
    into it, so a provenance stamp can answer "under which rates was this read?"
    without re-parsing prose.

    Attributes:
        text: The prompt as the model receives it.
        period: The filing period the rates were resolved for.
        iva_rate_pcts: Every registered Spanish IVA percentage whose effective
            window overlaps ``period``, ascending.
        retencion_rate_pcts: Every RIRPF art. 95 retención percentage, ascending.
        fingerprint: Short content hash of :attr:`text`. Two prompts compiled
            from different registry values differ here, which is what makes the
            stamp discriminating.
        template_version: Which registered template version issued the
            instructions. Distinct from :attr:`fingerprint`, which moves whenever
            any substituted value moves; this moves only when the instructions
            themselves change.
    """

    model_config = STRICT_FROZEN_CONFIG

    text: str = Field(min_length=1)
    period: Period
    template_version: int = Field(ge=1)
    iva_rate_pcts: tuple[Decimal, ...]
    retencion_rate_pcts: tuple[Decimal, ...]
    fingerprint: str = Field(min_length=_FINGERPRINT_LENGTH, max_length=_FINGERPRINT_LENGTH)

    @property
    def rate_provenance(self) -> str:
        """Return the compact ``<year>-<code>-<fingerprint>`` rate-provenance token.

        Returns:
            The token a reader folds into its ``decided_by`` stamp.
        """
        return f"{self.period.filing_year}-{self.period.code}-{self.fingerprint}"


@lru_cache(maxsize=1)
def invoice_extraction_prompt_registry() -> PromptRegistry:
    """Return the registry holding the pre-substitution extraction template.

    The template is versioned prompt metadata, which is exactly what
    :class:`~adapters.outbound.llm.PromptRegistry` already stores -- so it is
    registered there rather than reachable only as a module constant. The
    compiler then asks the registry for its template instead of closing over one,
    which is what lets the id and version travel onto the compiled artefact.

    Cached because the registered definition is immutable: rebuilding it per call
    would mint an equal object and lose the identity a caller can compare.

    Returns:
        :class:`~adapters.outbound.llm.PromptRegistry`: A registry carrying the
        extraction template at :data:`INVOICE_EXTRACTION_PROMPT_VERSION`.
    """
    registry = PromptRegistry()
    registry.register(
        PromptDefinition(
            id=INVOICE_EXTRACTION_PROMPT_ID,
            version=INVOICE_EXTRACTION_PROMPT_VERSION,
            template=PROMPT_TEMPLATE,
            expected_output_schema=None,
            description=(
                "Read one invoice document into typed fields, each beside the verbatim printed anchor it was read from."
            ),
        ),
    )
    return registry


def default_extraction_period() -> Period:
    """Return the annual period a reader falls back to when the caller names none.

    A document arriving for reading may not yet be bound to a filing period, so
    the reader needs a coordinate to resolve rates against. The current civil
    year's annual period (``0A``) is the honest default: it is derived from the
    canonical civil-date authority (:func:`~core.time.today_madrid`) rather than
    guessed, and it spans the whole year, so its enumeration is the UNION of
    every rate in force at any point in it -- never a mid-year window that would
    omit a rate a document legitimately prints.

    A caller that knows the document's period passes it explicitly and gets a
    narrower, more useful enumeration.

    Returns:
        :class:`~core.Period`: The current civil year's annual period.
    """
    from ..core.time import today_madrid

    return Period.from_year_and_code(today_madrid().year, "0A")


def template_numeric_literals(template: str | None = None) -> tuple[str, ...]:
    """Return every numeric literal in ``template``, ignoring allowlisted tokens.

    Exposed rather than inlined in the gate so the gate asserts a property of
    production code instead of re-implementing the scan it is checking.

    Args:
        template: Template text to scan. ``None`` reads the REGISTERED template
            AT CALL TIME rather than defaulting to it in the signature: a
            default argument is evaluated once at import, so the scan would hold
            a snapshot and keep reporting clean over a template that had since
            gained a literal -- which a mutation probe caught it doing. Reading
            it from the registry rather than from the constant keeps the scan
            pointed at the text the compiler will actually use.

    Returns:
        The numeric literals found, in order. Empty is the passing state.
    """
    scanned = (
        invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID).template
        if template is None
        else template
    )
    for token in _NON_NUMERIC_TOKEN_ALLOWLIST:
        scanned = scanned.replace(token, "")
    return tuple(match.group(0) for match in _NUMERIC_LITERAL_RE.finditer(scanned))


def _format_pct(value: Decimal) -> str:
    """Render a percentage without a trailing zero tail (``7.5`` and ``21``)."""
    normalised = value.normalize()
    text = format(normalised, "f")
    return text


def _join_pcts(values: Iterable[Decimal]) -> str:
    return ", ".join(_format_pct(value) for value in values)


def _iva_rate_pcts_for(period: Period) -> tuple[Decimal, ...]:
    """Return every registered Spanish IVA percentage overlapping ``period``.

    Raises:
        IvaCatalogueError: When the bundled rate registry cannot be read.
    """
    from ..domain.iva import EUMemberState, load_iva_rate_table

    start = period.start_date
    end = period.end_date
    overlapping = {
        record.pct
        for record in load_iva_rate_table().get(EUMemberState.ES, ())
        if record.effective_from <= end and (record.effective_until is None or record.effective_until >= start)
    }
    return tuple(sorted(overlapping))


def _retencion_rate_pcts() -> tuple[Decimal, ...]:
    """Return every RIRPF art. 95 retención rate as a percentage, ascending.

    The registry stores these as fractions (``0.15``) because that is how a
    transaction carries them; a printed invoice states the percentage, so the
    prompt does too.

    Raises:
        TransactionValidationError: When the registry parameters cannot be read.
    """
    from ..domain.transactions import statutory_activity_retencion_rates

    return tuple(sorted(rate * Decimal("100") for rate in statutory_activity_retencion_rates()))


def _zero_cuota_reasons() -> str:
    """Return the no-printed-tax category tokens as one comma-joined line.

    Derived from :data:`~domain.iva.NO_PRINTED_TAX_IVA_CATEGORIES` rather than
    listed here, so a category the law moves in or out of the set moves in the
    prompt too.

    Reading this line off the M303 cuota-less set instead would be the closest
    available answer and the wrong one: that set excludes the received side of
    inversión del sujeto pasivo *because* it bears a self-assessed 303 cuota,
    while the invoice for it repercutes nothing at all. The question the prompt
    asks is about the paper, so it takes the paper's authority.
    """
    from ..domain.iva import NO_PRINTED_TAX_IVA_CATEGORIES

    return ", ".join(sorted(category.value.replace("_", " ") for category in NO_PRINTED_TAX_IVA_CATEGORIES))


def _field_lines() -> str:
    return "\n".join(
        f"- {contract.field_name}: {contract.concept}; {contract.form_instruction}."
        for contract in INVOICE_FIELD_CONTRACTS
    )


def _json_skeleton() -> str:
    # Terse by design: every field's meaning and form is already stated once in
    # the Fields block above, and restating it inside the skeleton doubles the
    # prompt for a model whose context budget is the binding constraint.
    #
    # The anchor key is listed beside its field rather than in a nested object or
    # a second block. Both alternatives cost fewer characters and were rejected:
    # the design target is the lowest-bound vision-capable model, which pairs a
    # value with its anchor most reliably when the two keys are adjacent and both
    # hold a flat string. A nested `{"value": ..., "anchor": ...}` moves the one
    # relationship that must not drift behind a level of structure that small
    # models routinely flatten or drop.
    body = ",\n".join(
        f'  "{contract.field_name}": <string or null>,\n'
        f'  "{anchor_key_for_field(contract.field_name)}": <string or null>'
        for contract in INVOICE_FIELD_CONTRACTS
    )
    return "{\n" + body + "\n}"


def build_invoice_extraction_prompt(*, period: Period) -> CompiledInvoiceExtractionPrompt:
    """Compile the extraction prompt for ``period`` from the registry authorities.

    Args:
        period: Filing period whose in-force rates the prompt enumerates. The
            period is the caller's law-determined coordinate, never a stored
            revision id fed back into resolution
            (``aeat-registry-authority-flow``).

    Returns:
        :class:`CompiledInvoiceExtractionPrompt`: The prompt text plus the
        authority values that produced it.

    Raises:
        PeriodError: When ``period`` carries no calendar span, so no rate window
            can be resolved against it.
    """
    definition = invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID)
    iva_rate_pcts = _iva_rate_pcts_for(period)
    retencion_rate_pcts = _retencion_rate_pcts()
    text = definition.template.format(
        anchor_suffix=ANCHOR_KEY_SUFFIX,
        field_lines=_field_lines(),
        iva_rates=_join_pcts(iva_rate_pcts),
        retencion_rates=_join_pcts(retencion_rate_pcts),
        zero_cuota_reasons=_zero_cuota_reasons(),
        json_skeleton=_json_skeleton(),
    )
    return CompiledInvoiceExtractionPrompt(
        text=text,
        period=period,
        iva_rate_pcts=iva_rate_pcts,
        retencion_rate_pcts=retencion_rate_pcts,
        fingerprint=sha256_hex(text.encode("utf-8"))[:_FINGERPRINT_LENGTH],
        template_version=definition.version,
    )
