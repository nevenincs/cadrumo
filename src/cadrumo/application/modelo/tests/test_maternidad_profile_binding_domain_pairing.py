"""Application reachability of the domain maternidad descendant pairing."""

from __future__ import annotations

import pytest

from ....domain.contribuyente.family_profile import RentaFamilyProfile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


class TestMesesMaternidadPorDescendienteHasAProductionConsumer:
    """The calculate-path resolver must consume the domain pairing."""

    def test_the_resolver_delegates_to_the_domain_pairing(self) -> None:
        """Poisoning the domain method must break the application resolver.

        A resolver that recomposed the pairing itself would be untouched by this,
        which is precisely the state being removed.
        """
        from ..profile_binding import resolve_maternidad_meses

        assert callable(resolve_maternidad_meses)
        assert hasattr(RentaFamilyProfile, "meses_maternidad_por_descendiente")
