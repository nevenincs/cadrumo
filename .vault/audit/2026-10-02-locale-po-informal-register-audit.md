---
tags:
  - '#audit'
  - '#locale-po-informal-register'
date: '2026-10-02'
modified: '2026-10-02'
body_schema: 'body-v2'
body_hash: 'sha256:99997ec7c83f38ad14c5fefea26bb10e4e67275944af6112809619033fc83c52'
related:
  - "[[2026-10-02-locale-po-informal-register-plan]]"
  - "[[2026-07-18-user-docs-localization-adr]]"
  - "[[2026-07-12-multilang-externalization-adr]]"
---

# `locale-po-informal-register` audit: `Documentation register, source synchronization and commit review`

## Scope

Review the owned runtime commit and ca/es/hu documentation PO register against the accepted gettext and externalization ADRs. Runtime ownership is established by exact coordinates; PO completeness is derived from current source pages and real Babel catalogues. English message identities, official excerpts, code and links are protected. A scoped source synchronization for one pre-existing changed paragraph is reviewed separately from register rewrites.

## Findings

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

### supplemental-forms | medium | Broad finite-form discovery closes the initial lexical gaps

Parent spot searches found omitted Hungarian potential forms and possessed infinitives, including guide introductions, a confirmation obligation, and optional-consent changes. The detector now counts open `-hatja/-heti/-hat/-het/-nia/-nie` families alongside its original curated forms. Six released-page rows were repaired with exact current guards. Existing third-party predicates remain counted until supported by a span-specific contextual decision; the initial baseline is unchanged.

### range-and-agency-grammar | medium | Parent corrects range meaning and an agency subject

Review found that a Hungarian draft shortened `across a year range` to a single vintage and omitted the grammatical marker for facts held by the agency. Root corrected the range to a multi-year interval and restored `által` to the agency clause through the owning service, then reviewed the exact final paragraphs. All four runtime keys previously deferred with new caller work now match HEAD after the contributor's commits; no runtime correction remains deferred.

### renta-dependency-direction | medium | Restore the annual filing dependency direction

Parent review rejected the drafted Renta prerequisite sentence: it reversed which filing depends on which. The English source requires earlier filings used by the annual declaration to be recorded as filed. Root restored that direction through the owning writer, retained the prior-year AEAT proof and same-year advisory conditions, and independently reviewed the final text. The same pass restored data-source contract terminology. A subsequent parent grammar pass corrected the article from `a` to `az` after the root's terminology change.

### obsolete-download-entries | low | Owning writer removes seven exact obsolete download entries

The HU-B packet 16 dry run refused all writes because download.po retained seven Babel obsolete entries. Active identities already match the fresh source extraction; there is no new source drift. Root saved the exact obsolete metadata and used the owning remove_obsolete manifest alongside one informal instruction. The dry run and write each report seven obsolete removals and one changed active translation. Active identities, flags, headers and source locations remain unchanged; an exact before/after control receipt keeps this limited repair visible to the gate.

### residual-discovery-and-house-style | medium | Required checks expose gaps in writer coverage

Independent review found a missed remove-link imperative and formal potential forms in table navigation and a help heading. Parent morphology spot searches added open Hungarian imperative endings and identifier possessives to live discovery, then repaired 23 additional released-page values through current guarded manifests. Existing third-party clauses remain unresolved until their exact grammatical evidence is accepted. The owning documentation test also rejected 58 Hungarian values that introduced em/en dashes absent from their English source; the scratch gate now counts that house-style violation. The failed run remains visible: 33 passed and 1 failed in 15.20 seconds. No test or requirement was weakened.

Independent review also clarified workbench support coverage, restored the model-dependent filing-mode sentence and reader identifier grammar, and repaired invoice field coordination and the requirement for both profile-name option values. Each correction was re-read against the English source and sealed at its exact current value.

### final-address-discovery | medium | Count prerequisite headings and authored reference labels

The final contextual searches counted open Hungarian imperative endings, potential forms, necessity predicates and authored MyST display labels. They found additional direct instructions, prerequisite headings and dependent reader verbs outside the first worklist. Exact guarded writes made these informal singular. Three authored reference-label changes preserve their role and target; source and message hashes constrain the narrow literal receipts. Official Spanish and corpus excerpts remain unchanged by this work.

### meaning-and-review-arbitration | medium | Preserve legal conditions and actual grammatical subjects

Independent source review and parent arbitration repaired ambiguous withholding terminology, VAT-detail wording, a profile-bundle antecedent, the master-key requirement for reading an encrypted Drive copy, the distinction between a superseded capture and an overwritten capture, and informal reader clauses. The earlier calculation-history and quoted-example findings are resolved. Two review findings were bound to the wrong strings and were rejected and corrected without catalogue edits. Claims against valid Hungarian coordinated-inanimate singular agreement and accusative apposition were not upheld. Exact source context and current value hashes govern acceptance.

### punctuation-resolution | low | Required documentation checks accept the corrected house style

The 58 introduced Unicode dash violations were repaired with source-consistent punctuation through the owning manifest service. The final combined run passed all 42 translation-service, catalogue-integrity and scratch detector tests; its separate Hungarian build test failed on unrelated live registry validation. Fifteen adversarial scratch cases now exercise real Babel parsing, the owning writer, stale receipts, partial exemptions, metadata/source damage, machine-text punctuation and authored-label target preservation.

### current-convergence | low | Runtime and documentation address signals reach zero

The live runtime gate and documentation PO gate both equal zero. No stale decision, missing rewrite review, literal/control violation, fuzzy or untranslated message, source identity drift or source-context change remains in the PO gate. The immutable discovery baselines and history are retained. Zero describes the reviewed detector surface; it does not certify complete linguistic recall.

### concurrent-build-input | medium | Keep the failed live build visible

The Hungarian nitpicky documentation build stopped while compiling Modelo 360 revision 2010-y-siguientes: its live form layout referenced bindings that concurrent registry changes had removed. The run recorded 42 passed and 1 failed in 137.75 seconds. No localization test or registry condition was weakened. Current input comparison shows that the obsolete layout references have since been removed by that workstream; a fresh owning build remains required before final verification is closed.

### live-build-resolution | low | Hungarian nitpicky rendering passes on the corrected shared inputs

A fresh call through the actual compiled_bundled_authority path passed after the concurrent Modelo 360 layout was corrected. The owning Hungarian localized nitpicky test then passed in 453.96 seconds, with no test or production validation weakened. The prior failure remains recorded as an incomplete concurrent input state. Together with the earlier Catalan/Spanish localized builds, all three required language builds are verified. The 42 passing unit cases, three fresh-gettext integration cases, source/control receipts and zero runtime/PO gates complete the localization evidence.

### final-review | low | PASS: owned localization work is verified and committed

Commit 34d0e8754977070d1cbc2a302e2af4ee8a4d9bb0 records 1400 changed or new Hungarian active translations across 51 catalogues and the S04 evidence. Runtime commit 32d2115c44 and the scoped Catalan/Spanish commits 9999d4e797 and dd72924f694 remain in history. The runtime and PO numerical gates are zero; every changed value has current independent review and all exact-span exceptions have contextual evidence. Official excerpts, quantities, code, placeholders, role/link targets and non-reconciled catalogue controls remain protected. Three scoped paragraph identities and seven obsolete Hungarian entries have exact owning-service reconciliation records.

Verification covers 188 runtime tests, 42 documentation-service/catalogue/scratch unit cases, three fresh-gettext integration cases and all three localized nitpicky language builds. The earlier concurrent registry failure and its successful Hungarian retry are both retained. Scratch lint and formatting pass. The four runtime keys previously deferred with caller changes now match committed HEAD; no localization correction remains deferred. Only owned paths entered the isolated commits, with the shared index preserved. No push was performed. No required localization work remains.

## Recommendations

Keep informal singular address coupled to independent source-meaning review. A morphology detector supplies a worklist; zero is accepted only with current full-string hashes, exact-span grammatical evidence, complete rewrite reviews and passing owning documentation checks. Retain the frozen discovery baseline and rejected findings so later source or wording changes reopen the gate rather than erasing history.
