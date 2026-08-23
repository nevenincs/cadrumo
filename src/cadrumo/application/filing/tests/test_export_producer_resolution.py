"""Every producer key a published export layout cites must be resolvable.

A record design says WHERE a value sits; a producer key says WHERE IT COMES FROM. Declaring
the key satisfies the filing-capability gate, which only asks whether a namespace exists.
Nothing asked whether anything actually produces the value.

It does not, for several modelos. `filing_producer_values` asserts it is exhaustive over
the keys owned by ``shared_snapshot`` and returns only those, so a key owned by a modelo
namespace resolves to nothing. `_header_field_value` then returns ``None`` for a field that
is not ``required``, which renders BLANK rather than refusing.

Modelo 222 is the worked example: 23 header fields cite ``m222.*`` keys, all
``required = false``, and nothing in ``src/`` resolves them -- so the fiscal-group pago
fraccionado emits with its número de grupo and its entidad dominante empty while every
other gate stays green. AEAT's own design prescribes a format for that field
(``Nota 8``: ``- - - - / - -`` estatal, ``- - - / - - A`` foral) on a return only groups
file.

The project already ruled on this. ADR ``2026-06-13-m303-form-vs-semantic-casilla-dual-keying``
states that "a layout containing any unsupported or deferred producer is physically
withdrawn with a grounded support-removal decision". A layout that ships one instead is
outside that decision, and until now nothing detected it.

This gate is the detector. It does not assert a tally -- it asserts the property that every
cited key resolves -- so it keeps biting as layouts are added.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from cadrumo.application.filing._export_producer import filing_producer_ownership

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_REGISTRY_MODELOS = Path(__file__).resolve().parents[3] / "_data" / "registry" / "aeat" / "modelos"
_PRODUCER_KEY = re.compile(r"""producer_key\s*=\s*['"]([^'"]+)['"]""")


def _cited_producer_keys() -> dict[str, set[str]]:
    """Return every producer key cited by a published export layout, by modelo."""
    cited: dict[str, set[str]] = {}
    for layout in _REGISTRY_MODELOS.glob("*/revisions/*/export/*.toml"):
        modelo = layout.relative_to(_REGISTRY_MODELOS).parts[0]
        for key in _PRODUCER_KEY.findall(layout.read_text(encoding="utf-8")):
            cited.setdefault(modelo, set()).add(key)
    return cited


def test_the_scan_finds_producer_keys_at_all() -> None:
    """Anti-tautology: a zero from this parser would make every assertion below vacuous.

    The export TOML uses SINGLE quotes. A pattern expecting double quotes returns an empty
    set and every resolution assertion passes for free -- which happened three times while
    this defect was being measured by hand.
    """
    cited = _cited_producer_keys()
    assert cited, "no export layout was read at all -- the scan is broken, not the tree"
    total = sum(len(keys) for keys in cited.values())
    assert total > 100, f"only {total} producer keys found across {len(cited)} modelo(s); the parse is suspect"


def test_every_cited_producer_key_is_resolvable() -> None:
    """Fail with the modelos whose layouts cite producers nothing can supply."""
    ownership = filing_producer_ownership()
    resolvable = {key.value for key, owner in ownership.items() if owner == "shared_snapshot"}
    declared = {key.value for key in ownership}

    undeclared: dict[str, set[str]] = {}
    unresolvable: dict[str, set[str]] = {}
    for modelo, keys in sorted(_cited_producer_keys().items()):
        for key in sorted(keys):
            if key not in declared:
                undeclared.setdefault(modelo, set()).add(key)
            elif key not in resolvable:
                unresolvable.setdefault(modelo, set()).add(key)

    assert not undeclared, (
        "export layout(s) cite a producer key that is not in the FilingProducerKey "
        f"vocabulary at all: { {m: sorted(k) for m, k in undeclared.items()} }"
    )

    assert not unresolvable, (
        f"{sum(len(k) for k in unresolvable.values())} producer key(s) across "
        f"{len(unresolvable)} modelo(s) are cited by a published export layout but are "
        "resolved by nothing: filing_producer_values() is exhaustive over the "
        "shared_snapshot-owned keys and returns only those, so these render BLANK on a "
        "non-required field instead of refusing. A return that emits its identifying "
        "header empty is worse than one that refuses.\n"
        + "\n".join(
            f"  modelo {modelo}: {len(keys)} unresolvable -- {', '.join(sorted(keys)[:4])}"
            + (" ..." if len(keys) > 4 else "")
            for modelo, keys in sorted(unresolvable.items())
        )
    )
