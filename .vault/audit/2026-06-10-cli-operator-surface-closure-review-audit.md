---
tags:
  - '#audit'
  - '#cli-operator-surface'
date: '2026-06-10'
related:
  - '[[2026-06-10-cli-operator-surface-adr]]'
  - '[[2026-06-10-cli-operator-surface-audit]]'
  - '[[2026-06-10-cli-operator-crud-matrix-audit]]'
---

# `cli-operator-surface-closure-review` audit: `campaign-close honesty review`

## Scope

Fresh-context honesty review (the mandatory campaign-close gate per the campaign-close-honesty-review rule) over the cli-operator-surface campaign implementing decisions D1-D8 of the operator-surface ADR plus the D4 operator-directed amendment, a retired-verb-subsystem removal, a 6-document explanation cluster, and W04 read-back surfaces. The coordinator self-reported the campaign complete. This review treats that claim as a third-party assertion and verifies each piece against HEAD on branch chore/eliminate-shims: live CLI behaviour, the shipped code for the unreviewed-by-independent-agent landings, plan-checkbox completeness, the envelope-token shadow, vocabulary-honesty residue, and peer-regression attribution. Evidence is cited by commit short-hash and file:line. Every finding is tagged a real gap or verified-OK.

## Findings

### F-OK1 D1 switch-replaces-unlock landed and behaves (VERIFIED-OK)

Commit `f2e1b0c5e` (`relocation:switch`). Live `aeat config --help` lists `aeat config switch NAME` and `aeat config bucket --help` returns No such command bucket; `unlock` is absent. `switch` wires to the session-unlock mechanics underneath: `src/aeat/entrypoints/cli/_config/_custody.py:19` documents `_register_switch_command` as Select and unlock pointer through the canonical profile lifecycle span. Hard rename, no surviving alias. Matches the D1 claim.

### F-OK2 reset-state to reset-progress landed (VERIFIED-OK)

Commit `b1d40bd51`. Live `aeat config repair --help` shows `reset-progress`; `reset-state` is absent. Verb-level rename verified-OK. Help-text jargon is a separate finding F3 below.

### F-OK3 config profile history replaces config bucket history (VERIFIED-OK, verb level)

Commit `68b86138f` (`relocation:bucket-history`). Live `aeat config profile --help` lists `history`; `aeat config bucket --help` is No such command. The verb relocation is real. The operator-facing bucket NOUN is a separate gap, F1 below; this finding covers only the command path.

### F-OK4 D4 single strict period grammar landed and behaves (VERIFIED-OK)

Commit `7c150c749` (D4 rework). Live `aeat app ledger preflight --help` advertises Filing period as an AEAT token 1T-4T and the new `--year INTEGER [required]`. `aeat app ledger preflight --period 2026Q1 --year 2026` is refused with Unrecognized period 2026Q1. Use an AEAT token 1T-4T. `src/aeat/entrypoints/cli/_common.py:247` `_canonical_period` validates through the registry period union (`aeat.core._period`) and converts AEAT-token+year to the internal calendar shape; no re-declared accepted token set. The old `_PERIOD_RE` calendar grammar is gone (only docstring mentions of 2026Q1 survive, describing what is now refused). D4 matches the claim. Sub-item: the `--filter period=` mini-grammar (which carries no `--year`) retains a year-qualified 2026-1T AEAT-token form (`_common.py:278` `_FILTER_YEAR_QUALIFIED_RE`), which the D4 amendment text described as removed. A defensible deviation (the filter clause has no separate `--year` to pair the bare token with) but a documented-claim-vs-implementation divergence. Low harm; worth a one-line ADR reconciliation.

### F-OK5 D8 preflight defaults --revision-id (VERIFIED-OK)

Commit `5dc7806c2`. Live `aeat config profile preflight --help` shows `--revision-id TEXT Optional registry ...` (no required marker). The natural-key default landed; `--revision-id` remains an explicit override. Matches the claim.

### F-OK6 --language made to work for help text (VERIFIED-OK)

Commit `ced5ef49a`. The D6 ordering picked outcome one, make it work: `aeat --language en config profile create --help` renders the English help and `aeat --language es ...` renders the Spanish help live, with no env var set. The flag no longer silently fails. Matches the strongest D6 outcome.

### F-OK7 D5 self-referential-string + enum conformance gate green (VERIFIED-OK)

Commit `2ac338d4b`. The gate lives at `src/aeat/entrypoints/cli/tests/test_self_referential_string_conformance.py` (371 lines). Ran it plus `test_json_schema_conformance.py` under `-m integration`: 155 passed. The advertised-enum-vs-handler and hint-resolves-to-live-command contracts hold at HEAD.

### F-OK8 IVA-wallet correct guard is sound, never-live intact (VERIFIED-OK)

W04.P10 IVA-wallet correction (one of the unreviewed-by-independent-agent landings). `src/aeat/entrypoints/cli/_modelo_iva_wallet_cli.py:294` requires `--confirm` (refuses without it, `:310`), requires a non-empty `--reason` recorded into an audit event, and the underlying action `correct_iva_compensation_period_for_bucket` in `src/aeat/application/modelo/_iva_wallet_seed.py:172` refuses when a sealed (already-filed) Modelo 303 consumed the seeded basis (`_iva_wallet_seed.py:83,89,190`). The honest-record and never-live-submission boundary is preserved; guard parity with the forward set-aside verbs holds.

### F-OK9 M036 + reconciliation-history read-backs are typed, no parallel write path (VERIFIED-OK)

Commits `0a76a01d8` (M036) and `6cb36cd2d` (reconciliation-history). `src/aeat/application/modelo/_m036_lifecycle.py:185` `list_m036_declarations` and `:200` `read_m036_declaration` both return typed `M036DeclarationResult` read through a `SecureSnapshotRepository` (`:158`), a read path through the owning repository, not a parallel writer. `reconciliation-history` is registered at `src/aeat/entrypoints/cli/_modelo_reconcile_cli.py:36` over a typed modelo.reconciliation_history schema (`_modelo_payloads.py:1345`). Read-back baseline (D7) is genuinely present for the in-scope surfaces.

### F-OK10 D2 ledger restore verb present with full hardening (VERIFIED-OK; brief commit hash was wrong)

The brief listed `afcb56c8b` as the restore commit; that hash is in fact an auth-tests typing commit (widen x509.NameAttribute), unrelated to restore. The restore work nonetheless landed: `src/aeat/application/ledger/_actions_lifecycle.py:133` `restore_manual_transaction` emits BucketEventType.LEDGER_TRANSACTION_RESTORED (`:193`); the CLI verb is registered at `src/aeat/entrypoints/cli/_ledger_lifecycle_cli.py:59` (`ledger_restore`, `:327`) accepting `--id`, `--reason`, `--yes`, `--actor`. D2 is real; only the brief commit attribution was incorrect. No gap.

### F-OK11 retired-verb subsystem removal is behaviour-neutral (VERIFIED-OK)

Commit `44a859855` removed RETIRED_OPERATOR_SURFACES, retired_surface_suggestion, `_RETIRED_VERBS`, the cli/retired.rst page, and the tombstone tests. A HEAD grep confirms `_RETIRED_VERBS` no longer exists anywhere, and that typing a retired verb still yields click standard No such command via AeatTyperGroup. ZERO operator-facing runtime change. Verified-OK. Downstream doc drift: ADR D1 and plan step `W03.P06.S33` both promise the `_RETIRED_VERBS` test records unlock as retired, that artefact is now deleted (see F4).

### F1 Operator-facing bucket noun NOT renamed -- D1 family incomplete (REAL GAP, MEDIUM)

ADR D1 queued the operator-facing bucket noun where the operator means profile for the same hard-rename discipline, and plan step `W03.P07.S37` is rename the operator-facing bucket noun to profile across CLI help and locale strings, keeping bucket only where it names the internal encrypted-storage concept. The command-path rename (F-OK3) landed, but the NOUN did not. Live help leaks it: `aeat config profile create --help` renders Initialize a new active profile and config bucket and Create a local tax profile bucket. `src/aeat/locales/en.yml` carries 121 bucket occurrences, many operator-facing: `:417` registered profile bucket, `:420` No active profile bucket, `:1113` List inventory ledgers in the active bucket, `:1386` Filter by bucket, `:2029` and `:2056` Initialize a new active profile and config bucket. D6 made help honest in both locales, so the leak is now visible to Spanish operators too. This is an operator-vocabulary leak the campaign own D1 discipline targets, left unclosed.

### F2 Plan checkboxes are almost entirely OPEN while the code landed (REAL GAP -- bookkeeping, MEDIUM)

`.vault/plan/2026-06-10-cli-operator-surface-plan.md`: only the six W01.P01 D5 steps S01 to S06 are checked. Every other step W01.P02 S07-S10, W01.P03 S11-S14, all of W02 S15-S31, all of W03 S32-S44, all of W04 S45-S55 is unchecked, yet the corresponding code is verifiably at HEAD: D2 restore, D3 lineage `f483d3360`, D4 `7c150c749`, D8 `5dc7806c2`, D6 `ced5ef49a`, the D1 renames, M036/reconcile/IVA read-backs. The plan-checkbox state badly under-reports actual completion. A fresh inheritor reading the plan alone would conclude most of the campaign is unstarted. The checkboxes must be ticked to reflect HEAD, or the genuinely open gaps named explicitly. This is the single largest structural-honesty discrepancy in the closure.

### F3 reset-progress help leaks storage jargon envelope and workflow-state (REAL GAP, LOW)

Live `aeat config repair reset-progress --help`: Drop the unreadable workflow-state envelope, requires --yes, and Report the envelope fingerprint. Envelope and workflow-state envelope are storage-layer nouns, the exact class of leak D1 policy paragraph condemns: an operator verb names the operator intent, not the storage mechanism. The verb name was de-jargoned, reset-state to reset-progress, but its help body re-introduces the storage vocabulary. Operator-facing; low harm but on-discipline.

### F4 ADR D1 / plan W03.P06.S33 describe the now-deleted _RETIRED_VERBS mechanism (REAL GAP -- doc drift, LOW)

Because commit `44a859855` deleted the retired-verb subsystem AFTER D1 landed, the accepted ADR text and plan step `W03.P06.S33` now reference an artefact, the `_RETIRED_VERBS` test, that no longer exists. Not a code defect, a stale decision record. A one-line amendment note on the ADR or an exec record should reconcile the removal.

### F5 Envelope-token shadow: config.bucket.history retained for config profile history (REAL TENSION -- recommend KEEP, document)

`src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py:81` keeps a _PATH_KEY_OVERRIDES map mapping config.profile.history to config.bucket.history: the operator command path is config profile history but the JSON envelope registry token stays config.bucket.history. The comment at `:73-80` states the token is a STABLE MACHINE API deliberately kept unchanged so existing machine consumers are not broken. Assessment: honest, asserted, exact, not an allowlist mute; the no-allowlist gate stays exact and catches any OTHER mismatch, and it is documented, NOT a silent bridge. But it IS, strictly, a token-level shadow against ADR caveat 1, no alias synonym shadow or deprecation window survives. The tension is real: the campaign that nuked the retired-verb deprecation subsystem on the no-shims principle simultaneously retained a machine-token shadow on the same principle surface. Recommendation: KEEP the token stable, renaming it breaks machine consumers for zero operator benefit and the JSON token is not an operator-facing spelling, but make the exception explicit in the ADR no-shadow caveat. The caveat targets operator-facing verbs and spellings; a stable machine-API token is a legitimate carve-out the ADR should name rather than leave as a test-file-only override. Do not rename.

### F-OK12 peer-regression attribution spot-checks (VERIFIED, mostly peer-attributable)

- Profile-lifecycle BUCKET_DEK_V1: `src/aeat/application/user_profile/tests/test_lifecycle.py` runs 15 passed at HEAD. The coordinator failing claim is STALE or already-fixed; not failing now and not attributable to this campaign.
- educational-docs index.md: `test_educational_docs_conformance.py` fails on `docs/how-to/index.md` citing aeat reconcile troubleshooting authenticate-with-aeat. Lines 220-226 are doc-slug list items inside a code fence, page names reconcile troubleshooting authenticate-with-aeat, not a CLI command; the conformance parser over-reaches on the doc-index fence. Last authored by `df71ba94a`, the parent userdocs campaign; fence originates in `c9d1a496f`, unrelated. Genuinely peer-attributable parser false-positive, not a regression this campaign introduced.
- M130/M202 source-bound-casilla: the candidate tests test_dormant_ledger_resolvers_fire_live and test_source_boundary_and_enrollment belong to the concurrent calculation-engine-foundations campaign, recent commits `ab903b06b` and `a85e601cf`, entirely outside the cli-operator-surface diff. Credibly peer-attributable.

Two of three are confirmed peer or false-positive; one, profile-lifecycle, is simply not failing at HEAD. No mislabeled self-inflicted regression found.

### F-OK13 deferred sub-items are documented-as-deferred, not silently dropped (VERIFIED-OK)

The ADR explicitly defers the gestor cross-profile bulk gap, CRUD F-04, its own Triage section, and the filing-record unfile and reopen decision, D7 body, deferred with rationale, touches the never-live-submission boundary. Both are honest deferrals with stated rationale, not dropped scope. No TODO or placeholder residue was found in the shipped docs cluster or new how-to files.

## Recommendations

Punch-list of items to close or formally defer before declaring the campaign structurally complete. Each is a trackable follow-up. None is CRITICAL or HIGH.

- FU-1, F2, MEDIUM: Tick the plan checkboxes in `2026-06-10-cli-operator-surface-plan.md` to reflect HEAD via vaultspec-core vault plan step check, OR convert the genuinely-open steps to explicit deferrals. The plan currently mis-reports most landed work as unstarted.
- FU-2, F1, MEDIUM: Execute plan step `W03.P07.S37`, rename the operator-facing bucket noun to profile across CLI help and locale strings in `src/aeat/locales/en.yml` and siblings, keeping bucket only for the internal encrypted-storage concept. This is the unclosed half of the D1 family.
- FU-3, F3, LOW: De-jargon the reset-progress help text, remove envelope and workflow-state envelope storage nouns in favour of operator intent vocabulary, via the aeat.locales CLI.
- FU-4, F5, recommend KEEP plus document: Add an explicit machine-API carve-out sentence to the ADR no-shadow caveat 1 naming the retained config.bucket.history envelope token as a deliberate stable-machine-API exception. Do NOT rename the token. This closes the strict-caveat tension without breaking consumers.
- FU-5, F4 plus D4 sub-item, LOW: Add a one-line amendment note to the operator-surface ADR or an exec record reconciling, first, the `44a859855` removal of the `_RETIRED_VERBS` subsystem with D1 and `W03.P06.S33` references to it, and second, the retained `--filter` 2026-1T year-qualified form the D4 amendment described as removed.

No safety violation, no never-live-submission breach, no data-loss path, and no architectural mismatch was found. The campaign substantive decisions D1-D8 all behave at HEAD as claimed.

## Codification candidates

The ADR already enumerates three codification candidates: operator-verbs-name-operator-intent, cli-hint-and-enum-choices-conformance-gated, set-aside-verbs-need-a-reversal-or-documented-permanence. This review surfaces one durability-worthy addition.

- Source: finding F5, machine-API token retained as a shadow under a strict no-shadow rollout. Rule slug: `machine-api-tokens-are-a-named-exception-to-operator-rename`. Rule: When an operator-facing CLI verb is hard-renamed under the strict no-alias and no-shadow rollout, a stable machine-API token such as a JSON envelope key or schema registry path that downstream consumers depend on MAY be retained, but ONLY when the retention is recorded as an explicit asserted exception, a conformance-gated override with a stated rationale and never a mute allowlist, and named in the governing ADR no-shadow caveat as a deliberate machine-surface carve-out distinct from operator-facing spellings.

