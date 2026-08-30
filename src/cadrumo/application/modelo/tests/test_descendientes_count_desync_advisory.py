"""The stored descendientes count against the rows it aggregates.

``renta_family.descendientes_count`` is a derived aggregate: the entry
surface, the wizard descendant door and the checkpoint projection each
rewrite it in the same atomic batch as the ``renta_family.descendiente.{n}.*``
rows, so those writers cannot desync it.

The profile manager can. The count is a declared schema field and renders
as an ordinary editable row, while the rows it counts are an indexed fact
namespace the manager does not render at all — so the operator edits a
number with nothing beside it to contradict. The divergence then splits
the filing: the ``renta-2024-profile-descendientes-count`` binding reads
the stored count, and casillas 0513/0514 are injected from the rows.

These cases pin the advisory that says so, and — as the control — that a
count standing alone with no rows is still the supported declaration the
sibling undeclared-advisory treats it as, not a fault.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....core.modelo import Modelo
from ....domain.contribuyente.descendant import DescendantInfo
from ....domain.contribuyente.descendant_facts import descendant_facts_from_list
from ....domain.user_profile.values import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from .._minimo_descendientes_advisory import collect_descendientes_count_desync_diagnostics
from ._advisory_bucket_fixture import _bucket  # noqa: F401

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "9a9a9a9a-9a9a-4a9a-8a9a-9a9a9a9a9a9a"
_COUNT_PATH = "renta_family.descendientes_count"


@pytest.fixture
def bucket_id() -> str:
    return _BUCKET_ID


def _write(*facts: UserProfileFact) -> None:
    set_active_test_profile_facts(facts)


def _two_descendants() -> tuple[UserProfileFact, ...]:
    kids = [DescendantInfo(birth_date=date(2020, 3, 1)), DescendantInfo(birth_date=date(2022, 7, 4))]
    return tuple(UserProfileFact(path=p, value=v) for p, v in descendant_facts_from_list(kids))


def _advise() -> tuple[str, ...]:
    """The text an OPERATOR sees, not the message field alone.

    A diagnostic states the problem in ``message`` and the fix in ``remedy``,
    which the calculate CLI projects onto the notice's ``suggestion`` and renders
    as one line. Asserting against ``message`` alone would let a remedy fall off
    the operator-facing surface without any test noticing.
    """
    return tuple(
        d.message if d.remedy is None else f"{d.message} {d.remedy}"
        for d in collect_descendientes_count_desync_diagnostics(modelo=Modelo.M100.value, bucket_id=_BUCKET_ID)
    )


def test_a_count_edited_away_from_its_rows_is_reported() -> None:
    """The measured defect: the manager writes the count, the rows stay put."""
    _write(*_two_descendants())
    _write(UserProfileFact(path=_COUNT_PATH, value="7"))

    reported = _advise()

    assert len(reported) == 1
    assert "7" in reported[0] and "2" in reported[0], "the advisory must name both answers the profile holds"
    assert "descendiente add" in reported[0], "it must name the surface that rewrites both together"


def test_the_atomic_writers_leave_nothing_to_report() -> None:
    """The control: the entry surface's own output must not trip this.

    The descendant projection writes the count and the rows in one batch,
    so an advisory here would fire on every correctly-entered profile and
    be trained away — which is how a real desync then goes unread.
    """
    _write(*_two_descendants())

    assert _advise() == ()


def test_a_count_standing_alone_is_a_declaration_not_a_desync() -> None:
    """A bare count with no rows is supported, including a declared zero.

    The sibling undeclared-advisory treats exactly this as an explicit
    statement of the filer's family situation, so flagging it here would
    contradict the module this one lives in.
    """
    _write(UserProfileFact(path=_COUNT_PATH, value="3"))

    assert _advise() == ()


def test_a_profile_with_rows_and_no_stored_count_is_not_reported() -> None:
    """Absence is not disagreement; there is only one answer on record."""
    rows = tuple(fact for fact in _two_descendants() if fact.path != _COUNT_PATH)
    _write(*rows)
    _write(UserProfileFact(path=_COUNT_PATH, value=None))

    assert _advise() == ()


def test_another_modelo_is_left_alone() -> None:
    """The count binds Modelo 100; every other filing must be untouched."""
    _write(*_two_descendants())
    _write(UserProfileFact(path=_COUNT_PATH, value="7"))

    assert collect_descendientes_count_desync_diagnostics(modelo=Modelo.M303.value, bucket_id=_BUCKET_ID) == ()
