---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:f16df6a08ac501ad5640d526fbee21cbe0387d842ccfa143df9beeabfb65bdbe'
step_id: 'S127'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
# Bring the IVA registry tables inside the evidence gate, since they are read by the IVA domain directly rather than through the registry authority and their legal refs are therefore validated by nothing at all, which the territory table only escaped once a bespoke gate was written for it. The rate tables, the recargo rates and the place-of-supply tables carry the same structural exposure, and these are regulatory values where an ungrounded citation reads as grounded to every later reader. The bespoke territory gate is explicitly NOT the template and its author says so: it hardcodes the catalogue files it searches and checks a citation by substring-matching the raw TOML rather than loading the catalogue, which was proportionate for one table and one provision but does not scale, and four copies of it would be worse than the gap. Route these files legal refs through the real catalogue verification and evidence validator path so they get anchor-scoped required-text checking, and treat the bespoke gate as a candidate for deletion once they do

## Scope

- `src/cadrumo/_data/registry`
- `src/cadrumo/domain/iva`

## Description

- Add a shared IVA grounding verifier that resolves a table's cited provisions through the registry's own evidence validator, delegating rather than re-implementing the check.
- Route the recargo rate, place-of-supply and territory loaders through it, so an ungrounded citation refuses at load rather than passing unread.
- Require a territory row to cite the provision establishing its exclusion, which the loader previously discarded.
- Move the rate loader's legal-reference resolution into the shared verifier and delete its local copy, keeping the source-reference and applicability-window checks where they belong.
- Add a gate covering the shipped tables, the three ways a citation goes wrong, and the anchor scoping that separates a real check from a file-wide one.

## Outcome

The four regulatory tables under the IVA registry directory now verify their own grounding at load. A citation naming a provision the legal catalogue does not define, or defining one whose declared wording is absent from the anchored unit of bundled consolidated text it points at, refuses the table instead of being read as grounded.

Every citation shipped today resolves. Measured across all six IVA tables: 75 citation occurrences, 20 distinct provisions, every one carrying a catalogue entry with an anchored corpus reference and declared required text. Nothing was found unverifiable, so no grounding was authored to close a gap.

Two findings shaped the design and are worth carrying forward.

The tables do not agree on a citation field name. The rate, recargo and territory tables write `legal_refs`; the place-of-supply table writes `legal_references` beside an `establishing_reference`. A generic sweep discovering citations by searching for one field name would have examined none of the place-of-supply table, which holds 51 of the 75 occurrences, and passed while checking two thirds of nothing. Citations are therefore handed over by each loader from rows it has already parsed, never discovered by field name.

The bespoke territory gate the row describes no longer matches its description. It was rewritten to parse the catalogue as TOML and resolve the cited corpus reference through the same anchored resolver the registry uses, so the substring-matching characterisation is stale. It is not a deletion candidate: its remaining cases assert what the cited article SAYS, which is a different property from whether the citation resolves, and the statutory-silence case behind the Balears has no equivalent elsewhere. Only its citation-resolution case is now redundant with the load-time gate, and it is cheap.

## Verification

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m "unit and not external_tool and not os_keychain"
    531 passed in 25.65s

Run against a clean checkout of the commit under test rather than the working tree: a peer's in-flight rename of the classification criteria model left the domain package unimportable mid-session, and 12 unrelated failures in the working copy belong to that lane.

    uv run --no-sync pytest src/cadrumo/domain/iva/tests -n0 -q -m "integration"
    531 deselected in 0.96s

The integration lane selects nothing here; the modules are unit-marked, and that is a statement about coverage of that lane rather than a green from it.

    uv run --no-sync pytest src/cadrumo/domain/iva/tests/test_iva_registry_grounding.py src/cadrumo/domain/iva/tests/test_rate_grounding_refusals.py -n0 -q
    26 passed in 2.76s

Mutation proof, driven from outside the repository with no tracked file modified. Emptying the legal catalogue reddened all four loaders; every table loaded on the unmutated baseline first, so the refusals discriminate rather than firing unconditionally.

The first attempt reddened three of four. The rate loader stayed green because it holds a from-import binding to the catalogue accessor, so patching the defining module never reached it. That was a defect in the probe rather than a gap in the gate, and patching the binding at its own site reddened the fourth.

## Notes

Seven failures in the registry calculation suite are outside this surface and belong to the export-schema lane: a field definition missing its decimals declaration, and a validator module grown past its complexity baseline. None reference IVA grounding.

The shared verifier deliberately lets the registry loader's own error propagate rather than wrapping it, so a malformed tree still reports the file that is malformed.
