---
name: aeat-campaign-close-honesty-review
trigger: always_on
---

# AEAT campaign close honesty review

Every campaign close MUST trigger a fresh-context honesty review against the
closure summary BEFORE the campaign is declared structurally complete. An agent
driving execution routinely self-reports "campaign complete" while a substantial
fraction of the work is still structurally incomplete; the honesty review is the
gate that surfaces the hidden items.

The review may be any one of:

1. **An independent code-reviewer dispatch**, given the campaign summary, ADR and
   commit ranges as context. Its findings become new Steps with verification
   gates.
2. **A persona switch on the driving agent**, with the explicit prompt: "review
   the campaign as if you had just inherited it and list what is missing, vague,
   or assumed-but-unverified." Treat the response as a third-party report.
3. **A `vaultspec-curate` invocation** scanning campaign artefacts for
   declarative-versus-action gaps — Steps that say "investigate" or "consider"
   without producing a verification gate, ADR claims with no matching test, audit
   recommendations not tracked as Steps.

Persist the output as a vault audit document, and track every item it surfaces as
a new Step with a verification gate. **The campaign is NOT structurally complete
until honest-pass items are either closed with verification or formally deferred
with a follow-up campaign reference.**

A pattern of recurring multi-item discoveries per pass is expected: each pass
narrows the surface, and full eradication in one campaign is not the gate. The
gate is whether a fresh honest review ran before closure was declared.

**A campaign cannot narrow its own completion criterion.** Scoping work out is a
decision the campaign records about itself; it does not move the standing goal,
and measuring "complete" against the narrowed version is the error — invisible
from inside precisely because the narrowing is documented and reads as rigour.
Write beside every scope-narrowing note what the standing goal still asks for
that it excludes.

Companion: `plan-closure-requires-exec-records`.
