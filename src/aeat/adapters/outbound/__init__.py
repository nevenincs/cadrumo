"""Outbound adapter namespace for external service integrations.

This package root exports no provider classes. Focused child packages group
concrete integrations by external counterpart: :mod:`aeat.adapters.outbound.aeat`
for AEAT Sede authentication, browser, read, verify, and export adapters;
:mod:`aeat.adapters.outbound.google` for Google-backed collaboration services;
:mod:`aeat.adapters.outbound.llm` for model-provider completion adapters;
:mod:`aeat.adapters.outbound.fx` for exchange-rate acquisition; and
:mod:`aeat.adapters.outbound.storage` for outbound storage synchronisation.

Application-layer facades define the stable protocols and operator actions.
Outbound adapters provide concrete implementations without becoming import-time
dependencies of state-free command paths.

See Also:
    :mod:`aeat.adapters.outbound.aeat`
        AEAT Sede authentication, browser, read, verify, and export adapter
        boundary.
    :mod:`aeat.application.auth`
        Application auth facade that selects providers and owns operator-facing
        session lifecycle commands.
    :mod:`aeat.application.live`
        Read-only live acquisition facade that consumes outbound AEAT adapters.
    :mod:`aeat.core.access_gate`
        Core live-read gate and permanent live-write refusal enforced before
        outbound AEAT access proceeds.
"""
