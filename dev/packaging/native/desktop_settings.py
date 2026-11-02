"""Generate desktop operational defaults from the canonical environment declaration."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from dev._paths import REPO_ROOT

from .application_environment import load
from .operational_settings import typescript_settings
from .stable_output import write_text


def main(argv: Sequence[str] | None = None) -> int:
    """Write only presentation settings, independent of package provisioning."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)
    output = arguments.output
    if output.name != "operational-settings.ts":
        parser.error("--output must name operational-settings.ts")
    rendered = typescript_settings(load(REPO_ROOT).settings)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_text(output, rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
