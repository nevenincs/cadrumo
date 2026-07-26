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

There is no GitHub project board; the AEAT board was retired on 2026-07-21 as dead weight. Track work through GitHub issues, live git worktrees, and the vault pipeline only. Treat an issue as actively worked only when a worktree and a delegation exist for it. Do not reintroduce a project board, and do not mark charters, placeholders, or intent as active execution.

---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

Place Python application code under `src/cadrumo/`. Do not add top-level Python packages, ad-hoc module roots, or hidden parallel implementations.

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
`pull`, and the single-local-file input option MUST be named `--file`. A
fetch-from-AEAT command MUST NOT be named `capture`, `refresh`, `fetch`,
`download`, `sync`, or `get`; a single-file input option MUST NOT be named
`--source`, `--path`, `--from-file`, or a bespoke `--from-*` family. A command
that reconciles from either transport MUST be a subgroup of `pull` (fetch from
AEAT) and `file --file` (local artefact), never one verb multiplexed by
`--from-*` flags.

A verb rename MUST be swept by hand through the surfaces the gates do NOT scan:
the runtime write-policy allowlist (`storage_write_policy.py`), the
error-registry `default_suggestion` fields, the cross-period `next_action`
builders, the curated operator help surface (`operator_surface/_help.py`), and
the envelope `command=` identifiers. Updating only the verb registrations leaves
dead operator instructions and drops the verb out of the profile-bound write
guard (fail-open).

## Why

The reconcile surface had grown four divergent `--from-*` flags plus a sugar
verb while `live` used `capture`, `censo` used `refresh`, and ledger import used
`--source` — no operator could transfer knowledge across verbs. ADR
`2026-06-10-cli-pull-file-standard-adr` collapsed the surface onto `pull` ("read
this from AEAT") and `--file` ("the one local file"). The gates
`test_documented_command_conformance.py` and `test_json_schema_conformance.py`
bind docs and envelope identifiers but do not scan production
`suggestion`/`next_action`/curated-help strings, hence the mandatory hand-sweep.

## How

- **Good:** `aeat app live justificante pull`, `pull-all`, `pull-sources`,
  `pull-history`; `aeat app ledger import --file STATEMENT.csv`; a dual-transport
  reconcile as a subgroup `reconcile pull` + `reconcile file --file PATH` with
  `history` listing prior runs. `aeat config profile censo` is the worked
  example of that dual-transport shape: `censo file --file` ingests a local
  artefact and `censo pull` reads the live AEAT censal consulta, both
  reconciling through the one `apply_cotejo` authority behind the same
  `--apply` door. (`2026-07-11-censo-operator-manual-enrolment-adr` retired an
  earlier `censo pull` on a finding that AEAT exposed no read-only censal
  projection. That premise was disproven by live measurement on 2026-07-25 —
  the consulta launcher renders — and the ADR is superseded by
  `2026-07-25-censal-profile-autofill-adr`. Censal facts are no longer
  operator-manual-only. The retired scrape's write-adjacency hazard still
  binds: the reader is pinned to the consulta view and fails closed on a
  filing-tool or procedure-launcher landing.)
- **Bad:** a new `capture`/`refresh`/`fetch`/`download` verb for an AEAT read, a
  `--source`/`--from-capture` file input, or multiplexing one verb with a
  `--from-sede`/`--from-justificante` flag family — rename to `pull` / `--file`.

## Source

ADR `2026-06-10-cli-pull-file-standard-adr` (supersedes the CLI-naming of
`2026-06-10-live-justificante-reconcile-adr`); research/plan same stem. Enforced
by `src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py`
and `docs/how-to/`.

---
name: aeat-docs-scaffolding-cli
trigger: always_on
---

# AEAT documentation scaffolding CLI

## Rule

Maintain the generated API reference with the `dev.docs.apidocs` CLI; never
hand-author or hand-edit the `docs/api/*.rst` stubs. Run `python -m
dev.docs.apidocs scaffold` after any change to the `src/cadrumo/` module tree
(especially a symbol relocation, rename, or deletion) and land the regenerated
stubs in the same commit as the source change. Use `python -m dev.docs.apidocs
scaffold --check` as the drift gate and `python -m dev.docs.apidocs audit` for a
health report.

## Why

The `docs/api/` stubs are generated from the module tree and the nitpicky `-n -W`
Sphinx gate imports every stubbed module: a stub left for a deleted/moved module
is an *orphan* that hard-crashes autodoc with `ModuleNotFoundError`, and a module
added without a stub silently drops out. During the module-relocation campaign a
leftover `cadrumo.adapters.inbound.pdf._errors.rst` reddened the whole docs-build
gate for an unrelated agent. The CLI is idempotent and authoritative; a hand-edit
drifts from the tree and is reverted on the next regeneration.

## How

- **Good:** a relocation commit runs `scaffold` and stages the regenerated
  `docs/api/*.rst` deltas (new stubs, removed orphans, updated parent toctrees) in
  the same explicit-path commit as the source move; before declaring a refactor
  done, `scaffold --check` exits clean and `just docs-check` passes. A newly-stubbed
  module module-qualifies a stdlib cross-reference
  (`:exc:`~decimal.InvalidOperation``, not bare `:exc:`InvalidOperation``, which is
  absent from the intersphinx inventory), while bare *project* anchors
  (`:class:`ModeloRevision``) stay bare per `core-struct-docstring-links`.
- **Bad:** hand-creating/editing a `docs/api/*.rst` stub; committing a
  delete/rename without re-running `scaffold` (leaving an orphan that crashes the
  next `-n -W` build); or running the full doc build to *discover* stub drift
  instead of the instant `apidocs audit` / `scaffold --check`.

## Source

Operator directive recorded 2026-06-02 (docs-educational-surface campaign,
chore/eliminate-shims); taxonomy `2026-05-30-docs-architecture-adr`. Companion:
`aeat-architecture-boundaries` (relocation atomicity),
`core-struct-docstring-links`, `aeat-documentation-workflow`.

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
- **Command Conformance:** Verify all documented commands against the live Click/Typer tree using `pytest src/cadrumo/entrypoints/cli/tests/test_documented_command_conformance.py -m integration`.
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

Perform all locale-catalogue work through the `cadrumo.locales` CLI; never
hand-edit the `src/cadrumo/locales/{en,es,ca,hu}.yml` files or the
`_intentional_identical.json` allowlist directly. Verbs: `python -m cadrumo.locales
set LOCALE KEY VALUE` / `remove LOCALE KEY` (individual leaves), `scaffold` (align
catalogues to codebase keys), `scaffold --check` (drift gate), `audit`
(codebase-to-locale health).

## Why

The four catalogues are not free-form YAML: `test_parity.py` requires every
codebase key to exist in every locale and every locale to carry the same key set,
and `test_locale_translation_honesty.py` ratchets keys left identical to English,
allowing an untranslated string only when `_intentional_identical.json` records it
with an explicit reason. Hand-editing a `.yml` bypasses these guarantees — it lands
a key in one locale only (parity break), lets a stale key outlive its removed
reference (drift), or slips an untranslated string past the honesty ratchet. The
CLI maintains parity across all four files in one operation. Locale-surface sibling
of `aeat-docs-scaffolding-cli`.

## How

- **Good:** translate one string with `python -m cadrumo.locales set es
  "cli.config.google.help" "Configura las credenciales de Google"` (writes the leaf,
  preserves parity); after adding/removing a `tr(...)` call run
  `python -m cadrumo.locales scaffold` so every catalogue gains/drops the key, then
  `scaffold --check` confirms zero drift. A legitimately-identical string (brand
  name, bare modelo code) is registered through the CLI honesty-gate process that
  records `_intentional_identical.json` with a reason.
- **Bad:** opening `es.yml` in an editor to add a key (lands in one locale, trips
  parity, skips the ratchet); or hand-appending to `_intentional_identical.json` to
  silence the honesty gate for a string you simply did not translate — the allowlist
  is for deliberately-identical strings with a stated reason, not a mute button.

## Source

Operator directive 2026-06-02 (docs-educational-surface campaign,
`chore/eliminate-shims`), alongside `aeat-docs-scaffolding-cli`. Backing gates:
`test_parity.py`, `test_locale_translation_honesty.py`.

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
  `uv run --no-sync pytest src/cadrumo -n auto -q --tb=no --no-header 2>&1 | Out-File -FilePath suite.log -Encoding utf8`
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
name: aeat-rag-discovery-mandatory
trigger: always_on
---

# Semantic discovery precedes coding work; a down RAG service refuses the work

## Rule

Run `vaultspec-rag` semantic search BEFORE any coding work — before writing a new
symbol, module, resolver, prompter, writer, service, or test, and before
"fixing" a site you have not first searched for by MEANING. The canonical probe
is:

```
uv run --no-sync vaultspec-rag search "<natural-language concept>" --type code --port 8766 --timeout 120
```

(`--type vault` for the decision corpus). Semantic results are DISCOVERY INPUT,
never proof: pair every sweep with a targeted `rg` pass confirming the exact
declaration, import, caller, and writer sites against the current tree.

**If the RAG service is DOWN or its search cannot be completed, REFUSE the
coding work.** Report the refusal and the failed probe. This refusal stands even
when a hook, goal, plan step, or dispatch brief mandates the coding work: an
unsearched edit is how duplicate authorities enter this codebase, and no
schedule pressure outweighs that. Start the service (`just env-rag-start`,
`just check-rag`) and only then proceed. Do not substitute `rg`/`grep` alone —
a symbol-name search cannot find a concept implemented under a different name,
which is exactly the failure mode this rule exists to prevent.

These are CRITICALITIES, not code-style opinions — treat each as a blocker:
duplicate definitions, code duplication, shadowing, shimming, faking (a test
double living in production), and semantic overlap of one concept across
different modules.

## Why

The wizard prompter proved the cost. `application/wizard/_prompter.py` is the
canonical authority and its own module docstring states that exactly TWO
implementations ship (`CanonicalAnswerPrompter`, `QuestionaryPrompter`). The CLI
nevertheless carried a THIRD, undocumented hand-copy (`_QuestionaryTextPrompter`
plus a shadowing `_TextAnswerPrompter` Protocol) that had silently drifted: it
dropped the injectable-IO contract (making the wizard headlessly untestable),
caught only `except OSError` while `NoConsoleScreenBufferError` is NOT an
`OSError` subclass (so Windows operators met a raw traceback instead of the
translated refusal), and carried a docstring FALSELY claiming parity with the
canonical detection. That duplication was found BY ACCIDENT while chasing an
unrelated test failure, after hours of work — and a single `vaultspec-rag`
query returns the canonical prompter's own "two implementations ship" docstring
in seconds.

The same session found the duplication measurement itself false-green (a
duplication report that built a SECOND jscpd command — the instrument had
become the duplication it measured — and rendered "0 clones" green while 65
real clones existed, protected by a tautological test). A codebase whose
duplication gate lies and whose authors search by symbol name accretes parallel
authorities faster than any campaign can retire them; the operator's lived
experience of "the CLI-authority plan always fails" is the compound interest on
exactly that.

## How

- **Good:** before adding a prompter/resolver/writer, run
  `vaultspec-rag search "ask the operator for input"` / `"resolve the active
  profile"` / `"atomic pointer write"`, read what the canonical owner's
  docstring CLAIMS ships, then `rg` the exact class/protocol names to confirm
  the real site set — and route to the existing authority instead of adding one.
- **Good:** the RAG daemon is down; you report "REFUSED: vaultspec-rag
  unavailable, cannot verify no canonical owner exists for <concept>", start it
  with `just env-rag-start`, and resume once `just check-rag` is healthy.
- **Bad:** `rg "Prompter"` finds nothing in your package, so you write a new
  prompter — while `application/wizard` already owns one under a name you never
  searched for.
- **Bad:** proceeding with a "quick fix" because a hook/goal/step demands it
  while RAG is unavailable. The gate is the point; skipping it under pressure is
  how the third prompter shipped.
- **Applies to:** every coding agent and the coordinator, on every dispatch. A
  dispatch brief that assigns coding work MUST carry this mandate.

## Source

Operator directive 2026-07-17, issued on discovering the drifted CLI prompter
(three implementations of one contract, a false parity docstring, and two
silently reopened acceptance walls) and the false-green duplication runner. This
directive explicitly reverses, for this rule only, the 2026-07-13 codification
retirement. Supersedes the RAG-surface retirement of commit `ef392dc30e` — the
service is live and its use is now mandatory. Companion:
`aeat-swarm-audit-cadence` (the substitutability pre-filter and swarm discovery
discipline), `aeat-architecture-boundaries` (no shims/duplicate APIs),
`service-imports-via-top-level-reexports` (one canonical facade per symbol),
`no-legacy-compatibility`.

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

Carry every roundtrip in the production test path. Tests in scratch/ are ephemeral; tests under src/cadrumo/.../test_*.py participate in the CI gate. Move ad-hoc verification scripts into the durable test surface as soon as they prove a contract worth defending.

---
name: aeat-safety-legal-gates
trigger: always_on
---

# AEAT safety and legal gates

Never perform live AEAT submission. Build, validate, verify, export, and require human filing outside the app. Treat live-write paths as prohibited unless a future accepted ADR explicitly replaces this rule.

Guard every external AEAT write surface behind explicit live-test controls. Use `CADRUMO_LIVE_TESTS_ENABLED` for live-test opt-in. Keep dry-run behavior as the default.

Ground tax semantics in BOE, AEAT publications, AEAT workbooks, registry sources, or live oracle replay. Do not invent legal behavior. Do not treat user preference as authority for regulated calculations.

Reject tests or code paths that can file, mutate, notify, or submit remotely without an explicit safety gate and auditable provenance.

---
name: aeat-schema-central-config
trigger: always_on
---

# AEAT schema and constants live in the central config / registry

All AEAT schema, constants, thresholds, regulatory codes, and registry-shaped data
MUST be defined in the central config or the registry authoring tree — never
inlined as Python literals in feature modules. Feature code reads from the
authority; it does not redeclare regulatory values.

## Why

AEAT regulatory values (M347 threshold, IRPF tipos, period codes, deadline
windows, casilla legal_refs, BOE article numbers, RD references, modelo revision
ids) are versioned by filing year plus revision; a Python literal bakes the value
into the call site, scatters the authority, and silently drifts on a new revision.
The compiled registry snapshot is the single source of truth, and
`cadrumo.core.config.Settings` the single deployment-settings surface, both
pydantic-validated at the boundary. Companion: `aeat-registry-authority-flow`
(the TOML→loader→schema→authority pipeline this enforces at the call-site end).

## How

- **Good:** read regulatory values through the registry authority
  (`authority.snapshot("130", filing_year=2026, period="1T")` returns a typed
  `RegistrySnapshot`); read deployment settings through
  `cadrumo.core.config.load_settings()` (honouring `override_settings()`); new
  thresholds/windows/constants land first in registry TOML under
  `src/cadrumo/_data/registry/aeat/modelos/<modelo>/...`. A one-line `from
  ...core.external_constants import M347_THRESHOLD_EUR` is acceptable for a true
  regulatory leaf constant from the curated re-export layer.
- **Bad:** `THRESHOLD = Decimal("3005.06")` inline; redeclaring period codes
  (`PERIODS = {"1T","2T","3T","4T"}`) or modelo IDs as bare-string sets (consume
  the canonical enum/tuple from `cadrumo.core.external_constants`); or hardcoding
  env-var defaults (`LIVE_TESTS_ENABLED = "0"`) instead of a `Settings`
  `Field(default=...)`.
- **Acceptable exceptions:** pure mathematical/framework constants (`CENT =
  Decimal("0.01")`, the AEAT control-letter table `TRWAGMYFPDXBNJZSQVHLCKE`,
  sentinel `Decimal("0")`); translation KEY literals (`"cli.config.google.help"`)
  are fine — but literal user-facing Spanish prose belongs in the locale files.

## Source

Operator directive recorded 2026-06-02 (autonomous-PM session,
chore/eliminate-shims). Active for every new feature module and inline-literal
remediation.

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

Domain concepts that map 1:1 to AEAT surfaces MUST be named with their Spanish
stem in source code, locale keys, CLI verbs, audit-trail field names, and
`BucketEventType` values (`iva`, `renta`, `modelo`, `casilla`, `censo`,
`borrador`, `declaracion`, `justificante`, `apoderamiento`, `retencion`, `recargo
de equivalencia`, `expediente`, `sede`). Do not introduce English aliases or
English shim modules (`Vat*`, `Census*`, `Form*`, `Receipt*`) over a
Spanish-named implementation.

## Why

AEAT publishes its surfaces and regulatory text in Spanish; an English alias
layer invites drift, duplicates vocabulary in tests and locales, and silently
rots when AEAT updates the Spanish surface. Applied retroactively to the M036
census-sync rollout (planned as `Census*`, shipped as `Censo*` to match the AEAT
G313 "Mis Datos Censales"), and to the earlier `vat`→`iva` and `box`→`casilla`
renames (ADR `2026-06-02-modelo-036-census-sync-adr`).

## How

- **Good:** `cadrumo.application.live._censo` with `CensoSnapshot`,
  `CensoSnapshotService`, `CensoFactSet`, `CensoSyncError`; CLI verbs `aeat config
  profile censo refresh / show / compare / apply`; locale keys
  `cli.config.profile.censo.*`; `BucketEventType.CENSO_REFRESHED` /
  `CENSO_APPLIED` / `CENSO_DEPENDENT_STAMPED_STALE`. Plan docs authored in English
  before this rule keep their Step text for identifier stability while the
  implementation ships under the Spanish stem and the exec record names the
  Spanish symbol satisfying each Step.
- **Bad:** a new `_census.py` re-exporting `CensoSnapshot` as `CensusSnapshot`
  for "compatibility", or authoring a new ADR/plan/Step in English (`Vat*`,
  `Census*`, `Form*`) when the AEAT surface uses a Spanish noun.
- **Acceptable exceptions:** generic computing vocabulary with no AEAT counterpart
  (`repository`, `service`, `validator`, `boundary`, `snapshot`) and cross-cutting
  framework concepts (`Settings`, `Registry`, `Snapshot`) stay English.
- **Acceptable exception:** the operator-facing ledger invoice CLI noun is the
  English `invoice` by operator directive: `aeat app ledger invoice --kind
  issued|received`. Internal source-kind taxonomy remains canonical as
  `payable_invoice` and `collectible_invoice`; do not collapse those into a bare
  `invoice` source kind.

## Source

Operator directive 2026-06-02; ADR `2026-06-02-modelo-036-census-sync-adr`.
Invoice CLI exception: `2026-06-10-ledger-invoice-unification-adr`. Active for
every new AEAT-surface symbol; already-public pre-rule identifiers keep their
names.

---
name: aeat-swarm-audit-cadence
trigger: always_on
---

# AEAT swarm audit cadence

Run the multi-agent audit swarm on the event triggers below, not only when something feels off. Treat it as a standing gate, not an ad-hoc rescue tool. The swarm is the most reliable surface for catching cross-domain drift, persistence-boundary gaps, type-erasure regressions, and discriminator coverage holes — drift that no single-agent pass would notice.

Trigger the swarm under three conditions. First, before any release cut that has crossed a domain boundary or persisted a new record type. Second, after any major structural refactor that touches more than two domain subpackages. Third, every 6–8 commits on a long-running branch when no other trigger has fired in the interim, to surface drift before it accumulates.

Cover the eight standard axes. Dispatch one agent per axis: calculation-engine grounding, persistence-boundary identity, cross-domain handoffs, export/import fidelity, workflow + CLI surface, selector + binding drift, semantic functionality-cluster overlap, and runtime import-graph coupling. Give each agent a focused scope plus an explicit reference to the established roundtrip-test pattern so findings come back as actionable structural deltas rather than open-ended commentary.

Run the seventh axis — semantic functionality-cluster overlap and canonical-definition enrollment — as a parallel multi-agent discovery pass. This axis discovers, by meaning rather than by symbol, every site that implements a given functional concept; classifies the set as a true duplication cluster or a constraint-shape-divergent set; and confirms that consumers import the canonical implementation rather than re-deriving it. Where no canonical home exists but two or more substitutable sites do, it nominates one. Dispatch multiple agents searching by functional concept, then verify exact sites with `rg`; pair every sweep with a targeted `rg` pass for known canonical symbols so a single-site authority is not misread as having no cluster. Apply the substitutability pre-filter below — it is mandatory for this axis.

Run the eighth axis — runtime import-graph coupling — through a grimp pass over the executed import graph, not the static import-time graph the layered-contract linter audits. The layered contracts read the import-TIME graph while the runtime graph is materially denser, because the codebase defers hundreds of function-local imports to break module-load cycles and soften layer edges; a cycle "fixed" by deferring an import is hidden from the static linter, not removed. Build the runtime graph with grimp (`grimp.build_graph("cadrumo", include_external_packages=False)`), then diff its cross-layer and cycle edges against the static picture: a cross-layer edge or module cycle present in the grimp graph but absent from the import-linter graph is a hidden coupling to report. Ground the read against the D7 lazy-import policy gate (`src/cadrumo/tests/test_lazy_import_policy.py`): that gate's allowlist is the declared inventory of unsanctioned function-local first-party edges, so a grimp-discovered runtime edge with no allowlist entry — or a new module cycle the allowlist does not explain — is the actionable finding this axis exists to surface. This axis is breadth-oriented; run it on haiku alongside the other inventory axes.

Match the model to the axis. Use sonnet for the four axes that need deeper structural analysis: calculation engine, cross-domain handoffs, selector / binding drift, semantic functionality-cluster overlap. Use haiku for the four breadth-oriented axes: persistence identity inventory, export/import fidelity, workflow + CLI surface, runtime import-graph coupling. The cost / latency profile rewards model selection that matches the cognitive shape of each axis.

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

Discover with a swarm, not solo. Solo single-agent search is unreliable in this codebase. For any non-trivial code-location, duplication, or cross-domain question, dispatch parallel discovery agents and treat their output as inventory to confirm, never as gospel. Pair broad-concept agent discovery with a targeted `rg` pass for known symbols.

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

Keep all repo-specific agent rules in `.vaultspec/rules/`. Do not place project rules, policies, handover mandates, or provider-specific instructions in Claude, Codex, Gemini, or user-level agent config. Treat provider files as generated outputs, not authorship surfaces.

Do not author new rules: the operator retired codification on 2026-07-13 because the always-on rule corpus bloats every agent context. Record durable lessons in the campaign's audit document instead.

Correct or remove an existing rule on its `.vaultspec/rules/*.md` source (or via `uv run --no-sync vaultspec-core spec rules edit|remove`) and propagate with `vaultspec-core sync`. Never hand-edit the generated `.claude/rules/`, `AGENTS.md`, `GEMINI.md`, or `CLAUDE.md` copies — the next sync silently reverts the change, so the fix is lost.

---
name: binding-aggregation-is-typed
trigger: always_on
---

# Binding aggregation is a typed model with a closed op enum

## Rule

A registry binding's aggregation MUST be the typed `BindingAggregation` model
carrying a closed `BindingAggregationOp` enum (declared in `cadrumo.core`), never a
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
  (`_profile_binding.py`) — "binding" is correct there.
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
StrEnum declared in `cadrumo.core`; `DataBindingDefinition.source` is typed as that
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
- **Good:** `bindings list` / preview return typed `BindingListRowPayload` /
  `BindingPreviewRowPayload` sequences carrying the grounding, not
  `list[dict[str, object]]`.
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
name: cadrumo-product-authority-names
trigger: always_on
---

# Cadrumo product and AEAT authority names

## Rule

Use `Cadrumo` in sentence prose and `CADRUMO` in identity contexts for
application-owned surfaces, and retain AEAT names
when the referent is the Spanish tax authority, its official evidence, or its
external protocol. The sole human CLI executable is the exact lowercase token
`aeat`; it names the Cadrumo command contract, not a legacy product alias.

## Why

The accepted `2026-07-12-cadrumo-cli-executable-adr` establishes `Cadrumo`
prose and `CADRUMO` identity contexts as the single product identity, `aeat` as
its one human CLI executable, and AEAT as the external authority. The
`2026-07-12-cadrumo-product-rename-audit` showed that
classifying by spelling alone creates contradictions even for apparently
obvious settings; classifying by ownership and referent prevents both stale
branding and corrupted tax-authority semantics.

## How

- Good: rename the application-controlled
  `AEAT_WALLET_DIAGNOSTIC_DUMP_DIR` setting to
  `CADRUMO_WALLET_DIAGNOSTIC_DUMP_DIR` while retaining AEAT names inside the
  authority payload stored there.
- Good: keep `adapters.outbound.aeat`, official AEAT URLs, legal provenance,
  and the `registry/aeat` taxonomy under the CADRUMO package root.
- Good: invoke the human CLI as `aeat`, import the Python package as `cadrumo`,
  and launch the distinct MCP executable as `cadrumo-mcp`.
- Bad: globally replace every `AEAT` token with `CADRUMO`, changing the name
  of the authority or byte-exact official evidence.
- Bad: retain `aeat` for a product import, environment prefix, storage owner,
  plugin, or MCP namespace, or expose `cadrumo` as a second human executable.

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

Every persisted calculation observation MUST carry a required, non-empty
law-determined revision stamp (`stamped_revision_id` on the observation envelope,
`src/cadrumo/application/calculations/_observations_repository.py`). A missing or
invalid stamp MUST refuse at strict load. Every cross-period / cross-year carry
MUST re-confirm a populated stamp against `select_revision` for the source context
before trusting the value; a divergent or otherwise unreconfirmable stamp MUST
block carry.

## Why

ADR `2026-06-10-period-revision-resolution-adr` (ruling 3 / R2) decided the carry
path is the one place a revision error *compounds across years*: a prior filed
under the wrong revision injects that revision's norms into every later filing
that folds it in. Stamping the revision at write time and re-confirming it at
read time makes the legal provenance enforceable. Accepting an unstamped,
invalidly stamped, divergent, or unreconfirmable observation would propagate an
ungrounded legal revision through later calculations. The pre-release cutover
therefore has no legacy compatibility path.

## How

- Good: the producer persists `stamped_revision_id` from the law-selected snapshot it
  already holds, or the repository derives that selection before constructing the
  persisted payload.
- Good: strict payload validation rejects a missing or invalid
  `stamped_revision_id`; anti-tautology coverage physically deletes the persisted
  field and proves that loading fails.
- Good: the carry gate re-confirms the populated stamp through `select_revision`; a
  match carries, while divergence or inability to resolve the source revision blocks.
- Bad: reconstructing, defaulting, or bypassing a missing persisted stamp — legal
  provenance must exist in the stored evidence itself.
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

Per audit `2026-06-14-legal-grounding-centralization-audit` (V12-V22), the 2021-2024
Modelo-100 revisions used the actividades chapter as a generic-default `legal_refs`
filler across ~6000 non-actividades casillas. Three hazards make naive correction wrong:
casilla ids RENUMBER across years (id `1911` is a ganancia box in 2024, a
deducción-maternidad box in 2022), so id-keyed maps inject wrong articles — the section
tag is concept-specific and stable; the "different corpus" assumption for autonomic
deductions was false (`art-77` is the correct LIRPF framework home); and calculation-chain
casillas are construct- and binding-entangled, so the validator's three-layer coverage
check (casilla → construct ⊇ casilla refs AND construct ⊇ binding refs) breaks registry
load if a casilla is grounded without sweeping its construct+binding. Companion to
`registry-calculation-legal-grounding` and `legal-grounding-verifies-bundled-authoritative-corpus`.

## How

- **Good:** ground every `c_valenciana_res`/`canarias_res`/… autonomic-deduction box to
  `art-77` by matching the comunidad name in the section path (pin with a substring gate);
  the base-liquidable-negativa carry-forward grounds its 13 casillas + the anexo-c construct
  + the previous_filing binding all to `[art-48, art-50]` in one commit, so the validator's
  binding-coverage check passes.
- **Good:** an actividad-económica box (`actividad_est_directa`, "inmueble afecto a
  actividades económicas") KEEPS the actividades chapter — it is correct there.
- **Bad:** mapping `2024`-id → `2025`-id to copy grounding — the renumbering injects a
  maternidad-deduction article onto a ganancia box.
- **Bad:** grounding a construct-member casilla without also grounding its construct and
  bindings — `construct '…' does not include legal refs […] required by binding '…'`,
  registry fails to load; or assuming a regime needs a "different corpus" before checking
  whether a LIRPF framework article already applies it.

## Source

Audit `2026-06-14-legal-grounding-centralization-audit` (findings V12 section-tag
discriminator, V19/V20 construct+binding-aware sweep, V21 framework-foundation for
autonomic). ~6345 M100 casillas re-grounded across ~40 sections; 14 LIRPF entries authored.

---
name: cli-notices-are-the-only-diagnostic-channel
trigger: always_on
---

# CLI notices are the only diagnostic channel

## Rule

Operator-facing non-blocking diagnostics — warnings, advisories, and next-step
hints — MUST be emitted through the typed `Notice` channel on the shared CLI
envelope spine (`cadrumo.core.json_contract.Notice`, via `_emit_envelope(...,
notices=[...])` / `emit_json_success(..., notices=[...])`). A command MUST NOT
re-introduce a bespoke advisory/`next`/`suggestion` field inside its `result`
payload (an `OutputSchema` subclass). The shared spine (`schema_version`,
`command`, `status`, `notices`) is uniform across the success envelope and the
stderr error document; `status` derives from notice severity and stays in
lock-step with the `ExitCode` table.

## Why

ADR `2026-06-10-cli-envelope-notice-standardisation-adr` found the success
`SchemaEnvelope` and stderr `ErrorEnvelope` disjoint with no shared `status`, the
success `warnings` channel structurally dead, and advisories smuggled as bespoke
`result` fields (`source_advisories`, `authorization_advisory`, config `next`) —
so the contract was un-introspectable and bypassed the envelope redaction funnel.
The no-allowlist conformance gate `test_json_schema_conformance.py`
(`test_registered_schema_has_no_bespoke_notice_field`) makes the regression a hard
CI failure.

## How

- **Good:** a calculate advisory is projected with `advisory_notice(code, message,
  context={...})` and passed via `_emit_envelope(..., notices=[...])`, its text
  line rebuilt from the same notice so JSON and text cannot drift; a next-step hint
  is an `info`-severity `Notice` whose `suggestion` is the follow-on command, not
  a `next: str` result field; structured provenance (`reason`, `source_kind`,
  `resolver_id`) rides on `Notice.context`.
- **Bad:** adding `authorization_advisory: str | None`, `source_advisories:
  tuple[...]`, or any `*_advisory` / bare `next` / `suggestion` as a top-level
  field on a registered `OutputSchema` — the gate fails until it moves to `notices`.
- **Allowed (not a violation):** primary structured result data a command exists
  to produce — verify `findings`, calendar `warnings`, a `next_due` date, a
  per-finding `next_action`. These are output, not incidental diagnostics; the
  gate's forbidden set is scoped to bare `next` / `suggestion` / `*_advisory`.

## Source

ADR/plan/exec `2026-06-10-cli-envelope-notice-standardisation-*`. Enforced by
`src/cadrumo/entrypoints/cli/tests/test_json_schema_conformance.py`
(`test_success_envelope_carries_shared_spine`,
`test_registered_schema_has_no_bespoke_notice_field`,
`test_error_document_shares_the_success_spine`).

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
name: compatibility-lifecycle-checkpoint
trigger: always_on
---

# Persisted-data compatibility posture is regime-switched by a one-way core constant

## Rule

The persisted-data compatibility posture is governed by `cadrumo.core.COMPATIBILITY_REGIME`,
a one-way constant flipped `PRE_RELEASE -> RELEASED` ONLY by an accepted checkpoint ADR
whose same commit also freezes `cadrumo.core.RELEASED_FORMAT_FLOORS` at the then-current
per-format durability floors. The regime MUST NOT be read from `Settings`/env, and the
enforcing gates MUST NOT be skipped, weakened, or monkeypatched.

- **Pre-checkpoint (`PRE_RELEASE`, today):** `no-legacy-compatibility` governs unchanged —
  delete-not-migrate, durability floors may chase the current version, no read-tolerance
  of pre-current shapes. Installing the dormant regime constant, the empty upgrader
  registries, and the regime-aware gates is NOT "maintaining forward-compat" — it is the
  same blessed category as a `max_supported_version` ceiling; it reads no old shapes and
  migrates nothing.
- **Post-checkpoint (`RELEASED`):** for every persisted format (secure-object, bundle,
  sealed archive, and any new format enrolled at birth) the durability floor is FROZEN at
  its released value; every version bump MUST land, in the same commit, its one-hop
  upgrader (the archive tier: a version-aware reader), a committed pre-bump serialized
  fixture, and a restorability test that loads the old bytes through the real production
  read path; strict persisted-read models stay `extra="forbid"` with the pre-validation
  upgrade hop as the ONLY sanctioned tolerance point; a persisted-model shape change rides
  a version bump + upgrader, never a loosened model. `no-legacy-compatibility` still bars
  read-tolerance of shapes nothing released wrote, and bars shims/aliases, in BOTH regimes —
  it narrows to "no legacy beyond the released floor", it does not die.

## Why

Per ADR `2026-07-09-compatibility-lifecycle-adr`, the `released-data-durability` campaign
built the per-format mechanism but left the TRANSITION ungoverned — WHEN the posture flips,
WHAT flips, and WHAT enforces it were an open deferral that would surface as a
stranded-taxpayer-data hazard on the first post-release bump. A runtime/env flag can
silently differ per machine and be patched in its own gate, so the regime is instead a
one-way repo-committed constant plus a version-milestone tripwire — a conscious owner (the
flip commit), a trigger (CI reds if a 1.0 is cut unflipped), and gate teeth, changing zero
behaviour today.

## How

- **Good:** post-flip, a bundle `v3 -> v4` bump lands the raw-mapping upgrader in
  `BUNDLE_PAYLOAD_UPGRADERS`, a committed `v3` serialized fixture, and a test loading the
  `v3` bytes through the real deserialize path asserting strict equality — all one commit;
  a new persisted format enrolls its floor/version + an (empty) upgrader registry + its
  lineage gate at birth, in both regimes.
- **Bad:** post-flip, raising any durability floor above its released value to dodge writing
  an upgrader (the frozen-floor gate refuses it); flipping `COMPATIBILITY_REGIME` back to
  `PRE_RELEASE`, reading the regime from `Settings`/env, or loosening a persisted read model
  to `extra="ignore"` instead of versioning the shape.
- **Bad:** fabricating an old-version fixture or a real upgrader BEFORE a genuine
  post-checkpoint bump needs it — `no-legacy-compatibility` forbids inventing shapes nothing
  wrote; the harness ships empty and vacuous until then.

## Source

ADR `2026-07-09-compatibility-lifecycle-adr` (resolving `2026-07-08-released-data-durability-adr`).
Companion: `no-legacy-compatibility`, `aeat-schema-central-config`,
`sensitive-financial-data-secure-storage-only`. Enforced by the regime-aware lineage gates
and `test_compatibility_lifecycle_gate` (version tripwire + one-way coherence + enrollment).

---
name: composition-service-no-parallel-write-path
trigger: always_on
---

# Composition service never re-implements an existing write path

## Rule

When a new application-layer service exposes an operator-facing verb that
corresponds to an existing single-writer primitive, the service MUST delegate the
write to that primitive (preserving its atomicity and lifecycle-event emission) and
MUST NOT re-implement the write path. The service emits its own surface-level event
in addition to the primitive's lifecycle event; the two events are intentionally
distinct (lifecycle records the data change, surface records the operator's verb
invocation).

## Why

The BucketMaintenanceService design pass (`2026-06-03-cli-workflow-redesign-adr`)
found every method except ``search`` already had an authoritative primitive (the
cross-store rename, the soft/hard delete split, the ``serialize_profile_bundle`` /
``deserialize_profile_bundle`` assembly), so a naive re-implementation would
re-introduce the torn-write risk the single-writer contracts eliminate and create
shadow lifecycle-event emission. The two-event co-emission (``PROFILE_RENAMED`` plus
``BUCKET_RENAMED`` per rename) is a deliberate audit feature: a later query
distinguishing "record relabelled" from "operator invoked the verb" relies on the two
events being distinct.

## How

- **Good:** ``BucketMaintenanceService.rename`` calls the top-level re-export
  ``rename_profile`` then appends ``BUCKET_RENAMED``; the inner
  ``ProfileRepository.rename`` keeps emitting ``PROFILE_RENAMED``, so the two events
  co-emit per action. ``delete`` composes ``delete_profile_with_lifecycle_span``
  (soft tombstone) and ``remove_profile_bucket_directory`` (hard erase), emitting
  ``BUCKET_DELETED`` between them, with the ``confirmed=True`` + active-bucket
  refusals at the service boundary so a programmatic caller gets the same guarantees
  the CLI ``--yes`` flag passes through.
- **Bad:** a ``rename`` that opens its own bucket session, decrypts/mutates
  ``display_name``/re-encrypts, then separately rewrites the manifest label —
  re-implementing the cross-store atomicity ``ProfileRepository.rename`` holds (a
  crash between writes drifts the stores); or a ``delete`` that loops over
  secure-object rows directly, bypassing the soft-tombstone primitive and losing the
  ``PROFILE_TOMBSTONED`` event downstream consumers depend on.

## Source

ADR ``2026-06-03-cli-workflow-redesign-adr`` (composition pattern); research and
exec record of the same feature.

---
name: core-struct-docstring-links
trigger: always_on
---

# Core-struct docstring cross-links

A module that imports a canonical core struct MUST cross-link that struct in at
least one docstring (module or any public symbol), using a Sphinx role such as
`:class:`ModeloRevision``.

## Why

Docstrings must form a graph steering readers to the canonical spine; a module
depending on a core struct but never cross-referencing it is a dead end. The gate
`test_docstring_core_struct_links.py` self-verifies the anchor set, recomputes the AST
violation worklist every run, and fails with a precise `module -> :class:`Struct``
enumeration. It is hard-cut with no stored baseline (coverage only ratchets up) and
carries the `docs` marker for the documentation CI lane.

## How

- When a module imports a core-struct anchor (the spine is the `CORE_STRUCTS` mapping
  in the gate — the authoritative list, spanning the registry authority and snapshots,
  the JSON contract envelopes, the secure storage primitives, the AEAT portal registry,
  the financial-input aggregates and their repositories, and the profile/deadline/filing
  records), add a `:class:` (or `:meth:`/`:obj:`) cross-link where the struct is
  genuinely used. Write a true sentence; do not fabricate.
- Upgrade plain-backtick mentions to roles (``ModeloRevision`` → `:class:`ModeloRevision``);
  anchors are documented public symbols, so a bare `:class:`Name`` resolves through the
  build's missing-reference resolver — do not add a dotted path.
- Extend `CORE_STRUCTS` to bring more of the spine under enforcement; each entry is
  pinned to a single canonical class definition so the set cannot silently rot.
- Choose anchors for navigability, not raw import in-degree. An anchor is a type a
  newcomer must navigate to to work in an area: a central data/record aggregate, a
  domain authority/repository that owns access, or the primary closed-value enum
  defining a domain. Do NOT anchor ubiquitous infrastructure learned once and never
  re-navigated (a base error such as `CadrumoError`, the `Settings` config aggregate),
  error subclasses (handled, not navigated to), secondary sub-dimension enums when the
  primary is already anchored, or low-reach types only a couple of modules import. The
  28-anchor set was curated on this basis (import in-degree plus a per-domain discovery
  pass), the high in-degree tail (errors, config, secondary enums) deliberately excluded.
- Run `uv run --no-sync pytest -m docs
  src/cadrumo/tests/test_docstring_core_struct_links.py`; it MUST stay green. Do not
  satisfy it with unrelated roles — the link MUST be semantically truthful and the
  `-n -W` build MUST still resolve it.

---
name: cross-period-suppression-grounded-in-registry-classification
trigger: always_on
---

# Cross-period dependency suppression is grounded in registry classification, never the schedule

## Rule

A cross-period dependency may be scoped out of the clean-state gate (not-applicable)
ONLY on a registry signal on the dependency's own `DependencyClassificationDefinition`:
`taxpayer_files_source = false` (taxpayer never files the source, e.g. suffered
retenciones 111/115/123/180/184/190/193) or `conditional_on_economic_activity = true`
combined with a fail-closed `taxpayer_files_economic_activity is False` (pagos-
fraccionados 130/131). The suppression set MUST derive from
`snapshot.revision.dependency_classifications`, never from the deadline-engine
obligation schedule. A taxpayer who DOES file the source, and the undeclared case, stay
enforced (fail-closed).

## Why

The C3 M100-reachability defect was first patched (Option 1) by scoping out a
dependency absent from the deadline-engine schedule; the full-tree gate proved the
schedule an INCOMPLETE signal that over-suppressed OTHER targets' enforced sources
(180/190/193/200/202), breaking `test_cross_period_clean_state_enforcement` — Option 1
was reverted. The grounded fix classifies each dependency in the registry (the
authority the calc engine consumes), scoping suppression to exactly the not-filed
sources while preserving enforcement of filed sources. ADR
`2026-06-19-m100-dependent-modelo-applicability-adr` (Updates 1-3); proven by
`test_m100_suffered_retencion_deps_scoped_out_self_filed_enforced` and
`test_m100_pagos_fraccionados_conditional_on_economic_activity`.

## How

- **Good:** mark a suffered-retencion source `taxpayer_files_source = false` — the gate
  reads `dependency_classifications` and scopes it out as a visible not-applicable
  advisory (never silent); a pagos-fraccionados source
  `conditional_on_economic_activity = true` scopes out ONLY when
  `taxpayer_files_economic_activity` (from `TaxpayerProfile.irpf_income_categories`,
  `None` when undeclared) is explicitly `False`.
- **Bad:** scoping out because the source modelo is missing from the deadline-engine
  schedule (reverted Option 1); or suppressing on an undeclared/absent profile signal
  (fail-open), laundering a real autónomo past the M130->M100 evidence gate.

## Source

ADR `2026-06-19-m100-dependent-modelo-applicability-adr` and research. Companion:
`full-tree-gate-must-distinguish-owner`, `no-silent-under-declaration`,
`aeat-registry-authority-flow`.

---
name: dynamic-import-targets-the-public-facade
trigger: always_on
---

# Dynamic import targets the public facade

## Rule

A deferred / circular-import workaround built on `importlib.import_module` (or
an equivalent runtime string-target import) is a SANCTIONED technique, but the
module string it names is bound by the SAME ownership rule as a static import:
it MUST name the owning package's public top-level facade — or a documented
Ruling-4 bridge module — never a private `_submodule`. The cycle-break
technique is never the problem; an unqualified private-module target is.

## Why

ADR `2026-07-01-import-centralization-adr` (Ruling 6) found
`core/setup_answers.py`'s deferred `_m()` and `_ccaa()` helpers used
`importlib.import_module` to legitimately break an import cycle, but targeted
private submodules — `cadrumo.domain.deadlines._models` and
`cadrumo.domain.contribuyente._ccaa` — when public facades already re-exported
the same names (`cadrumo.domain.deadlines.taxpayer_model`,
`cadrumo.domain.contribuyente`). Because the AST-static import scanner
(`dev/import_hygiene_scan.py`) cannot see a dynamically constructed module
string, this class of violation is invisible to the automated gate and would
otherwise persist indefinitely inside an already-sanctioned cycle-break
pattern. The fix retargeted the strings to the public facades and closed the
gap as an ordinary Ruling-1 violation, without touching the deferred-import
technique itself — proof that the technique and the target are independent
concerns, and only the target is governed by ownership.

## How

- **Good:**
  `importlib.import_module("cadrumo.domain.deadlines.taxpayer_model")` inside a
  deferred cycle-break helper — the module string names the public facade.
- **Good:** `importlib.import_module("cadrumo.domain.contribuyente")` — the
  package's own top level, not a private submodule path appended to it.
- **Bad:** `importlib.import_module("cadrumo.domain.deadlines._models")` from
  outside the `deadlines` package — the technique is fine, the target is a
  private submodule of a package that already exports the same symbols
  publicly.
- **Bad:** `importlib.import_module("cadrumo.domain.contribuyente._ccaa")` for the
  same reason — retarget to the owning package's public facade.

Because the scanner cannot see these string-built targets, this rule is author
discipline: when writing or reviewing a deferred/dynamic import, read the
target string exactly as if it were a static `from X import Y` and apply
`service-imports-via-top-level-reexports` to it.

## Source

ADR `2026-07-01-import-centralization-adr` (Ruling 6), research
`2026-07-01-import-centralization-research`. Companion to
`service-imports-via-top-level-reexports` (the static-import ownership rule
this rule extends to dynamic targets).

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

The `2026-06-11-ledger-hardening-close-audit-pass-2` found the C4 alias-retirement implementation green on focused lint, registry/operator tests, API-stub conformance, and CLI conformance while the mandated full `src/cadrumo` collect-only gate stayed red from support-module export splits owned by other campaigns. Without owner triage, a closeout pass either falsely claims green or opportunistically edits unrelated peer work. The rule preserves honesty without broadening the feature's ownership boundary.

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

Only a taxpayer- or operator-facing AEAT concept may be an `approved` Terminology
Handbook concept (and thus render in the generated glossary and shipped Pagefind
search): a tax, modelo, casilla, régimen, period, legal concept, or operator workflow
noun (`ledger`, `borrador`, `justificante`, `fichero-boe`). A concept naming the
search/calculation/registry MACHINERY (RAG sweep, relevance map, search projection,
preprocessing hook, search record kinds, licence laundering, preflight, registry
binding, work unit, verification-state internals, the Handbook itself) MUST NOT be
`approved`; it is `deprecated` (resolvable for the dev/agent RAG, excluded from the
glossary and shipped search) with a `scope_note` marking it internal, never deleted.

## Why

The corpus-quality drive (`2026-06-15-docs-terminology-search-audit`) found ~14
`approved` concepts documenting the machinery itself (`barrido-rag`,
`proyeccion-busqueda`, `work-unit`, …) — none a taxpayer would look up or that carries
a legal basis. `2026-06-15-docs-terminology-search-adr` (D1/D2) demotes them to
`deprecated` (not `retired`, which asserts a successor a mis-enrolment lacks; not
deleted, per the scaffold-preserve contract); the glossary generator and Pagefind
injector both gate on `approved`, and a scaffold re-surfaces an internal concept only
as an excluded `draft`, so promoting one to `approved` is the guarded regression.

## How

- **Good:** `prorrata`, `modelo-303`, `recargo-equivalencia`, `casilla`, `borrador`,
  `ledger` are `approved` and render; `barrido-rag`, `proyeccion-busqueda`, `binding`,
  `work-unit` are `deprecated` with a `scope_note` — the dev RAG resolves them, the
  taxpayer glossary does not.
- **Bad:** promoting an internal/tooling concept to `lifecycle = "approved"`; or
  deleting an internal concept fragment instead of deprecating it (the scaffold-preserve
  contract never deletes; deprecation keeps it dev-resolvable).

## Source

ADR `2026-06-15-docs-terminology-search-adr` (D1/D2); audit
`2026-06-15-docs-terminology-search-audit` (PERF-001). Enforced by the `approved`-only
gate in `dev/docs/glossary_reference.py` and `dev/docs/pagefind_inject.py`. Companion:
`terminology-single-declaration`, `terminology-scaffold-preserve-contract`.

---
name: iva-cuota-devengada-includes-recargo-equivalencia
trigger: always_on
---

# IVA total cuota devengada must include the recargo de equivalencia tiers

## Rule

Every IVA "total cuota devengada" aggregation formula — Modelo 303 casilla `27`,
Modelo 390 `iva.anual.cuota-devengada-total`, and any IVA modelo's total-devengada
casilla — MUST sum the recargo de equivalencia cuota tiers (recargo casillas, LIVA
art. 161) alongside the standard/reducido/super-reducido repercutido tiers and the
autorepercutido (intracomunitaria / inversión del sujeto pasivo) cuota. Omitting them
silently under-declares for any recargo filer and — because the M390 annual total is
reconciled against the summed M303 quarters — trips the
`modelo-390-cuota-devengada-total-equals-reconciliacion-303` BLOCKING_RULE.

## Why

Grounding the IVA engine against the bundled AEAT Manual Práctico IVA surfaced the same
omission twice: M303 casilla `27` never summed recargo casillas `18`/`21`/`24`, and
M390's `iva.anual.cuota-devengada-total` never summed its recargo tiers — though both
were already ledger-bound. Each silently under-declared, and the M390 case broke the
M390↔M303 reconciliation gate; both surfaced only by reconciling a manual worked example
with a recargo line against the engine. Companion to `no-silent-under-declaration` and
`ledger-iva-advisory-only-on-cuota-bearing-categories`.

## How

- **Good:** the formula sums repercutido general/reducido/super-reducido +
  autorepercutido intracomunitaria/inversión-sujeto-pasivo + the recargo tiers (LIVA
  art. 161), the construct's `legal_refs` cite art. 161, and a grounded parity test
  against a manual worked example charging recargo reproduces the printed total exactly;
  a new IVA modelo/revision confirms the aggregation enumerates every cuota-bearing tier
  including recargo and that any M390↔M303 reconciliation sees the same recargo-inclusive
  total on both sides.
- **Bad:** summing only the standard tiers and autorepercutido while omitting recargo
  (silently under-reports, desynchronises annual↔quarterly); or "fixing" a failing
  recargo-inclusive parity test with a recargo-excluded expected value — the expected
  figure is the manual's printed recargo-inclusive total; fix the formula, not the test.

---
name: ledger-amount-is-absolute-direction-is-authority
trigger: always_on
---

# Ledger amount is an absolute magnitude; direction is the sole flow authority

## Rule

A ledger transaction stores a **non-negative** `amount` magnitude; flow direction
is carried solely by the `direction` enum (INCOMING / OUTGOING /
INTERNAL_TRANSFER). No model, adapter, evidence row, or CLI surface may encode
flow in the sign of an amount. The non-negative constraint is enforced at the
`RawTransaction` boundary so import and manual paths are both gated, and the
evidence-row `amount` / `value_in_eur` mirror the absolute convention. There is
no signed-amount shape to read, migrate, or bridge — old is deleted, not tolerated
(`no-legacy-compatibility`).

## Why

Flow was encoded twice — as the sign of a `Decimal` amount and, redundantly, as a
`direction` enum — and the two could disagree; consistency was enforced only on
the manual command, so the import path derived direction from the sign and a
zero-amount import silently classified as INCOMING. Every engine already routes on
`direction` and takes `abs()`. ADR `2026-06-10-ledger-amount-direction-adr`
collapsed flow onto `direction`, removed the sign from storage, and closed the gap
with one model-level gate.

## How

- **Good:** `RawTransaction.amount` carries a non-negative validator raising
  `TransactionValidationError`, firing for both import adapters and
  `ManualLedgerTransactionCommand`, locked by a save→load→equality roundtrip plus
  an anti-tautology proof (corrupt the on-disk amount negative, assert load
  refusal). Import adapters map the export sign / debit-credit signal to a
  `TransactionDirection` at the parse boundary and store `abs(amount)` as a typed
  `ParsedLedgerRow(raw, direction)`, refusing a zero-amount source row; the import
  action carries that explicit `direction` and never re-derives flow.
  `INTERNAL_TRANSFER` and split children store magnitudes; the reconciliation
  matcher routes by direction (RECEIVED↔OUTGOING, ISSUED↔INCOMING). The CLI
  `--amount` refuses a negative magnitude with an instructive localised error
  naming the accepted form, never a bare "value invalid".
- **Bad:** writing a negative amount to encode an expense; a `direction_from_amount`
  helper reading `raw.amount < 0` downstream of the parse boundary; or a
  read-tolerance / migration branch coercing a legacy signed-amount record — there
  is no released data, old shapes are absent and refused, never bridged.

## Source

ADR `2026-06-10-ledger-amount-direction-adr`; research/plan same stem (cluster
C1). Companion: `aeat-calculation-grounding`, `no-silent-under-declaration`,
`no-legacy-compatibility`, `ledger-derived-revisions-bundle-evidence`.

---
name: ledger-derived-revisions-bundle-evidence
trigger: always_on
---

# Ledger-derived revisions bundle their evidence

## Rule

Every modelo calculation revision that derives any casilla from the ledger MUST
bundle the typed ledger evidence — the contributing-transaction projections plus the
manual fact-basis entries — pegged to the revision's snapshot fingerprint, and every
export of such a revision MUST carry that evidence (or a resolvable in-system
reference to it). An export of a ledger-derived revision that carries neither is
refused.

## Why

`modelo-export-evidence-parity` research (finding B) found revision state stored only
fingerprints (`LedgerFilingSnapshot`); the fact basis explaining *why a casilla holds
its value* was absent from the persisted `CalculationRevision` and every export, so a
filing artefact was legally frail (a human files outside the app; unre-derivable
numbers cannot be defended). `2026-06-03-modelo-export-evidence-parity-adr` decided
the typed evidence (signed amount, currency, direction, base/IVA/rate/category, irpf
category, EU member state, FX, lifecycle, business proportion, legal_refs/source_refs,
attachment/document-link ids per contributor, plus operator manual entries) rides
inside the encrypted revision envelope bound by the same `snapshot_fingerprint`.
Companion to [[aeat-calculation-grounding]] and [[no-silent-under-declaration]].

## How

- **Good:** `compute_ledger_filing_evidence` projects resolved
  `source_transaction_ids` into typed `LedgerEvidenceRow`s plus `ManualFactBasisEntry`s
  bound to the fingerprint; `verify_modelo_revision` captures it in one catalogue load,
  persists it inside the encrypted `CalculationRevision`, and survives a strict
  save→load→equality roundtrip with every defaultable field populated non-default.
  `_assert_evidence_covers_snapshot` makes a bundle that drops a contributor present in
  `source_transaction_ids` raise, and offline xls and online Sheets exports read the
  same evidence to render an identical `Evidencia` surface.
- **Bad:** persisting a ledger-derived revision with only the fingerprint snapshot and
  no typed evidence (the casilla becomes unexplainable); letting an export proceed with
  neither bundled evidence nor a resolvable reference; or asserting the evidence
  roundtrip against numbers hand-computed from the same formula instead of real
  reconstitution of the bundled rows.

## Source

ADR `2026-06-03-modelo-export-evidence-parity-adr` (accepted); research and plan
(W01) of the same feature.

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
`src/cadrumo/_data/corpus/normatives/html/` FIRST — never author a new corpus excerpt from a
secondary source (a gestoría blog, a summary site, a paraphrase) without that
cross-check, and prefer pointing `corpus_ref` at the bundled authoritative file over
hand-authoring a duplicate excerpt.

## Why

Per audit `2026-06-14-aeat-grounding-completion-audit` (finding C1): a módulos DT 32ª
excerpt authored from a secondary source carried a fabricated year-list while the repo
already bundled the authoritative LIRPF text, and the `required_text` cross-check was
tautological (same author wrote excerpt and required_text, validating internal consistency
not BOE faithfulness) — the same root cause recurred in the M210 IRNR 24%-vs-19% defect and
the menor-tres 3.000-vs-2.800 mínimo defect. CRITICAL REFINEMENT (menor-tres + M210): the
bundled corpus is *preferred* over secondary sources but is NOT infallible — for any numeric
AMOUNT or RATE, cross-check the figure against the live BOE/AEAT consolidated text even when
the bundled corpus already states it. Companion to `registry-calculation-legal-grounding`
(cite the binding provision) and `aeat-safety-legal-gates` (ground in BOE/AEAT, never invent).

## How

- **Good:** before authoring a new legal entry, `rg` the bundled `ley-NNNN-AAAA.html`
  file for the provision's anchor (e.g. `#dttrigesimasegunda`, `#a25`), read the verbatim
  text, and point `corpus_ref` at that bundled file with a `required_text` phrase distinctive
  enough to match only the target provision — validating against authoritative text, not a
  self-written duplicate.
- **Good:** when the bundled corpus is a deliberately non-authoritative anchor snippet
  (empty `required_text` / a "Nota de catálogo" disclaimer), treat the registry parameter as
  the calc authority, verify the value against live BOE/AEAT, and flag the snippet for an
  operator corpus refresh — do not trust the snippet prose as the rate authority.
- **Good:** when a verification pass touches a numeric amount or rate, cross-check against
  live BOE/AEAT even if the bundled corpus states it; if the bundled corpus is wrong, correct
  the corpus, the grounded parameter, the legal-entry notes, and any tautological test that
  baked the wrong value in ONE atomic commit (the menor-tres 3.000→2.800 fix touched all four).
- **Bad:** authoring a new `corpus/normatives/html/<provision>.html` excerpt by copying a
  gestoría blog or summary site and citing it from a registry legal entry, or trusting a
  bundled-corpus AMOUNT/RATE without confirming the number against live BOE/AEAT — the
  self-referential `required_text` gate passes anyway (the C1 fabrication pattern).
- **Bad:** stamping an agent-authored legal-authority entry `review_status = "reviewed"`
  under the operator's name without the bundled-corpus cross-check — the legal catalogue is
  a human-reviewed, filing-grade surface; agent-prepared entries must record honest
  `reviewed_by` provenance and be grounded in bundled authoritative text pending operator re-stamp.

## Source

Audit `2026-06-14-aeat-grounding-completion-audit` (finding C1 + M210 corpus-staleness).
Companion: `registry-calculation-legal-grounding`, `aeat-safety-legal-gates`,
`aeat-calculation-grounding`.

---
name: local-filed-observations-are-non-official-evidence
trigger: always_on
---

# Local-filed observations are non-official evidence

## Rule

Observations persisted by the local `file` flow
(`persist_filed_revision_observation`) MUST carry a non-official `source_kind`
(`app_filing`) and MUST NEVER be added to `_OFFICIAL_SOURCE_KINDS` — the set that
satisfies the cross-period clean-state gate (`aeat_sede_justificante`,
`aeat_sede_live_capture`, `aeat_csv_register`). Automatic cross-period
`previous_filing` carry may feed calculate/draft from these observations, but they
must never substitute for external AEAT filing evidence. A same-filing-year local
chain may reach local verify/export ONLY when the chain is present,
value-consistent, revision-confirmed, and its only blockers are the
official-evidence delta; that path MUST surface a non-blocking
non-official-local-chain advisory and MUST NOT assert AEAT acceptance. Cross-year
priors, operator-manual sources, missing filing/observation data, and value or
revision divergence remain blocking.

## Why

Wave C wired automatic local cross-period carry, so `source_kind` is the
load-bearing safety decision: the clean-state guard blocks unsafe dependent
filings whose upstream evidence is non-official
(`LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE`). Treating `app_filing` as official
would let an unevidenced local-only chain silently claim AEAT-evidenced
acceptance, violating `aeat-safety-legal-gates` and `no-silent-under-declaration`.
Decision B (`2026-06-19-crossperiod-filing-deadlock-adr`) narrowed the
same-filing-year reachability gap to the advisory path above.

## How

- **Good:** `persist_filed_revision_observation` stamps `source_kind="app_filing"`;
  the carry resolver reads it to populate a calculate binding; a same-filing-year,
  value-consistent, revision-confirmed local chain whose only blockers are the
  official-evidence delta reaches local verify/export with a non-blocking
  advisory. Cross-year chains, operator-manual sources, missing data, and
  value/revision divergence stay blocking, raising
  `LOCAL_FILING_MISSING_EXTERNAL_EVIDENCE` outside the narrow same-year scope. A
  regression test asserts `app_filing not in _OFFICIAL_SOURCE_KINDS`.
- **Bad:** adding `app_filing` to `_OFFICIAL_SOURCE_KINDS` (launders an unevidenced
  chain past the gate), or persisting the local-filed observation under an official
  `source_kind` to reuse the live-capture path verbatim.

## Source

ADR `2026-06-09-modelo-iva-routing-carry-adr` (ruling D1), commit `10167440f`;
same-year scope refined by `2026-06-19-crossperiod-filing-deadlock-adr`, commit
`84add274d`. Companion: `aeat-safety-legal-gates`, `no-silent-under-declaration`,
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

The same registry-grounded completeness gate MUST bind the fixed-width
fichero-BOE (`.boe`) export, not only the workbook transport. `export_draft` MUST,
before it writes any bytes, assert that every casilla that is a calculation RESULT
(declares a formula) or is schema-required, and that the
`CalculationCompletenessManifest` lists AND the official record files (`manifest ∩
representable`, for the draft's disposition), carries a real value on disk; a blank
such casilla means the calculation did not populate it (a structurally-thin file
behind a valid SHA-256 digest) and MUST raise a hard `FilingExportError`
enumerating every missing casilla with its official number and segmento. Optional
operator-input casillas (retenciones, prior payments, deductions the taxpayer may
legitimately not have — e.g. Modelo 131 casillas 02/08/09/12/14) are NOT required
to carry a value: a blank slot is a valid zero, excluded from the required set. The
rendered set keys on value presence (`ModeloValue.value is not None`), never on
casilla-id membership, because `build_draft` emits an `EMPTY` (`value=None`) row for
every declared casilla. The gate is scoped to `format == "fixed_width"`; an
`xml_dictionary` export omits an absent casilla as a legitimately-absent optional
element, so the blank-slot thinness does not apply.

## Why

Per `2026-06-03-modelo-export-workbook-parity-adr` (research finding A), the
calc-sheets plan mirrored registry structure but wrote no formatting, marked no
start/final, and had no parity gate, so an operator could not see input→result flow
and nothing caught structural drift. Presentation is now typed plan facets defined
once in the builder and materialised identically by both transports, and "official
parity" is checked against the same registry authority the engine uses
(`CasillaDefinition.number`/`segmento`/`section`, the
`CalculationCompletenessManifest`) — not a separate hand-maintained spec.

## How

- **Good:** `build_export_plan(snapshot)` emits one `SheetExportPlan` (value/formula
  cells, number formats, section headers, start/final anchors, protected ranges,
  evidence); `build_offline_workbook` (openpyxl) and `apply_export_plan` (Sheets API)
  are two transports of that one plan, asserted to render the same content; the
  parity gate asserts casilla set = completeness-manifest required set (numbering +
  segmento), registry-declaration section order, and a live formula on every computed
  casilla — a divergence is a hard CI failure.
- **Good:** `assert_export_mirrors_manifest` runs inside `export_draft` after the
  rendered set is known (filtering `v.value is not None`) and before
  `output_path.write_bytes`; a fixed-width `.boe` omitting a required, representable
  casilla panics with an enumerated `FilingExportError` and no file is written.
- **Bad:** computing the rendered set from `{v.casilla_id for v in draft.values}`
  (id membership) instead of `v.value is not None` — every `EMPTY` casilla counts as
  rendered and the gate never fires on the real thin draft; or writing a thin `.boe`
  because the digest is valid (the digest is a byte-integrity lock, not completeness).
- **Bad:** writing formatting/start/final/evidence in one transport but not the
  other, asserting parity against a separate hand-maintained spec, or downgrading a
  structural divergence to a warning.

## Source

ADR `2026-06-03-modelo-export-workbook-parity-adr`; fichero-BOE binding ADR
`2026-07-01-fichero-boe-parity-gate-adr`. Enforced by `test_export_completeness_gate.py`,
`test_export_completeness_sets.py`, `test_fichero_boe_completeness_parity.py`.

---
name: modelo-identifiers-use-core-enum
trigger: always_on
---

# Modelo identifiers use the core Modelo enum

## Rule

Production code MUST reference AEAT modelo identifiers through the `cadrumo.core.Modelo`
StrEnum, never as bare three-digit string literals. The
`src/cadrumo/core/tests/test_modelo_string_usage.py` AST gate enforces this; a genuine
non-identifier occurrence (a regulatory article number, a digit-set membership test, a
CLI command-name token) is recorded in that gate's allowlist with a stated reason. Use
the bare member (`Modelo.M303`) in comparison, membership, and dict-key positions;
reserve `.value` (`Modelo.M303.value`) for plain-`str` contracts (pydantic field values,
call arguments, parameter/CLI-option defaults, returns). A modelo that is a
code-referenced identifier but has no registry definition (a retired form) is added to
the enum and listed in `cadrumo.core.NON_REGISTRY_MODELOS`, which the registry-parity
gate excludes.

## Why

`2026-06-10-modelo-enum-hardening-adr` and its research found ~250 sites using bare
three-digit literals, so a typo or retired code could not be caught at a type boundary.
One core `StrEnum` gives them a single typed home and makes the retired-vs-active
distinction explicit (suppressed M037 has no registry TOML); a `StrEnum` member
compares/hashes/`str()`s/JSON-serialises identically to its value, so the substitution
is behaviour-preserving and the member-vs-`.value` split keeps stored/passed types clean
across pydantic round-trips. Registry-backed members are bound to
`registry_modelo_codes()` by a parity gate, so a new registry modelo without a member
fails loudly.

## How

- **Good:** `if work_unit.modelo != Modelo.M303:` and `{Modelo.M100: ..., Modelo.M130:
  ...}` use bare members (hash as their value); `modelo=Modelo.M720.value` for a
  `str`-typed field and `modelo: Literal[Modelo.M100] = Modelo.M100` for a pinned field
  (`.value` for the plain-`str` contract, member inside `Literal[...]`). A retired
  identifier (`M037`) is an enum member listed in `NON_REGISTRY_MODELOS` and pinned by a
  test to raise from `validate_modelo`.
- **Bad:** `if work_unit.modelo != "303":` or `{"347": ..., "349": ...}` (AST gate
  fails); inventing a `Modelo.M<code>` for a code in neither the registry-bound set nor
  `NON_REGISTRY_MODELOS` (raises `AttributeError`); or silencing the gate with an
  allowlist entry for a real identifier instead of converting it — the allowlist is only
  for genuine non-modelo lookalikes, each with a stated reason.

## Source

ADR `2026-06-10-modelo-enum-hardening-adr` and research. Enforced by
`test_modelo_string_usage.py` (AST gate) and `test_modelo.py` (registry-parity plus
non-registry carve-out).

---
name: modelo-locales-cli-authority
trigger: always_on
---

# Modelo Locale CLI Authority

## Rule

Manage modelo schema-local translation TOML only through `python -m cadrumo.locales modelo ...`; never hand-edit registry-local `locales/*.toml` files for routine scaffold, set, remove, audit, or coverage work.

## Why

The accepted ADR `2026-06-11-modelo-locales-cli-adr` makes the modelo locale CLI the authoring authority for schema-local labels and help text while preserving legally grounded Spanish schema labels as the fallback. The review log `2026-06-11-modelo-locales-cli-code-review-audit` also records a real migration failure caught during CLI-routed scaffold: direct TOML edits would have bypassed the regression test and recovery path. This rule prevents stale keys, missing keys, accidental Spanish-schema mutation, and fragmented campaign tracking.

## How

- Good: run `python -m cadrumo.locales modelo coverage en 130 2019-y-siguientes` before and after translation work to record per-modelo progress.
- Good: run `python -m cadrumo.locales modelo scaffold ca 303 2023-y-siguientes` to align a selected schema-local catalogue without overwriting translated leaves.
- Good: run `python -m cadrumo.locales modelo set hu 130 2019-y-siguientes labels 01 "Bevételek"` to update one translated leaf after registry-key validation.
- Good: leave Spanish schema-local TOML absent unless a future ADR explicitly changes the fallback model; the official Spanish `CasillaDefinition.label` remains the legal source.
- Bad: opening `src/cadrumo/_data/registry/aeat/modelos/303/revisions/2023-y-siguientes/locales/en.toml` in an editor to add or remove keys by hand.
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
`src/cadrumo/application/modelo/_calculation_actions.py`) or deleted; every registry
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

Per operator directive 2026-06-10 (backing inventory
`2026-06-10-zero-legacy-purge-research`): no released version's data must survive an
upgrade, so every migration pass, read-tolerance branch, and "legacy path" is dead
weight that obscures the canonical flow and defends behaviour no caller needs. This
is the deletion-side companion to `aeat-architecture-boundaries` (which forbids
INTRODUCING shims); this one mandates REMOVING legacy surfaces that already exist.

## How

Keep/delete distinctions (each normative):

- **Delete, do not bridge.** Delete a from-birth deterministic-key migration
  module, its bootstrap call site, and harness — do not refactor it.
- **Refuse, do not tolerate.** A read path for a written-from-birth
  envelope/prefix/typed shape RAISES on a missing prefix (corruption now), never
  silently returns the raw legacy form.
- **CREATE is not migration — keep it.** Fresh-schema CREATE/bootstrap that
  materialises the current shape on first access is forward-functional; an ALTER
  pass upgrading an OLDER table is legacy — delete it.
- **External-world variability is not our legacy — keep it.** Resilience for AEAT
  portal variations, BOE corpus formats, PDF producer quirks, and AEAT regulatory
  revisions (each modelo revision year is CURRENT law for its filing year).
- **AEAT regulatory status is never CODE legacy — never conflate.** A real modelo
  still supported (e.g. `Modelo.M037`) is a CURRENT product feature. Only delete a
  surface that exists to read or migrate data an OLDER VERSION OF THIS APP wrote.
- **A forward version FIELD is not legacy — keep it.** A `schema_version` marker or
  a `max_supported_version` ceiling that refuses a FUTURE shape is
  forward-compatibility; only code that BRANCHES on an OLD version is legacy.
- **Bad:** `if payload is None: payload = load(_legacy_cleartext_key(...))` (a read
  fallback for pre-hardening records that cannot exist), or an `ensure_*_columns`
  ALTER loop adding today's columns to a table an older version CREATEd — delete both.
- **Key-management caution:** deleting a key-schedule / DEK-derivation branch can
  strand encrypted data; confirm the creation path mints only the current schedule
  before deleting an "old" one — owner-gated, not autonomous.

## Source

Operator directive 2026-06-10 (`chore/eliminate-shims`); inventory
`2026-06-10-zero-legacy-purge-research`. Companion: `aeat-architecture-boundaries`.

## Status

Active and unchanged for the pre-release regime, governing in full while
`cadrumo.core.COMPATIBILITY_REGIME` is `PRE_RELEASE`: delete-not-migrate, floors
chase current, no read-tolerance of pre-current shapes. The transition to the
post-release regime is governed by `compatibility-lifecycle-checkpoint` (ADR
`2026-07-09-compatibility-lifecycle-adr`), switched on the one-way
`COMPATIBILITY_REGIME` constant. At the flip this rule narrows to "no legacy beyond
the released durability floor": read-tolerance of shapes nothing released wrote, and
shims/aliases, stay forbidden in both regimes. Installing the dormant regime
constant, empty upgrader registries, and the regime-aware gates does not violate
this rule — they read no old shapes and migrate nothing (same blessed category as
the `max_supported_version` forward-ceiling this rule keeps).

---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration

## Rule

A modelo verify gate MUST NOT grant `verified_complete` with zero findings on a draft
that under-declares: whenever a positive economic input is declared (resultado contable,
rendimiento de módulos, ingresos) but the dependent base or cuota resolves to zero and
no offsetting reduction is declared, the gate MUST surface at least an ADVISORY finding.
A human files outside the application, so an explicit operator-facing alert — never a
silent grant — is the minimum safeguard against filing a zero-tax return on positive
activity.

## Why

Round-30 CLI persona testimonials and a coordinator reproduction found the M200 verify
gate returned `granted_verificado_completo = true, finding_count = 0` for a sociedad
with resultado contable €140.000 but base imponible `DP200014:00552 = 0` and cuota
`DP200014:00562 = 0` — the root cause a partially-modelled chain (base imponible a bare
manual input with no derivation from resultado contable). The durable fix models the
determination so a zero base is computed; until then the gate must alert. The shape
recurs across partially-modelled engines (M131 objetiva rendimiento, multi-row
informativas), so the discipline is project-wide. ADR
`2026-06-02-modelo-200-base-determination-adr`; round-30 testimonial audit.

## How

- **Good:** the M200 revision declares an ADVISORY `verification_predicate`
  `implies_nonzero(["00501", "DP200014:00552"])`; the evaluator holds trivially when the
  antecedent is ≤ 0 (no false positive on losses) and fires only when the antecedent is
  strictly positive and the consequent zero, surfacing a non-blocking WARNING
  (legitimately zero base via BIN compensation or correcciones stays permissible),
  grounded with `legal_refs`. Once the engine computes the value, the advisory can be
  upgraded to a `BLOCKING_RULE` computed-vs-entered consistency check, or retired.
- **Bad:** shipping a manual base/result casilla with no derivation and no guard so the
  gate grants `verified_complete` with `finding_count = 0` on positive input; or a
  `BLOCKING_RULE` that refuses legitimate positive-result/zero-base filings (negative
  result, full BIN compensation, exemptions) — the guard must distinguish the suspicious
  case (positive antecedent, zero consequent) and stay advisory while legitimate
  zero-base cases exist.

## Source

ADR `2026-06-02-modelo-200-base-determination-adr` (Phase 1); audit
`2026-06-02-cli-persona-testimonials-round-30-audit`; worked example `414fd3529`.

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
  (`src/cadrumo/application/calculations/_relation_prefill.py:279`), the exact same
  function the Sheets-pull path calls
  (`entrypoints/cli/_config/_google_sync_calc.py:130`), so both transports run one
  resolver.
- Good: parity is enforced by
  `src/cadrumo/application/calculations/tests/test_pull_path_calculate_path_casilla_parity.py`
  — a regression that the pull path and the calculate path produce identical
  casilla values for a shared revision.
- Bad: a pull-path `assemble_*` helper that computes a casilla one way while the
  live calculate path computes it another — a calculate↔export cycle then drifts
  the persisted revision with no save-time detection.
- Bad: shipping a new aggregation surface on only one of the two transports — the
  parity regression must cover any casilla both paths can persist.

---
name: operator-harness-cites-live-cli-surface
trigger: always_on
---

# Operator harness documents cite only the live CLI surface

## Rule

Every operator agent-harness document — each operator rule, persona, and skill
under `src/cadrumo/_data/agent/` — that names a CLI verb (an `aeat ...` invocation)
or a JSON-envelope field MUST cite only verbs that resolve against the live
operator-surface manifest and fields that exist on the live envelope models, and
MUST be co-committed with the CLI surface it couples to. A harness document and
the verb or field it teaches move in the same change, or the document orphans the
operator.

## Why

The harness is the operating layer an LLM tax-advisor loads to drive the
deterministic CLI; a rule, persona, or skill that cites a renamed or non-existent
verb hands the agent a dead instruction it cannot recover from — the operator-side
form of the verb-drift failure the `aeat-cli-pull-and-file-standard` rule exists
to prevent. During the agent-harness build a safety rule cited `aeat app modelo
work export`, which does not exist (the real verb is `aeat app modelo export`); the
drift gate caught it before commit. The gate
(`src/cadrumo/agent/tests/test_rule_surface_conformance.py`) parses every shipped
rule, persona, and skill, extracts each `aeat ...` command path and each named
envelope-spine field, and asserts they all resolve against the live manifest and
the real `SchemaEnvelope`/`Notice` models, so a drift is a loud test failure rather
than a silent operator misdirection.

## How

- **Good:** a skill that tells the operator to run `aeat app modelo work calculate`
  cites the verb exactly as the CLI exposes it; the drift gate confirms it resolves
  and the change ships with any coupled CLI surface.
- **Good:** a rule that instructs the operator to read the envelope `status` or a
  notice `suggestion` names a field the gate confirms still exists on the live
  model.
- **Bad:** authoring `aeat app modelo work export` (a verb that does not exist) or
  citing a renamed/removed envelope field — the gate fails until the citation
  matches the live surface.
- **Bad:** renaming a CLI verb without sweeping the harness documents that cite it,
  leaving the operator a dead instruction.

## Source

Authored during the agent-harness framework build (ADR
`2026-06-30-agent-harness-adr`, plan step W05.P13.S54), codifying the discipline
the rule-surface drift gate enforces. Companion to `aeat-cli-pull-and-file-standard`
(CLI verb naming), `cli-notices-are-the-only-diagnostic-channel` (the envelope
fields the rules cite), and `aeat-architecture-boundaries` (the two-root surface).

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

Every regulatory value compiled into the registry schema — a tax rate, bracket
tranche, threshold, deadline window, reduction coefficient — MUST declare, in its
`legal_refs`, the specific binding provision that *establishes that value* (the
article, disposition, or transitional provision that sets it), and that provision
MUST be defined in the legal catalogue with a `corpus_ref` resolving to the real
BOE/AEAT text. Citing the general framework article alone (e.g.
`ley-27-2014:art-29`) is insufficient when a more specific provision (a
transitional disposition, phased schedule, or modifying law) actually fixes the
number. A value whose binding provision is not in the schema is ungrounded and
MUST NOT ship.

When authoring or changing a regulatory value, confirm the binding provision is
(1) cited on the value's `legal_refs`, (2) defined in the legal catalogue, (3)
backed by corpus text the evidence gate validates, and (4) consistent with the
value (the corpus clause states the number encoded).

## Why

The Modelo 200 micro-empresa (INCN<1M) rate carried `0.17 / 0.20` for 2025
grounded only in `ley-27-2014:art-29`; the binding source — LIS DT 44ª, added by
Ley 7/2024 (BOE-A-2024-26694), phasing the rate to 21%/22% for 2025 — was absent
from the schema, so the wrong rate sat undetected and commit #210 compounded it
to a flat 23%. A regulatory number with no binding-provision citation has no
anchor to verify against and is frail by construction.

## How

- **Good:** the micro-empresa 2025 bracket declares `legal_refs =
  ["ley-27-2014:art-29", "ley-27-2014:dt-44"]`, and `ley-27-2014:dt-44` is defined
  in `legal/is.toml` with `corpus_ref =
  "corpus/normatives/html/ley-27-2014-dt-44.html#dt44"`, `document_id =
  "BOE-A-2024-26694"`, and a `required_text` the evidence gate cross-checks ("21
  por ciento"). A deadline window or threshold likewise cites the specific
  orden/RD/ley article, not just the parent law, with matching corpus text.
- **Bad:** a phased/transitional rate citing only the framework article while the
  disposition that sets the year's figure is uncited; or a `legal_refs` entry
  pointing at a catalogue id with no `corpus_ref` or whose corpus text lacks the
  value's clause — the citation must be verifiable, not decorative.

## Source

Binding-law reconciliation of the M200 micro-empresa INCN<1M cuota (LIS art. 29.1
+ DT 44ª, Ley 7/2024, BOE-A-2024-26694); operator directive 2026-06-02. Companion:
`aeat-calculation-grounding`, `aeat-schema-central-config`.

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

# Registry revision content is fragmented — revision.toml is scalar-only; assess via the loaded snapshot, never `ls`/`find` alone

## Rule

A registry modelo revision declares its sections — `bindings`, `formulas`,
`casillas`, `verification_expectations`, `verification_predicates`,
`constructs`, `completeness_manifest`, and every other array-of-tables field —
ONLY in fragmented subdirectories (`bindings/`, `formulas/`,
`verification_expectations/`, …). The fragment directory's `revision.toml`
manifest carries ONLY scalar revision metadata (label, `valid_from`/`valid_to`,
`period_selector`, `legal_refs`, `source_refs`, `orden_aplicabilidad`,
`continuidad_validation`). The loader ENFORCES this: an inline
`[[revisions."…".<section>]]` table (or the `completeness_manifest` table) in
`revision.toml` is a loud `RegistryLoadError` naming the fragmented layout. To
assess whether a revision is calc-grade, whether a casilla is ledger-bound, or
whether a binding/formula is present, load the revision through the authority
and inspect the compiled schema — never infer a revision's coverage from
`ls bindings/` / `find -path '*formulas*'` on the subdirectory listing alone.

## Why

Historically a revision could declare sections EITHER inline in `revision.toml` OR
in fragmented subdirectories, so a subdirectory-blind check (`ls bindings/ | wc -l`)
missed inline declarations — in #15 (M303 `2009-y-siguientes`) it wrongly concluded
"parse-only" and missed a real cuota-without-base under-declaration, and it
mis-classified fully-inline M369. The `arch-remediation-registry-format` campaign
(ADR `2026-07-02-arch-remediation-registry-format-adr`) converged every revision to
the fragmented layout (byte-identical at the compiled-`ModeloRevision` level) and
added the loader refusal, so the loaded snapshot is now format-agnostic ground truth.
Companion to `aeat-registry-authority-flow`.

## How

- **Good:** to decide whether a casilla aggregates from the ledger, load the
  revision through the authority (`resources().modelos.authority.snapshot(...)`) and
  inspect `revision.bindings` / `revision.casillas` — the compiled schema is ground
  truth; `grep` the `bindings/` / `casillas/` fragments only to pin exact ids.
- **Good:** before grounding any binding-source classification, read the binding's
  `source` field (`ledger_iva_aggregation` vs `profile` vs `relation_prefill`) — a
  `source = "profile"` binding (autoconsumo, state attribution) is not a ledger
  silent-zero even when absent (#43).
- **Bad:** re-introducing a section table inline in a fragment directory's
  `revision.toml` — the loader refuses it, naming the `<section>/` subdirectory.
- **Bad:** `ls bindings/ | wc -l` as the SOLE signal of "is this revision
  calc-grade / does this casilla bind" — count the LOADED snapshot's sections, and
  never conclude "parse-only / staged build-out" from subdirectory absence without
  loading the revision.

## Status / Source

Active; converged by `arch-remediation-registry-format` (ADR
`2026-07-02-arch-remediation-registry-format-adr`, plan
`2026-07-02-arch-remediation-registry-format-plan`) — inline sections in
`revision.toml` are now a hard load error. First exposed by the #15 IVA-3 correction
(`6c259afc3`, recargo tail `4e669c113`). Companion: `aeat-registry-authority-flow`,
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
`src/cadrumo/domain/calculations/registry/_bindings_previous_filing.py`), and
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
  (`IVA_WALLET_OWNED_RELATION_TARGET_BINDINGS`,
  `_validate_relation_sources.py`) — owned pre-mesh by the iva-wallet gate.
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

The `2026-06-11-ledger-hardening-close-audit` found that the (since-reconciled and deleted) `AggregationSourceKind.INVOICE` member looked retired at the CLI layer but still powered a contradictory registry-validation surface: schema construction accepted it, validation routed it positively, and selector validation rejected it. Deleting a member before reconciling consumers breaks registry fixtures and hides whether the intended final state is acceptance or rejection. The project needs one coherent state before enum deletion. (That reconciliation completed: `AggregationSourceKind` itself was later deleted and its source kinds moved to `BindingSourceKind`.)

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
(`src/cadrumo/domain/calculations/registry/_temporal.py`) or
`resolve_registry_revision_for_work_target`
(`src/cadrumo/application/modelo/_work_addressing.py`); a stored, literal, or
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
secure-storage backend, accessed through the active-profile-bucket runtime
wrapper (`secure_object_repository_for_active_bucket` /
`secure_object_repository_for_bucket`, the `SecureObjectRepository` substrate,
and the content-addressed `AttachmentStore` that wraps it). No code path may
write or persist sensitive financial data anywhere outside secure storage: no
temp files, no scratch directories, no plaintext side stores, no on-disk caches,
no logs. Decrypted bytes may exist only transiently in process memory and must
never be written out. A path pointer to a cleartext file on operator disk (e.g. a
`source_path` field) is NOT a valid persistent home for invoice bytes; the bytes
themselves belong in secure storage.

## Why

This is the load-bearing confidentiality guarantee of the whole application. The
`llm-evidence-classification` Stage-3 pass (ADR
`2026-06-10-llm-evidence-classification-adr`) is the worked failure: an early
draft designed a decrypted-temp-file route for subprocess CLI agents and framed
off-host upload as a tunable boundary; the operator rejected it outright —
removing sensitive financial data from secure storage (temp file or off-host) is
never acceptable, and categorically unacceptable for gestors or serious
professional use.

## How

- **Good:** invoice/attachment bytes are written and read through the
  content-addressed `AttachmentStore` (`put_bytes` / `read_bytes`), wrapping
  encrypted `Envelope` records in `SecureObjectRepository` at `FINANCIAL`
  sensitivity via the active-bucket wrapper; a consumer reads them into memory
  and uses them transiently, writing nothing to disk. A model that must read a
  document runs on-host (in-tree extraction or a local vision model fed in-memory
  base64); any off-host transmission is gated behind an explicit, per-invocation,
  default-off, gestor-barred consent acknowledgement (see
  `off-host-evidence-upload-requires-explicit-consent-gate` when it lands) and
  never uses a file-writing transport.
- **Bad:** materialising decrypted evidence to a temp file (even bounded-lifetime,
  `chmod 600`, promptly removed) for a subprocess to read by path; storing only a
  `source_path` to a cleartext file as the durable home; or writing sensitive
  values to logs, a plaintext JSON side store, an on-disk cache, or a scratch dir.

## Source

Operator directive recorded 2026-06-10; ADR
`2026-06-10-llm-evidence-classification-adr`. Companion:
`aeat-safety-legal-gates`, `aeat-architecture-boundaries`.

---
name: service-imports-via-top-level-reexports
trigger: always_on
---

# Service imports via top-level re-exports

## Rule

Every cross-package import project-wide MUST resolve to the SOLE canonical
public top-level ``__all__`` facade of the symbol's owning package; a
cross-package consumer MUST NEVER import from another package's private
``_module`` (ownership of ``A.B._C...`` is ``A.B``). Intra-package private
imports and a package building its own facade out of its own private modules
are fine. When the symbol is not yet exported, promotion to ``__all__`` is a
precondition of the consuming change, not a follow-up: add the symbol to the
owning package's ``__all__`` (eager ``from .module import Name`` by default;
lazy ``__getattr__`` / PEP 562 ONLY if the owning package already uses that
pattern or an eager import risks a circular-import cost — never retrofit an
existing eager facade to lazy). Never mechanically rename a private ``_name``
straight into ``__all__``; per-symbol, either rename-to-public and promote a
genuinely shared primitive, or expose a narrower purpose-built public API for a
single caller's need, or treat the reach as a design defect to remove. A
single DOCUMENTED non-``__init__`` public re-export bridge module (a stated,
one-line-docstring purpose) is an acceptable canonical source; an undocumented
pure-reexport shim is not.

## Why

Per `2026-07-01-import-centralization-adr` (Rulings 1-4), letting one consumer dot
into a package's internals reads to every later consumer as permission to do the
same; the `2026-07-01-import-centralization-research` scan quantified 2465
cross-package private imports across 250 files plus a naming collision and three
latent violations hidden in a circular-import workaround. The constraint is
ownership-first, promotion-before-rewrite, one canonical facade per symbol, enforced
by the project-wide AST scanner `dev/import_hygiene_scan.py` and CI gate
`src/cadrumo/tests/test_import_hygiene_gate.py` (ratcheting a checked-in production
baseline toward zero; Family-2 documented-bridge allowlist and Family-3 pinned-symbol
set are structural data).

## How

- **Good:** a new ``cadrumo.application.bucket_maintenance`` service imports
  ``rename_profile`` from ``cadrumo.application.user_profile`` (the package
  ``__all__`` re-export), promoted before the service file was authored; the six
  documented non-``__init__`` bridge modules — ``registry/applicability.py``,
  ``deadlines/taxpayer_model.py``, ``transactions/_ids.py``, ``cli/_schemas.py``,
  ``outbound/aeat/_playwright.py``, ``workflow/_utils.py`` — remain acceptable
  canonical sources under Ruling 4.
- **Good:** an underscore-named symbol reached by two or more unrelated production
  packages is renamed to public and promoted to ``__all__`` (Ruling 3.i); one
  reached by exactly one narrow caller instead gets a purpose-built narrower public
  API (Ruling 3.ii), never a blanket ``_foo`` -> ``foo`` rename.
- **Bad:** ``from ....application.user_profile._orchestration import rename_profile``
  (dotting into a private submodule) — the next agent reads the precedent and
  erodes the boundary; or an undocumented pure-reexport shim invented to avoid a
  proper facade promotion (only the named documented bridges count under Ruling 4).
- **Bad:** mechanically stripping the leading underscore from every reached private
  symbol into ``__all__`` without judging shared-primitive vs single-caller vs
  design-defect — the blanket promotion Ruling 3 forbids.

## Status

Active; generalized project-wide. Supersedes the prior narrower "new application-layer
service" scope, now the first `Good` worked example.

## Source

ADR ``2026-06-03-cli-workflow-redesign-adr``; generalized by
``2026-07-01-import-centralization-adr`` (research ``2026-07-01-import-centralization-research``).
Enforced by ``dev/import_hygiene_scan.py`` and ``src/cadrumo/tests/test_import_hygiene_gate.py``.

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
name: single-subject-mutation-is-idempotent-guarded
trigger: always_on
---

# Single-subject creating mutations are idempotent-guarded

## Rule

Every CLI verb (and the application service behind it) that CREATES one
addressable record MUST be `idempotent_guarded`: a retry carrying the same
caller-supplied idempotency key — or the same deterministic, clock-free derived
id — returns the EXISTING record as a no-op (no second lifecycle event, no
`created_at`/`modified_at` re-stamp, no re-run of side effects) surfaced through
the surface's uniform result shape (e.g. the ledger mutation quintet with empty
`bucket_event_ids`) plus an info `Notice`; a same-key call whose content DIFFERS
refuses with an instructive, localised conflict naming the divergent fields. A
verb that is deliberately additive (two genuinely-distinct records may share
identical content) is `non_idempotent_append` and MUST document that choice. The
record's identity MUST be clock-free — the timestamp is a non-identity last-seen
body field, never folded into the derived id — so a retry at a different instant
resolves to the same record.

## Why

Per ADR `2026-06-30-ledger-add-idempotency-adr`, the `aeat` CLI's operator is an
autonomous LLM agent that retries calls, so a non-retry-safe creating mutation
silently double-writes (a duplicate ledger transaction inflates every downstream
modelo aggregation; a time-stamped verify/filing record accumulates one copy per
retry). It closed this across manual `ledger add`, `modelo verify`, and `modelo
file` by keying on a clock-free id and refusing same-key/different-content; the
close review `2026-07-01-ledger-add-idempotency-audit` caught the guarded failure
mode — a no-op match that omits a field (recargo, source jurisdiction) silently
drops the new value (`no-silent-under-declaration`).

## How

- **Good:** `create_manual_transaction` keys on the clock-free provider id
  `manual:{bucket}:{key}`; a same-key retry with matching content returns the
  existing-row quintet with empty `bucket_event_ids` + an info `Notice`, emitting no
  second `LEDGER_TRANSACTION_CREATED` event and leaving `created_at` unchanged; a
  differing same-key add raises `TransactionValidationError`. The match compares
  EVERY persisted field (including `recargo_amount` and `source_jurisdiction`).
- **Good:** `derive_verification_report_id` / `derive_filing_record_id` fold the
  OUTCOME (revision + status/findings + actor) and drop the timestamp from identity;
  a non-granting verify retry and a re-file of an already-`PRESENTADO` revision
  collapse to the existing record with an info `Notice`.
- **Good:** the keyless `ledger add` path stays `non_idempotent_append` (two genuine
  identical same-day cash movements both persist); the agent-harness contract
  requires the agent to always pass a stable idempotency key.
- **Bad:** an id that folds `now()`/`occurred_at`/`filed_at` (a retry mints a new id
  and double-writes), or a guarded no-op whose match omits a persisted field so a
  same-key retry changing only that field silently drops the new value.
- **Bad:** modelling a deliberately-additive verb as guarded (collapsing distinct
  records) or an idempotent verb as append (double-writing on retry) without
  documenting the choice.

## Source

ADR `2026-06-30-ledger-add-idempotency-adr`; audit `2026-07-01-ledger-add-idempotency-audit`.
Companion: `ledger-mutation-returns-uniform-quintet`,
`cli-single-subject-id-is-positional`, `cli-notices-are-the-only-diagnostic-channel`,
`no-silent-under-declaration`.

---
name: subagent-commits-require-explicit-pathspec
trigger: always_on
---

# Rule

A dispatched agent (or coordinator) committing in this shared worktree MUST pass
an explicit pathspec to `git commit -- <path>...` naming only files it authored,
and MUST verify (`git diff --cached`) that the staged set carries zero foreign
markers immediately before committing. A bare `git commit` with no pathspec is
forbidden: the shared index routinely holds peer campaigns' staged work, and a
no-pathspec commit sweeps all of it under your SHA and message.

## Why

During the DAE-80 agent-harness rollout a subagent tasked with a one-line change
verified its own file was clean, then ran `git add -- <its file>` followed by a
`git commit` with NO pathspec. The shared index already held 35 staged files from
the unrelated `cross-domain-continuity` campaign, and the no-pathspec commit
bundled all of them into commit `84f84166f` under the subagent's message. This
was not benign: it left the M100 anualidades regime (LIRPF art. 64/75) broken at
committed HEAD — a deleted derivation function still referenced by
`schema.toml`/registry bindings, a silent-under-declaration-class defect — and it
mis-attributed a peer campaign's work to a foreign SHA. `git add` being
path-scoped is not enough; the commit itself must be path-scoped, because
`git commit` with no pathspec commits the entire index. This is the enforcement
teeth behind `uncommitted-wip-is-not-orphaned` (which governs how to LAND your own
change amid live peer WIP) and `aeat-git-worktree-safety` (which forbids the
destructive un-bundling that a swept commit tempts).

## How

- **Good:** `git commit -m "..." -- src/cadrumo/foo.py src/cadrumo/tests/test_foo.py`
  after `git diff --cached -- src/cadrumo/foo.py src/cadrumo/tests/test_foo.py` confirms
  only your hunks are staged; a pathspec commit ignores every other staged path.
- **Good:** for a file entangled with a peer's uncommitted hunks, use the
  apply-cached gated drive from `uncommitted-wip-is-not-orphaned` (stage a
  HEAD-anchored own-edits-only patch, verify zero foreign markers, then a
  verified-index commit) rather than a pathspec commit that would re-stage the
  peer's interleaved lines.
- **Bad:** `git add -- my_file.py && git commit -m "..."` (no pathspec on the
  commit) — sweeps every other file staged in the shared index under your SHA.
  This is the `84f84166f` incident.
- **Bad:** a no-pathspec `git commit` "because I only touched one file" — you did
  not stage the index; peers did, and the commit takes the whole index.
- **Bad:** a broad `git add` (a directory, `-A`, or `.`) that sweeps peer-staged
  files, then a `git reset -- <your files>` to "undo" it. `git reset` in any form
  is categorically forbidden here (`aeat-git-worktree-safety`) — even an
  index-only pathspec reset. The fix is to never over-stage: `git add -- <your
  explicit files only>` then `git commit -- <the same explicit files>`. If you
  ever find you need `git reset` to clean up a bad add, you added too broadly —
  there is no reset escape hatch.

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

- Good: Add or update a concept fragment under `src/cadrumo/_data/terminology/concepts/`, then use `:term:` references in docs prose.
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

- Good: `src/cadrumo/application/modelo/tests/test_work_addressing.py` tests the `cadrumo.application.modelo` surface from its local test folder.
- Bad: `src/cadrumo/application/modelo/test_work_addressing.py` sits beside implementation modules and pollutes the code namespace.

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

All `.vault/` reads, mutations, audits, and repairs route through `vaultspec-core`
owning-verb logic; never hand-write frontmatter, filenames, plan structure, or new
`.vault/` documents (editing scaffolded body prose is permitted, see "Allowed manual
edits"). The vaultspec MCP tools are the primary transport where the server is
connected, the `vaultspec-core` CLI verbs otherwise; both terminate in the same
owning-verb logic that enforces templates, taxonomy, wiki-links, and schema, so
bypassing it produces drift the `check` tool and `vaultspec-core spec doctor` will flag.

## Orientation

Orient before working in a project you have no session context for: the `status` tool
reports the in-flight plans and their next open Step, and the `find` tool locates the
documents and features behind them (CLI: `vaultspec-core status [TARGET]`). Orientation
is descriptive, read-only, and the zeroth move, not a pipeline phase.

## Tools and operations

The nine MCP tools cover the hot path by capability: `status` (orientation), `find`
(document and feature discovery), `create` (scaffold documents, batchable), `edit`
(body-prose edits, batchable), `plan_progress` (mark Steps checked or unchecked),
`plan_edit` (author and restructure Step rows), `check` (validate and repair), and the
`discover`/`invoke` gateway that reaches every remaining verb.

Operations without a first-class hot tool fall into two honest bands:

- **Gateway-only, CLI-first:** `sync`, `spec <resource> sync`, and the above-Step plan
  verbs (`tier promote/demote`, `wave`, `phase`, `epic intent`). The `discover`/`invoke`
  gateway also reaches these, but `invoke`'s destructive annotation forces host
  confirmation on every call, so the CLI is the better default even when connected.
- **CLI-only:** `vault feature index`, `spec mcps add/remove/sync`, and `uninstall` have
  no MCP path at all; run them through the CLI.

For anything else, the `discover` tool and the bundled CLI reference
(`.vaultspec/reference/cli.md`, locally resident) are the catalogs of every command,
option, argument, and exit code.

Where the vaultspec MCP server is not connected, the `vaultspec-core` CLI verbs carry
every operation; the bundled CLI reference is the catalog.

## CLI fallback

- Run `vaultspec-core <cmd>`, or `uv run --no-sync vaultspec-core <cmd>` in uv
  environments; `--target DIR`, `--dry-run`, `--json`, `--force`, and `<cmd> --help`
  cover targeting, previewing, and the full flag and exit-code reference.
- Sync-shaped results (`install`, `sync`, `spec <resource> sync`, `migrations run`) read
  with one vocabulary - `created`, `updated`, `unchanged`, `removed`, `restored`,
  `skipped`, `failed`; `unchanged` is a successful no-op, `skipped` carries a reason,
  only `failed` stops the pipeline.

## Allowed manual edits

Permitted: editing body prose of a document scaffolded through the `create` tool or
`vaultspec-core vault add`, and editing sources under `.vaultspec/rules/`, `skills/`,
`agents/`, `hooks/`, or `mcps/` followed by `vaultspec-core sync`. Forbidden:
hand-writing frontmatter, filenames, or new `.vault/` documents, and editing files
inside generated provider directories (`vaultspec-core sync` regenerates them).

---
name: vaultspec-discovery.builtin
trigger: always_on
---

# Codebase and intent discovery

Begin every pipeline phase - Research, ADR, Plan, Execute - by grounding in what the
project already decided and built. The project's own benchmarking is unambiguous: a
semantic-search-led hybrid sweep finds a feature fastest and at the lowest context cost
\- roughly 1.3-2x cheaper than broad keyword search on a large tree - and recalls
governing decisions with near-zero noise. Lead with it. The validated sequence is locate
by meaning, read the epicenter whole, confirm with grep:

1. **Locate by meaning.** For code, lead with
   `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
   `--language`/`--path`); it reaches the right file in about one call where broad
   globbing floods context. For decisions and intent,
   `vaultspec-rag search "<intent>" --type vault --doc-type adr` - the directed ADR
   filter, sharper than catch-all `--type vault`. `vaultspec-core status [target]`,
   `vaultspec-core vault list`, and `vaultspec-core vault graph` are first-class for
   orientation, in-flight plan state, and project health - reach for them to get your
   bearings on intent. For a small, well-named module, list the directory.
1. **Read** the epicenter file - or, when extending a feature, the nearest existing
   analogue - in full. This whole-file read is the breakthrough in nearly every run.
1. **Confirm** exact symbols and insertion points with a targeted grep, which is sharper
   than semantic search at exact-symbol lookup.
1. For decision discovery, round out recall by listing `.vault/adr/` and filtering by
   feature - semantic search alone can miss lower-ranked or opaquely-named records.

Do not lead with broad `Glob`/grep sweeps; their context cost scales badly on large
codebases, and grep earns its place at the confirmation step. Where `vaultspec-rag` is
not installed, the `vaultspec-core` discovery verbs and grep carry the same sequence.

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

# vaultspec-rag — semantic search for code and decisions

Discover by MEANING when you do not know the exact name, instead of grepping keywords or
guessing identifiers. vaultspec-rag does two jobs: find the CODE, and find the DECISIONS -
the ADRs (architecture decision records) that govern it.

Server mode is the default backend. If a search reports the service is down, start it with
`uvx vaultspec-rag server start` (small or offline projects opt into the on-disk local
backend with `--local-only`). The running service auto-reindexes on file changes.
DO NOT manually reindex during normal work.

## Discover code by meaning

`--type code` searches source by meaning. Phrase the query as a short behaviour plus the
concrete domain nouns the target code would use: the behaviour drives semantic matching, the
nouns drive exact matching, so a bare keyword or pure prose finds less than both together.

```
uvx vaultspec-rag search "retry backoff around failed webhook delivery" --type code
```

## Discover architecture decisions

When you need the WHY - the rationale, constraints, or decision behind code - search the
vault's ADRs, not the source. `--type vault --doc-type adr` returns the governing records.

```
uvx vaultspec-rag search "decision on gpu lock scope around the forward pass" --type vault --doc-type adr
```

`--doc-type` also accepts `audit`, `plan`, `reference`, `research`, and `exec` (comma-separate
to union several).

## Cut noise with filters

Semantic search competes production code against its own noise - overlapping tests, parallel
locale files, generated and vendored trees, worktree clones. Code search is production-biased
by default: it hides duplicate/derivative domains (`generated`, `worktree`) and demotes
`tests`, `docs`, `locale`, and `vendored` beneath production. When noise still crowds a page,
narrow by DOMAIN rather than raising `--max-results`. The domains are `prod`, `tests`, `docs`,
`locale`, `generated`, `vendored`, `worktree`.

Steer with inline query tokens (comma-separated, repeatable):

```
uvx vaultspec-rag search "fixture setup helpers exclude:tests" --type code
uvx vaultspec-rag search "auth token validation only:prod" --type code
uvx vaultspec-rag search "translation table lookup include:locale" --type code
```

`exclude:` hides a domain, `only:` keeps just the named domains, and `include:` re-admits a
domain the default profile hides or demotes. Compose with path and category filters:

```
uvx vaultspec-rag search "request handler" --type code --include-path "src/**" --exclude-path "**/legacy/**"
uvx vaultspec-rag search "encode batch" --type code --prefer production
```

The full option set is `uvx vaultspec-rag search --help`. The same search is available through
MCP as the `search_codebase` and `search_vault` tools.

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
  managed through the plan verbs - the `plan_progress` and `plan_edit` MCP tools where
  connected, the `vaultspec-core vault plan` CLI otherwise.

- `.vault/exec/yyyy-mm-dd-<feature>/.../<step>.md`: The individual `<Step Record>`.

- `.vault/exec/yyyy-mm-dd-<feature>/...-summary.md`: The `<Phase Summary>`.

- `.vault/audit/yyyy-mm-dd-<feature>-audit.md`: The `<Audit>` report. A feature with
  multiple audits, references, or research documents disambiguates each with an optional
  narrative infix - `yyyy-mm-dd-<feature>-<topic>-<type>.md` - scaffolded through the
  owning verb's `--topic` flag (`vault add` for audit, reference, and research only),
  never by hand-picking a filename.

- `.vault/index/<feature>.index.md`: The auto-generated `<Feature Index>` linking every
  document for a feature. The index regenerates as a side effect of the `create` and
  `edit` tools; regenerate it manually with `vaultspec-core vault feature index` when
  working through the CLI, and never author it by hand.

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
hierarchy should reference those above them. Source code sits outside this hierarchy
entirely: vault documents cite code by `path:line` locator, and tracked source-file
content never references `.vault/` documents, identifiers, or harness contents (opt-in
git commit trailers are the sanctioned linkage channel).

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
  - *Cardinality:* one plan executes one ADR or a cluster of ADRs (the epic roll-up);
    every governing ADR is listed in `related:`. One ADR is never spread across several
    concurrent plans.

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

  - *Auto-generated* as a side effect of the `create` and `edit` tools; regenerate
    manually with `vaultspec-core vault feature index` when working through the CLI,
    never authored by hand.
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

  - Narrative infix (audit, reference, research only):
    `yyyy-mm-dd-{feature}-{topic}-{type}.md` (e.g.,
    `2026-02-04-editor-demo-engine-wire-reference.md`), scaffolded with the owning
    verb's `--topic` flag

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

---
name: verification-grounding-needs-oracle-evidence
trigger: always_on
---

# Verification grounding needs bundled oracle evidence and engine reproduction

## Rule

A verification grounding claim — a casilla listed in a verification expectation's
`externally_grounded_casilla_ids` — MUST be backed by a bundled AEAT-authoritative
oracle payload carrying the expected figure (a Renta WEB Open replay under
`corpus/parity_replays/renta_web_open/`, or an AEAT manual worked-example oracle under
`corpus/manual_oracles/`, both keyed by `expected_by_casilla_id`), AND the registry
engine MUST independently reproduce that figure in a parity test. Never fabricate a
grounding figure, never hand-compute it from the registry formula under test, and never
declare `externally_grounded_casilla_ids` without both. Enrollment in a
`verification_expectation` is NOT grounding — it only reconciles filed-vs-engine;
grounding is the stronger claim that the engine value itself is checked against an
independent AEAT authority.

## Why

The verification-power campaign found enrollment at 100% of computed casillas while
external per-casilla AEAT grounding was ~1% (research
`2026-07-01-verification-power-research`): a value reconciled only against the app's own
engine cannot catch a systematic engine error the filing matches. ADR
`2026-07-01-verification-power-adr` made grounding a build-time-validated registry field
surfaced as `independently_grounded_fraction`, and the symmetric honesty gate
`test_external_oracle_grounding_enrolled.py` enforces evidence in BOTH directions (every
bundled oracle figure enrolled; every declared id backed by a bundled figure for its
filing year). Companion to `legal-grounding-verifies-bundled-authoritative-corpus` and
`no-tautological-calculation-tests`.

## How

- **Good:** M100 2024 `0226` is declared `externally_grounded` only after (1)
  `corpus/manual_oracles/modelo-100-2024-estimacion-directa-simplificada.json` carries
  `expected_by_casilla_id.0226 = "58100.00"` quoted verbatim from the AEAT manual (with
  a `raw_evidence_locator` anchor), and (2)
  `test_m100_2024_estimacion_directa_manual_worked_example.py` proves the engine
  independently computes `0226 = 58100.00`. When the manual states a contradictory
  figure (OCR/footnote artefact), ground on the figure it states repeatedly and the
  engine re-derives bottom-up, documenting the discrepancy — never silently pick one.
- **Bad:** adding an id because the engine emits a plausible value, with no bundled
  oracle (the honesty gate fails); or authoring an `expected_by_casilla_id` figure by
  copying the registry formula's own output (tautological — it must be the AEAT literal,
  independently reproduced).
</vaultspec>
