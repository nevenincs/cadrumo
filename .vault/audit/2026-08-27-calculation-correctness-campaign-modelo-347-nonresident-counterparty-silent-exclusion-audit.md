---
tags:
  - '#audit'
  - '#calculation-correctness-campaign'
date: '2026-08-27'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:51c360b829c45d4ae021de171fdb893333810c5aec9bca1e0a9b9a136d564123'
related:
  - "[[2026-08-11-tui-architecture-plan]]"
---

# `calculation-correctness-campaign` audit: `modelo 347 nonresident counterparty silent exclusion`

## Scope

Determination requested by S302's disposition: whether `_m347_invoice_observation`'s
`if invoice.counterparty_country != "ES": return None` gate (`application/invoices/_source_resolver.py:598-600`)
is a deliberate, grounded scope limit or an oversight. Grounded against RD 1065/2007
arts. 31-33, the diseño de registro's own `pais-codigo` field, git history of the gate,
and existing test/ADR evidence. No code changed.

## Findings

### modelo 347 nonresident counterparty silent exclusion | critical | the ES-only gate is an oversight, not a grounded scope limit, and it silently drops real above-threshold declarable operations

RD 1065/2007 art. 31.1 obliges "personas físicas o jurídicas... que desarrollen
actividades empresariales o profesionales" to file M347 for their "operaciones con
terceras personas" -- the obligation is keyed on the FILER's own activity, never on the
counterparty's residency. Art. 32 (exclusions from the FILING obligation) excludes an
entity with no Spanish PE/domicile from having to FILE M347 itself -- again the filer's
own residency, not a counterparty-side exclusion. Art. 33.2 is the actual exhaustive list
of operations EXCLUDED from a real filer's declaration, and its two residency-adjacent
items are narrow: (g) operations run directly from/to the OBLIGADO TRIBUTARIO'S OWN
foreign permanent establishment, and (i) operations already reported via a DIFFERENT
periodic informativa with coincident content (the exact mechanism the M347/M349
capability-parity test below exercises for intra-EU operations). Nowhere does art. 33
exclude an operation merely because the THIRD PARTY (declarado) is non-resident.

The diseño de registro's own `CÓDIGO PROVINCIA/PAIS` field (positions 77-80,
`contraparte.pais-codigo`) is direct, structural evidence the opposite is true: AEAT
explicitly provides a "XX" country-code slot for a non-established non-resident
DECLARADO, meaning AEAT expects some M347 counterparties to be non-resident. A blanket
filter that never lets a non-ES counterparty become an observation makes that field
permanently unreachable by construction, not merely unbuilt.

`_m347_invoice_observation` (`application/invoices/_source_resolver.py:598-600`)
filters solely on `invoice.counterparty_country != "ES"`, with no qualification for
whether the operation is genuinely intra-EU-recapitulativa-reportable (the real,
narrower, legally correct exclusion the M349 side of the SAME resolver already
implements via `IvaCategory`/`IntracomOperationType`, not via bare country). The
adjacent skip two lines below it (`counterparty_tax_id is None`) carries a full
grounded comment citing RD 1619/2012 art. 6.1.d and the failure it prevents; the
country skip carries no comment, no citation, no reason at all. That asymmetry, on two
skips written by the same author in the same function, is the tell of an unexamined
default rather than a considered decision.

`test_capability_parity_m347_declares_only_the_domestic_party`
(`application/invoices/tests/test_source_resolver.py:1084`) is real, passing, existing
coverage -- but its own fixture (`_capability_bucket_invoices`) proves the exclusion it
pins is coincidentally correct only because every non-ES invoice in that fixture also
happens to carry a genuine intra-EU `IvaCategory` (`INTRA_COMMUNITY_SUPPLY`,
`INTRA_COMMUNITY_ACQUISITION_SERVICES`). No fixture anywhere exercises a non-EU or
non-recapitulativa-reportable non-resident counterparty (e.g. a US consultant, a UK
post-Brexit supplier, or an EU counterparty engaged in an ordinary domestic-Spain
transaction under general B2B rules) -- the case art. 33 does NOT exclude and the
diseño's own país-código field exists to represent. The test's docstring title,
"M347 counts the domestic party and excludes the intra-community ones," describes
what the fixture happens to demonstrate, not what the code actually implements; the
code implements a strictly broader, ungrounded exclusion the test cannot see because
it never varies country independently of `IvaCategory`.

Git history could not attribute an authorial decision: `git log -S` on the exact
country check finds it present since the earliest reachable relocation-era commits,
which are mechanical `refactor(workflow)` moves and one `Aggregate wip commit of all
current changes` -- squashed history with no decision commit or message behind it. No
ADR or audit in `.vault/` rules on M347's counterparty residency scope specifically.
The nearest precedent is `2026-08-06-invoice-canonical-structure-adr.md` decision D-I,
which independently found and is actively fixing the SAME defect SHAPE in a DIFFERENT
module: the M303/M390 invoice-versus-ledger screen's `counterparty_country == "ES"`
filter (`_modelo_bindings.py:1113-1123`) is explicitly named a "blind spot" to be
extended "past its ES-only... reach to cover non-domestic counterparties." That
decision did not reach `_source_resolver.py`'s M347 gate, which sits in a different
module the ADR's scope never named -- a genuine gap between the two decisions, not a
ruling that the M347 gate is fine.

### Impact

A Spanish filer with real, above-threshold (>3.005,06 EUR/year, or >300,51 EUR for the
cobro-por-cuenta-de-terceros clave) operations with a non-resident counterparty NOT
falling into art. 33.2's narrow exclusions -- e.g. services purchased from or sold to
a non-EU or non-recapitulativa EU counterparty under ordinary rules -- has those
operations SILENTLY ABSENT from their M347 declaration today. No refusal, no advisory,
nothing in the output names anything as dropped; the fichero renders as a
structurally valid, complete-looking file. This is precisely the shape
`no-silent-under-declaration` exists to prevent, and it predates and is independent of
S294's repoint: the gate returns `None` before an observation is ever constructed, so
no row, bound or unbound, was ever going to represent the operation.

## Recommendations

Open a dedicated Step (this audit's own, separate from S302 and S303) to replace the
bare `counterparty_country != "ES"` filter with the legally correct, narrower
exclusion RD 1065/2007 art. 33.2 actually states: operations already reported via a
coincident periodic informativa (the M349 intra-EU case, keyed on `IvaCategory`/
`IntracomOperationType` the way the M349 side of this same resolver already does, not
on bare country) and operations run through the filer's OWN foreign permanent
establishment (art. 33.2.g, a fact this resolver does not currently carry at all and
would need to source or explicitly defer). The Step should also decide how the diseño's
provincia/país compound field (S302's own scope) and this gate interact: a genuine
non-resident declarado can only ever populate país-código once this gate stops refusing
it outright, so país-código's real per-row source is blocked on this fix landing first,
not merely "currently unreachable" as a standing fact -- the two Steps are ordered,
S302's país half depends on this one. A grounded test varying country independently of
`IvaCategory` (a non-EU counterparty with an ordinary, non-excluded operation) is the
proof this fix needs and the current capability-parity test cannot provide.
