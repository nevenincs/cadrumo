"""Build-time compilers projecting registry data into docs search records.

This package is dev build tooling (alongside ``dev/docs/cli_reference.py``
and ``dev/docs/apidocs``), not shippable ``src/cadrumo`` code: the projected
records are a build-time artifact consumed by the downstream Pagefind
injection, never committed (like the generated CLI reference). The casilla
records are MACHINE-GENERATED from registry snapshots and never hand-curated,
distinct from the curated ``dev.docs.terminology_handbook`` concept Handbook.

Every symbol this package defines is imported from the module that defines it;
this initialiser is an inert namespace marker and forwards nothing.
"""
