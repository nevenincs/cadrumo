---
tags:
  - '#audit'
  - '#code-dedup-sweep'
date: '2026-08-07'
modified: '2026-08-07'
body_schema: 'body-v1'
body_hash: 'sha256:266313fa60ac461e8cb90c60a1a2dd3ef3ddcb10872371e897228bc91c75bd16'
related:
  - '[[2026-07-25-code-dedup-sweep-rag-inventory-audit]]'
  - '[[2026-08-07-code-dedup-sweep-status-header-audit]]'
---

# `code-dedup-sweep` audit: `D1-1 dual binding-validator convention: refuted`

## Status: SUPERSEDED

This note is superseded by the parent document itself. A full read of
`2026-07-25-code-dedup-sweep-rag-inventory-audit` (754 lines, not the ~200-line
sample this note was written against) found the same conclusion already recorded
there, in more detail, at heading `refuted-2-dual-binding-validator-convention` —
written before this note, independently. That entry additionally names two real
follow-on defects this note does not: false "defence-in-depth" docstrings on the
raise-style bodies, and inconsistent public/private visibility of the delegate
across binding families.

This note is kept, not deleted, as a record of independent corroboration and of
the miss that produced it: the parent document is not a stale worklist but an
actively-maintained rolling log where an early finding's resolution is recorded
as a *later* addendum, often hundreds of lines below the finding it resolves. A
reader who samples the head of the document — as this note's author did — sees
only the open claim and never reaches the resolution. That findability gap, not
document staleness, is the durable finding; see
`2026-08-07-code-dedup-sweep-status-header-audit` for the remediation (a status
index prepended to the parent document).

## Scope

As originally written; retained for the record. Confirming pass over finding D1-1 of the standing `2026-07-25-code-dedup-sweep-rag-inventory-audit`
document, which the audit's own text flags as "RAG-reported and UNCONFIRMED against
HEAD, requiring targeted `rg` confirmation before acting." This note carries that
confirmation for D1-1 only; it does not curate the parent document, which belongs to
the standing dedup campaign already active on this feature tag.

## Findings

### D1-1 dual binding-validator convention: refuted | high | four raise-style functions flagged as an unregistered second convention are each the sole registered callback for their family, wrapped by the one sanctioned generic accumulator

D1-1 claimed a dual binding-validation convention: a `-> None` raise-style function
alongside the registered `-> list[str]` accumulator contract that
`binding-validation-single-contract` mandates, naming four functions in
`src/cadrumo/domain/calculations/registry/_ledger_bindings.py`
(`validate_ledger_oss_aggregation_binding_definition`,
`validate_ledger_iva_aggregation_binding_definition`,
`validate_ledger_renta_gastos_estimacion_directa_aggregation_binding_definition`,
`validate_ledger_renta_gastos_pago_fraccionado_aggregation_binding_definition`, plus a
fifth, `validate_ledger_renta_income_aggregation_binding_definition`) as an
unregistered, competing validation path.

`rg` confirms each of the five is called from exactly one site: a paired public
`-> list[str]` function immediately below it in the same file that returns
`invariant_diagnostics(binding, "<family>", validate_ledger_*_binding_definition)`.
`invariant_diagnostics` is the shared accumulator primitive — it invokes the raise-style
body, catches the raise, and returns the accumulated diagnostics as the `list[str]`
contract requires. Each of those five wrapping functions is itself the one entry
registered in `_BINDING_VALIDATOR_REGISTRY` for its `BindingSourceKind`
(`src/cadrumo/domain/calculations/registry/_bindings.py:992`), confirmed by the
registry's own comment at line 286: "source family registers exactly one in
`_BINDING_VALIDATOR_REGISTRY`."

So the raise-style function is not a second, unregistered validator competing with the
registered one — it is the body the registered accumulator wraps. This is exactly the
composition the governing rule `binding-validation-single-contract` sanctions ("a single
`validate(binding) -> list[str]` validator... registered in the one binding validator
dispatch table"): one registered contract per family, implemented as an accumulating
wrapper around a raise-style body, never two competing conventions.

The searcher that produced D1-1 matched on function-name shape (`-> None` raise-style
vs. `-> list[str]` accumulator) without following the call graph from the raise-style
function to its sole caller. The audit's own confirming-pass instruction anticipated
exactly this blind spot; this note is that pass, and it refutes the finding.

## Recommendations

No action against D1-1 or the parent document from this note: it is already closed
there at `refuted-2-dual-binding-validator-convention`. Do not delete or "unify" the
raise-style bodies — they are the load-bearing implementation the registered
accumulator wraps, and the parent document's entry already says so.

Read `2026-08-07-code-dedup-sweep-status-header-audit` for the actioned remediation
(a status index prepended to the parent document) rather than treating this note as
the current word on D1-1.

General lesson, still valid despite the retraction: semantic (RAG) results are
discovery input, never proof. A finding phrased as "two functions with the shape of
a dual convention" requires a call-graph confirming pass — same discipline as
`independence-of-agent-is-not-independence-of-method` (agreement without a differing
instrument is not corroboration) applied to a single searcher's own shape-only match.
That discipline caught the original D1-1 finding's error; it did not, on its own,
catch that the parent document had already caught it too — that required reading the
whole document, not just re-deriving the same conclusion from the code.
