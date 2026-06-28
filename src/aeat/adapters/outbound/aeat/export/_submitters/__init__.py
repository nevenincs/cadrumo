"""Empty namespace for the permanently absent AEAT remote submitter.

The project has no outbound submitter ABC, browser-session submitter, or
remote filing transport. Live AEAT submission and write-shaped portal
walks are permanently forbidden, so this package intentionally exports
nothing; ``__all__`` is the empty list and star imports surface no names.

The canonical refusal lives outside the adapter layer:
:meth:`aeat.core.access_gate.AeatAccessGate.require_live_write` always
raises :class:`aeat.core.access_gate.LiveSubmitForbiddenError`. Local
filing state is modeled separately by :mod:`aeat.domain.submission`, and
file generation remains a local export concern under
:mod:`aeat.adapters.outbound.aeat.export`.

See Also:
    :mod:`aeat.core.access_gate`
        Core live-read gate and unconditional live-write refusal.
    :class:`aeat.core.access_gate.LiveSubmitForbiddenError`
        Typed error raised for every attempted live AEAT write.
    :func:`aeat.application.filing.export_draft`
        Local fichero-BOE file generation path; it writes disk artefacts,
        not remote submissions.
"""

from __future__ import annotations

__all__: list[str] = []
