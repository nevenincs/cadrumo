"""Closed set of operator-selectable service capabilities.

A *capability* is a per-profile opt-in/opt-out of an external service the app can
use. It is operator intent, distinct from (a) the global safety posture (gestor
mode, the secure-storage invariant) and (b) dependency availability (is Ollama
running?). The three axes are ANDed at the gate, and a capability may only NARROW
the global safety floor, never widen it (``service-capabilities`` ADR).

The set is declared here in ``core/`` — the innermost hexagonal ring — per
``aeat-schema-central-config`` and ``aeat-architecture-boundaries`` so the Typer
boundary renders the accepted-value ``Choice([...])`` from the enum, production
code routes on members, and the profile schema / resolver / doctor share one
authority for the capability identifiers.

The :class:`ServiceCapability` members are consumed by
:func:`aeat.application.user_profile.resolve_capability` and by the setup
wizard's capability questions.
"""

from __future__ import annotations

from enum import StrEnum


class ServiceCapability(StrEnum):
    """The closed set of external-service capabilities a profile can opt into.

    Each value is the dotted profile-schema field leaf under the ``capabilities``
    section (``capabilities.<value>``) so the enum, the schema fact path, and the
    resolver agree on one identifier.

    Members:
        CLOUD_EVIDENCE_UPLOAD: Whether this profile permits sending sensitive
            financial evidence (a text-layer invoice) to a cloud CLI provider for
            classification. Default OFF; gestor mode bars it absolutely regardless
            of this opt-in (the capability can only narrow, never widen, the floor).
        LLM_VISION: Whether this profile may read scanned/image evidence on-host
            with the local Ollama vision model. Default ON (on-host, no byte
            leaves the machine); opting out disables the vision read entirely.
        GOOGLE_EXPORT: Whether this profile may export modelo workbooks to Google
            Sheets/Drive. Default ON; opting out keeps exports offline-only.
    """

    CLOUD_EVIDENCE_UPLOAD = "cloud_evidence_upload"
    LLM_VISION = "llm_vision"
    GOOGLE_EXPORT = "google_export"

    @property
    def schema_path(self) -> str:
        """Return the dotted profile-schema fact path for this capability."""
        return f"capabilities.{self.value}"

    @property
    def default_enabled(self) -> bool:
        """Return the conservative default posture when no profile fact is set.

        Cloud evidence upload defaults OFF (the regulated, sensitive path); the
        on-host vision and Google export capabilities default ON because they are
        non-sensitive or local by construction. The resolver still ANDs the global
        safety floor on top of this default.
        """
        return self is not ServiceCapability.CLOUD_EVIDENCE_UPLOAD
