---
name: aeat-campaign-close-honesty-review
---

# AEAT campaign close honesty review

Every campaign close MUST trigger a fresh-context honesty review against the closure summary BEFORE the campaign is declared structurally complete. The agent driving execution routinely self-reports "campaign complete" while a substantial fraction of the work is still structurally incomplete. The honesty review is the gate that surfaces the hidden items.

The review may be performed by one of:

1. Independent code-reviewer agent dispatch. Use vaultspec-code-reviewer with the campaign summary, ADR, and commit ranges as context. The reviewer's findings become new Steps with verification gates.

2. Persona switch on the driving agent. Explicit prompt: "review the campaign as if you had just inherited it and list what is missing, vague, or assumed-but-unverified." Treat the response as a third-party report. Track the items as Steps.

3. vaultspec-curate skill invocation. Scan campaign artefacts for declarative-vs-action gaps - Steps that say "investigate" or "consider" without producing a verification gate; ADR claims that don't have a matching test; audit-document recommendations that aren't tracked as Steps.

Persist the honesty-review output as a vault audit document. Track every item it surfaces as a new Step with a verification gate. The campaign is NOT structurally complete until honest-pass items are either closed with verification or formally deferred (closed with a follow-up campaign reference).

A pattern of recurring multi-item discoveries per pass is documented and expected. Each pass narrows the surface; full eradication in one campaign is not the gate. The gate is: did a fresh honest review run before closure was declared?