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

- Put product Python code under its owning `src/` package and development-only registry compilation, authoring and migration tooling under `dev/registry/`. Runtime must not import the development compiler. Do not create parallel implementations or ad-hoc import roots.
- Preserve the accepted dependency direction: domain code is independent of adapters; application services coordinate domain behavior; inbound, outbound, persistence, entrypoint, and core responsibilities remain separate.
- Put every Python test below the narrowest owning `tests/` directory, never beside implementation modules as a naked `test_*.py`.
- Keep the CLI root surface to `config` and `app`; extend the established hierarchy instead of adding a third root family.

## Canonical definitions and imports

- Every public symbol has one canonical definition in a semantically named, non-underscore module.
- Consumers import directly from that defining module. This applies to production code, tests, development tooling, plugins, dynamic imports, and type-only imports.
- Package `__init__.py` files are inert namespace markers. Do not add exports, lazy maps, `__getattr__`, import forwarding, initialization side effects, or compatibility surfaces.
- Do not create facade modules, re-export layers, alias modules, forwarding wrappers, duplicate definitions, or cross-package imports from private underscore modules.
- Registry domain declarations and runtime resolvers belong to their public defining domain modules; source compilation and corpus validation belong to the development compiler. Enroll each implementation at its owning dispatch boundary without moving development dependencies into runtime.

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
- Cite the specific provision, official instruction, record design, schema, or worked example used. A generic landing page, search result or third-party summary is not sufficient grounding. Preserve source-year and applicability scope; projection does not turn an earlier source into newly reviewed target-year evidence.
- Preserve provenance from source capture through the compiled registry, calculation result, explanation, and filing handoff. A value without traceable authority cannot be promoted to filing grade.
- Runtime calculations consume validated published authority. Authoring and repair use the candidate-inspection and validation boundaries defined in `aeat-registry-authority-flow`; a missing published generation must not prevent evidence-backed source repair.

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
- Registry task briefs and handoffs name the target boundary: source edit, candidate verification, live source installation, authority publication or runtime adoption. State deliverables and measurable acceptance for the requested boundary; do not use ambiguous "live", "validated" or "done" for all of them.
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
- A tool wait window is not a process failure. Resume the owned session to obtain its final result, and confirm the intended tests actually ran; default marker selections may exclude integration tests.
- When proving a source transformation, identify both source and interpreting-tool dependencies. Use stable captured inputs and revalidate receipts before application; do not test a copied registry with changing compiler code and call the result current.
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
- To test whether a local edit causes a failure, reproduce it in an isolated
  fixture or snapshot, or evaluate the question from `git diff` output. Do not
  temporarily overwrite shared files and later restore a potentially stale copy.
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
- Round-trip tests compare canonical typed meaning, including absence, zero, precision, contract-defined ordering, provenance, and revision identity. Mapping-key serialization order is not sequence order; exclusions require an explicit representation contract and independent checks of the meaning they omit.
- Hydrated equivalence does not prove compact authoring. Delta acceptance independently measures redundant payload and overrides, unresolved shapes, coverage and idempotence. Discover the complete live inventory; a successful no-op or representative modelo is not registry-wide acceptance.

## Detector teeth

A gate that protects a declaration or generated relationship must demonstrate that a representative defect is detected. Use an isolated fixture, temporary registry tree, or explicit test input; do not monkeypatch production modules globally or mutate the contributor's working tree. The defect proof and the normal path must both pass in the same test suite.

## Repository enumeration

Never use Git commands, the Git index, tracked-file lists, commit history, or branch state as the authority for a quality, completeness, parity, or packaging gate. Derive the expected set in-process from the current source tree and its checked-in inclusion, exclusion, catalogue, or schema policy.

- Good: enumerate current files with `dev.source_tree.repository_files`, then project them through the packaging or corpus policy and compare that set with the built artifact.
- Good: use Git in an explicitly named release workflow to inspect or publish a commit, where commit identity itself is the subject—not as a test oracle.
- Bad: define expected wheel members, registry completeness, source coverage, or corpus parity with `git ls-files`, `git status`, or a commit diff.

## Layered validation

- Keep focused unit and contract tests near the owning boundary, integration tests at real handoffs, and end-to-end checks for user-visible flows.
- Overlapping gates are justified when they catch distinct failure modes. Remove duplicate tests that assert the same implementation detail without adding detection value.
- Generated-reference checks compare generated output with the committed artifact through the owning generator.
- A change is not complete while it introduces a new lint, type, test, schema, or Vaultspec failure. Pre-existing unrelated failures are reported separately with evidence.
- Apply the stage-specific acceptance boundaries in `aeat-registry-authority-flow`. Name the failed invariant and affected input, distinguish new or worsened findings from unchanged baseline findings, and do not substitute an aggregate red/green status for that classification.

---
name: aeat-registry-authority-flow
trigger: always_on
---

# AEAT registry authority flow

## Source, candidate and runtime boundaries

- Authored source is the registry data physically stored on disk. A staged candidate is an isolated proposed replacement; it is not installed source or published authority.
- Development authoring uses the canonical compiler, parser and hydrator. `inspect_authoring_candidate()` exposes typed candidate components, source/evidence fingerprints and validation findings; those components are not a `ValidatedRegistryAuthority`. This path is available when inspecting unpublished edits, including before the first publication.
- `compile_validated_authority()` establishes full candidate validation. Successful compilation is not publication. Product runtime consumes the published authority through the canonical reader; it must not compile mutable source or fall back to raw TOML.
- Raw-file comparisons may measure authored structure and duplication. Claims about hydrated meaning use canonical typed loading; claims about runtime behavior use the published generation. Never invent a second loader to cross these boundaries.

## Delta authoring and hydration

- Store a baseline plus genuine field/value differences, new members, explicit removals and required ordering/scope metadata. Do not repeat a whole row or family merely because one field or evidence reference changes.
- An omitted override inherits; an explicit removal deletes. Empty values, false, zero, sequence order and revision-specific assertions retain their typed meaning. A changed default must not silently change inherited provenance.
- Storage selectors and baselines address payload, not legal identity. Missing `continuidad_id`, a lower capability grade or a changed physical representation is not by itself a prohibition on lossless storage reuse.
- Preserve real continuity, review and capability claims with their original scope. Do not invent evidence, advance a review date or promote capability because payload is shared. A failed migration is a tool diagnostic, not a new legal no-predecessor declaration.
- Conversion is modelo-independent and discovers authored revisions and dependencies from canonical metadata. Existing delta chains still undergo remaining-family conversion and redundant-override assessment; they are not automatically complete.

## Temporal selection

- A projected edition supplies a missing temporal coordinate from the nearest eligible authored source through the canonical resolver, backward or forward and across internal gaps. It creates no copied source edition and asserts no new target-year review.
- Resolve applicability branches, periods, ties and explicit divergences through the same typed selection contract for loaders, facts, runtime and support reporting. Do not select by lexical filenames or a consumer-specific newest-year fallback.
- The registry's canonical support declaration owns the temporal envelope. Consumers must not introduce separate floor/ceiling constants or ranges. Historical sources outside the request envelope may remain required storage baselines.
- Available projected data and eligibility for a particular operation are separate results. Preserve capability limitations without falsely treating an un-authored but resolvable edition as missing data.

## Application, publication and completion

- Prove source replacement with effective typed equivalence, independent minimality, complete assessment scope, idempotence and stable input receipts. Intentional semantic corrections need their own grounded change evidence rather than a claim of unchanged meaning.
- Report unchanged publication-readiness defects separately from defects introduced by a representation rewrite. Unrelated unchanged defects do not automatically forbid a proven source-only replacement; full publication validation remains mandatory.
- Installing source means the actual authoring tree matches the accepted candidate. Publishing means the active descriptor references the accepted content-addressed artifact. A temporary database, retained lock sidecar or passing compile is neither of those outcomes.
- Publication verifies current source/evidence/compiler receipts and never exposes an incomplete generation. Runtime and packaging checks must identify the generation they actually consume; caches invalidate on relevant input or generation changes.
- State completion separately for candidate validation, installed source, published authority and runtime/package adoption. Do not mark overall rollout complete while a required boundary remains unverified.

---
name: aeat-registry-bindings
trigger: always_on
---

# AEAT registry bindings

- Each relationship family has a typed declaration, a typed validator enrolled in the canonical dispatch table, and a resolver at its owning public module.
- Validation rejects unknown family names, invalid selectors, ambiguous targets, incompatible applicability, missing required provenance, and unresolvable legal references. Resolve inherited and projected declarations before evaluating the relationship; absent local payload is not itself a missing binding. Typed mapping-valued families are legitimate; unvalidated arbitrary mappings are not a substitute for their contract.
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
- Evaluate the hydrated selected layout, not whether that layout is fully copied into the requested edition. Storage reuse must preserve edition-local identity and conditions; it does not by itself establish filing eligibility for a projected request.
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
- Inherited baseline data is not obsolete merely because it is historical. Remove displaced duplicate payload only after proving reconstruction; retain required baselines and evidence. Keep recovery copies outside live authoring and packaging scope.
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
- Absence of an authored edition or override is not necessarily absent data: resolve canonical hydration and temporal projection first. Explicit deletions and genuinely missing taxpayer inputs must not be filled by that distinction.
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

- Private taxpayer, credential, banking, ledger, invoice, filing and associated evidence payloads are stored only through the project's approved encrypted persistence boundary.
- Public AEAT/BOE publications, public registry definitions and synthetic fixtures are not private taxpayer evidence merely because they concern taxation. They may use the repository's canonical source/corpus storage. Check content for embedded private data; never use this distinction to reclassify a real filing or secret as public.
- Do not write sensitive payloads to source files, fixtures, logs, exceptions, command history, caches, plaintext databases, temporary files, generated references, vault documents, or agent transcripts.
- Persist private evidence as encrypted bytes with integrity and provenance metadata. A filesystem path or remote URL is not a secure stored copy.
- Secrets come from the approved secret boundary and are never committed, echoed, serialized with domain data, or passed in command-line arguments when a safer channel exists.
- Off-host transfer requires the explicitly approved encrypted integration and the minimum necessary fields. Do not upload real financial data to search, AI, analytics, paste, or debugging services.

## Execution safety

- Tests use synthetic or irreversibly anonymized data. A production-shaped fixture must still contain no real identity or secret.
- Logs and user-visible diagnostics expose stable identifiers and remediation, not raw payloads. Redaction happens before serialization or transport.
- Local registry source replacement and authority publication are not AEAT filing submissions. They require the authorization and verification for their own workflow. Writing or signing a real remote filing requires explicit transaction-specific authorization through the product's guarded workflow; ordinary development authorization does not permit it.
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

# Vaultspec tools

Every `.vault/` mutation, listing, and repair goes through the owning verbs: MCP tools
when connected, else the `vaultspec-core` CLI. Bypassing them produces drift that
`check` flags. A record's body is read as a file.

## Tools

The MCP server exposes `status` (in-flight plans and next open Step), `find` (documents
and features), `create` (scaffold, batchable), `edit` (body prose, batchable),
`plan_progress` (check or uncheck Steps), `plan_edit` (author and restructure Step
rows), `log` (append a Step's ledger rows), `check` (validate and repair), and the
`discover`/`invoke` gateway to every other verb. `invoke` asks for host confirmation on
every call, so the above-Step plan verbs (`tier`, `wave`, `phase`, `epic intent`) and
`vaultspec-core sync` are better run through the CLI even when connected.
`vaultspec-core vault feature index`, `vaultspec-core spec mcps`, and `uninstall` are
CLI-only.

The bundled CLI reference, `.vaultspec/reference/cli.md`, catalogues every command,
flag, and exit code. Run `vaultspec-core <cmd>`, or
`uv run --no-sync vaultspec-core <cmd>` in uv environments; `--dry-run`, `--json`, and
`<cmd> --help` preview and explain. Sync-shaped commands report created, updated,
unchanged, removed, restored, skipped, or failed; only `failed` stops.

## Manual edits

Permitted: body prose of a scaffolded record, including the `proposed`, `accepted`,
`rejected`, or `deprecated` token in an ADR's heading (`superseded` is set by
`vaultspec-core vault adr supersede`). Policy sources under `.vaultspec/rules/`,
`skills/`, `agents/`, `hooks/`, and `mcps/` are the user's: propose changes, apply them
only on request, then run `vaultspec-core sync`. Forbidden: frontmatter, filenames, plan
structure, Step checkboxes, new `.vault/` files, and anything inside generated provider
directories.

---
name: vaultspec-discovery.builtin
trigger: always_on
---

# Discovery

Discover before changing: at each phase start, and before a session's first edit to
source or vault, at any horizon. The sequence is locate by meaning, read the epicenter
whole, confirm with grep.

1. **Locate by meaning.** Code:
   `vaultspec-rag search "<concept and domain nouns>" --type code` (narrow with
   `--language` or `--path`). Decisions:
   `vaultspec-rag search "<intent>" --type vault --doc-type adr`. Orientation: the
   discovery verbs `vaultspec-core status [target]`, `vaultspec-core vault list`, and
   `vaultspec-core vault graph` (MCP: `status`, `find`). A small, well-named module is
   listed directly.
1. **Read** the epicenter file, or the nearest existing analogue when extending a
   feature, in full.
1. **Confirm** exact symbols and insertion points with a targeted grep.
1. For decisions, also list `.vault/adr/` filtered by feature; search alone misses
   lower-ranked or opaquely named records. Search across features before narrowing:
   shared decisions can govern work under another tag. Read accepted decisions that
   cover the scope and follow their evidence links. This discovery does not itself
   require a persisted Research or Reference record.

Do not lead with broad glob or grep sweeps on a large tree; grep is the confirmation
step. Where `vaultspec-rag` is unavailable, the `vaultspec-core` discovery verbs and
grep carry the same sequence.

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

# Vault records

Every `.vault/` record belongs to one feature and is scaffolded by its owning verb: the
`create` tool where the MCP server is connected, otherwise
`vaultspec-core vault add <type> --feature <feature>`. The verb owns the filename and
the frontmatter; the author writes body prose only. The frontmatter schema, tag pair,
placeholders, and filename patterns are catalogued in
`.vaultspec/reference/vault-schema.md`; never hand-write them.
`vaultspec-core vault check all --fix` repairs drift and strips leftover template hints.

## Record types

- **Research** (`.vault/research/`) grounds a decision: claim-first findings, each with
  a re-fetchable locator, and a `## Sources` list. It frames options; it never records
  the decision. Requires nothing.
- **Reference** (`.vault/reference/`) grounds work in code: how this or another codebase
  implements the thing, as patterns with `file:line` locators, not copied code. Requires
  nothing.
- **ADR** (`.vault/adr/`) records one decision and only the decision, citing research
  and other evidence by stem, never restating it. Requires sufficient Research,
  Reference, or Audit evidence. Its heading starts `proposed`; approval, unchanged
  reuse, amendments, and supersession follow the vaultspec system section.
  `vaultspec-core vault adr supersede OLD --by NEW` owns supersession after the
  successor is accepted. Pending amendment text never replaces accepted content.
- **Plan** (`.vault/plan/`) sequences authorized work with decision coverage assessed
  under the vaultspec system section. When no costly decision is involved and no ADR
  governs, its Description records that assessment. Otherwise, `related:` lists every
  governing ADR (`--related`, repeatable, at scaffold; `vaultspec-core vault link add`
  later). Scaffold with `--tier L1..L4`; build and change structure only through the
  `plan_progress` and `plan_edit` tools or the `vaultspec-core vault plan` verbs.
  Conventions are in the hint blocks of `.vaultspec/templates/plan.md`.
- **Ledger** (`.vault/exec/`) is the mechanical log of a plan's execution, one per plan,
  append-only.
  `vaultspec-core vault exec log --feature <feature> --step S## --related <plan-stem> --row A:path`
  (the `log` tool when connected) creates it on first use and appends one
  `S## A|M|D|R path` row per path touched; `--verify` adds a check line, `--by` the
  persona, `--note` an exception (data loss, skipped work, a scaffold left in code, a
  persistent failure). Rows are written only by the verb. No narrative.
- **Audit** (`.vault/audit/`) holds findings from review or curation, one
  `### {topic} | {level} | {summary}` entry each, appended as a rolling log, with
  recommendations that name a decision for a follow-on ADR rather than making it.
  Requires the artifacts it reviews.
- **Feature index** (`.vault/index/`) is generated: the `create` and `edit` tools
  regenerate it; after CLI scaffolds run `vaultspec-core vault feature index`.

A feature that needs a second ADR, audit, reference, or research record disambiguates it
with the owning verb's `--topic` flag, never a hand-picked filename.

## Links and boundaries

- `related:` carries quoted Obsidian wiki-links (`- '[[stem]]'`), set by the owning
  verbs. Bodies carry no wiki-links and no markdown links; a source file is named in
  backticks, a code fact is cited as `path:line`.
- Vault records cite code; code never cites the vault. The `Vaultspec-Step` and
  `Vaultspec-Feature` commit trailers (`vaultspec-core vault plan trailer emit`) are the
  only link from git history to a record; emit them when the project's recent commits
  already carry them.
- Each fact has one home: research grounds, the ADR decides, the plan sequences, the
  ledger logs, the audit finds. A fact needed elsewhere is cited by stem, not restated.
</vaultspec>
