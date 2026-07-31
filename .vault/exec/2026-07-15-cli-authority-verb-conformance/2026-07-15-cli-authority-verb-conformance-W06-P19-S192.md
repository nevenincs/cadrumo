---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-25'
modified: '2026-07-25'
body_hash: 'sha256:19548393adf259654f595dae16754a21f7a52e4316baf9aa780fa13181694fe7'
step_id: 'S192'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

# Run generated CLI reference and static-tree conformance

## Scope

- `dev/docs/tests/`

## Description

Run generated CLI reference and static-tree conformance.

## Outcome

FAILED, peer working-tree churn carrying a latent committed hazard.

Command: `uv run --no-sync pytest -q -rs -n0 -m "" -p no:cacheprovider
dev/docs/tests/test_cli_reference_conformance.py dev/docs/tests/test_cli_tree.py
dev/docs/tests/test_cli_anchor_parity.py`.
Collected 23, 22 passed, 1 failed, exit line `1 failed, 22 passed in 171.36s`, exit code 1, at
HEAD `1844ef2ea0`.

The failing case asserts every live CLI leaf has a registered output schema. Two leaves, the
profile create and edit verbs, are unregistered as far as the production discovery walk can see.

Root cause established by exact search: both schemas ARE declared, in a NEW UNTRACKED module
under the application wizard package named for results. The production discovery walk imports
only modules whose name contains the payload token, inside the declared payload packages. An
application-layer module named for results is outside both filters, so the registration
decorators never run and the registry never learns the two keys.

Re-run before reporting, at HEAD `593559067c`: `1 failed, 5 passed in 44.04s`, the same
live-leaf-schema case. The relocated wizard results module is STILL untracked at that HEAD, so the
hazard is standing rather than resolved.

## Notes

The gate is non-tautological and it is right: it compares the live tree against the
registry, two independent sources, and consults no generated page.

The hazard is real rather than cosmetic. If that relocation is committed as it stands, the two
leaves lose their schema in the contract manifest and in the MCP tool surface, not only in this
gate. The owning campaign should either keep the declarations inside a discovered payload module
or extend the discovery walk in the same commit.

The JSON schema conformance suite recorded under S188 is green over the same state, because it
does not compare the live leaf set against the registry.

The semantic code index was degraded throughout this Phase: the service reported `Source code sections: 466` against 3982 tracked Python files while declaring its code generation succeeded. No absence recorded here rests on a semantic miss.

## Status at 2026-07-26: fixed, and the diagnosis held

CLOSED. The two profile-verb schemas ARE enrolled at HEAD `990ddbb860`. Measured
directly: the production discovery walk reports zero load failures, 295 registered
schemas, and both `config.profile.create` and `config.profile.edit` present. The
gate that originally caught this now passes 6 of 6, where it reported 1 failed and
5 passed when this record was written.

The finding above was correct when it was made and was fixed thirteen hours later,
not mistaken. The record is updated rather than withdrawn, and the distinction
matters for the reason below.

The fix is commit `92b0dfd10b`, "restore the two profile verbs to the MCP surface",
landed 2026-07-26 at 11:30 and a descendant of the HEAD this record measured at
2026-07-25 22:07. It does NOT change the discovery walk. It adds two module-level
imports of the wizard result classes into a module the walk already reaches, so
importing that module transitively runs the registration decorators. The fix's own
comment restates this record's diagnosis almost word for word: the registry is
populated from payload-named modules under the declared payload packages only, the
wizard module declaring these two schemas is under neither, and without the import
both verbs drop off the MCP surface.

So enrolment IS still filename-filtered. What changed is that a deliberate bridge
now spans the filter. Any later reading that concludes filename filtering was never
the mechanism will mis-describe why the bridge has to exist.

RESIDUAL FRAGILITY, recorded because the fix's shape invites removal. The bridge is
written in the re-export idiom, importing each name and rebinding it to itself. That
is visually indistinguishable from a redundant re-export, and the obvious tidy-up is
to delete it. Doing so silently drops both verbs from the MCP surface again. Two
things currently hold that line: the comment marking the import load-bearing, and the
live-leaf-versus-registry gate, which fails when either key goes missing. The gate is
the real guard; the comment is a courtesy. Confirmed by running the gate, not by
reading it.

## Full-suite run at HEAD bc80aa2808

PARTIALLY SATISFIED. The CLI-specific gates (test_cli_reference_conformance.py,
test_cli_tree.py, test_cli_anchor_parity.py) pass. The broader `dev/docs/tests/`
suite has 3 peer-owned failures.

Command: `uv run --no-sync pytest dev/docs/tests/ --tb=short`.
Collected 151, 148 passed, 3 failed, exit line `3 failed, 148 passed in 682.84s`,
exit code 1, at HEAD `bc80aa2808`.

Failure 1: `test_env_reference.py::test_generated_page_is_fresh` — the generated
environment-overrides reference page is stale. The MCP stdio watchdog setting
(`CADRUMO_MCP_STDIO_WATCHDOG`) was added by commit `faa8643ece feat(mcp): anchor the
stdio server's lifetime to its client` without regenerating the docs page. Peer-owned
(MCP campaign).

Failure 2: `test_env_reference.py::test_settings_fields_all_present_in_env_example` —
`CADRUMO_MCP_STDIO_WATCHDOG` is present in Settings but absent from `env/.env.example`.
Same root cause and same owning commit as failure 1.

Failure 3: `test_docs_build_full_scope.py::test_sphinx_nitpicky_build_is_clean` —
Sphinx `-n -W` build fails on four warnings from peer commits: inline literal
formatting in `_fts_query.py` (commit `286db29da0`), unresolved cross-reference in
`_export_parity.py` (commit `914c59ad07`), unresolved cross-reference in
`_bundle_export_operation.py` (commit `279bd29bfc`), and a dangling attribute reference
to `ModeloSupportMatrixEntry.is_deprecated` in `_classification_coherence.py` (commit
`8bec35ac37`). None of these modules belong to the cli-authority-verb-conformance
surface.

The three CLI-specific reference gates this step was originally scoped to are all green
at this HEAD. No failure is owned by this feature.
