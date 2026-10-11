---
tags:
  - '#adr'
  - '#mcp-parity'
date: '2026-10-10'
modified: '2026-10-11'
body_schema: 'body-v2'
body_hash: 'sha256:daf4ac0c2b4d849e35cd2bdf54d25deb8eaab7963a0bdf19d8a9dbc13a86f536'
related:
  - "[[2026-10-10-mcp-parity-agent-provenance-reference]]"
  - "[[2026-10-10-mcp-parity-admission-rulings-adr]]"
  - "[[2026-10-10-mcp-parity-approval-step-adr]]"
  - "[[2026-06-04-llm-ledger-classification-adr]]"
  - "[[2026-06-10-llm-evidence-classification-adr]]"
  - "[[2026-06-30-ledger-add-idempotency-adr]]"
---

# `mcp-parity` adr: `Amounts an agent states carry an agent mark set from the session, the registry computes the tax figures where it can, and only the person's review makes them filing grade` | (**status:** `rejected`)

Rejected on 2026-10-11. The owner ruled first-hand that the command line, the terminal interface and MCP are at parity and that MCP never refuses anything the command line can do: "MCP should aboslutely NEVER refuse anyhting the cli can do" and "I want the cli tui and mcp to be partify. clic can do everythign so should the tui and mcp. no more qesitons". This record made the admission of operations wait on a mechanism, which `2026-10-11-mcp-parity-full-parity-adr` rules out. It is kept as history.

## Problem Statement

The owner admitted `ledger.add`, `ledger.update`, `ledger.classify.single` and `ledger.classify.bulk` to agents. Each accepts a taxable base, a rate and a tax amount from its caller. Today such a write would be stamped `manual`, name the person as its actor, and read as reviewed. Accepted rules say a model selects and the registry derives the regulated figure, and that model output, deterministic grounding and human confirmation stay distinct. The accepted admission rulings leave the provenance of these amounts to this record.

Filing grade here means fit for Cadrumo's local verification and local export. It says nothing about the tax authority's state.

## Considerations

Code facts are in `2026-10-10-mcp-parity-agent-provenance-reference`.

- The actor on these writes is a free-text request field. It authenticates nobody.
- The source command on a row is a constant that names the command-line verb.
- The classifier attribution is a closed vocabulary with no member for an agent caller.
- An executor cannot see who called it. The admission provenance holds the frontend and is kept encrypted, away from the row.
- A registry derivation from category, date and gross already exists and already stamps its own attribution.
- That derivation assumes the gross is base plus tax. The domain model documents rows where it is not: withholding, a surcharge, a self-assessed category.
- Nothing in aggregation reads who entered a row. Review status follows the classification alone.
- The accepted `2026-10-10-mcp-parity-admission-rulings-adr` says a non-sensitive admitted write lands with nobody confirming each one, and that the registry still derives the regulated figure wherever it can.
- The proposed `2026-10-10-mcp-parity-approval-step-adr` defines how the runtime recognises an agent caller on both doors.
- A single agent cannot certify its own work (`2026-10-10-mcp-parity-admission-rulings-adr`).

## Considered options

On the mark:

- **Trust the request's actor field.** No new machinery. Rejected: the caller writes it.
- **Add a separate agent-provenance record beside the row.** Rejected: a parallel vocabulary that every reader would have to join.
- **Extend the existing attribution and actor stamps with an agent member set by the runtime.** Chosen.

On a stated tax amount that disagrees with the derived one:

- **Refuse the write.** Rejected: the agent could not record what a document shows, and a difference of a cent becomes a dead end.
- **Store both as values.** Rejected: a row has one tax amount, and aggregation would have to pick one silently.
- **Store the derived figure, keep the stated one as an observation, and raise a finding.** Chosen. It is the treatment the accepted record gives a figure read by Cadrumo's own reader.

On grade:

- **Filing grade on landing.** Rejected: an unreviewed model statement would reach a verified declaration with no person in between.
- **Advisory and left out of calculation.** Rejected: the agent could not prepare a declaration, which the owner asked for.
- **Counted in a draft calculation, filing grade only after the person's review.** Chosen.

## Constraints

Binding:

1. **The mark.** A ledger write admitted from an agent caller is marked as entered by an agent. The mark is a new member of the existing vocabularies: an agent shape in the classifier attribution, beside `manual`, `auto`, `rule:`, `llm:` and `derived:`, and an agent actor on the row's creation stamp and on each lineage entry. `manual` is reserved to the person.
2. **Where the mark comes from.** The runtime sets it from the session and the connection, at admission. No request field sets or clears it. The request's actor field is a label at most and never decides the mark.
3. **Who is an agent caller.** The gated caller of `2026-10-10-mcp-parity-approval-step-adr`: a connection that declares the MCP frontend, or a peer inside a hosted assistant's process tree whatever frontend it declares. When the evidence cannot be read, the caller is treated as an agent. The command line sends nothing about this. The runtime decides.
4. **Both doors.** The rule is the same for an operation submitted through MCP and for a command the assistant runs. Until the runtime can recognise the assistant's tree, the four writes are refused to that tree on the command line, or the assistant's terminal is not offered.
5. **What the registry computes.** Where the category and the date resolve to one registry rate, and the row is a shape the existing derivation covers, Cadrumo computes the rate, the base and the tax amount, whatever the caller stated. The stored figures carry the derived attribution. The category the agent selected still carries the agent mark.
6. **Disagreement.** A stated figure that agrees with the computed one adds nothing. A stated figure that disagrees is kept on the row as an observation, the computed figure is stored, and the row carries a finding the person resolves. The write is not refused.
7. **Where nothing can be computed.** When the category has no single rate, or the stated facts put the row outside the derivation's shape, the stated amounts are stored as stated with the agent mark. The existing domain checks still apply.
8. **Grade.** An agent-marked row counts in a draft calculation. It is not filing grade until the person has reviewed it. Verification does not grant while a declaration's sources include an unreviewed agent-marked row, and it reports a structured finding that names those rows. No consumer promotes the row on its own.
9. **The person's review.** It is a recorded act bound to the content of the rows it covers. A later agent write to a row marks it again. A row's status never reads as reviewed when its only reviewer was an agent. The review is the person's statement, so an agent caller can ask for it only behind the person's approval, with the rows shown.
10. **What a person sees.** Wherever a row's amounts or classification status are shown to a person, the agent mark and any open finding are shown too: the terminal interface's ledger, the command line's row view, the review queue, the verification report and exported review material. The hand-off approval shows whether agent-marked rows contribute.
11. **Scope of the accepted model rule.** The rule that a model selects and the system derives the tax numbers binds Cadrumo's own classifier and reader, which stay unable to emit a rate, base or amount. An agent caller is not Cadrumo's reader. What it states falls under this record.

Hypotheses, free to change within the commitments:

- The mark's suffix names the requester as the runtime identifies it: a grant, a surface or the assistant's tree.
- The executor receives the caller kind through its context.
- The mark is per row. It may become per field.
- The stated figures of a new row are kept in its raw fields, where a manual row already keeps them.
- The verification finding is an application gate and not a registry-authored predicate.
- One review act may cover many rows.

Not decided here:

- How far a stated tax amount may differ from the computed one before it counts as disagreement. That is a registry rule, and none was found.
- A derivation of the tax amount from a stated base and rate. It needs a grounded registry rule.
- The mark on other facts an agent writes: invoices, profile facts, ratios, rules, wallet entries, local observations. Each is decided when its family is admitted.
- Rows an agent brings in from a provider file. That waits on file exchange.
- Which model stands behind an agent. Cadrumo cannot know it.

To confirm with the owner, because each changes a binding line if answered otherwise: that the person reviews an agent's entries before a declaration using them can be verified, where the alternative is that the export or filing approval only shows how many entries an agent made (lines 8 and 9); that Cadrumo keeps its own computed figure and shows the agent's as a note to resolve, and does not refuse the entry (line 6); and that entries made through the person's own editor's MCP client are marked as agent entries like the hosted assistant's (line 3).

Affected prior rulings, each needing an amendment the owner approves, are listed under Consequences.

## Implementation

We will mark every ledger fact an agent caller states, from the session, and we will compute the tax figures in the registry wherever the existing derivation applies.

- The runtime hands the caller kind to the executor. The four writes stamp the agent mark and stop taking the actor from the request for an agent caller.
- For an agent caller the four writes run the existing derivation and record a finding on disagreement.
- Review status, verification and the person's surfaces read the mark.
- A review act for agent-marked rows is added as a registered operation, reserved behind the person's approval for an agent caller.

## Rationale

The owner's rule gives an agent the writes, and the accepted rules keep the regulated figure with the registry and confirmation with the person. Marking from the session is the only mark an agent cannot forge. Treating a stated figure as the accepted record treats a printed one gives one rule for every number a model produces. Letting marked rows into a draft keeps the agent useful. Holding verification until the person reviews keeps a single agent from certifying its own entries, which the admission rulings already refuse for the hand-off.

## Consequences

- An agent can add, correct and classify entries and prepare a draft declaration with no confirmation per write.
- A declaration built on agent entries cannot be verified until the person reviews them. That is new work for the person, and one review can cover many rows.
- The person's own MCP client is an agent caller. Rows entered through an editor's assistant are marked.
- A same-account process that declares another frontend outside the assistant's tree is not marked. The owner has ruled that such reach is not a security concern.
- The computed figure can be wrong for a row the derivation does not fit. The finding and the review are what catch it.
- The row model, the attribution vocabulary and the verification gate change. Only test data exists, so no stored row is rewritten.
- The packaged agent material needs a line: state the category, and let Cadrumo compute the figures.
- Amendments required once this record is accepted:
  - `2026-06-04-llm-ledger-classification-adr`. "An LLM may select a regulated tax category only from a closed, registry-grounded allow-list with a hallucination guard; it must never emit a tax rate, base, or amount" becomes "Cadrumo's own classifier and reader may select a regulated tax category only from a closed, registry-grounded allow-list with a hallucination guard; they must never emit a tax rate, base, or amount", and gains "An agent that calls a ledger write is a caller and not Cadrumo's reader; what it states is governed by `2026-10-10-mcp-parity-agent-provenance-adr`".
  - `2026-06-10-llm-evidence-classification-adr`. "manual flags override any field and re-stamp manual provenance" gains "when the person's own session writes them. The same fields written by an agent caller carry the agent mark under `2026-10-10-mcp-parity-agent-provenance-adr`".
  - `2026-10-10-mcp-parity-admission-rulings-adr`. Its sentence that the provenance of these writes is still to be recorded becomes "Their provenance is decided in `2026-10-10-mcp-parity-agent-provenance-adr`: what an agent states is marked from the session as entered by an agent, the registry computes the tax figures wherever it can, and the entries are filing grade only after the person's review". Its sentence that an admitted write that is not sensitive lands with nobody confirming each one gains "Landing is not filing grade".
  - The rule source for ledger, invoices and registers says model classification remains a proposal. It is the owner's policy file and is changed only on request; after acceptance it needs a sentence that separates Cadrumo's classifier from an agent caller.
- Reconsider if the owner rules that the hand-off approval is review enough, if a registry rule for base times rate is grounded, or if tree recognition cannot be built on a platform that ships the terminal.
