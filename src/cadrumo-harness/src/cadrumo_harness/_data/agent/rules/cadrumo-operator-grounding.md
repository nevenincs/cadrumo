# Grounding: law-determined revisions and honest declarations

The registry is the legal authority. These rules keep your output grounded in it.

## Let the law pick the revision; never inject one

Which registry revision applies to a `(modelo, filing_year, period)` is determined by
the law AEAT published, not by you and not by a stored value. Address a modelo work
unit by `--modelo`, `--year`, and `--period` and let the CLI resolve the revision.
Never try to force a different revision to change a number. If the CLI refuses a
`(modelo, year, period)` combination, the refusal lists the accepted set — pick from
it; do not work around it.

## Provenance flows from the registry to the taxpayer

Every casilla the CLI emits carries `legal_refs` and `source_refs` from the registry.
When you explain a value, cite that grounding as given. Do not substitute a legal
reference from your own knowledge for the one the CLI returned; if they disagree, trust
the CLI and surface the discrepancy.

## Do not present an under-declaration as complete

See the honest-declaration rule: a `verified_complete` result with zero findings
on positive income is a question to resolve, never a result to celebrate.

## Use the ledger as the source of truth, not your summary of it

When a casilla derives from the ledger, the contributing transactions and their
evidence are the basis. Reach the value through the calculation path
(`aeat app modelo work calculate`), not by tallying transactions yourself. If you need
to show the basis, pull it from the CLI's evidence surface, not from a running total
you kept in your head.

## When you are unsure, run a command — do not guess

The CLI is cheap, deterministic, and instructive. Any time you are tempted to state a
tax fact from memory — a rate, a threshold, a deadline, a casilla number — run the
command that returns it (`aeat app overview calendar`, `aeat app modelo describe`,
or the MCP `contract` tool) and quote the result.
