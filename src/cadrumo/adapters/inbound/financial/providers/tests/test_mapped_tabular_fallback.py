"""The mapping lane is enrolled strictly after the exact fixed-layout providers.

An exact layout match is a deterministic read of a known structure; the mapping
lane's read depends on a column-role mapping decided per file. So the ordering
is the control, not the lane's capability — and the test that matters proves the
lane *would* have taken a known bank export had it been offered it first.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ......core.field_role import FieldRole
from ......core.tabular import NormalizedTable
from ......domain.transactions.enums import TransactionDirection
from ......tests import FIXTURES_DIR
from .._detection import _ordered_candidates, detect_provider
from .._mapped_tabular import MappedTabularProvider, default_tabular_mapping_resolver
from .._tabular_projection import ColumnRoleMapping
from ..base import InvalidFinancialSourceError
from ..csv import CsvProvider

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

_FIXTURES = FIXTURES_DIR / "financial"
_TABULAR = _FIXTURES / "tabular-dialects"

#: A known bank export the exact CSV provider parses today.
_KNOWN_BANK_FIXTURE = _FIXTURES / "bbva-sample.csv"
#: An export of no fixed layout the product recognises: neobank column names,
#: dot decimals, an ISO date and an exchange-rate column with no role.
_UNKNOWN_FORMAT_FIXTURE = _TABULAR / "bank_neobank_2026Q1.csv"

#: The role of each column of the unknown-format export, in column order. This
#: is the data a mapping step supplies; the lane consumes it, it does not
#: derive it.
_NEOBANK_ROLES = (
    FieldRole.INVOICE_DATE,
    FieldRole.UNMAPPED,
    FieldRole.COUNTERPARTY_NAME,
    FieldRole.NOTES,
    FieldRole.UNMAPPED,
    FieldRole.GRAND_TOTAL,
    FieldRole.CURRENCY,
    FieldRole.UNMAPPED,
)

#: The same for the known bank export, so the shadowing test can prove the lane
#: is capable of taking that file and is held back only by the ordering.
_KNOWN_BANK_ROLES = (
    FieldRole.INVOICE_DATE,
    FieldRole.UNMAPPED,
    FieldRole.NOTES,
    FieldRole.GRAND_TOTAL,
    FieldRole.UNMAPPED,
    FieldRole.CURRENCY,
)


def _resolver(roles: tuple[FieldRole, ...]):
    """Return a resolver supplying ``roles`` for whatever table it is handed."""

    def resolve(table: NormalizedTable) -> ColumnRoleMapping | None:
        if len(table.headers) != len(roles):
            return None
        return ColumnRoleMapping(roles=roles)

    return resolve


def test_mapping_lane_is_last_for_every_source_shape() -> None:
    """The fallback trails every exact provider, whatever the file looks like."""
    shapes = (
        Path("statement.csv"),
        Path("statement.xlsx"),
        Path("statement.ofx"),
        Path("statement.pdf"),
        _UNKNOWN_FORMAT_FIXTURE,
        _KNOWN_BANK_FIXTURE,
    )
    for path in shapes:
        candidates = _ordered_candidates(path)
        assert isinstance(candidates[-1], MappedTabularProvider), path.name
        mapped_positions = [
            index for index, provider in enumerate(candidates) if isinstance(provider, MappedTabularProvider)
        ]
        assert mapped_positions == [len(candidates) - 1], path.name


def test_known_bank_fixture_still_takes_the_exact_provider() -> None:
    """A recognised bank export parses deterministically, end to end.

    An OUTCOME check: it pins which provider answers and the values it yields.
    It does **not** on its own establish that the ordering is what produced that
    outcome — under test the production resolver cannot act, so this stays green
    even with the lane ordered first. The shadowing guarantee lives in
    :func:`test_the_known_bank_export_matches_before_the_mapping_lane_is_reached`.
    """
    provider = detect_provider(_KNOWN_BANK_FIXTURE)
    assert isinstance(provider, CsvProvider)
    rows = list(provider.ingest(_KNOWN_BANK_FIXTURE))
    assert rows
    assert rows[0].direction is TransactionDirection.INCOMING
    assert rows[0].raw.amount == Decimal("1500.25")


def test_the_known_bank_export_matches_before_the_mapping_lane_is_reached() -> None:
    """The exact provider matches at a position AHEAD of the mapping lane.

    This is the gate against shadowing, and it is deliberately structural
    rather than an assertion about which provider won. The outcome test above
    cannot do this job on its own: under test the production resolver reaches a
    model and a profile-bound cache that are not available, so the lane declines
    every file **wherever it sits in the order**. A known export would keep
    taking its exact parser even with the lane ordered first — green because the
    fallback cannot act, not because the ordering protects anything.

    Comparing positions removes that dependency entirely. If the lane were
    ordered ahead of the exact providers, the matching index would fall after
    the lane's and this reddens, whether or not the lane's resolver could have
    answered.
    """
    candidates = _ordered_candidates(_KNOWN_BANK_FIXTURE)
    lane_index = next(index for index, provider in enumerate(candidates) if isinstance(provider, MappedTabularProvider))
    matched_index = next(
        (index for index, provider in enumerate(candidates) if provider.validate_source(_KNOWN_BANK_FIXTURE).is_valid),
        None,
    )

    assert matched_index is not None, "no provider claimed the known bank export"
    assert isinstance(candidates[matched_index], CsvProvider)
    assert matched_index < lane_index, (
        f"the mapping lane sits at {lane_index}, ahead of the exact provider that matched at {matched_index}"
    )


def test_the_mapping_lane_can_read_the_known_bank_fixture_when_it_can_map() -> None:
    """The lane is held back by the ordering, not by an inability to read the file.

    Stated as capability only. It uses a supplied mapping rather than the
    production resolver, so it proves the lane *can* act on this export — which
    is what makes ordering it last meaningful — while the shadowing guarantee
    itself rests on the position comparison above.
    """
    lane = MappedTabularProvider(mapping_resolver=_resolver(_KNOWN_BANK_ROLES))
    validation = lane.validate_source(_KNOWN_BANK_FIXTURE)
    assert validation.is_valid, validation.warnings
    assert list(lane.ingest(_KNOWN_BANK_FIXTURE))


def test_unknown_format_fixture_is_refused_by_every_exact_provider() -> None:
    """No exact provider claims the unknown export — the precondition for reaching the lane."""
    for provider in _ordered_candidates(_UNKNOWN_FORMAT_FIXTURE)[:-1]:
        assert not provider.validate_source(_UNKNOWN_FORMAT_FIXTURE).is_valid, provider.name


def test_unknown_format_fixture_reaches_the_mapping_lane() -> None:
    """Detection consults the lane for the unknown export, and it imports under a mapping."""
    candidates = _ordered_candidates(_UNKNOWN_FORMAT_FIXTURE)
    assert isinstance(candidates[-1], MappedTabularProvider)

    lane = MappedTabularProvider(mapping_resolver=_resolver(_NEOBANK_ROLES))
    validation = lane.validate_source(_UNKNOWN_FORMAT_FIXTURE)
    assert validation.is_valid, validation.warnings

    rows = list(lane.ingest(_UNKNOWN_FORMAT_FIXTURE))
    assert len(rows) == 12
    assert rows[0].direction is TransactionDirection.OUTGOING
    assert rows[0].raw.amount == Decimal("469.52")
    assert rows[0].raw.currency == "EUR"
    assert rows[1].direction is TransactionDirection.INCOMING
    assert rows[1].raw.amount == Decimal("4596.00")


def test_unmapped_columns_are_reported_rather_than_refusing_the_file() -> None:
    """Three columns carry no role; the export still imports and says which."""
    lane = MappedTabularProvider(mapping_resolver=_resolver(_NEOBANK_ROLES))
    validation = lane.validate_source(_UNKNOWN_FORMAT_FIXTURE)
    assert validation.is_valid
    unmapped = [warning for warning in validation.warnings if "not mapped to a role" in warning]
    assert len(unmapped) == 3
    assert any("exchange_rate" in warning for warning in unmapped)


def test_lane_reports_when_roles_cannot_be_established() -> None:
    """A host that cannot map declines and says why; it never invents roles.

    The mapping may be unavailable for several reasons — no resolver wired, the
    optional extra absent, no model configured, an unusable reply — and every
    one of them arrives here as "no mapping". The lane must report that and
    refuse, rather than fall back to guessing column meanings.
    """
    lane = MappedTabularProvider(mapping_resolver=lambda table: None)
    validation = lane.validate_source(_UNKNOWN_FORMAT_FIXTURE)
    assert not validation.is_valid
    assert any("column roles could not be established" in warning for warning in validation.warnings)
    with pytest.raises(InvalidFinancialSourceError, match="column roles could not be established"):
        list(lane.ingest(_UNKNOWN_FORMAT_FIXTURE))


def test_lane_with_no_resolver_at_all_reports_rather_than_guesses() -> None:
    """The unwired case is distinct from the unmappable one and names itself."""
    lane = MappedTabularProvider()
    lane.mapping_resolver = None
    validation = lane.validate_source(_UNKNOWN_FORMAT_FIXTURE)
    assert not validation.is_valid
    assert any("no column-role mapping resolver" in warning for warning in validation.warnings)
    with pytest.raises(InvalidFinancialSourceError, match="no column-role mapping resolver"):
        list(lane.ingest(_UNKNOWN_FORMAT_FIXTURE))


def test_the_wiring_point_is_the_lanes_only_production_mapping_source() -> None:
    """Whatever supplies roles in production arrives through the one wiring point.

    Asserted as identity against that function rather than against a particular
    resolver, so binding or unbinding the semantic mapper does not make this
    test fail for saying nothing. What must not happen is a second mapping
    source appearing beside it.
    """
    assert MappedTabularProvider().mapping_resolver == default_tabular_mapping_resolver()


def test_a_mapping_missing_a_required_role_is_refused_with_the_role_named() -> None:
    """A mapping with no amount column cannot produce movements, and says so."""
    roles = tuple(FieldRole.UNMAPPED if role is FieldRole.GRAND_TOTAL else role for role in _NEOBANK_ROLES)
    lane = MappedTabularProvider(mapping_resolver=_resolver(roles))
    validation = lane.validate_source(_UNKNOWN_FORMAT_FIXTURE)
    assert not validation.is_valid
    assert any("grand_total" in warning for warning in validation.warnings)


def test_one_unparseable_row_does_not_refuse_the_whole_file(tmp_path: Path) -> None:
    """A bad row is reported and skipped; every other row still imports."""
    source = (
        "fecha;concepto;importe\n"
        "01/02/2026;Compra uno;-10,00\n"
        "no-es-fecha;Compra dos;-20,00\n"
        "03/02/2026;Compra tres;-30,00\n"
    )
    path = tmp_path / "unknown_export.csv"
    path.write_bytes(source.encode("utf-8"))
    lane = MappedTabularProvider(
        mapping_resolver=_resolver((FieldRole.INVOICE_DATE, FieldRole.NOTES, FieldRole.GRAND_TOTAL)),
    )
    validation = lane.validate_source(path)
    assert validation.is_valid
    assert any("line 3 cannot be imported" in warning for warning in validation.warnings)
    rows = list(lane.ingest(path))
    assert [row.raw.amount for row in rows] == [Decimal("10.00"), Decimal("30.00")]
