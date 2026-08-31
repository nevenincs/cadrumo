"""An unsatisfiable previous-filing carry is named, not dropped.

Every ``previous_filing`` binding in the registry carries a quantity that REDUCES
what the taxpayer owes: a pago fraccionado already paid, a negative result carried
forward, a prior-year valuation baseline. So a carry the local store cannot supply
does not produce a suspicious-looking return — it produces one declaring more tax
than is owed, arithmetically indistinguishable from a taxpayer who had no prior
filing at all.

Until this landed, `PreviousFilingSourceResolver` returned only ``binding_values``
and ``provenance``: no diagnostics and no unresolved binding ids, for any of the
bindings it could not satisfy. The gap was structural rather than accidental, and
it is the same gap seen from the other side as the registry declaring no
dependency treatment for those bindings — undeclared treatment and undetectable
failure are one hole with two faces.

The shape follows the `withholding` resolver, which already materialises its
value and emits a ``source_issue`` naming the source when its store is empty. This
is that established pattern applied to a family that never adopted it, not a new
mechanism.

Real behaviour throughout: real encrypted-SQLite observation store through
`isolated_runtime_profile`, real registry authority, the production resolver
class. No mock, stub, fake, skip or xfail.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.bindings import RegistryModeloObservation
from ....domain.calculations.registry.ids import BindingId
from ....tests.registry_observations import registry_grounded_observations
from ....tests.secure_sql import isolated_runtime_profile
from ...aggregation import CalculationSourceContext
from .._multi_year import PreviousFilingSourceResolver
from ..observations_repository import CalculationObservationRepository, ObservationSourceKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "10006042-0000-4000-8000-000000000001"
_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_YEAR = 2024
_TARGET_PERIOD = "2T"
_PRIOR_QUARTER = "1T"
_M130_PRIOR_PAGOS_BINDING: BindingId = "modelo-130-pagos-fraccionados-anteriores"
_M130_C07: CasillaId = validated_casilla_id("07", surface="_M130_C07")
_M130_C16: CasillaId = validated_casilla_id("16", surface="_M130_C16")
_M130_SALDO_NEGATIVO: CasillaId = validated_casilla_id(
    "saldo-negativo-fin-periodo",
    surface="_M130_SALDO_NEGATIVO",
)
#: The four Modelo 100 casillas the cross-modelo prior-year net-income carry sums.
_M100_NET_INCOME_CASILLAS: tuple[CasillaId, ...] = tuple(
    validated_casilla_id(token, surface="_M100_NET_INCOME_CASILLAS") for token in ("0224", "1479", "1553", "1577")
)


def _m130_snapshot():
    return bundled_authority().snapshot(
        Modelo.M130.value,
        filing_year=_YEAR,
        period=_TARGET_PERIOD,
    )


def _declared_previous_filing_binding_ids() -> frozenset[BindingId]:
    """Read the carry surface off the loaded revision rather than hardcoding it.

    A hardcoded id list would keep passing after a registry rename while silently
    testing nothing, and would pin a count this gate must not depend on.
    """
    binding_ids: set[BindingId] = set()
    for binding in _m130_snapshot().revision.bindings:
        if str(binding.source) != "previous_filing":
            continue
        binding_id = binding.id
        assert isinstance(binding_id, str)
        binding_ids.add(binding_id)
    return frozenset(binding_ids)


def _resolve(secure_objects: SecureObjectRepository):
    snapshot = _m130_snapshot()
    resolver = PreviousFilingSourceResolver(
        repository=CalculationObservationRepository(objects=secure_objects),
        registry_snapshot=snapshot,
    )
    return resolver.resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo=Modelo.M130.value,
            filing_year=_YEAR,
            period=Period.from_year_and_code(_YEAR, _TARGET_PERIOD),
            revision=snapshot.revision,
        ),
    )


def _seed_prior_quarter(secure_objects: SecureObjectRepository) -> None:
    """Persist the prior-trimestre Modelo 130 filing the same-modelo carries look for.

    Every casilla the prior-quarter carries require is supplied together. A
    PRESENT observation missing one of them does not resolve to a silent nothing —
    it raises a registry validation error naming the missing casilla — so a partial
    seed would exercise that refusal instead of the control this test is for.
    """
    CalculationObservationRepository(objects=secure_objects).save(
        CalculationObservationRepository(objects=secure_objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=Modelo.M130.value,
                filing_year=_YEAR,
                period=_PRIOR_QUARTER,
                observations=registry_grounded_observations(
                    modelo=Modelo.M130.value,
                    filing_year=_YEAR,
                    period=_PRIOR_QUARTER,
                    casilla_values={
                        _M130_C07: Decimal("412.55"),
                        _M130_C16: Decimal("0"),
                        _M130_SALDO_NEGATIVO: Decimal("0"),
                    },
                ),
            ),
            source_kind=ObservationSourceKind.APP_FILING,
            captured_at=_T0,
        )
    )
    # The cross-modelo prior-year net-income carry reads Modelo 100. Once ANY
    # observation is present the registry resolver refuses a still-absent
    # requirement rather than skipping it, so the control seeds the whole prior
    # history a taxpayer with a complete record would have.
    CalculationObservationRepository(objects=secure_objects).save(
        CalculationObservationRepository(objects=secure_objects).prepare_observation_envelope(
            RegistryModeloObservation(
                modelo=Modelo.M100.value,
                filing_year=_YEAR - 1,
                period="0A",
                observations=registry_grounded_observations(
                    modelo=Modelo.M100.value,
                    filing_year=_YEAR - 1,
                    period="0A",
                    casilla_values=dict.fromkeys(_M100_NET_INCOME_CASILLAS, Decimal("0")),
                ),
            ),
            source_kind=ObservationSourceKind.APP_FILING,
            captured_at=_T0,
        )
    )


def test_every_unsatisfiable_previous_filing_binding_is_named(tmp_path: Path) -> None:
    """With an empty store, each declared carry is named on the diagnostics channel.

    Gated on the PROPERTY — every declared previous-filing binding is named by some
    diagnostic — rather than on a diagnostic count, so adding or removing a carry in
    the registry cannot make this pass vacuously or force a constant to be updated.
    """
    declared = _declared_previous_filing_binding_ids()
    assert declared, "the M130 revision must declare previous-filing bindings for this gate to mean anything"

    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        resolution = _resolve(profile.repository)

    carry_diagnostics = tuple(
        diagnostic for diagnostic in resolution.diagnostics if diagnostic.source_kind == "previous_filing"
    )
    named = {diagnostic.binding_id for diagnostic in carry_diagnostics}
    assert declared <= named, (
        f"every declared previous-filing binding must be named when unsatisfiable; missing {declared - named}"
    )
    assert declared <= set(resolution.unresolved_binding_ids), (
        "an unsatisfiable carry must also surface as an unresolved binding id so the merge propagates it; "
        f"missing {declared - set(resolution.unresolved_binding_ids)}"
    )
    for diagnostic in carry_diagnostics:
        assert diagnostic.reason == "unresolved_binding"
        assert diagnostic.resolver_id == "previous_filing"
        # The message must locate the missing filing, not merely announce a gap.
        assert str(_YEAR - 1) in diagnostic.message or str(_YEAR) in diagnostic.message


def test_a_satisfiable_previous_filing_binding_stays_silent(tmp_path: Path) -> None:
    """The positive control: a carry the store CAN satisfy is not named.

    Without this, "emits on failure" is indistinguishable from "emits always", and
    the gate above would pass against a resolver that named every binding
    unconditionally.
    """
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        _seed_prior_quarter(profile.repository)
        resolution = _resolve(profile.repository)

    named = {
        diagnostic.binding_id for diagnostic in resolution.diagnostics if diagnostic.source_kind == "previous_filing"
    }
    assert _M130_PRIOR_PAGOS_BINDING in resolution.binding_values, (
        "the seeded prior trimestre must satisfy the pagos carry, or this control proves nothing"
    )
    assert _M130_PRIOR_PAGOS_BINDING not in named, (
        "a satisfied carry must NOT be named; the resolver would otherwise be reporting unconditionally"
    )
    assert _M130_PRIOR_PAGOS_BINDING not in set(resolution.unresolved_binding_ids)
