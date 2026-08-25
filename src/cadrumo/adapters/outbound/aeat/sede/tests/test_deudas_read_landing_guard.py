"""The deudas read-landing guard admits the consulta and refuses its neighbours.

AEAT's debts consulta sits one control away from *pagar todas mis deudas*,
*pagar algunas deudas*, *pago parcial* and the aplazamiento request. This
application never pays, files or mutates remotely, so the guard is the runtime
wall.

The allow-list no longer ships empty: an authenticated capture of the live sede
established the consulta endpoint, so the guard now declares exactly that one
path. What the capture ALSO established is why the entry is the endpoint rather
than its application prefix -- AEAT serves *pagar todas mis deudas* from the
SAME ``/wlpl/SRVO-JDIT/`` application as the consulta, so allow-listing that
shared prefix would admit the payment launcher into the guard that exists to
keep it out. That is the regression
:func:`test_the_payment_launcher_sharing_the_consulta_application_is_refused`
pins, and it is the single most valuable assertion in this module.

A test that only showed "every URL is refused" would be worthless evidence,
because a guard refusing for an unrelated reason -- a rejected host, a malformed
policy -- would pass it just as well. The admission case below is what gives the
refusals their meaning: the same guard, driven with the real tuple, admits the
consulta, so every refusal is attributable to the allow-list and nothing else.
"""

from __future__ import annotations

from urllib.parse import urlsplit

import pytest

from ......tests.aeat_literal_fixtures import (
    DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE,
    DEUDAS_CONSULTA_PATH_SHAPE_CANARY,
    DEUDAS_OBSERVED_PAYMENT_SURFACE_PATH_FIXTURES,
    DEUDAS_OFF_HOST_LANDING_CANARY,
    DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE,
    DEUDAS_PAYMENT_SURFACE_PATH_SHAPE_CANARIES,
    DEUDAS_READ_SURFACE_PATH_SHAPE_CANARIES,
    aeat_url,
)
from .. import assert_deudas_landing, deudas_read_path_prefixes
from .._adapter_utils import assert_read_landing
from ..deudas import _READ_GUARD_POLICY
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# The landing shapes are declared centrally, so no test module owns an AEAT
# route literal, and the origin comes from the configured AEAT domain rather
# than a pinned host number.
_PAYMENT_SHAPED = tuple(aeat_url("www6", path) for path in DEUDAS_PAYMENT_SURFACE_PATH_SHAPE_CANARIES)
_READ_SHAPED = tuple(aeat_url("www6", path) for path in DEUDAS_READ_SURFACE_PATH_SHAPE_CANARIES)
#: The payment and aplazamiento launchers OBSERVED beside the live consulta.
_PAYMENT_OBSERVED = tuple(aeat_url("www6", path) for path in DEUDAS_OBSERVED_PAYMENT_SURFACE_PATH_FIXTURES)
_CONSULTA_OBSERVED = aeat_url("www6", DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE)

# A relative path has no establishable origin, which is its own refusal reason.
_UNREADABLE = ("", "about:blank", DEUDAS_CONSULTA_PATH_SHAPE_CANARY, None)


def test_the_allow_list_carries_exactly_the_observed_consulta_endpoint() -> None:
    """One entry, and it is the ENDPOINT rather than its application prefix.

    Asserted on the real tuple, and asserted as an exact equality rather than a
    membership check: membership would still pass if a later edit ADDED a second
    path beside the consulta, which is precisely how a payment launcher would
    arrive. The tuple is the whole allow-list, so the test is the whole tuple.
    """
    assert deudas_read_path_prefixes() == (DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE,)


def test_the_observed_consulta_landing_is_admitted() -> None:
    """The admission case that gives every refusal below its meaning.

    Without this, a guard broken so thoroughly that it refused everything would
    pass the entire rest of this module.
    """
    assert_deudas_landing(_CONSULTA_OBSERVED)


@pytest.mark.parametrize("origin", ["sede", "www1", "www2", "www3", "www6", "www12"])
def test_the_consulta_is_admitted_on_whichever_numbered_host_answers(origin: str) -> None:
    """``www{n}`` is a per-SESSION variable, so no single number may be required.

    AEAT load-balances the authenticated surface across its numbered pool and
    assigns the host per session. The capture that grounded this guard happened
    to land on one of them; a guard that admitted only that number would work in
    the session it was written in and refuse a legitimate dispatch afterwards --
    a failure that reproduces only on someone else's session, which is the worst
    shape a guard bug can take.

    The refusals elsewhere in this module are all path-driven, so widening the
    host axis here costs nothing: an off-apex host is still refused by
    :func:`test_an_off_host_landing_is_refused`, and every payment path is still
    refused on EVERY one of these origins.
    """
    assert_deudas_landing(aeat_url(origin, DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE))

    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(aeat_url(origin, DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE))


def test_the_host_suffix_is_what_carries_the_numbered_dispatch() -> None:
    """Which FIELD survives the session, proved by removing it.

    The test above passes whether the policy names an exact numbered host or the
    unnumbered origin, because ``allowed_host_suffixes`` admits the whole AEAT
    apex either way. That makes it a statement of intent rather than evidence,
    so this pins the mechanism: rebuild the policy with the suffix dropped and a
    single numbered host named, and a SIBLING number is refused.

    So the suffix is load-bearing and the exact host is not, which is why the
    module builds ``_SEDE_HOST`` on the unnumbered origin. Anyone who later
    tightens the suffix away to "lock down the host" reintroduces exactly the
    refusal this proves, in a session that is not theirs.
    """
    numbered_only = _READ_GUARD_POLICY.model_copy(
        update={
            "allowed_hosts": (urlsplit(aeat_url("www6", "/")).netloc,),
            "allowed_host_suffixes": (),
        },
    )

    # The named number still resolves...
    assert_read_landing(
        aeat_url("www6", DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE),
        surface="deudas suffix mechanism proof",
        policy=numbered_only,
        allowed_path_prefixes=(DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE,),
    )

    # ...and a sibling the load balancer could equally have assigned does not.
    with pytest.raises(SedeNavigationError):
        assert_read_landing(
            aeat_url("www2", DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE),
            surface="deudas suffix mechanism proof",
            policy=numbered_only,
            allowed_path_prefixes=(DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE,),
        )


def test_the_payment_launcher_sharing_the_consulta_application_is_refused() -> None:
    """*Pagar todas mis deudas* lives in the consulta's OWN AEAT application.

    Both are served from ``/wlpl/SRVO-JDIT/``; only the endpoint segment
    separates a read of what is owed from the flow that pays it. This is the
    regression that fails if anyone ever "simplifies" the allow-list to the
    application prefix, which is the natural shape to reach for and the one that
    would put a taxpayer's money one navigation from a read.
    """
    shared_application = DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE.rsplit("/", 1)[0] + "/"
    assert DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE.startswith(shared_application), (
        "the fixtures no longer witness the shared-application arrangement this test exists for"
    )

    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(aeat_url("www6", DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE))


@pytest.mark.parametrize("landing", _PAYMENT_OBSERVED)
def test_every_observed_payment_or_aplazamiento_landing_is_refused(landing: str) -> None:
    """The real launchers AEAT links beside the consulta, each refused."""
    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(landing)


@pytest.mark.parametrize("landing", _PAYMENT_SHAPED)
def test_a_payment_or_aplazamiento_landing_is_refused(landing: str) -> None:
    """The landings that would put a taxpayer's money one navigation away."""
    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(landing)


@pytest.mark.parametrize("landing", _READ_SHAPED)
def test_a_plausible_but_unobserved_read_landing_is_still_refused(landing: str) -> None:
    """Read-SHAPED is not enough; the landing must be THE consulta.

    These paths look exactly like a debts consulta and are not the one AEAT
    serves. Admitting them would mean the guard is matching a vibe rather than
    an observation -- and a detail-page shape being refused is the tell that the
    allow-list is one endpoint rather than a permissive prefix.
    """
    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(landing)


@pytest.mark.parametrize("landing", _UNREADABLE)
def test_a_landing_with_no_establishable_origin_is_refused(landing: str | None) -> None:
    """Where AEAT dispatched cannot be established, so the read is refused."""
    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(landing)


def test_an_off_host_landing_is_refused() -> None:
    """An authenticated session is never followed off the AEAT apex."""
    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(DEUDAS_OFF_HOST_LANDING_CANARY)


def test_the_guard_discriminates_on_the_allow_list_and_not_on_something_else() -> None:
    """The discrimination follows the allow-list ARGUMENT, not this module.

    Distinct from the admission test above, which exercises the shipped tuple.
    Here the shared function is driven with a tuple this module supplies -- a
    real argument to the real function, not a patched module -- and it admits
    that prefix while still refusing the payment sibling beside it. Without
    this, a guard hard-wired to admit the shipped consulta and refuse all else
    would satisfy every other assertion here while ignoring its own parameter.
    """
    permitted_prefix = DEUDAS_CONSULTA_PATH_SHAPE_CANARY

    assert_read_landing(
        aeat_url("www6", permitted_prefix),
        surface="deudas consulta positive control",
        policy=_READ_GUARD_POLICY,
        allowed_path_prefixes=(permitted_prefix,),
    )

    for refused in (_PAYMENT_SHAPED[0], _PAYMENT_SHAPED[3]):
        with pytest.raises(SedeNavigationError):
            assert_read_landing(
                refused,
                surface="deudas consulta positive control",
                policy=_READ_GUARD_POLICY,
                allowed_path_prefixes=(permitted_prefix,),
            )


def test_the_policy_declares_no_drivable_browser_action() -> None:
    """No control on this surface may be driven; every payment action is one."""
    assert _READ_GUARD_POLICY.allowed_browser_action_patterns == ()
    assert _READ_GUARD_POLICY.requires_authentication is True
    assert _READ_GUARD_POLICY.synthetic_data_allowed is False


def test_the_read_post_allowance_is_scoped_to_the_consulta_alone() -> None:
    """The consulta needs a POST; nothing else on this surface may have one.

    The listing exists only behind the NIF form's submission, so the read is a
    POST query. The guard admits that only for a path named in
    ``allowed_read_post_paths``, so the allowance has to be pinned to exactly
    the consulta -- a second entry here would be a payment endpoint handed a
    method the rest of the guard is built to deny.
    """
    assert _READ_GUARD_POLICY.allowed_read_post_paths == (DEUDAS_CONSULTA_OBSERVED_PATH_FIXTURE,)
    assert DEUDAS_PAGAR_TODAS_OBSERVED_PATH_FIXTURE not in _READ_GUARD_POLICY.allowed_read_post_paths
