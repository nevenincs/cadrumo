"""Import-light namespace for user-facing entrypoints.

Concrete transports live in child packages, currently the Typer CLI under
:mod:`aeat.entrypoints.cli`. The root exports no commands and should remain a
marker so importing :mod:`aeat.entrypoints` does not initialise command trees,
locale catalogues, browser integrations, or storage sessions.

Entrypoints translate process-level concerns into application-facade calls. They
own presentation, command parsing, exit-code mapping, and terminal error
contracts; business decisions stay in :mod:`aeat.application` and
:mod:`aeat.domain`.
"""
