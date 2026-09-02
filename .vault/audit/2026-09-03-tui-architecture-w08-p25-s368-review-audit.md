---
tags:
  - '#audit'
  - '#tui-architecture'
date: '2026-09-03'
modified: '2026-09-02'
body_schema: 'body-v2'
body_hash: 'sha256:aa6e8789374ea0aff97e363257286a5645641a5ff2dfdc8a1eba73a705c8b373'
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

### remediation-sensitive-boundary | high | Plain labels, source identifiers and reversible token indexes keep the redaction finding open

The public snapshot accessor and plaintext `search_terms` are gone, request plaintext is excluded from model serialization and repr, and query/document terms are normalized before hashing. Those changes close the original direct hidden-term retention shape. They do not establish the claimed redacted boundary. `_RedactedLabel` is only a bounded `str` with a control-character check. A direct probe constructed a declaration labelled `X2482300W Â· ES91 2100 0418 4502 0005 1332`; `model_dump_json()` emitted the NIF and IBAN unchanged. `Hex64Str` similarly proves only spelling and length for `stable_id`: any existing 64-hex transaction, filing, invoice or other protected source ID passes without being search-derived.

The token channel is pseudonymized rather than irreversibly redacted. `digest_operator_safe_tokens` publishes unsalted SHA-256 for each normalized word independently, the document model serializes those digests, and the response serializes the query digests. Low-entropy and enumerable tokens such as modelo numbers, years, `csv`, NIF components and status words are dictionary-recoverable, while splitting punctuation loses the boundary that distinguished a filing reference. The test proves only that one raw string is absent and even asserts against the literal word `secret`; it does not prove safe provenance, irreversibility or absence of protected content in labels and IDs. Ephemeral private service storage is an improvement, but public serializable carrier models remain. `sensitive-search-retention` therefore remains open at high severity.

### remediation-source-semantics | high | The status matrix is keyed by kind, not source, and accepts arbitrary semantic suffixes

First-class `ledger_entry`, `ledger_evidence` and `notification` kinds close the original family-coverage omission. The replacement status rule does not preserve source-native semantics: `_STATUS_PREFIX_BY_KIND` never reads `source`, despite the test name claiming a source-native contract, and `startswith` admits any namespaced suffix rather than a closed status set. Direct probes accepted a Ledger entry from `modelo.local_projection` with `ledger.entry.filed` and a revision from `notification.aeat_projection` with `revision.unread`; a declaration carrying `declaration.nif_exposed` also validated. The shared test helper itself assigns `modelo.local_projection` to every result family, so the positive matrix normalizes rather than detects source/kind disagreement.

The remediation prevents a status from another kind prefix, but does not prove which authority produced a result or that its suffix has meaning for that source. `source-semantics` remains open at high severity until source, kind and a closed source-owned status vocabulary are validated together, or a typed discriminated source projection preserves the native status without caller-authored strings.

### remediation-address-identity | medium | Natural typing improved, but revision identity is the wrong semantic coordinate and exact fields are not discriminated

`ModeloCode`, filing year/period agreement, `FilingRecordId`, canonical fold order and `Hex64Str` stable ordering close the mechanical portions of `natural-address-type` and `identity-normalization`. Revision search, however, carries `domain.calculations.registry.ids.RevisionId`, the legal registry revision coordinate exemplified by `m303-2025-r1`. The navigation decision's declaration revisions are calculation-history records; their canonical exact identity is `CalculationRevisionId`, not the registry law revision. The address also permits `revision_id` and `filing_record_id` on every kind and permits both simultaneously, requiring only the one associated with revision or filing. Thus a declaration, history row or Modelo result can carry irrelevant exact identities, and revision/filing variants are not a discriminated address contract. This residual natural-address defect remains medium severity.

### remediation-admission-localization-purity | low | Candidate authority, localization and current purity are correctly bounded

Renaming the field to `action_candidate_id`, removing `ActionReference`, and explicitly assigning resolution to S369's destination catalogue closes `admission-action-boundary`: the application result no longer claims the candidate is executable authority, while unavailable destinations correctly reject one. The service imports no locale catalogue and keeps source, status, destination, admission and action tokens untranslated; a later presenter may localize a genuinely redacted label. Inspection and the expanded AST/import test found no filesystem, repository, adapter or network I/O. These axes have no remaining production defect at the reviewed scope.

### remediation-test-teeth | medium | Expanded tests still bless the two open high-severity shapes

The suite now covers every kind, prefix rejection, canonical Modelo shape, required revision/filing IDs, Hex64 identity, normalization, absent snapshot accessor, raw-query omission and module imports. It remains unable to detect the live high findings: the serialization case uses a harmless label and checks only the raw filing-reference term, the schema case examines field names rather than content/provenance, and the all-kind helper supplies the same contradictory source for every family. The status-negative case changes only the prefix to `nonsense`, so arbitrary suffixes and wrong source/kind pairs stay green. No test distinguishes registry `RevisionId` from `CalculationRevisionId`, rejects irrelevant/both exact address IDs, or demonstrates that token digests resist a finite sensitive-token dictionary. `gate-teeth` remains medium severity.

### final-protected-boundary | low | The protected identifier, label and search-retention high is resolved

The final projection admits no provider-authored label, search terms, token digests, source identifier or asserted stable result identifier. Labels are closed localization keys, every result identity is derived inside the service, plaintext queries are excluded from representation and serialization, and neither documents nor query indexes have a public snapshot accessor. Canonical `CalculationRevisionId` and `FilingRecordId` values remain explicit natural-address coordinates rather than being smuggled through an opaque display or search field. The focused sensitive-input and serialization probes now fail closed for the original NIF, IBAN, raw Hex64 and dictionary-token attacks. The original `sensitive-search-retention` and `remediation-sensitive-boundary` high findings are closed.

### final-source-address-authority | low | Source semantics, exact addresses and authority boundaries are resolved

Kinds, sources, statuses and label keys are closed enums joined by exact maps; the source-owned status sets reject wrong families and arbitrary valid-looking suffixes. Natural addresses are discriminated `modelo_case`, `calculation_revision` and `filing_record` variants, use canonical `ModeloCode`, `CalculationRevisionId` and `FilingRecordId`, enforce period/year agreement, and reject irrelevant exact identities. `action_candidate_id` remains explicitly non-authoritative pending S369, while unavailable admissions require a reason and cannot advertise a candidate. The module is frontend-neutral, untranslated and pure by inspection and by the expanded AST/import gate. The original `source-semantics`, `natural-address-type`, `remediation-address-identity` and `admission-action-boundary` defects are closed.

### final-search-identity-cardinality | high | Derived identity cannot represent record-level search and changes with mutable state

The safe-boundary remediation removed every record identity from `WorkbenchSearchDocument`, but `_derived_stable_id` hashes only kind/source/status/label, optional Modelo coordinates, destination admission and action candidate. For families without a natural address, two distinct same-state records at the same destination therefore derive the same identity and `WorkbenchSearchService` rejects the snapshot. A direct probe with two Ledger-entry projections in `ledger.entry.ready` reproduced that refusal. The same structural collision applies to Ledger evidence, reconciliation findings and notifications, so the service cannot represent the required record-level cross-domain denominator except up to the small number of status/admission combinations.

The identifier also includes mutable `status`, admission state/reason and action candidate. Direct probes showed the same Ledger projection receiving different identifiers after `ready` became `classified` or its destination became locked. It is consequently not a stable semantic identity for deterministic focus restoration. This is a high-severity functional contract failure even though the earlier protected-input high is closed: a safe opaque per-record search identity must be derived by the owning source or from an approved non-sensitive canonical record coordinate, and mutable presentation state must not participate in it.

### final-gate-teeth | medium | Green tests omit record cardinality and identity stability

The final suite has useful negative teeth for the two original highs, exact address discrimination, `CalculationRevisionId`, admission, localization boundaries and I/O imports/calls. It proves only duplicate identical projections are refused, however; it never supplies two distinct same-state records from a required multi-record family, and it never asserts that identity survives a status, admission or action-candidate change. Those omissions leave the live high-severity identity/cardinality defect green.

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
8. Final remediation re-review supersedes neither high disposition: introduce an enforceable redacted-label/search-identity boundary, derive search IDs rather than accepting arbitrary source Hex64 IDs, and avoid serializing reversible low-entropy token indexes or explicitly classify and secure that index as sensitive ephemeral data.
9. Replace `_STATUS_PREFIX_BY_KIND` with a real source/kind/status authority contract. Tests must vary source independently, enumerate each closed native status, and reject valid-looking statuses under the wrong source.
10. Use canonical `CalculationRevisionId` for declaration calculation-history results and make revision/filing exact address variants discriminated so irrelevant or simultaneous identities fail closed.
11. Add bite probes for a NIF/IBAN label, a raw 64-hex source ID, a dictionary-recoverable sensitive token, cross-source valid-prefix statuses, arbitrary suffixes, and wrong/both exact address IDs.
12. The remediation suite passed with 32 tests; Ruff and Basedpyright were clean. No critical finding remains, but two high and two medium findings remain open, so S368 still should not be credited.
13. Introduce an intrinsically safe, source-owned per-record identity (or an approved canonical natural coordinate) for every multi-record family. Derive result identity from that immutable coordinate only; exclude status, admission, reason and action candidate.
14. Add detector tests that admit two distinct same-status Ledger entries, evidence records, reconciliation findings and notifications without collision, and prove stable identity across status and admission transitions.
15. Final gates passed: focused Pytest reported 28 passed; Ruff and ty passed; Basedpyright reported 0 errors, warnings or notes. The two prior high findings are closed, but one new high and one supporting medium remain open. No critical finding exists. `W08.P25.S368` must not close.

<!-- Actionable recommendations, each tied to a finding above. An
     architecturally significant recommendation names the decision a
     follow-on ADR must make; the decision itself is never recorded here. -->
