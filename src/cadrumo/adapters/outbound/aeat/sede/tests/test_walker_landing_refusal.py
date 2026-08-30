"""Landing refusals for the expedientes walker.

The walker's ``goto`` helper already re-asserts the LANDED url against
its policy, which is the right shape. Two gaps remained and are covered
here.

The re-assertion was skipped whenever the landed URL was empty, so the
one case where the outcome could not be established was the one case
that was not checked.

And the branch expansion JS-clicks every ``mostrarListado`` anchor in the
tree, after which the walker snapshots the DOM and parses it AS the
expedientes tree. Those anchors are AJAX expanders, so the page is
expected not to move -- but a navigation during expansion would be read
as a tree with no error anywhere: the parser would find no rows, and an
empty result is indistinguishable from a taxpayer with no expedientes.

Expediente DETAIL landings are deliberately not covered by a path
allow-list. Their URLs come off an ``href`` on the resumen page, so their
paths are not knowable here and any allow-list over them would be
invented rather than grounded; those navigations keep the policy check
alone, which is the honest strength for a page-supplied target.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import (
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY,
    aeat_url,
    configured_path,
)
from ..errors import SedeNavigationError
from ..walker import assert_landed_url_readable, assert_resumen_landing

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_AEAT = Settings.external_constants().aeat
_RESUMEN_PATH = configured_path("sede_paths", "expedientes_resumen")


class TestResumenLandingAfterExpansion:
    """The page parsed as the expedientes tree must be the resumen page."""

    def test_the_resumen_page_is_admitted(self) -> None:
        assert_resumen_landing(f"{_AEAT.domains.www6}{_RESUMEN_PATH}")

    def test_a_numbered_load_balancer_host_serving_the_resumen_is_admitted(self) -> None:
        """AEAT load-balances the authenticated surface; that dispatch is not a write."""
        assert_resumen_landing(f"{_AEAT.domains.www12}{_RESUMEN_PATH}")

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_a_real_aeat_write_surface_is_refused(self, write_path: str) -> None:
        """None of these carries a write verb; the path allow-list is what refuses them."""
        with pytest.raises(SedeNavigationError):
            assert_resumen_landing(aeat_url("www6", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_resumen_landing(aeat_url("www6", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"))

    def test_an_unrelated_aeat_page_is_refused_rather_than_parsed_as_a_tree(self) -> None:
        """The failure this closes is silent: a wrong page parses to zero rows.

        Zero expedientes is a legitimate result for a taxpayer with none,
        so a navigation during expansion would surface as an empty walk
        rather than as an error.
        """
        with pytest.raises(SedeNavigationError):
            assert_resumen_landing(aeat_url("www6", UNKNOWN_AEAT_STATE_SURFACE_PATH_CANARY))

    def test_the_auth_gate_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_resumen_landing(aeat_url("www6", configured_path("sede_paths", "auth_gate_4033")))


class TestUnreadableLandingIsRefused:
    """A navigation that produced no readable URL is refused, not skipped."""

    def test_a_readable_landing_is_returned_unchanged(self) -> None:
        landed = f"{_AEAT.domains.www6}{_RESUMEN_PATH}"
        assert assert_landed_url_readable(landed, requested_url=landed) == landed

    @pytest.mark.parametrize("landed", ["", "about:blank", _RESUMEN_PATH])
    def test_a_landing_with_no_usable_origin_is_refused(self, landed: str) -> None:
        with pytest.raises(SedeNavigationError):
            assert_landed_url_readable(landed, requested_url=f"{_AEAT.domains.www6}{_RESUMEN_PATH}")

    def test_the_refusal_names_the_requested_url(self) -> None:
        requested = f"{_AEAT.domains.www6}{_RESUMEN_PATH}"
        with pytest.raises(SedeNavigationError) as excinfo:
            assert_landed_url_readable("", requested_url=requested)
        context = excinfo.value.context
        assert context is not None
        assert context["requested_url"] == requested
