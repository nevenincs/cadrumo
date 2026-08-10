---
tags:
  - '#audit'
  - '#cli-root-help-profile-identity'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:80fddeb22fb56989f64b78ba99f04010a8a581a0bda325869ae807e302c27a43'
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

Post-fix verification re-read the live shared tree after the remediation settled.
Both high findings and all four medium findings are resolved. Storage reclaim now
validates each selected target before traversal at
`src/cadrumo/application/storage_management/_service.py:283-287` and rejects a
symlink, junction, or resolved escape at
`src/cadrumo/application/storage_management/_service.py:359-387`. Calculation
remedies are retained as structured context and text at
`src/cadrumo/entrypoints/cli/_modelo_rendering.py:191-239`, while structured notice
identity and presentation-line identity are deduplicated separately at
`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py:618-638`. Work-unit input
is limited to 12 or 64 hexadecimal characters at
`src/cadrumo/application/modelo/_selectors.py:54-64`, ambiguity now names the
supplied id and directs the operator to the full id, and the candidate heading at
`src/cadrumo/entrypoints/cli/_modelo_cli_support.py:664` is truthful. The pinned TUI
sink redacts both summary and message values at
`src/cadrumo/adapters/inbound/tui/_status_bar.py:85-168`.

Profile/action parity is also resolved. The centralized bridge unwraps
`ResolvedNoticeAction`, validates catalogue target and live argument names, joins
the live `cli_path`, and renders argv from the live schema at
`src/cadrumo/entrypoints/cli/_common.py:417-478`; the sandbox banner composes with,
rather than replaces, derived actions at
`src/cadrumo/entrypoints/cli/_common.py:555-561`. Modelo list projects an action
only for exactly one work unit, status binds the full id for calculate, and both
text paths show the canonical profile label once at
`src/cadrumo/entrypoints/cli/_modelo_work_lifecycle_cli.py:453-547`. Logged-out
recovery binds the operator profile label rather than the storage UUID at
`src/cadrumo/entrypoints/cli/__init__.py:655-665`. Installed normal and sandbox
`app modelo work list` / `status` replays exited 0 with executable derived actions;
the isolated logged-out replay carried `operator-manual` consistently in the
active-profile projection and login binding.

The final bounded lanes were `64 passed` for storage, diagnostic, selector, TUI,
notice-action resolution, and envelope unit tests; `5 passed` for real CLI
zero/one/many list, status, sandbox composition, and login-binding integration;
and one pass each for auth active-profile projection, degraded root landing, legacy
notice-transport conformance, and calculate idempotency. A mistyped integration
node that collected zero tests is not counted. The low finding is only partially
resolved: both stale assertions now pass, but targeted Ruff still reports six
deterministic errors from unused, misordered `next_action` imports at
`src/cadrumo/entrypoints/cli/_config/_repair_profile.py:9` and
`src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py:27`, including the resulting
name redefinitions at lines 89 and 107.

A final adversarial review of the newly centralized action-text bridge qualifies
the disposition above: the seven original findings have the statuses recorded,
but one new medium action-quoting finding remains open. The catalogue, provenance,
required-input, and live-`cli_path` joins are sound; only the conversion of a
resolved argument value into pasteable shell text is unsafe.

That final medium was resolved in flight before closeout. The bridge now emits
unsafe values as PowerShell literal single-quoted tokens and doubles embedded
apostrophes. The exact adversarial resolver probe now renders
`'C:\tmp\$(Write-Output PWN)\bundle.aeat'`; the real-shell/common-action lane
passes all 13 cases, including `$()`, `$env:`, spaces, quotes, apostrophes,
backticks, and backslashes, and focused Ruff is clean for the bridge and its test.

The remaining low gate debt was also resolved before closeout. The obsolete
`next_action` imports were removed from
`src/cadrumo/entrypoints/cli/_config/_repair_profile.py` and
`src/cadrumo/entrypoints/cli/_modelo_work_runs_cli.py`; an exact two-file Ruff
rerun and diff check pass. Together with the already passing root and auth
assertions, all recorded findings are resolved in the final reviewed tree.

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

### resolved-action-shell-quoting | medium | JSON quoting leaves PowerShell expressions executable in derived commands

`src/cadrumo/entrypoints/cli/_common.py:454-478` treats a token outside
`_SAFE_ACTION_TOKEN` as safe command text after `json.dumps(token)`. JSON string
escaping is not PowerShell argument escaping: PowerShell expands `$variable` and
`$(...)` inside the emitted double quotes. This bridge is generic and already
renders operator-controlled profile names and export paths, while `ProfileName` at
`src/cadrumo/domain/contribuyente/_constants.py:26-29` deliberately constrains only
whitespace and length. A real resolver probe for `operator.profile.import` with the
path `C:\tmp\$(Write-Output PWN)\bundle.aeat` emitted
`next_action aeat config profile import "C:\\tmp\\$(Write-Output PWN)\\bundle.aeat"`.
Copying that advertised command into PowerShell evaluates the parenthesized
expression rather than passing the literal path. The typed action itself remains
safe machine data and its catalogue target, required binding, provenance, and live
`cli_path` all resolved correctly; the defect is confined to the human text
projection.

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
8. For `resolved-action-shell-quoting`, do not use JSON serialization as shell
   escaping. Either render a shell-neutral structured argv representation that is
   explicitly not advertised as pasteable, or use a platform-correct argument
   quoting authority for the supported console. Add real bridge tests with `$()`,
   `$env:NAME`, spaces, quotes, backticks, and backslashes, and prove the dispatched
   argument remains byte-for-byte data rather than executable shell syntax.

### Post-fix disposition

- `storage-reclaim-target-redirection` is resolved. The service rejects a selected
  target redirect before counting or deletion, proves resolved containment, and
  the real-filesystem test creates links or a Windows junction without swallowing
  setup failure.
- `calculation-remedy-projection` is resolved. Non-command remedies survive in
  structured context and text; executable repair remains reserved for typed
  actions. The idempotency selector confirms repeating identical calculate input
  does not persist another revision.
- `calculation-message-deduplication` is resolved. Full notice identity preserves
  distinct provenance, while separately deduplicated text avoids repeated operator
  prose.
- `modelo-short-id-selector` is resolved. One-character aliases are refused, the
  accepted displayed form has 12 hexadecimal characters, collisions refuse with
  id-specific guidance, and the candidate table exposes the full work-unit id.
- `tui-failure-redaction` is resolved at the common pinned-status sink. Every
  summary and message crosses the canonical redactor immediately before storage
  and widget presentation.
- `modelo-profile-and-action-text-parity` is resolved. Text and JSON share the same
  typed action, profile text uses the canonical label once, bucket ids stay out of
  the text surface, zero/multiple lists do not invent a target, and sandbox
  presentation preserves the derived command.
- `focused-verification-red` remains open at low severity only for the six Ruff
  errors named above. Its two stale behavior assertions are resolved and pass.
- The central action-resolution architecture is accepted for this remediation.
  Producers provide only catalogue identity and provenance-bearing values;
  application resolution refuses undeclared, unresolved, or missing required
  bindings; the CLI adds the reconciled live path and uses `cli_argv_for` plus
  `PRODUCT_IDENTITY` for presentation. No notice body hardcodes these executable
  commands, and informational prose is not forced to invent an action.
- Subsequent adversarial review leaves `resolved-action-shell-quoting` open at
  medium severity. It does not invalidate the typed action wire contract, but the
  generic human command renderer must not describe JSON-quoted PowerShell-active
  data as executable argv.
- `resolved-action-shell-quoting` was then resolved in flight. The live renderer
  uses PowerShell literal quoting, preserves the structured binding unchanged, and
  passed 13 focused real-shell and action-resolution tests. No high or medium
  finding remains open at closeout.
- `focused-verification-red` was finally resolved by removing the two obsolete
  imports. Exact Ruff and diff checks for both files pass, so no low finding remains
  open either.
