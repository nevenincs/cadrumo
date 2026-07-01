"""Import-light namespace for user-facing entrypoints.

Concrete transports live in child packages, currently the Typer CLI under
:mod:`aeat.entrypoints.cli`. The root exports no commands and should remain a
marker so importing :mod:`aeat.entrypoints` does not initialise command trees,
locale catalogues, browser integrations, or storage sessions.

Entrypoints translate process-level concerns into application-facade calls. They
own presentation, command parsing, exit-code mapping, and terminal error
contracts; business decisions stay in :mod:`aeat.application` and
:mod:`aeat.domain`.

See Also:
    :mod:`aeat.entrypoints.cli`
        Typer transport that mounts the operator command tree.
    :mod:`aeat.application.operator_surface`
        Backend-owned command-surface contract consumed by entrypoint adapters.
    :mod:`aeat.core.json_contract`
        Shared success-envelope, schema registry, and notice-channel contract.
    :mod:`aeat.core.errors`
        Central error envelope and exit-code mapping used at transport
        boundaries.
"""
