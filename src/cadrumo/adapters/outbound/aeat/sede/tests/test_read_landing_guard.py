"""Proof for the shared sede landing refusal.

The landing refusal is the only wall in this package that sees where AEAT
actually dispatched a read. Its siblings each miss a browser-driven
navigation by construction: the package's forbidden-verb source scan
deliberately permits ``click`` / ``fill`` / ``press`` because reads here
are driven by submitting consulta forms, and the HTTP guard is consulted
only for a first-party request, never for the form POST a click issues.

This file exercises the real production helper rather than a mirrored
copy of its rule. A copy would keep agreeing with itself after the rule
changed shape, which is the failure mode that makes a no-write proof
worthless.

Every AEAT path used here is a declared canary or a configured path; the
file names no AEAT literal of its own.
"""

from __future__ import annotations

import pytest

from ......domain.calculations.registry import RemoteStateGuardPolicy
from ......tests.aeat_literal_fixtures import (
    CENSAL_M036_FILING_TOOL_PATH_CANARY,
    CENSAL_MODIF_DOMICILIO_FISCAL_PATH_CANARY,
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    LIVE_PARITY_SUBMIT_PATH_CANARY,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY,
    aeat_host,
    aeat_url,
    configured_path,
)
from .._adapter_utils import assert_read_landing
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


_SURFACE = "test-surface"
_READ_PATH = configured_path("sede_paths", "declarations_listing")
_READ_PREFIX = _READ_PATH.removesuffix("/index.zul")

_POLICY = RemoteStateGuardPolicy(
    id="aeat-sede-landing-guard-proof",
    evidence_tier="official_source_guidance",
    classification="authenticated_read_surface",
    allowed_hosts=(aeat_host("sede"),),
    synthetic_data_allowed=False,
    requires_authentication=True,
    requires_aeat_authorization=True,
)


def _assert_landing(landing_url: str | None, *, prefixes: tuple[str, ...] = (_READ_PREFIX,)) -> None:
    assert_read_landing(
        landing_url,
        surface=_SURFACE,
        policy=_POLICY,
        allowed_path_prefixes=prefixes,
    )


class TestDeclaredReadPagesAreReachable:
    """The guard must not refuse the pages the surface exists to read."""

    def test_the_declared_read_page_is_admitted(self) -> None:
        _assert_landing(aeat_url("sede", _READ_PATH))

    def test_a_deeper_path_under_the_declared_prefix_is_admitted(self) -> None:
        _assert_landing(aeat_url("sede", f"{_READ_PREFIX}/detalle"))

    def test_a_query_string_does_not_defeat_the_prefix_match(self) -> None:
        _assert_landing(f"{aeat_url('sede', _READ_PATH)}?EJER=2024")


class TestWriteSurfacesAreRefused:
    """A landing on a real AEAT write surface must be refused."""

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_every_known_censal_write_surface_is_refused(self, write_path: str) -> None:
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("sede", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("sede", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"))

    def test_a_write_surface_is_refused_even_when_declared_as_a_read_page(self) -> None:
        """The policy's write-token scan holds when the allow-list is wrong.

        The two checks are complementary: the path allow-list catches an
        AEAT write path carrying no write verb, and the policy scan
        catches a write verb the allow-list was mistakenly widened to
        admit. This asserts the second half by declaring the submit path
        as a read page and requiring the refusal to survive it.
        """
        with pytest.raises(SedeNavigationError):
            _assert_landing(
                aeat_url("sede", LIVE_PARITY_SUBMIT_PATH_CANARY),
                prefixes=(LIVE_PARITY_SUBMIT_PATH_CANARY,),
            )

    def test_the_filing_tool_carries_no_write_verb_so_the_allow_list_is_load_bearing(self) -> None:
        """The allow-list, not the token scan, is what refuses the M036 tool.

        Establishes that the path check is doing real work rather than
        shadowing a refusal the policy would have produced anyway: with
        the filing tool declared as a read page, the policy admits it.
        """
        assert_read_landing(
            aeat_url("sede", CENSAL_M036_FILING_TOOL_PATH_CANARY),
            surface=_SURFACE,
            policy=_POLICY,
            allowed_path_prefixes=(CENSAL_M036_FILING_TOOL_PATH_CANARY,),
        )
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("sede", CENSAL_M036_FILING_TOOL_PATH_CANARY))


class TestUnrecognisedLandingsFailClosed:
    """An unrecognised landing is a refusal, never a pass."""

    def test_an_unknown_aeat_state_surface_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("sede", UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY))

    def test_the_site_root_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("sede", "/"))

    @pytest.mark.parametrize("landing_url", ["", None, "about:blank", _READ_PATH])
    def test_a_landing_with_no_usable_origin_is_refused(self, landing_url: str | None) -> None:
        with pytest.raises(SedeNavigationError):
            _assert_landing(landing_url)

    def test_a_surface_declaring_no_read_pages_refuses_its_own_read_page(self) -> None:
        """An empty allow-list refuses everything; it never admits a landing by default.

        This is the configuration most likely to arise by accident — a
        caller wiring the guard with a path tuple that resolves empty —
        so it must be the safe one.
        """
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("sede", _READ_PATH), prefixes=())


class TestOffPolicyAuthoritiesAreRefused:
    """The landing authority is decided by the policy, not by string shape."""

    def test_a_host_outside_the_policy_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            _assert_landing(aeat_url("www2", _READ_PATH))

    def test_a_lookalike_host_ending_in_the_aeat_apex_is_refused(self) -> None:
        from ......tests.aeat_literal_fixtures import AEAT_SUFFIX_LOOKALIKE_HOST_CANARY

        with pytest.raises(SedeNavigationError):
            _assert_landing(f"https://{AEAT_SUFFIX_LOOKALIKE_HOST_CANARY}{_READ_PATH}")


class TestRefusalIsDiagnostic:
    """A refusal must name what was refused, so an operator can act on it."""

    def test_the_refusal_names_the_surface_and_the_landed_path(self) -> None:
        with pytest.raises(SedeNavigationError) as excinfo:
            _assert_landing(aeat_url("sede", CENSAL_MODIF_DOMICILIO_FISCAL_PATH_CANARY))
        context = excinfo.value.context
        assert context is not None
        assert context["surface"] == _SURFACE
        assert context["landed_path"] == CENSAL_MODIF_DOMICILIO_FISCAL_PATH_CANARY
        assert context["allowed_path_prefixes"] == (_READ_PREFIX,)
