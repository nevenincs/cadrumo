---
tags:
  - '#audit'
  - '#cli-root-help-profile-identity'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:b91f00eb6ec1c6ec5519461e9132696c0ba9816438685ac13e7ec12aae0ea78a'
related:
  - "[[2026-08-10-cli-root-help-profile-identity-audit]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace cli-root-help-profile-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `cli-root-help-profile-identity` audit: `Manual installed CLI journey implementation review`

## Scope

This review covers the installed-console failures observed in the isolated manual
journey under `.tmp/manual-cli-root-20260810-0920`, the remediation committed or
still present in the live shared worktree, and the concurrent TUI status-bar import
repair. It evaluates profile/config repair and custody, storage inventory and
reclaim, auth configure/status/logout, bare-root landing and help, overview,
ledger, modelo work selectors/rendering, and TUI failure/status paths against
`2026-05-28-centralized-output-redaction-adr`,
`2026-05-12-cli-workflow-redesign-adr`,
`2026-06-04-modelo-addressing-ux-adr`, and the parent audit.

The review compared the exact manually observed commands with the live source and
diffs and ran bounded read-only checks with `uv run --no-sync`. The displayed
12-character work-unit selector and incoming-business overview classification
passed focused tests. A first integration invocation selected no applicable tests
and was not counted as evidence; it was rerun explicitly with `-m integration` and
`-n 0`. The focused root and auth assertions remain stale, the source-remedy
selector fails on removed `Notice.suggestion`, and targeted Ruff reports ten
errors in the reviewed slice.

The reviewed state resolves the original profile-id leakage in repair, status,
logout, ledger status, and overview; removes auth configure's `active_profile`
bucket field and overview's nested duplicate bucket projection; routes registered
logged-out profiles to login; supplies the required profile-create options in
help; excludes incoming business rows from expenses; accepts displayed
12-character work ids; avoids the post-persistence `Notice.suggestion` crash; and
contains the TUI status-bar module needed for modelo command loading. Exact
matching-identity and missing-identity Clave configure-to-status replays also agree
in the live state, so auth completeness is recorded as resolved in flight rather
than as a finding. The message-level calculate deduplication is reviewed below
rather than treated as complete. Storage localization/containment work remained in
flight, so the containment finding records the reproduced behavior and the exact
contract the pending fix must satisfy.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Manual installed CLI journey implementation review | {level} | {summary}

     followed by a paragraph carrying the detail. Manual installed CLI journey implementation review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### storage-reclaim-target-redirection | high | Reclaim follows a redirected declared target outside the storage root

`src/cadrumo/application/storage_management/_service.py:277-299` preflights the
declared targets but then calls `target.iterdir()` when the target itself is a
directory link or junction. The checks at
`src/cadrumo/application/storage_management/_service.py:315-354` prove taxonomy
scope and lexical nesting only; they do not reject a redirected target or prove
resolved filesystem containment. A temporary-directory probe against the real
service created a selected-target symlink to an external directory and produced
`TARGET_IS_SYMLINK True`, `REMOVED 1`, and `SURVIVOR_EXISTS False`: confirmed
reclaim deleted the external child. The existing test at
`src/cadrumo/application/storage_management/tests/test_reclaim_containment.py:49-70`
puts a link inside a normal target and catches link-creation failure without
failing, so it can pass without exercising a link. This is an operator-triggered
destructive escape from the storage taxonomy's containment boundary.

### calculation-remedy-projection | high | Successful calculation hides repair guidance required before export

`src/cadrumo/entrypoints/cli/_modelo_rendering.py:167-190` accepts a `suggestion`
but ignores it when constructing `Notice`, while
`src/cadrumo/entrypoints/cli/_modelo_rendering.py:193-224` passes
`diagnostic.remedy` through that dead parameter. The text renderer at
`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:604-644` renders only the
message. Concrete diagnostics separate diagnosis from repair: the carry diagnostic
at `src/cadrumo/application/calculations/_relation_prefill.py:774-803` tells the
operator to provide a binding override, and the rate-box diagnostic at
`src/cadrumo/application/modelo/_rate_box_advisory.py:68-83` tells them to record
the missing IVA rate before recalculating because export will refuse. Both remedies
are absent from JSON and text. The selector
`test_source_diagnostic_notice_context.py::test_the_remedy_reaches_the_notice_suggestion`
fails because `Notice` has no `suggestion`, while
`test_source_advisory_notice_channel.py:55-65` no longer asserts `_REMEDY`. Removing
the post-persistence `AttributeError` fixed exit 6 but silently weakened the
no-under-declaration recovery contract.

### calculation-message-deduplication | medium | Presentation equality discards distinct diagnostic provenance

`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:625-635` deduplicates
source notices solely by `notice.message`. A second diagnostic with the same human
message but a different source kind, resolver, binding, relation, casilla, or
source reference is discarded with its structured context. The assertion at
`src/cadrumo/entrypoints/cli/tests/test_source_advisory_notice_channel.py:73-83`
constructs different `source_kind` values and accepts only the first. This converts
the duplicate-presentation symptom into machine-visible provenance loss.

### modelo-short-id-selector | medium | One-character aliases can drive mutations and ambiguous refusals give circular guidance

`src/cadrumo/application/modelo/_selectors.py:56-59` accepts any one-to-64-character
hex token, and `src/cadrumo/application/modelo/_selectors.py:361-383` resolves it
against both the beginning and end of every active work-unit id. A unique
one-character token can therefore select work for mutating calculate/file flows,
although the published UX exposes a 12-character display id and the addressing ADR
reserves raw exact ids as the advanced escape hatch. Collisions refuse, but
`src/cadrumo/entrypoints/cli/_modelo_cli_support.py:685-697` misreports the cause as
multiple modelo/year/period targets and tells an operator who already supplied an
id to pass an explicit id. The table at
`src/cadrumo/entrypoints/cli/_modelo_cli_support.py:660-682` labels its final column
`name` while rendering the full id. The passing 12-character happy path does not
cover short-token mis-selection or prefix/suffix collisions.

### tui-failure-redaction | medium | Pinned status paths render raw exception and stage-failure text

Unexpected credential failures fall back to `str(error)` at
`src/cadrumo/adapters/inbound/tui/_credential_screen.py:146-165`, and manager worker
failures do the same at
`src/cadrumo/adapters/inbound/tui/_manager_screen.py:799-819`. The filed-history
summary appends `run.stage_failures` verbatim at
`src/cadrumo/entrypoints/cli/_config/_manager_actions.py:407-437`; those strings are
formed from raw exception text at
`src/cadrumo/application/live/_filed_data_capture.py:1713-1725` through
`bounded_context_text`, whose implementation at
`src/cadrumo/application/live/_remote_state_outcomes.py:138-143` normalizes and
truncates but does not redact. Widget `markup=False` prevents markup interpretation,
not disclosure. Backend exceptions can therefore put tax ids, secrets, URLs, or
local paths directly into the TUI contrary to the centralized-output ADR.

### modelo-profile-and-action-text-parity | medium | Work text hides both profile identity and its typed next action

Exact installed replays of `aeat app modelo work list` and
`aeat app modelo work status 7904801d1a41` exit 0 but omit the next action carried
by JSON. List renders its `bucket_id` as `<profile-id>`, status renders it as
`<bucket-id>`, and neither shows the active profile label `operator-manual`.
The actions are already resolvable catalogue entries at
`src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py:453-463` and
`src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py:494-505`, but neither is
folded into text lines. `_emit_envelope` says callers must do that at
`src/cadrumo/entrypoints/cli/_common.py:403-450`, and its text branch at
`src/cadrumo/entrypoints/cli/_common.py:470-485` emits only supplied lines. This is
not a request to invent actions for informational prose: these notices already
carry typed actions. It is also a state/presentation defect because the
profile-scoped text substitutes inconsistent storage placeholders for the one
canonical operator label.

### focused-verification-red | low | The reviewed slice still has deterministic test and lint failures

The root-after-logout integration selector fails at
`src/cadrumo/entrypoints/cli/tests/test_root_help_shape.py:172` because it expects
old unavailable-profile text while the implementation emits the accepted degraded
explanation. The auth status selector at
`src/cadrumo/application/auth/tests/test_operator.py:80` expects a bucket UUID even
though the implementation correctly projects the profile label. Targeted Ruff
reports ten unsorted/unused import and shadowing errors in
`src/cadrumo/application/auth/_operator.py:28-331`,
`src/cadrumo/entrypoints/cli/_config/__init__.py:9-59`,
`src/cadrumo/entrypoints/cli/_config/_repair_profile.py:7-26`, and
`src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py:25-107`. These are lower
priority than runtime defects, but this slice cannot honestly be called green; a
zero-collected or deselected invocation is not a pass.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->

1. For `storage-reclaim-target-redirection`, reject selected targets that are
   symlinks or Windows reparse-point redirects before counting or traversing them,
   resolve each target and prove it remains below the configured storage root,
   and repeat the proof at deletion time where practical. Add non-vacuous real
   filesystem tests for a target symlink and Windows directory junction; inability
   to create the redirect must never be silently swallowed.
2. For `calculation-remedy-projection`, deliberately project every remedy. Use a
   catalogue-backed typed action only where the command and arguments are genuinely
   resolvable; otherwise retain localized non-command remediation rather than
   inventing an action. Remove the ignored argument, restore JSON/text assertions,
   and run calculate twice to prove a post-persistence presentation failure cannot
   create a second revision or event.
3. For `calculation-message-deduplication`, keep distinct structured contexts or
   aggregate them under one presented message. Deduplicate on a stable semantic
   identity only after proving contexts redundant, with adversarial equal-message
   tests across source kinds, bindings, relations, casillas, and source refs.
4. For `modelo-short-id-selector`, admit exact ids and the published 12-character
   display form, or record a separate ADR decision for broader abbreviations. Fail
   closed on collisions, identify them as id ambiguity, tell the operator to use
   the full id, correct the candidate columns, and test one-character,
   prefix-versus-suffix, and duplicate-12-character catalogues before mutation.
5. For `tui-failure-redaction`, route domain and unexpected failures through the
   canonical sensitivity-class redaction and localized error projection before
   writing widgets or summaries. Exercise secrets, tax ids, authenticated URLs,
   certificate/local paths, and structured failure context in real TUI tests.
6. For `modelo-profile-and-action-text-parity`, show the canonical active-profile
   label once on profile-scoped text surfaces, protect the bucket id consistently,
   and derive the text command from the same typed action used by JSON. Add exact
   installed text/JSON assertions for work list and status.
7. For `focused-verification-red`, update only genuinely stale assertions, remove
   or correctly use the in-flight action imports without shadowing, then rerun the
   exact integration markers, focused unit selectors, targeted Ruff, and installed
   console commands. Report each lane's real collection and result separately.
