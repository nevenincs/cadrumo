---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-03'
body_schema: 'body-v2'
body_hash: 'sha256:0d3bac687fdc9673b7c1dc615084072dca48eb52fa16e41bf4f056212720b307'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
  - "[[2026-09-02-unreachable-capability-tui-navigation-join-adr]]"
  - "[[2026-09-02-unreachable-capability-tui-homepage-product-design-research]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #audit) and one feature tag.
     Replace tui-architecture with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar]]'.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

# `tui-architecture` audit: `w08 p25 s368 review`

## Scope

Independent review of `W08.P25.S368` across `src/cadrumo/application/search/workbench.py` and `src/cadrumo/application/search/tests/test_workbench.py` against the exact plan row, accepted navigation join, product research, and naming, architecture, localization, quality-gate and sensitive-data rules. The review covered vocabulary, source/kind coverage, natural address, admission/action consistency, determinism, duplicate identity, redaction, ephemeral retention, localization, I/O, and test teeth.

The implementation is frontend-neutral and pure by inspection. Ranking is bounded and deterministic for exact accepted byte strings, and non-available admissions require a reason and reject an action. The focused suite passed with 25 tests; Ruff passed and Basedpyright reported 0 errors, warnings or notes. Those green gates do not close the defects below.

<!-- What was audited and why -->

## Findings

### sensitive-search-retention | high | Opaque identifiers and hidden terms can carry and re-expose protected source data

`stable_id`, `label` and `search_terms` are bounded free strings, not redacted value objects or safe-grammar identifiers. `WorkbenchSearchService.documents` publicly returns documents including supposedly result-hidden terms, and each document is directly serializable. The focused test places a filing reference/CSV-shaped identifier in `search_terms` and proves only that the final result omits the field; the value remains reachable and serializable. `stable_id` can likewise be a NIF, account identifier or filing reference. Nested action/admission identities do not create the same leak: `ActionReference` contains only a canonical `NamespacedId`, and destination, source and reason codes are constrained technical vocabulary. Ephemeral memory prevents persistence by this service, but does not make protected raw payload safe or satisfy redaction-before-serialization.

### source-semantics | high | The flattened kind and status contract cannot preserve required source meaning

The accepted denominator spans Ledger entries and evidence, Modelo declarations and revisions, filing records, reconciliation findings and notifications while preserving type, source and status. `WorkbenchSearchKind` has no evidence or notification member; `message` cannot represent Ledger evidence distinctly. `source` accepts any namespaced ID and one flattened status enum accepts every status for every kind, so filed Ledger entries, unread revisions and draft reconciliation findings validate. This is unchecked caller-authored translation, not preservation of source-native status. The kind-set test freezes the incomplete set while helpers use `READY` across families; no source matrix or invalid-combination detector exists.

### natural-address-type | medium | Modelo natural addresses redeclare the canonical identifier as a plain string

`WorkbenchModeloAddress.modelo` retypes Modelo as regex-constrained `str` instead of canonical `ModeloCode`, contrary to the naming rule and existing Modelo addressing. Year/period agreement and required-address checks are sound, but the duplicate string type can drift. Revision and filing identity remains only an opaque `stable_id`, so the address cannot distinguish records sharing one Modelo/year/period case.

### identity-normalization | medium | Duplicate refusal and tie ordering use raw spellings rather than canonical identity

Duplicate detection and ties compare stripped `stable_id` strings verbatim. Canonically equivalent Unicode spellings and case variants can coexist although labels and queries are folded; ties follow raw code points. `_normalize_text` also strips diacritics before casefolding, the reverse of the canonical printed-phrase primitive even though casefolding can emit combining marks. ASCII-only permutation tests do not prove canonical identity.

### admission-action-boundary | medium | Availability is checked, but action authority is not joined to its destination

Non-available destinations correctly reject actions, but an available result's action need not belong to its destination, be capability-admitted, or carry operands addressing the result. `ActionReference` is only an ID while address and identity are separate. If this is intentionally a pre-S369/S382 candidate, it must be typed as non-authoritative rather than described as actionable.

### gate-teeth | medium | Tests inspect names instead of sensitive and I/O boundaries

The redaction test checks only top-level schema property names, missing protected content, public document serialization and `service.documents`. The no-I/O test checks a short name set only in `search.__code__.co_names`, missing constructor/helper I/O, `Path.open`, and differently named repositories. Current code is pure by inspection, but the test has no detector teeth. Coverage also omits invalid source/kind/status combinations, evidence/notification families, canonical Modelo typing, Unicode-equivalent duplicate IDs and action/destination disagreement.

<!-- A rolling log of findings: append one subsection per finding, grouped or ordered by
     severity, using the heading form

       ### w08 p25 s368 review | {level} | {summary}

     followed by a paragraph carrying the detail. w08 p25 s368 review is a concise kebab-case slug,
     {level} is the severity (critical, high, medium, low), and {summary} is a one-line
     statement. Append continuously as findings surface; do not rewrite settled entries. -->

## Recommendations

1. Resolve `sensitive-search-retention` before crediting S368: remove the public raw snapshot, use explicitly safe typed identity/search projections, and prove protected identifiers cannot cross or serialize.
2. Use complete source-owned families or a discriminated kind/status model for Ledger entry/evidence, declaration/revision, filing record, reconciliation finding and notification; reject invalid combinations.
3. Use canonical `ModeloCode` and decide how revision/filing identity extends the natural case without a potentially sensitive opaque ID.
4. Define canonical result identity/normalization, use canonical fold order, and test Unicode-equivalent duplicates and ties.
5. Join action capability and operands to admission, or type the action as a non-authoritative candidate requiring later resolution.
6. Add bite-proven serialization, sensitive-content, retention, constructor/helper I/O and source-family tests. Keep locale catalogues out of this service; stable codes correctly remain untranslated.
7. No critical finding was identified. Two high-severity findings remain open, so S368 should not be credited in its current form.

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
