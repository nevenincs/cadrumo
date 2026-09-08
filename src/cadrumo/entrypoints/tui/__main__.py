"""Module execution for the independent full-screen root."""

from __future__ import annotations

from .launcher import InstalledWorkbenchRootInputsProviderV1, main

_SELF_TEST_FLAG = "--self-test"
_MODULE_ARGUMENT_ERROR_EXIT_CODE = 2


class TuiModuleArgumentError(ValueError):
    """Arguments outside the independent TUI root's closed invocation surface."""


def run(
    arguments: list[str],
    *,
    workbench_root_inputs_provider: InstalledWorkbenchRootInputsProviderV1 | None = None,
) -> int:
    """Start the root session, retaining only the TUI-owned self-test flag."""
    if arguments not in ([], [_SELF_TEST_FLAG]):
        raise TuiModuleArgumentError(f"unrecognised TUI module arguments: {arguments!r}")
    return main(
        headless=arguments == [_SELF_TEST_FLAG],
        workbench_root_inputs_provider=workbench_root_inputs_provider,
    )


if __name__ == "__main__":
    import sys

    try:
        raise SystemExit(run(sys.argv[1:]))
    except TuiModuleArgumentError as exc:
        sys.stderr.write(f"error: {exc}\n")
        raise SystemExit(_MODULE_ARGUMENT_ERROR_EXIT_CODE) from None
