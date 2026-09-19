---
tags:
  - '#audit'
  - '#aeat-export-fragment-generator-authority'
date: '2026-09-14'
modified: '2026-09-14'
body_schema: 'body-v2'
body_hash: 'sha256:601726becb10ce422ff8ce8a48327a406a3bf36dd0d99d6149f8ced9df5b0c3a'
related:
  - "[[2026-08-16-aeat-export-fragment-generator-authority-pdf-source-wire-fact-authority-adr]]"
  - "[[2026-09-14-registry-edition-authoring-signed-composite-export-reference]]"
---
# `aeat-export-fragment-generator-authority` audit: `Reviewed signed-composite generator extension`

## Scope

Reviewed `render_profile.py`, `render_profile_eligibility.py`, `_export_tree.py`, `export_fragment_provenance.py`, `test_signed_composite_render_profile.py`, and `0002-signed-composite.toml` against the accepted signed-composite authority, its parent/split leaf decisions, the signed-composite reference, and W03.P08's cross-period diagnostic obligation. Checks covered exact parser-anchor/source-SHA binding, source-agreement gates, sign/magnitude geometry and partition, the existing money codec, provenance derivation code, ordinary AN/literal/reserved/workbook/split routing, and unchanged empty-composite digest behavior. This was a read-only bounded review; no generated artifact was changed or published.

The 27 focused signed-composite tests and Ruff checks passed (exit 0). A direct isolated M296 render passed (exit 0): six files, one composite derivation, offset 145, length 15, money, `blank_or_n`. The digest-preservation control passed separately (exit 0). Canonical compile now passes after four M100 manifest entries were fixed; the actual CLI renders and validates deterministically, then reaches the expected stale-profile receipt. No live publication result is claimed. The existing render-profile suite remains 59 passed with two baseline failures (self-scan token self-match and stale compiler dependency allowlist; exit 1).

## Findings

### Signed composite source agreement | medium | Contradictory sign text and sign type are not refused

`_validate_signed_composite_source_agreement` requires one positive regex match and counts required positive phrases, but it does not reject contradictory clauses appended to otherwise valid prose or verify the sign subclause's declared type. A targeted probe appending `En cualquier otro caso se consignara una "N"` was accepted (exit 0); replacing `SIGNO: Alfabetico` with `SIGNO: Numerico` was also accepted (exit 0). Both violate the explicit complete sign-clause/source-agreement refusal boundary. The committed M296 source itself passes; this is a generic admission defect for a changed or adversarial anchored source.

### Signed composite source agreement | medium | Textual sign/decimal contradiction still bypasses the repaired guard

The exact quoted-`N`, wrong-nature, and lowercase-`n` probes now refuse, and all 20 focused tests pass. However, appending `Se consignara con signo y con coma decimal.` to otherwise-valid composite prose still reports `ACCEPTED`; the targeted probe exits 1 because acceptance is unexpected. The repaired global quoted-token check does not reject this post-magnitude textual contradiction, so the explicit conflict/uncovered refusal boundary remains open.

### Signed composite source agreement | low | Complete-consumption remediation closes the bounded residue cases

The frozen validator now applies `_COMPOSITE_DEFINITION_RE.fullmatch` after whitespace normalization, so unmatched prefix, interstitial, and suffix text cannot be silently ignored. The exact remaining contradiction and its three placements (prefix, interstitial, suffix) were all refused by the targeted probe (exit 0). The 27 focused tests pass (exit 0), including the exact source-SHA/row anchor render control and the unchanged no-composite digest assertion. No remaining counterexample was found within this bounded M296 review; closure is limited to these tested residue cases.

## Recommendations

The prior medium findings are closed for this bounded M296 review. Retain the full-match/residue negatives, exact source-SHA/row render control, and digest-preservation assertion. Keep staged generation, provenance receipt validation, and any live publication decision separate; no live publication claim is made here.
