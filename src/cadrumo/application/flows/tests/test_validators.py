"""Widget-shape validation coverage for the DATE and DECIMAL kinds.

The tests drive ``validate_widget_shape`` from its defining module over real
:class:`FlowPage` records
and assert on the structural outcome — the canonical token, the verdict
``ok`` flag, the i18n message *key*, and the redacted context — never on
localized prose, and never leaking the raw answer into the diagnostic.
The DATE and DECIMAL blank policy mirrors INTEGER: an unconditionally
required page refuses blank, a gated or optional page accepts it.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.flows import CopyRefKind, FlowWidgetKind
from ..definition import CopyRef, FlowCondition, FlowPage
from ..validators import validate_widget_shape

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_GATE = FlowCondition(page_id="earlier", equals="x")


def _copy(ref: str = "flows.test.copy") -> CopyRef:
    return CopyRef(kind=CopyRefKind.LOCALE_KEY, ref=ref)


def _page(
    *,
    widget: FlowWidgetKind,
    required: bool = True,
    visible_when: FlowCondition | None = None,
) -> FlowPage:
    return FlowPage(
        id="probe",
        widget=widget,
        prompt=_copy(),
        required=required,
        visible_when=visible_when,
        answer_type=str,
    )


# ── DATE ─────────────────────────────────────────────────────────────────────


def test_date_accepts_iso_and_canonicalises_to_the_iso_string() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DATE), "2026-01-05")

    assert verdict.ok
    assert canonical == "2026-01-05"


def test_date_strips_surrounding_whitespace_before_parsing() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DATE), "  2026-01-05  ")

    assert verdict.ok
    assert canonical == "2026-01-05"


@pytest.mark.parametrize("raw", ["2026-1-5", "2026-13-01", "2026-02-30", "05/01/2026", "not-a-date"])
def test_date_rejects_non_iso_or_impossible_values(raw: str) -> None:
    """Non-zero-padded, out-of-range, and day-first forms all fail the ISO shape."""
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DATE), raw)

    assert not verdict.ok
    assert verdict.message_key == "flows.errors.invalid_date"
    assert canonical == ""
    # Only the page id rides the context; the raw answer never leaks.
    assert verdict.context == {"page_id": "probe"}


def test_date_rejects_blank_when_unconditionally_required() -> None:
    _canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DATE), "  ")

    assert not verdict.ok
    assert verdict.message_key == "flows.errors.blank_required"


def test_date_accepts_blank_when_optional() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DATE, required=False), "")

    assert verdict.ok
    assert canonical == ""


def test_date_accepts_blank_when_gated() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DATE, visible_when=_GATE), "")

    assert verdict.ok
    assert canonical == ""


# ── DECIMAL ──────────────────────────────────────────────────────────────────


def test_decimal_accepts_and_preserves_significant_trailing_zeros() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DECIMAL), "1.50")

    assert verdict.ok
    # Trailing zeros are significant for an amount: canonicalisation keeps them.
    assert canonical == "1.50"


def test_decimal_strips_surrounding_whitespace() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DECIMAL), "  1.5  ")

    assert verdict.ok
    assert canonical == "1.5"


@pytest.mark.parametrize("raw", ["+1.5", "+140000", "1e3", "1E3", "1_000", ".5", "1."])
def test_decimal_refuses_forms_the_bare_constructor_accepted(raw: str) -> None:
    """The canonical grammar refuses text whose numeric meaning is not what it appears.

    Each form is asserted constructible first, so the test proves a genuine
    tightening rather than restating the constructor. A leading ``+`` was
    previously normalised away, and ``1e3`` silently became one thousand — a
    thousand-fold misreading of a typo on an operator-typed amount.
    """
    assert isinstance(Decimal(raw), Decimal), raw

    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DECIMAL), raw)

    assert not verdict.ok
    assert canonical == ""
    assert verdict.message_key == "flows.errors.invalid_decimal"
    assert verdict.context == {"page_id": "probe"}


@pytest.mark.parametrize("raw", ["1,5", "abc", "1.2.3", ""])
def test_decimal_rejects_non_decimal_tokens(raw: str) -> None:
    page = _page(widget=FlowWidgetKind.DECIMAL)
    canonical, verdict = validate_widget_shape(page, raw)

    assert not verdict.ok
    assert canonical == ""
    # A blank on a required page is the blank refusal; a malformed token is
    # the invalid-decimal refusal — both keyed, neither leaking the raw.
    expected_key = "flows.errors.blank_required" if raw == "" else "flows.errors.invalid_decimal"
    assert verdict.message_key == expected_key
    assert verdict.context == {"page_id": "probe"}


@pytest.mark.parametrize("raw", ["NaN", "Infinity", "-Infinity"])
def test_decimal_rejects_non_finite_values(raw: str) -> None:
    """``NaN`` / infinities parse under Decimal but an amount must be finite."""
    _canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DECIMAL), raw)

    assert not verdict.ok
    assert verdict.message_key == "flows.errors.invalid_decimal"


def test_decimal_accepts_blank_when_optional() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DECIMAL, required=False), "")

    assert verdict.ok
    assert canonical == ""


def test_decimal_accepts_blank_when_gated() -> None:
    canonical, verdict = validate_widget_shape(_page(widget=FlowWidgetKind.DECIMAL, visible_when=_GATE), "")

    assert verdict.ok
    assert canonical == ""


#: The affirmative and negative words each shipped catalogue's
#: ``flows.errors.invalid_confirm`` message actually names:
#:   en  "Answer yes or no."
#:   es  "Responde sí o no."
#:   ca  "Respon sí o no."
#:   hu  "Válaszolj igennel vagy nemmel."
#: Listed here rather than parsed out of the prose, because a test that read the
#: message would agree with whatever the message happened to say. A new locale
#: has to be added by hand, which is the point: shipping a prompt obliges you to
#: ship the words it asks for.
_ADVERTISED_CONFIRM_WORDS: tuple[tuple[str, str, str], ...] = (
    ("en", "yes", "no"),
    ("es", "sí", "no"),
    ("ca", "sí", "no"),
    ("hu", "igen", "nem"),
)


@pytest.mark.parametrize(("locale", "affirmative", "negative"), _ADVERTISED_CONFIRM_WORDS)
def test_a_confirm_page_accepts_the_words_its_own_refusal_advertises(
    locale: str,
    affirmative: str,
    negative: str,
) -> None:
    """Every locale can answer the question its own prompt asks.

    The confirm door once carried a private token set that knew no Spanish
    affirmative at all and neither Hungarian word. A taxpayer reading
    "Responde sí o no" typed ``sí`` and was refused with that same sentence
    again -- able to decline, since ``no`` happened to be in the set, but not to
    consent. Under ``hu`` neither ``igen`` nor ``nem`` was recognised, so the
    page could not be answered either way.

    Both directions are asserted because the Spanish failure was asymmetric:
    testing only the negative would have passed throughout the defect.
    """
    page = _page(widget=FlowWidgetKind.CONFIRM)

    yes_token, yes_verdict = validate_widget_shape(page, affirmative)
    no_token, no_verdict = validate_widget_shape(page, negative)

    assert yes_verdict.ok, f"{locale}: prompt advertises {affirmative!r} but the door refuses it"
    assert no_verdict.ok, f"{locale}: prompt advertises {negative!r} but the door refuses it"
    assert (yes_token, no_token) == ("true", "false")


def test_a_confirm_page_still_refuses_a_word_no_prompt_advertises() -> None:
    """Positive control: the door has not simply stopped refusing.

    Without this, a validator that accepted every non-blank token would satisfy
    every case above while admitting anything at all.
    """
    page = _page(widget=FlowWidgetKind.CONFIRM)

    token, verdict = validate_widget_shape(page, "peut-être")

    assert not verdict.ok
    assert verdict.message_key == "flows.errors.invalid_confirm"
    assert token == ""
