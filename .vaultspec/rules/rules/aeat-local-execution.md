---
name: aeat-local-execution
trigger: always_on
---

# AEAT local execution

Use `fd` and `rg` for discovery and search. Prefer native PowerShell commands in this environment. Do not wrap normal commands in `pwsh`, `powershell`, `cmd /c`, or `bash -lc` unless a tool explicitly requires a separate shell process.

Use the uv-managed workflow. Prefer platform-agnostic project configuration over shell-specific variants.

Run real gates. Do not use mocks, fakes, stubs, patches, monkeypatches, skip, xfail, or tautological assertions as shortcuts. Prefer real-behavior tests with useful diagnostics when failures need trace context.

Re-run before blaming the code. Registry-suite failures under parallel pytest (`-n N`) are more often a loader-cache race than a real regression. Re-run the failing tests sequentially before triaging them as a regression.
