"""The deudas read-landing guard refuses every landing, by construction.

AEAT's debts consulta sits one control away from *pagar todas mis deudas*,
*pagar algunas deudas*, *pago parcial* and the aplazamiento request. This
application never pays, files or mutates remotely, so the guard is the runtime
wall, and it ships with an EMPTY allow-list: no specimen of the consulta exists
in this tree, so there is no honest prefix to declare and the surface stays
unreachable until a real capture supplies one.

A test that only showed "every URL is refused" would be worthless evidence,
because a guard that refused for an unrelated reason -- a rejected host, a
malformed policy -- would pass it just as well. The positive control below is
what makes the refusals meaningful: driving the SAME shared guard with a
populated prefix tuple shows it admits exactly that prefix and still refuses
the payment sibling, so the blanket refusal above is attributable to the empty
allow-list and nothing else.
"""

from __future__ import annotations

import pytest

from ......tests.aeat_literal_fixtures import (
    DEUDAS_CONSULTA_PATH_SHAPE_CANARY,
    DEUDAS_OFF_HOST_LANDING_CANARY,
    DEUDAS_PAYMENT_SURFACE_PATH_SHAPE_CANARIES,
    DEUDAS_READ_SURFACE_PATH_SHAPE_CANARIES,
    aeat_url,
)
from .. import assert_deudas_landing, deudas_read_path_prefixes
from .._adapter_utils import assert_read_landing
from .._deudas import _READ_GUARD_POLICY
from .._errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

# The landing shapes are declared centrally, so no test module owns an AEAT
# route literal, and the origin comes from the configured AEAT domain rather
# than a pinned host number.
_PAYMENT_SHAPED = tuple(aeat_url("www6", path) for path in DEUDAS_PAYMENT_SURFACE_PATH_SHAPE_CANARIES)
_READ_SHAPED = tuple(aeat_url("www6", path) for path in DEUDAS_READ_SURFACE_PATH_SHAPE_CANARIES)

# A relative path has no establishable origin, which is its own refusal reason.
_UNREADABLE = ("", "about:blank", DEUDAS_CONSULTA_PATH_SHAPE_CANARY, None)


def test_the_allow_list_ships_empty() -> None:
    """The fail-closed-by-construction claim, asserted on the real tuple.

    An empty tuple is what makes every refusal below unconditional. A later
    change can only NARROW what is refused by adding an observed prefix; it
    cannot widen the surface by having forgotten to add the guard.
    """
    assert deudas_read_path_prefixes() == ()


@pytest.mark.parametrize("landing", _PAYMENT_SHAPED)
def test_a_payment_or_aplazamiento_landing_is_refused(landing: str) -> None:
    """The landings that would put a taxpayer's money one navigation away."""
    with pytest.raises(SedeNavigationError):
        assert_deudas_landing(landing)


@pytest.mark.parametrize("landing", _READ_SHAPED)
def test_even_a_plausible_read_landing_is_refused_while_no_specimen_exists(landing: str) -> None:
    """A read-SHAPED path is refused too, and that is the intended state.

    Admitting a plausible-looking consulta path would assert an observation
    nobody made. The guard stays shut until a capture establishes the real one.
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
    """Positive control: the same guard PERMITS when a prefix is declared.

    This is the assertion that gives the blanket refusals their meaning. The
    guard is driven here with a populated single-entry tuple -- a real argument
    to the real shared function, not a patched module -- and it admits exactly
    that prefix while still refusing the payment sibling beside it. The
    refusals above are therefore caused by the empty allow-list, which is the
    property under test, rather than by a host rejection or a broken policy
    that would refuse no matter what.
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
