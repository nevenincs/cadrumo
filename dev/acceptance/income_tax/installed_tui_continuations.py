"""Run installed CLI/TUI continuation acceptance with value-free receipts."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from dev.acceptance.installed_cli import InstalledCliError

from .cli_journey import (
    JourneyError,
)
from .continuation_contracts import _SCHEMA_VERSION, InstalledContinuationError, InstalledContinuationEvidence
from .continuation_request import _requested_continuation_evidence
from .installed_tui_child import (
    InstalledTuiChildError,
    write_installed_tui_failure_receipt,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cli", type=Path)
    parser.add_argument("--python", type=Path)
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--authority-root", type=Path)
    parser.add_argument("--output-root", type=Path)
    parser.add_argument("--scratch", type=Path)
    parser.add_argument("--year", type=int)
    parser.add_argument("--receipt", required=True, type=Path)
    parser.add_argument("--child-direction", choices=("cli_to_tui", "tui_to_cli"))
    parser.add_argument("--only-direction", choices=("cli_to_tui", "tui_to_cli"))
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run a parent receipt or one stdin-credentialed installed TUI child."""
    args = _parser().parse_args(argv)
    try:
        evidence = _requested_continuation_evidence(args)
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(
            json.dumps(
                evidence.to_dict() if isinstance(evidence, InstalledContinuationEvidence) else evidence,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        return 0
    except (JourneyError, InstalledCliError) as exc:
        phase = str(exc).split(":", 1)[0]
        safe_phases = {"profile creation failed", "CLI invocation failed", "CLI returned no JSON"}
        reason = phase if phase in safe_phases else "installed CLI partial workflow failed"
        trace = exc.__traceback__
        while trace is not None:
            if Path(trace.tb_frame.f_code.co_filename).name in {"cli_journey.py", "installed_tui_continuations.py"}:
                reason += f" [{trace.tb_frame.f_code.co_name}]"
            trace = trace.tb_next
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(reason),
        )
        return 2
    except (InstalledContinuationError, InstalledTuiChildError) as exc:
        write_installed_tui_failure_receipt(
            path=args.receipt, schema_version=_SCHEMA_VERSION, error=InstalledTuiChildError(str(exc))
        )
        return 2
    except Exception as exc:
        write_installed_tui_failure_receipt(
            path=args.receipt,
            schema_version=_SCHEMA_VERSION,
            error=InstalledTuiChildError(f"unexpected continuation failure: {type(exc).__name__}"),
        )
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
