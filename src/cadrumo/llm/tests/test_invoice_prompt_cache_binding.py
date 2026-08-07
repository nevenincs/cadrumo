"""The compiled prompt must reach both the cache key and the provenance stamp.

Two silent-wrong-answer paths, both closed here.

**The cache key.** The prompt is now compiled from registry-resolved rates, so
two reads under different filing periods are different requests. If the compiled
text did not participate in the key, a response cached under one year's rates
would be served after a revision moved them -- a wrong figure returned with
``cache_hit`` set and nothing to distinguish it from a fresh read.

**The provenance stamp.** ``decided_by`` is the only durable record of how a
figure was reached. Naming only the model leaves "under which rates was this
read?" unanswerable, which is the same class of defect as a stamp that says
``local`` for an off-host read: it answers the audit question confidently and
incompletely.

Model-free and network-free: no transport is constructed, only a key derivation
and a string property.

See Also:
    :meth:`~adapters.outbound.llm.LLMCache.build_key`
        The derivation under test.
    :class:`~llm._invoice_extraction_prompt.CompiledInvoiceExtractionPrompt`
        Carrier of the rate-provenance token the stamp folds in.
"""

from __future__ import annotations

import pytest

from ...adapters.outbound.llm import LLMCache
from ...core import Period
from ...core.time import now
from ...domain.transactions import DecisionProvenance
from .._evidence_draft_text import TextInvoiceFieldExtractor
from .._evidence_draft_vision import LocalVisionInvoiceFieldExtractor
from .._invoice_extraction_prompt import build_invoice_extraction_prompt
from .._models import LLMProvider, LLMRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_ANNUAL_2026 = Period.from_year_and_code(2026, "0A")
_Q4_2024 = Period.from_year_and_code(2024, "4T")


class TestTheCompiledPromptAlreadyParticipatesInTheCacheKey:
    """No new key component was added: ``build_key`` already hashes ``request.prompt``.

    Duplicating it would have produced a second, redundant path to the same
    guarantee -- the fragmentation this campaign exists to close -- so the
    correct action was to PROVE the existing binding rather than add to it. The
    binding is load-bearing precisely because it is invisible: nothing in the
    prompt-compilation code names the cache.
    """

    def test_two_periods_compile_to_two_distinct_cache_keys(self) -> None:
        cache = LLMCache()
        annual = build_invoice_extraction_prompt(period=_ANNUAL_2026)
        q4 = build_invoice_extraction_prompt(period=_Q4_2024)

        assert annual.text != q4.text

        annual_key = cache.build_key(
            LLMRequest(prompt=annual.text),
            LLMProvider.LOCAL,
            "vision-model",
        )
        q4_key = cache.build_key(
            LLMRequest(prompt=q4.text),
            LLMProvider.LOCAL,
            "vision-model",
        )

        assert annual_key.prompt_hash != q4_key.prompt_hash

    def test_the_same_compiled_prompt_derives_the_same_key(self) -> None:
        """The key is deterministic, so an unchanged registry still hits cache."""
        cache = LLMCache()
        text = build_invoice_extraction_prompt(period=_ANNUAL_2026).text

        first = cache.build_key(LLMRequest(prompt=text), LLMProvider.LOCAL, "vision-model")
        second = cache.build_key(LLMRequest(prompt=text), LLMProvider.LOCAL, "vision-model")

        assert first == second

    def test_changing_one_enumerated_rate_moves_the_key(self) -> None:
        """The discriminating control: the binding reacts to the RATES specifically.

        The nudge edits exactly the substring the registry produced, so a pass
        here cannot be explained by the key reacting to prompt length or to some
        other component. ``LLMRequest`` trims its prompt, so a whitespace-only
        nudge would be normalised away and prove nothing.
        """
        cache = LLMCache()
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)
        enumerated = ", ".join(format(pct.normalize(), "f") for pct in compiled.iva_rate_pcts)
        assert enumerated in compiled.text

        baseline = cache.build_key(LLMRequest(prompt=compiled.text), LLMProvider.LOCAL, "m")
        restated = cache.build_key(
            LLMRequest(prompt=compiled.text.replace(enumerated, f"{enumerated}, 19", 1)),
            LLMProvider.LOCAL,
            "m",
        )

        assert baseline.prompt_hash != restated.prompt_hash


class TestTheProvenanceStampNamesTheRatesTheReadUsed:
    """A stamp that cannot answer "under which rates?" will mislead an audit."""

    def test_the_vision_stamp_carries_the_period_and_the_prompt_fingerprint(self) -> None:
        extractor = LocalVisionInvoiceFieldExtractor(model="qwen2.5vl:3b", period=_ANNUAL_2026)
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)

        assert extractor.decided_by == f"llm:local-vision:qwen2.5vl:3b:rates-{compiled.rate_provenance}"
        assert "2026-0A" in extractor.decided_by

    def test_the_text_stamp_carries_it_too(self) -> None:
        extractor = TextInvoiceFieldExtractor(model="some-text-model", period=_ANNUAL_2026)
        compiled = build_invoice_extraction_prompt(period=_ANNUAL_2026)

        assert extractor.decided_by == f"llm:text-extract:some-text-model:rates-{compiled.rate_provenance}"

    def test_a_different_rate_period_produces_a_different_stamp(self) -> None:
        """The discriminating control: the stamp moves when the rates move."""
        annual = LocalVisionInvoiceFieldExtractor(model="m", period=_ANNUAL_2026)
        q4 = LocalVisionInvoiceFieldExtractor(model="m", period=_Q4_2024)

        assert annual.decided_by != q4.decided_by

    def test_the_transport_half_is_still_derived_from_the_provider(self) -> None:
        """The pre-existing property survives the extension."""
        local = LocalVisionInvoiceFieldExtractor(model="m", period=_ANNUAL_2026)
        cloud = LocalVisionInvoiceFieldExtractor(
            model="m",
            provider=LLMProvider.ANTHROPIC,
            period=_ANNUAL_2026,
        )

        assert local.decided_by.startswith("llm:local-vision:")
        assert not cloud.decided_by.startswith("llm:local-vision:")

    def test_the_extended_stamp_still_persists_as_a_decision_provenance(self) -> None:
        """It must survive the persisted record's own validator and its 128-char bound.

        Asserted by constructing the real typed record rather than by re-stating
        the shape rule here: a longer stamp that the record refuses is a broken
        stamp, and the record is the authority on that.
        """
        extractor = LocalVisionInvoiceFieldExtractor(
            model="claude-haiku-4-5-20251001",
            provider=LLMProvider.ANTHROPIC,
            period=_ANNUAL_2026,
        )

        provenance = DecisionProvenance(decided_by=extractor.decided_by, decided_at=now())

        assert provenance.decided_by == extractor.decided_by
