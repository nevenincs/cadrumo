# Ledger governance harness

This directory owns the offline governance suites for the `clitui-ledger` campaign. The tests
read the live `.vault/` records and import the read-only matrix implementation from
`dev.quality`; the implementation does not depend on this harness.

Run the complete migrated suite from the repository root with:

```powershell
uv run --no-sync pytest -q -n 0 .vaultspec/tests/clitui_ledger
```

The Vaultspec CLI remains the authority for execution-record mapping; run its check directly
when that contract is needed:

```powershell
uv run vaultspec-core vault check exec-mapping --json
```
