"""Persistence adapters for operator profile state.

Re-exports the public surface of :mod:`aeat.adapters.persistence.profile.tax_residence`
so callers do not have to reach into the submodule. Sibling modules expose
encrypted ledger persistence for assets and inventory.
"""

from .tax_residence import (
    clear_json,
    clear_tax_residence,
    default_path,
    load_json,
    load_tax_residence,
    require_tax_residence,
    save_json,
    save_tax_residence,
)

__all__ = [
    "clear_json",
    "clear_tax_residence",
    "default_path",
    "load_json",
    "load_tax_residence",
    "require_tax_residence",
    "save_json",
    "save_tax_residence",
]
