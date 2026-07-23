"""Registry-declared locale key discovery for the category profile registry.

The category profile TOML under ``registry/aeat/categories/profiles`` declares
operator-facing labels and notes as translation keys rather than prose. This
module is the fourth codebase-key discovery path beside the regex, AST, and
f-string scanners: those walk Python source, this walks the committed registry.

Kept separate from :mod:`locales._ast_scanner`, whose contract is Python-AST
walking; the registry is a TOML surface and shares no traversal machinery.
"""

from __future__ import annotations

from ..domain.categories import load_category_profile_registry


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
