"""Write the reference an agent reads to go from a command to the tools that do its work.

The recorded join of commands to operations and the declared counterparts are
the authority and the reference is their copy. Write it again after either
changes; a test beside the command tests holds the two together::

    python -m dev.harness_data.command_operation_reference
"""

from __future__ import annotations

from cadrumo.entrypoints.cli.operator_surface_reconciliation import recorded_command_operation_join
from cadrumo.entrypoints.cli.tests.command_operation_reference import (
    REFERENCE_PATH,
    render_command_operation_reference,
)


def main() -> int:
    """Write the reference from the recorded join."""
    join = recorded_command_operation_join()
    REFERENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    REFERENCE_PATH.write_text(render_command_operation_reference(join), encoding="utf-8", newline="\n")
    print(f"wrote {REFERENCE_PATH} ({len(join.commands)} commands)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
