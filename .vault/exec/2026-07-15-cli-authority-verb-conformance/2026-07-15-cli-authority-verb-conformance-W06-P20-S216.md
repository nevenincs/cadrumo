---
tags:
  - '#exec'
  - '#cli-authority-verb-conformance'
date: '2026-07-28'
modified: '2026-07-28'
step_id: 'S216'
related:
  - "[[2026-07-15-cli-authority-verb-conformance-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace cli-authority-verb-conformance with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S216 and 2026-07-15-cli-authority-verb-conformance-plan placeholders are machine-filled by
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
     The Audit every amended ADR decision, including delete-only certificate cutover, atomic ledger evidence, live export routing, 18 plus 4 hashing consolidation, backend replay removal, namespace adoption, filed capture, LLM review, registry as-of behavior, and truthful duplication infrastructure, against code and objective evidence and ## Scope

- `.vault/adr/2026-07-15-cli-authority-verb-conformance-adr.md` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Audit every amended ADR decision, including delete-only certificate cutover, atomic ledger evidence, live export routing, 18 plus 4 hashing consolidation, backend replay removal, namespace adoption, filed capture, LLM review, registry as-of behavior, and truthful duplication infrastructure, against code and objective evidence

## Scope

- `.vault/adr/2026-07-15-cli-authority-verb-conformance-adr.md`

## Description

- Audit each named decision against code rather than against the record that
  claims it.
- Distinguish decisions already covered by a closed verification Step from
  those needing a fresh spot-check.

## Outcome

SATISFIED. Ten named decisions, six covered by closed verification Steps
carrying their own evidence, four spot-checked here directly.

COVERED BY CLOSED STEPS, each with a command, a non-zero count, an exit line
and a HEAD in its own record: the 18-plus-4 hashing consolidation, namespace
adoption and its non-vacuous production check, filed capture, typed LLM review
routing, registry as-of query behaviour, and truthful duplication
infrastructure. Those are not re-derived here; pointing at evidence that exists
is the correct move, and re-running them would be theatre.

SPOT-CHECKED DIRECTLY, because no dedicated Step owns them:

Delete-only certificate cutover. The certificate CLI module contains zero
occurrences of backend, keyring or migration vocabulary. The decision was that
the cutover exposes no backend selection and no migration surface at all, and
an exact search over the module confirms it rather than inferring it from the
absence of a verb.

Backend replay removal. Measured against the materialised 290-leaf tree: no
leaf anywhere contains an audit replay path, the modelo audit group registers
exactly show, check and export, and `modelo.audit.replay` is absent from the
live schema registry. Three independent surfaces, all clean.

Atomic ledger evidence with one writer. All four evidence mutation verbs - add,
update, remove and confirm - are inside the profile-bound write guard, so none
can mutate on an unattached storage route. The confirm leaf was outside it
until today and is now inside, which is why this check is worth having rather
than assuming.

Live export routing through one service. The portable-bundle serialiser is
reached from the bucket-maintenance service and its tests, consistent with the
composition rule that a service delegates to the single-writer primitive rather
than re-implementing it.

Gates at HEAD `76c94c4a81ee7a4c7f98973e87f6e8331840740b`:

- Certificate module vocabulary search: 0 matches for backend, keyring or
  migration.
- Live tree: 290 leaves, zero audit-replay leaves, audit group exactly
  `show`/`check`/`export`, `modelo.audit.replay` not in the schema registry.
- Guarded evidence verbs: `add`, `update`, `remove`, `confirm`.

## Notes

The audit is against CODE, which is what the row asks, and that distinction did
work here. The replay decision could have been confirmed from the plan, which
records the removal, or from the tests, which assert the verb is gone - but
both are artefacts referencing the subject. The live tree and the live registry
are the subject.
