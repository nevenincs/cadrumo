"""Render the invoice-extraction prompt from values an authority already resolved.

The prompt is an ARTEFACT, not a literal: a digit-free template plus values
substituted at render time. This module owns the TEMPLATE and the rendering; it
owns none of the numbers.

Why that matters more here than anywhere else. ``aeat-registry-authority-flow``
forbids inlining an AEAT rate, threshold or regulatory code as a Python literal,
because those values are versioned by filing year plus revision and a literal
bakes one year's law into the call site. A prompt is the least-audited place in
the codebase for such a literal to hide: nothing type-checks it, no gate reads
it, and a stale ``21`` would keep steering a reading model long after the
registry moved.

**So the renderer cannot reach an authority at all.** Every regulatory value
arrives as data, in one frozen
:class:`~application.ledger.invoice_extraction_authority.InvoiceExtractionAuthorityValues` resolved by
:func:`~application.ledger.invoice_extraction_authority.resolve_invoice_extraction_authority_values`. This
package is an adapter over a model transport, and an adapter that looks a rate up
for itself has made itself a second consumer of the calculation authorities.
Removing the reach is a stronger guarantee than remembering not to write ``21``:
the only rate this module can print is one it was handed.

What arrives, and what each part is for:

* IVA rate percentages for the requested :class:`~core.Period` -- every record
  whose effective window OVERLAPS it, because a period is a span and RD-ley
  4/2024 stepped part of the reducido and super-reducido tiers mid-year.
* Retención rate percentages, the RIRPF art. 95 figures.
* The no-printed-tax :class:`~domain.iva.IvaCategory` members, rendered here into
  the prose tokens the model reads.
* The regime mentions RD 1619/2012 art. 6.1 obliges an issuer to print. The
  prompt asks the model to COPY one if printed, never to choose one -- a closed
  list offered as a recognition aid, not as a menu, because selecting from it
  would be the classification this stage does not do.

**The two template scanners deliberately keep their own read** of the vocabulary
they assert is absent. They are checks, not substitutions: a scanner handed its
needle by the same caller that supplied the template could be handed an empty
needle and would then report clean over anything at all.

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

**An identity field is asked for a third time: what assigns it to a party.** Two
tax identifiers on one invoice have the same shape, so an anchor -- which says
only where a number was printed -- cannot say whose it is. The role-evidence key
carries the printed heading or label instead, and it is checked against the
transcription exactly as an anchor is, so a heading the document does not show
is dropped and the identity stays unresolved rather than being assigned on the
reader's own say-so.

**The enumeration is a hint, never a constraint.** Documents in scope are
international; a German invoice prints 19 %, which is not a Spanish registered
rate. The rate line therefore says what Spain registers *and* that a foreign
document may print something else, because a model told "the rate is one of
these" would otherwise coerce 19 to 21 -- fabricating the exact class of figure
the null-over-guess rule exists to prevent.

See Also:
    :data:`~llm.invoice_field_contract.INVOICE_FIELD_CONTRACTS`
        The single field-form declaration whose rows become the field lines.
    :func:`~llm.invoice_field_grounding.ground_extracted_fields`
        The other derivation from that same declaration.
"""

from __future__ import annotations

import re
from decimal import Decimal
from functools import lru_cache
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ..core.models import STRICT_FROZEN_CONFIG
from ..core.period import Period
from ..core.hashing import sha256_hex
from .invoice_field_contract import (
    ANCHOR_KEY_SUFFIX,
    INVOICE_FIELD_CONTRACTS,
    ROLE_EVIDENCE_KEY_SUFFIX,
    InvoiceFieldContract,
    anchor_key_for_field,
    role_evidence_key_for_field,
)
from .models import PromptDefinition, PromptRegistry

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable

    from ..application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
    from ..domain.iva.schema import IvaCategory

__all__ = [
    "INVOICE_EXTRACTION_PROMPT_ID",
    "INVOICE_EXTRACTION_PROMPT_VERSION",
    "PROMPT_TEMPLATE",
    "CompiledInvoiceExtractionPrompt",
    "build_invoice_extraction_prompt",
    "default_extraction_period",
    "invoice_extraction_prompt_registry",
    "render_invoice_extraction_prompt",
    "selected_invoice_field_contracts",
    "template_numeric_literals",
    "template_unsourced_legend_phrases",
]

_FINGERPRINT_LENGTH: Final[int] = 12

INVOICE_EXTRACTION_PROMPT_ID: Final[str] = "ledger-invoice-extraction"
"""Registry id of the pre-substitution extraction template."""

INVOICE_EXTRACTION_PROMPT_VERSION: Final[int] = 2
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

Whose identifier is whose:
- An invoice prints two tax identifiers that look alike, so the number itself \
never says which party it belongs to. For each identity field below, return a \
third key named after it with the suffix "{role_evidence_suffix}".
{role_evidence_lines}
- Copy that text EXACTLY as printed. Never write what you decided; write what the \
document shows. If the document shows nothing that assigns the identifier to that \
party, the key is null -- which is always better than a guess.

Rates:
- IVA rates registered in Spain for this period: {iva_rates}.
- Withholding (retencion) rates fixed by Spanish law: {retencion_rates}. Most \
invoices withhold nothing; then both retencion fields are null. It is printed as \
a deduction, so it may appear negative or in parentheses.
- A document issued outside Spain may print a rate on neither list. Copy the \
printed rate; never move it onto a listed one.
- Some documents carry no tax at all ({zero_cuota_reasons}). Then the rate and \
the tax amount are both null. Never supply a rate the document does not print.

Regime wording:
- Spanish law makes an issuer PRINT a set phrase when a special regime applies. \
If one of these appears, copy it into regime_legend exactly as printed: \
{regime_legends}.
- Copy only what is printed. If none appears, regime_legend is null. Never pick \
the closest phrase, and never write one the document does not show.

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
    :class:`~llm.PromptRegistry` already stores -- so it is
    registered there rather than reachable only as a module constant. The
    compiler then asks the registry for its template instead of closing over one,
    which is what lets the id and version travel onto the compiled artefact.

    Cached because the registered definition is immutable: rebuilding it per call
    would mint an equal object and lose the identity a caller can compare.

    Returns:
        :class:`~llm.PromptRegistry`: A registry carrying the
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
    """Return the period a reader falls back to when the caller names none.

    Delegates to
    :func:`~application.ledger.invoice_extraction_authority.default_invoice_extraction_period` rather than
    re-deriving the fallback. Which coordinate an unbound document is read
    against is a decision, and a decision with two homes is a decision that will
    eventually be made two ways.

    Returns:
        :class:`~core.Period`: The current civil year's annual period.
    """
    from ..application.ledger.invoice_extraction_authority import default_invoice_extraction_period

    return default_invoice_extraction_period()


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


def _regime_legends(phrases: Iterable[str]) -> str:
    """Return the mandated regime mentions as one quoted, comma-joined line.

    Substituted from the values handed in rather than restated here, for the same
    reason the rates are: the phrases are fixed by RD 1619/2012 art. 6.1 and a
    copy in the template would be a second home for a legal vocabulary, drifting
    silently the moment the regulation's list moves.

    Quoted, because the model is being told to copy a phrase and the quotes mark
    where each one starts and ends -- a bare comma-joined line of Spanish prose
    gives a small model no boundary to copy between.
    """
    return ", ".join(f'"{phrase}"' for phrase in phrases)


def template_unsourced_legend_phrases(template: str | None = None) -> tuple[str, ...]:
    """Return any mandated legend phrase hardcoded in ``template``.

    The literal scan's counterpart on the prose axis. A numeric scan cannot see
    this class of drift at all: a statutory phrase written into the template is
    not a digit, so the rate gate reports clean over it while a second, silently
    diverging copy of the legal vocabulary ships inside the prompt.

    Args:
        template: Template text to scan. ``None`` reads the REGISTERED template
            at call time, never a snapshot bound at import -- the same trap the
            numeric scan was caught in, and the reason that gate now points at
            the artefact that actually ships rather than at a module constant.

    Returns:
        The phrases found hardcoded, in declaration order. Empty is the passing
        state, because the compiler substitutes them from the one declaration.
    """
    from ..domain.iva.regime_legend import regime_legend_phrases

    scanned = (
        invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID).template
        if template is None
        else template
    )
    folded = scanned.casefold()
    return tuple(phrase for phrase in regime_legend_phrases() if phrase.casefold() in folded)


def _zero_cuota_reasons(categories: Iterable[IvaCategory]) -> str:
    """Return the no-printed-tax category tokens as one comma-joined line.

    Substituted from the members handed in rather than listed here, so a category
    the law moves in or out of the set moves in the prompt too. The members
    arrive typed and are rendered to prose only here, which keeps the closed-set
    fact and its presentation apart.

    The resolver reads that set off the paper's own authority rather than the
    M303 cuota-less set, which would be the closest available answer and the
    wrong one: that set excludes the received side of inversión del sujeto pasivo
    *because* it bears a self-assessed 303 cuota, while the invoice for it
    repercutes nothing at all.
    """
    return ", ".join(sorted(category.value.replace("_", " ") for category in categories))


def selected_invoice_field_contracts(
    fields: Collection[str] | None,
) -> tuple[InvoiceFieldContract, ...]:
    """Return the contracts a caller selected, in declaration order.

    The one place a field selection becomes contracts, so the three prompt
    blocks that enumerate fields cannot disagree about what the prompt is
    asking for. A block emitting a different subset from its siblings would ask
    the model for a key the skeleton never lists, or list a key the Fields block
    never explains.

    Declaration order is preserved rather than the caller's argument order,
    because field ordering is part of what a measurement compares: two arms
    passing the same set differently ordered must get the same prompt, or they
    differ by argument order alone.

    Args:
        fields: The field names to emit, or ``None`` for every declared field.

    Returns:
        The selected contracts, in :data:`INVOICE_FIELD_CONTRACTS` order.

    Raises:
        ValueError: When ``fields`` is empty, or names a field the contract
            declaration does not carry. Refusing is the point. A silently
            dropped name still renders -- just shorter -- and a measurement
            taken against a prompt missing a contract nobody noticed is worse
            than no measurement. An empty selection is refused on the same
            terms the period path fails closed on an empty rate set: a prompt
            asking for nothing is not a smaller prompt, it is a broken one.
    """
    if fields is None:
        return INVOICE_FIELD_CONTRACTS
    requested = frozenset(fields)
    declared = _declared_field_names()
    if not requested:
        raise ValueError(
            "an invoice extraction prompt must ask for at least one field; "
            f"pass None for the full set, or name any of: {', '.join(declared)}",
        )
    unknown = sorted(requested - set(declared))
    if unknown:
        raise ValueError(
            f"no invoice field contract is declared for {', '.join(unknown)}; "
            f"accepted fields are: {', '.join(declared)}",
        )
    return tuple(contract for contract in INVOICE_FIELD_CONTRACTS if contract.field_name in requested)


def _declared_field_names() -> tuple[str, ...]:
    """Return every declared field name, in declaration order."""
    return tuple(contract.field_name for contract in INVOICE_FIELD_CONTRACTS)


def _field_lines(contracts: tuple[InvoiceFieldContract, ...]) -> str:
    return "\n".join(
        f"- {contract.field_name}: {contract.concept}; {contract.form_instruction}." for contract in contracts
    )


def _role_evidence_lines(contracts: tuple[InvoiceFieldContract, ...]) -> str:
    """Return the per-identity-field role-evidence guidance, one line each.

    Derived from the contract declaration like :func:`_field_lines`, so the set
    of fields asked to evidence a role is the set the payload schema and the
    grounding stage agree on, never a third hand-maintained list.
    """
    return "\n".join(
        f"- {role_evidence_key_for_field(contract.field_name)}: {contract.role_evidence_instruction}."
        for contract in contracts
        if contract.carries_role_evidence
    )


def _json_skeleton(contracts: tuple[InvoiceFieldContract, ...]) -> str:
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
    #
    # An identity field's role-evidence key sits third in the same adjacent run,
    # for the same reason: the value, where it was printed, and what assigns it
    # to a party are one thought about one field, and a small model keeps them
    # together when they are written together.
    def _keys(contract: InvoiceFieldContract) -> str:
        lines = [
            f'  "{contract.field_name}": <string or null>',
            f'  "{anchor_key_for_field(contract.field_name)}": <string or null>',
        ]
        if contract.carries_role_evidence:
            lines.append(f'  "{role_evidence_key_for_field(contract.field_name)}": <string or null>')
        return ",\n".join(lines)

    body = ",\n".join(_keys(contract) for contract in contracts)
    return "{\n" + body + "\n}"


def render_invoice_extraction_prompt(
    *,
    values: InvoiceExtractionAuthorityValues,
    fields: Collection[str] | None = None,
) -> CompiledInvoiceExtractionPrompt:
    """Render the extraction prompt from already-resolved authority ``values``.

    The whole of this module's regulatory content arrives through this one
    argument. Nothing here reads a rate table, a parameter file or a category
    set, so the prompt cannot carry a number the application layer did not
    resolve for the period it names.

    Args:
        values: The regulatory values to substitute, resolved by
            :func:`~application.ledger.invoice_extraction_authority.resolve_invoice_extraction_authority_values`
            against a law-determined period.
        fields: The field names the prompt should ask for, or ``None`` for
            every declared field. A named field the contract declaration does
            not carry refuses rather than being dropped, because a silently
            shorter prompt still renders and a measurement taken against one
            missing a contract nobody noticed is worse than no measurement.

    Returns:
        :class:`CompiledInvoiceExtractionPrompt`: The prompt text plus the
        values that produced it.
    """
    contracts = selected_invoice_field_contracts(fields)
    definition = invoice_extraction_prompt_registry().get(INVOICE_EXTRACTION_PROMPT_ID)
    text = definition.template.format(
        anchor_suffix=ANCHOR_KEY_SUFFIX,
        field_lines=_field_lines(contracts),
        role_evidence_suffix=ROLE_EVIDENCE_KEY_SUFFIX,
        role_evidence_lines=_role_evidence_lines(contracts),
        iva_rates=_join_pcts(values.iva_rate_pcts),
        retencion_rates=_join_pcts(values.retencion_rate_pcts),
        zero_cuota_reasons=_zero_cuota_reasons(values.no_printed_tax_categories),
        regime_legends=_regime_legends(values.regime_legend_phrases),
        json_skeleton=_json_skeleton(contracts),
    )
    return CompiledInvoiceExtractionPrompt(
        text=text,
        period=values.period,
        iva_rate_pcts=values.iva_rate_pcts,
        retencion_rate_pcts=values.retencion_rate_pcts,
        fingerprint=sha256_hex(text.encode("utf-8"))[:_FINGERPRINT_LENGTH],
        template_version=definition.version,
    )


def build_invoice_extraction_prompt(
    *,
    period: Period,
    fields: Collection[str] | None = None,
) -> CompiledInvoiceExtractionPrompt:
    """Resolve ``period``'s authority values and render the prompt from them.

    The convenience shape for a caller holding only a period. It resolves through
    the application layer's compiler and renders; it does not itself know where
    any number comes from. A caller that already holds resolved values -- the
    evidence-reading chain does, and resolves once per document rather than once
    per prompt -- calls :func:`render_invoice_extraction_prompt` directly.

    Args:
        period: Filing period whose in-force values the prompt enumerates. The
            period is the caller's law-determined coordinate, never a stored
            revision id fed back into resolution
            (``aeat-registry-authority-flow``).
        fields: The field names the prompt should ask for, or ``None`` for
            every declared field. Passed through to
            :func:`render_invoice_extraction_prompt` unchanged, so both entry
            points accept a selection on identical terms -- one accepting it
            while the other ignored it would be worse than neither.

    Returns:
        :class:`CompiledInvoiceExtractionPrompt`: The prompt text plus the
        authority values that produced it.

    Raises:
        PeriodError: When ``period`` carries no calendar span, so no rate window
            can be resolved against it.
    """
    from ..application.ledger.invoice_extraction_authority import resolve_invoice_extraction_authority_values

    return render_invoice_extraction_prompt(
        values=resolve_invoice_extraction_authority_values(period=period),
        fields=fields,
    )
