---
tags:
  - '#audit'
  - '#cli-root-verb-homes'
date: '2026-08-25'
modified: '2026-08-25'
body_schema: 'body-v1'
body_hash: 'sha256:bd3f23e971c12c1b6781920057bb829e5be5844dca902a59a987e106c12591ab'
related: []
---

# `cli-root-verb-homes` audit: `config versus app verb home drift`

## Scope

Every callable leaf of the live executable command graph was enumerated from the
declaration authority in `src/cadrumo/entrypoints/cli/_command_spec.py` and its
aggregator `src/cadrumo/entrypoints/cli/_command_specs.py`, then classified by the
root it is mounted under against the `ExecutionPolicySpec` it declares. The graph
carries 294 leaves: 212 under `app`, 82 under `config`.

The declared charters are the two root help strings. `config` is "Manage local
configuration and diagnostics" (`cli.config.app_help`); `app` is "Tax application
commands (ledger, modelo, overview, registry)" (`cli.root.app_app_help`). No ADR in
`.vault/adr/` states a placement rule beyond those two sentences, and no gate in
`src/cadrumo/entrypoints/cli/tests/` asserts root ownership as a property. The
existing root-grammar gate at
`src/cadrumo/entrypoints/cli/tests/test_root_grammar_invariants.py` tests only that
named retired spellings stay unmounted.

The audit uses the declared policy axes as the objective placement signal, because
they are already authored per leaf and are greppable: `calculation`, `filing` and
`registry` capabilities mark tax-application work; `profile-custody` with a
`bootstrap-root` write route marks configuration work.

Method note: the census is derived from the declared graph rather than from a
`--help` walk, so it is complete by construction rather than by sampling. Reports
here modify no production code.

## Findings

### calc-workbook-surface-under-config | critical | The entire modelo workbook calculate, export, pull and parity surface is mounted under `config google`, and one of those leaves is the only `filing`-capability leaf outside `app`.

Four leaves live at `aeat config google sync calc {export,verify,pull,compute}`,
declared at `src/cadrumo/entrypoints/cli/_config/_google_command_specs.py:333`,
`:365`, `:382` and `:407`, handled by
`src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py:142`, `:249`, `:382` and
`:502`. Their own docstrings state what they do: export the registry calculation
surface for a modelo and period to a workbook, run a three-way parity check across
AEAT oracle, local Decimal runtime and Sheets, read operator-edited cells back into
typed records, and compute casilla values from a workbook's operator edits. Each
declares `calculation`; `export` additionally declares `filing`.

Across the whole graph, `filing` appears on eleven leaves. Ten are under
`app modelo` or `app ledger`. `config google sync calc export` is the sole
exception. `calculation` appears on forty-one leaves, thirty-three under `app`. The
declared policy axes therefore already dissent from the mount point.

What is lost is not correctness but discoverability and transferability. There is
no offline workbook export verb anywhere on the CLI, so `config google` is not a
duplicate home for the workbook surface — it is the only home. An operator reading
the `app` root help ("ledger, modelo, overview, registry") is told the modelo
surface lives under `app`, and the modelo workbook surface is the one part that
does not. The application layer is not at fault: both transports already share the
one plan builder through `build_export_plan` in
`src/cadrumo/application/export/_google_operation.py:216`, so this is a verb-home
defect at the entrypoint only.

The drift is additionally baked into the JSON contract. The envelope identifiers
are the literal strings `config.google.sync.calc.export` and siblings, emitted at
`src/cadrumo/entrypoints/cli/_config/_google_sync_calc.py:200`, so a re-home is a
breaking envelope change and not a pure move.

### google-transport-split-across-both-roots | high | The Google data transport is split across both roots, with pulls under `app ledger` and pushes plus pulls under `config google`.

Sixteen leaves declare the `google` capability. Auth and folder configuration —
`config google {login,logout,register,status}`, `config google folder {get,set}`,
`config google credential-source {set,show}` — is correctly under `config`. But the
data movement is split: `aeat app ledger pull-folder` and `aeat app ledger doclink`
pull document bytes from Drive under `app`
(`src/cadrumo/entrypoints/cli/_app_ledger_management_command_specs.py:544`), while
`aeat config google sync push`, `sync probe` and the four `sync calc` leaves move
data under `config`
(`src/cadrumo/entrypoints/cli/_config/_google_command_specs.py:288`, `:309`).

An operator who learns that Drive document intake is `app ledger pull-folder`
cannot transfer that knowledge to workbook intake, which is
`config google sync calc pull`. The same transport, the same credentials, two
roots, no rule distinguishing them.

### secure-object-mirror-is-a-backup-not-a-setting | high | `config google sync push` mirrors the entire encrypted object store to Drive; that is a bulk data operation wearing a configuration mount.

`aeat config google sync push`
(`src/cadrumo/entrypoints/cli/_config/_google.py:1053`) walks every
`SecureObjectRepository` row via `iter_all_records_raw` and uploads each row's
ciphertext to Drive. It accepts `--namespace-filter`, `--limit` and `--dry-run`.
This is a backup or replication verb over the operator's whole financial corpus.
Nothing about it configures the application; it moves the application's data.

Its sibling `config google sync probe` reads Drive state back, and both sit beside
genuine settings verbs in the same group, so the group's blast radius is not
legible from its name.

### modelo-scoped-profile-readiness-has-two-homes | high | `config profile preflight` and `app modelo readiness` both answer profile readiness for one modelo target, from two roots.

`aeat config profile preflight --modelo --filing-year --period`
(`src/cadrumo/entrypoints/cli/_config/_profile_command_specs.py:596`, handler
`src/cadrumo/entrypoints/cli/_config/_profile_inspect.py:240`) reports which
profile fields a given filing context requires that are missing, delegating to
`modelo_work_profile_preflight_report` in the modelo application package. `aeat app
modelo readiness --modelo --revision-id --filing-year --period`
(`src/cadrumo/entrypoints/cli/_modelo_readiness_cli.py:28`) reports "active-profile
readiness for one modelo target". Both declare `calculation` plus
`encrypted-facts`; both are read-only; both key on the same modelo, filing year and
period triple.

Two homes for one question means an operator can get two answers and has no rule
for which is authoritative. This is the shadowed-responsibility shape the
architecture-boundaries rule rejects, surfaced at the operator boundary rather than
in the package graph.

### registry-integrity-reported-from-both-roots | medium | `config repair integrity registry` reports registry authority integrity, duplicating the `app registry verify` family.

`aeat config repair integrity registry`
(`src/cadrumo/entrypoints/cli/_config/_repair_command_specs.py:171`, handler
`src/cadrumo/entrypoints/cli/_config/_repair_cli.py:344`) reports calculation
registry authority and bundled snapshot integrity, and is the only leaf outside
`app` declaring the `registry` capability. The other twenty-two `registry` leaves
are under `app registry` and `app modelo`, including `app registry verify` and
`app registry inspect`, which exist to report exactly that authority's health.

The registry is bundled read-only data, not operator configuration, so a repair
verb over it under `config` implies a mutation door that does not exist — the leaf
declares side effect `none`.

### crash-recovery-orphaned-under-app-maintenance | medium | `app maintenance reconcile` recovers interrupted `config profile archive export` operations from the wrong root, and is the sole member of a one-verb family.

`aeat app maintenance reconcile`
(`src/cadrumo/entrypoints/cli/_app_maintenance_command_specs.py:48`, handler
`src/cadrumo/entrypoints/cli/_app_maintenance.py:47`) resolves crash-interrupted
portable profile-bundle publications, calling `reconcile_prepared_exports` in the
user-profile application package. The operation it recovers is produced by `aeat
config profile archive export`, and the recovery home for every other custody-side
interruption is the `config repair` family (`quarantine`, `reset-progress`,
`profile`).

This is the reverse drift of the findings above: profile-custody maintenance
mounted under `app`. It is also the only leaf in the entire `app` tree carrying a
`profile-bound` write route without an `encrypted-facts` capability, which is the
declared-policy tell that it is a custody verb.

### diagnostics-charter-contradicts-its-mount | medium | The `config` root help claims diagnostics, but the diagnostics family is mounted under `app`.

`cli.config.app_help` reads "Manage local configuration and diagnostics". The
seven-leaf diagnostics family is `aeat app diagnostics
{errors,latency,llm-usage,run-health,runs,telemetry flush,telemetry status}`, every
one declaring `local-storage` and nothing else. Meanwhile `config` does carry
diagnostics-shaped leaves of its own: `config check`, `config auth diagnostics
{list,report,show}`, `config repair logs`, `config provision report`.

So diagnostics genuinely spans both roots while only one root's help claims it. An
operator following the help text will not find `app diagnostics`.

### aeat-network-pull-precedent-is-inconsistently-applied | low | `config profile censo pull` is the one sanctioned AEAT network pull under `config`, and it is the precedent the Google sync verbs appear to have followed without the same justification.

Every AEAT network fetch in the graph is under `app live` — twelve `pull`-family
leaves declaring `network` — except `aeat config profile censo pull`, which
declares `encrypted-facts,network,profile-custody`. That exception is deliberate
and named in the CLI-contract rule as its worked example, because the censal data
it fetches *is* profile configuration.

The finding is not that censo pull is wrong. It is that it is the only precedent
for a fetching verb under `config`, and the Google sync verbs sit beside it while
fetching modelo calculation data, which is not profile configuration. Without a
written charter, the exception reads as a general licence.

### pull-verb-semantics-diluted-beyond-aeat | low | `pull` names three different transports across the graph, and the CLI contract defines it for only one.

The CLI-contract rule fixes `pull` as the verb that fetches data from AEAT. In the
live graph `pull` also names a Google Sheets read (`config google sync calc pull`),
a Google Drive read (`app ledger pull-folder`) and a local model download (`config
provision pull`,
`src/cadrumo/entrypoints/cli/_config/_provision_command_specs.py:75`, handler
`src/cadrumo/entrypoints/cli/_config/_provision_cli.py:96`, whose docstring is
"Fetch a model").

None of these is a contract violation as written, because the rule constrains the
AEAT direction rather than reserving the token. But the operator-facing consequence
is that `pull` no longer signals "this reaches AEAT", which was the property the
rule was written to buy.

### no-gate-enforces-root-ownership | high | Root placement is enforced by nothing; the declared policy axes make a gate cheap, and its absence is why every finding above could land.

`test_root_grammar_invariants.py` asserts that specific retired spellings stay
unmounted — a list of names, not a property. Nothing asserts that a leaf declaring
`filing` or `registry` is mounted under `app`, or that a leaf whose write route is
`bootstrap-root` is mounted under `config`.

Every finding in this audit was derived mechanically from data the specs already
carry, in a single pass over `COMMAND_GRAPH.nodes()`. A gate over that same pass
would have refused each drift at authoring time. Per the quality-gates rule the
gate must be a property, not a tally: a leaf count or an exemption count would
encode this moment and then detect nothing.

One mitigating fact reduces the cost of remediation: the runtime write guard in
`src/cadrumo/application/storage_write_policy.py` derives from the spec's declared
`write_route` rather than from a hand-maintained path allowlist, so re-homing a
leaf carries its write policy with it. The hand-sweep surfaces the CLI-contract
rule names — error-registry suggestions, `next_action` builders, the curated help
surface, and the envelope `command=` identifiers — remain.

## Recommendations

An ADR must rule on the placement criterion itself before any verb moves. The
decision it owes is: what makes a verb a `config` verb. The evidence in this audit
supports keying it on the declared `ExecutionPolicySpec` — `calculation`, `filing`
and `registry` capabilities belong to `app`; `profile-custody` with a
`bootstrap-root` write route belongs to `config` — but the criterion is a decision,
not a finding, and the two roots' help strings are today the only written charter.

Tied to `no-gate-enforces-root-ownership`: land the capability-versus-root gate in
the same change as the criterion it enforces, walking `COMMAND_GRAPH.nodes()` and
refusing on the property. Any exemption states its reason and is keyed by leaf
path, never by count. Prove the gate bites by mounting a `filing` leaf under
`config` from outside the repository and confirming it reds.

Tied to `calc-workbook-surface-under-config` and
`google-transport-split-across-both-roots`: the four `sync calc` leaves are the
first re-home candidates, because the application layer already shares one plan
builder and only the entrypoint mount and the envelope identifiers move. Treat the
`command=` identifier change as the breaking part and sweep the CLI-contract rule's
named unscanned surfaces in the same commit. `config google` retains auth, folder
and credential-source configuration.

Tied to `secure-object-mirror-is-a-backup-not-a-setting`: `sync push` and `sync
probe` are a backup surface, not a Google setting, and the ADR should rule whether
their home is an `app`-side backup family or the `config profile archive` family
that already owns portable custody export.

Tied to `modelo-scoped-profile-readiness-has-two-homes`: one of `config profile
preflight` and `app modelo readiness` is redundant. Determine whether their reports
actually differ before choosing; if they do not, delete one outright rather than
bridging, per the no-legacy-compatibility rule.

Tied to `crash-recovery-orphaned-under-app-maintenance`: `app maintenance
reconcile` is a single-verb family recovering a `config`-side operation, and
folding it into `config repair` retires the family with it.

Tied to `diagnostics-charter-contradicts-its-mount`: whichever way the ADR rules,
the `cli.config.app_help` string and the `app` root help must be corrected in the
same change, through the locale CLI. A charter that misdescribes its own tree is
what let the drift accumulate unnoticed.

Tied to `pull-verb-semantics-diluted-beyond-aeat`: lowest priority, and possibly a
wontfix. Record the ruling either way, because a later reader will otherwise
re-open it.
