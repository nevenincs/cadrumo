"""Import-light namespace for user-facing entrypoints.

Concrete transports live in child packages, currently the Typer CLI under
:mod:`cli`. The root exports no commands and should remain a
marker so importing :mod:`entrypoints` does not initialise command trees,
locale catalogues, browser integrations, or storage sessions.

Entrypoints translate process-level concerns into application-facade calls. They
own presentation, command parsing, exit-code mapping, and terminal error
contracts; business decisions stay in :mod:`application` and
:mod:`domain`.

See Also:
    :mod:`cli`
        Typer transport that mounts the operator command tree.
    :mod:`application.operator_surface`
        Backend-owned command-surface contract consumed by entrypoint adapters.
    :mod:`core.json_contract`
        Shared success-envelope, schema registry, and notice-channel contract.
    :mod:`core.errors`
        Central error envelope and exit-code mapping used at transport
        boundaries.

Consumers import from the owning module -- :mod:`censal_review`,
:mod:`operation_composition`, :mod:`adapter_composition` -- rather than from
this package root, which is inert.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
"""Inert namespace: every contract is reached at the module that defines it."""
