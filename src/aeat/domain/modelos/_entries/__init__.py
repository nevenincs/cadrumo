"""Per-modelo registry entries.

Each module in this subpackage exposes a single module-level
``ENTRY: ModeloMetadata``. The canonical import point is
``aeat.domain.modelos._registry``, which collects every ``ENTRY`` into the
public ``MODELO_REGISTRY`` mapping.
"""

from __future__ import annotations
