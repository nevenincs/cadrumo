"""Per-modelo policy the modelo-agnostic filing-envelope renderer dispatches to.

The envelope GRAMMAR is one contract for every modelo -- prefix roles, relative
closer, emitted-byte total -- and lives in the generic renderer. What is not
shared is tax law: which records apply to which taxpayer, and which operator
elections a modelo's records make mandatory. Those stay per modelo, and they
arrive here as a registered row rather than as a branch inside the renderer.

Registering a modelo is therefore additive: a new row, and (where the modelo has
conditional records) its own applicability module. A modelo with no row is not
refused -- it simply carries no extra constraint beyond the generic ones the
renderer already proves -- because "this modelo declares no conditional record
family" is a legitimate state, not an unfinished one.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from pydantic import BaseModel, ConfigDict

from cadrumo.domain.calculations.registry.schema import RegistrySnapshot
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition

from ...core import Modelo, Period
from ._m303_export_applicability import validate_m303_export_applicability
from ._producer_snapshot import FilingProducerSnapshot

__all__ = [
    "FilingEnvelopeModeloPolicy",
    "filing_envelope_modelo_policy",
]


#: One modelo's applicability gate, called with the already-selected authority.
type FilingEnvelopeApplicabilityGate = Callable[..., None]


class FilingEnvelopeModeloPolicy(BaseModel):
    """The per-modelo constraints one registered modelo adds to envelope render."""

    model_config = ConfigDict(frozen=True, extra="forbid", arbitrary_types_allowed=True)

    #: Whether the modelo's records make the operator's prior-domiciliation
    #: election a mandatory explicit input rather than a defaulted one.
    requires_prior_domiciliation_election: bool = False
    #: The modelo's own exhaustive applicability gate, where it declares one.
    applicability_gate: FilingEnvelopeApplicabilityGate | None = None

    def validate_applicability(
        self,
        *,
        period: Period,
        registry_snapshot: RegistrySnapshot,
        layout: ExportLayoutDefinition,
        producer_snapshot: FilingProducerSnapshot,
    ) -> None:
        """Run the modelo's own applicability gate, where it registered one."""
        if self.applicability_gate is None:
            return
        self.applicability_gate(
            period=period,
            registry_snapshot=registry_snapshot,
            layout=layout,
            producer_snapshot=producer_snapshot,
        )


_POLICY_BY_MODELO: Mapping[Modelo, FilingEnvelopeModeloPolicy] = {
    Modelo.M303: FilingEnvelopeModeloPolicy(
        requires_prior_domiciliation_election=True,
        applicability_gate=validate_m303_export_applicability,
    ),
}

_NO_EXTRA_POLICY = FilingEnvelopeModeloPolicy()


def filing_envelope_modelo_policy(modelo: Modelo) -> FilingEnvelopeModeloPolicy:
    """Return the registered policy for ``modelo``, or the empty one."""
    return _POLICY_BY_MODELO.get(modelo, _NO_EXTRA_POLICY)
