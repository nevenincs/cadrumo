"""Per-portal entries backing :data:`domain.portals.PORTAL_REGISTRY`.

Each file under this package exposes a module-level
``ENTRY: PortalMetadata``. :mod:`domain.portals.registry` imports every
entry and stitches them into the frozen public registry.
"""
