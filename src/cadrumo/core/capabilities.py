"""Closed set of operator-selectable service capabilities.

A *capability* is a per-profile opt-in/opt-out of an external service the app can
use. It is operator intent, distinct from (a) the global safety posture (gestor
mode, the secure-storage invariant) and (b) dependency availability (is Ollama
running?). The three axes are ANDed at the gate, and a capability may only NARROW
the global safety floor, never widen it.

The set is declared here in ``core/`` — the innermost hexagonal ring — so the
Typer boundary renders the accepted-value ``Choice([...])`` from the enum,
production code routes on members, and the profile schema / resolver / doctor
share one authority for the capability identifiers.

The :class:`ServiceCapability` members are consumed by
:func:`~application.user_profile.resolve_capability`,
:func:`~application.user_profile.resolve_active_capability`, and by the
setup wizard's capability questions. The product doctor renders those same
members beside :class:`~application.provisioning.DependencyStatus` rows
from :func:`~application.provisioning.probe_ollama_vision`,
:func:`~application.provisioning.probe_model_runtime_hardware_floor`, and
:func:`~application.provisioning.probe_optional_extras`, keeping operator
intent separate from dependency availability.

This enum is deliberately separate from
:attr:`domain.calculations.registry.ModeloDefinition.capabilities` and
:data:`domain.calculations.registry.ModeloFilingCapability`. Registry
capabilities describe which workflows a modelo definition supports; service
capabilities describe what an active profile permits the app to use.
"""

from __future__ import annotations

from enum import StrEnum


class ServiceCapability(StrEnum):
    """The closed set of external-service capabilities a profile can opt into.

    Each value is the dotted profile-schema field leaf under the ``capabilities``
    section (``capabilities.<value>``) so the enum, the schema fact path, and the
    resolver agree on one identifier. Optional package availability is modeled
    separately through :class:`~core.OptionalExtra` and
    :func:`~core.require_optional_extra`; a capability records whether the
    profile permits the service, not whether its import/runtime dependency is
    installed.

    See Also:
        :class:`~application.user_profile.CapabilityDecision`
            Resolved posture after applying gestor mode, profile facts, defaults,
            and global settings.
        :mod:`entrypoints.cli.config._capabilities_cli`
            Operator-facing ``show`` and ``set`` commands that expose these enum
            values directly.

    Members:
        LLM_VISION: Whether this profile may read scanned/image evidence on-host
            with the local Ollama vision model. Default ON (on-host, no byte
            leaves the machine); opting out disables the vision read entirely.
        GOOGLE_EXPORT: Whether this profile may export modelo workbooks to Google
            Sheets/Drive. Default ON; opting out keeps exports offline-only.
        CLOUD_EVIDENCE_UPLOAD: Whether this profile is ELIGIBLE to be offered the
            off-host evidence-read consent gate at all. Default OFF, and barred
            outright under gestor mode. This is the standing eligibility bar, a
            layer above the per-invocation acknowledgement: while it is off no
            token can be minted, so no surface offers the gate and "withdraw
            consent for the future" is one profile setting.
    """

    LLM_VISION = "llm_vision"
    GOOGLE_EXPORT = "google_export"
    CLOUD_EVIDENCE_UPLOAD = "cloud_evidence_upload"

    @property
    def schema_path(self) -> str:
        """Return the dotted profile-schema fact path for this :class:`ServiceCapability`."""
        return f"capabilities.{self.value}"

    @property
    def default_enabled(self) -> bool:
        """Return the conservative default posture when no profile fact is set.

        On-host vision and Google export default ON: both are local or
        non-sensitive by construction, so an unanswered question costs the
        operator a working feature and nothing else.
        :attr:`CLOUD_EVIDENCE_UPLOAD` is the one member that defaults OFF, and
        for the opposite reason -- an unanswered question there would decide,
        by silence, that a taxpayer's document may leave the machine. The
        resolver ANDs the global safety floor on top, yielding a
        :class:`~application.user_profile.CapabilityDecision`.
        """
        return self is not ServiceCapability.CLOUD_EVIDENCE_UPLOAD
