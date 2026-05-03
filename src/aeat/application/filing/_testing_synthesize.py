"""Synthesise an APPROVED :class:`aeat.domain.filing.FilingDraft` for reconciliation.

The reconcile happy-path compares an APPROVED local
:class:`aeat.domain.filing.FilingDraft` against the AEAT-stored
justificante. Registry-backed drafts are produced by the filing
workflow once validated modelo definitions are available. For a
one-shot reconcile sanity check we keep a much shorter loop: pick a
sanitised fixture under ``tests/fixtures/justificantes/{modelo}/``,
read its casillas off the source-pdf parser, and stamp them onto a
synthetic :class:`FilingDraft` whose status is
:attr:`aeat.domain.filing.FilingDraftStatus.APPROVED`.

This helper never reaches AEAT — it operates entirely on local
fixture bytes plus pure construction; the live-write guard remains
intact.

Examples:
    >>> from decimal import Decimal
    >>> from aeat.application.filing.testing import synthesize_filing_draft
    >>> draft = synthesize_filing_draft(
    ...     modelo="100",
    ...     period="0A",
    ...     profile_tax_id="Y0000001S",
    ...     casilla_values={"0511": Decimal("5550.00")},
    ... )
    >>> draft.status.name
    'APPROVED'
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from decimal import Decimal

from ...domain.filing._schema import (
    SCHEMA_VERSION_DEFAULT,
    FilingDraft,
    FilingDraftStatus,
    FilingScalar,
    FilingValue,
    FilingValueKind,
    compute_draft_id,
)


def synthesize_filing_draft(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str = "Y0000001S",
    casilla_values: Mapping[str, FilingScalar],
    status: FilingDraftStatus = FilingDraftStatus.APPROVED,
    schema_version: str = SCHEMA_VERSION_DEFAULT,
    source_label: str = "synthesized for read-only reconcile",
    created_at: datetime | None = None,
) -> FilingDraft:
    """Build a strict-frozen :class:`FilingDraft` from a casilla map.

    The resulting record carries:

    * ``draft_id`` content-hashed from
      ``(modelo, period, profile_tax_id, schema_version, values)``
      so two equivalent calls yield identical IDs.
    * One :class:`FilingValue` per ``casilla_values`` entry, with
      ``kind=LITERAL`` and ``source=source_label``.
    * ``status`` set to :class:`FilingDraftStatus.APPROVED` by
      default, ready for ``aeat filing reconcile`` to compare
      against the live AEAT record.
    * ``created_at == updated_at`` set to ``created_at`` (UTC now
      when omitted).
    * ``approved_at`` matching ``created_at`` (since the synthesised
      draft is born APPROVED).
    * ``approved_by`` set to ``"synthesize_filing_draft"`` so audit
      logs can cleanly distinguish a synthesized draft from an
      operator-approved one.

    Args:
        modelo: AEAT modelo code (``"100"`` / ``"130"`` / ...).
        period: Period token in :class:`FilingDraft` shape (e.g.
            ``"0A"`` for annual, ``"1T"``-``"4T"`` for quarterly).
        profile_tax_id: Synthetic taxpayer NIE/NIF. Defaults to
            ``"Y0000001S"`` (the value committed fixtures use).
        casilla_values: Mapping of casilla ID -> typed value
            (Decimal preferred for monetary values).
        status: Override the default APPROVED status. Useful when
            a caller wants to test the reconcile gate's
            :class:`FilingDraftStatus.DRAFT` rejection path.
        schema_version: Schema version stamp (rarely overridden).
        source_label: Free-text provenance string. Stamped on
            every :class:`FilingValue.source`.
        created_at: Optional UTC timestamp. ``None`` -> ``datetime.now(UTC)``.

    Returns:
        A frozen :class:`FilingDraft` ready for reconciliation.
    """
    timestamp = created_at if created_at is not None else datetime.now(UTC)
    values = tuple(
        FilingValue(
            casilla_id=casilla_id,
            value=value,
            kind=FilingValueKind.LITERAL,
            source=source_label,
        )
        for casilla_id, value in sorted(casilla_values.items())
    )

    draft_id = compute_draft_id(
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        schema_version=schema_version,
        values=values,
    )

    is_approved = status is FilingDraftStatus.APPROVED
    return FilingDraft(
        draft_id=draft_id,
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        status=status,
        values=values,
        created_at=timestamp,
        updated_at=timestamp,
        schema_version=schema_version,
        approved_at=timestamp if is_approved else None,
        approved_by="synthesize_filing_draft" if is_approved else None,
    )


def synthesize_filing_draft_from_decimals(
    *,
    modelo: str,
    period: str,
    profile_tax_id: str = "Y0000001S",
    casilla_decimals: Mapping[str, str | Decimal],
    status: FilingDraftStatus = FilingDraftStatus.APPROVED,
    schema_version: str = SCHEMA_VERSION_DEFAULT,
    source_label: str = "synthesized for read-only reconcile",
    created_at: datetime | None = None,
) -> FilingDraft:
    """Convenience wrapper: accept decimal-as-string casilla values.

    The :func:`synthesize_filing_draft` helper expects typed
    :class:`Decimal` values per AEAT's monetary precision rules.
    Real-world fixture values are usually printed as Spanish
    decimal strings (``"5.550,00"``) or canonical decimal strings
    (``"5550.00"``). This wrapper coerces every value to
    :class:`Decimal` so callers don't repeat the conversion at
    every call site.

    Args:
        modelo: AEAT modelo code.
        period: Period token.
        profile_tax_id: Synthetic taxpayer ID.
        casilla_decimals: Mapping of casilla ID -> decimal-as-string
            (``"5550.00"``) or :class:`Decimal`. Each value is
            coerced to :class:`Decimal` before being stamped.
        status: Forwarded to :func:`synthesize_filing_draft`.
        schema_version: Forwarded to :func:`synthesize_filing_draft`.
        source_label: Forwarded to :func:`synthesize_filing_draft`.
        created_at: Forwarded to :func:`synthesize_filing_draft`.

    Returns:
        A frozen :class:`FilingDraft` ready for reconciliation.

    Raises:
        ValueError: If a value cannot be parsed as a decimal.
    """
    coerced: dict[str, FilingScalar] = {}
    for casilla_id, raw in casilla_decimals.items():
        if isinstance(raw, Decimal):
            coerced[casilla_id] = raw
        else:
            # Spanish thousand-separators ("5.550,00") are implicitly
            # rejected here by Decimal() raising InvalidOperation —
            # callers must canonicalise upstream so the contract
            # surface stays narrow.
            coerced[casilla_id] = Decimal(raw)
    return synthesize_filing_draft(
        modelo=modelo,
        period=period,
        profile_tax_id=profile_tax_id,
        casilla_values=coerced,
        status=status,
        schema_version=schema_version,
        source_label=source_label,
        created_at=created_at,
    )


__all__ = [
    "synthesize_filing_draft",
    "synthesize_filing_draft_from_decimals",
]
