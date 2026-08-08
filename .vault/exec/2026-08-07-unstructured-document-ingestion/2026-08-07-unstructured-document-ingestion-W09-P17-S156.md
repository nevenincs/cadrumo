---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:8474bd13e6939f19e4cedfbbc26373f827cf4a50406fbaca3e6dd7fd36351ed6'
step_id: 'S156'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---
## Description

- Remove the printed tax identifier as an establishment rung: it settles no territory at any point in the walk, on either side of the symmetry.
- Keep the prefix terminal for the other fact, and carry the identification state on the ladder result independently of the scope, populated on conflicted and unestablished results alike.
- Add a typed registration-versus-establishment conflict record, distinct from the confirmed-fact contradiction it sits beside, and expose it through the package facade.
- Check the conflict BEFORE the ordinary rungs, so a foreign registration printed beside Spain-indicating evidence surfaces instead of being answered by the postal rung.
- Collect the Spain-indicating signals rather than short-circuiting them, since the finding is what an operator acts on.
- Resolve a foreign registration to its own State's territory only by concordance: an independent signal agreeing, and no rung indicating Spain.
- Read the printed treatment as that independent signal, requiring both the reverse-charge mention and the absence of charged Spanish IVA.
- Ask the bundled rate registry whether a charged rate is a Spanish one, converting the printed whole-number percentage to the fraction the registry keys on.
- Thread the regime mention, the charged rates and the invoice date through the resolution path, and extract them from both the line and the per-rate breakdown carriers in the draft router.
- Delete the retired rung member rather than retaining it unused, and rewrite the four suite cases that encoded it.

## Outcome

A registration now evidences registration and nothing else, symmetrically. The population that used to resolve silently and wrongly — foreign-registered, established in Spain — now surfaces as a typed conflict carrying both halves of the disagreement. The population that used to resolve correctly by accident of rung order still resolves with no operator question, because the address rung answers on its own authority and needs no help from the prefix.

Two judgements are worth recording because neither is forced by the row.

The conflict is checked ahead of the ordinary rungs rather than after them. Checking after would have let the dangerous document resolve anyway, just to a different wrong value: a Spanish address opens the postal rung, which answers Madrid perfectly well. That is gated directly rather than left to the ordering comment.

The rate check is inconclusive without a date, and inconclusive contributes nothing in either direction. It raises no conflict, because a false conflict blocks a legitimate filing, and it supplies no corroboration, because a rate nobody could verify is not a second signal. The operation falls to a question, which is safe both ways.

The retired rung member was deleted rather than kept. An unreachable value in a closed set is one every consumer still has to handle, and the honest record of what settled such a document is that nothing did.

## Verification

Owning suite plus the new gates, unit lane:

    uv run --no-sync pytest src/cadrumo/application/ledger/tests/test_establishment_ladder.py src/cadrumo/application/ledger/tests/test_registration_concordance.py -n0 -q -p no:randomly -m unit
    55 passed in 11.94s

Affected packages, unit lane:

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/domain/iva src/cadrumo/adapters/inbound/einvoice -n0 -q -p no:randomly -m unit
    1668 passed, 22 deselected, 15 warnings in 146.50s (0:02:26)

Integration lane, excluding one module a peer lane had mid-edit at the time (its collection error is an import of a symbol not yet added to the country resolver, on a file this row does not touch):

    uv run --no-sync pytest src/cadrumo/application/ledger src/cadrumo/domain/iva -n0 -q -p no:randomly -m integration --ignore=src/cadrumo/domain/iva/tests/test_country_vocabulary_boundary.py
    22 passed, 1641 deselected in 80.69s (0:01:20)

Two mutations, installed from an out-of-repo plugin at module scope, each carrying an invocation counter as well as a banner because a banner proves only that the plugin loaded:

- a printed foreign prefix terminates the establishment ladder again: MUTATED CALLABLE INVOKED 15 TIMES, 8 failed
- a conflicted document silently resolves to the registration state: MUTATED CALLABLE INVOKED 15 TIMES, 3 failed

The first reddens the refusal cases, the concordance cases and the conflict cases together, which is the signature of the rung genuinely being back rather than of one assertion being brittle.

## Notes

Four cases in the existing suite encoded the removed rung and were rewritten rather than deleted, each recorded by category. One is a property the split retires and INVERTS: the page proving the identifier rung outranked the others is the exact conflict fixture the amendment names, so it keeps its fixture and reverses its verdict, and it still discriminates in both directions. Two are the same property in new vocabulary: the Greek prefix divergence now bites on the identification state, and the no-bare-except coverage moved to the lookup the walk actually makes first — patching the retired symbol would have left that case green against a call nothing performs. One is a routing property re-proven on the terminal fact, which is a sharper probe than the territory it used.

A unit mismatch was caught by the gates rather than by review. The registry's inverse rate lookup takes a fraction while a document prints a whole-number percentage, so the first implementation asked whether 21 was a Spanish rate, got nothing, and reported no Spain-indicating evidence for exactly the conflict fixture. The conversion the draft module already applies is now applied here with the unit named at the parameter.

A separate lane holds the intra-community predicates, which declare consuming the identification state while no predicate reads it. That is a different module and is not closed by this row.

The concordance signal currently has one source, the reverse-charge mention. Other treatments consistent with non-establishment exist and none is claimed here; a document carrying one of those and no address country still reaches a question rather than a wrong value.
