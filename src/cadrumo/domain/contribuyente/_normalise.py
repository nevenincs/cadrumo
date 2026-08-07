"""Canonical normalisation for profile-key lookups.

A profile key written by the operator (``TAX.ID``, ``tax-id``,
``  tax.id  ``) and a profile key stored in the registry (``tax.id``)
must compare equal. The normalisation strips surrounding whitespace,
lowercases, and folds dashes into dots. Underscores are preserved
verbatim so registry-canonical keys (``does_intracomunitario``,
``iva.roi_enrolled``) survive the round-trip through the user-CLI
store and reach the deadline engine, which looks values up by exact
key.

This is the only definition of the profile-key normaliser. Callers
import this function (or ``ProfileKey.normalise``, which forwards
here) and never re-implement the rule.

:func:`normalise_key` is the canonical lookup transform used by
:class:`ProfileKey` and the profile-key registry before matching operator
input against registry-owned profile paths.
"""

from __future__ import annotations


def normalise_key(value: str) -> str:
    """Return the canonical form of a profile key for registry lookup."""
    return value.strip().lower().replace("-", ".")


__all__ = ["normalise_key"]
