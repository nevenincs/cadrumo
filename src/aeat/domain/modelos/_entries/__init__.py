"""Per-modelo registry entries.

Each module in this subpackage exposes a single module-level
``ENTRY: ModeloMetadata`` value. The canonical import point is
:mod:`aeat.domain.modelos._registry`, which collects every ``ENTRY``
into the public :data:`aeat.domain.modelos._registry.MODELO_REGISTRY`
mapping.
"""

from __future__ import annotations
