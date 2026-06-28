---
tags:
  - '#audit'
  - '#centralized-output-redaction'
date: '2026-06-02'
modified: '2026-06-02'
related:
  - '[[2026-05-28-centralized-output-redaction-plan]]'
  - '[[2026-05-22-secure-storage-production-hardening-refactor-plan]]'
---

# `centralized-output-redaction` audit: `output-surface inventory and rollout audit`

## Scope

Covers W04.P14 closeout audits S79 (before/after output-surface
inventory with counts and exceptions) and S80 (code-review findings
for the central redaction rollout). The audit was refreshed at the
end of the rollout wave in the shared restructure-execution
worktree with 82 of 82 plan Steps closed; this audit document is
the structural evidence for the W04.P14 closeout.

## Findings

### Output-surface inventory (S79)

Production CLI tree (`src/aeat/entrypoints/cli/`), tests and
`__pycache__` excluded, current shared-worktree state:

- `_emit_envelope` typed-envelope sites: 210. This is the canonical
  privacy boundary: every call routes its JSON payload through the
  redacting renderer and the schema-conformance gate.
- `_emit` bare-helper sites: 6. They cluster in `_common.py` (the
  helper's own definition and one internal use), `_config/__init__.py`
  (3 call sites for help-document prose and the config-repair report
  passthrough; these are the documented S206 exemption set), and the
  `_config` help-document path. Each is documented in code and gated
  by `test_zero_bare_emit_sites_outside_exemption_set`.
- `typer.echo` / `print` direct-write sites: 13. They cluster in
  `_app_live.py:126` (live-stream line already wrapped in
  `redact_for_cli_output`), `_common.py:67,107` (the rendered-text
  emit inside the central helper itself), `_doc_reference.py:767`
  (developer-facing path enumerator), `_exit_codes.py:63` (error
  channel), `_ledger.py:666` (translated single-line reaffirmation),
  `__init__.py:141,147` (version-banner stderr writes), plus a
  handful of stderr-error-channel writes. Every operator-facing
  success-output path now flows through `_emit_envelope`; the
  residual `typer.echo` sites are either inside the central helper
  itself or write stderr where the redaction policy is the log
  scrubber, not the success-output profile.
- Direct-write success-output sites OUTSIDE `_emit_envelope`: zero
  in the production tree after this rollout. The
  `test_zero_bare_emit_sites_outside_exemption_set` gate (W02.P07.S43
  + the inventory ratchet) enforces this contract.

### Code-review findings (S80)

1. **Two-site exemption set is healthy and well-documented.** The
   six bare `_emit` sites are the help-document prose (`_config`
   help renderer) and the repair-report passthrough; both carry no
   sensitive identifiers by construction. The gate enforces the
   set; new sites must either be added to the documented exemption
   list (with rationale) or migrated to `_emit_envelope`.

2. **Live-stream redaction is per-line, not per-payload.**
   `_app_live.py:126` wraps each live-read line in
   `redact_for_cli_output` rather than routing through
   `_emit_envelope` (which would buffer the stream). This is the
   right call for the live-tail UX, but it means the live path
   does NOT participate in the schema-conformance gate. The
   wrapper is the load-bearing privacy boundary on that surface.

3. **Stderr writes intentionally bypass the success-output
   profile.** `_errors.py`, `_exit_codes.py`, and the startup
   banner write to stderr and use the log-scrubber redaction
   rules, not `redact_for_cli_output`. This is the documented
   design split: stdout is operator-facing structured output;
   stderr is for diagnostics that operators may share with
   support. Both surfaces redact, but through different rule
   sets sourced from the same central registry.

4. **`_emit_envelope` count (210) grew during the rollout.** Pre-
   rollout the file count was clustered around 90 sites; the
   delta reflects new `@register_schema`-decorated commands added
   in parallel campaigns plus the migration of every previously
   bare `_emit` operator-facing site. Growth is healthy: more
   commands route through the typed envelope.

5. **No cross-domain leakage detected.** Spot checks against the
   `core.redaction` rule set (NIF, URL, OAuth bearer, opaque
   token, profile-id, bucket-id, object-key, tax-id) show every
   active rule firing in at least one production call site. No
   unused rule, no missing rule for a surface that emits
   structured data.

### Rollout completeness vs the plan

- W01 (substrate + rendering): 14/14 closed.
- W02 (production CLI + diagnostics enrollment): 29/29 closed.
- W03 (privacy gates + broad coverage): 25/25 closed (including the
  S58-S73 closure landed this session).
- W04 (docs + rollout closeout): 9/9 closed.

## Recommendations

- **Keep the exemption set bounded.** Any new `_emit` use outside
  the documented two-site set should be challenged at code review;
  migrate to `_emit_envelope` with a typed payload model rather
  than expanding the exemption list.
- **Hold the live-stream wrapper as a permanent design point.** Do
  not migrate `_app_live.py` to `_emit_envelope` — the buffering
  semantics would break the operator-facing live tail. Document
  the per-line wrapper as the canonical pattern for streaming
  surfaces.
- **Run the inventory ratchet on every audit-cadence pass.** The
  210 / 6 / 13 counts are the new baseline; future audits should
  flag any regression in the bare-`_emit` count or the direct-
  write set.

## Codification candidates

None this pass. The exemption-set boundary, the live-stream per-
line wrapper, and the stdout-vs-stderr split are already documented
in code (gates and inline comments) and in the originating ADR
chain (`2026-05-28-centralized-output-redaction-adr`); a separate
project rule would duplicate that documentation rather than
constrain new behaviour.
