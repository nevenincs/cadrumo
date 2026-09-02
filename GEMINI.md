<vaultspec type="config">
## Vaultspec Rules

You MUST respect these rules at all times:

---
name: aeat-agent-orchestration
trigger: always_on
---

# AEAT execution ownership

## Invariants

- The person or agent delivering a change owns its evidence: inspect the live tree, verify any delegated finding, and report only the state that still exists at handoff.
- Delegation is optional. Use it only when the operator permits it and the work can be split without losing the context needed for correctness. No task requires a swarm, standing team, role count, vendor, or launcher.
- Give one writer ownership of each shared file or tightly coupled surface. Coordinate overlapping work before editing and preserve unrelated worktree changes.
- A plan, issue, agent transcript, or prior audit is orientation, never proof that code is correct or work is complete. Acceptance comes from the current source, authoritative evidence, and the gates that exercise the changed behavior.
- Make reversible choices from the repository when they stay within the requested scope. Do not use autonomy to broaden authorization, publish externally, write live AEAT systems, or discard another contributor's work.
- Re-read affected files and the current diff before acting on a finding or handing work off; concurrent work can invalidate an earlier inventory.
- Report blockers precisely. Pre-existing failures remain visible, but they do not justify hiding a regression introduced by the current change.

## Handoff

A handoff states the outcome, changed surfaces, validation run with exit status, and any remaining risk. Agent topology, campaign history, and private scratch reasoning are not project facts and do not belong in source code or durable documentation.

---
name: aeat-architecture-boundaries
trigger: always_on
---

# AEAT architecture boundaries

## Placement and dependency direction

- Put Python application code under `src/cadrumo/`; do not create parallel top-level implementations or ad-hoc import roots.
- Preserve the accepted dependency direction: domain code is independent of adapters; application services coordinate domain behavior; inbound, outbound, persistence, entrypoint, and core responsibilities remain separate.
- Put every Python test below the narrowest owning `tests/` directory, never beside implementation modules as a naked `test_*.py`.
- Keep the CLI root surface to `config` and `app`; extend the established hierarchy instead of adding a third root family.

## Canonical definitions and imports

- Every public symbol has one canonical definition in a semantically named, non-underscore module.
- Consumers import directly from that defining module. This applies to production code, tests, development tooling, plugins, dynamic imports, and type-only imports.
- Package `__init__.py` files are inert namespace markers. Do not add exports, lazy maps, `__getattr__`, import forwarding, initialization side effects, or compatibility surfaces.
- Do not create facade modules, re-export layers, alias modules, forwarding wrappers, duplicate definitions, or cross-package imports from private underscore modules.
- Registry binding or resolver families live in their own public defining modules under `domain/calculations/registry/`, with their typed model, validator, and dispatch enrollment colocated at the owning boundary.

## Changes

- Relocate a symbol atomically: create the canonical definition, update every consumer and dynamic reference, delete the old definition or forwarding path, then run import-boundary and owning tests.
- Do not keep a transitional shim unless a released public compatibility floor explicitly requires it under `no-legacy-compatibility`.
- Production code, tests, configuration, and user documentation must stand on their own. Do not embed Vaultspec paths, rule slugs, plan or audit identifiers, step numbers, agent roles, or campaign state in them.

Authority: accepted import-centralization architecture decision and the current package-boundary tests.

---
name: aeat-calculation-aggregation
trigger: always_on
---

# AEAT calculation aggregation

## One aggregation mechanism

- Every registry aggregate resolves through the canonical typed aggregation mechanism. Do not add construct-name branches, modelo-specific `if` trees, substring dispatch, or a second summation path.
- An aggregation declaration identifies its source family explicitly and is enrolled in the shared resolver dispatch. Unknown, ambiguous, or structurally invalid declarations fail validation.
- `pull`, calculation, preview, and filing consume the same compiled aggregation semantics. No caller may reinterpret or partially reproduce the registry declaration.

## Source eligibility

- A source is included only when the registry relationship proves it belongs to the aggregate for the active revision and filing context.
- Missing source data and a proven zero are distinct states. Do not coerce absent, deferred, advisory, or unsupported inputs to zero in a filing-grade total.
- Deferred or advisory sources may produce diagnostics, but must not silently contribute to a complete total.
- Sign, rounding, currency, and period behavior come from the owning typed contracts; aggregation code must not infer them from field names or presentation labels.

## Verification

Exercise at least one positive multi-source case, exclusion cases, missing/deferred source behavior, and parity between pull and calculation. Tests must use the real resolver and compiled registry rather than a mocked substitute.

---
name: aeat-calculation-grounding
trigger: always_on
---

# AEAT calculation grounding

## Filing-grade authority

- A filing-affecting formula, rate, threshold, classification, or relationship must be grounded in the official AEAT/BOE authority that governs the exact modelo, revision, period, territory, and taxpayer conditions.
- Cite the specific provision, official instruction, record design, schema, or worked example used. A generic landing page, search result, third-party summary, or another year is not sufficient authority.
- Preserve provenance from source capture through the compiled registry, calculation result, explanation, and filing handoff. A value without traceable authority cannot be promoted to filing grade.
- Load behavior through the validated registry authority. Raw TOML inspection is useful for diagnosis but does not establish compiled behavior.

## Implementation

- Encode legal variation as typed registry data or a shared domain mechanism, not as duplicated modelo-specific branches.
- Keep applicability, units, sign, rounding, temporal window, dependencies, and exclusions explicit. Do not infer law from labels or field numbering.
- A total is complete only when every required component is present or explicitly classified by the governing contract. Suspicious absence must remain visible under `no-silent-under-declaration`.
- Cross-check representative live inputs against an independent official example or separately implemented oracle where one exists. Expected values copied from the implementation under test are not independent evidence.

## Change evidence

For a calculation change, retain the authoritative source reference, the registry or code location that carries it, and focused tests covering the normal case plus material boundaries and exclusions. If the official evidence is ambiguous, keep the capability advisory or unsupported rather than guessing.

---
name: aeat-cli-contract
trigger: always_on
---

# AEAT CLI contract

## Command surface

- The root command families are `config` and `app`. Commands extend the established subject hierarchy and do not create aliases or parallel spellings.
- The subject is positional where the hierarchy already makes it the command target. Options represent modifiers or explicit parameter loci; do not encode the same concept both positionally and as an option.
- Use stable transport tokens and machine-readable identifiers at the CLI boundary. Localized presentation text is output, never an input protocol.
- Local file ingestion uses the subject's `import --file` flow, for example `aeat config profile censo import --file ...`; do not revive retired `file` command families.

## Behavior

- Commands are deterministic and idempotent where they mutate local configuration. Refuse ambiguous state instead of guessing.
- User-facing notices go through the established notice/output channel. Do not mix diagnostics with structured output or write directly to arbitrary streams.
- Parse, validate, and normalize at the boundary, then call the same application service used by non-CLI entrypoints. The CLI must not carry a second business implementation.
- Help, completion, examples, and generated CLI reference derive from the live command tree. Do not maintain hand-copied inventories.

## Verification

Test the live parser and command registration, including success, refusal, idempotency, output channel, and machine-readable form. When changing a command, update its generated reference through the owning CLI generator rather than editing generated output.

---
name: aeat-documentation
trigger: always_on
---

# AEAT documentation

## User-facing documentation

- Write concise, outcome-oriented documentation in the user's language. State prerequisites, exact commands, observable results, failure behavior, and recovery where those facts matter.
- Use the product name Cadrumo consistently. Use AEAT names, Spanish domain terms, and command tokens exactly as the product exposes them; do not invent synonyms for canonical concepts.
- Keep each fact in one authoritative home. Link to that home instead of duplicating command inventories, schemas, legal claims, or status across documents.
- Generated API and CLI references are owned by their generators. Change the source or generator, regenerate, and verify the diff; never hand-edit generated reference files.
- Examples must be safe, runnable, and free of credentials, taxpayer data, machine-specific paths, and stale campaign state.

## Evidence and licensing

- Legal and filing claims cite the applicable official source. Technical claims identify the live code or generated reference that establishes them.
- External research is paraphrased and license-clean. Do not copy substantial text, diagrams, or examples whose reuse rights are unclear.
- Reviews check terminology, command accuracy, links, safety, and consistency with the live product. No document requires a particular number or topology of reviewers.

## Repository separation

User documentation must not explain internal Vaultspec workflow, agent roles, plan steps, audit identifiers, or rule slugs. Architecture and implementation records belong in the vault; production and user documentation remain self-contained.

---
name: aeat-ledger-contract
trigger: always_on
---

# AEAT ledger contract

## Monetary semantics

- Store an amount as its non-negative magnitude and carry economic direction in the owning typed direction field. Do not encode the same direction a second time in the numeric sign.
- Currency, precision, rounding, tax category, period, and counterparty identity remain explicit. Do not infer them from descriptions, account names, or UI placement.
- A derived balance or tax total is reproducible from immutable ledger facts and the active registry authority. Corrections append a new revision or reversal; they do not erase the evidence chain.

## Evidence and classification

- Evidence attached to a ledger revision is persisted as encrypted bytes with its integrity and provenance metadata. A path, URL, filename, or plaintext cache is not the evidence.
- IVA categories come from the canonical category set. Importers map external values into that set and refuse unknown or ambiguous classifications.
- Participation, ownership, and allocation values are derived through the canonical typed relationship mechanism. Do not duplicate percentages in unrelated records or silently normalize an inconsistent total.
- Missing evidence, unknown classification, and a genuine zero are distinct states and remain distinguishable through calculation and filing handoff.

## Verification

Tests cover sign/direction invariants, currency and rounding boundaries, encrypted evidence round trips, immutable revision behavior, classification refusal, and parity between ledger-derived and filing-facing totals.

---
name: aeat-local-execution
trigger: always_on
---

# AEAT local execution

- Run repository commands from the owning worktree and use the environment declared by the project. Prefer `uv run ...` for Python tools and `rg`/`rg --files` for search.
- Use PowerShell-native quoting and path handling on Windows. Do not publish Unix-only command recipes as the sole project workflow.
- Validate the narrow changed surface first, then the owning subsystem, then broader gates in proportion to risk. Re-run dependent commands sequentially when concurrent runs could contend for the same cache, database, port, or generated output.
- Preserve the actual command, exit status, and complete failure identity. A truncated excerpt, passing retry without explanation, or background launch is not evidence of success.
- Use isolated temporary locations for destructive or detector-teeth checks. Resolve and verify exact paths before delete, move, overwrite, or cleanup operations.
- Do not substitute a mocked service for a repository gate that claims to exercise the real integration. If an external dependency is unavailable, report that limitation explicitly.

---
name: aeat-locales-cli
trigger: always_on
---

# AEAT locale and CLI language contract

- Locale changes are performed through the canonical CLI workflow and catalogue implementation, not by editing generated catalogues or maintaining a parallel translation path.
- The supported locale set is the live product set. Each supported locale contains a real translation for every required key; copying the source text or filling placeholders does not satisfy coverage.
- CLI help, notices, errors, and model or registry presentation use the same canonical keys and catalogue. Transport tokens, identifiers, enum values, and stored data remain stable and untranslated.
- A concept has one canonical translation key. Reuse it across revisions when continuity is proven; create a distinct key when legal meaning differs.
- Do not restore a retired command, locale family, or compatibility alias to make an old test or document pass.

Verify catalogue completeness, source-key parity, fallback/refusal behavior, and live CLI rendering for every supported locale through the owning tests.

---
name: aeat-naming
trigger: always_on
---

# AEAT naming

## Domain language

- Use the official Spanish tax-domain term for public concepts and stable product language for technical concepts. Names describe legal or business meaning, not the current implementation trick.
- A public type, command, registry key, or file family uses one canonical stem. Avoid synonyms, abbreviations without domain currency, English/Spanish duplicates, and aliases kept only for old callers.
- Modelo identifiers use the canonical typed modelo representation; casilla, revision, period, and legal-reference identifiers keep their established structured forms.
- CLI verbs follow the live hierarchy. For local censo ingestion, use `aeat config profile censo import --file ...`, not a parallel `file` command.

## Files and modules

- Public modules are semantically named and define the symbols consumers import from them. Leading-underscore modules are private to their package and are not cross-package APIs.
- A filename, class, and registry family should reveal the same responsibility. Do not use generic buckets such as `utils`, `helpers`, `common`, or `misc` for domain behavior.
- Renames are atomic across code, tests, dynamic references, documentation, and generated outputs. Delete the displaced name unless an explicit released compatibility floor requires it.

---
name: aeat-no-destructive-git
trigger: always_on
---

# No destructive git commands

## Absolute prohibition

Never run a git command that can discard, rewrite, or relocate work that is not
yours to move. These are forbidden outright, with no exception and no "safe"
variant:

- `git stash` in every form, including `push`, `pop`, `apply`, `drop`, `clear`,
  and `save`. Stashing removes another contributor's in-flight edits from the
  working tree, and popping against a moved `HEAD` writes conflict markers into
  source files.
- `git reset` (`--hard`, `--mixed`, `--soft`), `git restore`, and
  `git checkout -- <path>` used to discard working-tree or index changes.
- `git clean` in every form.
- `git rebase`, `git cherry-pick`, `git revert`, `git commit --amend`, and any
  history rewrite (`filter-branch`, `filter-repo`, `push --force`).
- `git branch -D`, `git worktree remove --force` on a worktree you did not
  create, and any deletion of a ref you do not own.
- Removing or bypassing a lock file such as `.git/index.lock`. A held lock means
  another process is mid-operation; wait, or report it.

## Why

A dirty worktree is another contributor's work in progress, and this repository
is edited concurrently. A stash/pop cycle in one session removed a contributor's
uncommitted edits and, on restore against an advanced `HEAD`, wrote
`<<<<<<<`/`=======`/`>>>>>>>` markers into nine tracked source files, breaking
every module that imported them. Nothing warned before the damage; the loss was
found only by a later import smoke test. No reversibility argument survives
that: the operations above destroy state that exists nowhere else.

## Instead

- To read a committed version, use a read-only command that writes nothing:
  `git show HEAD:<path>`, `git diff`, `git log`, `git cat-file`.
- To compare against a baseline, create a separate worktree
  (`git worktree add --detach <dir> HEAD`) and read from it. Never mutate the
  working tree to get a clean state.
- To test whether a local edit causes a failure, copy the file aside and restore
  it by copy, or evaluate the question from `git diff` output.
- If work genuinely must be set aside, stop and ask the operator. Removing
  someone's uncommitted changes is their decision, never the agent's.

## Scope

This binds every agent and every session, including when a command appears to
target only files the agent itself wrote: a path-scoped destructive command
still acts on whatever the working tree holds at that moment, which may have
changed. Commit, push, merge, and any other command that alters shared or
external state still require an explicit operator request.

---
name: aeat-quality-gates
trigger: always_on
---

# AEAT quality gates

## What a gate must prove

- A gate exercises the real authority path, parser, compiler, resolver, calculation, or serializer whose contract it names. Mocking the production behavior under test is not acceptance evidence.
- Test outcomes and invariants, not implementation trivia, frozen corpus counts, campaign milestones, or the mere presence of a string.
- Positive tests prove the supported path. Negative tests prove malformed, ambiguous, unsupported, stale, and incomplete inputs fail closed at the owning boundary.
- Round-trip tests compare canonical typed meaning, including absence, zero, precision, ordering, provenance, and revision identity; lossy equality is not sufficient.

## Detector teeth

A gate that protects a declaration or generated relationship must demonstrate that a representative defect is detected. Use an isolated fixture, temporary registry tree, or explicit test input; do not monkeypatch production modules globally or mutate the contributor's working tree. The defect proof and the normal path must both pass in the same test suite.

## Layered validation

- Keep focused unit and contract tests near the owning boundary, integration tests at real handoffs, and end-to-end checks for user-visible flows.
- Overlapping gates are justified when they catch distinct failure modes. Remove duplicate tests that assert the same implementation detail without adding detection value.
- Generated-reference checks compare generated output with the committed artifact through the owning generator.
- A change is not complete while it introduces a new lint, type, test, schema, or Vaultspec failure. Pre-existing unrelated failures are reported separately with evidence.

---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority flow

## Single authority path

- Registry source data is compiled, validated, and published through `ValidatedRegistryAuthority` and the established loader. Filing, calculation, pull, support reporting, and development diagnostics consume that authority rather than parsing raw files independently.
- Registry source files are declarations, not a second runtime API. Direct file reads may diagnose source shape but cannot establish filing-grade behavior.
- Public registry symbols are defined in semantically named public modules and imported directly. A curated re-export layer is still a facade and is forbidden; package initializers remain inert.

## Registry identity and selection

- Modelo identity uses the canonical typed modelo representation. Revisions, filing periods, legal windows, and territorial or taxpayer applicability are explicit and validated.
- Select a revision from the applicable law and filing context, never from filename ordering, newest-available fallback, or string comparison.
- Fragmented declarations compile into one validated revision. Duplicate ownership, missing fragments, ambiguous casilla identity, invalid references, or conflicting declarations fail before publication.
- Values used by calculations come from typed registry fields or their canonical configuration mechanism. Do not scatter regulatory constants through runtime code.
- Cross-revision continuity is accepted only when the chain and its evolutions are grounded. A repeated box number or similar label is candidate evidence, not identity.

## Publication and failure

- The authority publishes only a completely validated snapshot and never exposes a partially constructed generation.
- Cache identity includes the authoritative source state and invalidates on relevant source or evidence changes. Callers receive isolated validated snapshots rather than mutable shared registry state.
- Unsupported or insufficiently grounded capability fails closed or remains explicitly advisory. It must not be upgraded by a consumer-side fallback.

Authority: accepted registry/compiler and import-centralization architecture decisions plus the live registry authority tests.

---
name: aeat-registry-bindings
trigger: always_on
---

# AEAT registry bindings

- Each relationship family has a typed declaration, a typed validator enrolled in the canonical dispatch table, and a resolver at its owning public module.
- Validation rejects unknown family names, invalid selectors, ambiguous targets, incompatible revisions, missing provenance, and unresolvable legal references. Do not accept a generic mapping and defer interpretation to callers.
- Aggregation source families use the canonical typed aggregation enum and resolver. A binding must not introduce a private summation path.
- Source taxonomy distinguishes filing-grade, advisory, deferred, unsupported, and absent states. Consumers preserve that classification instead of converting it to a boolean or zero.
- Binding provenance identifies the registry declaration and governing authority and survives into the resolved result and explanation.
- Relation prefill is derived from the validated relationship and active filing context. User-supplied or imported values never silently override a higher-authority binding.
- New binding families follow the existing defining-module pattern and are exercised through registry validation, positive resolution, ambiguity/refusal, and consumer parity tests.

---
name: aeat-vaultspec-centralisation
trigger: always_on
---

# AEAT Vaultspec centralisation

## Authority and sync

- `.vaultspec/rules/` and `.vaultspec/skills/` are the authored project sources. Provider directories such as `.codex/rules/`, `.agents/skills/`, `.claude/`, `.gemini/`, and `.agent/` are generated destinations.
- Edit, add, or remove project governance only at the Vaultspec source, then preview and run `vaultspec-core sync`. Do not hand-edit provider copies.
- Files ending in `.builtin.md` and built-in Vaultspec skills are installation-owned. Never edit, delete, fork, or shadow them from the project.
- Use the Vaultspec CLI for vault lifecycle metadata, status, links, stamps, archive operations, and generated indexes. Body-only edits still require the owning focused check afterward.

## Context budget

- Do not add a rule for a one-off defect, campaign, plan step, tool preference, or fact already enforced by code. Codification is retired for this project; strengthen the owning gate, schema, type, generator, or existing rule instead.
- A rule states stable, enforceable invariants and the boundary they protect. Exclude dated inventories, frozen counts, migration history, agent topology, repeated examples, and long command transcripts.
- A skill contains only a repeatable workflow whose procedural detail is genuinely needed at invocation time. Move optional detail into referenced resources; remove a skill when normal repository instructions are sufficient.
- Provider-global skills and rules must be narrowly triggered and useful across projects. Project-specific behavior belongs here, not in a user's global context.

## Separation

- Do not create private agent memory or a parallel policy directory.
- Production code, tests, configuration, and user documentation do not cite Vaultspec documents, rule slugs, plan steps, audit names, or agent metadata. Existing citations are migration debt; do not add new ones.
- Preserve existing rule slugs while they are referenced by current gates or source. Rename or consolidate only with an explicit repository-wide citation migration and validation.

---
name: aeat-worktree-safety
trigger: always_on
---

# AEAT worktree safety

- Work only in the assigned worktree and confirm its root and branch before a material change.
- Treat every pre-existing modification as another contributor's work. Inspect before editing, preserve unrelated changes, and never use destructive reset, checkout, clean, or broad restore operations to obtain a tidy tree.
- Before moving or deleting recursively, resolve the exact absolute targets and verify they remain inside the intended directory. Prefer recoverable operations when practical.
- Use one writer for a shared file or tightly coupled generated surface. Re-read the file and diff before applying a stale patch.
- Stage or report only the files owned by the requested change. A dirty worktree is not permission to absorb, reformat, fix, commit, or discard unrelated work.
- Do not commit, push, merge, publish, or alter external project state unless the operator requested that action or the active approved workflow explicitly requires it.

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
name: modelo-export-mirrors-official-structure
trigger: always_on
---

# Modelo export mirrors official structure

- A modelo export derives its record order, field positions, widths, repetitions, encodings, and conditional sections from the official record design or schema for the selected revision.
- One canonical export builder and formula path owns both preview and emitted filing data. Do not maintain a second hand-built serializer or recompute values differently for display.
- Every exported field maps to a validated registry concept and carries the same typed meaning, formatting, sign, rounding, and provenance used by calculation.
- Fixed-width completeness is value-aware: distinguish absent, required blank, permitted blank, zero, and populated values. Padding a missing required value does not make a record complete.
- Conditional records and repeated groups are emitted only when their official conditions and cardinalities are satisfied. Reject overflow, truncation, illegal characters, inconsistent totals, and unsupported revision layouts.
- Generated export references and fixtures are CLI-owned. Change the source/generator, regenerate, and verify byte-for-byte or schema parity against the official structure; do not hand-edit generated artifacts.
- Tests cover official examples where available, boundary widths, encoding, required absence, conditional sections, totals, and parse/serialize semantic round trips.

---
name: no-legacy-compatibility
trigger: always_on
---

# No unowned legacy compatibility

- Before the project declares a released public compatibility floor, remove displaced commands, imports, schemas, configuration keys, aliases, facades, wrappers, and data shapes in the same change that replaces them.
- A passing old caller or test is not by itself a reason to preserve a legacy surface. Update repository consumers to the canonical contract and delete the old path.
- After a public compatibility floor exists, compatibility requires an explicit owner, supported-version window, migration or upgrader path, deprecation signal, and removal condition. Keep it at the boundary; do not duplicate domain implementations.
- Persistent data migrations are forward, deterministic, idempotent, and tested from every supported stored version. Silent coercion or fallback from an unknown shape is forbidden.
- Do not create a shim merely to stage an internal relocation. Canonical definitions and all consumers move atomically under `aeat-architecture-boundaries`.

---
name: no-silent-under-declaration
trigger: always_on
---

# No silent under-declaration

## Preserve uncertainty

- Missing, unknown, unsupported, deferred, advisory, not applicable, and proven zero are distinct states. Do not collapse any of them to zero, empty text, false, or a complete total.
- A filing-grade result is complete only when every legally required input and dependency is present, validated, and covered by authority for the active filing context.
- Suspicious zeros or absences at filing-bound fields produce a structured advisory or refusal with modelo, revision, field, source family, and reason. Diagnostics must reach the user-facing handoff.
- A local calculation or prefill is not an official AEAT value. Label its origin and authority honestly.

## Coverage and suppression

- Compare independent sources where the product has both an external value and an engine-derived value. A disagreement remains visible until resolved; neither side silently wins.
- Suppression is explicit, narrowly keyed, classified, and reviewable. It must state why the condition is safe or non-applicable and must not use a broad model, prefix, or count-based exemption.
- New declarations are covered by semantic gates that detect unclassified filing-bound gaps. Frozen corpus counts and baseline-only ratchets do not prove completeness.
- Advisory capability cannot be promoted to filing grade by a UI, exporter, or downstream consumer.

## Tests

Exercise genuine zero, missing input, unsupported authority, deferred source, mismatch, valid suppression, invalid suppression, and end-to-end diagnostic propagation through the real registry and calculation paths.

---
name: sensitive-financial-data-secure-storage-only
trigger: always_on
---

# Sensitive financial data uses secure storage only

## Storage and transport

- Taxpayer, credential, banking, ledger, invoice, filing, and evidence payloads are stored only through the project's approved encrypted persistence boundary.
- Do not write sensitive payloads to source files, fixtures, logs, exceptions, command history, caches, plaintext databases, temporary files, generated references, vault documents, or agent transcripts.
- Persist evidence as encrypted bytes with integrity and provenance metadata. A filesystem path or remote URL is not a secure stored copy.
- Secrets come from the approved secret boundary and are never committed, echoed, serialized with domain data, or passed in command-line arguments when a safer channel exists.
- Off-host transfer requires the explicitly approved encrypted integration and the minimum necessary fields. Do not upload real financial data to search, AI, analytics, paste, or debugging services.

## Execution safety

- Tests use synthetic or irreversibly anonymized data. A production-shaped fixture must still contain no real identity or secret.
- Logs and user-visible diagnostics expose stable identifiers and remediation, not raw payloads. Redaction happens before serialization or transport.
- Local development and automated agents must never submit, amend, sign, or otherwise write a live AEAT filing. Live remote behavior is read-only unless the operator gives explicit transaction-specific authorization through the product's guarded workflow.
- Cleanup of decrypted material is fail-safe and verified. If a workflow cannot guarantee secure lifetime and disposal, it must refuse the operation.

Verification covers encryption at rest, redaction, temporary-material cleanup, secret handling, and refusal of unauthorized live writes.

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

- **Gateway-only, CLI-first:** `vaultspec-core sync`,
  `vaultspec-core spec <resource> sync`, and the above-Step plan verbs
  (`tier promote/demote`, `wave`, `phase`, `epic intent`). The `discover`/`invoke`
  gateway also reaches these, but `invoke`'s destructive annotation forces host
  confirmation on every call, so the CLI is the better default even when connected.
- **CLI-only:** `vaultspec-core vault feature index`,
  `vaultspec-core spec mcps add/remove/sync`, and `vaultspec-core uninstall` have no MCP
  path at all; run them through the CLI.

For anything else, the `discover` tool and the bundled CLI reference
(`.vaultspec/reference/cli.md`, locally resident) are the catalogs of every command,
option, argument, and exit code.

Where the vaultspec MCP server is not connected, the `vaultspec-core` CLI verbs carry
every operation; the bundled CLI reference is the catalog.

## CLI fallback

- Run `vaultspec-core <cmd>`, or `uv run --no-sync vaultspec-core <cmd>` in uv
  environments; `--target DIR`, `--dry-run`, `--json`, `--force`, and `<cmd> --help`
  cover targeting, previewing, and the full flag and exit-code reference.
- Sync-shaped results (`vaultspec-core install`, `vaultspec-core sync`,
  `vaultspec-core spec <resource> sync`, `vaultspec-core migrations run`) read with one
  vocabulary - `created`, `updated`, `unchanged`, `removed`, `restored`, `skipped`,
  `failed`; `unchanged` is a successful no-op, `skipped` carries a reason, only `failed`
  stops the pipeline.

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
  multiple ADRs, audits, references, or research documents disambiguates each with an
  optional topic infix - `yyyy-mm-dd-<feature>-<topic>-<type>.md` - scaffolded through
  the owning verb's `--topic` flag (`vaultspec-core vault add` for adr, audit,
  reference, and research only), never by hand-picking a filename.

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
  - *Content:* A mechanical log, not a narrative. One `A`/`M`/`D`/`R` line per path
    touched under `## Changes`, plus the machine-filled `## Scope`. No prose: the Step
    row states the intent and the commit carries the diff. A `## Notes` section is added
    only on exception (data loss, skipped work, a scaffold left in code, a persistent
    failure) and is otherwise omitted.
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
  - *Content:* The deduplicated union of the Phase's Step Record `## Changes` lines, in
    the same mechanical grammar. Not a retelling of the Step Records.
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
body_hash: 'sha256:...'
related:
  - '[[related-file]]'
---
```

`modified:` is a CLI-maintained last-modified stamp: set equal to `date:` at scaffold,
refreshed by every mutating verb and by `vaultspec-core vault check all --fix`, parsed
leniently but rewritten to the canonical quoted `yyyy-mm-dd` form, never hand-edited.

`body_hash:` is the machine-filled fingerprint of the document body that `modified:`
attests, written beside the stamp by the same verbs. It is what makes an unstamped body
edit detectable: the reconciliation check compares the live body against this value, and
file timestamps are never consulted. Never hand-write or hand-edit it - a value the
author did not compute is the only way the field can lie. A document that carries no
`body_hash:` simply makes no claim about its body and is reported clean until a verb or
migration seeds it.

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

The frontmatter fields `modified:` and `body_hash:` belong to the same machine-filled
class but carry no template placeholder: their values are derived at write time - from
the clock and from the rendered body - so they are injected by the owning verb rather
than substituted into a template token.

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

  - Optional topic infix (adr, audit, reference, research only):
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
</vaultspec>
