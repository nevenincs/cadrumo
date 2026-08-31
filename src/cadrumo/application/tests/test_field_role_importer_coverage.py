"""Every column a tabular importer consumes has a role to be mapped onto.

The column-role vocabulary is only useful if a role the mapping step assigns
lands on a column an importer actually accepts. The two sets are declared in
different packages and drift independently: a new importer column added without
a matching role leaves that column unreachable through the mapping step, and
nothing else in the tree notices.

The importer sets are read from their owning facades rather than restated here.
A copy would pass while the real column set moved underneath it, which is the
whole failure this gate exists to catch.
"""

from __future__ import annotations

import pytest

from ...application.invoices.bulk_import import BULK_INVOICE_IMPORT_ALLOWED_COLUMNS
from ...application.ledger.models import BULK_CLASSIFY_ALLOWED_COLUMNS
from ...core.field_role import FieldRole

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


_IMPORTER_COLUMNS: frozenset[str] = BULK_INVOICE_IMPORT_ALLOWED_COLUMNS | BULK_CLASSIFY_ALLOWED_COLUMNS


def test_the_derived_importer_column_set_is_populated() -> None:
    """Guard the denominator before asserting coverage over it.

    If either facade constant were emptied or renamed to something falsy, the
    coverage assertion below would pass over nothing at all.
    """
    assert BULK_INVOICE_IMPORT_ALLOWED_COLUMNS
    assert BULK_CLASSIFY_ALLOWED_COLUMNS
    assert len(_IMPORTER_COLUMNS) >= len(BULK_CLASSIFY_ALLOWED_COLUMNS)


def test_every_importer_column_resolves_to_a_role() -> None:
    """Each accepted column token is a member of the role vocabulary."""
    role_tokens = {member.value for member in FieldRole}
    unreachable = sorted(_IMPORTER_COLUMNS - role_tokens)
    assert not unreachable, f"importer columns with no FieldRole member: {unreachable}"


@pytest.mark.parametrize("column", sorted(_IMPORTER_COLUMNS))
def test_each_importer_column_hydrates_to_its_role(column: str) -> None:
    """The constructor direction, so a member added with a drifted value reddens."""
    assert FieldRole(column).value == column


def test_unmapped_is_not_itself_an_importer_column() -> None:
    """The sentinel must not collide with a real column an importer accepts.

    A collision would make "meaning not established" indistinguishable from a
    genuine column, and the deterministic copy step would write the sentinel's
    cells into a real field.
    """
    assert FieldRole.UNMAPPED.value not in _IMPORTER_COLUMNS
