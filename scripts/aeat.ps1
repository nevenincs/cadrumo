# Windows PowerShell launcher for the aeat CLI.
#
# Plain `uv run aeat` resyncs the venv on every invocation, which races the
# Windows process holding `Scripts/aeat.exe` open and raises os error 32.
# This launcher forces `--no-sync`, which is the canonical Windows
# interactive shape per the dev-environment-uv-windows ADR.
#
# Operators who modified pyproject.toml or lockfiles must run `uv sync`
# explicitly once before using this launcher again. `aeat config repair`
# surfaces a stale-sync diagnostic row when sync drift is detected.

& uv run --no-sync aeat @args
