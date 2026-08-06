---
tags:
  - '#exec'
  - '#conformance-cli'
date: '2026-07-28'
modified: '2026-07-28'
body_hash: 'sha256:1acdfb98e0835cf5756cc9ab8634ec70bd73bee81b45ceed07dd34be51b0442c'
step_id: 'S59'
related:
  - "[[2026-07-27-conformance-cli-plan]]"
---

# declare the full-right-to-deduct article on the prorrata formula legal refs of both M303 revisions rather than only on the enclosing construct, as a coherent two-revision change

## Scope

- `src/cadrumo/_data/registry/aeat/modelos/303`

## Description

- Established what the article actually says and what the formula actually
  needs from it, before adding any citation.
- Confirmed the three-layer coverage precondition on both revisions so the
  change could not break registry load for the worktree.
- Ran the amendment-history check on the added article across both revision
  windows, one of which straddles its only amendment.
- Added the citation to both revisions in one change, each with its grounding
  and its per-window invariance finding recorded at the change site.
- Extended the existing two-revision prorrata gate to pin the declaration per
  revision and their agreement, reusing its probe years rather than
  duplicating them.
- Proved the gate by two mutations, each removing the citation from one
  revision only, and confirmed the failure lands on that revision alone.

## Outcome

The reported gap is real and the article is the right one. Article 94 is
headed "Operaciones cuya realizacion origina el derecho a la deduccion", read
verbatim in the bundled per-article extraction and again in the live
consolidated text. The formula depends on it twice, and neither dependency was
visible from the citations the formula carried. Article 104, apartado Dos,
regla 1a puts in the numerator exactly "las entregas de bienes y prestaciones
de servicios que originen el derecho a la deduccion", and article 94 is the
article that determines which operations those are, so it is the membership
rule for the numerator rather than background colour. It also carries the
no-volume branch this campaign corrected in an earlier Step, where article
102, apartado Uno, leaves the regla de prorrata inapplicable and the input tax
stays deductible in full. A reader of the formula could see neither, because
the article sat only on the enclosing construct.

The change was made on both revisions at once, which is the point of the Step.
The earlier Step deliberately mirrored the newer revision rather than widening
either, because its scope was one directory; this Step has both, so the
citation lands on both in one commit and the gate now asserts the two agree.

The coverage precondition was verified before editing, not after. Formulas are
construct members, and the construct closure validator requires a construct's
legal references to include every reference its members declare. Both
revisions' enclosing construct already carries article 94, so adding it at
formula level is covered by construction and cannot fail the closure check.
That was confirmed by reading both construct declarations, and then confirmed
again empirically by the registry verification below. Had the construct lacked
it, the construct would have had to move in the same commit.

The per-window invariance question was answered on evidence rather than
assumed. Article 94 has exactly two redactions in the consolidated text: the
original, in force from 1 January 1993, and the current one, in force from 1
July 2021 by article 10.14 of Real Decreto-ley 7/2021. That single amendment
rewrites only apartado Uno, numero 1, letra c, which is the enumeration of
exempt operations that nonetheless originate the right, and it is where the
article 20 bis reference was inserted. The chapeau of apartado Uno and the
sujetas-y-no-exentas rule the prorrata numerator rests on are untouched. This
matters specifically for the earlier revision, whose window opens in 2009 and
therefore straddles that amendment date: the grounding does not vary inside
its own window, and it is identical to the newer revision's. Both findings are
recorded at the two change sites so a later reader does not repeat the work.

No legal entry was created or changed, so the registry-and-legal-entry
atomicity constraint is satisfied trivially. Article 94 already exists in the
catalogue at legal-authority tier with a bundled corpus reference, its BOE
document identifier and verbatim required text, and it is already declared on
both enclosing constructs. Its reviewer attribution was left untouched, and in
particular was not re-stamped.

Article 92 was considered and deliberately not added. The Step names the
full-right-to-deduct article in the singular, and article 94 is the one whose
own heading is that concept; article 92 governs which input cuotas are
deductible at all rather than which operations originate the right, so it is a
step further from what this formula reads. Both articles are already on the
enclosing constructs, so nothing is lost by the narrower choice.

The gate was proven capable of failing, and of failing in the right place.
Removing the citation from the newer revision alone failed its parametrisation
and the agreement assertion while the earlier revision's parametrisation stayed
green; removing it from the earlier revision alone produced the mirror result.
That asymmetry is the evidence that the gate detects a per-revision omission
rather than merely reacting to any change. The gate was added to the existing
no-volume grounding module rather than a new one, because that module already
states the article 92 and 94 dependency in prose and already owns the
two-revision probe years, so the declaration assertion and the branch
assertion now stand on the same footing.

Verification run. Registry tree verification reports verified true over 73
modelos, 90 revisions, 15774 casillas, 1256 formulas and 568 legal references,
which is the check that the added reference resolves and that the construct
closure still holds on both revisions. The extended grounding module is 10
passed. The registry prorrata, grounding and legal surface is 447 passed with
workers disabled. The registry revision diff test, which an open Step of this
campaign is separately reconciling, is 13 passed and was not disturbed: the
same citation was added to both revisions, so the inter-revision diff is
unchanged. Format and lint are clean on the changed test module.

## Notes

Semantic discovery was waived for this campaign by operator directive: the
vaultspec-rag index is broken and the service is stopped, so it was neither
started, restarted, reindexed nor probed. Grounding was done with ripgrep plus
whole-file reads, against the loaded registry snapshot rather than fragment
listings for every structural claim, and against the bundled corpus plus a live
consolidated fetch for the legal text.

Peer working state was checked before the first edit on all three files and all
were clean. The index was empty at commit time and the commit named its three
paths explicitly.

One finding is reported rather than fixed, because it is outside this Step and
touches a shared surface. The bundled per-article extraction for article 94 is
a pre-2021 snapshot: it carries the original structure, with the
sujetas-y-no-exentas rule as numero 1 and the exempt-operations and
agencias-de-viajes rules as separate numbered items, whereas the live
consolidated text has the post-2021 structure, with numero 1 subdivided into
letters a to d and the remaining rules renumbered. The catalogue entry's
required text is the article heading, which is present in both redactions, so
the corpus verification passes either way and nothing is currently mis-grounded
by it. It nevertheless means a reader consulting the bundled excerpt for
article 94's current wording gets a superseded one. Refreshing a bundled corpus
excerpt is regulated work affecting every consumer of that article, so it is
flagged here for an operator corpus refresh rather than done inside a
citation-declaration Step.
