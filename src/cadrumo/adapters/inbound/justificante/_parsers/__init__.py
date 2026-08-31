"""Private text-backend dispatch for the inbound justificante adapter.

Callers outside :mod:`adapters.inbound.justificante` must never import
from here. Backends expose a common ``extract_text`` entry point that
returns the raw concatenated text of a justificante PDF; all field-level
extraction happens in :mod:`adapters.inbound.justificante._extract`.

The dispatch is keyed on
:class:`domain.justificante.JustificanteParserBackend`, and parse
failures are normalised as
:class:`domain.justificante.JustificanteParseError`. The path entry point
caches concatenated text by source digest, backend, size, and mtime; the bytes
entry point stays uncached so secure-storage callers do not need to materialise
or persist plaintext files.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
