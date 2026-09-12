"""Inert namespace for outbound storage providers.

Protocols, records, factories, mirror-manifest helpers, pagination guards, and
errors are imported from their defining modules. Concrete backends live in
:mod:`adapters.outbound.storage.local` and
:mod:`adapters.outbound.storage._google_drive`. The package initializer owns
and exports no symbols.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
