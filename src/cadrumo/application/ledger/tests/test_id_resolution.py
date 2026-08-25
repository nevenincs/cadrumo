"""Tests for transaction-id prefix resolution and display-id width."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, tr
from ....domain.transactions import (
    RawProvenance,
    RawTransaction,
    SourceFormat,
    Transaction,
    TransactionCatalogue,
    TransactionDirection,
    TransactionEditLineageEntry,
    TransactionIdPrefixError,
)
from ..id_resolution import (
    MINIMUM_DISPLAY_ID_WIDTH,
    compute_display_id_width,
    resolve_lineage_transaction_id,
    resolve_transaction_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_ID_A = "a" * 64
_ID_B = "b" * 64
_ID_AA = "a" + "0" * 63
_ID_AB = "a" + "1" * 63


def test_display_id_width_floors_at_minimum_for_empty_bucket() -> None:
    assert compute_display_id_width([]) == MINIMUM_DISPLAY_ID_WIDTH


def test_display_id_width_floors_at_minimum_for_well_separated_ids() -> None:
    assert compute_display_id_width([_ID_A, _ID_B]) == MINIMUM_DISPLAY_ID_WIDTH


def test_display_id_width_grows_when_minimum_collides() -> None:
    # _ID_A and _ID_AA share the first character "a"; their first 8 chars
    # are "aaaaaaaa" and "a0000000". They diverge at character 2 (index 1),
    # so width must be at least 2 to keep them unique. Since
    # MINIMUM_DISPLAY_ID_WIDTH=8 already separates them, width stays at 8.
    assert compute_display_id_width([_ID_A, _ID_AA]) == MINIMUM_DISPLAY_ID_WIDTH


def test_display_id_width_grows_when_ids_share_long_prefix() -> None:
    shared = "c" * 12
    a = shared + "1" * 52
    b = shared + "2" * 52
    # First 12 chars collide; first 13 diverge. With floor of 8 the
    # computed width must rise to 13.
    assert compute_display_id_width([a, b]) == 13


def test_resolve_full_id_passes_through() -> None:
    assert resolve_transaction_id(_ID_A, [_ID_A, _ID_B]) == _ID_A


def test_resolve_unique_prefix_resolves() -> None:
    assert resolve_transaction_id("a", [_ID_A, _ID_B]) == _ID_A


def test_resolve_ambiguous_prefix_refuses_with_collisions_listed() -> None:
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("a", [_ID_A, _ID_AA, _ID_AB])
    # The refusal now carries a typed translated_message key + context (not a raw
    # args[0] string); assert the locale-independent identity and interpolation data.
    err = exc_info.value
    assert err.translated_message == "application.ledger.errors.transaction_id_prefix_ambiguous"
    assert err.context is not None
    assert err.context["count"] == 3
    matches_text = err.context["matches"]
    assert isinstance(matches_text, str)
    assert _ID_A in matches_text
    assert _ID_AA in matches_text
    assert _ID_AB in matches_text


def test_resolve_no_match_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("deadbeef", [_ID_A, _ID_B])
    assert exc_info.value.translated_message == "application.ledger.errors.transaction_id_prefix_no_match"


def test_resolve_empty_prefix_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("", [_ID_A])
    # This raise site historically carried a bare positional message with no
    # translated_message, so resolve_error_message fell through to the raw
    # English args[0] on every locale. Pin the fix: a real translation key.
    assert exc_info.value.translated_message == "application.ledger.errors.transaction_id_prefix_empty"


def test_resolve_non_hex_prefix_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("xyz", [_ID_A])
    assert exc_info.value.translated_message == "application.ledger.errors.transaction_id_prefix_non_hex"


def test_resolve_too_long_prefix_refuses() -> None:
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("a" * 65, [_ID_A])
    assert exc_info.value.translated_message == "application.ledger.errors.transaction_id_prefix_too_long"


def test_resolve_prefix_is_case_insensitive_on_input() -> None:
    assert resolve_transaction_id(_ID_A.upper(), [_ID_A]) == _ID_A


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_empty_prefix_translated_key_renders_per_locale(locale: str) -> None:
    """The empty-prefix condition renders real, non-key-fallback text everywhere.

    This is the one raise site that used to carry no ``translated_message`` at
    all, so ``resolve_error_message`` fell back to the raw English
    ``args[0]`` on every non-English locale regardless of which language the
    operator configured. Pin the fix directly against ``tr()`` per locale.
    """
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_transaction_id("", [_ID_A])
    key = exc_info.value.translated_message
    assert key is not None
    rendered = tr(key, locale=locale)
    assert rendered, f"locale={locale!r}: got empty string"
    assert rendered != key, f"locale={locale!r}: tr() returned the key itself, indicating a missing catalogue entry"


def test_five_prefix_conditions_render_distinct_text() -> None:
    """Every distinct invariant violation must still read as distinct English text.

    Guards against a future edit collapsing two conditions onto the same
    translation key, which would read to the operator as one condition
    changing meaning rather than two conditions becoming indistinguishable.
    """

    def _rendered(prefix: str, ids: list[str]) -> str:
        with pytest.raises(TransactionIdPrefixError) as exc_info:
            resolve_transaction_id(prefix, ids)
        key = exc_info.value.translated_message
        assert key is not None
        interpolation = dict(exc_info.value.context or {})
        return tr(key, **interpolation)

    rendered_by_condition = {
        "empty": _rendered("", [_ID_A]),
        "non_hex": _rendered("xyz", [_ID_A]),
        "too_long": _rendered("a" * 65, [_ID_A]),
        "no_match": _rendered("deadbeef", [_ID_A, _ID_B]),
        "ambiguous": _rendered("a", [_ID_A, _ID_AA, _ID_AB]),
    }
    assert len(set(rendered_by_condition.values())) == len(rendered_by_condition), (
        f"two or more conditions rendered identical text: {rendered_by_condition}"
    )


# --- lineage-aware resolution -------------------------------------------------
def _raw(*, provider_id: str, amount: str, description: str) -> RawTransaction:
    return RawTransaction(
        provider_transaction_id=provider_id,
        booked_date=date(2026, 5, 1),
        value_date=date(2026, 5, 1),
        amount=Decimal(amount),
        currency="EUR",
        counterparty="Proveedor SL",
        description=description,
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="d" * 64,
            source_row_index=1,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2026, 5, 1, 12, 0, tzinfo=UTC),
            provider_name="CSV provider",
        ),
        raw_fields={"Concepto": description},
    )


def _transaction(
    *,
    provider_id: str,
    amount: str,
    description: str,
    edit_lineage: tuple[TransactionEditLineageEntry, ...] = (),
) -> Transaction:
    return Transaction.model_validate(
        {
            "raw": _raw(provider_id=provider_id, amount=amount, description=description),
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "source_jurisdiction": "ES",
            "edit_lineage": edit_lineage,
        },
    )


def _lineage_entry(previous_transaction_id: str) -> TransactionEditLineageEntry:
    return TransactionEditLineageEntry(
        previous_transaction_id=previous_transaction_id,
        actor="operator",
        source_command="aeat app ledger update",
        edited_at=datetime(2026, 5, 2, 9, 0, tzinfo=UTC),
    )


def test_lineage_resolver_passes_live_id_through_unchanged() -> None:
    """A current id resolves directly, exactly like the base resolver."""
    live = _transaction(provider_id="row-1", amount="100.00", description="v0")
    catalogue = TransactionCatalogue.from_transactions((live,))
    assert resolve_lineage_transaction_id(live.transaction_id, catalogue) == live.transaction_id


def test_lineage_resolver_resolves_a_superseded_old_id_to_the_heir() -> None:
    """An id that names no live row but is a previous_transaction_id on a live
    row's edit lineage resolves to that live row's current id.
    """
    original = _transaction(provider_id="row-1", amount="100.00", description="v0")
    heir = _transaction(
        provider_id="row-1",
        amount="100.00",
        description="v1",
        edit_lineage=(_lineage_entry(original.transaction_id),),
    )
    # Only the heir is in the catalogue (the update removed the original id).
    catalogue = TransactionCatalogue.from_transactions((heir,))
    assert original.transaction_id not in {t.transaction_id for t in catalogue.values()}
    assert resolve_lineage_transaction_id(original.transaction_id, catalogue) == heir.transaction_id


def test_lineage_resolver_walks_a_two_edit_chain() -> None:
    """The oldest handle in a two-edit chain still resolves to the latest row."""
    v0 = _transaction(provider_id="row-1", amount="100.00", description="v0")
    v1 = _transaction(
        provider_id="row-1",
        amount="100.00",
        description="v1",
        edit_lineage=(_lineage_entry(v0.transaction_id),),
    )
    v2 = _transaction(
        provider_id="row-1",
        amount="100.00",
        description="v2",
        edit_lineage=(_lineage_entry(v0.transaction_id), _lineage_entry(v1.transaction_id)),
    )
    catalogue = TransactionCatalogue.from_transactions((v2,))
    assert resolve_lineage_transaction_id(v0.transaction_id, catalogue) == v2.transaction_id
    assert resolve_lineage_transaction_id(v1.transaction_id, catalogue) == v2.transaction_id


def test_lineage_resolver_refuses_an_id_with_no_live_row_and_no_lineage() -> None:
    """An id that names neither a live row nor any lineage handle is refused."""
    live = _transaction(provider_id="row-1", amount="100.00", description="v0")
    catalogue = TransactionCatalogue.from_transactions((live,))
    with pytest.raises(TransactionIdPrefixError):
        resolve_lineage_transaction_id("deadbeef" + "0" * 56, catalogue)


def test_lineage_resolver_keeps_malformed_prefix_refusal() -> None:
    """Empty / non-hex prefixes are refused before lineage resolution runs."""
    live = _transaction(provider_id="row-1", amount="100.00", description="v0")
    catalogue = TransactionCatalogue.from_transactions((live,))
    with pytest.raises(TransactionIdPrefixError):
        resolve_lineage_transaction_id("", catalogue)
    with pytest.raises(TransactionIdPrefixError):
        resolve_lineage_transaction_id("xyz", catalogue)


def test_lineage_resolver_refuses_an_ambiguous_lineage_prefix() -> None:
    """A prefix naming no live row, but a lineage handle on two live rows, is
    ambiguous -- not silently resolved to whichever row happens first.

    The two lineage handles here are synthetic hex ids (not derived content
    hashes) sharing a common prefix by construction, so the collision is
    deterministic rather than a coincidence of the real derivation.
    """
    shared_prefix = "cfcf" + "0" * 60
    other_old_id = "cfcf" + "1" * 60
    live_a = _transaction(
        provider_id="row-1",
        amount="100.00",
        description="v1",
        edit_lineage=(_lineage_entry(shared_prefix),),
    )
    live_b = _transaction(
        provider_id="row-2",
        amount="200.00",
        description="v1",
        edit_lineage=(_lineage_entry(other_old_id),),
    )
    catalogue = TransactionCatalogue.from_transactions((live_a, live_b))
    with pytest.raises(TransactionIdPrefixError) as exc_info:
        resolve_lineage_transaction_id("cfcf", catalogue)
    err = exc_info.value
    # Same typed identity as the direct-resolver ambiguous case: a
    # lineage-side collision is not a distinct condition the operator needs
    # to read differently from a live-row collision.
    assert err.translated_message == "application.ledger.errors.transaction_id_prefix_ambiguous"
    assert err.context is not None
    assert err.context["count"] == 2
    matches_text = err.context["matches"]
    assert isinstance(matches_text, str)
    assert live_a.transaction_id in matches_text
    assert live_b.transaction_id in matches_text
