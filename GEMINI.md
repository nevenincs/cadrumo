<vaultspec type="config">
## Vaultspec Rules

You MUST respect these rules at all times:

---
name: aeat-agent-delivery
trigger: always_on
---

# AEAT agent delivery

Delegate one issue at a time. Keep handovers agent-agnostic. Do not hard-code Claude, Codex, Gemini, or launcher commands into project instructions.

Balance active work across Track A for AEAT remote synchronisation and Track B for financial-input processing. Keep six-agent capacity balanced. Do not starve either track.

Bind financial-input work to the Transaction Data Pipeline step it serves. Preserve provenance from ingest through handoff. Treat Google Sheets as a one-way export mirror, never an authority.

Keep project board In Progress limited to actively worked items with a worktree and delegation. Do not mark charters, placeholders, or intent as active execution.

---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

Place Python application code under `src/aeat/`. Do not add top-level Python packages, ad-hoc module roots, or hidden parallel implementations.

Expose validated boundary data through pydantic v2 models. Use strict config where practical. Do not expose bare `dict[str, Any]` for persisted records, wire payloads, configuration, CLI input, MCP messages, LLM responses, or fixtures.

Preserve the accepted hexagonal direction. Keep domain logic independent from adapters. Keep inbound, outbound, persistence, application, entrypoint, and core responsibilities separated.

Keep the CLI root surface to `config` and `app`. Do not add a third root command family.

Do not introduce shims, compatibility layers, deprecation paths, or duplicate legacy APIs. Move callers to the canonical path instead.

Land every symbol relocation in one atomic explicit-path commit. The canonical-site move, every consumer update, every fixture update, and every `__all__` baseline update share one git index and one commit. Run `uv run --no-sync pytest --collect-only -q` immediately before the commit and observe clean collection. Never split the canonical-site move from the consumer sweep across commits. Never reintroduce a re-export as a temporary bridge. One Step = one symbol = one atomic commit. Tag the commit subject with `relocation:<symbol>` so audits can grep history for the canonical-home decisions.

Type every constant-like axis. Closed value sets (period codes, output languages, lifecycle states, source kinds, auth providers, etc.) MUST be declared as StrEnum (or Literal where appropriate) in `core/` per the core-authority ADR. Production code and CLI handlers MUST accept and emit enum members, not raw strings. The registry TOML stays free-form per the registry-authority-flow rule; the loader hydrates the typed enum at boundary. Tests MUST assert against enum members.

Hint accepted values at the CLI boundary. Every Typer argument whose value is a closed enum MUST declare that enum as its type so click renders `Choice([...])` and surfaces the accepted-value set on parse failure. Late, registry-driven refusals (e.g. modelo-period-revision combinatorial checks) are acceptable for axes that depend on dynamic registry data, but the refusal MUST list the accepted set in the error message — never a bare "value invalid" without options. The CLI gate is the operator's first instructive surface. Never make it a silent black hole.

---
name: aeat-calculation-grounding
trigger: always_on
---

# AEAT calculation grounding

Carry regulatory grounding through every domain boundary. Every casilla observation, calculation revision, filing draft, export record, and CLI emit MUST preserve its legal_refs, source_refs, and formula_id provenance from the registry source to the operator-facing surface.

Persist typed envelopes, not flat scalar mappings. RegistryFilingObservation, CasillaObservation, CalculationRevision.observations, and equivalent typed records are canonical. Do not collapse them to dict[str, Decimal] for downstream consumers. Expose a derived mapping as a property if a flat view is needed.

Emit every casilla in engine_result.values, not only computed entries. Input and bound casillas MUST produce CasillaObservation rows pulled from the registry casilla definition (legal_refs, source_refs). Pull the same fields for computed casillas from the matching engine entry. Never drop a casilla on the way to the persisted revision.

Surface legal_refs and source_refs on every operator-facing CLI JSON payload. Wrap typed observations in a parallel JSON list alongside any flat casilla_values mapping. The flat view is for human readability; the typed list is the contract.

Validate referential integrity at snapshot build. Every typed-ID reference must point at an existing entity on the snapshot. Every per-source binding selector must satisfy its typed selector model. Every cross-domain routing table (renta first-slice expense, registry capabilities, etc.) must reference real casillas in the modelo revision.

Treat type-system escapes as boundary leaks. cast(...) calls, dict[str, Any] returns, and bare str(...) coercion of typed aliases are documentation debt or design escapes. Document third-party API boundaries inline. Remove them everywhere else.

---
name: aeat-campaign-close-honesty-review
trigger: always_on
---

# AEAT campaign close honesty review

Every campaign close MUST trigger a fresh-context honesty review against the closure summary BEFORE the campaign is declared structurally complete. The agent driving execution routinely self-reports "campaign complete" while a substantial fraction of the work is still structurally incomplete. The honesty review is the gate that surfaces the hidden items.

The review may be performed by one of:

1. Independent code-reviewer agent dispatch. Use vaultspec-code-reviewer with the campaign summary, ADR, and commit ranges as context. The reviewer's findings become new Steps with verification gates.

2. Persona switch on the driving agent. Explicit prompt: "review the campaign as if you had just inherited it and list what is missing, vague, or assumed-but-unverified." Treat the response as a third-party report. Track the items as Steps.

3. vaultspec-curate skill invocation. Scan campaign artefacts for declarative-vs-action gaps - Steps that say "investigate" or "consider" without producing a verification gate; ADR claims that don't have a matching test; audit-document recommendations that aren't tracked as Steps.

Persist the honesty-review output as a vault audit document. Track every item it surfaces as a new Step with a verification gate. The campaign is NOT structurally complete until honest-pass items are either closed with verification or formally deferred (closed with a follow-up campaign reference).

A pattern of recurring multi-item discoveries per pass is documented and expected. Each pass narrows the surface; full eradication in one campaign is not the gate. The gate is: did a fresh honest review run before closure was declared?

---
name: aeat-cli-pull-and-file-standard
trigger: always_on
---

# AEAT CLI uses `pull` to fetch and `--file` for file input

## Rule

Across every CLI interface, the verb that fetches data from AEAT MUST be named
`pull`, and the option that takes a single local file as input MUST be named
`--file`. A fetch-from-AEAT command MUST NOT be named `capture`, `refresh`,
`fetch`, `download`, `sync`, or `get`; a single-file input option MUST NOT be
named `--source`, `--path`, `--from-file`, or a bespoke `--from-*` family. When
a command both reconciles and accepts either a live pull or a local file, model
it as a subgroup whose members are `pull` (fetch from AEAT) and `file --file`
(local artefact), not as one verb multiplexed by `--from-*` flags.

## Why

The reconcile surface had grown four divergent `--from-sede` / `--from-capture`
/ `--from-justificante` / `--from-declaration` flags plus a sugar verb, and the
live family used `capture`, the censo family used `refresh`, and ledger import
used `--source` — every fetch and every file-input spelled differently per
command. An operator could not transfer knowledge from one verb to the next, and
`--help` taught a different vocabulary on every screen. The
`2026-06-10-cli-pull-file-standard-adr` collapsed the surface onto two words:
`pull` always means "go read this from AEAT", `--file` always means "here is the
one local file". A single learned verb and a single learned flag now generalise
across the whole CLI. The documented-command conformance gate
(`test_documented_command_conformance.py`) prevents the how-to docs from citing a
non-canonical or dead verb, and `test_json_schema_conformance.py` keeps every CLI
leaf's `command` envelope identifier bound to a registered schema — but neither
scans production `suggestion` / `next_action` / curated-help strings, so a verb
rename MUST be swept by hand through the runtime write-policy allowlist
(`storage_write_policy.py`), the error-registry `default_suggestion` fields, the
cross-period `next_action` builders, the curated operator help surface
(`operator_surface/_help.py`), and the envelope `command=` identifiers. A
rename that updates only the verb registrations leaves dead operator instructions
and — critically — drops the verb out of the profile-bound write guard
(fail-open). This is the CLI-surface companion to `aeat-architecture-boundaries`
(the CLI gate is the operator's first instructive surface) and to
`aeat-locales-cli` (the help text for these verbs is authored only through the
locale CLI).

## How

- **Good:** `aeat app live justificante pull`, `aeat app live expedientes pull`
  / `pull-all`, `aeat app live notifications pull`, `aeat app live filed pull` /
  `pull-all` / `pull-sources`, `aeat app live iva-wallet pull-history` /
  `pull-remote-state`, `aeat config profile censo pull` — every live AEAT read is
  a `pull`.
- **Good:** `aeat app ledger import --file STATEMENT.csv` and
  `aeat app modelo reconcile file --file JUSTIFICANTE.pdf` — the single local
  file is `--file` on both.
- **Good:** a reconcile that supports both transports is a subgroup:
  `reconcile pull` (fetch the justificante from the AEAT sede) and
  `reconcile file --file PATH` (reconcile against a local artefact); `history`
  lists prior runs. No `--from-*` flag selects the source.
- **Bad:** adding a new `capture`, `refresh`, `fetch`, or `download` verb for an
  AEAT read, or a new `--source` / `--from-capture` option for a file input —
  the conformance gate and this rule reject it; rename to `pull` / `--file`.
- **Bad:** multiplexing one verb across data sources with a `--from-sede` /
  `--from-justificante` flag family instead of distinct `pull` and `file`
  subcommands.

## Source

ADR `2026-06-10-cli-pull-file-standard-adr` (accepted), which supersedes the
CLI-naming of `2026-06-10-live-justificante-reconcile-adr`; research
`2026-06-10-cli-pull-file-standard-research` (full blast radius); plan
`2026-06-10-cli-pull-file-standard-plan`. Enforced by
`src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py` and the
how-to guides under `docs/how-to/`. Promoted per the `vaultspec-codify`
discipline.

---
name: aeat-docs-scaffolding-cli
trigger: always_on
---

# AEAT documentation scaffolding CLI

## Rule

Maintain the generated API reference with the `dev.docs.apidocs` CLI; never
hand-author or hand-edit the `docs/api/*.rst` stubs. Run
`python -m dev.docs.apidocs scaffold` after any change to the `src/aeat/` module
tree — especially a symbol relocation, rename, or deletion — and land the
regenerated stubs in the same commit as the source change. Use
`python -m dev.docs.apidocs scaffold --check` as the drift gate and
`python -m dev.docs.apidocs audit` for a health report.

## Why

The API reference stubs under `docs/api/` are generated from the module tree,
and the nitpicky `-n -W` Sphinx gate imports every stubbed module. A stub left
behind for a deleted or moved module is an *orphan* that hard-crashes autodoc
with `ModuleNotFoundError`; a module added without a stub silently drops out of
the reference. During the module-relocation campaign this recurred: deleting
`adapters/inbound/pdf/_errors.py` left an orphan
`aeat.adapters.inbound.pdf._errors.rst` that reddened the entire docs-build gate
for an unrelated agent, and `apidocs audit` then found 2 orphan plus 6 missing
stubs accumulated across uncoordinated moves. The CLI is idempotent and
authoritative; hand-editing a stub drifts from the source tree and is reverted on
the next regeneration. This rule is the call-site companion to the
relocation-atomicity paragraph in `aeat-architecture-boundaries` (one atomic
explicit-path commit per relocation) and to `core-struct-docstring-links` (which
governs the docstring cross-references the stubs expose).

## How

- **Good:** a relocation commit that moves a symbol runs
  `python -m dev.docs.apidocs scaffold` and stages the regenerated `docs/api/*.rst`
  deltas (new stubs, removed orphans, updated parent toctrees) in the same
  explicit-path commit as the source move, so the docs tree never lags the code.
- **Good:** before declaring a structural refactor done,
  `python -m dev.docs.apidocs scaffold --check` exits clean (no drift) and
  `just docs-check` passes.
- **Good:** a newly-stubbed module that cross-references a stdlib name
  module-qualifies it (`:exc:`~decimal.InvalidOperation``, not bare
  `:exc:`InvalidOperation``) — the bare form is absent from the Python
  intersphinx inventory and reds the nitpicky gate the moment its stub is
  generated. Bare *project* anchors (`:class:`ModeloRevision``) stay bare: the
  short-reference resolver maps them, and `core-struct-docstring-links` forbids a
  dotted path on an anchor.
- **Bad:** hand-creating or hand-editing a `docs/api/*.rst` stub. It drifts from
  the module tree and the next `scaffold` overwrites it.
- **Bad:** deleting or renaming a module and committing without re-running
  `scaffold`, leaving an orphan stub that crashes the next `-n -W` build for a
  peer agent.
- **Bad:** running the full doc build to *discover* stub drift instead of
  `apidocs audit` / `scaffold --check` — the build is a tens-of-minutes gate; the
  audit is instant.

## Source

Operator directive recorded 2026-06-02 during the docs-educational-surface
campaign on the `chore/eliminate-shims` branch, after a relocation-orphan stub
(`aeat.adapters.inbound.pdf._errors`) reddened the nitpicky docs-build gate.
Documentation-surface taxonomy: `2026-05-30-docs-architecture-adr`. Companion
rules: `aeat-architecture-boundaries` (relocation atomicity),
`core-struct-docstring-links` (docstring cross-reference coverage),
`aeat-documentation-workflow` (the hand-written narrative surfaces this rule's
generated surfaces complement).

---
name: aeat-documentation-workflow
trigger: always_on
---

# AEAT documentation workflow

## Rule
Every change to user-facing or technical documentation must follow the `vaultspec-documentation` skill lifecycle, write incrementally in document-by-document steps, maintain simple taxpayer-general terminology, and verify command syntax against the live CLI and Sphinx build gates.

## Why
Ensuring user-facing docs are simple, technically accurate, and logically cross-linked prevents operator error and documentation rot. The dual-agent workflow isolates context collection from drafting to eliminate process noise and temporary assumptions from final documentation.

## How

### 1. VaultSpec Documentation Framing (`vaultspec-documentation`)
- **Lifecycle:** All documentation processes MUST follow the phases defined in the `vaultspec-documentation` skill:
  - **Phase 1-3:** Wireframe, Refinement (zero-context subagent), and User Approval.
  - **Phase 4-5:** Context Gathering (single-section focus) and Drafting (isolated section-by-section drafting).
  - **Phase 6-7:** Technical Review (cross-referencing codebase/conformance) and Editorial Review (zero-context prose-style review).
  - **Phase 8:** User Approval (final).
- **Dual-Subagent Pattern:**
  - **Researcher:** Gathers codebase context, help commands, and CLI output structures without writing draft files.
  - **Author:** Writes or updates the markdown pages using *only* the gathered research context.
  - **Editor:** Reviews the final pages against newcomers' clarity, tone, and link integrity.

### 2. Simple Language & Story-Driven Content
- **Simple, Non-Demanding Tone:** Do not present all options or complex parameters at once. Walk through concrete scenarios step-by-step.
- ** taxpayer Generalization:** Use general terminology like NIF, CIF, DNI, NIE, or NII rather than referring to a single group (e.g. autónomos).
- **Narrative Progression:** Guide the user from basic profile setup and transaction imports to calculations and reconciliations using clear, story-driven examples.
- **Cross-linking:** Involve the user gradually in complex topics by cross-referencing to how-to guides and CLI references.

### 3. Verification & Compliance Gates
- **Command Conformance:** Verify all documented commands against the live Click/Typer tree using `pytest src/aeat/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`.
- **Sphinx Build:** Verify all cross-references and formatting using the nitpicky build gate `pytest dev/docs/tests/test_docs_build.py`.
- **No Self-Praise:** Keep descriptions objective, factual, and free of self-congratulatory or boastful phrasing.
- **Wiki-links:** Chat responses must use absolute `file://` scheme links with forward slashes for code and files; user-facing docs use relative markdown links.

---
name: aeat-git-worktree-safety
trigger: always_on
---

# AEAT git and worktree safety — ABSOLUTE PROHIBITION

This worktree runs many concurrent agents from independent campaigns
holding uncommitted work in the index and working tree at all times.
ANY destructive Git operation can silently destroy a peer agent's
hours of in-flight work. **The following commands are categorically
forbidden in every dispatched agent's tool calls — there are no
debugging exceptions, no "I'll pop it back" exceptions, no "just to
isolate the failure" exceptions.**

## FORBIDDEN COMMANDS — DO NOT RUN, EVER

- `git stash` in any form: `push`, `pop`, `apply`, `drop`, `save`,
  `store`, `clear`, `create`, or bare `git stash`. Stash captures
  every concurrent campaign's WIP into a single blob; pop conflicts
  partially apply and silently strand peer work. The previous
  incidents are documented in audit history.
- `git reset` in any form: `--hard`, `--mixed`, `--soft`, `--keep`,
  or with a `<paths>` pathspec. Reset rewrites the index against
  files peer agents are actively staging.
- `git checkout <path>` or `git checkout -- <path>` (file restore /
  discard). Overwrites uncommitted peer work in the working tree.
- `git checkout <branch>` / `git switch <branch>`. The worktree is
  pinned to its branch; switching disturbs every parallel agent.
- `git restore` in any form (the modern alias for the above).
- `git clean` in any form: `-f`, `-fd`, `-fdx`. Deletes peer agents'
  untracked work without confirmation.
- `git rebase`, `git rebase --interactive`, `git rebase --onto`.
- `git revert <sha>` against any commit that is not your own from
  the current session. Reverting peer commits drops their work.
- `git push --force` / `git push --force-with-lease`. Rewrites
  shared history.
- `git worktree remove` / `git worktree prune` / forced branch
  deletion (`git branch -D`). Worktrees are permanent inventory.
- `rm -rf` / `Remove-Item -Recurse -Force` against any tracked path
  or any directory containing tracked paths.

## ABSOLUTE PROHIBITION — NO EXCEPTIONS

If you are tempted to use one of the above because:

- "I just need to isolate whether this failure is mine or pre-existing"
  — **NO.** Investigate by inspection: read `git diff -- <files>`,
  read `git log -- <files>`, run pytest on the specific test in
  isolation. To compare against a committed version without `checkout`
  or `stash`: copy the working file aside, `git show HEAD:<file>` and
  `Write` the committed content in place, test, then restore your copy.
  Never destroy state to debug.
- "I'll pop it right back" — **NO.** Pop can conflict; partial apply
  strands work. Two consecutive prior incidents confirm this is not
  recoverable in practice.
- "It's just my own files" — **NO.** You cannot guarantee a peer
  agent has not written into the same file in the working tree
  between your stash and your pop.
- "The pre-tool-use will allow it" — **NO.** Any agent that runs a
  forbidden command commits a critical safety violation that gets
  reported back to the coordinator and the user.

If you find yourself genuinely blocked and reaching for these tools,
**STOP and report**. The coordinator will adjudicate. Reporting
"blocked because I would need to stash" is acceptable; running
`git stash` is not.

## ALLOWED OPERATIONS

- `git status`, `git status --short`, `git diff`, `git diff -- <paths>`,
  `git diff --stat`, `git diff --cached`, `git log`, `git log --oneline`,
  `git log -S <symbol>`, `git log -- <path>`, `git show <sha>`,
  `git stash list` (read-only view, NOT mutating), `git ls-files`,
  `git branch --show-current`, `git rev-parse`.
- `git add -- <explicit pathspec>` for files you authored. Never
  `git add -A`, never `git add .`, never `git add -p` (interactive).
- `git commit -- <explicit pathspec>` for files you authored. The
  message via `-m` or `-F message.file`.
- `git fetch` (read-only network operation), `git pull --ff-only`
  on `main` only when authorised (rare; coordinator decision).
- `git push` (without `--force`) of your own branch's new commits.

## OTHER WORKTREE DISCIPLINE

Keep worktrees on disk permanently. Do not move, delete, or rewrite
another agent's workspace. Report stale or merged worktrees as
inventory only.

Name branches `<type>/<issue>-<subject>` with `feature`, `bug`, or
`chore`. Name worktree folders with the slash flattened to a dash.

Provision new worktrees from main. Create the branch, push upstream
immediately, sync all dependency groups, refresh the lockfile,
install vaultspec, then return to main.

## CONSEQUENCES

A forbidden-command run by a dispatched agent is logged as a
security incident in the audit trail, escalated to the user, and
the responsible agent's session is treated as compromised — its
output is reviewed for unrelated destructive side-effects before
any of its work is trusted. Repeat offences across the agent fleet
trigger a coordinator-level review of dispatch briefs.

---
name: aeat-local-execution
trigger: always_on
---

# AEAT local execution

Use `fd` and `rg` for discovery and search. Prefer native PowerShell commands in this environment. Do not wrap normal commands in `pwsh`, `powershell`, `cmd /c`, or `bash -lc` unless a tool explicitly requires a separate shell process.

Use the uv-managed workflow. Prefer platform-agnostic project configuration over shell-specific variants.

Run real gates. Do not use mocks, fakes, stubs, patches, monkeypatches, skip, xfail, or tautological assertions as shortcuts. Prefer real-behavior tests with useful diagnostics when failures need trace context.

Re-run before blaming the code. Registry-suite failures under parallel pytest (`-n N`) are more often a loader-cache race than a real regression. Re-run the failing tests sequentially before triaging them as a regression.

---
name: aeat-locales-cli
trigger: always_on
---

# AEAT locale catalogue CLI

## Rule

Perform all locale-catalogue work through the `aeat.locales` CLI; never
hand-edit the `src/aeat/locales/{en,es,ca,hu}.yml` files or the
`_intentional_identical.json` allowlist directly. Use `python -m aeat.locales
set LOCALE KEY VALUE` and `python -m aeat.locales remove LOCALE KEY` for
individual string leaves, `python -m aeat.locales scaffold` to align the
catalogues with the concrete translation keys in the codebase, `python -m
aeat.locales scaffold --check` as the drift gate, and `python -m aeat.locales
audit` for a codebase-to-locale health report.

## Why

The four locale catalogues are not free-form YAML: the parity gates
(`test_parity.py`) require every codebase translation key to exist in every
locale and every locale to carry the same key set, and the translation-honesty
gate (`test_locale_translation_honesty.py`) ratchets the number of keys left
identical to English, allowing an untranslated string only when
`_intentional_identical.json` records it with an explicit reason. Hand-editing a
`.yml` bypasses these structural guarantees: it is how a key lands in one locale
but not the other three (inter-locale parity break), how a stale key outlives its
removed codebase reference (codebase-to-locale drift), and how an untranslated
string slips past the honesty ratchet. The CLI maintains key parity across all
four files in one operation and keeps the allowlist honest, so the gates stay
green. This rule is the locale-surface sibling of `aeat-docs-scaffolding-cli`
(the generated-documentation CLI) and complements the audience-separation
mandate that user-facing docs must not re-author or reuse locale keys.

## How

- **Good:** translating one string runs `python -m aeat.locales set es
  "cli.config.google.help" "Configura las credenciales de Google"`, which writes
  the leaf and preserves key parity; a follow-up `scaffold --check` and `audit`
  exit clean.
- **Good:** after adding or removing a `tr(...)` call in the code, run
  `python -m aeat.locales scaffold` so every catalogue gains the new key (or
  drops the retired one) in the same change, then `scaffold --check` confirms zero
  drift before commit.
- **Good:** a string that is legitimately identical across locales (a brand name,
  a bare modelo code) is registered through the CLI / honesty-gate process that
  updates `_intentional_identical.json` with a reason — never by silently leaving
  it untranslated.
- **Bad:** opening `es.yml` in an editor to add a key. It almost always lands in
  one locale only, tripping the inter-locale parity gate, and skips the honesty
  ratchet entirely.
- **Bad:** hand-appending an entry to `_intentional_identical.json` to silence the
  honesty gate for a string you simply did not translate. The allowlist is for
  deliberately-identical strings with a stated reason, not a mute button.
- **Bad:** running the full test suite to discover locale drift instead of
  `aeat.locales audit` / `scaffold --check`, which report it instantly.

## Source

Operator directive recorded 2026-06-02 during the docs-educational-surface
campaign on the `chore/eliminate-shims` branch, authored alongside
`aeat-docs-scaffolding-cli` to give the locale surface the same
CLI-is-authoritative discipline. Backing gates: `test_parity.py`
(codebase-to-locale and inter-locale parity), `test_locale_translation_honesty.py`
(the `_intentional_identical.json` untranslated-ceiling ratchet).

---
name: aeat-pytest-background-capture
trigger: always_on
---

# Background pytest capture: write the full log to disk, then read

## Rule

When launching pytest in the background, write the **full** output to a log file and read it back from disk. Do not pipe through `Select-Object -Last N` (or `tail -n N`) BEFORE Tee-Object — the truncation happens upstream of the file write, and only the last N lines reach the log. The `FAILED` / `ERROR` summary lines are then lost and the diagnostic value of the background run is destroyed.

## Why

Across one rolling burndown session three separate background pytest captures used the pattern `pytest ... 2>&1 | Tee-Object -FilePath foo.log | Select-Object -Last 5` and produced 5-line log files instead of full output. The fail list went into the truncated pipe before Tee wrote, and Tee dutifully wrote 5 lines. The runs were correct but their value was zero because there was no way to identify which tests failed. Re-running the same probe cost 7 to 45 minutes each pass — the cost of a bad capture is the cost of an extra full suite run.

The correct shape is to let Tee-Object see the full stream, then read the file with `Get-Content -Tail N` or `Select-String -Pattern '^FAILED'` afterwards. The on-disk log keeps every line; the operator decides how to slice it.

## How

- **Good:** background launch with full file capture:
  `uv run --no-sync pytest src/aeat -n auto -q --tb=no --no-header 2>&1 | Out-File -FilePath suite.log -Encoding utf8`
  then post-completion `Get-Content suite.log | Where-Object { $_ -match '^FAILED' } | Sort-Object -Unique` to extract the fail list.

- **Good:** when launching via the Bash/PowerShell `run_in_background: true` flag (which already writes the full pipe to a per-task output file), simply `Read` the output file and use `Select-String` or `Where-Object` to slice the relevant rows.

- **Bad:** `pytest ... 2>&1 | Tee-Object -FilePath suite.log | Select-Object -Last 5` — the file only carries the last 5 lines. Same shape with `| head -N` (bash) is the same trap.

- **Bad:** `pytest ... 2>&1 > suite.log; Get-Content suite.log -Tail 5` looks fine but actually skips stdout redirection unless `2>&1 >` is paired correctly. Prefer `Out-File` or `Tee-Object` without truncation in the pipeline.

- **Bad:** running a 45-minute full suite, watching the summary, and discarding the per-test FAILED rows — the next investigation cycle then has to re-run the suite.

## Source

Operator-direct burndown session 2026-06-02 to 2026-06-03; three suite runs lost their FAILED lists to the Tee-Then-Select truncation antipattern. Recorded under session-honest-followups plan Step P03.S16.

---
name: aeat-quality-gates
trigger: always_on
---

# AEAT quality gates

Write real-behavior tests. Do not use fakes, mocks, stubs, monkeypatches, skipped tests, xfail markers, or tautological assertions to make gates pass.

For calculation tests, derive expected values from AEAT workbooks, BOE or AEAT examples, registry-authoritative fixtures, or live oracle replay. Do not hand-compute the same formula that the registry declares.

Test structure, graph wiring, validation errors, and provenance when no external numeric oracle exists. Do not assert arbitrary Decimal outputs produced only by the test author.

Reject duplicated symbols, shadowed responsibilities, misplaced code, import cycles, dead code, and cross-package private imports. Run structural audits at milestone and cluster gates.

---
name: aeat-rag-discovery
trigger: always_on
---

# AEAT RAG discovery

**Standing mandate — RAG-first code grounding for every worker.** Before any non-trivial code work — locating an implementation, discovering all sites of a concept, scoping a feature surface, or grounding a change — run a vaultspec-rag code search FIRST, then narrow with grep. This binds the coordinator, every dispatched subagent, and every future worker. Every dispatch brief that involves touching code MUST instruct the worker to ground via `vaultspec-rag search "<concise noun phrase>" --type code --port 8766 --max-results 12 --timeout 30` before editing, then verify exact symbols with grep. Discovery in this codebase is unreliable solo-grep-only; RAG surfaces conceptually identical sites grep misses (see the cross-vocabulary examples below). The `--timeout 30` flag is REQUIRED on every `vaultspec-rag search` invocation to avoid the model-warmup/first-query timeouts that otherwise abort the search.

Use vaultspec-rag for semantic search before grep when you know the concept but not the project's chosen vocabulary. Run `vaultspec-rag search "<query>" --type code|vault --port 8766 --max-results N --timeout 30`. The RAG indexes source chunks and `.vault/` documents under one embedding model and surfaces conceptually identical locations across vocabulary mismatches that grep cannot recover. Use grep only to pin the exact symbol, path, or literal string once RAG has located the surface (RAG for discovery, grep for confirmation).

Scope new feature surfaces with both passes. `--type code` returns implementation chunks. `--type vault` binds them to the ADR, plan, exec, and audit trail that justifies the code. Inspect the highest-score hit per directory. Ignore the long 0.0x tail.

Route every command through the resident service. Check `vaultspec-rag server status` first (exit 0 = running; start it with `vaultspec-rag server start` if stopped). Pass `--port 8766` and `--timeout 30` to every `search`, and `--port 8766` to every `index`, so they delegate through the service rather than each spawning a competing qdrant lock holder. Local-file qdrant is single-writer; concurrent stdio MCP children strand each other on the lock.

Reindex after substantial edits and before consequential reasoning: `vaultspec-rag index --type all --port 8766`. Incremental ingest is under 15s on this codebase and the service holds the GPU models warm.

Treat the CLI `--language`, `--function-name`, `--class-name`, and `--node-type` flags as no-ops against the HTTP fast path; they return identical results for nonsense filter values. For AST-level narrowing, call the `search_codebase` MCP tool directly with the filter fields and verify the response shape.

Phrase queries as one concise sentence or noun phrase. Do not write verbose multi-clause paragraphs; they dilute the embedding signal sharply. A 50-word natural-English description caps top scores around 0.02 even when the right module is in the top hits, while the same concept phrased as a six-word noun phrase scores 0.5 to 0.9 on the same surface.

Read directory clustering across the top results, not just the single highest score. When absolute scores collapse below 0.1, look for the same module or `.vault/` feature folder repeating across three to five hits; that cluster is usually the right surface even when no single result clears the visible noise floor.

Expect concept-as-thing queries to score high and concept-as-event-flow queries to score low. "Where is X evaluated", "what is the reconciliation surface", and "where do we project invoices" return tight clusters with strong scores. "What triggers Y when Z happens" and "how does this connect to that" return correct topology with weak scores. Lean on the cluster pattern when the score signal is thin.

Plan for translation-file and test-docstring crowding in result tables. This codebase ships parallel `locales/{en,es,ca,hu}.yml` files; the same translated string returns four near-identical hits per concept and consumes most of `--max-results`. Test docstrings often outrank the production module they exercise because tests spell out the concept more explicitly. Raise `--max-results` to 12 to 20 for code searches, skip past locale and test rows when you need the production surface, and treat the same string in four languages as one signal, not four.

Phrase vault queries toward the document-title and heading vocabulary actually used under `.vault/`; colloquial paraphrase degrades vault score quality sharply. Code queries tolerate paraphrase and partial misspellings; the hybrid dense and sparse index recovers most jargon, distinctive single tokens, and typos.

Default to RAG for cross-vocabulary concept lookups. Grep returns the test scaffolding and misses the authority surface when the codebase and the developer use different terms for the same idea (for example "duplicate" vs "fingerprint", "guard" vs "gate", "fake" vs "stub", "soft delete" vs "archive").

---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority flow

Treat the modelo registry as a deterministic authoring-compiler pipeline:

`TOML authoring tree -> loader/compiler -> strict schema objects -> registry validation -> validated authority -> immutable snapshots -> runtime projections`.

Keep `ValidatedRegistryAuthority` as the production orchestration boundary for registry-backed modelo access. Request validated modelos, deadline windows, and snapshots through the authority or a repository facade that owns an authority. Do not add new production paths that call raw loaders and then independently validate or select revisions.

Keep `_loader.py` as the TOML compiler implementation detail. Loader changes MUST preserve deterministic merge order, reject ambiguous scalar conflicts, include every read TOML file in cache invalidation, and compile fragments into the existing strict `ModeloDefinition` / `ModeloRevision` runtime schema.

Keep snapshot construction authority-owned. Runtime consumers such as filing schema providers, query services, formula execution, export parsing, and adapter projections MUST consume `RegistrySnapshot` or typed projections derived from snapshots, not fragment paths or partially merged raw dictionaries.

Invalidate any cache above the loader by the complete registry tree fingerprint, including directory-mode manifests and recursive revision fragments. Do not introduce path-only registry caches that can serve stale TOML after source edits.

---
name: aeat-roundtrip-discipline
trigger: always_on
---

# AEAT roundtrip discipline

Write strict roundtrip tests for every persistence boundary, not just every pydantic model. Give each of these its own dedicated roundtrip test: encrypted SQL via SecureObjectRepository, TOML manifests, JSON envelopes, fichero-BOE bytes, worksheet export/pull, and any CLI emit path that flows over the wire.

Use real adapters, not mocks. Real EphemeralMasterKeyProvider, real SQLite engine, real serializer/deserializer. A mock that returns what the test expects is the canonical false-positive signal.

Assert strict pydantic equality across the boundary. Build a populated model on one side, push through the real cycle, load on the other side, assert model_a == model_b. Mocks, partial-field comparison, and string-shape checks are insufficient.

Populate every defaultable field with a non-default value in roundtrip fixtures. A save-drops-field / load-re-defaults-field regression is invisible when the test fixture uses the default. Set state to a non-default lifecycle stage, populate optional metadata triples, fill empty containers with real entries. Rely on typed model_validators that reject partial defaults to lock the boundary.

Provide an anti-tautology proof test for each boundary class. Save a record, mutate the on-disk payload to delete a field, reload, and assert either ValidationError raised or strict inequality surfaced. If this test ever passes with the boundary broken, every roundtrip in the suite is tautological.

Never use xfail, skip, or stub. A test that passes today but is documented as expected-to-fail is a process leak. Write tests that fail loudly today when the structural work is incomplete, and pass cleanly when it lands. Do not wrap roundtrips in try/except to hide failures.

Carry every roundtrip in the production test path. Tests in scratch/ are ephemeral; tests under src/aeat/.../test_*.py participate in the CI gate. Move ad-hoc verification scripts into the durable test surface as soon as they prove a contract worth defending.

---
name: aeat-safety-legal-gates
trigger: always_on
---

# AEAT safety and legal gates

Never perform live AEAT submission. Build, validate, verify, export, and require human filing outside the app. Treat live-write paths as prohibited unless a future accepted ADR explicitly replaces this rule.

Guard every external AEAT write surface behind explicit live-test controls. Use `AEAT_LIVE_TESTS_ENABLED` for live-test opt-in. Keep dry-run behavior as the default.

Ground tax semantics in BOE, AEAT publications, AEAT workbooks, registry sources, or live oracle replay. Do not invent legal behavior. Do not treat user preference as authority for regulated calculations.

Reject tests or code paths that can file, mutate, notify, or submit remotely without an explicit safety gate and auditable provenance.

---
name: aeat-schema-central-config
trigger: always_on
---

# AEAT schema and constants live in the central config / registry

All AEAT schema, constants, thresholds, regulatory codes, and
registry-shaped data MUST be defined in the central config or the
registry authoring tree — never inlined as Python literals in feature
modules. Feature code reads from the authority; it does not redeclare
regulatory values.

## Why

AEAT regulatory values (M347 threshold, IRPF tipos, period codes,
deadline windows, casilla legal_refs, BOE article numbers, RD
references, modelo revision identifiers) are versioned by filing year
plus revision. A Python literal in a feature module bakes the value
into the call site, scatters the authority across the codebase, and
silently drifts when AEAT publishes a new revision. The compiled
registry snapshot is the single source of truth; the central
:class:`aeat.core.config.Settings` is the single source of deployment
settings. Both are pydantic-validated at the boundary so a feature
module that reads them gets a typed record, not a raw string.

The companion rule `aeat-registry-authority-flow` defines the
TOML-authoring → loader/compiler → strict-schema → validated-authority
pipeline that this rule enforces at the call-site end.

## How

- **Good:** read AEAT regulatory values through the registry
  authority. `authority.snapshot("130", filing_year=2026, period="1T")`
  returns a typed `RegistrySnapshot` carrying every casilla, formula,
  legal_ref, and source_ref. Feature code consumes the typed record.

- **Good:** read deployment settings through
  `aeat.core.config.load_settings()` (which honours
  `override_settings()` for tests). The `Settings` pydantic model is
  the single config surface; per-axis env vars are validated there
  once and surfaced as typed fields.

- **Good:** new AEAT thresholds, deadline windows, or per-modelo
  constants land first in the registry TOML under
  `src/aeat/_data/registry/aeat/modelos/<modelo>/...` and ride through
  the loader/compiler. Feature code reads the compiled snapshot.

- **Good:** a one-line `from ...core.external_constants import
  M347_THRESHOLD_EUR` is acceptable when the constant is a true
  regulatory value pulled from the central authoring surface
  (`external_constants` is the curated re-export layer for the small
  set of leaf constants that are easier to consume by-name than via
  the registry).

- **Bad:** writing `THRESHOLD = Decimal("3005.06")` inline in a
  feature module. The threshold is a regulatory value; if AEAT moves
  it, this literal silently drifts.

- **Bad:** redeclaring period codes (`PERIODS = {"1T", "2T", "3T",
  "4T"}`) or modelo IDs as bare-string sets / frozen-sets in feature
  modules. The closed set lives in `aeat.core.external_constants`
  (or the registry); consume the canonical enum / tuple.

- **Bad:** hardcoding env-var defaults (`LIVE_TESTS_ENABLED = "0"`)
  in feature modules. Those belong on the `Settings` model with a
  `Field(default=...)` declaration.

- **Acceptable exceptions:** pure mathematical or framework constants
  (`CENT = Decimal("0.01")`, the AEAT control-letter table
  `TRWAGMYFPDXBNJZSQVHLCKE`, sentinel zero `Decimal("0")`). Translation
  KEY literals (`"cli.config.google.help"`) are fine; literal
  user-facing Spanish prose is not — the locale files are the
  authority for that.

## Status

Active. Applies to every new feature module and to remediation of
existing inline-literal call sites discovered by the rolling audit
swarm.

## Source

Operator directive recorded 2026-06-02 during the autonomous-PM
session driving the chore/eliminate-shims branch.

---
name: aeat-source-hygiene
trigger: always_on
---

# AEAT source hygiene

Keep source code free of project-management metadata. Do not encode waves, phases, agent names, issue workflow, handover state, temporary migration labels, or process history in production identifiers, comments, fixtures, schemas, or public APIs.

Use domain names that remain true after the current project plan changes. Replace transient labels with stable tax, filing, storage, adapter, or workflow terminology.

Do not land design-only implementation shells. Ship working behavior, executable validation, and useful tests together.

---
name: aeat-spanish-stem-naming
trigger: always_on
---

# AEAT domain concepts use Spanish stems

Domain concepts that map 1:1 to AEAT surfaces MUST be named with their
Spanish stem in source code, locale keys, CLI verbs, audit-trail field
names, and `BucketEventType` values. Do not introduce English aliases
or English shim modules over a Spanish-named implementation.

## Why

AEAT publishes its surfaces, regulatory text, and operator-visible
labels in Spanish. The codebase's load-bearing concepts already follow
the Spanish stem (`iva`, `renta`, `modelo`, `casilla`, `censo`,
`borrador`, `declaracion`, `justificante`, `apoderamiento`,
`retencion`, `recargo de equivalencia`, `expediente`, `sede`). Naming
the implementation in the language of the surface it integrates with
keeps the developer mental model aligned with AEAT documentation; an
English alias layer (`Vat*`, `Census*`, `Form*`, `Receipt*`, etc.)
invites drift, duplicates vocabulary in tests and locales, and
silently rots when AEAT updates the Spanish surface.

The convention was applied retroactively to the M036 census-sync
rollout — the plan was authored in English (`Census*`) but the
implementation shipped under `Censo*` to match the AEAT G313 page
title "Mis Datos Censales". The same retroactive resolution applies
to the earlier `vat` → `iva` and `box` → `casilla` renames.

## How

- **Good:** `aeat.application.live._censo` with `CensoSnapshot`,
  `CensoSnapshotService`, `CensoFactSet`, `CensoSyncError`. CLI verbs
  `aeat config profile censo refresh / show / compare / apply`.
  Locale keys `cli.config.profile.censo.*` across all four target
  languages. `BucketEventType.CENSO_REFRESHED`, `CENSO_APPLIED`,
  `CENSO_DEPENDENT_STAMPED_STALE`.

- **Good:** `aeat.domain.iva` with `IvaCategory`, `IvaRateKind`,
  `IvaFlowDirection`, `IvaInvoiceClassification`. CLI verbs and
  locale keys under `cli.ledger.iva.*`. `BucketEventType.IVA_*`.

- **Good:** plan documents authored before this rule may keep their
  English Step text verbatim for identifier stability; the
  implementation ships under the Spanish stem and the exec record
  explicitly names the Spanish symbol that satisfies each English-
  named Step (the M036 closure on commit
  `exec(modelo-036-census-sync): close P02+P03+P04+P06` is the
  canonical reference for this pattern).

- **Bad:** introducing a new `_census.py` module that re-exports
  `CensoSnapshot` as `CensusSnapshot` for "compatibility." There is
  no compatibility surface to preserve; the Spanish stem is the
  canonical name.

- **Bad:** authoring a new ADR / plan / Step in English (`Vat*`,
  `Census*`, `Form*`) when the AEAT surface uses a Spanish noun.
  Use the Spanish stem at authoring time and avoid the retroactive
  resolution.

- **Acceptable exceptions:** generic computing vocabulary that has
  no AEAT counterpart (e.g. `repository`, `service`, `validator`,
  `boundary`, `snapshot`) stays English. Cross-cutting framework
  concepts that bind multiple AEAT domains (e.g. `Settings`,
  `Registry`, `Snapshot`) stay English where the English word is the
  framework convention.

- **Acceptable exception:** the operator-facing ledger invoice CLI noun is
  the English `invoice` by direct operator directive:
  `aeat app ledger invoice --kind issued|received`. Internal source-kind
  taxonomy remains canonical and load-bearing as `payable_invoice` and
  `collectible_invoice`; do not collapse those internal strings into a bare
  `invoice` source kind.

## Status

Active. Applies to every new domain symbol, locale key, CLI verb,
audit-trail field, and `BucketEventType` value that names an AEAT
surface. Pre-rule artefacts whose English naming is already public
keep their identifiers for stability; the implementation underneath
must use the Spanish stem.

## Source

Operator directive recorded 2026-06-02 during the autonomous-PM
session driving the chore/eliminate-shims branch, formalising the
convention applied to the M036 census-sync rollout
(sibling ADR `2026-06-02-modelo-036-census-sync-adr`).
Invoice CLI exception recorded in
`2026-06-10-ledger-invoice-unification-adr`.

---
name: aeat-swarm-audit-cadence
trigger: always_on
---

# AEAT swarm audit cadence

Run the multi-agent audit swarm on the event triggers below, not only when something feels off. Treat it as a standing gate, not an ad-hoc rescue tool. The swarm is the most reliable surface for catching cross-domain drift, persistence-boundary gaps, type-erasure regressions, and discriminator coverage holes — drift that no single-agent pass would notice.

Trigger the swarm under three conditions. First, before any release cut that has crossed a domain boundary or persisted a new record type. Second, after any major structural refactor that touches more than two domain subpackages. Third, every 6–8 commits on a long-running branch when no other trigger has fired in the interim, to surface drift before it accumulates.

Cover the seven standard axes. Dispatch one agent per axis: calculation-engine grounding, persistence-boundary identity, cross-domain handoffs, export/import fidelity, workflow + CLI surface, selector + binding drift, and semantic functionality-cluster overlap. Give each agent a focused scope plus an explicit reference to the established roundtrip-test pattern so findings come back as actionable structural deltas rather than open-ended commentary.

Run the seventh axis — semantic functionality-cluster overlap and canonical-definition enrollment — through the resident vaultspec-rag service. This axis discovers, by meaning rather than by symbol, every site that implements a given functional concept; classifies the set as a true duplication cluster or a constraint-shape-divergent set; and confirms that consumers import the canonical implementation rather than re-deriving it. Where no canonical home exists but two or more substitutable sites do, it nominates one. It exists because text search cannot cluster lexically different but semantically identical code: two modules that both round a Decimal to cents never co-occur in a grep result.

Query the service by functional concept, never by domain jargon. Always pass `--port 8766` and `--max-results 20`. Treat a score floor around 0.50 as the signal threshold. Use RAG for discovery, then `rg` to verify the exact sites. Filter locale and test-docstring rows and treat the same string across four locales as one signal. RAG is a clustering instrument, not a symbol locator: pair every sweep with a targeted `rg` pass for known canonical symbols so a single-site authority is not misread as having no cluster. Apply the substitutability pre-filter below — it is mandatory for this axis. RAG goes stale during active remediation; run an incremental `index --type all --port 8766` after major commits and before each sweep rather than relying on the filesystem watcher alone.

Match the model to the axis. Use sonnet for the four axes that need deeper structural analysis: calculation engine, cross-domain handoffs, selector / binding drift, semantic functionality-cluster overlap. Use haiku for the three breadth-oriented axes: persistence identity inventory, export/import fidelity, workflow + CLI surface. The cost / latency profile rewards model selection that matches the cognitive shape of each axis.

Persist every finding in the vault. Each agent writes a single .vault/audit/yyyy-mm-dd-<axis>-swarm-audit.md document with frontmatter following the vaultspec template. Write findings as third-level headings with pathway label, file:line, data lost, and a concrete remediation. Reports must not modify production code; they exist to drive subsequent action commits.

Action findings in the same incremental pattern this campaign established. Turn every finding into either a structural fix paired with a roundtrip test, a vault audit note explaining the wontfix rationale, or a follow-up task linked back to the originating audit document. Do not let findings rot in the vault unactioned — process them on the same cadence as their landing.

Treat the swarm output as inventory, not gospel. Sub-agents miss things and occasionally hallucinate file:line coordinates. Verify every finding against the current code before action. The pattern is agent-as-discovery, coordinator-as-confirmation, structural test as enforcement.

Apply the substitutability pre-filter before flagging any "X where Y exists" violation. Any audit brief that identifies a site X where a canonical alternative Y exists MUST require the auditor to verify that Y's constraint shape is a superset of (more permissive than) X's current constraint before classifying X as actionable. If Y carries additional constraints (min_length, pattern, max_length, or value-format restrictions) that X does not, the site is NOT promotable: exclude it from the findings or document it as a constraint-shape mismatch. This pre-filter eliminates the 96% false-positive rate observed in the PROMOTE-001 pass (52 of 54 sites were blocked by constraint-shape incompatibility).

---
name: aeat-swarm-orchestration
trigger: always_on
---

# AEAT swarm orchestration

This worktree is a shared workspace driven by many concurrent campaign agents. These disciplines govern how agents are dispatched and coordinated. They are the durable counterpart to `aeat-git-worktree-safety` (which governs the commands) and `aeat-swarm-audit-cadence` (which governs the periodic audit).

Drive campaigns through a persistent, role-based agent team — legal-authority, ADR-specialist, coders, reader/reviewers, commit-bot — resumed by name via the team-dispatch messaging tools. Resume a standing teammate to reuse its accumulated context. Do not spawn fresh one-shot task-named agents for work a standing role already owns.

Discover with a swarm, not solo. Solo single-agent search is unreliable in this codebase. For any non-trivial code-location, duplication, or cross-domain question, dispatch parallel discovery agents and treat their output as inventory to confirm, never as gospel. Pair semantic RAG discovery with a targeted `rg` pass for known symbols.

Drive autonomously. Long-running reconciliation and hardening campaigns run open-ended without a human in the loop. The coordinator adjudicates and persists decisions in `.vault/`, and does not stall on confirmation for choices it can resolve from the code, the rules, or sensible defaults. Treat suite runs as rolling checkpoints. Never cap work as "final", "complete", or "done"; keep the audit → fix → review cycle running.

Before dispatching a plan Step, grep `git log --grep` and check plan status — the team lands Steps in parallel and a Step may already be done. Before a coder's first edit to a file, `git diff -- <file>` and abort on non-authored WIP — peers may be mid-edit in the same file.

Re-read HEAD before recommending or acting on any finding. This is the read-side companion to the abort-on-WIP edit gate above: in this fast-landing shared worktree a peer fix can land between an agent's investigation and its recommendation, so the investigation *facts* stay valid but the "still-a-gap" *conclusion* MUST be recomputed against HEAD at report/action time. Immediately before recommending an edit or acting on a finding that names a file, run `git log -1 -- <file>` and re-read the file at HEAD; abort the recommendation if a peer commit already closed the gap. This churned the multi-year-renta campaign twice: a "GO edit the test" directive fired against the #38 M100 enrollment test that was already full-calc at HEAD (commit `5ac27ed5c`), and a #42 stale read concluded "M369 is already sound / finding mis-bundled" from a copy read before `627f0aa05` landed, when in fact both M309 and M369 were `data_fidelity` and both were upgraded together. The code-reviewer flagged the version-skew explicitly; see audit `2026-06-02-modelo-multiyear-renta-audit`.

A backgrounded agent's empty or zero-byte output file is not a death signal; transcripts flush at completion. Wait for the completion notification rather than re-dispatching on file size.

Absorb in-scope regressions rather than deferring them. Any regression a campaign's activity touches is in scope and MUST be fixed — there are no "pre-existing, not my problem" deferrals. Run standing read-only review agents over recent commits as a continuous gate.

Lead every dispatch brief with the destructive-git prohibition stated verbatim. "I know this stash/reset is safe" reasoning is the canonical violation; the brief's SAFETY header is what prevents it.

---
name: aeat-user-docs-hardening
trigger: always_on
---

# AEAT user documentation hardening

## Rule
Write user-facing documentation in simplistic, singular, imperative language as instruction steps.

## Why
Ensures documentation clarity, prevents technical detours, and optimizes token usage.

## How
- Good: Create taxpayer profile.
- Good: Import bank statement.
- Good: Run calculation.
- Bad: We will now set up the taxpayer profiles.
- Bad: Let's import our transactions.
- Bad: Running the calculations.

---
name: aeat-vaultspec-centralisation
trigger: always_on
---

# AEAT vaultspec centralisation

Keep all repo-specific agent rules in `.vaultspec/rules/rules/`. Do not place project rules, memories, policies, handover mandates, or provider-specific instructions in Claude, Codex, Gemini, or user-level agent config.

Promote durable repo guidance into vaultspec source rules or vault documents. Delete stale provider memory after migration. Treat provider files as generated outputs, not authorship surfaces.

Use `uv run vaultspec-core spec rules add` for new custom rules. Use `uv run vaultspec-core install --force` after rule changes. Do not edit generated provider rule directories or vaultspec-managed gitignore blocks by hand.

Correct an existing rule on its `.vaultspec/rules/rules/project/` source and propagate with `vaultspec-core sync`. Never hand-edit the generated `.claude/rules/`, `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md` copies — the next sync silently reverts the change, so the fix is lost.

---
name: binding-aggregation-is-typed
trigger: always_on
---

# Binding aggregation is a typed model with a closed op enum

## Rule

A registry binding's aggregation MUST be the typed `BindingAggregation` model
carrying a closed `BindingAggregationOp` enum (declared in `aeat.core`), never a
free-form `Mapping`. No call site may re-parse `aggregation.get("op")` from a raw
mapping or pick its own local default; the single `binding_aggregation_op(binding)`
accessor returns the typed op and applies the one declared per-family default in
one place.

## Why

The bindings-interface discovery found `aggregation` was a free-form
`Mapping[str, ...]` and `op` was re-derived as
`str((binding.aggregation or {}).get("op", <default>))` at ~10 sites with
divergent silent defaults (`"sum"` for the scalar-folding families, `"rows"` for
the detail-record families). The default op was therefore silently
source-dependent and unauditable, and an unknown op was caught only at resolve
time. Typing the model rejects an unknown op at registry-build, and one accessor
makes the per-family default declared data rather than scattered string literals.
Recorded in ADR `2026-06-14-bindings-interface-hardening-adr` (decision B);
exercised by `test_binding_aggregation.py`.

## How

- **Good:** read a binding's op via `binding_aggregation_op(binding)`; it returns
  a `BindingAggregationOp` member and applies the declared default for the
  binding's source when `aggregation is None`.
- **Good:** a new op value is added to the `BindingAggregationOp` enum (the
  complete registry set), so the typed field validates it at build.
- **Bad:** `str((binding.aggregation or {}).get("op", "sum"))` inline in a
  resolver — re-introduces the untyped re-parse and a local default.
- **Bad:** widening `aggregation` back to a bare mapping, or stuffing arbitrary
  keys beyond the typed model.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision B), research
`2026-06-14-bindings-interface-hardening-research` (cluster B). The relation and
formula-expression `op` axes are separate concepts and are out of scope. Companion
to `aeat-architecture-boundaries` (closed value sets are enums in `core`).

---
name: binding-names-reserved-for-registry-input
trigger: always_on
---

# "binding" is reserved for the registry-data-input concept

## Rule

The term "binding" in module names, type names, and CLI surfaces is RESERVED for
the registry-data-input concept (`DataBindingDefinition` and its value carrier /
source resolvers). Account-scoping, parsing helpers, verification gates, and other
unrelated concepts MUST NOT be named "binding". When two concepts would share a
name, the non-registry-input one is renamed to what it actually does.

## Why

The discovery found "binding" was one strong core surrounded by overloaded
homonyms: two unrelated `_profile_binding.py` modules (an OAuth account-scoping
resolver vs the registry profile-fact resolver — a direct grep/refactor trap), a
`decimal_from_string` parser misfiled in a `_decimal_binding_value` module, and a
`legal_basis_binding` test concept that actually binds a tax RATE to its BOE
article (a verification gate). Reusing the word for unrelated ideas misleads every
reader and grep-driven refactor. Reserving it for the registry-data-input concept
keeps the vocabulary load-bearing. Recorded in ADR
`2026-06-14-bindings-interface-hardening-adr` (decision E); the homonyms were
renamed in wave W05 (`resolve_active_profile`/`_active_profile`, `_decimal_parsing`,
`test_legal_basis_rate_grounding`).

## How

- **Good:** the OAuth active-profile resolver lives in `_active_profile.py` as
  `resolve_active_profile`; the str→Decimal parser lives in `_decimal_parsing.py`;
  the rate-to-BOE gate is `test_legal_basis_rate_grounding.py`.
- **Good:** the registry profile-fact resolver KEEPS the "binding" name
  (`_profile_binding.py`, `ProfileSourcedBindingResult`) — "binding" is correct
  there.
- **Bad:** naming a new module `_*_binding.py` for an OAuth/session/identity
  scoping concern, a generic parser, or a verification gate.
- **Bad:** introducing an English/Spanish alias module over a binding type for
  "compatibility" (also barred by `aeat-architecture-boundaries` / no-shims).

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision E), research
`2026-06-14-bindings-interface-hardening-research` (cluster E). Companion to
`aeat-architecture-boundaries` (no shims/alias layers) and
`aeat-spanish-stem-naming` (domain naming discipline).

---
name: binding-source-kind-single-taxonomy
trigger: always_on
---

# Binding source kinds are one canonical core taxonomy

## Rule

The binding `source` closed set MUST be the single canonical `BindingSourceKind`
StrEnum declared in `aeat.core`; `DataBindingDefinition.source` is typed as that
enum, and every per-family source-kind collection (the invoice / ledger /
counterpart frozensets) MUST be DERIVED from it, never hand-maintained as a
string-literal list. A new binding source kind is added to `BindingSourceKind`
(value byte-identical to its stored token), and the registry-vs-enum parity gate
keeps the enum and the registry-declared source set in lock-step.

## Why

The discovery found the binding source set was a MIXED Literal (some enum
members, some bare strings) with per-family frozensets hand-listed and disagreeing
with it: `LEDGER_BINDING_SOURCE_KINDS` carried only 2 of the 4 ledger kinds (so
the ledger preflight misclassified OSS / renta-income bindings), and the
`RowSetGroupingKind` members for related-party / atribución / refund did not match
the source tokens. One canonical enum with derived collections makes the closed
set a single typed home, makes "is this a ledger binding?" computable rather than
hand-maintained, and a parity gate makes a new registry source without an enum
member fail loudly. Recorded in ADR `2026-06-14-bindings-interface-hardening-adr`
(decision B); enforced by `test_binding_source_kind_taxonomy.py`.

## How

- **Good:** `DataBindingDefinition.source: BindingSourceKind`; the loader hydrates
  the registry's plain-string token to its member at the boundary.
- **Good:** `LEDGER_BINDING_SOURCE_KINDS = frozenset(k for k in BindingSourceKind if ...)`
  — derived from the enum, complete by construction.
- **Bad:** a new `INVOICE_BINDING_SOURCE_KINDS = {"collectible_invoice", ...}`
  hand-listed string set, or a mixed enum/string Literal on `source`.
- **Bad:** renaming a stored source token to "align" it — the enum VALUE must
  equal the stored token (behaviour-preserving lift), and the
  `retired-enum-members-need-consumer-reconciliation` rule governs any member move.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision B), research
`2026-06-14-bindings-interface-hardening-research` (cluster B). Companion to
`aeat-architecture-boundaries`, `aeat-schema-central-config`,
`retired-enum-members-need-consumer-reconciliation`.

---
name: binding-validation-single-contract
trigger: always_on
---

# Binding validation: one contract, enforced at registry-build

## Rule

Every registry binding `source` family MUST expose a single
`validate(binding) -> list[str]` validator (accumulating, never raising),
registered in the one binding validator dispatch table keyed by
`BindingSourceKind`, and run by the registry-build section validator for ALL
families. A binding's op/fact invariants MUST be enforced at registry-build
time, never resolve-time-only; resolve-time helpers may remain only as
defence-in-depth backstops, and the underlying pydantic field error MUST be
preserved in the diagnostic (never flattened to a generic "malformed selector").

## Why

The bindings-interface discovery found validation scattered across three
incompatible conventions — public `validate_* -> None` that raised (invoice,
ledger), a `-> list[str]` accumulator (withholding), and no public validator at
all (counterpart, the four detail-record families) — with op/fact invariants run
at registry-build for counterpart/withholding but only at resolve time for the
detail-record families and `previous_filing`. A malformed binding for those
families shipped clean through snapshot build and failed only when a taxpayer's
calculation ran. One contract, run at build for every family, makes a malformed
binding a loud registry-build failure for all sources uniformly, closing the
stricter-than-runtime / looser-than-runtime gradient. Recorded in ADR
`2026-06-14-bindings-interface-hardening-adr` (decision A); the build gate is
exercised by `test_binding_build_validation.py`.

## How

- **Good:** a new source family is added to the `_BINDING_VALIDATOR_REGISTRY`
  dispatch table with a `validate(binding) -> list[str]` entry; the registry-build
  section validator runs it for every binding of that source and accumulates
  failures in one pass.
- **Good:** the validator routes the selector through `selector_as_dict` for
  normalisation and surfaces the pydantic field message verbatim.
- **Bad:** adding a per-family `validate_*_binding_definition` that raises, or a
  private `_validated_*_selector` invoked only inside the resolver — that
  re-creates the build-vs-resolve split this rule closes.
- **Bad:** flattening the selector validation error to a generic string, losing
  the field that drifted.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision A), research
`2026-06-14-bindings-interface-hardening-research` (cluster A). Companion to
`aeat-registry-authority-flow` (the registry is the authority) and
`no-silent-under-declaration`.

---
name: binding-values-carry-provenance
trigger: always_on
---

# Binding values carry provenance at casilla parity

## Rule

Every persisted and operator-facing binding value MUST carry its `legal_refs` and
`source_refs` and a typed `BindingSourceKind` source, at parity with casilla
provenance (`ModeloCasillaProvenance`). The filing builder populates them from the
binding definition; a hardcoded free-text source string (e.g. `"registry binding
input"`) is forbidden. The CLI bindings list/preview payloads MUST expose the same
grounding and be typed models, never an untyped `dict` bag.

## Why

The discovery found a provenance asymmetry at exactly the operator boundary:
casilla values carried full `legal_refs`/`source_refs` to draft and export, but
binding values were flattened to a hardcoded `source="registry binding input"`
with no grounding on the `ModeloBindingValue` carrier or the CLI payloads — even
though the registry binding definitions hold that grounding and the export layer
still emits it. An operator inspecting or filing a bound value could not see its
legal basis: the bindings half silently breached `aeat-calculation-grounding`
that the casilla half upholds. Recorded in ADR
`2026-06-14-bindings-interface-hardening-adr` (decision D); the encrypted-boundary
roundtrip + anti-tautology proof is `test_binding_value_provenance_roundtrip.py`.

## How

- **Good:** `ModeloBindingValue` carries `legal_refs`/`source_refs` +
  `source: BindingSourceKind`; the filing builder reads `binding.legal_refs` /
  `binding.source_refs` / `binding.source` from the definition it already holds.
- **Good:** `bindings list` returns a typed `BindingRowPayload` sequence carrying
  the grounding, not `list[dict[str, object]]`.
- **Bad:** constructing a `ModeloBindingValue` with a literal free-text `source`
  string, or dropping the binding definition's grounding at the builder.
- **Bad:** a bindings CLI payload that omits `legal_refs`/`source_refs` while the
  casilla payload carries them.

## Source

ADR `2026-06-14-bindings-interface-hardening-adr` (decision D), research
`2026-06-14-bindings-interface-hardening-research` (cluster D). Companion to
`aeat-calculation-grounding` (provenance through every boundary),
`aeat-roundtrip-discipline` (the persistence-boundary tests), and
`cli-notices-are-the-only-diagnostic-channel`.

---
name: calculation-source-canonical-mechanism
trigger: always_on
---

# One canonical aggregation mechanism per calculation type

## Rule

Each calculation value channel has exactly one canonical mechanism per
calculation type per the aggregation-taxonomy table: cross-MODELO fold-ins are
relations (`cross_model_output` / `annual_summary` / `previous_period`),
same-modelo static carry is a direct `previous_filing` binding, ledger projection
is a ledger aggregation resolver, cross-member fan-in is a `per_grupo_member`
binding, and M303 compensación is the IVA wallet decision; a new aggregation
surface MUST enroll under an existing row or amend the ADR before shipping —
never model one fold-in two ways at once.

## Why

ADR `2026-06-10-calculation-aggregation-taxonomy-adr` (Implementation §1 table,
Option A) decided this because the engine's value channels had multiple
overlapping mechanisms with implicit canonicality: the M100←M130 fold-in was
declared BOTH as a relation and as a `previous_filing` binding, two entities and
two resolvers with different live-fire status. Picking one canonical mechanism per
type makes mechanism ownership declared data — binding `source` kind maps to
resolver `owned_sources`, greppable and gate-auditable — and prevents the
dual-modelling that hid the dormant-relation silent-blank.

## How

- Good: a cross-modelo fold-in (M100 `0604` ← sum of M130 casilla `19`) is
  modelled as a relation feeding the engine's `relation_values` channel via
  `RelationPrefillSourceResolver`, not as a second `previous_filing` binding.
- Good: same-modelo single-filer carry (M130 cumulative,
  `source_period_offset_from_target = -1`) uses a direct `previous_filing` binding
  resolved by `PreviousFilingSourceResolver`; M353←M322 cross-member fan-in stays
  a `per_grupo_member` binding (the relation schema has no grouping axis).
- Bad: declaring the same fold-in as both a relation and a `previous_filing`
  binding — the overlap the ADR closes; two schema entities for one value invite
  drift and a dormant resolver.
- Bad: inventing a new resolver/source kind for a value an existing taxonomy row
  already covers, instead of enrolling under that row or amending the ADR.

---
name: carried-observations-stamp-their-revision
trigger: always_on
---

# Carried observations stamp their revision and re-confirm it on carry

## Rule

Every persisted calculation observation MUST stamp the registry revision its
source filing resolved to (`stamped_revision_id` on the observation envelope,
`src/aeat/application/calculations/_observations_repository.py`), and every
cross-period / cross-year carry read MUST re-confirm that stamp against
`select_revision` for the source context before trusting the value — a divergent
stamp blocks the carry, a missing (legacy) stamp surfaces a non-blocking
advisory, never silence.

## Why

ADR `2026-06-10-period-revision-resolution-adr` (ruling 3 / R2) decided the carry
path is the one place a revision error *compounds across years*: a prior filed
under the wrong revision injects that revision's norms into every later filing
that folds it in. The pre-ADR envelope carried no revision field, so a
stale-revision prior could not even be detected. Stamping the revision at write
time and re-confirming it at read time makes the contradiction loud; the
blocking-vs-advisory split follows `no-silent-under-declaration` — a contradicted
claim blocks, an absent legacy claim warns without bricking stored history.

## How

- Good: a producer stamps `stamped_revision_id` from the snapshot it already
  holds; the carry-read gate computes `(diverges, advisory)` —
  `payload.stamped_revision_id != snapshot.revision.id`
  (`_binding_prefill.py:98`) — and a divergent stamp yields
  `REGISTRY_REVISION_DIVERGENCE`
  (`_cross_period_clean_state.py:106`), blocking the carry.
- Good: a missing stamp on a legacy record returns `(False, True)` — the carry
  proceeds but sets `unstamped_revision_advisory`
  (`_cross_period_clean_state.py:207`, `_binding_prefill.py:88`), surfacing a
  non-blocking advisory.
- Bad: persisting an observation with no `stamped_revision_id` and trusting the
  carried value silently — the prior's revision can no longer be re-confirmed, so
  a stale-revision norm propagates undetected.
- Bad: treating a divergent stamp as a warning instead of a blocker — a prior
  filed under one revision must not silently carry its norms into a period the
  law binds to another.

---
name: casilla-grounding-corrects-actividades-default-by-section
trigger: always_on
---

# Casilla legal_refs: correct the actividades generic-default by section, never by id

## Rule

A casilla whose `legal_refs` carry the actividades-económicas chapter
(`ley-35-2006:art-{27,28,30,31,32}`) as a *generic default* — i.e. the box is NOT
an actividad-económica income/affectation box — MUST be re-grounded to ITS concept's
binding article, keyed by the **renumbering-immune section tag** (the leaf of
`section = [...]`), never by casilla id across filing years. A framework article
that *applies* a regime is a valid foundation home even when the regime is
*established* elsewhere (autonomic deductions → `art-77` cuota líquida autonómica;
régimen de atribución → `art-86`; base reductions/integración → `art-48/49/50`;
individualización → `art-11`; RIC → `ley-19-1994:art-27`). For a casilla that is a
member of a calculation **construct/binding**, sweep the casilla, its construct, AND
its previous_filing/per-source bindings in ONE coherent change — the registry validator
requires a construct's `legal_refs` to cover both its member casillas' and its bindings'
refs. Where the box genuinely IS actividades (estimación directa/objetiva, módulos
agrícolas, "inmueble afecto a actividades económicas"), the actividades chapter is the
CORRECT grounding and MUST be preserved.

## Why

The 2021-2024 Modelo-100 revisions used the actividades chapter as a generic-default
`legal_refs` filler across ~6000 non-actividades casillas (income, cuota, base,
autonomic deductions, ganancias, reductions, inmueble, contribuyente identification) —
documented in the `2026-06-14-legal-grounding-centralization-audit` (V12-V22). Three
hazards made naive correction wrong: (1) casilla ids RENUMBER across years (id `1911`
is a ganancia box in 2024 but a deducción-maternidad box in 2022), so id-keyed maps
inject wrong articles — the section tag is concept-specific and stable; (2) the
"different corpus" assumption for autonomic deductions was false — `art-77` (which
applies them to the cuota) is the correct LIRPF framework home, collapsing a
~2000-casilla "separate campaign" into a section grounding; (3) calculation-chain
casillas are CONSTRUCT- and BINDING-entangled — the validator's three-layer coverage
check (casilla → construct ⊇ casilla refs AND construct ⊇ binding refs) means a casilla
grounded without sweeping its construct+binding breaks registry load. This rule is the
correction-method companion to `registry-calculation-legal-grounding` (which governs the
binding provision a compiled VALUE must cite) and `legal-grounding-verifies-bundled-
authoritative-corpus` (verify the figure against bundled corpus).

## How

- **Good:** ground every `c_valenciana_res`/`canarias_res`/… autonomic-deduction box to
  `art-77` by matching the comunidad name in the section path; pin with a substring gate.
- **Good:** the base-liquidable-negativa carry-forward grounds the 13 casillas + the
  anexo-c construct + the previous_filing binding all to `[art-48, art-50]` in one commit,
  so the validator's binding-coverage check passes.
- **Good:** a heterogeneous section (the `gravamenes_res` cuota computation) is grounded
  PER-BOX by deaccented label (escala→`art-63/74`, cuota líquida→`art-67/77`, each
  deducción→its own article), leaving the RIC/regularización boxes that bind elsewhere.
- **Good:** an actividad-económica box (`actividad_est_directa`, "inmueble afecto a
  actividades económicas") KEEPS the actividades chapter — it is correct there.
- **Bad:** mapping `2024`-id → `2025`-id to copy grounding — the renumbering injects a
  maternidad-deduction article onto a ganancia box.
- **Bad:** grounding a construct-member casilla without also grounding its construct and
  bindings — `construct '…' does not include legal refs […] required by binding '…'`,
  registry fails to load.
- **Bad:** assuming a regime needs a "different corpus" before checking whether a LIRPF
  framework article (cuota líquida autonómica, régimen de atribución, base liquidable)
  already applies it.

## Source

Campaign `legal-grounding-centralization`, audit
`2026-06-14-legal-grounding-centralization-audit` (findings V12 section-tag discriminator,
V19/V20 construct+binding-aware sweep, V21 framework-foundation for autonomic). ~6345
M100 casillas re-grounded across ~40 sections; 14 LIRPF legal entries authored. Promoted
per the `vaultspec-codify` discipline after the method held across the full form.

---
name: cli-notices-are-the-only-diagnostic-channel
trigger: always_on
---

# CLI notices are the only diagnostic channel

## Rule

Operator-facing non-blocking diagnostics — warnings, advisories, and next-step
hints — MUST be emitted through the typed `Notice` channel on the shared CLI
envelope spine (`aeat.core.json_contract.Notice`, surfaced via
`_emit_envelope(..., notices=[...])` / `emit_json_success(..., notices=[...])`).
A command MUST NOT re-introduce a bespoke advisory/`next`/`suggestion` field
inside its `result` payload (an `OutputSchema` subclass). The shared spine
(`schema_version`, `command`, `status`, `notices`) is uniform across the success
envelope and the stderr error document; `status` derives from notice severity
and stays in lock-step with the `ExitCode` table.

## Why

The `cli-envelope-notice-standardisation` campaign (ADR
`2026-06-10-cli-envelope-notice-standardisation-adr`) found the success
`SchemaEnvelope` and the stderr `ErrorEnvelope` were disjoint with no shared
`status`, the success `warnings` channel was structurally dead, and non-blocking
advisories were smuggled as bespoke per-command `result` fields
(`source_advisories`, `authorization_advisory`, config `next`) plus duplicated
text lines. That made the contract un-introspectable: a consumer could not read
one shape to learn the outcome or what to do next. The standardisation collapsed
every diagnostic onto one typed `Notice` channel and a shared spine. A new
bespoke advisory field re-fragments the surface and silently bypasses the
redaction funnel that runs over the envelope. The no-allowlist conformance gate
(`test_json_schema_conformance.py`:
`test_registered_schema_has_no_bespoke_notice_field`) makes the regression a
hard CI failure, so the uniformity cannot rot.

## How

- **Good:** a calculate advisory is projected with `advisory_notice(code,
  message, context={...})` and passed via `_emit_envelope(..., notices=[...])`;
  its text line is rebuilt from the same notice so JSON and text cannot drift.
- **Good:** a post-action next-step hint is an `info`-severity `Notice` whose
  `suggestion` is the follow-on command (e.g. the wizard create/edit next step,
  the overview status next-step guidance), not a `next: str` result field.
- **Good:** structured provenance a former bespoke payload exposed
  (`reason`, `source_kind`, `resolver_id`) rides on `Notice.context`
  (mirroring `ErrorEnvelope.context`), so nothing machine-queryable is lost.
- **Bad:** adding `authorization_advisory: str | None` or `source_advisories:
  tuple[...]` (or any `*_advisory` / bare `next` / `suggestion`) as a top-level
  field on a registered `OutputSchema`. The gate fails until it moves to
  `notices`.
- **Allowed (not a violation):** primary structured result data that a command
  exists to produce — verify `findings`, calendar `warnings`, a `next_due` date,
  a per-finding `next_action`. These are the command's output, not incidental
  diagnostics, and the gate's forbidden set is scoped to bare `next` /
  `suggestion` / `*_advisory` precisely to leave them alone.

## Source

ADR `2026-06-10-cli-envelope-notice-standardisation-adr`; plan
`2026-06-10-cli-envelope-notice-standardisation-plan`; exec
`2026-06-10-cli-envelope-notice-standardisation-exec`. Enforced by
`src/aeat/entrypoints/cli/tests/test_json_schema_conformance.py`
(`test_success_envelope_carries_shared_spine`,
`test_registered_schema_has_no_bespoke_notice_field`,
`test_error_document_shares_the_success_spine`). Companion to
`aeat-calculation-grounding` (provenance through boundaries) and
`no-silent-under-declaration` (an unrouted diagnostic must surface, not vanish).
Promoted per the `vaultspec-codify` discipline once the burndown landed and the
extended conformance gate was green.

---
name: cli-single-subject-id-is-positional
trigger: always_on
---

# CLI single subject id is positional

## Rule

A CLI verb that addresses one ledger transaction must accept the id as a positional `Argument` resolved through the single shared transaction-id resolver, never as a `--id` option and never through a duplicated resolver.

## Why

The `2026-06-10-ledger-interface-contract-adr` recorded that ledger single-subject verbs had mixed `--id` options, positional arguments, optional ids, and duplicated `_resolve_id` helpers. That made documented-command conformance and operator muscle memory diverge. One positional subject id follows the CLI convention that the subject is an argument and flags configure the operation.

## How

- Good: `ledger view <transaction-id>`, `ledger history <transaction-id>`, and `ledger track <transaction-id>` all resolve through the same shared helper over `resolve_transaction_id`.
- Good: optional single-subject verbs still use an optional positional when the command semantics genuinely allow no subject.
- Bad: `ledger view --id tx_123` for a one-subject read or mutation verb.
- Bad: adding a second `_resolve_id` shim in a command module.

---
name: composition-service-no-parallel-write-path
trigger: always_on
---

# Composition service never re-implements an existing write path

## Rule

When a new application-layer service exposes an operator-facing verb that
corresponds to an existing single-writer primitive, the service MUST delegate
the write to the existing primitive (preserving its atomicity and lifecycle-
event emission) and MUST NOT re-implement the write path. The service emits
its own surface-level event in addition to the primitive's lifecycle event;
the two events are intentionally distinct (lifecycle records the data change,
surface records the operator's verb invocation).

## Why

The BucketMaintenanceService design pass on 2026-06-03 found a real
hexagonal-design risk: every method except ``search`` already had a partial
or full authoritative primitive in the application or adapter layer (the
cross-store profile rename in ``ProfileRepository.rename``, the soft/hard
delete split in ``delete_profile_with_lifecycle_span`` +
``remove_profile_bucket_directory``, the bundle assembly in
``serialize_profile_bundle`` / ``deserialize_profile_bundle``). A naive
service that re-implemented any of these would re-introduce the torn-write
risk the single-writer contracts eliminate and create shadow lifecycle-event
emission.

The two-event co-emission pattern (``PROFILE_RENAMED`` plus
``BUCKET_RENAMED`` per rename invocation) is a deliberate audit feature, not
a bug. A future audit query distinguishing "the record was relabelled" from
"the operator invoked the maintenance verb" relies on the two events being
distinct.

## How

- **Good:** ``BucketMaintenanceService.rename`` calls the top-level re-export
  ``rename_profile`` for the cross-store relabel, then appends
  ``BUCKET_RENAMED`` to the bucket-event history. The inner
  ``ProfileRepository.rename`` keeps emitting ``PROFILE_RENAMED``; the two
  events co-emit per operator action.
- **Good:** ``BucketMaintenanceService.delete`` composes
  ``delete_profile_with_lifecycle_span`` (soft tombstone) and
  ``remove_profile_bucket_directory`` (hard erase) in sequence; emits
  ``BUCKET_DELETED`` between them. The destructive-action ``confirmed=True``
  + active-bucket refusals live at the service boundary so a programmatic
  caller observes the same guarantees the CLI ``--yes`` flag passes through.
- **Bad:** a service ``rename`` method that opens its own bucket session,
  decrypts the encrypted profile record, mutates ``display_name``,
  re-encrypts, writes back, then separately rewrites the plaintext manifest
  label. This re-implements the cross-store atomicity that
  ``ProfileRepository.rename`` already holds; a crash between the two writes
  leaves the stores drifted.
- **Bad:** a service ``delete`` that loops directly over the bucket
  directory's secure-object rows to clear them. The soft-tombstone primitive
  exists for a reason; bypassing it loses the ``PROFILE_TOMBSTONED``
  lifecycle event downstream consumers depend on.

## Source

ADR ``2026-06-03-cli-workflow-redesign-adr`` (composition pattern); research
``2026-06-03-cli-workflow-redesign-research``; exec record
``2026-06-03-cli-workflow-redesign-exec``. Codified per the
``vaultspec-codify`` discipline because the constraint binds future agents
across sessions whenever a new composition service is introduced over an
existing single-writer primitive.

---
name: core-struct-docstring-links
trigger: always_on
---

# Core-struct docstring cross-links

A module that imports a canonical core struct MUST cross-link that struct in at
least one docstring (the module docstring or any public symbol's docstring),
using a Sphinx role such as `:class:`ModeloRevision``.

## Why

The API documentation is only navigable if its docstrings form a graph that
steers a reader toward the canonical spine. A module that depends on a core
struct but never names it in a cross-reference is a dead end: a newcomer has no
thread to follow back to the authoritative definition. Cross-reference coverage
started well below half of module docstrings and documented public symbols. The
gate `test_docstring_core_struct_links.py` makes the
contract enforceable: it self-verifies the anchor set, recomputes the violation
worklist from the AST on every run, and fails with a precise
`module -> :class:`Struct`` enumeration. It is hard-cut with no stored baseline,
so coverage can only ratchet up to green; it carries the `docs` marker so it
runs in the documentation CI lane.

## How

- When a module imports a core-struct anchor (the spine is the `CORE_STRUCTS`
  mapping in the gate, the authoritative list; it spans the registry
  authority and snapshots, the JSON contract envelopes, the secure storage
  primitives, the AEAT portal registry, the financial-input aggregates and their
  repositories, and the profile/deadline/filing records),
  add a `:class:` (or `:meth:`/`:obj:`) cross-link in the docstring where the
  struct is genuinely used (a return type, a parameter, the operation performed).
  Write a true sentence describing the real relationship. Do not fabricate.
- Upgrade existing plain-backtick mentions (``ModeloRevision``) to roles
  (`:class:`ModeloRevision``). The anchors are documented public symbols, so a
  bare `:class:`Name`` resolves through the build's missing-reference resolver.
  Do not add a dotted path.
- Extend the `CORE_STRUCTS` mapping in the gate to bring more of the spine under
  enforcement. Each entry is pinned to a single canonical class definition, so
  the set cannot silently rot.
- Choose anchors for navigability value, not raw import in-degree. An anchor is a
  type a newcomer must navigate to in order to work in an area: a central data or
  record aggregate, a domain authority or repository that owns access, or the
  primary closed-value enum that defines a domain. Do NOT anchor ubiquitous
  infrastructure learned once and never re-navigated (a base error such as
  `AeatError`, the `Settings` config aggregate), error subclasses (they are
  handled, not navigated to), secondary sub-dimension enums when the primary one
  is already anchored, or low-reach types only a couple of modules import.
  Linking those everywhere is noise that degrades the graph rather than enriching
  it. The 28-anchor set was curated on this basis from import in-degree plus a
  per-domain discovery pass; the high in-degree tail (errors, config, secondary
  enums) was deliberately excluded.
- Run the gate: `uv run --no-sync pytest -m docs src/aeat/tests/test_docstring_core_struct_links.py`.
  It MUST stay green. Do not satisfy it by sprinkling unrelated roles; the link
  MUST be semantically truthful and the `-n -W` build MUST still resolve it.

---
name: cross-period-suppression-grounded-in-registry-classification
trigger: always_on
---

# Cross-period dependency suppression is grounded in registry classification, never the schedule

## Rule

A cross-period dependency may be scoped out of the clean-state gate (treated as
not-applicable) ONLY on a registry-authoritative signal carried by the dependency's
own `DependencyClassificationDefinition` — `taxpayer_files_source = false` (the
taxpayer never files the source modelo, e.g. suffered retenciones 111/115/123/180/
184/190/193) or `conditional_on_economic_activity = true` combined with an explicit,
fail-closed profile signal (`taxpayer_files_economic_activity is False` for the
pagos-fraccionados 130/131). The suppression set MUST be derived from
`snapshot.revision.dependency_classifications` (the snapshot's own authority), never
from the deadline-engine obligation schedule. A taxpayer who DOES file the source,
and the undeclared case, stay enforced (fail-closed).

## Why

The C3 Modelo-100-reachability defect was first patched (Option 1) by scoping out a
dependency when its source modelo was absent from the deadline-engine obligation
schedule. The full-tree gate proved that wrong: the schedule is an INCOMPLETE
"which modelos does the taxpayer file" signal, so it over-suppressed the
legitimately-enforced cross-period sources of OTHER targets (180/190/193/200/202),
breaking `test_cross_period_clean_state_enforcement`. Option 1 was reverted. The
grounded fix classifies each dependency in the registry (the same authority the
calculation engine consumes) and drives suppression from the snapshot's own
classifications plus a fail-closed profile-activity signal — so suppression is
per-modelo registry data, scoped to exactly the not-filed sources, and the
enforcement contract for filed sources is preserved. Recorded in ADR
`2026-06-19-m100-dependent-modelo-applicability-adr` (Updates 1-3); proven by
`test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced` and
`test_m100_pagos_fraccionados_conditional_on_economic_activity`.

## How

- **Good:** mark a suffered-retencion source `taxpayer_files_source = false`; the gate
  reads `snapshot.revision.dependency_classifications` and scopes it out as a visible
  not-applicable advisory (never silent).
- **Good:** mark a pagos-fraccionados source `conditional_on_economic_activity = true`
  and pass `taxpayer_files_economic_activity` (derived from
  `TaxpayerProfile.irpf_income_categories`, `None` when undeclared) into the gate; it
  scopes out ONLY when the value is explicitly `False`.
- **Bad:** scope a dependency out because its source modelo is missing from the
  deadline-engine obligation schedule — the schedule is incomplete and over-suppresses
  other targets' enforced sources (the reverted Option 1).
- **Bad:** suppress on an undeclared/absent profile signal (fail-open) — a real autónomo
  who has not yet declared income categories would launder past the M130->M100 evidence
  gate.

## Source

ADR `2026-06-19-m100-dependent-modelo-applicability-adr`; research
`2026-06-19-m100-dependent-modelo-applicability-research`. Companion to
`full-tree-gate-must-distinguish-owner` (the gate that caught Option 1),
`no-silent-under-declaration`, and `aeat-registry-authority-flow`.

---
name: firmware-reference-parity.builtin
trigger: always_on
---

# Firmware reference parity: named artifacts must resolve

A worked example of codification applied to an audit finding. Promoted from the firmware
wording review audit following the discipline described in the `vaultspec-codify` rule.

## Rule

Every skill, persona, template, or CLI verb named in firmware prose - the bundled rules,
system fragments, skills, personas, and templates under `src/vaultspec_core/builtins/` -
must resolve to a shipped artifact of exactly that name, and a rename must update every
referencing surface in the same change.

## Why

The firmware is consumed by agents at session load, so a dangling name in an always-on
mandate degrades every downstream session. The
`2026-06-10-firmware-wording-review-audit` documented two such breakages: a phantom
`vaultspec-write-plan` skill name routing the Plan phase across the pipeline table,
intent table, and catalog (the shipped directory is `vaultspec-write`), and an orphaned
`ref-audit.md` template left behind by a rename. Both were renames that updated one
surface and left the old name standing in the others, contradicting the firmware's own
consistency mandate.

## How

- Before naming a skill, persona, template, or verb in firmware prose, confirm it ships:
  `vaultspec-core spec <resource> list` (one of `rules`, `skills`, `agents`) enumerates
  the shipped artifacts to check names against, and the template files live under
  `src/vaultspec_core/builtins/templates/`.

- **Good:** renaming a skill updates the pipeline table, the intent table, the catalog,
  and every cross-reference atomically in one change, so no surface names the old slug.

- **Bad:** renaming the skill directory (or template file) and leaving the old name in
  the system prompt, a discipline rule, or another skill's prose; the next agent loads a
  reference to an artifact that no longer exists.

## Status

Active. Until a structured firmware-name linter lands, the cross-surface sweep is the
author's discipline; `vaultspec-core spec <resource> list` is the check.

## Source

Audit `2026-06-10-firmware-wording-review-audit`, findings REVIEW-001 and REVIEW-002 and
the campaign's renamed-artifact root cause. Sibling decision ADR
`2026-06-09-firmware-wording-review-adr` (decisions D1 and D7).

---
name: fixture-provenance-declared-in-sidecar
trigger: always_on
---

# Fixture provenance is declared in the sidecar, never allowlisted

## Rule

Every test-fixture PDF under a modelo subdirectory MUST declare its provenance
(`real_corpus` | `synthetic_generated`) in its `.json` sidecar. Provenance gates
MUST read that declaration and cross-check it against physical evidence (the PDF
`/Producer` DocInfo), and MUST NOT hardcode per-fixture exception allowlists in
test source.

## Why

The verification-source honesty gate inferred fixture provenance from a single
proxy (`/Producer`) and assumed every fixture in a modelo directory shared one
provenance. Modelo 390 broke that: a real sanitised AEAT parser-fidelity anchor
(`2021-0A`) lives alongside synthetic formula-verification specimens
(`2022-0A`, `2023-0A`). Campaign step `W06.P16.S37` patched the red gate with a
hardcoded allowlist (`_REAL_CORPUS_ANCHORS_IN_SYNTHETIC_POOLS`) — re-introducing
the honor-system per-fixture list the gate exists to remove. The
`2026-06-01-verification-fixture-roles-adr` decided the durable fix: provenance
is data the sidecar already half-encoded (real specimens carry redaction
metadata, synthetic carry formula ground truth), so the fixture declares it
explicitly and the gate validates the declaration against `/Producer`. A
mis-stamped sidecar still reds the gate via the cross-check, so honesty is
preserved without an allowlist.

## How

- **Good:** a real parser-corpus anchor added to an otherwise-synthetic pool
  stamps `provenance = real_corpus` in its sidecar. The gate reads it and
  confirms the PDF carries no `aeat-test-fixture-generator` signature. No test
  source changes.
- **Good:** the synthetic fixture generator stamps
  `provenance = synthetic_generated`; the gate confirms the generator signature
  is present.
- **Good:** a mis-stamp (claiming `synthetic_generated` on a real PDF) reds the
  gate via the `/Producer` cross-check — the sidecar is trusted but verified.
- **Bad:** a fixture whose provenance differs from its pool's per-modelo tag is
  exempted by adding `(modelo_id, filename)` to an allowlist constant in the
  test module. This is the smell this rule forbids; declare provenance in the
  sidecar instead.
- **Bad:** a gated fixture ships without a `provenance` field in its sidecar.
  The gate fails it: every gated fixture must self-declare.

## Source

ADR `2026-06-01-verification-fixture-roles-adr` (accepted); research
`2026-06-01-verification-fixture-roles-research`; origin campaign step
`W06.P16.S37` of `2026-06-01-semantic-cluster-hardening-plan`.

---
name: full-tree-gate-must-distinguish-owner
trigger: always_on
---

# Full tree gates must distinguish owner

## Rule

When a required full-tree gate is red in the shared factory worktree, always record the exact current failure signatures and distinguish owner-surface failures from unrelated peer churn before marking a feature step complete.

## Why

The `2026-06-11-ledger-hardening-close-audit-pass-2` found the C4 alias-retirement implementation green on focused lint, registry/operator tests, API-stub conformance, and CLI conformance while the mandated full `src/aeat` collect-only gate stayed red from support-module export splits owned by other campaigns. Without owner triage, a closeout pass either falsely claims green or opportunistically edits unrelated peer work. The rule preserves honesty without broadening the feature's ownership boundary.

## How

- Good: capture the full-tree gate output to a log, extract the import/error summaries, name the affected modules, and keep the plan step open when failures are outside the feature surface.
- Good: if the failing signatures are in the feature's touched files or contracts, fix them before closing the step and rerun the full-tree gate.
- Bad: marking a full-tree verification step complete because focused feature tests passed while the repository-wide gate still has untriaged collection errors.
- Bad: patching unrelated support modules just to make a closeout gate pass when those files belong to active peer campaigns.

---
name: generated-reference-is-cli-owned.builtin
trigger: always_on
---

# Generated reference is CLI-owned: regenerate, never hand-edit the managed zones

A worked example of codification applied to an audit finding. Promoted from the CLI
reference automation audit following the discipline described in the `vaultspec-codify`
rule.

## Rule

The bundled CLI references' generator-managed regions - delimited by the
`vaultspec:generated:begin` and `vaultspec:generated:end` markers in
`src/vaultspec_core/builtins/reference/cli.md` and `docs/CLI.md` - are updated only by
running `vaultspec-core spec reference generate`, never by hand-editing inside the
markers; the `--check` mode gates pre-commit and CI and fails until both references
match fresh output.

## Why

The bundled reference is hand-authored prose wrapped around generator-owned zones, and
the hand-authored content drifted from the live Typer surface every time a flag or
enumeration changed. The `2026-06-10-cli-reference-automation-audit` documented that
drift (the prior reference omitted live signatures, D6) and that the two surfaces
drifted in ordering against each other (`GENREVIEW-003`, first divergence at index 7).
The generator plus `--check` is the durable guarantee: drift is mechanically corrected
and CI fails deterministically until the managed regions equal fresh output.

## How

- **Good:** a new flag lands on a verb; run `vaultspec-core spec reference generate`,
  review the regenerated managed region, and commit it. Both `cli.md` and `docs/CLI.md`
  inventories regenerate from one Typer walk and cannot diverge.

- **Bad:** hand-edit a signature or option table inside the
  `vaultspec:generated:begin/end` markers; the edit is overwritten on the next generate
  and `--check` fails CI in the meantime.

- Hand-written prose **outside** the markers (the entry-point table, global-options
  narrative, sync-vocabulary section, environment-variable table) is still
  hand-maintained normally; the generator reads but never rewrites those zones.

## Status

Active. The generator and its `--check` gate have shipped across both managed files. The
rule's intent (the managed zones are CLI-owned) is now structurally enforced; the
author's remaining duty is to regenerate rather than hand-edit inside the markers.

## Source

Audit `2026-06-10-cli-reference-automation-audit`, the generator design plus findings
`GENREVIEW-002` and `GENREVIEW-003`. Sibling decision ADR
`2026-06-10-cli-reference-automation-adr`.

---
name: glossary-concepts-are-taxpayer-facing
trigger: always_on
---

# Terminology Handbook glossary concepts are taxpayer-facing only

## Rule

Only a taxpayer- or operator-facing AEAT concept may be an `approved`
Terminology Handbook concept (and therefore render in the generated glossary and
the shipped Pagefind search injection): a tax, modelo, casilla, régimen, period,
legal concept, or an operator workflow noun (`ledger`, `borrador`,
`justificante`, `fichero-boe`). A concept that names the search / calculation /
registry MACHINERY (RAG sweep, relevance map, search projection, preprocessing
hook, search record kinds, licence laundering, preflight, registry binding, work
unit, verification-state internals, the Handbook itself) MUST NOT be `approved`;
it is `deprecated` (resolvable for the dev/agent RAG, excluded from the glossary
and shipped search) with a `scope_note` marking it internal, never deleted.

## Why

The corpus-quality drive (`2026-06-15-docs-terminology-search-audit`) found ~14
`approved` concepts documenting the search/calculation machinery itself, so the
glossary a taxpayer reads carried first-class entries for `barrido-rag`,
`proyeccion-busqueda`, `mapa-relevancia`, `work-unit`, and the like — none of
which a taxpayer would ever look up, none of which can carry a legal basis. The
decision is recorded in `2026-06-15-docs-terminology-search-adr` (D1/D2): the
Handbook's `approved` tier is the taxpayer/operator vocabulary; internal
concepts are demoted to `deprecated` (not `retired`, which asserts a successor
that a mis-enrolment lacks; not deleted, per the scaffold-preserve contract).
The glossary generator and the Pagefind injector both gate on `approved`, so the
lifecycle is the enforcement surface. The scaffold walks live enrolment sources,
so a future scaffold can re-surface an internal concept as a `draft` (harmless —
drafts are excluded); promoting one to `approved` is the regression this rule and
the curation audit guard against.

## How

- **Good:** `prorrata`, `modelo-303`, `recargo-equivalencia`, `casilla`,
  `borrador`, `ledger` are `approved` — taxpayer/operator terms — and render in
  the glossary.
- **Good:** `barrido-rag` (RAG sweep), `proyeccion-busqueda` (search
  projection), `binding` (registry binding), `work-unit` are `deprecated` with a
  `scope_note` recording they are internal machinery; the dev RAG still resolves
  them, the taxpayer glossary does not.
- **Bad:** promoting an internal/tooling concept to `lifecycle = "approved"`, so
  it renders as a first-class taxpayer glossary entry.
- **Bad:** deleting an internal concept fragment instead of deprecating it (the
  scaffold-preserve contract never deletes; deprecation keeps it resolvable for
  developers).

## Source

ADR `2026-06-15-docs-terminology-search-adr` (D1/D2); audit
`2026-06-15-docs-terminology-search-audit` (PERF-001 follow-up). Enforced by the
`approved`-only gate in the glossary generator (`dev/docs/glossary_reference.py`)
and the Pagefind injector (`dev/docs/pagefind_inject.py`). Companion rules:
`terminology-single-declaration`, `terminology-scaffold-preserve-contract`.

---
name: ledger-amount-is-absolute-direction-is-authority
trigger: always_on
---

# Ledger amount is an absolute magnitude; direction is the sole flow authority

## Rule

A ledger transaction stores a **non-negative** `amount` magnitude; flow
direction is carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row, or CLI surface may encode
flow in the sign of an amount. The non-negative constraint is enforced at the
`RawTransaction` boundary so the import and manual paths are both gated, and the
evidence-row `amount` / `value_in_eur` mirror that absolute convention. There is
no signed-amount shape to read, migrate, or bridge — old is deleted, not
tolerated (`no-legacy-compatibility`).

## Why

Flow was encoded twice — as the sign of a `Decimal` amount and, redundantly, as
a parallel `direction` enum — and the two could disagree. Consistency was
enforced only on the manual command; the import path derived direction from the
sign and skipped the gate, so a zero-amount import silently classified as
INCOMING. Every aggregation engine already routes on `direction` and takes
`abs()` of the amount (the sign carried no arithmetic signal), and `value_in_eur`
was already stored non-negative. The `2026-06-10-ledger-amount-direction-adr`
collapsed flow onto the single authoritative `direction`, removed the sign from
storage, and closed the enforcement gap with one model-level gate. This is the
ledger-encoding counterpart of `aeat-calculation-grounding` (provenance —
including `direction` — survives every boundary) and `no-silent-under-declaration`
(the zero-amount misclassification was a silent error a shared gate now refuses).

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator that raises
  `TransactionValidationError` on a negative value; it fires whether the row is
  built by an import adapter or by `ManualLedgerTransactionCommand`. A
  save→load→equality roundtrip plus an anti-tautology proof (corrupt the on-disk
  amount to a negative, assert refusal at load) lock the boundary.
- **Good:** an import adapter maps the bank export's sign (or native debit/credit
  signal) to a `TransactionDirection` **at the parse boundary** and stores
  `abs(amount)`, yielding a typed `ParsedLedgerRow(raw, direction)`; the import
  action carries that explicit `direction` onto the `Transaction` and never
  re-derives flow from a sign. A zero-amount source row is refused at the parse
  boundary, consistent with the manual path.
- **Good:** `INTERNAL_TRANSFER` is stored as a magnitude paired with
  `direction = INTERNAL_TRANSFER`; split children store magnitudes and inherit
  the parent's `direction`; the reconciliation matcher routes by direction
  (RECEIVED↔OUTGOING, ISSUED↔INCOMING) and matches on the magnitude.
- **Good:** the CLI `--amount` refuses a negative magnitude with an instructive,
  localised error that names the accepted form (a non-negative amount plus
  `--direction`), never a bare "value invalid".
- **Bad:** writing a negative amount to encode an expense, or a
  `direction_from_amount` helper that reads `raw.amount < 0` downstream of the
  parse boundary — flow lives in `direction`, and there is no sign to read.
- **Bad:** a read-tolerance branch that coerces a legacy signed-amount record on
  load, or a migration that flips old fingerprints — there is no released data;
  old shapes are absent, refused, never bridged.

## Source

ADR `2026-06-10-ledger-amount-direction-adr` (accepted); research
`2026-06-10-ledger-amount-direction-research`; plan
`2026-06-10-ledger-amount-direction-plan` (cluster C1). Companion rules:
`aeat-calculation-grounding`, `no-silent-under-declaration`,
`no-legacy-compatibility`, `ledger-derived-revisions-bundle-evidence`.

---
name: ledger-derived-revisions-bundle-evidence
trigger: always_on
---

# Ledger-derived revisions bundle their evidence

## Rule

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — the contributing-transaction projections plus
the manual fact-basis entries — pegged to the revision's snapshot fingerprint,
and every export of such a revision MUST carry that evidence (or a resolvable
in-system reference to it). An export of a ledger-derived revision that carries
neither is refused.

## Why

The `modelo-export-evidence-parity` research (finding B) found that revision
state stored only fingerprints (`LedgerFilingSnapshot`) — the fact basis that
explains *why a casilla holds its value* was absent from both the persisted
`CalculationRevision` and every export, so "why is casilla X this value" was
unanswerable from a filing artefact alone. A human files outside the
application; an artefact whose numbers cannot be re-derived from bundled
evidence is legally frail. The `2026-06-03-modelo-export-evidence-parity-adr`
decided that the typed evidence (signed amount, currency, direction,
base/IVA/rate/category, irpf category, EU member state, FX, lifecycle, business
proportion, legal_refs/source_refs, attachment/document-link ids per
contributor, plus operator manual entries) rides inside the encrypted revision
envelope bound by the same `snapshot_fingerprint`, so evidence and staleness
share one content address. This is the data-carrying companion to
[[aeat-calculation-grounding]] (provenance through boundaries) and
[[no-silent-under-declaration]] (a casilla without an explainable basis must not
file silently).

## How

- **Good:** `compute_ledger_filing_evidence` projects the resolved
  `source_transaction_ids` into typed `LedgerEvidenceRow`s plus
  `ManualFactBasisEntry`s, binds them to the snapshot fingerprint, and the
  `verify_modelo_revision` action captures it alongside the fingerprint snapshot
  in one catalogue load; the evidence persists inside the encrypted
  `CalculationRevision` and survives a strict save→load→equality roundtrip with
  every defaultable field populated non-default.
- **Good:** the capture asserts the evidence set covers the fingerprint set
  (`_assert_evidence_covers_snapshot`); a bundle that drops a contributor present
  in `source_transaction_ids` raises rather than silently omitting it.
- **Good:** offline xls and online Sheets exports both read the same bundled
  evidence and render an identical `Evidencia` surface, so the two transports are
  evidence-identical.
- **Bad:** persisting a ledger-derived revision with only the fingerprint
  snapshot and no typed evidence — the casilla becomes unexplainable and the
  export is not a self-contained filing artefact.
- **Bad:** letting an export of a ledger-derived revision proceed when neither
  the bundled evidence nor a resolvable reference is present.
- **Bad:** asserting the evidence roundtrip against numbers hand-computed from
  the same formula; the roundtrip must assert real reconstitution of the bundled
  rows.

## Source

ADR `2026-06-03-modelo-export-evidence-parity-adr` (accepted); research
`2026-06-03-modelo-export-evidence-parity-research`; plan
`2026-06-03-modelo-export-evidence-parity-plan` (W01). Promoted per the
[[vaultspec-codify]] discipline.

---
name: ledger-evidence-bytes-not-links
trigger: always_on
---

# Ledger evidence bytes, not links

## Rule

Every ledger evidence record must carry the document's encrypted bytes in a bucket-scoped secure-object namespace; a Gmail, Drive, or URL reference must be fetched and encrypted or the attachment must be refused, never stored as a link-only manifest.

## Why

The `2026-06-10-ledger-evidence-enforcement-adr` made encrypted evidence bytes the C2 ledger evidence invariant. A stored pointer is not evidence: links rot, permissions change, and a later modelo audit cannot answer why a casilla had a value from a dead `text/uri-list` manifest. This rule is the evidence-specific companion to `sensitive-financial-data-secure-storage-only`.

## How

- Good: `doclink` resolves a permitted Drive file to bytes, stores the bytes through the attachment secure-object namespaces, and records source metadata in the manifest.
- Good: Gmail links, arbitrary URLs, and out-of-scope Drive files fail with an actionable refusal that names the scope-upgrade or manual-download path.
- Bad: persisting only `https://...`, a Gmail message URL, or a Drive URL as `text/uri-list` and treating it as evidence.
- Bad: falling back to link storage after a fetch permission error.

---
name: ledger-iva-advisory-only-on-cuota-bearing-categories
trigger: always_on
---

# Ledger IVA advisory fires only on cuota-bearing categories

## Rule

The unconsumed-declarable-IVA advisory — the non-blocking `CalculationSourceDiagnostic`
raised by `unsupported_ledger_iva_observations` on the calculate path and surfaced to the
operator as the `source_advisories` / `ADVISORY:` line — MUST fire only on `IvaCategory`
values that are legally expected to produce a cuota a binding should route. Categories that
are cuota-less by law (exempt, zero-rated, not-subject, exempt intra-community supply,
intra-community triangulation, other-regime) MUST be excluded from the advisory's flagged
set via the named `CUOTA_LESS_M303_IVA_CATEGORIES` frozenset — never by an inline literal.

## Why

Finding #64 wired the advisory to surface declarable IVA that no binding consumes
(`no-silent-under-declaration`). A Modelo 303 grounding pass found it false-fired on
categories that bear no cuota by law (`DOMESTIC_EXEMPT` LIVA art. 20, `INTRA_COMMUNITY_SUPPLY`
art. 25, `OPERACION_NO_SUJETA` art. 7, exports, triangulation, simplificado): they
legitimately match no cuota binding, so flagging them is noise that trains operators to
ignore the alert. The advisory only earns trust if every fire is a genuine unrouted cuota.
After the M303 reverse-charge and import routing landed, the residual flagged set is empty
for every declarable category — the correct invariant: a fire means a real unrouted cuota.

## How

- **Good:** a declarable category that should route a cuota but has no binding yet
  (`DOMESTIC_REVERSE_CHARGE` before its binding; `IMPORT_THIRD_COUNTRY` before its deducible
  binding) fires the advisory until its binding lands.
- **Good:** an exempt/zero/not-subject/exempt-supply/triangulation/simplificado observation
  is a member of `CUOTA_LESS_M303_IVA_CATEGORIES` and never fires the advisory.
- **Bad:** flagging an exempt entrega intracomunitaria or an export as "unrouted declarable
  IVA" — it is base-only/informativa with no cuota, so the fire is a false positive.
- **Bad:** silencing a genuine unrouted reverse-charge or import cuota by adding it to the
  cuota-less set — it bears a real cuota; route it (add the binding) instead.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (accepted) codification candidate; grounding
research `2026-06-09-modelo-iva-routing-carry-research`; commits `068045d2b` (advisory
refinement + the named frozenset), `a9aca68fc` / `f3b0cc777` (routing that empties the
residual set). Companion to `no-silent-under-declaration` and `aeat-calculation-grounding`.

---
name: ledger-mutation-returns-uniform-quintet
trigger: always_on
---

# Ledger mutation returns uniform quintet

## Rule

Every CLI verb that mutates exactly one ledger transaction must return `{bucket_id, transaction_id, bucket_event_ids, review_status, transaction}` through the shared ledger mutation result shape.

## Why

The `2026-06-10-ledger-interface-contract-adr` standardised mutation output because ledger mutation verbs had drifted across add, update, classify, review, and related paths. Operators and downstream automation need one envelope shape to read the changed subject, its review state, and its emitted bucket events. Structural verbs that act on a set or destroy the subject are different operations and must declare their typed exception explicitly.

## How

- Good: `add`, `update`, `classify`, and `review` emit the shared mutation result with bucket id, transaction id, bucket event ids, review status, and a `TransactionPayload`.
- Good: `split`, `merge`, `remove`, and `reset` use their own typed schemas because they operate on multiple rows or destroy the subject.
- Bad: adding a single-transaction mutation verb that returns only `transaction_id` or only the updated transaction.
- Bad: duplicating the quintet fields in a new ad hoc payload instead of using the shared shape.

---
name: ledger-participation-index-is-derived-rebuildable
trigger: always_on
---

# Ledger participation index is derived and rebuildable

## Rule

The transaction-to-revision participation index is a derived encrypted cache co-written atomically with revision persistence and must be rebuildable from the revision catalogue; lifecycle correctness must rely on the live catalogue scan, never on index freshness.

## Why

The `2026-06-10-ledger-modelo-crossref-adr` introduced the participation index for operator cross-reference and audit navigation, not as a new source of truth. If deletion guards or filing correctness depended on the cache, a stale or missed index write could silently permit destructive ledger changes. Rebuildability keeps the index useful without making correctness depend on denormalised state.

## How

- Good: verification or filing persistence co-emits participation entries in the same secure-object write batch as the revision state change.
- Good: a rebuild action scans finalized revision catalogues and regenerates every per-transaction participation entry.
- Good: ledger removal blockers continue scanning the live revision catalogue.
- Bad: allowing a ledger transaction delete because the participation index has no entry for it.
- Bad: writing a plaintext participation index outside the active profile's encrypted secure-object repository.

---
name: legal-grounding-verifies-bundled-authoritative-corpus
trigger: always_on
---

# Rule

When authoring or grounding any regulatory value (a registry `legal_refs`→`corpus_ref`
entry, a `corpus/normatives/html/*.html` excerpt, an `external_constants` figure), verify
the legal text against the BUNDLED authoritative consolidated corpus already shipped under
`src/aeat/_data/corpus/normatives/html/` FIRST — never author a new corpus excerpt from a
secondary source (a gestoría blog, a summary site, a paraphrase) without that
cross-check, and prefer pointing `corpus_ref` at the bundled authoritative file over
hand-authoring a duplicate excerpt.

## Why

The honesty review of the grounding-completion campaign found a CRITICAL defect (finding
C1): a módulos DT 32ª corpus excerpt was authored from a secondary source ("supercontable")
with a fabricated year-list ("…2025 y 2026"), while the repository ALREADY bundled the
authoritative consolidated LIRPF (`ley-35-2006.html#dttrigesimasegunda`) whose real text
reads "en los ejercicios 2016 a 2024" and records the 2025/2026 extensions were DEROGADAS
(BOE-A-2026-4667). The `required_text` corpus cross-check was tautological — the same author
wrote both the excerpt and the `required_text`, so the gate validated internal consistency,
not BOE faithfulness. The same root cause recurred as the M210 IRNR interest defect (a
stale bundled corpus snippet phrased art. 25.1.f as EU/EEE-conditional, contributing to a
wrong 24% rate where the law is 19%). And it recurred a third time as the IRPF menor-tres
mínimo defect — the bundled `ley-35-2006-art-58.html` itself carried "3.000 euros" (despite
a header asserting it was the official unchanged BOE text) where the AEAT manual and BOE
state 2.800, grounding a wrong registry parameter and two tautological tests. Grounding a
regulated calc value against a secondary-source or self-authored excerpt is how a wrong
figure ships looking grounded; the bundled consolidated corpus is the faithful source the
project already trusts and is the companion check to `registry-calculation-legal-grounding`
(cite the binding provision) and `aeat-safety-legal-gates` (ground in BOE/AEAT, never
invent). CRITICAL REFINEMENT (from the menor-tres + M210 cases): the bundled corpus is
*preferred* over secondary sources but is NOT infallible — it can carry authored figure
errors. For any numeric AMOUNT or RATE, cross-check the figure against the live BOE/AEAT
consolidated text even when the bundled corpus already states it; a bundled-corpus figure
is a strong default, not a substitute for confirming the number itself.

## How

- **Good:** before authoring a new legal entry, `rg` the bundled `ley-NNNN-AAAA.html`
  consolidated file for the provision's anchor (e.g. `#dttrigesimasegunda`, `#a25`), read
  the verbatim text, and point `corpus_ref` at that bundled file with a `required_text`
  phrase distinctive enough to match only the target provision — so the cross-check
  validates against authoritative text, not a self-written duplicate.
- **Good:** when the bundled corpus is a deliberately non-authoritative anchor snippet
  (its `required_text` is empty / it carries a "Nota de catálogo" disclaimer), treat the
  registry parameter as the calc authority, verify the value against the live BOE/AEAT
  consolidation, and flag the snippet for an operator corpus refresh — do not trust the
  snippet's prose as the rate authority.
- **Good:** when a verification pass touches a numeric amount or rate, cross-check the
  figure against the live BOE/AEAT consolidated text even if the bundled corpus already
  states it — and if the bundled corpus is wrong, correct the corpus, the grounded
  parameter, the legal-entry notes, and any tautological test that baked the wrong value, in
  one atomic commit (the menor-tres 3.000→2.800 fix touched all four).
- **Bad:** trusting a bundled-corpus AMOUNT/RATE without confirming the number itself against
  live BOE/AEAT — the corpus can carry an authored figure error (3.000 vs 2.800) behind a
  header that claims it is the official unchanged text, and the self-referential
  `required_text` gate passes anyway.
- **Bad:** authoring a new `corpus/normatives/html/<provision>.html` excerpt by copying a
  gestoría blog or summary site, then citing it from a registry legal entry — the year-list
  / scope / figures may be stale or wrong, and the self-referential `required_text` gate
  passes anyway (the C1 fabrication pattern).
- **Bad:** stamping such an agent-authored legal-authority entry `review_status = "reviewed"`
  under the operator's name without the bundled-corpus cross-check — the legal catalogue is
  a human-reviewed, filing-grade surface; agent-prepared entries must record honest
  `reviewed_by` provenance and be grounded in the bundled authoritative text pending operator
  re-stamp.

## Source

Audit `2026-06-14-aeat-grounding-completion-audit` (finding C1, reinforced by the M210
art. 25.1.f corpus-staleness finding). Companion rules: `registry-calculation-legal-grounding`
(cite the binding provision), `aeat-safety-legal-gates` (ground in BOE/AEAT, never invent),
`aeat-calculation-grounding` (provenance through boundaries). Promoted per the
`vaultspec-codify` discipline after the lesson held across multiple findings in one campaign.

---
name: local-filed-observations-are-non-official-evidence
trigger: always_on
---

# Local-filed observations are non-official evidence

## Rule

Observations persisted by the local `file` flow (`persist_filed_revision_observation`) MUST
carry a non-official `source_kind` (`app_filing`) and MUST NEVER be added to
`_OFFICIAL_SOURCE_KINDS` — the set that satisfies the cross-period clean-state gate
(`aeat_sede_justificante`, `aeat_sede_live_capture`, `aeat_csv_register`). Automatic
cross-period `previous_filing` carry may feed calculate/draft from these observations, but
they must never substitute for external AEAT filing evidence. A same-filing-year local chain
may reach local verify/export only when the chain is present, value-consistent,
revision-confirmed, and its only blockers are the official-evidence delta; that path MUST
surface a non-blocking non-official-local-chain advisory and MUST NOT assert AEAT acceptance.
Cross-year priors, operator-manual sources, missing filing/observation data, and value or
revision divergence remain blocking.

## Why

Wave C wired automatic local cross-period carry: local `file` now persists the filed
revision's observations so a later period's calculate can auto-carry the prior value. The
load-bearing safety decision is the `source_kind`. The cross-period clean-state guard blocks
unsafe dependent filings whose upstream evidence is non-official
(`LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`). Decision B later narrowed one reachability gap:
same-filing-year local reconstruction may proceed to local export with a warning when every
upstream dependency is otherwise clean and only the official-evidence delta is missing. If
`app_filing` were treated as official, an unevidenced local-only chain could silently claim
AEAT-evidenced acceptance, violating `aeat-safety-legal-gates` and
`no-silent-under-declaration`. Stamping the carry observation non-official keeps the prior
value available for calculation while still disclosing the local-only basis and still demanding
a real justificante / CSV register / live capture before any official-evidence assertion.

## How

- **Good:** `persist_filed_revision_observation` stamps `source_kind="app_filing"`; the carry
  resolver reads it to populate a calculate binding; a same-filing-year, value-consistent,
  revision-confirmed local chain whose only blockers are the official-evidence delta reaches
  local verify/export with a non-blocking non-official-local-chain advisory.
- **Good:** cross-year local chains, operator-manual sources, missing filing/observation data,
  and value or revision divergence remain blocking; the official-evidence delta still raises
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` outside the narrow same-year advisory scope.
- **Good:** a regression test asserts `app_filing not in _OFFICIAL_SOURCE_KINDS` and fails the
  moment it is added.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS` to make cross-period filing "just
  work" — it launders an unevidenced local chain past the evidence gate.
- **Bad:** persisting the local-filed observation under an official `source_kind` to reuse the
  live-capture path verbatim — the non-official kind is the deliberate delta from that template.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (accepted) codification candidate, ruling D1;
research `2026-06-09-modelo-iva-routing-carry-research`; commit `10167440f` (Wave C carry).
Refined same-year Decision B scope: ADR `2026-06-19-crossperiod-filing-deadlock-adr`,
commit `84add274d`.
Companion to `aeat-safety-legal-gates`, `no-silent-under-declaration`, and
`ledger-derived-revisions-bundle-evidence`.

---
name: modelo-export-mirrors-official-structure
trigger: always_on
---

# Modelo exports mirror the official structure

## Rule

Every modelo workbook export — offline xls and online Google Sheets alike — MUST
be generated from the single shared plan builder, render live spreadsheet
formulas with an explicit labelled start (input) and final (resultado) anchor,
and pass the registry-grounded parity gate (casilla set, numbering, section
order). A structural divergence from the official AEAT modelo layout is a hard
failure, never a warning.

## Why

The `modelo-export-workbook-parity` research (finding A) found the calc-sheets
plan already mirrored registry structure and emitted live formulas but wrote no
formatting, marked no explicit start/final, and had no parity gate — so an
operator reviewing a filing artefact before submitting it outside the
application could not see input→result flow and nothing caught structural drift
from the official layout. The `2026-06-03-modelo-export-workbook-parity-adr`
decided presentation is typed plan facets (number formats, section headers,
start/final anchors, the `Evidencia` surface) defined once in the builder and
materialised identically by both transports, and that "official parity" is
checked against the same registry authority the calculation engine uses
(`CasillaDefinition.number`/`segmento`/`section`, the
`CalculationCompletenessManifest` projected from the AEAT Diseño de Registros) —
not a separate hand-maintained spec. This is the export-surface companion to
[[aeat-registry-authority-flow]] (the registry is the authority) and
[[ledger-derived-revisions-bundle-evidence]] (the evidence the workbook renders).

## How

- **Good:** `build_export_plan(snapshot)` emits one `SheetExportPlan` carrying
  value/formula cells, number formats, section headers, start/final anchors,
  protected ranges, and evidence; `build_offline_workbook` (openpyxl) and
  `apply_export_plan` (Sheets API) are two transports of that one plan, and a
  conformance test asserts they render the same content.
- **Good:** the parity gate asserts the exported casilla set equals the
  completeness-manifest required set (numbering + segmento), section ordering
  follows the registry declaration order, every computed casilla carries a live
  formula, and the start/final anchors are present and correctly placed; a
  divergence is a hard CI failure.
- **Good:** the gate reports coverage honestly — a modelo whose completeness
  manifest is incomplete yields a weaker gate that says so, rather than implying
  full parity.
- **Bad:** writing formatting, start/final, or evidence in one transport but not
  the other, or computing them at apply time instead of in the plan — offline
  and online then drift.
- **Bad:** asserting official parity against a separate hand-maintained layout
  spec instead of the registry completeness manifest, introducing a second drift
  surface.
- **Bad:** downgrading a structural divergence to a warning; the official
  casilla set, numbering, and section order are a gate, not a hint.

## Source

ADR `2026-06-03-modelo-export-workbook-parity-adr` (accepted); research
`2026-06-03-modelo-export-workbook-parity-research`; plan
`2026-06-03-modelo-export-evidence-parity-plan` (W03/W04/W05). Promoted per the
[[vaultspec-codify]] discipline.

---
name: modelo-identifiers-use-core-enum
trigger: always_on
---

# Modelo identifiers use the core Modelo enum

## Rule

Production code MUST reference AEAT modelo identifiers through the
`aeat.core.Modelo` StrEnum, never as bare three-digit string literals. The
`src/aeat/core/tests/test_modelo_string_usage.py` AST gate enforces this; a
genuine non-identifier occurrence (a regulatory article number, a digit-set
membership test, a CLI command-name token) is recorded in that gate's allowlist
with a stated reason. Use the bare member (`Modelo.M303`) in comparison,
membership, and dict-key positions; reserve `.value` (`Modelo.M303.value`) for
plain-`str` contracts (pydantic field values, call arguments, parameter /
CLI-option defaults, returns). A modelo that exists as a code-referenced
identifier but has no registry definition (a retired form) is added to the enum
and listed in `aeat.core.NON_REGISTRY_MODELOS`, which the registry-parity gate
excludes.

## Why

The `2026-06-10-modelo-enum-hardening-adr` decision and its research found
roughly 250 sites referencing modelo ids as bare three-digit string literals,
so a typo or a retired code could not be caught at a type boundary and the
closed set was scattered. Naming them through one core `StrEnum` gives the
identifiers a single typed home, makes the retired-versus-active distinction
explicit (the suppressed M037 censo simplificada is a code-referenced identifier
with no registry TOML), and lets the AST gate keep the convention from rotting.
Because a `StrEnum` member compares, hashes, `str()`-formats, and JSON-serialises
identically to its value, the substitution is behaviour-preserving; the
member-versus-`.value` split keeps stored and passed types clean across pydantic
round-trips. The enum's registry-backed members are bound to
`registry_modelo_codes()` by a parity gate, so a new registry modelo without a
matching enum member fails loudly.

## How

- **Good:** `if work_unit.modelo != Modelo.M303: ...` — comparison uses the bare
  member.
- **Good:** `_MODELO_APPLICABILITY_RULES = {Modelo.M100: ..., Modelo.M130: ...}`
  — dict keys are members (they hash as their string value).
- **Good:** `modelo=Modelo.M720.value` for a `str`-typed field value, and
  `modelo: Literal[Modelo.M100] = Modelo.M100` for a pinned field — `.value` for
  the plain-`str` contract, the member inside `Literal[...]`.
- **Good:** a retired identifier (`M037`) is an enum member listed in
  `NON_REGISTRY_MODELOS` and pinned by a test to raise from `validate_modelo`.
- **Bad:** `if work_unit.modelo != "303":` or `{"347": ..., "349": ...}` — bare
  string literals; the AST gate fails until they reference `Modelo`.
- **Bad:** inventing a `Modelo.M<code>` member for a code that is neither in the
  registry-bound set nor declared in `NON_REGISTRY_MODELOS` (e.g. a `Modelo.M037`
  reference before the carve-out existed) — it raises `AttributeError`.
- **Bad:** silencing the gate by adding an allowlist entry for a real identifier
  occurrence instead of converting it; the allowlist is only for genuine
  non-modelo lookalikes, each with a stated reason.

## Source

ADR `2026-06-10-modelo-enum-hardening-adr`; research
`2026-06-10-modelo-enum-hardening-research`. Enforced by
`src/aeat/core/tests/test_modelo_string_usage.py` (AST gate) and
`src/aeat/core/tests/test_modelo.py` (registry-parity plus non-registry
carve-out). Promoted per the `vaultspec-codify` discipline.

---
name: modelo-locales-cli-authority
trigger: always_on
---

# Modelo Locale CLI Authority

## Rule

Manage modelo schema-local translation TOML only through `python -m aeat.locales modelo ...`; never hand-edit registry-local `locales/*.toml` files for routine scaffold, set, remove, audit, or coverage work.

## Why

The accepted ADR `2026-06-11-modelo-locales-cli-adr` makes the modelo locale CLI the authoring authority for schema-local labels and help text while preserving legally grounded Spanish schema labels as the fallback. The review log `2026-06-11-modelo-locales-cli-code-review-audit` also records a real migration failure caught during CLI-routed scaffold: direct TOML edits would have bypassed the regression test and recovery path. This rule prevents stale keys, missing keys, accidental Spanish-schema mutation, and fragmented campaign tracking.

## How

- Good: run `python -m aeat.locales modelo coverage en 130 2019-y-siguientes` before and after translation work to record per-modelo progress.
- Good: run `python -m aeat.locales modelo scaffold ca 303 2023-y-siguientes` to align a selected schema-local catalogue without overwriting translated leaves.
- Good: run `python -m aeat.locales modelo set hu 130 2019-y-siguientes labels 01 "Bevételek"` to update one translated leaf after registry-key validation.
- Good: leave Spanish schema-local TOML absent unless a future ADR explicitly changes the fallback model; the official Spanish `CasillaDefinition.label` remains the legal source.
- Bad: opening `src/aeat/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/locales/en.toml` in an editor to add or remove keys by hand.
- Bad: treating scaffold placeholders whose value equals the schema key as completed translations.
- Bad: moving official Spanish schema labels into locale TOML or replacing schema `label` values with translated operator-facing text.

---
name: no-dormant-source-resolvers
trigger: always_on
---

# No dormant source resolvers; every binding source is routed or advised

## Rule

Every `ModeloSourceResolver` merged to main MUST be enrolled in the live calculate
mesh (`merge_source_resolutions` in
`src/aeat/application/modelo/_calculation_actions.py`) or deleted; every registry
binding `source` kind MUST be a member of the enrolled-or-explicitly-deferred set
(`_BUCKET_AGGREGATION_OWNED_SOURCES` ∪ `DEFERRED_SOURCE_KINDS`, enforced by
`assert_no_novel_source_kinds`); and `collect_unhandled_source_diagnostics` MUST
run on the live calculate path so an unrouted source surfaces a non-blocking
advisory — never a silent blank.

## Why

Audit `2026-06-10-calculation-engine-foundations-audit` finding F4 found the
safety net built and switched off: `collect_unhandled_source_diagnostics` had no
live-calculate caller, and `_BUCKET_AGGREGATION_OWNED_SOURCES` described the
enrolled set but enforced nothing — a new TOML binding with a novel `source`
compiled and silently resolved to blank, an estimated 50–70 silently-skipped
bindings across 7+ source kinds. A blank produced by a dormant or missing
resolver surfaces zero findings, violating `no-silent-under-declaration`. The
ADR `2026-06-10-calculation-aggregation-taxonomy-adr` (Implementation §6) made
closing this non-negotiable.

## How

- Good: a resolver is enrolled in the live `merge_source_resolutions((...))`
  tuple (`_calculation_actions.py:633`); `assert_no_novel_source_kinds`
  (`_calculation_actions.py:802`) raises `ModeloAggregationBindingError` at
  calculate time if a binding's `source` is in neither the owned nor the deferred
  set; `collect_unhandled_source_diagnostics` (`_calculation_actions.py:688`)
  appends a non-blocking advisory for any declared-but-unrouted source.
- Good: a not-yet-built source kind is added to `DEFERRED_SOURCE_KINDS` (canonical
  in `application/aggregation/_source_mesh.py`) — explicitly deferred, advisory-
  visible — never added to the `manual_input` allowlist (which would re-silence
  it).
- Bad: merging a fully-implemented `.resolve()` resolver that is exported but
  never enrolled in the mesh tuple — it is dead capacity and its declared registry
  kind blanks silently.
- Bad: landing a new `source` kind in registry TOML without enrolling a resolver
  or registering it deferred — the novel-source gate refuses it loudly, which is
  correct; silencing it via the manual allowlist is the violation.

---
name: no-legacy-compatibility
trigger: always_on
---

# No legacy or backwards-compatibility support

## Rule

This is an unreleased pre-beta project with no released data and no deployed
callers. Carry ZERO legacy code: no migration of old on-disk formats, no
read-tolerance of pre-current data shapes, no deprecated aliases, no retired
field handling, no version-upgrade ALTER passes, no "old serialised record"
coercion branches. When a format, schema, key derivation, or API shape changes,
DELETE the old surface and its tests outright — never add a bridge, fallback,
or compatibility shim to read what an earlier version of THIS app wrote. The
canonical state is the only state; old is deleted, not maintained.

## Why

There is no released version whose data must survive an upgrade, so every
migration pass scans for rows that cannot exist, every read-tolerance branch
guards against a shape nothing writes, and every "legacy path" is dead weight
that obscures the canonical flow and accretes test surface defending behaviour
no caller needs. Operator directive recorded 2026-06-10: "we should NOT be
supporting any legacy migration, legacy schema, legacy, retired or old
backwards compatibility. Basically old is to be deleted, and we're working
towards the future with ZERO legacy code support. This is an unreleased
pre-beta project. There's no backwards looking functionality support to
carry." This rule is the deletion-side companion to the architecture-boundaries
rule (which forbids INTRODUCING shims and deprecation paths); this one mandates
REMOVING the legacy surfaces that already exist. The zero-legacy-purge research
inventory (`2026-06-10-zero-legacy-purge-research`) is the worked deletion
backlog.

## How

- **Delete, do not bridge.** A from-birth deterministic key schema needs no
  migration from a randomized-key past — delete the migration module, its
  bootstrap call site, and its harness, not refactor it.
- **Refuse, do not tolerate.** When an envelope/prefix/typed shape is written
  from birth, the read path strips it and RAISES on a missing prefix (it can
  only mean corruption now), never silently returns the raw legacy form.
- **CREATE is not migration — keep it.** Fresh-schema CREATE/bootstrap that
  materialises the current shape on first access is forward-functional. An
  ALTER pass that upgrades an OLDER table to the current shape is legacy —
  delete it.
- **External-world variability is not our legacy — keep it.** Resilience for
  AEAT portal variations, BOE corpus formats, third-party PDF producer quirks,
  and AEAT regulatory revisions (each modelo revision year is CURRENT law for
  its filing year) is forward function, not backwards compatibility.
- **AEAT regulatory status is never evidence of CODE legacy — never conflate
  the two.** "AEAT (the Spanish tax authority) retired or superseded a modelo,
  revision, or rate as a matter of policy" is orthogonal to "our code carries a
  backwards-compatibility shim." A real modelo the application supports (e.g.
  `Modelo.M037`, no longer in general use but still supported) is a CURRENT
  product feature, not legacy code — keep it. Only delete a surface when it
  exists to read or migrate data that an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy — keep it.** A `schema_version`
  marker that lets a future version read today's records, or a
  `max_supported_version` ceiling that refuses a FUTURE shape, is
  forward-compatibility. Only code that BRANCHES on an OLD version is legacy.
- **Bad:** `if payload is None: payload = load(_legacy_cleartext_key(...))` —
  a read fallback under the current hardened key for pre-hardening records that
  cannot exist on an unreleased app. Delete the function and the fallback.
- **Bad:** an `ensure_*_columns` ALTER loop that adds today's columns to a
  table an older version CREATEd. Delete it; the CREATE already has them.
- **Key-management caution:** deleting a key-schedule or DEK-derivation branch
  on inference can strand encrypted data. Confirm the creation path mints only
  the current schedule before deleting an "old" one; this is the single place
  where a wrong deletion is unrecoverable, so it is owner-gated, not autonomous.

## Source

Operator directive recorded 2026-06-10 during the quality-hardening campaign on
the `chore/eliminate-shims` branch. Backing inventory:
`2026-06-10-zero-legacy-purge-research`. Companion rule:
`aeat-architecture-boundaries` (no new shims / deprecation paths).

---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration

## Rule

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a
draft that under-declares: whenever a positive economic input is declared (e.g.
resultado contable, rendimiento de módulos, ingresos) but the dependent base or
cuota resolves to zero and no offsetting reduction is declared, the gate MUST
surface at least an ADVISORY finding. A human files outside the application, so an
explicit operator-facing alert — never a silent grant — is the minimum safeguard
against filing a zero-tax return on positive activity.

## Why

Round-30 CLI persona testimonials and a coordinator reproduction found that the
Modelo 200 verify gate returned `granted_verificado_completo = true,
finding_count = 0` for a sociedad with resultado contable €140.000 but base
imponible `DP200014:00552 = 0` and cuota `DP200014:00562 = 0` — a silent
under-declaration the gate could not surface. The root cause was a calculation
chain modelled only partway (the base imponible casilla is a bare manual input
with no derivation from the resultado contable), so a positive-result filer who
does not also enter the base files zero. The durable fix is to model the
determination so a zero base is computed, not silently omitted; until that lands,
the gate must at least alert. See ADR `2026-06-02-modelo-200-base-determination`
and the round-30 testimonial audit. The same shape recurs across modelos whose
engines are partially modelled (M131 estimación objetiva rendimiento, multi-row
informativas), so the discipline is project-wide, not M200-specific.

## How

- **Good (worked example):** the Modelo 200 revision declares an ADVISORY
  `verification_predicate` `implies_nonzero(["00501", "DP200014:00552"])`. The
  `implies_nonzero` evaluator holds trivially when the antecedent is ≤ 0 (no false
  positive on losses) and fires only when the antecedent is strictly positive and
  the consequent is zero. As ADVISORY it surfaces a non-blocking WARNING (a
  legitimately zero base via BIN compensation or correcciones remains permissible)
  while making the under-declaration non-silent. Grounded with `legal_refs`.
- **Good:** when a calculation engine is later completed so the dependent value is
  computed (not manual), the silent-zero becomes impossible and the advisory can be
  upgraded to a `BLOCKING_RULE` consistency check between computed and entered
  values, or retired.
- **Bad:** shipping a partially-modelled calc chain (a manual base/result casilla
  with no derivation and no guard) so the verify gate grants `verified_complete`
  with `finding_count = 0` on positive economic input — the operator gets no signal
  that the return under-declares.
- **Bad:** using a `BLOCKING_RULE` guard that refuses legitimate
  positive-result/zero-base filings (negative result, full BIN compensation,
  exemptions). The guard must distinguish the suspicious case (positive antecedent,
  zero consequent) and stay advisory while legitimate zero-base cases exist.

## Source

ADR `2026-06-02-modelo-200-base-determination-adr` (Phase 1); round-30 CLI
testimonial audit `2026-06-02-cli-persona-testimonials-round-30-audit`; worked
example commit `414fd3529`. Promoted per the `vaultspec-codify` discipline.

---
name: no-tautological-calculation-tests
trigger: always_on
---

# No tautological calculation tests

Treat tautological calculation tests as forbidden. Do not assert registry runtime output against numbers hand-computed from the same registry formula under test.

Use external authority for expected calculation values. Prefer AEAT workbooks, BOE or AEAT worked examples, registry-authoritative fixtures, or live AEAT oracle replay.

When no external numeric authority exists, test graph wiring, validation errors, provenance, schema shape, or primitive evaluator contracts. Do not manufacture Decimal expectations from synthetic inputs.

Before accepting a calculation test, ask whether the test would fail if the registry formula were wrong against AEAT. If not, remove or rewrite it.

---
name: one-aggregation-path-pull-equals-calculate
trigger: always_on
---

# Pull and calculate share one aggregation path

## Rule

A casilla's value MUST be produced by the same aggregation logic whether reached
via the live `calculate` path or the Sheets-pull path; both surfaces share one
resolver set, and a regression proves they agree for a shared revision.

## Why

Audit `2026-06-10-calculation-engine-foundations-audit` finding F5 found
disconnected-surface drift: the Sheets-pull assemblers and the live calculate path
both persisted to the SAME revision, so a calculate-then-export or
export-then-calculate cycle could yield divergent, conflicting casilla values with
no detection at save time — a correctness hazard distinct from the silent-blank
class. Sharing one resolver set (the relation enrollment the aggregation-taxonomy
ADR mandated) eliminates the two-surface drift risk so the two transports cannot
disagree.

## How

- Good: `RelationPrefillSourceResolver.resolve` delegates to
  `resolve_relations_from_local_store`
  (`src/aeat/application/calculations/_relation_prefill.py:279`), the exact same
  function the Sheets-pull path calls
  (`entrypoints/cli/_config/_google_sync_calc.py:130`), so both transports run one
  resolver.
- Good: parity is enforced by
  `src/aeat/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
  — a regression that the pull path and the calculate path produce identical
  casilla values for a shared revision.
- Bad: a pull-path `assemble_*` helper that computes a casilla one way while the
  live calculate path computes it another — a calculate↔export cycle then drifts
  the persisted revision with no save-time detection.
- Bad: shipping a new aggregation surface on only one of the two transports — the
  parity regression must cover any casilla both paths can persist.

---
name: period-filter-single-boundary-authority
trigger: always_on
---

# Period filter single boundary authority

## Rule

Every period-scoped selection must resolve its date span through `Period.contains()` built from the canonical year plus AEAT-token grammar; no call site may implement a parallel boundary, inclusion override, or legacy period alias.

## Why

The `2026-06-10-ledger-filter-period-adr` made `Period.contains()` the single authority shared by CLI ledger filters, modelo calculation snapshots, sorting, and participation-index selection. Re-derived start/end math at call sites creates off-by-one gaps, overlaps, and inconsistent handling of adjacent quarters or months. A continuity invariant keeps the boundary gap-free and overlap-free.

## How

- Good: parse `--year 2026 --period 1T` to a `Period`, then filter rows by calling `period.contains(row.date)`.
- Good: modelo snapshot selection and ledger export use the same `Period` object and the same inclusion semantics.
- Bad: accepting `2026Q1`, `2026-1T`, `ANUAL`, or `Q1` as alternate boundary grammars after the canonical grammar is in force.
- Bad: open-coding `start <= row.date <= end` with locally derived dates in a CLI handler.

---
name: plan-closure-requires-exec-records
trigger: always_on
---

# Plan closure requires exec records

## Rule

A plan step must not be marked complete unless a matching exec record exists or the close audit explicitly records why the step is only a deferred carry-forward.

## Why

The `2026-06-11-ledger-hardening-close-audit` found C5 steps already checked without execution records and C4 implementation completed while its plan still showed zero progress. That made the handover harder to trust and hid the actual remaining work. Step checkboxes are the operator-facing truth only when backed by execution evidence.

## How

- **Good:** create one `.vault/exec` record per completed step before or alongside marking the step checked, then rebuild the feature index and run feature-scoped Vault checks.
- **Good:** leave a step unchecked when it is intentionally deferred, and name the follow-up campaign or blocker in the close audit.
- **Bad:** marking a plan step checked based only on code inspection, or claiming a campaign complete while `vault plan status` reports missing exec records.

---
name: registry-calculation-legal-grounding
trigger: always_on
---

# Registry calculation values must cite their binding legal source

## Rule

Every regulatory value compiled into the registry schema — a tax rate, a
bracket tranche, a threshold, a deadline window, a reduction coefficient — MUST
declare, in its `legal_refs`, the specific binding provision that *establishes
that value* (the article, disposition, or transitional provision of the law that
sets it), and that provision MUST be defined in the legal catalogue with a
`corpus_ref` resolving to the real BOE/AEAT text. Citing the general framework
article alone (e.g. `ley-27-2014:art-29`) is insufficient when a more specific
provision (a transitional disposition, a phased schedule, a modifying law) is
what actually fixes the number. A value whose binding provision is not in the
schema is treated as ungrounded and MUST NOT ship.

## Why

The Modelo 200 micro-empresa (INCN < 1M) two-tranche rate carried `0.17 / 0.20`
for 2025 in `is.modelo-200.tipo-gravamen-pyme`, grounded only in
`ley-27-2014:art-29`. The binding source — LIS **disposición transitoria 44ª**,
added by **Ley 7/2024** (BOE-A-2024-26694), which phases the rate to **21 % / 22 %
for 2025** and 19 % / 21 % for 2026 — was absent from the schema. Because the
specific provision that fixes the 2025 figure was never cited or cross-checked
against its corpus text, the wrong rate sat in the registry undetected and a
downstream commit (#210) compounded it by routing the cuota to a flat 23 %. The
value drifted precisely because nothing in the schema pinned it to the law that
sets it. A regulatory number with no binding-provision citation has no anchor to
verify against and is frail by construction. This is the authoring counterpart of
`[[aeat-calculation-grounding]]` (which preserves provenance through boundaries)
and `[[aeat-schema-central-config]]` (which keeps values in the registry): this
rule mandates that the value, at its authoring site, names and grounds the
provision that makes it binding.

## How

- **Good:** the micro-empresa 2025 bracket declares
  `legal_refs = ["ley-27-2014:art-29", "ley-27-2014:dt-44"]`, and
  `ley-27-2014:dt-44` is defined in `legal/is.toml` with
  `corpus_ref = "corpus/normatives/html/ley-27-2014-dt-44.html#dt44"`,
  `document_id = "BOE-A-2024-26694"`, and a `required_text` source-citation that
  the evidence gate cross-checks against the real text ("21 por ciento").
- **Good:** a deadline window or threshold cites the specific orden/RD/ley
  article that publishes it, not just the parent law, and the corpus carries the
  matching clause.
- **Bad:** a phased or transitional rate citing only the consolidated framework
  article while the transitional disposition that actually sets the year's figure
  is uncited — the number can be wrong and no gate can catch it.
- **Bad:** adding a `legal_refs` entry that points at a catalogue id with no
  `corpus_ref`, or whose corpus text does not contain the value's clause. The
  citation must be verifiable, not decorative.
- **Verification:** when authoring or changing a regulatory value, confirm the
  binding provision is (1) cited on the value's `legal_refs`, (2) defined in the
  legal catalogue, (3) backed by corpus text the evidence gate validates, and
  (4) consistent with the value (the corpus clause states the number you encoded).

## Source

Binding-law reconciliation of the Modelo 200 micro-empresa INCN<1M cuota
(LIS art. 29.1 + DT 44ª, Ley 7/2024, BOE-A-2024-26694). Origin: operator
directive recorded 2026-06-02 — "legal groundings the schema must be grounded
against and cross-referenced; if the actual modelo schema does not contain the
legal grounding all work will be frail." Promoted per the `[[vaultspec-codify]]`
discipline.

---
name: registry-resolver-family-extraction
trigger: always_on
---

# Registry binding/resolver families extract into per-family modules

## Rule

A registry binding or resolver family (counterpart, ledger, invoice,
detail-record, withholding, previous-filing, …) MUST live in its own per-family
module under `domain/calculations/registry/`, consumed only through the package
top-level `__all__` facade. New families follow the established per-family module
shape (selector model + typed validator registered in the dispatch table +
`resolve_*` functions) rather than growing the `_bindings.py` aggregator. The
aggregator re-exports; it does not accrete family implementations.

## Why

The `2026-06-02-registry-bindings-boundary-audit` found `_bindings.py` had grown
to a ~3,000-line module mixing ~15 resolver families with a private selector
coupling into `_formula_runtime.py`; it proposed a staged per-family extraction
behind re-exports as the codify candidate `registry-resolver-family-extraction`,
which was never promoted. The bindings-interface-hardening campaign confirmed the
shape: families already split into `_counterpart_bindings.py`, `_ledger_bindings.py`,
`_invoice_bindings.py`, `_detail_record_bindings.py`, `_withholding_bindings.py`,
and `_bindings_previous_filing.py`, with one validator dispatch table in
`_bindings.py`. Codifying the discipline keeps the aggregator from re-accreting and
keeps cross-package consumers on the package facade rather than dotting into a
family's internals. Promoted per the `vaultspec-codify` discipline after the shape
held across the campaign.

## How

- **Good:** a new source family lands as `_<family>_bindings.py` (selector model,
  `validate(binding) -> list[str]` in the dispatch table, `resolve_*`), re-exported
  through the registry package `__all__`; consumers import from the package top
  level.
- **Good:** `_bindings.py` holds the cross-family dispatch table and re-exports,
  not per-family resolver bodies.
- **Bad:** adding a new family's selector/validator/resolver inline into
  `_bindings.py`, regrowing the monolith.
- **Bad:** a consumer importing `from ...registry._counterpart_bindings import ...`
  (dotting into a family's private submodule) instead of the package facade.

## Source

Audit `2026-06-02-registry-bindings-boundary-audit` (codify candidate, never
promoted) and ADR `2026-06-14-bindings-interface-hardening-adr` (decision F).
Companion to `service-imports-via-top-level-reexports` and
`aeat-architecture-boundaries` (relocation atomicity).

---
name: registry-revision-content-inline-or-fragmented
trigger: always_on
---

# Registry revision content is inline OR fragmented — assess by both, never `ls`/`find` alone

## Rule

A registry modelo revision MAY declare its bindings, formulas,
`verification_expectations`, and `verification_predicates` EITHER inline in
`revision.toml` (the older monolithic format) OR in fragmented subdirectories
(`bindings/`, `formulas/`, `verification_expectations/`, …). When assessing
whether a revision is calc-grade, whether a casilla is ledger-bound, or whether a
binding/formula is present, read BOTH the inline `revision.toml` AND the
subdirectories — RAG-ground the concept first (`aeat-rag-discovery`), then `grep`
to confirm. NEVER infer a revision's calc-grade or binding coverage from
`ls bindings/` / `find -path '*formulas*'` on the subdirectories alone: the
subdirectory listing is blind to inline declarations and yields false
"parse-only / zero-bindings / staged build-out" conclusions.

## Why

During #15 (IVA-3, M303 `2009-y-siguientes`, filing years 2009-2022), a
structural check that only counted `bindings/` and `formulas/` subdirectory
files concluded the revision was "parse-only" with no calculation machinery and
filed a verdict of "not a live gap, by design". That was WRONG: the
`2009-y-siguientes` revision declares its cuota bindings, formulas, compensación
carry, and `verification_expectations` INLINE in `revision.toml`, while the
sibling `2023-y-siguientes` uses the fragmented-subdirectory format. The
subdirectory-blind check missed a real, plausibly-live "cuota-without-base"
under-declaration (the base-imponible casillas 01/04/07/28 were ledger-unbound on
2009-2022 while the cuota resolved). The operator's "the schema may be defective —
use RAG" challenge surfaced it; RAG-grounding the actual binding sets exposed the
defect, which was then fixed (#15 + the #41 recargo/59-60 tail). The same
inline-vs-fragmented blind spot also mis-classified M369 (OSS, fully inline) in
the settlement-guard sweep. Only M303 and M369 use inline today, but the format
is per-revision, not per-modelo, so the check must always consider both. This is
the discovery-method companion to `aeat-rag-discovery` (RAG-first grounding) and
`aeat-registry-authority-flow` (the loader merges inline and fragmented into one
strict schema regardless of on-disk form).

## How

- **Good:** to decide whether a casilla aggregates from the ledger on a given
  revision, `grep` BOTH `revision.toml` (inline `[[revisions."…".bindings]]` +
  the casilla's `binding =` / `input_kind`) AND the `bindings/` /
  `casillas/` subdirectories; RAG-search the concept first, then `grep` the exact
  ids. Better still, load the revision through the authority
  (`resources().modelos.authority.snapshot(...)`) and inspect
  `revision.bindings` / `revision.casillas` — the loaded schema is format-agnostic
  and is the ground truth.
- **Good:** to find binding-coverage asymmetries, compare a casilla's `binding =`
  + `input_kind` across sibling revisions from the LOADED snapshot (or by reading
  both inline and fragmented sources), not by diffing subdirectory file counts
  (the #15 / #40 pattern).
- **Good:** before grounding any binding-source classification, read the binding's
  `source` field (`ledger_iva_aggregation` vs `profile` vs `relation_prefill`),
  wherever it is declared — a `source = "profile"` binding (autoconsumo, state
  attribution) is not a ledger silent-zero even when absent (#43).
- **Bad:** `ls bindings/ | wc -l` or `find … -path '*formulas*' -name '*.toml' | wc -l`
  as the SOLE signal of "is this revision calc-grade / does this casilla bind" —
  blind to inline declarations; it produced the wrong #15 "parse-only" verdict.
- **Bad:** concluding "not a gap / staged build-out / parse-only by design" from
  subdirectory absence without reading `revision.toml` and RAG-grounding the
  actual binding/formula set.

## Source

The #15 IVA-3 correction (M303 `2009-y-siguientes` domestic-base, fixed in
`6c259afc3`; the recargo/59-60 tail in `4e669c113`), the binding-coverage
systemic sweep, and the binding-source grounding that scoped out the
profile-source autoconsumo/state-attribution casillas. Promoted per the
`vaultspec-codify` discipline after the inline-vs-fragmented blind spot caught two
real regulated under-declaration defects and prevented a false-positive in one
campaign. Companion rules: `aeat-rag-discovery`, `aeat-registry-authority-flow`,
`registry-calculation-legal-grounding`.

---
name: relation-slot-bindings-declare-relation-source
trigger: always_on
---

# Relation-targeted slot bindings declare relation_prefill

## Rule

A binding that exists only as a relation's `target_binding` materialisation slot
MUST declare `source = "relation_prefill"`, never `source = "previous_filing"`; a
`previous_filing` binding MUST satisfy the direct-selector predicate
(`_is_direct_previous_filing_binding`,
`src/aeat/domain/calculations/registry/_bindings_previous_filing.py`), and
registry validation refuses a binding that is both relation-targeted AND
previous-filing-resolvable — the M303 iva-wallet compensación slot being the sole
documented carve-out.

## Why

ADR `2026-06-10-calculation-aggregation-taxonomy-adr` (Implementation §3,
slot-binding hygiene) found the cross-modelo fold-in overlap had a single root
cause: relation `target_binding` slots were mislabelled `source = "previous_filing"`
for a value only relation resolution could produce, so one fold-in looked like two
mechanisms and the enrolled `previous_filing` resolver skipped the non-direct slot
by design, leaving it dormant. Re-stamping the slot `relation_prefill` and gating
the collision at registry-compile time makes the dual-modelling structurally
impossible (defence in depth per `composition-service-no-parallel-write-path`).

## How

- Good: a relation-targeted M100/M180/M190/M193/M200/M202 slot binding declares
  `source = "relation_prefill"`; the collision gate in
  `domain/calculations/registry/_validate_relation_sources.py` confirms no binding
  is both relation-targeted and direct-previous_filing-resolvable.
- Good: a same-modelo direct carry keeps `source = "previous_filing"` and passes
  `_is_direct_previous_filing_binding`; the M303
  `modelo-303-compensacion-pendiente-anteriores` slot is the named carve-out
  (`_IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS`,
  `_validate_relation_sources.py:42`) — owned pre-mesh by the iva-wallet gate.
- Bad: a relation `target_binding` slot declaring `source = "previous_filing"`
  with a non-direct selector — the registry gate now refuses it instead of letting
  the enrolled resolver silently skip it.
- Bad: a binding that is both a relation `target_binding` and a direct
  previous_filing carry (outside the M303 carve-out) — the collision gate rejects
  it at compile time.

---
name: retired-enum-members-need-consumer-reconciliation
trigger: always_on
---

# Retired enum members need consumer reconciliation

## Rule

Before deleting a retired enum member, reconcile every validation, schema, fixture, and test consumer into one accept-or-reject state and prove the owning collection gate is green.

## Why

The `2026-06-11-ledger-hardening-close-audit` found that `AggregationSourceKind.INVOICE` looked retired at the CLI layer but still powered a contradictory registry-validation surface: schema construction accepted it, validation routed it positively, and selector validation rejected it. Deleting that member before reconciling consumers would break registry fixtures and hide whether the intended final state is acceptance or rejection. The project needs one coherent state before enum deletion.

## How

- **Good:** before removing an enum member, search production and test consumers, migrate fixtures to the replacement member, update validators so all paths either accept or reject consistently, then run the owning collection and behavior gates.
- **Good:** if collection is red from peer work, leave the deletion step open and record the blocker in an audit or plan note.
- **Bad:** deleting the enum member because no production TOML uses its string while schema, validator, and tests still construct or branch on the member.

---
name: revision-resolution-is-law-determined
trigger: always_on
---

# Revision resolution is law-determined, never injected

## Rule

Every production calculation, verification, filing, export, or projection path
MUST resolve its registry revision from `(modelo, filing_year, period)` through
`ValidatedRegistryAuthority.snapshot` / `select_revision`
(`src/aeat/domain/calculations/registry/_temporal.py`) or
`resolve_registry_revision_for_work_target`
(`src/aeat/application/modelo/_work_addressing.py`); a stored, literal, or
operator-supplied `revision_id` may only be *asserted equal* to that resolution,
never injected as the selector.

## Why

ADR `2026-06-10-period-revision-resolution-adr` (ruling 1 / D1) ratifies
`select_revision` as the single law-determined period→revision resolver: AEAT
binds every `(modelo, filing_year, period)` triple to exactly one revision by
publishing orden, so "which revision applies" is a derived fact, not an input.
Feeding a stored `revision_id` back into resolution makes the stored value
*causal* on the computation — the defect class that lets one year's numbers be
computed under another year's norms. Comparing it against the resolver's answer
makes the law causal and the stored value a checked claim; the non-overlap gate
`validate_revision_windows` guarantees the resolution is unique, so a `revision_id`
narrowing can only equal the law-determined pick or refuse.

## How

- Good: a calc entry loads a WorkUnit, resolves the snapshot from its
  `filing_year` + `period`, then asserts equality —
  `if snapshot.revision.id != work_unit.revision_id:` raises an instructive
  refusal naming both revisions (`_calculation_actions.py:594`,
  `_calculate_input.py:265`). The unit's `revision_id` is compared, never passed
  into resolution.
- Good: a creation-time `--revision` is accepted only when it names exactly
  `select_revision(modelo, filing_year=year, period=period).id`
  (`resolve_registry_revision_for_work_target`); the explicit id is an
  assertion/idempotence handle, not a free override.
- Bad: passing `unit.revision_id` (or a literal) into `authority.snapshot(...)`
  on a calculation path so resolution is *selected* by the stored value — a
  silent legal mismatch when the registry's law-mapping was corrected after the
  unit was created.

---
name: sensitive-financial-data-secure-storage-only
trigger: always_on
---

# Sensitive financial data persists only in secure storage

## Rule

All sensitive financial data — every purchase invoice and every incoming or
outgoing business invoice, every bank statement and supporting document, and any
decrypted evidence bytes derived from them — persists ONLY inside the encrypted
secure-storage backend, accessed through the runtime wrapper that maps to the
active profile bucket (`secure_object_repository_for_active_bucket` /
`secure_object_repository_for_bucket`, the `SecureObjectRepository` substrate, and
the content-addressed `AttachmentStore` that wraps it). No code path may write or
persist sensitive financial data anywhere outside secure storage: no temp files, no
scratch directories, no plaintext side stores, no caches on disk, no logs. Decrypted
bytes may exist only transiently in process memory and must never be written out. A
path pointer to a cleartext file on operator disk (e.g. a `source_path` field) is
NOT a valid persistent home for invoice bytes; the bytes themselves belong in secure
storage.

## Why

This invariant is enforced by prior ADRs and by secure-storage enrollment across
multiple epic runs; it is the load-bearing confidentiality guarantee of the whole
application. The `llm-evidence-classification` Stage-3 research/ADR pass on
2026-06-10 is the worked example of how an agent breaks it: an early draft, reaching
for "let an LLM read the invoice", designed a decrypted-temp-file route for the
subprocess CLI agents and framed "which providers may receive decrypted evidence" as
a tunable privacy boundary. The operator rejected this outright — taking sensitive
financial data out of secure storage (to a temp file, or by uploading it off-host)
is never acceptable, and is categorically unacceptable for gestors or any serious
professional usage. Writing a client's invoice bytes to a scratch file or shipping
them to a third party is exactly the exposure secure storage exists to prevent. The
rule is restated in the rule layer (not only in ADRs) because this is the authoring
moment where the temptation appears, and a rule is what loads into the next agent's
context before it writes the violating line.

## How

- **Good:** invoice/attachment bytes are written and read through the
  content-addressed `AttachmentStore` (`put_bytes` / `read_bytes`), which wraps
  encrypted `Envelope` records in `SecureObjectRepository` at `FINANCIAL`
  sensitivity via the active-bucket runtime wrapper. A consumer that needs the bytes
  (e.g. to hand a document to an on-host model) reads them into memory and uses them
  transiently; nothing is written to disk.
- **Good:** a feature that must let a model read a document runs the reader on-host
  (in-tree text extraction, or a local vision model fed in-memory base64) so the
  bytes never leave the machine. Any off-host transmission is gated behind an
  explicit, per-invocation, default-off, gestor-barred operator consent
  acknowledgement (see `off-host-evidence-upload-requires-explicit-consent-gate` when
  it lands) and never uses a transport that writes a file.
- **Bad:** materialising decrypted evidence to a temp file (even "bounded
  lifetime", even `chmod 600`, even "removed promptly") so a subprocess CLI tool can
  read it by path. The temp file is persistence outside secure storage — forbidden.
- **Bad:** storing only a `source_path` to a cleartext file on operator disk and
  treating that as the durable home of the bytes. The bytes must be in secure
  storage; a path is not storage.
- **Bad:** writing sensitive financial values to logs, a plaintext JSON side store,
  an on-disk cache, or a scratch directory for debugging.

## Source

Operator directive recorded 2026-06-10 during the `llm-evidence-classification`
Stage-3 research/ADR pass on the `chore/eliminate-shims` branch, after an ADR draft
proposed a decrypted-temp-file evidence-reading route. Backing decision: ADR
`2026-06-10-llm-evidence-classification-adr` (the `sensitive-financial-data-persists-
only-in-secure-storage` and `off-host-evidence-upload-requires-explicit-consent-gate`
codification candidates). Companion rules: `aeat-safety-legal-gates`,
`aeat-architecture-boundaries`.

---
name: service-imports-via-top-level-reexports
trigger: always_on
---

# Service imports via top-level re-exports

## Rule

A new application-layer service MUST consume cross-package primitives through
the consumed package's top-level ``__all__`` re-export, never through an
internal submodule import (the ``_foo`` module that owns the implementation is
private to its package). Promote the symbol to ``__all__`` as a precondition;
the service-side import line is then the package-top-level form.

## Why

The BucketMaintenanceService composition pattern landing on 2026-06-03 surfaced
the consequence of letting one consumer dot into a package's internals: every
later consumer reads the precedent as permission to do the same. The fix is
mechanical (add the symbol to ``__all__`` + the lazy ``__getattr__`` block) but
re-binding the call sites later is invasive. Better to insist at authoring
time that a new service consume symbols through the package boundary.

Concretely, the precondition Step for the bucket-maintenance composition
promoted ``rename_profile``, ``delete_profile_with_lifecycle_span``,
``remove_profile_bucket_directory``, ``serialize_profile_bundle``,
``deserialize_profile_bundle``, ``SUPPORTED_BUNDLE_SCHEMA_VERSIONS``, and
``UserProfilePortableExport`` to top-level surfaces before the service
consumed them. Operator-direct directive recorded 2026-06-03 in the same
session: "single authoritative source that is imported only from top level
re-exports not from internal submodules".

## How

- **Good:** a new ``aeat.application.bucket_maintenance`` service imports
  ``rename_profile`` from ``aeat.application.user_profile`` (the package
  ``__all__`` re-export). The precondition Step promoted the symbol to that
  surface before the service file was authored.
- **Good:** a regression-gate test pins the public surface
  (``test_bundle_reexports.py``) so a future refactor cannot retract the
  re-export and force the service to import from internals again.
- **Bad:** a service file imports ``from ....application.user_profile._orchestration
  import rename_profile`` (dotting into the private submodule). The next agent
  who needs the same symbol reads the precedent and does the same; gradually
  the package boundary is eroded.

## Source

Operator directive recorded 2026-06-03 during the BucketMaintenanceService
composition-pattern landing on the ``chore/eliminate-shims`` branch. Backing
ADR: ``2026-06-03-cli-workflow-redesign-adr``. Backing research:
``2026-06-03-cli-workflow-redesign-research``. Backing exec record:
``2026-06-03-cli-workflow-redesign-exec``.

---
name: shipped-search-licence-clean
trigger: always_on
---

# Shipped Search Licence Clean

## Rule

Documentation search artifacts that ship in the package or built docs must contain only licence-clean sources and laundered identifiers/rankings; never ship vectors, sparse term weights, raw retrieval scores, snippets, or data derived from NC/ND/gated sources. Commit only the LIGHT precompiled DATA (the laundered relevance mapping, synonym candidates, held-out queries, the Handbook fragments); never commit the HEAVY generated search INDEX (the Pagefind corpus under `pagefind/` and `docs/_build/`), which is gitignored and regenerated on every docs build.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` makes licence-clean shipping a hard constraint and, in D6/D9, allows the dev RAG only as a build-time oracle whose outputs are laundered before shipping. This prevents SPLADE or other restricted model/data outputs from tainting the offline documentation search backend. The `2026-06-15-docs-terminology-search-adr` (D3) adds the commit boundary after a 63 MB / ~16k-file compiled Pagefind index was found committed at the repo root: the index is a deterministic build output, not source, so committing it bloats every clone and drifts from the corpus. The light precompiled data is what CI and readers consume; the heavy index they regenerate.

## How

- Good: Commit a relevance mapping containing target ids, target URLs, surfaces, and normalised ranking weights after ratified review; keep `pagefind/` gitignored and untracked.
- Good: regenerate the Pagefind index at docs-build/deploy time from the committed light data; never `git add` the generated `pagefind/` corpus.
- Bad: Commit an embedding vector, SPLADE sparse map, raw score/path/snippet payload, or unreviewed term data from an NC, ND, gated, or unlicensed source.
- Bad: commit the generated Pagefind index corpus (`pagefind/`, thousands of fragment/index/wasm files) to the git base.

---
name: terminology-scaffold-preserve-contract
trigger: always_on
---

# Terminology Scaffold Preserve Contract

## Rule

Every Terminology Handbook scaffold run must preserve curated fields verbatim, scaffold new entries as empty drafts, and retire vanished entries as tombstones with `replaced_by`; never fuzzy-fill curation fields or delete concept records.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` adopts the msgmerge three-outcome contract in D3 because generated discovery and human curation share the same TOML authoring tree. Clobbering curated prose, inventing definitions, or deleting vanished records breaks reviewability and the immutable-id/tombstone model.

## How

- Good: A new registry enrolment creates a draft concept with empty curated prose, while an existing concept keeps its hand-edited definitions and aliases unchanged.
- Bad: A scaffold run rewrites a curated short description from source labels, guesses an English definition, or removes a concept file because the source disappeared.

---
name: terminology-single-declaration
trigger: always_on
---

# Terminology Single Declaration

## Rule

Every user-facing domain term must be enrolled once in the Terminology Handbook and referenced from docs through that entry; never redeclare an enrolled term's definition in prose or maintain a parallel hand-authored glossary.

## Why

The accepted `2026-06-10-docs-terminology-search-adr` identifies four unsynchronised terminology stores as the failure mode this feature removes. D7 makes the generated glossary and `:term:` references the enforcement surface, so inline redefinitions recreate the drift the Handbook exists to prevent.

## How

- Good: Add or update a concept fragment under `src/aeat/_data/terminology/concepts/`, then use `:term:` references in docs prose.
- Bad: Define "prorrata" in a how-to paragraph while also keeping a Handbook concept and generated glossary entry for `prorrata`.

---
name: tests-live-under-domain-tests-folders
trigger: always_on
---

# Tests live under domain tests folders

## Rule

Every Python test file must live under a parent `tests/` directory at the narrowest owning package or architectural boundary; naked `test_*.py` files beside implementation modules are forbidden.

## Why

The `2026-06-05-test-topology-refactor-adr` decision keeps Rust-style local ownership while removing implementation namespace pollution. Without this rule, future agents can reintroduce naked colocated tests and undo the mechanical topology invariant the refactor depends on.

## How

- Good: `src/aeat/application/modelo/tests/test_work_addressing.py` tests the `aeat.application.modelo` surface from its local test folder.
- Bad: `src/aeat/application/modelo/test_work_addressing.py` sits beside implementation modules and pollutes the code namespace.

---
name: uncommitted-wip-is-not-orphaned
trigger: always_on
---

# Rule

An uncommitted working-tree change with no *reachable* owner MUST be treated as live peer WIP, never orphaned: never discard or overwrite it (by `git restore`/`checkout`/`reset` OR by a file `Write`-from-HEAD — the mechanism is irrelevant), and to land your OWN change that shares a file with that WIP, use the apply-cached gated drive (stage a HEAD-anchored own-edits-only patch to the index, verify the staged set carries zero foreign markers, commit) rather than waiting on, discarding, or bundling the peer work.

## Why

During RET-1 (#6) P02 the coordinator discarded an uncommitted `_calculation_actions.py` change believing it orphaned (zero committed consumers, both *reachable* teammates disclaimed it); it re-appeared within minutes — a live, unaddressable agent owned it, and **re-appearance after a discard is proof of life** (audit `2026-06-24-retenciones-perceptor-count-audit`, INCIDENT-1/2). The campaign then proved the safe alternative across three independent landings (r2 #6 P02 `699b73dfe`, iva #2 P02 `95e328b38`, autonomo-130 A1/A2 `5cc10dc6a`): `git apply --cached` stages only your HEAD-anchored hunks to the index without touching the working tree, so the peer's live WIP is preserved and your commit carries only your lines. A fourth lesson rode the same campaign: in a shared worktree `git push` carries **all** ancestors to origin, so a peer's locally-held commit can be pushed by anyone else's push — check `git log origin..HEAD` before pushing.

## How

- **Good:** to land your own edit in a file that also holds a peer's uncommitted sweep, `git show HEAD:path > /tmp/copy`, apply ONLY your edits to that HEAD copy, `git diff --no-index` it into a HEAD-anchored own-only patch, `git apply --cached` it (the entangled interleaved-hunk case is handled this way), `git add` your fully-clean files, verify `git diff --cached | grep -c <peer-sweep-marker>` is `0` **immediately before** committing, then commit the index. The peer's working-tree WIP stays intact and commits cleanly on top later.
- **Good:** before `git push`, run `git log origin..HEAD` and confirm no peer's hold-for-now commit is in the range; if one is, expect your push to carry it (coordinate first).
- **Good:** a whole-revision-validating change (a registry re-stamp) is NOT a candidate for the apply-cached drive — it validates against the dirty working tree, so it genuinely waits for the peer sweep to commit; hold, don't force.
- **Bad:** `git restore`/`checkout`/`reset`/`git clean` or a `Write`-from-HEAD that wipes a live peer's uncommitted change to "unblock" your commit — destroys in-flight work; a prior authorization to discard an *orphaned* WIP does not extend to a *proven-live* one, and a peer proposing the mechanism cannot supply the authorization.
- **Bad:** a `git commit` with **no pathspec** while another agent has files staged in the shared index — it sweeps their staged work under your SHA; verify the staged set is exactly yours first (a pathspec commit, conversely, re-stages the working-tree peer WIP for entangled files, so it is not a substitute — the verified-index no-pathspec commit is the correct shape).

---
name: vaultspec-archive-discipline.builtin
trigger: always_on
---

# Archive discipline: audit incoming references before retiring a feature

A working example of codification applied to a real audit finding. This rule was
promoted from the rolling CLI UX audit (finding B9) following the discipline described
in the `vaultspec-codify` rule.

## Rule

Before invoking `vaultspec-core vault feature archive <feature-tag>`, run the same verb
with `--dry-run` as the canonical discovery pass and audit the preview for incoming
references: documents outside the feature whose `related:` frontmatter points at
documents inside it. Decide whether each incoming reference should be rewritten,
acknowledged as dangling, or block the archive entirely before applying the real run.

## Why

The rolling CLI UX audit's B9 finding documented compounding gaps in the archive verb:
no preview, no reversal verb, silent breakage of cross-feature `related:` links, and a
destructive auto-fix path. The CLI has since closed the verb-level gaps: the archive
verb carries `--dry-run`, a paired `vaultspec-core vault feature unarchive` verb
restores a mistaken archive, and archiving a nonexistent tag exits 1 with an error
(re-verified against the live CLI on 2026-06-10, `vaultspec-core --version` 0.1.26).
What the CLI cannot decide is whether an incoming cross-feature reference is provenance
to preserve, a stale link to drop, or a dependency that should block retirement. That
judgment is this rule.

## How

- Run `vaultspec-core vault feature archive <feature-tag> --dry-run` and read the
  previewed changes; classify every incoming reference before the real run.
- After the real run, verify `vaultspec-core vault check all` stays green. If the
  archive was a mistake, `vaultspec-core vault feature unarchive <feature-tag>` reverses
  it.

## Status

Active. The CLI improvements this rule anticipated (`cli-memory-lifecycle`
`W02.P04.S14`) have landed: `--dry-run` is the canonical discovery pass, `unarchive` is
the reversal verb, and typo'd tags fail loudly. The rule's intent (audit incoming
references before retirement) survives the verb improvement; the discovery procedure now
lives in the CLI preview.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B9 critical. Sibling
decision ADR `2026-05-17-cli-memory-lifecycle-adr`. Umbrella plan step `W02.P04.S14` in
`2026-05-17-cli-simplification-ux-plan`.

---
name: vaultspec-cli.builtin
trigger: always_on
---

# Vaultspec Core CLI

This project is vaultspec-managed. See `vaultspec.builtin.md` for framework rules and
workflow concepts.

## Mandate

Use `vaultspec-core` to create, read, audit, and repair `.vault/` documents. Never
hand-write frontmatter, filenames, plan structure, or new `.vault/` documents; editing
the body prose of a document scaffolded by `vaultspec-core vault add` is permitted (see
"Allowed manual edits" below). `vaultspec-core` enforces templates, tag taxonomy,
wiki-link resolution, schema dependencies, and provider sync; bypassing it produces
drift that `vaultspec-core vault check` and `vaultspec-core spec doctor` will flag.

## Orientation

Before starting work in a vaultspec-managed project you have no session context for, run
`vaultspec-core status` and read the in-flight plans it names. Each in-flight plan shows
a one-line overview: tier, completed waves and phases, step completion, and the next
open step. The targeted form `vaultspec-core status <plan-or-feature>` traces a plan to
its steps, execution records, and grounding documents. Orientation is descriptive and
read-only: it is the zeroth move, not a pipeline phase, and produces no artifact.

## Commands

### Orient

- `vaultspec-core status [TARGET]` - orient in an unknown or resumed project
- `vaultspec-core vault feature list` - list feature tags in the vault
- `vaultspec-core vault list [DOC_TYPE] [--feature <tag>]` - list or filter vault
  documents

### Author the pipeline

- `vaultspec-core vault add <type> --feature <tag>` - create a `.vault/` document

### Verify & audit

- `vaultspec-core vault check all [--fix]` - audit drift, broken links, or missing
  references
- `vaultspec-core vault check features --feature <tag>` - confirm required documents
  exist for a feature
- `vaultspec-core vault sanitize annotations [--feature <tag>] [--dry-run]` - strip
  generated template annotations

### Advanced vault inspection

- `vaultspec-core vault stats [--invalid] [--orphaned]` - show statistics, invalid, or
  orphan documents
- `vaultspec-core vault graph [--feature <tag>]` - visualize the vault dependency graph

### Workspace & maintenance

- `vaultspec-core spec <resource> list` - list registered rules, skills, agents, hooks,
  or MCPs
- `vaultspec-core spec mcps status --json` - verify MCP config health
- `vaultspec-core spec system show` - inspect the assembled system prompt
- `vaultspec-core sync` - propagate edits under `.vaultspec/rules/...`
- `vaultspec-core spec doctor` - diagnose overall workspace health
- `vaultspec-core migrations status` / `vaultspec-core migrations run` - inspect or run
  pending schema migrations
- `vaultspec-core vault feature archive <tag>` - archive a feature so it no longer
  exists in the active project
- `vaultspec-core vault rule promote --from <audit-stem> --as <rule-name>` - promote an
  audit finding to a project rule

`<resource>` is one of `rules`, `skills`, `agents`, `hooks`, or `mcps` for `list`; one
of `rules`, `skills`, `agents`, `hooks`, `mcps`, or `system` for resource-scoped
maintenance sync. Use top-level `vaultspec-core sync` as the authoritative complete
propagation command after source-side changes.

## Runtime

- Run `vaultspec-core <cmd>` when the binary is on `PATH`. In uv-managed environments,
  run `uv run --no-sync vaultspec-core <cmd>`.
- Use `--target DIR` (or `-t`) to operate on a directory other than the current one.
- Use `--dry-run` to preview changes.
- Use `--json` for machine-readable output.
- Read sync-shaped results (`vaultspec-core install`, `vaultspec-core sync`,
  `vaultspec-core spec <resource> sync`, `vaultspec-core migrations run`) with one
  vocabulary: `created`, `updated`, `unchanged`, `removed`, `restored`, `skipped`,
  `failed`. `unchanged` is a successful no-op, not a failure; `skipped` always carries a
  reason worth reading; only `failed` stops the pipeline. With `--json`, the top-level
  `status` is the run's aggregate outcome (`mixed` when items disagree).
- Use `--force` when a mutating command must overwrite existing output.
- Run `vaultspec-core <cmd> --help` for the full flag, subcommand, and exit-code
  reference.

## Allowed manual edits

Permitted:

- Edit body prose of a `.vault/` document scaffolded by `vaultspec-core vault add`.
- Edit source files under `.vaultspec/rules/rules/`, `.vaultspec/rules/skills/`,
  `.vaultspec/rules/agents/`, `.vaultspec/rules/hooks/`, or `.vaultspec/rules/mcps/`,
  then run `vaultspec-core sync`.

Forbidden:

- Hand-writing frontmatter, filenames, or new `.vault/` documents.
- Editing files inside generated provider directories; `vaultspec-core sync` regenerates
  them.

## References

- `.vaultspec/rules/reference/cli.md` - locally-resident machine-facing CLI reference:
  command inventory, options, argument enumerations, exit codes, and environment
  variables. Read this first; no network round-trip needed.

---
name: vaultspec-codify.builtin
trigger: always_on
---

# Codify durable lessons as project rules

The `vaultspec-core` workflow has a research → decide → plan → execute → review arc. The
audit-derived sixth phase is `codify`: when a review surfaces a durable lesson - a
constraint that should bind future agents across sessions - write that lesson down as a
rule the next agent inherits on load.

This rule defines when to codify, what to codify, and how to author the artifact.

## When to codify

Not every observation in a review is a rule. The bar is durability. A
codification-worthy lesson satisfies all three:

- **Cross-session.** A new agent who has never seen this feature should still benefit
  from the rule.
- **Constraint-shaped.** The lesson can be rendered as a positive obligation ("always
  X") or a negative one ("never Y"), not as a description.
- **Project-bound.** The lesson is specific to this project's conventions, stack, or
  constraints. Generic engineering advice belongs in external documentation.

Never codify on the first encounter with a constraint. A lesson qualifies only after it
has held across at least one full execution cycle; the first encounter is an audit
finding, not yet a rule.

Examples that codify well: "harbor-notes runtime data lives under `~/.harbor-notes/`;
never under `$TMPDIR`", "every destructive verb must accept `--dry-run`", "step records
use the canonical filename schema". Examples that do not: "we considered library X,
picked library Y" (that is an ADR), "the deploy failed last week" (that is an audit
finding without a durable lesson).

## What to codify

The rule body names the constraint precisely. Three sections, in order:

- **Rule.** One sentence stating the obligation. Imperative voice. No backstory.
- **Why.** Two or three sentences naming the constraint's origin - the audit document or
  ADR that surfaced the lesson, the failure mode it prevents.
- **How.** Concrete worked examples of the rule applied and the rule violated.

Keep the rule short. A rule longer than its own justifying audit finding has lost the
plot. If the rule needs more than a page, it is actually a reference document; produce
`.vault/reference/yyyy-mm-dd-{feature}-reference.md` instead.

## How to author

A codification produces a file under `.vaultspec/rules/rules/` that captures the rule.
Two canonical authoring paths exist:

- **Promote from an audit** (preferred when the lesson originates in an audit document):
  `vaultspec-core vault rule promote --from <audit-stem> --as <rule-name>` reads the
  audit, scaffolds the rule file, and records the audit stem in the rule's
  `derived_from:` frontmatter. The author then refines the scaffolded body into the
  three-section shape above.

- **Author directly** (when the lesson originates in an ADR or outside the vault):
  `vaultspec-core spec rules add <rule-name>` scaffolds an empty rule file; the author
  fills the three sections and names the source document by stem in backticks in the
  **Why** section.

In both paths, `<rule-name>` is the kebab-case slug naming the rule's subject (e.g.,
`harbor-notes-runtime-data`, `destructive-verbs-need-dry-run`).

The CLI places authored project rules in the same directory as the framework's builtin
rules (`.vaultspec/rules/rules/`). Project-authored rules are distinguished from
builtins by name convention: builtins use the `*.builtin.md` suffix; authored rules do
not.

## How to find an existing rule

Before authoring a new rule, check whether one already covers the intent.
`vaultspec-core spec rules list` enumerates all project-shared rules.
`vaultspec-core spec rules show <name>` prints any single rule. If an existing rule
partially covers the intent, edit it via the standard CRUD path
(`vaultspec-core spec rules edit <name>`) rather than producing a near-duplicate;
partial rules are worse than complete ones because they fragment the discipline.

## Where the rule lives, and why

Project-authored rules live under `.vaultspec/rules/rules/` alongside the framework's
builtin rules. The framework's install policy is for that directory to be tracked by git
so the rule reaches every teammate on clone.

A rule that exists only on one developer's machine is not a codification; it is a
personal note. The whole point of writing the rule down is that the next agent inherits
it on the next session, on the next teammate's clone, on the next CI run.

## When a rule itself becomes wrong

Rules age. A rule that captured a constraint last quarter may no longer hold this
quarter. Two paths:

- **Edit in place** when the constraint has shifted at the margins. The rule's name
  stays; the body changes.
- **Supersede** when the constraint has changed at the center. Author a new rule with a
  new name and add a `## Status` section to both rule bodies: the prior rule's Status
  names the successor's slug, and the new rule's Status names the rule it supersedes.
  Once teammates are aware, remove the prior rule via
  `vaultspec-core spec rules remove <name>`.

A rule should never be silently deleted. The rule's removal is itself a project-level
event; record it.

## Audit-driven codification

The framework supports an audit-first codification flow. The sequence:

- A review at the end of a feature surfaces lessons in
  `.vault/audit/yyyy-mm-dd-{feature}-audit.md`.
- One audit can produce zero, one, or many rules - most produce zero (the lesson is
  feature-specific), some produce one, and a rare audit (the kind that surfaces a
  framework-wide pattern) produces several.
- Each qualifying finding is promoted with
  `vaultspec-core vault rule promote --from <audit-stem> --as <rule-name>`; the promoted
  rule carries the audit stem in its `derived_from:` frontmatter, and the rule's **Why**
  section names the finding in prose.

Audit-driven codification is the natural follow-on to the `review` phase. The pipeline
reads as research → decide → plan → execute → review → codify, with codify as the
discretionary sixth step. Most features end at review; the features whose lessons
outlast the feature itself end at codify.

---
name: vaultspec-dry-run-discipline.builtin
trigger: always_on
---

# Dry-run discipline: preview destructive verbs before applying

A worked example of codification. Promoted from the rolling CLI UX audit's findings S4,
S14, and the gating dimension of B9.

## Rule

Before invoking any vaultspec CLI verb that writes or removes state, run the same verb
with `--dry-run` first, read the previewed change list carefully, and apply the real run
only after the preview matches your intent. `--dry-run` is the canonical preview path on
every destructive verb.

## Why

The rolling CLI UX audit's findings S4, S14, and B9 documented asymmetric gating of
destructive verbs: some lacked a preview entirely, and others previewed nothing. Those
gaps have closed: `install`, `uninstall`, `sync`,
`vaultspec-core vault feature archive`, and every plan mutator accept `--dry-run`, and
`vaultspec-core install --upgrade --dry-run` prints a populated per-file preview
(re-verified against the live CLI on 2026-06-10, `vaultspec-core --version` 0.1.26). The
discipline survives the fix: a preview only protects the operator who reads it.

## How

- **Good:** `vaultspec-core install --dry-run` against an empty directory, read the file
  list, confirm provider selection, then run `vaultspec-core install`.

- **Good:**
  `vaultspec-core vault add plan --feature my-feature --title "..." --tier L1 --related <stem> --dry-run`
  to preview the scaffolded path, frontmatter, and tier value before the file is
  created.

- **Bad:** `vaultspec-core install` in a busy repository without a preview. About
  seventy files appear, `.gitignore` is rewritten, `CLAUDE.md` is created; the cleanup
  is manual.

- If a preview is empty on a verb that should produce side effects, escalate: an empty
  preview is a finding worth logging, not a green light.

## Status

Active. The universal preview discipline this rule anticipated
(`cli-blast-radius-gating` `W04.P11`) has landed: `--dry-run` is the canonical preview
path on every destructive verb. The rule's intent (preview before apply) is now
structurally supported; the operator's remaining duty is to read the preview before
applying.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), findings S4 (round 1), S14
(round 3a), and the gating dimension of B9 (round 3b). Sibling decision ADR
`2026-05-17-cli-blast-radius-gating-adr`. Umbrella plan steps `W04.P11.S39`, `S40`,
`S41`, `S42` in `2026-05-17-cli-simplification-ux-plan`.

---
name: vaultspec-plan-editing-discipline.builtin
trigger: always_on
---

# Plan editing discipline: structure first, prose last

A worked example of codification applied to an audit finding. Promoted from the rolling
CLI UX audit (finding B6) following the discipline described in the `vaultspec-codify`
rule.

## Rule

Treat the plan as one cohesive document: route every Wave, Phase, and Step structural
mutation through the `vaultspec-core vault plan {wave,phase,step}` CLI verbs, and author
the Description, Parallelization, and Verification prose sections by direct file edit.
Prose and structure may interleave freely: the serializer preserves authored prose
blocks verbatim across structural mutations.

## Why

The rolling CLI UX audit's B6 finding documented that plan structural verbs once
silently discarded author-written prose sections, forcing a structure-first, prose-last
ordering. The fix proposed in the sibling ADR `cli-plan-body-preservation` has landed:
every structural mutation now reports "Preserved N unknown blocks", and a live
confirmation against a prose-bearing scratch plan (sentinel sentences carried through
`phase add`, `step add`, and `step check`) showed every authored sentence surviving
byte-for-byte (verified against the live CLI on 2026-06-10, `vaultspec-core --version`
0.1.26).

## How

- Prose content is preserved verbatim; prose position may reflow, because the serializer
  re-anchors blocks around the canonical structure on write. Review the diff after a
  structural verb when section ordering matters.
- Every plan mutator accepts `--dry-run` to preview the rewritten document without
  writing it.
- `--canonicalise` is the explicit opt-in that strips unknown prose blocks; never pass
  it on a plan whose prose you mean to keep.

## Status

Active. The serializer fix this rule anticipated (`cli-plan-body-preservation`
`W03.P07`) has landed and was live-confirmed on 2026-06-10: the ordering constraint is
retired, and preservation is the default with stripping behind the `--canonicalise`
opt-in. The rule's intent (treat the plan as one cohesive document; mutate structure
only through the CLI verbs) survives the fix; only the procedure changed.

## Source

Audit `2026-05-17-cli-simplification-ux-audit` (rolling), finding B6 sharp (three
reproductions). Sibling decision ADR `2026-05-17-cli-plan-body-preservation-adr`.
Umbrella plan steps `W03.P07.S23`, `S24`, `S25`, `S26` in
`2026-05-17-cli-simplification-ux-plan`.

---
name: vaultspec-rag.builtin
trigger: always_on
---

# vaultspec-rag — semantic search

Use semantic search for codebase discovery and implementation discovery. When you need
to find where or how something is done and don't know the exact name, search by meaning
instead of grepping keywords or guessing identifiers.

## Write good queries

The index is hybrid: dense embeddings match meaning, sparse vectors match exact terms,
and a cross-encoder reranks the top hits. A good query feeds both halves. So:

- Describe the concept or behavior in a short phrase - this drives the dense, semantic
  half.
- In that same phrase, name the concrete domain nouns the target code or docs would use
  - these drive the sparse, exact-match half. A query of pure natural language leaves
    the sparse half nothing to match.
- One concept per query. Narrow with filters; don't paste bare keywords or a guessed
  function name.

```
vaultspec-rag search "file lock acquired around incremental index write" --type code
vaultspec-rag search "retry policy backoff for failed webhook delivery" --type code --language python
vaultspec-rag search "decision on gpu_lock scope around forward pass" --type vault --doc-type adr
```

Code filters: `--language --path --function-name --class-name --include-path GLOB`.
Vault filters: `--doc-type --feature --date --tag`. Filters also work inline in the
query: `type:adr lang:python func:main`.

## Run the server

If the server is not running, start it:

```
vaultspec-rag server start
```

Server mode is the default backend: `server start` supervises the managed Qdrant
server and loads the GPU models. The server is the only workable backend at codebase
scale - local mode is orders of magnitude slower - so it is the assumed default, not an
opt-in. Provision the binary and models once with `vaultspec-rag install` (it fetches
torch, the models, and the Qdrant binary by default).

Local mode is a first-class explicit opt-out for small projects, CI, or air-gapped
hosts: `vaultspec-rag server start --local-only` (or `VAULTSPEC_RAG_LOCAL_ONLY=1`, or
`vaultspec-rag install --local-only` which persists the choice). It uses the on-disk
store and needs no server binary.

Check dependency readiness any time with `vaultspec-rag server doctor` (`--json` for the
machine-readable snapshot): it reports torch CUDA, model presence, and the Qdrant binary
and supervised-server state.

The running service auto-reindexes on file changes - DO NOT manually reindex during
normal work.

The same search is available through MCP as the `search_vault` and `search_codebase`
tools.

---
name: vaultspec.builtin
trigger: always_on
---

# Spec Skills

This project follows a spec driven development framework and mandates a vaultspec
pipeline of: research -> decision (ADR) -> plan -> verify (+ audit either as closeout or
pipeline start).

The workflow persists the following documents, bound by a single feature tag:

- `.vault/research/yyyy-mm-dd-<feature>-research.md`: The `<Research>` findings.

- `.vault/reference/yyyy-mm-dd-<feature>-reference.md`: A project, code, or research
  grounding `<Reference>`, useful for grounding implementation details prior to ADR
  authoring.

- `.vault/adr/yyyy-mm-dd-<feature>-adr.md`: Research-derived `<ADR>`.

- `.vault/plan/yyyy-mm-dd-<feature>-plan.md`: The `<Plan>` to execute, authored and
  managed by the vaultspec-core CLI (`vaultspec-core vault plan`).

- `.vault/exec/yyyy-mm-dd-<feature>/.../<step>.md`: The individual `<Step Record>`.

- `.vault/exec/yyyy-mm-dd-<feature>/...-summary.md`: The `<Phase Summary>`.

- `.vault/audit/yyyy-mm-dd-<feature>-audit.md`: The `<Audit>` report. A feature with
  multiple audits disambiguates each with an optional narrative infix:
  `yyyy-mm-dd-<feature>-<topic>-audit.md`.

- `.vault/index/<feature>.index.md`: The auto-generated `<Feature Index>` linking every
  document for a feature. Managed by `vaultspec-core vault feature index`; do not author
  by hand.

Use the following pipeline skills:

- `vaultspec-research`
- `vaultspec-code-research`
- `vaultspec-adr`
- `vaultspec-write`
- `vaultspec-execute`
- `vaultspec-code-review`

The following helper skills are available:

- `vaultspec-curate`
- `vaultspec-documentation`
- `vaultspec-team`
- `vaultspec-projectmanager`

## Documentation Hierarchy

The documentation trail follows a strict dependency graph. Artifacts lower in the
hierarchy should reference those above them.

- **Brainstorm** / **Research** / **Reference** (`.vault/research/`,
  `.vault/reference/`)

- **Audits** (`.vault/audit/yyyy-mm-dd-{feature}-audit.md`, optionally
  `.vault/audit/yyyy-mm-dd-{feature}-{topic}-audit.md`)

  - *Depends on:* the artifacts under review (plans, execution records, code)
  - *References:* the artifacts under review

- **Architecture Decision Records (ADR)** (`.vault/adr/`)

  - *Depends on:* brainstorm, research, audits

- **Implementation Plans** (`.vault/plan/`)

  - *Depends on:* ADRs, research, audits, (previous or related feature plans)

- **Execution Records**
  (`.vault/exec/{yyyy-mm-dd-feature}/{yyyy-mm-dd-feature-{phase}-{step}}.md`)

  - *Depends on:* Plans.
  - *References:* The Plan being executed.
  - *Location:* Inside feature-specific folder.
  - *Filename:* `{yyyy-mm-dd-feature-{phase}-{step}}.md` where `{phase}` and `{step}`
    are the canonical container identifiers (`P##`, `S##`) from the plan, zero-padded to
    a minimum of two digits. At `L1` the `{phase}` segment is omitted; at `L3`/`L4` a
    `{wave}` segment (`W##`) is prepended.
  - *Examples:*
    - L1: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-S01.md`
    - L2: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-P01-S01.md`
    - L3 / L4:
      `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-W01-P01-S01.md`

- **Summaries**
  (`.vault/exec/{yyyy-mm-dd-feature}/{yyyy-mm-dd-feature-{phase}-summary}.md`)

  - *Depends on:* Execution Records.
  - *References:* The Plan and key Artifacts produced.
  - *Location:* Inside feature-specific folder.
  - *Filename:* `{yyyy-mm-dd-feature-{phase}-summary}.md` where `{phase}` is the
    canonical Phase identifier (`P##`).
  - *Examples:*
    - L2: `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-P01-summary.md`
    - L3 / L4:
      `.vault/exec/2026-02-04-editor-demo/2026-02-04-editor-demo-W01-P01-summary.md`

- **Feature Indexes** (`.vault/index/{feature}.index.md`)

  - *Auto-generated* by `vaultspec-core vault feature index`; never authored by hand.
  - *Filename:* `{feature}.index.md` (no date prefix).
  - *Example:* `.vault/index/editor-demo.index.md`

## Must follow

- We **ALWAYS** use **Obsidian-style Wiki Links** for internal documentation.

- **Always** populate the `related:` field in the YAML frontmatter with
  `'[[wiki-links]]'` (quoted as strings).

- **Never** use relative paths (`../`) in wiki links; assume a flat namespace or
  vault-root resolution.

- **Always** check if a referenced file exists before linking (if possible).

- **Always** include the relevant `#{feature}` tag in the YAML frontmatter using the
  `tags:` field.

- **Always** use the `tags:` field (not `feature:`) as a YAML list.

- **Always** quote wiki-links in YAML: `- '[[file-name]]'`.

## Tag Taxonomy

**ALLOWED TAGS - DO NOT REMOVE - REFERENCE:** `#adr` `#audit` `#exec` `#index` `#plan`
`#reference` `#research` `#{feature}`

Every document in `.vault/` MUST include the required tag pair in the frontmatter
`tags:` field:

- **Directory Tag**: Based on the `.vault/` subfolder location (`#adr`, `#audit`,
  `#exec`, `#index`, `#plan`, `#reference`, `#research`)

- **Feature Tag**: Groups related documents across the feature lifecycle (kebab-case,
  e.g., `#editor-demo`)

**CRITICAL:** No structural tags like `#step`, `#summary`, `#phase*`, or `#design` are
allowed. Every document carries exactly one directory tag plus exactly one `#{feature}`
tag - no more, no less. Any additional tag is read as a second feature tag and fails
validation.

### Directory Tags (Required for ALL documents)

The directory tag is determined by the file's location in `.vault/`:

| Directory           | Tag          | Description                              |
| :------------------ | :----------- | :--------------------------------------- |
| `.vault/adr/`       | `#adr`       | Architecture Decision Records            |
| `.vault/audit/`     | `#audit`     | Audit reports and assessments            |
| `.vault/exec/`      | `#exec`      | Execution records (steps & summaries)    |
| `.vault/index/`     | `#index`     | Auto-generated feature indexes           |
| `.vault/plan/`      | `#plan`      | Implementation plans                     |
| `.vault/reference/` | `#reference` | Implementation references and blueprints |
| `.vault/research/`  | `#research`  | Research and brainstorming               |

### Tag Format

All documents use YAML list syntax with exactly 2 tags (one directory tag, one feature
tag):

```yaml
---
tags:
  - '#plan'
  - '#feature-name'
date: '2026-02-06'
modified: '2026-02-06'
related:
  - '[[related-file]]'
---
```

`modified:` is a CLI-maintained last-modified stamp: set equal to `date:` at scaffold,
refreshed by every mutating verb and by `vaultspec-core vault check all --fix`, parsed
leniently but rewritten to the canonical quoted `yyyy-mm-dd` form, never hand-edited.

**Examples:**

- Plan file: `tags: ['#plan', '#editor-demo']`
- ADR file: `tags: ['#adr', '#editor-demo']`
- Exec step: `tags: ['#exec', '#editor-demo']`
- Exec summary: `tags: ['#exec', '#editor-demo']`
- Research: `tags: ['#research', '#text-layout']`
- Reference: `tags: ['#reference', '#text-layout']`
- Feature index (auto-generated): `tags: ['#index', '#editor-demo']`

### Feature Tags

Feature tags use kebab-case and group all documents related to a specific feature or
work stream:

- Format: `#{feature}` (e.g., `#live-preview-blocks`, `#grid-layout`,
  `#syntax-highlighting`)

- Must be consistent across all documents in the feature's lifecycle

- Always quoted in YAML

## Placeholder Naming Conventions

Templates use curly-brace placeholders `{...}` to indicate values that must be replaced.
Follow these conventions:

### Frontmatter Placeholders

| Placeholder      | Format                | Example                   |
| :--------------- | :-------------------- | :------------------------ |
| `{feature}`      | lowercase, kebab-case | `editor-demo`             |
| `{yyyy-mm-dd}`   | lowercase, ISO 8601   | `2026-02-06`              |
| `{yyyy-mm-dd-*}` | lowercase pattern     | `2026-02-04-feature-plan` |
| `{tier}`         | uppercase enum        | `L1`, `L2`, `L3`, `L4`    |
| `modified`       | CLI-maintained stamp  | `2026-02-06`              |

### Document Body Placeholders

Container identifiers (`{wave}`, `{phase}`, `{step}`) use the canonical uppercase
zero-padded form from the plan template hint blocks. `{feature}` uses lowercase
kebab-case. Narrative placeholders (`{topic}`, `{title}`) use concise prose.

| Placeholder | Format              | Example                   |
| :---------- | :------------------ | :------------------------ |
| `{feature}` | kebab-case          | `editor-demo`             |
| `{wave}`    | uppercase canonical | `W01`, `W02`              |
| `{phase}`   | uppercase canonical | `P01`, `P02`              |
| `{step}`    | uppercase canonical | `S01`, `S02`              |
| `{topic}`   | concise prose       | `event handling`          |
| `{title}`   | concise prose       | `display map integration` |

### Machine-Filled Placeholders

A separate placeholder class is filled by the CLI, never by the author. Machine-filled
placeholders use snake_case to distinguish them from author-replaced placeholders; do
not fill or rename them by hand - scaffold the document through the owning CLI verb
instead.

| Placeholder       | Filled by                            | Value                                           |
| :---------------- | :----------------------------------- | :---------------------------------------------- |
| `{heading}`       | `vaultspec-core vault add exec`      | The originating Step row's action text          |
| `{step_id}`       | `vaultspec-core vault add exec`      | The Step's canonical identifier (`S##`)         |
| `{plan_stem}`     | `vaultspec-core vault add exec`      | The parent plan's filename stem                 |
| `{scope_block}`   | `vaultspec-core vault add exec`      | A Scope section listing the Step's scoped files |
| `{document_list}` | `vaultspec-core vault feature index` | The feature's full document list                |

### General Rules

- **YAML frontmatter**: Always lowercase, kebab-case

- **Document titles/headings**: The shipped templates are canonical for level-one
  headings. Top-level vault documents use backticks around both the `{feature}` segment
  and the narrative `{title}`, `{topic}`, or `{phase}` segment. Examples:
  `# {feature} research: {topic}` represents the literal template heading '# `{feature}`
  research: `{topic}`', and `# {feature} plan` represents '# `{feature}` plan'.
  Narrative segments should be concise prose; canonical uppercase identifiers remain
  required for `{wave}`, `{phase}`, and `{step}` identifier segments.

- **File names**: lowercase kebab-case for narrative segments (`{feature}`, `{type}`);
  canonical uppercase identifiers for `{wave}`, `{phase}`, `{step}` segments. Patterns:

  - Top-level docs: `yyyy-mm-dd-{feature}-{type}.md` (e.g.,
    `2026-02-04-editor-demo-plan.md`)

  - Exec Steps (L1): `yyyy-mm-dd-{feature}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-S01.md`)

  - Exec Steps (L2): `yyyy-mm-dd-{feature}-{phase}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-P01-S01.md`)

  - Exec Steps (L3 / L4): `yyyy-mm-dd-{feature}-{wave}-{phase}-{step}.md` (e.g.,
    `2026-02-04-editor-demo-W01-P01-S01.md`) inside `.vault/exec/yyyy-mm-dd-{feature}/`
    folder.

  - Exec Summaries (L2): `yyyy-mm-dd-{feature}-{phase}-summary.md` (e.g.,
    `2026-02-04-editor-demo-P01-summary.md`)

  - Exec Summaries (L3 / L4): `yyyy-mm-dd-{feature}-{wave}-{phase}-summary.md` (e.g.,
    `2026-02-04-editor-demo-W01-P01-summary.md`) inside the feature folder.

- **Replace ALL placeholders**: No template should be committed with `{...}`
  placeholders remaining. Run `vaultspec-core vault check all --fix` to validate and
  format documents before committing - it reconciles frontmatter, strips leftover
  template annotations, and applies markdown hygiene fixes. The dedicated
  `vaultspec-core vault check placeholders` check surfaces any `{...}` residue left in
  body prose, which must be filled in by hand or by the owning CLI verb.
</vaultspec>
