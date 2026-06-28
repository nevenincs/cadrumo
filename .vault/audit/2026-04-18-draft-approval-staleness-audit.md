---
tags:
  - '#audit'
  - '#draft-approval-staleness'
date: '2026-04-18'
modified: '2026-04-18'
related:
  - '[[2026-04-18-draft-approval-staleness-plan]]'
  - '[[2026-04-18-draft-approval-staleness-adr]]'
---

# `draft-approval-staleness` Code Review

REVIEW-001 | HIGH | Submission preflight still bypasses the human approval gate
The approved implementation plan explicitly requires `src/aeat/adapters/outbound/aeat/export/_preflight.py`
to reject unapproved or stale drafts before any downstream submission surface
runs. The shipped code still treats `READY_TO_SUBMIT` as sufficient and never
requires `APPROVED`. Because `aeat submission preflight` and `aeat submission dry-run`
both still flow through that gate, Kent can continue past validation without the
persisted review sign-off that issue #230 was supposed to introduce.

REVIEW-002 | HIGH | Submission/workflow protocol shims still encode the pre-review status model
`src/aeat/adapters/outbound/aeat/export/_protocols.py` still exposes a `DraftStatus` enum that stops
at `READY_TO_SUBMIT`, and `src/aeat/entrypoints/cli/submission/_helpers.py` parses draft JSON
through that stale shim. This means the CLI submission surfaces cannot even load
an `APPROVED` draft JSON cleanly, and the surrounding workflow/submission tests
still model a merely validated draft as the happy path. The review state landed
in `aeat.application.filing`, but the downstream protocol seam was left behind.

REVIEW-003 | HIGH | `aeat review` ships as a path-only operator tool instead of the planned draft-id flow
The approved plan promised `aeat review approve <draft_id>`, anchored to the
configured drafts directory, but `src/aeat/entrypoints/cli/review/__init__.py` still
requires a raw filesystem path for `approve`, `unapprove`, and `show`. That is a
Kent-facing UX/configuration regression: users must know where draft JSON lives,
how `AEAT_DRAFTS_DIR` is configured, and how filenames are composed before they
can approve anything.

REVIEW-004 | HIGH | Review-state refresh reparses the transaction catalogue once per draft
Gemini’s high-priority review note is still valid in `src/aeat/application/filing/_review.py`.
`_load_transaction_catalogue()` is invoked through `refresh_review_status()` for
every reviewed draft surfaced by `aeat filing list` and `aeat review stale`.
With the default catalogue path this causes repeated disk I/O and JSON parsing in
a single command invocation, despite the catalogue being stable for the lifetime
of that process.

REVIEW-005 | MEDIUM | Transaction-catalogue fingerprinting still materialises the full normalized payload
Gemini’s second high-priority finding also remains open. `_transaction_catalogue_fingerprint()`
builds a complete list of normalized transactions and serialises the whole list
into one JSON string before hashing. That scales memory linearly with catalogue
size and is avoidable with a deterministic incremental hash update.

REVIEW-006 | MEDIUM | Coverage/configuration surfaces still describe #230 as unshipped
`docs/coverage/kent-capabilities.md` and `docs/coverage/pipeline.md` still mark
draft approval and staleness detection as not shipped, while the code and tests
have already introduced those capabilities. Separately, the review CLI remains
implicitly coupled to `AEAT_DRAFTS_DIR` and `AEAT_FINANCIAL_TXS_DIR` with no
Kent-facing indirection layer, which is why the path-only command shape leaked
into the shipped UX in the first place.

REVIEW-007 | INFO | Working-tree remediation now closes the blocking draft/review gaps
The current working tree now enforces `APPROVED` at `src/aeat/adapters/outbound/aeat/export/_preflight.py`,
extends the submission protocol shim to understand `APPROVED` / `APPROVAL_STALE`,
accepts draft-id based review commands in `src/aeat/entrypoints/cli/review/__init__.py`, and
updates the amendment CLI to persist amended drafts into the ordinary review
surface before submit.

REVIEW-008 | INFO | Working-tree remediation now closes the Gemini performance findings
`src/aeat/application/filing/_review.py` now caches default transaction-catalogue loads with
file-change invalidation and hashes the normalized catalogue incrementally
instead of materialising the full JSON payload in memory.

REVIEW-009 | INFO | Submission/workflow status shim now mirrors the live filing status model
`src/aeat/adapters/outbound/aeat/export/_protocols.py` no longer invents the non-existent
`INCOMPLETE` status and now carries the full `aeat.application.filing.FilingDraftStatus`
surface (`VALIDATED`, `APPROVED`, `APPROVAL_STALE`, and the historical
post-submission states). This removes a latent parse/configuration drift at the
submission boundary and aligns the workflow tests with a real filing status.

REVIEW-010 | INFO | Coverage matrices now reflect the shipped review surface
`docs/coverage/kent-capabilities.md` and `docs/coverage/pipeline.md` now mark
persisted draft approval and approval-staleness detection as shipped. The
provenance timestamp in the Kent matrix was also refreshed to match the live
2026-04-18 audit pass.

REVIEW-011 | HIGH | `aeat submission` still cannot consume the real persisted `FilingDraft` JSON shape
The current `aeat filing build` / `aeat filing complementaria build` surfaces
persist real `FilingDraft` payloads via `draft.model_dump_json(...)`, where
`values` is a tuple of structured `FilingValue` records. But the submission CLI
loader in `src/aeat/entrypoints/cli/submission/_helpers.py` still assumes a legacy
`dict[str, str]` shape and executes `values=dict(raw.get("values", {}))`. In a
direct reproduction against a real approved draft written by the filing domain,
`aeat.entrypoints.cli.submission._helpers.load_draft()` raises `ValueError: dictionary
update sequence element #0 has length 5; 2 is required`. The current
`src/aeat/entrypoints/cli/submission/test_cli.py` fixtures only pass because they fabricate
the old dict-valued payload instead of round-tripping the production draft
format, so the filing → review → submission CLI path remains broken in the real
operator flow.

REVIEW-012 | HIGH | `aeat filing validate` silently destroys approval provenance on already-approved drafts
`src/aeat/entrypoints/cli/filing/__init__.py` now calls `validate_draft(...)` and then
passes the result through `_refresh_persisted_draft(...)`. `validate_draft()`
re-applies machine validation status via `apply_validation(...)`, which drops
the draft back to `READY_TO_SUBMIT` / `VALIDATED` / `DRAFT` while leaving the
old approval metadata attached. `_refresh_persisted_draft()` then sees a
non-review status and clears `approved_at`, `approved_by`, `review_checksum`,
and `approval_basis` through `src/aeat/application/filing/_review.py`. In direct
reproduction, validating an unchanged approved draft returns
`STATUS READY_TO_SUBMIT APPROVED_AT None APPROVED_BY None CHECKSUM None`. That
means a no-op validation refresh irreversibly strips the persisted approval
record, which contradicts the issue #230 contract that approval is a first-class
persisted review decision rather than a fragile display-only flag.

REVIEW-013 | MEDIUM | Submission preflight still trusts stored status instead of recomputing review staleness at the boundary
Even after the new `APPROVED` / `APPROVAL_STALE` states landed in
`src/aeat/adapters/outbound/aeat/export/_preflight.py`, the submission CLI entrypoints
`src/aeat/entrypoints/cli/submission/preflight.py` and `src/aeat/entrypoints/cli/submission/dry_run.py`
only call `load_draft(...)` and then hand the deserialized object directly to
`Preflight.check(...)`. No path in that boundary recomputes
`refresh_review_status(...)` or approval-basis drift before trusting the stored
JSON status. Today this gap is masked by REVIEW-011 because the submission CLI
cannot load real filing drafts at all, but once the loader is corrected the
boundary will still accept an on-disk `APPROVED` draft whose upstream
transaction/category/schema basis has changed since approval unless some other
command happened to refresh and rewrite the file first.

REVIEW-014 | INFO | Working tree now closes the real-draft submission and approval-preservation gaps
`src/aeat/entrypoints/cli/submission/_helpers.py` now loads the real persisted
`aeat.application.filing.FilingDraft` JSON shape, refreshes review staleness through
`refresh_review_status(...)`, and rewrites the draft file when that refresh
changes the stored status. `src/aeat/application/filing/__init__.py` now revalidates drafts
without discarding an existing approval record: unchanged approved drafts remain
`APPROVED`, and reviewed drafts whose validation surface drifted become
`APPROVAL_STALE` instead of losing their approval provenance. Coverage now
includes CLI-level proof that submission preflight marks a persisted approved
draft stale after transaction-catalogue drift and that `aeat filing validate`
preserves approval metadata for an unchanged reviewed draft.

REVIEW-015 | HIGH | `aeat filing build` still crashed on a real cp1252 console due to non-ASCII success output
Manual operator verification against the persisted draft flow found a new
Kent-facing regression outside pytest: `src/aeat/entrypoints/cli/filing/__init__.py`
printed `Saved draft ... → ...` and `Saved amended draft ... → ...`. On the
native Windows cp1252 console this raised `UnicodeEncodeError: 'charmap' codec
can't encode character '\u2192'`, which aborts the command after the draft is
written and leaves the operator unsure whether the build actually succeeded.
This bug is severe because it breaks the very first success surface Kent sees in
the review workflow and was only detectable through live manual execution.

REVIEW-016 | INFO | Filing/review CLI now surfaces the operator's next step instead of only raw state
The current working tree now keeps the success messages ASCII-only and adds
explicit next-step guidance across `aeat filing build`, `aeat filing validate`,
`aeat filing complementaria build`, `aeat review approve`, `aeat review show`,
`aeat review unapprove`, and `aeat review stale`. Kent now sees concrete follow
up commands (`aeat review show <draft_id>`, `aeat review approve <draft_id>`,
`aeat submission preflight <path>`, `aeat submission dry-run <path>`) at the
point of decision, which closes the immediate UX gap between "approval state
exists" and "the operator knows what to do next."

REVIEW-017 | INFO | Forbidden behavior-patching tests are now removed from the repo surface
The repo-wide audit for `monkeypatch.setattr(...)`, `patch(...)`, and
`unittest.mock` usage across `src/aeat/**/test*.py` now comes back clean. The
three concrete behavior-patching cases previously found in
`src/aeat/entrypoints/cli/browser/test_health.py`, `src/aeat/domain/schema/test_fetch.py`, and
`src/aeat/domain/financial/invoices/test_reconciliation.py` were rewritten to use
explicit production seams or real filesystem behavior instead of runtime test
patching. Remaining `monkeypatch` usage is limited to environment-variable
setup/teardown (`setenv` / `delenv`), which matches the stricter local rule
accepted for this branch.

REVIEW-018 | INFO | Submission CLI now accepts draft ids directly, preserving the filing -> review -> submission operator flow
The current working tree closes the remaining Kent-facing handoff gap by
teaching `aeat submission preflight` and `aeat submission dry-run` to accept
either a draft id or a draft path. `src/aeat/entrypoints/cli/submission/_helpers.py` now
resolves persisted drafts by `draft_id`, loads the real `FilingDraft` payload,
refreshes approval staleness before submission gating, and rewrites the draft
file when the refreshed review state changes. This means the operator can stay
on the same identifier model from `aeat filing build` through `aeat review
approve` and into `aeat submission ...` instead of dropping back to filesystem
paths after review.

REVIEW-019 | HIGH | The wider test suite still violates the no-shortcuts policy through skip-gated live/deferred tests
Even with the behavior-patching cleanup complete, the broader repo test suite
is still not fully compliant with the project rule that tests must not rely on
fakes, stubs, or `pytest.skip(...)` as a shortcut for a green run. The
stub-based browser unit tests have now been replaced with real Playwright
coverage, but skip-gated live/deferred tests still remain in
`src/aeat/domain/casillas/test_live_cli.py`,
`src/aeat/inbox/test_live_inbox.py`, `src/aeat/domain/justificante/test_verify_live.py`,
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_certificate_live.py`, `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/auth/test_authenticator_live.py`,
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_live_evasion.py`, `src/aeat/history/test_live.py`,
`src/aeat/adapters/outbound/llm/test_live_anthropic.py`, and `src/aeat/status/test_live.py`.
One ordinary unit-test skip in `src/aeat/domain/schema/test_fetch.py` has now been
removed in this pass, but the remaining live/deferred skip surfaces still block
a strict claim that the whole suite is policy-clean.

REVIEW-020 | INFO | Browser lifecycle and evasion tests now run against real Playwright sessions
`src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_session.py` and `src/aeat/adapters/outbound/aeat/adapters/outbound/aeat/browser/test_evasion.py` no
longer depend on `Stub*` classes or synthetic browser stand-ins. The branch now
installs Chromium through the repo runtime and validates locale/timezone setup,
storage-state loading, certificate marker propagation, retained-browser
lifecycle rules, cleanup after malformed storage-state failure, process-count
stability across repeated cycles, and stealth webdriver suppression against a
real Playwright browser. This closes the largest remaining stub-based unit test
surface and leaves the live/deferred `pytest.skip(...)` tests as the next
policy-hardening target.
