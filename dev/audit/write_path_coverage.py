"""Render the persistence write-path analysis for diagnostic consumers.

The analyzer itself lives in ``dev.quality.write_path_coverage``. This module
owns only the finding-bearing diagnostic presentation and exit contract used
by the product write-path report; the blocking check consumes the same typed
result directly from the quality owner.
"""

from __future__ import annotations

import argparse
import sys

from dev.quality import write_path_coverage as _analysis


def main(argv: list[str] | None = None) -> int:
    """Run the shared analysis and report findings; exit 3 when found."""
    parser = argparse.ArgumentParser(
        description="Report persistence surfaces a product command reads but no production code writes.",
    )
    parser.add_argument("--json", action="store_true", help="Emit the result as JSON.")
    args = parser.parse_args(argv)

    result = _analysis.run_write_path_scan()
    print(_analysis.result_as_json(result) if args.json else _analysis.render_console_report(result))

    if result.outcome is _analysis.WritePathOutcome.ERROR:
        return 1
    if result.outcome is _analysis.WritePathOutcome.FINDINGS:
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
