@echo off
REM Windows launcher for the aeat CLI.
REM
REM Plain `uv run aeat` resyncs the venv on every invocation, which races the
REM Windows process holding `Scripts/aeat.exe` open and raises os error 32.
REM This launcher forces `--no-sync`, which is the canonical Windows
REM interactive shape per the dev-environment-uv-windows ADR.
REM
REM Operators who modified pyproject.toml or lockfiles must run `uv sync`
REM explicitly once before using this launcher again. `aeat config repair`
REM surfaces a stale-sync diagnostic row when sync drift is detected.

uv run --no-sync aeat %*
