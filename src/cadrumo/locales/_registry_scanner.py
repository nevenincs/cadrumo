"""Registry-declared locale key discovery for the committed registry trees.

Some operator-facing copy is declared as registry DATA rather than at a
Python call site, so the regex, AST, and f-string scanners -- all of which
walk Python source -- cannot see it. This module is the fourth discovery
path: it walks the committed registry.

Two registries declare keys, and they are scanned by separate functions
rather than one merged walk. The category profile registry names its keys
literally in TOML; the user-profile schema instead declares STRUCTURE, and
its keys are derived from that structure. Merging them would put an
unrelated registry inside :func:`scan_registry_keys`, whose caller-visible
contract (and pinned count) is the category-profile key universe.

Kept separate from :mod:`locales._ast_scanner`, whose contract is Python-AST
walking; the registry is a TOML surface and shares no traversal machinery.
"""

from __future__ import annotations

from ..domain.categories import load_category_profile_registry
from ..domain.user_profile import load_user_profile_schema, profile_schema_locale_keys


def scan_registry_keys() -> set[str]:
    """Return every locale key declared in the category profile registry.

    Citation quotes are excluded: they are verbatim AEAT excerpts and are
    authored as Spanish text in the registry TOML, never translated.

    Returns:
        The dotted translation keys declared across every year-keyed registry.
    """
    keys: set[str] = set()
    for profiles in load_category_profile_registry().values():
        for profile in profiles.values():
            keys.add(str(profile.display_label))
            keys.add(str(profile.proportionality.notes))
            for variant in profile.proportionality.statutory_cap_variants:
                keys.add(str(variant.label))
    return keys


def scan_profile_schema_keys() -> set[str]:
    """Return every locale key derived from the user-profile schema.

    The schema's section titles and field labels are keyed by structure, so
    a field added to the schema TOML declares its label key by construction.
    Enrolling them here is what makes such a field a parity failure rather
    than a row that silently renders its English-or-Spanish description.

    Returns:
        The dotted section-title and field-label keys the schema declares.
    """
    return profile_schema_locale_keys(load_user_profile_schema())
