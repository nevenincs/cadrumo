"""Storage-layer orchestration: secure object stores plus calc-sheet engine.

This package is a namespace container. Callers must import from the subpackages
directly (e.g. ``aeat.application.storage.calc_sheets``); nothing is re-exported
at this level by design. Exporting here would couple callers to the internal
subpackage layout and undermine the layered-import discipline.
"""
