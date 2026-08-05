---
tags:
  - '#exec'
  - '#ci-lane-deconflation'
date: '2026-08-05'
modified: '2026-08-05'
body_schema: 'body-v1'
body_hash: 'sha256:984a814819b54e0da386f187977c6fed54b28ac005b868658e7dd6de96e94c4e'
step_id: 'S27'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
---
# Rule on whether the schema-size gate should measure emitted content, its docstring calls itself a proxy for structured content while it directly measures the definition bytes a client actually loads

## Scope

- `src/cadrumo/entrypoints/mcp/tests`

## Description

- Ground the objection's premise in the gate's own docstring before ruling on it.
- Establish whether schema size is a cost in its own right or only a proxy.
- Rule on the instrument, the metadata suppression, and the docstring-discipline collision separately.

## Outcome

The decision record is `2026-08-05-ci-lane-deconflation-schema-size-instrument-adr`.

**The objection was correct on its premises and its premises were incomplete.** The gate's
docstring does say it bounds output-schema size as "the static proxy for the structured
content a verb emits", and titles never appear in structured content, so under that stated
purpose suppressing them reduces the proxy without reducing the target. That reasoning is
sound and was not waved away.

What it lacked is that there are two costs, not one. Structured content is double-emitted per
call and scales with rows returned. But the output schema is transmitted in the tool listing
once per session, and the progressive-discovery record establishes that a client defers tool
loading past roughly 10K definition tokens — so schema bytes are a cost in their own right
with a published threshold behind them.

Against the first target schema size is a weak proxy; against the second it is a direct
measurement. **The instrument is not broken, it is mislabelled**, and the mislabelling is
what made a legitimate reduction look like gaming. The ruling relabels the gate, which costs
one docstring and dissolves the objection rather than overruling it.

## Verification

    sed -n '1,24p' src/cadrumo/entrypoints/mcp/tests/test_result_size_budget.py
    "...bounds the per-verb output-schema size - the static proxy for the structured
     content a verb emits - ... The gate is intentionally static (it reads the
     registered output schemas, no CLI run)"

    rg -n "definition token|10K|ToolSearch|defer" .vault/adr/2026-07-08-mcp-progressive-discovery-adr.md
    44:  July-2026 facts: Claude Code's client-side ToolSearch defers tool loading
    45:  past ~10K definition tokens (default-on since January 2026, BM25 + regex

Both premises read at source rather than accepted from the report that raised them. The
docstring confirms the stated target and, in the same breath, that the gate is deliberately
static — which is the fact that makes "fix it to measure emitted content" structurally
impossible rather than merely expensive.

## Notes

**The convenient answer was available and is named in the record as refused.** Keeping the
proxy, taking the free bytes and moving on would have looked reasonable, and it would have
left the gate's own docstring asserting something false about it — which is precisely how the
next reader re-derives the gaming objection from scratch. The peer who raised the objection
had already declined that answer once; adopting it would have overruled a correct argument
with a shrug.

**Four rulings beyond the relabel.** Metadata suppression is legitimate under the corrected
label, and the record states plainly that it would still have been gaming had the target
genuinely been emitted content — the reason it is not is an argument about the instrument,
not about the remedy. Per-call content remains unbounded and is recorded as a named gap with
a stated shape rather than left as an implication. The docstring-discipline collision is a
real tension and not a contradiction, since that rule mandates cross-links for navigability
rather than verbose prose, so descriptions must NOT be exempted from measurement — they are
genuinely transmitted, and a gate that stops counting a cost it exists to bound has
re-acquired the defect being corrected. And the budget number is calibrated to a moment
rather than derived from the client threshold, which leaves recalibration open with one new
input: roughly 4734 characters of every verb's schema is shared envelope spine no payload can
touch.

**A pattern worth naming, since this is its third instance in one campaign.** An artefact
described itself inaccurately and sent careful readers to a wrong conclusion — after a plan
row naming four broken tests where only three shared a cause, and a consistency check whose
name implied coverage it did not have. An artefact's self-description is evidence about
intent, not about behaviour, and where the two diverge the behaviour is what other decisions
must be built on.

**Three things the record explicitly does not establish**, kept as open rather than resolved
by assertion: whether per-call content needs bounding at all, since nobody has measured what
a large call emits; whether 18000 is right under the corrected label; and whether the ~10K
client threshold applies to this deployment's listing as a whole, given progressive discovery
may mean not every definition loads. The threshold is cited as the reason definition size is a
real cost, not as a computed budget input.
