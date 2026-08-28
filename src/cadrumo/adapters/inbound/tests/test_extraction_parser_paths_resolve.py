"""Adapter-legal resolution gate for registry extraction-parser dotted paths.

The domain registry validator (:func:`validate_dotted_callable`) checks only the
STRUCTURAL shape of a ``parser =`` dotted path, so the domain registry validation
stays free of any ``adapters`` coupling (the ports-inversion boundary: the domain
must not name or import a parser module, even by string). This gate enforces the
other half: every ``parser =`` path declared anywhere in the bundled
registry resolves to a real callable under a sanctioned parser authority — from
the adapter layer, where importing ``cadrumo.adapters.inbound`` parsers is legal.

The registry is bundled, shipped data, so a CI gate is the authoritative
resolution check: a ``parser =`` path that is structurally valid but names a
non-existent / non-callable target, or a target outside the sanctioned parser
authorities, fails here. This is the adapter-owned complement to the
ports-inversion boundary.

See Also:
    :func:`~domain.calculations.registry._validate_extraction_profiles.validate_dotted_callable`
        Domain-side structural validator that deliberately avoids importing
        adapter parser modules.
    :func:`~adapters.inbound.declaracion.parse_declaracion`
        Registry-profile-driven declaración parser facade referenced by
        shipped extraction profiles.
    :func:`~adapters.inbound.borrador.parse_borrador`
        Borrador parser facade allowed as a sanctioned parser authority.
    :mod:`~domain.calculations.registry.tests.test_registry_schema_part2`
        Domain-layer regression proving only dotted-callable shape is checked.
"""

from __future__ import annotations

import re
from importlib import import_module
from pathlib import Path

import pytest

from ....core.directory_scan import scan_directory

pytestmark = [pytest.mark.unit, pytest.mark.hex_inbound_adapter]

# Sanctioned parser authorities: the two inbound-PDF parser packages, plus the
# registry's own in-tree export-payload parser (a domain-internal callable).
_ALLOWED_PARSER_AUTHORITY_PREFIXES: tuple[str, ...] = (
    "cadrumo.adapters.inbound.borrador",
    "cadrumo.adapters.inbound.declaracion",
    "cadrumo.domain.calculations.registry",
)

_REGISTRY_ROOT = Path(__file__).parents[3] / "_data" / "registry"
_PARSER_LINE_RE = re.compile(r'^\s*parser\s*=\s*"([^"]+)"', re.MULTILINE)


def _declared_parser_paths() -> list[str]:
    """Every distinct ``parser =`` dotted path declared in the bundled registry TOML."""
    paths: set[str] = set()
    for toml_path in scan_directory(_REGISTRY_ROOT, pattern="*.toml", recursive=True):
        paths.update(_PARSER_LINE_RE.findall(toml_path.read_text(encoding="utf-8")))
    return sorted(paths)


def test_bundled_registry_declares_parser_paths() -> None:
    """Anti-vacuity guard: the scan must find parser paths, else the gate is empty.

    If the registry layout or the ``parser =`` key changes and this scan silently
    returns nothing, the parametrized resolution gate below would pass with zero
    cases — a false green. This test fails loudly in that event.
    """
    assert _declared_parser_paths(), (
        f"no 'parser =' paths found under {_REGISTRY_ROOT}; the registry layout or the "
        "scan changed and the resolution gate would be vacuous"
    )


def test_extraction_parser_paths_resolve() -> None:
    """Each registry ``parser =`` path resolves to a callable under a sanctioned authority."""
    failures: list[str] = []
    for dotted_path in _declared_parser_paths():
        module_name, separator, attribute = dotted_path.rpartition(".")
        if not separator or not module_name or not attribute:
            failures.append(f"parser {dotted_path!r} is not a dotted callable path")
            continue
        if not module_name.startswith(_ALLOWED_PARSER_AUTHORITY_PREFIXES):
            failures.append(
                f"parser {dotted_path!r} must resolve under one of {sorted(_ALLOWED_PARSER_AUTHORITY_PREFIXES)!r}",
            )
            continue
        module = import_module(module_name)
        resolved = getattr(module, attribute, None)
        if not callable(resolved):
            failures.append(f"parser {dotted_path!r} does not resolve to a callable")

    assert not failures, "\n".join(failures)
