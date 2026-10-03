"""CLI consent preflight accepts only the explicit classified flag pair.

The worker owns profile eligibility, source binding and token minting. Local
preflight validates the provider, acknowledgement and stored evidence reference
before submission. These tests preserve its refusal partition, positive control
and localized recovery text without constructing private persistence ports.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer
import yaml

from ....adapters.outbound.llm.consent import OffHostEvidenceReadOutcome, classify_off_host_evidence_read
from ....core.config_support import LLMProvider
from ....core.i18n.render import tr
from .._ledger_evidence_cli import _OFF_HOST_REFUSAL_LOCALE_KEYS, _validate_extract_consent_options

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_LOCALES = ("en", "es", "ca", "hu")
_LOCALES_ROOT = Path(__file__).resolve().parents[3] / "locales"

#: The two outcomes this command answers with something other than a refusal.
_NON_REFUSING = frozenset(
    {
        OffHostEvidenceReadOutcome.ON_HOST_DEFAULT,
        OffHostEvidenceReadOutcome.OFF_HOST_CONSENTED,
    }
)


def _validate(*, provider: LLMProvider | None, acknowledged: bool, evidence_id: str | None = None) -> None:
    """Validate real request flags without opening any private repository."""
    _validate_extract_consent_options(
        evidence_id=evidence_id,
        off_host_provider=provider,
        acknowledged=acknowledged,
    )


def test_the_outcomes_partition_the_enum_with_nothing_left_over() -> None:
    """What makes the new refusal unreachable today, stated rather than assumed.

    Two outcomes proceed and the rest are worded refusals. If those sets stop
    covering the enum, an outcome exists that this command has no answer for --
    which is exactly the condition the refusal guards, and the point at which
    someone has to choose an answer rather than inherit one.
    """
    covered = frozenset(_OFF_HOST_REFUSAL_LOCALE_KEYS) | _NON_REFUSING

    assert covered == frozenset(OffHostEvidenceReadOutcome)


def test_no_outcome_is_both_worded_as_a_refusal_and_allowed_to_proceed() -> None:
    """The two sets are disjoint, so the partition is a partition.

    Without this the test above would still pass if a proceeding outcome were
    also given refusal wording, and which branch won would depend on statement
    order rather than on intent.
    """
    assert not frozenset(_OFF_HOST_REFUSAL_LOCALE_KEYS) & _NON_REFUSING


def test_neither_flag_supplied_accepts_the_on_host_default() -> None:
    """The default request needs no remote consent flags."""
    assert _validate(provider=None, acknowledged=False) is None


@pytest.mark.parametrize(
    ("provider", "acknowledged"),
    [
        (None, True),
        (LLMProvider.LOCAL, True),
        (LLMProvider.LOCAL, False),
        (LLMProvider.ANTHROPIC, False),
    ],
    ids=["acknowledged_without_provider", "local_acknowledged", "local_unacknowledged", "off_host_unacknowledged"],
)
def test_an_incomplete_off_host_request_is_refused(provider: LLMProvider | None, acknowledged: bool) -> None:
    """Each half-formed pair refuses AT THE CONSENT GATE, before reading anything.

    Which refusal is the whole point, not merely that one happened. An outcome
    that fell past the gate would still raise a moment later -- the minting
    path refuses a read that names no evidence -- so asserting only
    ``BadParameter`` would call a fall-through a pass and report the operator
    a missing id when what they actually lack is consent.

    Driven through the real classifier rather than by naming outcomes, so the
    test states what an operator can actually type.
    """
    outcome = classify_off_host_evidence_read(provider=provider, acknowledged=acknowledged)

    with pytest.raises(typer.BadParameter) as raised:
        _validate(provider=provider, acknowledged=acknowledged)

    assert str(raised.value) == tr(_OFF_HOST_REFUSAL_LOCALE_KEYS[outcome])


def test_an_explicit_remote_request_requires_a_stored_evidence_reference() -> None:
    """Acknowledgement alone cannot authorize unnamed evidence."""
    with pytest.raises(typer.BadParameter) as raised:
        _validate(provider=LLMProvider.ANTHROPIC, acknowledged=True, evidence_id=None)

    message = str(raised.value)
    assert "--evidence-id" in message or "evidence" in message.lower()


def test_the_explicit_remote_pair_and_reference_reach_worker_validation() -> None:
    """A complete request is admitted for the worker's independent consent gate."""
    assert _validate(provider=LLMProvider.ANTHROPIC, acknowledged=True, evidence_id="e" * 16) is None


@pytest.mark.parametrize(
    ("provider", "acknowledged", "expected"),
    [
        (None, False, OffHostEvidenceReadOutcome.ON_HOST_DEFAULT),
        (None, True, OffHostEvidenceReadOutcome.ACKNOWLEDGEMENT_WITHOUT_PROVIDER),
        (LLMProvider.LOCAL, True, OffHostEvidenceReadOutcome.PROVIDER_READS_ON_HOST),
        (LLMProvider.ANTHROPIC, False, OffHostEvidenceReadOutcome.PROVIDER_WITHOUT_ACKNOWLEDGEMENT),
        (LLMProvider.ANTHROPIC, True, OffHostEvidenceReadOutcome.OFF_HOST_CONSENTED),
    ],
    ids=lambda value: getattr(value, "name", str(value)),
)
def test_the_classifier_still_produces_the_outcome_this_command_expects(
    provider: LLMProvider | None,
    acknowledged: bool,
    expected: OffHostEvidenceReadOutcome,
) -> None:
    """The premise the partition rests on: which pairs yield which outcome.

    Pinned here because the wording table is keyed by outcome, so a classifier
    that started returning a different outcome for the same pair would silently
    change which sentence an operator sees -- or which branch they land in.
    """
    assert classify_off_host_evidence_read(provider=provider, acknowledged=acknowledged) is expected


@pytest.mark.parametrize("locale", _LOCALES)
def test_the_unclassified_refusal_is_worded_in_this_locale(locale: str) -> None:
    """``tr`` humanises a missing key instead of raising, so absence is silent.

    The refusal names the outcome it received, so the placeholder is part of
    the wording rather than decoration: without it the operator is told a read
    was refused and not what answer caused it.
    """
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    wording = catalogue["cli"]["app"]["ledger"]["evidence"].get("extract_off_host_unclassified", "")

    assert wording.strip(), f"{locale} has no wording for an unclassified consent outcome"
    assert "{outcome}" in wording, f"{locale} does not report which outcome was refused"


@pytest.mark.parametrize("locale", _LOCALES)
def test_every_worded_refusal_has_copy_in_this_locale(locale: str) -> None:
    """The three existing sentences, checked the same way and for the same reason."""
    catalogue = yaml.safe_load((_LOCALES_ROOT / locale / "cli.yml").read_text(encoding="utf-8"))
    evidence = catalogue["cli"]["app"]["ledger"]["evidence"]

    missing = [
        key
        for key in _OFF_HOST_REFUSAL_LOCALE_KEYS.values()
        if not str(evidence.get(key.rsplit(".", 1)[-1], "")).strip()
    ]

    assert not missing, f"{locale} has no wording for: {missing}"
