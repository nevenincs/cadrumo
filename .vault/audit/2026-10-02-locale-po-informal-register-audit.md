---
tags:
  - '#audit'
  - '#locale-po-informal-register'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:4d30aef4f8661dd131e78e6ac4d1a17ba4de1d1c07d16f5a076db6cf6d8ebffb'
related:
  - "[[2026-10-02-locale-po-informal-register-plan]]"
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-07-12-multilang-externalization-adr]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace locale-po-informal-register with a kebab-case feature tag, e.g. #foo-bar.
     Exactly these two tags are allowed; do not append additional tags.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - Cite code as inline backtick locators: `src/module.py:42`; never as a
       markdown link. -->

# `locale-po-informal-register` audit: `Documentation register, source synchronization and commit review`

## Scope

Review the owned runtime commit and ca/es/hu documentation PO register against the accepted gettext and externalization ADRs. Runtime ownership is established by exact coordinates; PO completeness is derived from current source pages and real Babel catalogues. English message identities, official excerpts, code and links are protected. A scoped source synchronization for one pre-existing changed paragraph is reviewed separately from register rewrites.

## Findings

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### Documentation register, source synchronization and commit review | {level} | {summary}

     followed by a paragraph carrying the detail. Documentation register, source synchronization and commit review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

### runtime-commit | low | Isolated index preserves concurrent work

Commit 32d2115c44 contains 1350 owned runtime coordinate deltas, the unused shortcut removal, test expectations, informal-register rule and completed runtime review records. The live runtime gate equals zero and the fresh runtime suite passed 188 tests in 187.90 seconds. Four corrected Hungarian translations belong to uncommitted new TUI keys and remain with their caller work. The shared index was synchronized only for previously unchanged owned paths.

### romance-register | low | Catalan and Spanish candidates retain their subjects

Independent root review accepted all 60 Catalan spans across 59 strings and all 76 Spanish spans across 74 strings. These are existing informal singular forms, adjectives, nouns, literal link fragments or grammatical third-person and passive predicates. No rewrite was justified by these signals. The owning docs integrity selection passed 27 tests.

### stale-source-paragraph | medium | Repair one changed English message through scoped synchronization

Fresh gettext extraction found one missing and one stale message in how-to/review-calculation-values.md for ca, es and hu. The source already differed when this PO work began. Root will repair only that page through the scoped docs workflow and translate the exact delta; broad catalogue synchronization is outside scope.

### saved-history-meaning | medium | Keep the actual calculation-history condition

Root review found that the Hungarian workbench paragraph for calculation without saved input history still describes calculation outside the declaration screen. That pre-existing condition is inaccurate. Root retained the independent review finding and will repair the exact paragraph through the owning manifest service.

### quoted-ui-address | medium | Application UI labels require current informal wording

The scratch detector originally masked all quoted prose. Independent review found formal Hungarian application-authored UI labels in quotes; these are outside official or corpus excerpts. PO discovery now includes quoted prose as exact reviewable spans while code stays masked. Root updated the entered-value, missing-input, confirmation, recalculate and first-open labels to match their current runtime keys. Exact baseline/after hashes and live runtime values protect these narrow quote updates; any later source change reopens the gate. A hypothetical Modelo 303 sentence still needs an informal quoted possessive, and remains in the unresolved numerical queue.

### detector-teeth | low | Adversarial real-reader checks reject false convergence

Three isolated PO fixture tests pass. They prove that a partial grammatical exception leaves a direct-address signal unresolved, changed wording invalidates its receipt, changed translations need independent review, literal or fuzzy metadata damage and source drift remain failures, the owning writer dry-run preserves bytes, and an old manifest cannot write after the catalogue changes. The initial fixture run was rejected for a missing required hex_core marker; the corrected selection executed all three tests.

- [medium; resolved] Independent review found two semantic defects in Hungarian worker drafts: the censo divergence described failure to agree instead of different stored values, and `--saturate` told the reader to derive tax values instead of explaining the system's calculation. Root repaired both with the owning SHA-guarded PO service and independently sealed their exact final values. The draft actor error had initially passed a parent review and was corrected on the subsequent context pass.
- [low; resolved] The scoped owning source synchronization replaced one outdated paragraph identity in `how-to/review-calculation-values.po` for all three target languages. Three new translations were reviewed against fresh English gettext output, fuzzy flags cleared through the owning service, and exact old/new identity and control hashes recorded without changing the immutable baseline.
- [low; verified] Catalan and Spanish nitpicky localized user documentation builds both pass (2 tests, 493.19 seconds). Six adversarial scratch gate tests pass, including stale runtime-label and authored-example source provenance controls. The new authored-example fixture initially included an unrelated third-person `mondja` match; its neutral fixture text was corrected, with no production exemption added.

## Recommendations

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
