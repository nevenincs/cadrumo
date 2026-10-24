"""Project the navigation register into the desktop's ``navigation.json``.

The window and its host read one generated projection of the register instead
of a hand-kept vocabulary: every element with its parent, label key, keywords,
surfaces and link parameters, every value kind, the retired ids, and the link
grammar's limits. The register is read only through its validating client
loader, so a register the loader refuses never reaches the desktop.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from cadrumo_client.contracts.navigation import (
    MAX_VIEW_ID_SEGMENTS,
    MAX_VIEW_LINK_LENGTH,
    NAVIGATION_SCHEMA_VERSION,
    PREFER_KEY,
    VIEW_LINK_PREFIX,
    NavigationRegister,
    NavigationRegisterError,
    NavigationSurface,
    load_navigation_register,
)

from .stable_output import write_text

#: The generated file's name in the desktop frontend's generated inputs.
NAVIGATION_OUTPUT = "navigation.json"


def navigation_projection(register: NavigationRegister) -> dict[str, object]:
    """Return the register as the desktop reads it, in declaration order."""
    return {
        "schema": NAVIGATION_SCHEMA_VERSION,
        "link": {
            "prefix": VIEW_LINK_PREFIX,
            "max_length": MAX_VIEW_LINK_LENGTH,
            "max_segments": MAX_VIEW_ID_SEGMENTS,
            "prefer_key": PREFER_KEY,
        },
        "surfaces": [surface.value for surface in NavigationSurface],
        "kinds": [{"name": kind.name, "alphabet": kind.alphabet, "length": kind.length} for kind in register.kinds],
        "retired": list(register.retired),
        "elements": [
            {
                "id": element.id,
                "parent": element.parent,
                "label": element.label,
                "keywords": element.keywords,
                "surfaces": [surface.value for surface in element.surfaces],
                "params": dict(sorted(element.params.items())),
            }
            for element in register.elements
        ],
    }


def render_navigation(register: NavigationRegister) -> str:
    """Serialize the projection deterministically as UTF-8 JSON."""
    return json.dumps(navigation_projection(register), ensure_ascii=False, indent=2) + "\n"


def main(argv: Sequence[str] | None = None) -> int:
    """Write the desktop's navigation projection."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    # The build names where its generated inputs go; nothing is written into the source tree.
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    output: object = arguments.output
    if not isinstance(output, Path) or output.name != NAVIGATION_OUTPUT:
        parser.error(f"--output must name the generated {NAVIGATION_OUTPUT}")
    try:
        rendered = render_navigation(load_navigation_register())
    except NavigationRegisterError as error:
        parser.exit(1, f"refused: {error}\n")
    output.parent.mkdir(parents=True, exist_ok=True)
    write_text(output, rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
