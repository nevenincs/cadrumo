"""Compare direct and CMD launch of the actual staged desktop executable."""

import os
import sys
from pathlib import Path

from ..command_execution import run_command


def main() -> None:
    """Require the staged image to launch identically through direct and CMD dispatch."""
    executable = Path(sys.argv[1]).resolve(strict=True)
    version, storage_variable = sys.argv[2:4]
    directory = Path(sys.argv[4]).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    shell = Path(os.environ["SYSTEMROOT"]) / "System32" / "cmd.exe"
    if not shell.is_absolute() or not shell.is_file():
        raise AssertionError("The Windows system command interpreter is unavailable")

    for explicit_storage in (False, True):
        environment = {
            key: value
            for key, value in os.environ.items()
            if key.upper() != "CADRUMO_DESKTOP_PACKAGE_ROOT"
            and (explicit_storage or key.upper() != storage_variable.upper())
        }
        environment["CADRUMO_TEST_IMAGE"] = f'"{executable}"'
        for argument in ("--version", "--help"):
            results = []
            for command in (
                [str(executable), argument],
                [str(shell), "/d", "/c", "%CADRUMO_TEST_IMAGE%", argument],
            ):
                result = run_command(
                    command,
                    cwd=directory,
                    environment=environment,
                    input_text="",
                    timeout_seconds=60,
                )
                if result.returncode != 0 or result.stderr or not result.stdout:
                    raise AssertionError(
                        f"Packaged launch failed (CMD={command[0] == str(shell)}, "
                        f"explicit_storage={explicit_storage}, argument={argument}): "
                        f"exit={result.returncode}, stderr={result.stderr!r}"
                    )
                results.append(result.stdout)
            if results[0] != results[1]:
                raise AssertionError("CMD and direct packaged launch produced different output")
            if argument == "--version" and results[0].strip() != f"CADRUMO {version}":
                raise AssertionError("Packaged launch reported an unexpected product version")
        sys.stdout.write(f"Direct/CMD packaged launch passed (explicit_storage={explicit_storage})\n")


if __name__ == "__main__":
    main()
