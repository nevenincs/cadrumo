"""Per-portal entries backing :data:`aeat.portals.PORTAL_REGISTRY`.

Each file under this package exposes a module-level
``ENTRY: PortalMetadata``. :mod:`aeat.portals._registry` imports every
entry and stitches them into the frozen public registry.
"""
