"""Landing refusal for the declaraciones register search.

The navigation INTO the register already refused a landing outside the
register prefix. The other side of the search did not: Buscar is a real
submit control, and its landing was LOGGED and never checked, so a search
that left the register was recorded and then scraped.

That failure is silent, which is what makes it worth a rule. The row
parser finds no rows on a wrong page, and an empty listing is a
legitimate result for a taxpayer who filed nothing that ejercicio -- so
the walk returns zero declarations and nothing anywhere reports a
problem.

The rule is the same prefix the navigation check already requires rather
than a wider one, because Buscar is a ZK AJAX RPC and the page is not
expected to move across it.
"""

from __future__ import annotations

import pytest

from ......core.config import Settings
from ......tests.aeat_literal_fixtures import (
    CENSAL_WRITE_SURFACE_PATH_CANARIES,
    JUSTIFICANTE_WLPL_COTEJO_PATH_PREFIX_FIXTURE,
    PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE,
    aeat_url,
    configured_path,
)
from ..declarations import assert_declarations_read_landing
from ..errors import SedeNavigationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_AEAT = Settings.external_constants().aeat
_LISTING_PATH = configured_path("sede_paths", "declarations_listing")


class TestRegisterLandingIsAdmitted:
    """The register the search runs on must stay reachable."""

    def test_the_register_page_is_admitted(self) -> None:
        assert_declarations_read_landing(f"{_AEAT.domains.www6}{_LISTING_PATH}")

    def test_a_sibling_numbered_host_serving_the_register_is_admitted(self) -> None:
        """AEAT load-balances the authenticated surface across its www{n} pool."""
        assert_declarations_read_landing(f"{_AEAT.domains.www1}{_LISTING_PATH}")


class TestOffRegisterLandingsAreRefused:
    """A landing off the register is refused rather than parsed as a listing."""

    @pytest.mark.parametrize("write_path", CENSAL_WRITE_SURFACE_PATH_CANARIES)
    def test_a_real_aeat_write_surface_is_refused(self, write_path: str) -> None:
        """None of these carries a write verb; the path allow-list is what refuses them."""
        with pytest.raises(SedeNavigationError):
            assert_declarations_read_landing(aeat_url("www6", write_path))

    def test_the_procedure_launcher_family_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_declarations_read_landing(
                aeat_url("www6", f"{PROCEDIMIENTOINI_PATH_PREFIX_FIXTURE}G322.shtml"),
            )

    def test_the_auth_gate_landing_is_refused(self) -> None:
        """A session that expired mid-search must not yield an empty listing."""
        with pytest.raises(SedeNavigationError):
            assert_declarations_read_landing(aeat_url("www6", configured_path("sede_paths", "auth_gate_4033")))

    def test_a_sibling_surface_under_the_same_application_root_is_refused(self) -> None:
        """The cotejo surface shares the register's root but is not the register.

        Proves the allow-list is the register directory rather than its
        parent, which a prefix taken one segment too short would be.
        """
        with pytest.raises(SedeNavigationError):
            assert_declarations_read_landing(
                aeat_url("www6", f"{JUSTIFICANTE_WLPL_COTEJO_PATH_PREFIX_FIXTURE}ABC123"),
            )

    def test_an_unreadable_landing_is_refused(self) -> None:
        with pytest.raises(SedeNavigationError):
            assert_declarations_read_landing("")
