---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8191b3cba697c6bf31aa14b2703c09d2de9aa77cb7af6332ac6c02bf0ae2a5f5'
step_id: 'S241'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Rename the establishment ladder's backwards country parameter

## Scope

- `src/cadrumo/application/ledger`

## Description

- Confirm from both callers which value the parameter actually receives, rather than from its name or its docstring.
- Rename the parameter to say resolved, and move the private helper carrying the same name with it.
- Correct the two docstrings claiming the document states this value, which is the prose the rename exists to retire.
- Update the draft-side warning that cited the old name by spelling.
- Land it as one commit, with a clean collect-only immediately before and after.

## Outcome

The parameter received the alpha-2 already resolved through the bounded vocabulary and was named for the token a record states. Both are optional strings, so the plausible reading of the name — feed it what the document stated — puts an alpha-3 into an alpha-2 slot on a tax-territory path, type-checks, and silently places nobody. The name was not merely inaccurate; it invited the wrong change on the axis this campaign spent the day grounding.

Two prose surfaces disagreed about which value belongs here, and the disagreement is now ruled rather than left. The ladder's own docstring said "an alpha-2 country code the document states"; the consuming draft-side docstring warned against exactly that, naming the parameter and explaining that it wants the resolved form. **The draft side was right.** Both callers pass the resolved code — one from the counterparty side's resolved attribute, one from the party's resolved country-code field — so the ladder's prose was describing a value it never receives.

The sibling name is deliberately unchanged. A document does state a country NAME, and that leg is matched against the vocabulary inside the ladder rather than resolved before arrival, so `stated_country_name` is accurate and renaming it for symmetry would have made a correct name wrong.

## Verification

Collection, immediately before and immediately after, on the working tree:

    uv run --no-sync pytest --collect-only -q
    23150/27193 tests collected (4043 deselected) in 76.18s     [before]
    23150/27193 tests collected (4043 deselected) in 77.83s     [after]

Residue, after the rename:

    rg -n --glob '*.py' '\bstated_country_code\b' | rg -v 'supplier_|customer_'
    (no matches)

Content in HEAD after the commit:

    resolved_country_code  x9
    stated_country_code    x0

Owner lanes:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests src/cadrumo/domain/iva/tests -n0 -q -m unit
    2 failed, 1935 passed, 26 deselected, 16 warnings in 198.05s

## Notes

The two failures are not this change and were attributed rather than assumed: both files carry zero references to the renamed symbol and both hold uncommitted peer work in the working tree, 41 and 110 insertions respectively. The rename cannot reach a file that never names it.

The four target files were confirmed clean before the edit, because three of them were rebuilt from their HEAD blobs rather than from the working copy — reading the working copy would have folded a peer's in-flight line into a rename commit, and writing it back would have discarded one.

One absorption is reported rather than hidden. Between reading and committing, an eight-line comment improvement by another lane appeared in the evidence-draft file, describing the anchor search becoming boundary-aware for word-shaped anchors. Committing that file by pathspec took it. It is a self-contained comment change, it is an improvement, and separating it would have split the citation update away from the rename it belongs to — but it is not mine and the record says so.

The helper was renamed alongside the parameter rather than left, because its name was the parameter's name: leaving it would have kept the retired vocabulary in the file under a different grammatical role, which is where a later reader would have re-learned the wrong distinction. The rename was applied helper-first, since the helper's name contains the parameter's and the other order would have produced a hybrid.
