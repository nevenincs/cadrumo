"""The filer's own identifier reaches the reading path from a live profile.

The seam that was missing. Two capabilities were built, exported and tested, and
neither could run on a real read: the counterparty role resolution excludes the
filer's own identifier from candidacy, and the direction derivation asks which
party's block prints it. Both are gated on an identifier that the reading chain
accepted as a parameter and that no caller ever supplied -- so both were
structurally unreachable however completely they were built, and no unit test
could show it, because a unit test passes the identifier in by hand.

This drives a real encrypted bucket with a real profile and asserts the lookup
returns what the profile declares. It is deliberately a test of the SEAM rather
than of either consumer: the consumers have their own gates, and what neither of
them can prove is that anything connects them to a profile.

Everything is reached through the package facade. The reading path's own thin
wrapper over this -- workflow-state load, then this call -- is deliberately NOT
reached here: a leading-underscore symbol pulled into a test across a package
boundary is a seam that should not exist, and the wrapper's remaining behaviour
is covered where it belongs, by an end-to-end read.

The negative case is the load-bearing half. A profile declaring no identifier
must yield ``None`` rather than a placeholder, because a placeholder compares
unequal to every real identifier and would look exactly like a working lookup
while silently disabling both consumers again.

See Also:
    :func:`~application.ledger.resolve_filer_tax_id`
        The profile-fact reader this exercises through a live store.
"""

from __future__ import annotations

from typing import Final

import pytest

from ....application.ledger import FILER_TAX_ID_FACT_PATH, resolve_filer_tax_id
from cadrumo.application.workflow.persistence import workflow_state_repository
from ....domain.user_profile import UserProfileFact
from ....tests.profile_capsule import set_active_test_profile_facts
from ._ledger_validation_fixtures import bucket

__all__ = ["bucket"]

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_DECLARED_NIF: Final = "B12345674"


@pytest.mark.usefixtures("bucket")
def test_the_reading_path_reads_the_identifier_the_profile_declares() -> None:
    """The link that did not exist: profile fact to reading path.

    The value asserted is one this test writes, and it differs from the one the
    session harness seeds. That difference is the point: asserting against the
    harness's own default would pass equally against a lookup that read some
    other profile, or a hardcoded constant, so the test writes a value of its own
    and requires the lookup to have followed it.
    """
    repository = workflow_state_repository()
    set_active_test_profile_facts((UserProfileFact(path=FILER_TAX_ID_FACT_PATH, value=_DECLARED_NIF),))

    declared = resolve_filer_tax_id(profile_record=repository.load().active_profile_record())

    assert declared == _DECLARED_NIF


def test_no_resolvable_profile_yields_nothing_rather_than_a_placeholder() -> None:
    """The negative control, and the failure mode it rules out.

    A canonical projection in this codebase defaults an absent NIF to the
    placeholder ``00000000T``. Reaching for it here would have produced a lookup
    that always returns a value, always compares unequal to every real
    identifier, and so silently re-disables both consumers while looking wired.

    Asserted against the resolver directly rather than through a bucket, because
    the session harness always seeds a valid identifier -- there is no live
    profile in it that declares none, and a control that cannot construct its own
    negative case is not a control.
    """
    assert resolve_filer_tax_id(profile_record=None) is None
