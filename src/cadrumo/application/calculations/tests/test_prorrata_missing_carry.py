"""Missing-provisional advisory for applicable prorrata ejercicios.

See Also:
    :func:`~application.calculations._prorrata_regularizacion.build_prorrata_missing_provisional_advisory`
        Pure no-silent-under-declaration diagnostic builder exercised here.
    :func:`~application.calculations._prorrata_regularizacion.derive_prorrata_applicability`
        Applicability projection that decides when the missing carry must be
        visible.
    :class:`~application.calculations._prorrata_regularizacion.ProrrataApplicabilityProjection`
        Typed evidence carrier consumed by the missing-carry builder.
    :class:`~domain.prorrata_register.ProrrataProvisionalResolution`
        Resolver output whose unresolved state triggers the diagnostic.
    :class:`~core.ProrrataRegisterRegime`
        Register regime enum used to prove active prorrata without declared
        volumes.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.prorrata_register import ProrrataRegisterRegime
from ....core.aggregation import BindingSourceKind
from ....domain.prorrata_register import (
    ProrrataProvisionalResolution,
    ProrrataRegisterEntry,
)
from .._prorrata_regularizacion import (
    CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA,
    build_prorrata_missing_provisional_advisory,
    derive_prorrata_applicability,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _unresolved() -> ProrrataProvisionalResolution:
    return ProrrataProvisionalResolution(percentage=None, provenance=None)


def test_missing_provisional_advisory_names_prior_definitive_follow_up() -> None:
    applicability = derive_prorrata_applicability(
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("80000.00"),
    )

    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=_unresolved(),
        ejercicio=2026,
    )

    assert diagnostic is not None
    assert diagnostic.binding_source is BindingSourceKind.PRORRATA_REGULARIZACION
    assert diagnostic.casilla_id == CASILLA_REGULARIZACION_PRORRATA_DEFINITIVA
    assert "2026" in diagnostic.message
    assert "definitiva del ejercicio anterior" in diagnostic.message
    assert "por defecto" in diagnostic.message


def test_missing_provisional_advisory_names_inicio_action_for_first_ejercicio() -> None:
    applicability = derive_prorrata_applicability(
        register_entries=(
            ProrrataRegisterEntry(ejercicio=2026, regime=ProrrataRegisterRegime.GENERAL, especial_transition=None),
        ),
    )

    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=_unresolved(),
        ejercicio=2026,
        first_ejercicio=True,
    )

    assert diagnostic is not None
    assert "inicio de actividad" in diagnostic.message


def test_missing_provisional_advisory_is_silent_when_prorrata_does_not_apply() -> None:
    applicability = derive_prorrata_applicability(
        register_entries=(
            ProrrataRegisterEntry(ejercicio=2026, regime=ProrrataRegisterRegime.NINGUNA, especial_transition=None),
        ),
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("100000.00"),
    )

    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=_unresolved(),
        ejercicio=2026,
    )

    assert diagnostic is None


def test_missing_provisional_advisory_is_silent_when_ladder_resolves() -> None:
    applicability = derive_prorrata_applicability(
        declared_volume_total=Decimal("100000.00"),
        declared_volume_con_derecho=Decimal("80000.00"),
    )

    diagnostic = build_prorrata_missing_provisional_advisory(
        applicability=applicability,
        provisional_resolution=ProrrataProvisionalResolution(percentage=Decimal("75"), provenance=None),
        ejercicio=2026,
    )

    assert diagnostic is None
