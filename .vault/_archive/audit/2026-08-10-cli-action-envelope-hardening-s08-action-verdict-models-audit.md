---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d2241d89e1d6d2ef51b04c0f0e644a7d5ff66ab713b406a864f8ac8d3d5d0992'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S08 action verdict models review`

## Scope

Formal review of W02.P03.S08 against the accepted ADR and plan. The review
covered application ownership and import boundaries, stable identities, typed
evidence and provenance, argument namespace and resolution consistency,
conditionality, action/no-recovery exclusivity, immutability, deterministic
serialization, presentation-prose exclusion, facade exports, and test strength.

## Findings

### s08-action-verdict-models | high | Localized and raw command prose can enter the verdict through evidence values

The ADR requires typed verdicts not to carry localized command prose, but the
constraint is present only in the `PreconditionVerdict` docstring.
`ConditionEvidence.values` accepts arbitrary nonblank mapping keys and arbitrary
strings. An adversarial construction with key `operator message` and value
`Run aeat config profile create NAME` validated and serialized unchanged. This
allows migrated producers to retain exactly the free-form action authority the
new contract is intended to remove, hidden inside an otherwise typed evidence
record. The tests do not exercise this prohibition.

Resolution: closed on re-review. Evidence keys now use the stable fact-key
grammar and reject presentation/action tokens, while string values reject raw
`aeat` command prose. Both plain and backtick-delimited command probes failed.
Legitimate factual strings containing AEAT-labelled registry paths, revision
identifiers, and filesystem paths remain accepted, so the rule does not reduce
all AEAT-related evidence to prose.

### s08-action-verdict-models | high | Condition-evidence bindings do not join to their declared evidence or value

`ActionArgumentBinding` validates its own resolved/missing shape but
`PreconditionVerdict` never resolves a `CONDITION_EVIDENCE` source against the
verdict's evidence. A resolved binding with
`source_key=profile.active.nonexistent` and value `different` was accepted next
to evidence containing `profile_key=operator`. Consequently the model can
claim a binding is resolved from condition evidence when the named evidence
does not exist and the value contradicts the observed fact. Later live-schema
sufficiency checks cannot establish the provenance truth that this application
verdict has already asserted.

Resolution: closed on re-review. A condition-evidence binding now carries both
`source_evidence_id` and `source_key`; the verdict joins them to an evidence row
and exact fact, then requires exact value and runtime type equality. Direct
probes rejected a missing evidence identity, missing fact key, contradictory
value, and type mismatch. The binding model also rejects absent evidence IDs
for condition-evidence sources and evidence IDs on other source namespaces.
Missing arguments remain source-free and validate only with
`requires_arguments` conditionality and the exact missing-name set.

### s08-action-verdict-models | medium | Equivalent verdicts do not serialize canonically

Evidence value maps are frozen and lexically sorted, but evidence rows,
argument bindings, and missing argument names retain caller order. Reversing
two unique evidence rows produced different JSON for the same semantic verdict.
This weakens deterministic snapshots, hashing, and cross-surface comparisons;
the current serialization test proves one chosen input order, not canonical
ordering across equivalent constructions.

Resolution: closed on re-review. Evidence rows, argument bindings, and missing
argument names are canonicalized by stable identity after uniqueness checks.
Verdicts constructed with reversed evidence and binding inputs now produce
identical JSON. Evidence maps remain lexically ordered and deeply immutable.

No architecture-boundary defect was found. The package imports no entrypoint,
Typer, or Click module, contains no guard predicate or catalogue, and importing
its facade loaded zero `cadrumo.entrypoints` modules. Namespaced identifier
patterns, typed provenance, local resolved/missing binding shape, unique
evidence and argument identities, action/no-recovery XOR, terminal/safety/
operator-decision outcomes, conditionality, frozen models, and deep freezing
of the evidence map behaved correctly.

Validation evidence: all seven focused unit tests passed; Ruff passed; and
basedpyright reported zero errors, warnings, or notes. Direct adversarial
constructions reproduced each finding without mocks or mutation of production
code.

Remediation validation: all 13 focused unit tests passed; Ruff passed; and
basedpyright reported zero errors, warnings, or notes. Independent adversarial
probes covered raw prose, legitimate factual strings, every evidence-join
failure arm, missing bindings, order equivalence, and deep immutability. No S08
findings remain open.

## Recommendations

1. Make the no-localized/raw-command-prose boundary executable across every
   string-bearing verdict field, including evidence keys and values, while
   retaining typed factual strings that are not presentation or action prose.
2. Define an unambiguous evidence-value namespace for binding sources and join
   every `CONDITION_EVIDENCE` binding to an evidence identity plus exact fact
   key/value inside `PreconditionVerdict`; reject missing and contradictory
   references.
3. Canonicalize evidence rows, argument bindings, and missing argument names by
   stable semantic identity before serialization, and test equality across
   reversed equivalent inputs.
4. Add adversarial production-importing tests for all three boundaries while
   preserving the clean application facade and existing XOR/conditionality
   coverage.

All recommendations are implemented and verified.
