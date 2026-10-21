# Grounding: the registry is the legal authority

## Let the law pick the revision; never inject one

Which registry revision applies to a `(modelo, filing_year, period)` is fixed by the law
AEAT published, not by you and not by a stored value. Address a work unit by `--modelo`,
`--year` and `--period` and let the CLI resolve the revision. Never force a different
revision to change a number. When a `(modelo, year, period)` combination is refused,
the refusal lists the accepted set: pick from it.

## Provenance flows from the registry to the taxpayer

Every casilla the engine emits carries `legal_refs` and `source_refs` from the registry.
Cite that grounding as given. Never substitute a legal reference from your own
knowledge; if it disagrees with the returned one, trust the returned one and surface
the discrepancy.

## The ledger is the source of truth, not your summary of it

When a casilla derives from the ledger, the contributing transactions and their
evidence are the basis. Reach the value through the calculation path
(`aeat app modelo work calculate`, or its registered operation), never by tallying
transactions yourself. To show the basis, pull it from the evidence surface, not from a
running total.

## When unsure, run a command

Any time you are tempted to state a tax fact from memory (a rate, a threshold, a
deadline, a casilla number), get it from the engine and quote the result:
`aeat app overview calendar`, `aeat app modelo describe`, or an `authority` query.
A zero on positive activity is a question, not a result: see the honest-declaration
rule.
