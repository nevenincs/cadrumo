---
tags:
  - '#exec'
  - '#profile-setup-flow'
date: '2026-07-24'
modified: '2026-07-24'
step_id: 'S25'
related:
  - "[[2026-07-23-profile-setup-flow-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace profile-setup-flow with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S25 and 2026-07-23-profile-setup-flow-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Convert the apoderado verb into a door that hosts the flow pages while routing writes to the ApoderadoService namespace, never profile facts and ## Scope

- `src/cadrumo/entrypoints/cli/_config/_apoderado.py` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Convert the apoderado verb into a door that hosts the flow pages while routing writes to the ApoderadoService namespace, never profile facts

## Scope

- `src/cadrumo/entrypoints/cli/_config/_apoderado.py`

## Description

<!-- Succinct line-by-line list of steps executed. Use imperative language, mirroring git commit summary lines. -->

- Host the apoderado `configure` interaction as a two-page flow (represented-party identifier, scope checkboxes) over an in-memory-only flow state in modify mode, checkpoint unavailable in both modes — the substrate's create checkpoint binds to profile-fact writes, exactly the store apoderamiento must never touch.
- Keep the flags path non-interactive for automation callers; commit both transports through the one `ApoderadoService.configure` write (no parallel write path; scope validation stays single-authority in `parse_scope_tokens`).
- Prove profile facts untouched: both pages bind no profile domain key, and a before/after record snapshot over real storage asserts byte-identical facts around a configure.
- Map the no-console refusal to a verb-specific hint naming the `--represented-nif` and `--scope` flags; enumerate the accepted scope codes live from the service catalogue in the empty-scope refusal.
- Move represented-party identity validation into `ApoderadoService.configure` as the single authority both transports pass, raising a typed registered error that carries no raw identifier; retain the flow-page validator as an early-refusal courtesy over the same law.

## Outcome

Landed as `0dfda24fe3` (door) and `66d1c7fcc6` (revision). First review: clean pass architecturally with three operator-facing mediums (misdirecting console refusal, scope refusal without the accepted set, flags-path identifier unvalidated); re-review verified all three closed with passing regressions and a clean caller sweep — every remaining `configure` caller and documented sequence uses a valid identity, and the docs' placeholder `11111111H` was confirmed a valid NIF. Zero new keys in the original; the revision minted three refusal keys, all scanner-visible with honest in-code default renderings pending the catalogue landing. Conformance 348, auth 18, door 8, error-registry gates green.

## Notes

<!-- Incidents. Data loss. Difficulties; persistent failures. Skipped work. Scaffolds left in code. Failures. -->

- The prior service tests passed only because nothing validated their placeholder identifiers (`B1`, `NIF-A`); adding the validation authority exposed and fixed that latent test weakness.
- Bespoke prompt loop: none existed — the prior verbs were flag-based, so the plan row's deletion clause is vacuous for apoderado; recorded rather than silently skipped.
- Review lows, ledger-bound: the represented-party prompt says NIF while NIE and CIF are accepted (format hint and failure copy carry the full set, so the operator is not misled); the declarative answers model is documented as a slot, with the service as the validation authority; the door integration tests exhibit the known registry loader-cache race under parallel pytest (pre-existing, sequential runs clean).
