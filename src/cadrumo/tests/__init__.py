"""Shared test package marker.

The package namespace is intentionally inert.  Test helpers are imported from
their defining modules so a package import cannot bind a cross-layer facade or
load support for an unrelated test cohort.
"""

__all__: tuple[str, ...] = ()
