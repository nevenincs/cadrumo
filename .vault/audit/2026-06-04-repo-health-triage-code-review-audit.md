---
tags:
  - '#audit'
  - '#repo-health-triage'
date: '2026-06-04'
related:
  - '[[2026-06-04-repo-health-triage-plan]]'
  - '[[2026-06-04-repo-health-triage-adr]]'
  - '[[2026-06-04-repo-health-triage-research]]'
---

# `repo-health-triage` Code Review

## W01-001 | HIGH | Public Drive service injection bypassed credential-owned construction

Status: remediated.

The W01 resolver change added a public `drive_service` keyword to
`resolve_document_link`, allowing callers to bypass credential-owned Google Drive
service construction. This conflicted with the minimal-scope resolver posture and
converted the test monkeypatch repair into a production test-double injection
surface.

Remediation removed the public service keyword from `resolve_document_link` and
restored `_download_drive_file` to always construct the Drive service from
credentials. Focused download behavior is covered through the private
`_download_drive_file_from_service` helper instead of the public API.

## W01-002 | MEDIUM | Corpus provenance step overstated relative import conversion

Status: remediated.

The checked W01 plan row claimed the corpus provenance test had been converted to
a relative import, but `src/aeat/_data/corpus` is a data-tree test location with
no package context. Turning the data tree into a package just to satisfy the row
would risk changing package-resource behavior.

Remediation updated the S03 plan action through `vaultspec-core vault plan step edit`
to describe the implemented behavior: remove the AST-visible absolute self-import
through the established `aeat.core.resources` boundary.

## W01-003 | LOW | Phase summaries lacked scoped command-output evidence

Status: remediated.

The W01 phase summaries listed verification commands but did not preserve concise
exit-code and result evidence, despite the ADR requiring scoped command output.

Remediation added focused evidence lines to the W01 phase summaries and corrected
the S10 step record to describe the post-review resolver contract.

## W02-001 | INFO | W02 type-control review found no actionable defects

Status: verified.

The W02 review found no findings and no remaining HIGH or CRITICAL issue. The
review checked the centralized counterpart source-kind subset, typed secure
repository payload accessors, sanitizer parse-error narrowing, narrow
import-linter test-helper exceptions, and W02 plan/exec/audit evidence.

The reviewer noted one non-blocking residual edge: a manually constructed invalid
revision with retired `invoice` source can be silently skipped by the resolver,
but production registry validation rejects that source before resolver use and
current production registry data does not contain `source = "invoice"` entries.

## W03-001 | LOW | Parallel plan step closure left S24 unchecked

Status: remediated.

The W03.P07 review found that `W03.P07.S24` was still unchecked while matching
execution and index records existed for the step. The root cause was a local
workflow error: S24, S25, and S26 were closed in parallel, and concurrent writes
to the same plan file lost the S24 update.

Remediation reran the S24 plan-step closure serially, regenerated the feature
index, removed the stale plan template annotation block, and reran VaultSpec
checks successfully. No HIGH or CRITICAL findings were reported for the W03.P07
code changes. The reviewer noted no behavioral regression in CLI command
registration, storage-session fixture direction, or the `work calculate` typed
boundary extraction.

## W03-002 | CRITICAL | S35 used an unapproved diagnostics source package

Status: remediated.

The S35 diagnostics analyzer extraction was invalid because `aeat.diagnostics`
is not an approved hexagonal module and must not live under the production source
package. The earlier no-findings review is superseded by this architectural
boundary correction.

Remediation removed the `aeat.diagnostics` package, deleted its generated API
stubs, removed the stale Ruff exception, replaced live source references to the
unapproved module, and rewrote the S35 execution record to document the
emergency removal rather than the rejected analyzer extraction.

Validation confirmed that `aeat.diagnostics` no longer resolves through
`importlib.util.find_spec`, the exact source/docs/package reference search is
clean, Ruff and Ty passed on touched files, and the non-ledger affected pytest
slice passed. The ledger validation module still carries the unrelated
storage-route mismatch failure and was verified with collection only for this
emergency package removal.

Focused review by Cicero found no actionable findings and no remaining HIGH or
CRITICAL issues for the emergency removal. The reviewer confirmed the source
package and generated API pages are deleted, live `aeat.diagnostics` references
are gone from source/docs/project config, import discovery returns `None`, and
VaultSpec plan/exec/index/audit records are coherent for the corrected S35
scope.

## W03-003 | INFO | Formula initial-value extraction review found no defects

Status: verified.

The W03.P09.S31 review found no behavioral defect in the extraction. The runtime
keeps the same private call sites by importing `initial_values` and
`materialise_observations` under the old private helper names, while the new
module owns the previous-filing absent-by-design and projection guards.

Verification covered formula runtime behavior, Modelo 130 carry-forward
absent-by-design behavior, previous-filing smuggling/projection rejection, ruff,
the VaultSpec plan check, and the registry reviewability gate.

## W03-004 | INFO | Workbook parity complexity baseline review found no defects

Status: verified.

The W03.P09.S32 review found no behavioral defect because the slice deliberately
does not change workbook parity execution. `_workbook_parity.py` remains the
reviewed 1,336-line hotspot, and `test_registry_reviewability.py` now fails if
that module grows past the recorded baseline.

Verification covered the reviewability gate, focused workbook parity scan and
inventory behavior, and Ruff on the touched reviewability surface.

## W03-005 | INFO | Modelo binding-resolution extraction review found no defects

Status: verified with scoped residual.

The W03.P08.S27 review found no behavioral defect in the extraction. The
calculation action now delegates profile, borrador, relation, previous-filing
override, bound-casilla, and informational-period input assembly to
`_binding_resolution.py`; IVA wallet reconciliation remains in `_actions.py` for
the next dedicated slice.

Focused verification passed for profile binding, real profile binding, borrador
binding, previous-filing casilla override, declaration-period binding, and Ruff
on touched surfaces. A broader source-mesh calculation run still has two
pre-helper failures where Renta expense source resolution raises
`aggregation.renta_ledger.errors.invoice_bucket_mismatch` before binding
resolution is reached; that edge is outside this extraction and remains tracked
as a source-mesh preflight ordering issue.

## W03-006 | INFO | Modelo IVA wallet gate extraction review found no defects

Status: verified.

The W03.P08.S28 review found no behavioral defect in the extraction. The
calculation action now delegates Modelo 303 IVA wallet decision resolution,
binding application, persisted-decision replay checks, blocked-message rendering,
and taxpayer NIF lookup to `_iva_wallet_gate.py`, while preserving the existing
private `_actions.py` import surface used by export, CLI, and tests.

Focused verification passed for IVA wallet binding behavior, blocked-message
localisation, export refusal checks, the closure token, the IVA wallet engine
integration file, and Ruff on the touched action/gate/error-registry surfaces.
One attempted export pytest command used stale node ids and collected no tests;
the corrected export refusal node ids passed.

## W03-007 | INFO | Modelo revision-persistence extraction review found no defects

Status: verified.

The W03.P08.S29 review found no behavioral defect in the extraction. The
calculation action now delegates bucket-event emission, draft revision
persistence, calculation-created event emission, verified-complete filing
transitions, supersession state updates, filing-record writes, and work-unit
pointer advancement to `_revision_persistence.py`.

Focused verification passed for calculate idempotency, calculation-created
events, verify/file workflow gates, filing pointer updates, filing and
supersession events, Modelo 303 wallet pre-mutation refusal, and Ruff on the
touched action/persistence/test surfaces.

A dedicated `vaultspec-code-reviewer` delegation was attempted for this slice,
but the active subagent pool returned a thread-limit failure; the review was
completed locally against the mandatory code-review checklist.

## W03-008 | INFO | Ledger review projection extraction review found no defects

Status: verified.

The W03.P10.S33 review found no behavioral defect in the extraction.
`_actions.py` now keeps repository loading and delegates review filtering,
event-filter matching, row projection, and review-status classification to
`_review_projection.py`.

Focused verification passed for review period/status projection, direction
filtering, import/issue event filters, ledger list CLI filters, the full
application ledger action test file, and Ruff on the touched ledger surfaces.

## W03-009 | INFO | Ledger list CLI extraction review found no defects

Status: verified with scoped residual.

The W03.P10.S34 review found no behavioral defect in the extraction. The
`ledger list` command now delegates filter parsing, shared review-query
matching, group filtering, group ordering, paging, truncation footer
construction, row payload construction, and text-line rendering to
`_ledger_list.py`, while `_ledger.py` keeps Typer option wiring, repository
resolution, parse-error translation, and envelope emission.

Focused verification passed for list filters, cold-start no-profile refusal,
review-filter help wording, and Ruff on the touched ledger CLI surfaces. A
broader lifecycle CLI test currently fails before the list path on an unrelated
`ledger update` taxable-base plus IVA gross-validation refusal.

## W04-001 | INFO | Formulas dependency ownership review found no defects

Status: verified with scoped residual.

The W04.P12.S38 review found no behavioral defect in the dependency hygiene
decision. `formulas` remains declared for the workbook parity oracle, while the
production registry formula runtime remains import-free for the external
package. The Deptry `DEP002` exception is explicit and scoped to that ownership
decision rather than a blanket dependency suppression.

Focused verification confirmed that no Python import of the external `formulas`
package exists, `uv run --no-sync deptry .` no longer reports `formulas`, and
the VaultSpec repo-health plan validates. Deptry still reports planned residual
findings for `rich`, `torch`, `playwright_stealth`, and `prompt_toolkit`, which
remain open under W04.P12.S39-S42.

## W04-002 | INFO | Rich dependency ownership review found no defects

Status: verified with scoped residual.

The W04.P12.S39 review found no behavioral defect in the dependency hygiene
decision. `rich` is retained as a direct version pin for Typer's console
rendering path, while application code remains free of direct Rich imports. The
Deptry `DEP002` exception is scoped to that Typer ownership rather than a broad
unused-dependency allowlist.

Focused verification confirmed no Python import of `rich`, Typer metadata still
declares `rich>=13.8.0`, root CLI command materialisation succeeds, and
`uv run --no-sync deptry .` no longer reports `rich`. Deptry still reports
planned residual findings for `torch`, `playwright_stealth`, and
`prompt_toolkit`, which remain open under W04.P12.S40-S42.
