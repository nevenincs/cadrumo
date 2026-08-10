---
tags:
  - '#exec'
  - '#synced-history-consumption'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
step_id: 'S12'
related:
  - "[[2026-08-08-synced-history-consumption-plan]]"
  - "[[2026-08-08-synced-history-consumption-adr]]"
---

# Wire the pulled filed observation to the divergence primitive

## Scope

- `src/cadrumo/application/modelo`

## Description

- Re-read the row against HEAD before building, rather than executing it as
  written.
- Establish that the row's blocking precondition was satisfied by the scoping
  condition landed under the preceding row.
- Mirror the in-tree counterpart-reconcile shape instead of authoring a new one.
- Resolve the registry revision inside the function from the work unit's own
  triple.
- Carry each finding's grounding from the diverging casilla's own registry
  definition.
- Wire it into the verify path beside its siblings.
- Cover it with four cases over a real isolated encrypted profile.
- Fix the routing defect that coverage exposed, with the assertion that pins it.

## Outcome

The taxpayer's own calculation is now compared against the filing AEAT holds for
the same modelo and period, scoped so an empty bucket says nothing.

THE ROW'S PREMISE WAS PARTLY FALSE AND THE ROW SURVIVES IT. The row states that
both sides live in the same bucket and nothing joins them. A join exists and is
reachable from the shipped CLI: the filed-state verification path loads a
captured observation and compares it against a live registry calculation. What
that path does NOT do is consult the taxpayer's own calculation — it re-runs the
engine using the FILED declaration's own input casillas, so it asks whether this
engine reproduces AEAT's arithmetic from AEAT's inputs. That is engine drift. The
row's question is whether the taxpayer's working disagrees with what they filed,
and nothing answered it. The two are deliberately kept apart rather than
collapsed, and the module says so where a later reader will find it.

WHAT THE NARROWING EXCLUDES, stated because a narrowing that is not written down
becomes invisible. The original row said "wire the pulled filed observation to
the divergence primitive", which read as though the engine-drift comparison were
also missing. It is not, and this row does not rebuild it. A reader wanting
engine-versus-AEAT reconciliation is served by the existing path, not by this
one.

THE BLOCKING PRECONDITION WAS SATISFIED, NOT WAIVED. The row is explicit that it
is blocked rather than at risk: a freshly onboarded profile computes zero nearly
everywhere, so comparing every pulled figure against it raises a mismatch on
essentially every reconciled casilla. The preceding row established that a
populated-enough condition IS derivable at casilla granularity, and this wiring
consumes it. An untouched bucket produces no findings at all.

GROUNDING IS CARRIED, NEVER MINTED. Each finding carries the diverging casilla's
own legal and source references. A divergence asserts no legal proposition of its
own — it says the value the registry grounds at these references does not match
what was filed — so its grounding is the casilla's grounding passed through. The
registry schema types both reference tuples as minimum-length-one on every
casilla definition, so there is always something to carry and no substitution
path exists. No unreachable guard was written for a branch the schema forbids;
the omission is stated here instead of being silently absent.

THE REVISION IS RESOLVED INSIDE THE FUNCTION from the work unit's own triple
rather than accepted as a parameter. That closes the stored-revision-id injection
path by signature rather than by discipline: no caller can feed a stored id in as
the selector, because there is no parameter to feed. A resolution failure returns
no findings rather than raising — an advisory reconcile must not turn an
unpublished filing year into a verification error.

## Notes

THE COVERAGE FOUND A REAL DEFECT IN THE MODULE IT COVERS, which is the argument
for the row not having been closed on the implementation alone. The finding model
already declares an optional casilla coordinate and the reconcile left it unset,
so the one field an automated operator would route on was recoverable only by
parsing the rendered message. That is the same route-on-a-field-not-prose defect
an earlier row fixed on the notice channel, reintroduced on the finding channel
by omission rather than by design. It was found by WRITING the test, not by
reading the code, and it was fixed with the assertion that pins it in the same
change.

THE ROW WAS HELD OPEN DELIBERATELY between the implementation landing and the
coverage landing, and the record says so rather than presenting one commit. A new
advisory on a filing-grade verify path with no test is a vacuous-green shape, and
separately a new module with no test is a tree-wide gate failure in its own
right — two independent reasons the intermediate state was not completion.

VERIFICATION WAS NOT RUN BY THE AUTHOR, and neither was it run by the author of
the coverage. The suite authority holds that role, ruled the lane by measuring
the convention rather than reasoning from marker prose, and re-runs everything
regardless of what any author reports.

ONE ITEM IS OUTSTANDING AT THE TIME OF WRITING. Several fixture fields were left
at their defaults with documented reasons, and that documentation had not been
audited against the populate-non-default rule when this record was written. A
field left at its default proves nothing about a save-drops-field boundary,
because the default is exactly the state such a regression collapses to. It was
flagged rather than claimed clean, and a separate audit owns it.
