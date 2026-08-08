---
tags:
  - '#exec'
  - '#unstructured-document-ingestion'
date: '2026-08-08'
modified: '2026-08-08'
body_schema: 'body-v1'
body_hash: 'sha256:7984e7c5c8e2f054b10dbb39e215ae096f250d749f2ef3a95d743156351cc63f'
step_id: 'S254'
related:
  - "[[2026-08-07-unstructured-document-ingestion-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace unstructured-document-ingestion with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S254 and 2026-08-07-unstructured-document-ingestion-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Close the second leak vector on the internal fault projection: a violation's loc tuple reproduces mapping KEYS as well as field names, so a taxpayer identifier used as a dict key reaches the context verbatim. Reproduced through pydantic directly, loc is by_party then the identifier itself, and the helper's docstring claiming the field path is not sensitive is false for that case. The message vector was closed separately by withholding value_error and assertion_error prose while reporting the error type and the raising exception class, but loc is a different vector on the same helper with the same guarantee and the same confidentiality class. NOT a filter: telling a key from a field name needs the model class, which a ValidationError does not carry, so it is a design change, and a pattern-matching redactor there would be exactly the guess the projection exists to avoid. Reachability measured rather than assumed: the outbound boundary's result-model tree carries exactly one string-keyed mapping whose keys are per-modelo detail-row field names, so it is not reachable with taxpayer data there today, while the stored-data boundary accepts arbitrary persisted records and was not enumerated. Same unreachable-today-but-guarded-elsewhere shape that justified the message vector and ## Scope

- `src/cadrumo/entrypoints/cli` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Close the second leak vector on the internal fault projection: a violation's loc tuple reproduces mapping KEYS as well as field names, so a taxpayer identifier used as a dict key reaches the context verbatim. Reproduced through pydantic directly, loc is by_party then the identifier itself, and the helper's docstring claiming the field path is not sensitive is false for that case. The message vector was closed separately by withholding value_error and assertion_error prose while reporting the error type and the raising exception class, but loc is a different vector on the same helper with the same guarantee and the same confidentiality class. NOT a filter: telling a key from a field name needs the model class, which a ValidationError does not carry, so it is a design change, and a pattern-matching redactor there would be exactly the guess the projection exists to avoid. Reachability measured rather than assumed: the outbound boundary's result-model tree carries exactly one string-keyed mapping whose keys are per-modelo detail-row field names, so it is not reachable with taxpayer data there today, while the stored-data boundary accepts arbitrary persisted records and was not enumerated. Same unreachable-today-but-guarded-elsewhere shape that justified the message vector

## Scope

- `src/cadrumo/entrypoints/cli`

## Description

- Establish what a pydantic validation error actually exposes, since the fix
  turns on whether the failing model can be recovered from the error alone.
- Project the failing path under the same rule as the message: a string
  component is emitted only where the model's own tree declares it as a field
  name, and replaced otherwise.
- Accept the model as an optional argument on the projection and on the
  outbound boundary, and supply it at the one raise site that validates exactly
  one model.
- Correct the docstring, which recorded this as a known gap.

## Outcome

Modified: `src/cadrumo/entrypoints/cli/_errors.py`,
`src/cadrumo/entrypoints/cli/_modelo_work_calculate_cli.py`,
`src/cadrumo/entrypoints/cli/tests/test_internal_fault_context_withholds_the_value.py`.

**The premise was checked rather than inherited.** A pydantic `ValidationError`
exposes `title` -- the model's NAME as a string -- and nothing else structural,
confirmed against the installed version. So a component genuinely cannot be
classified from the error alone, and the missing half has to come from the
caller.

**The rule: a string component is emitted only if the failing model's tree
declares it as a field name.** Field names are source identifiers and cannot be
taxpayer data; the repository declares no dynamically-named models, so that
invariant holds by construction rather than by convention. The allowlist is a
flat set of names across the whole tree rather than a positional walk of the
annotation graph, deliberately: the question is "could this be data", not "which
model owns this", and a positional walk that mishandles a union, a generic or a
forward reference fails OPEN.

**Without the model every string component is replaced.** That is a real loss of
detail and the direction to fail in. `failing_record` and the broken rule still
identify the contract, and the error log still holds the unredacted payload.
Pattern matching a component against identifier shapes was rejected for exactly
the reason it was rejected for the message vector: it is a guess about what is
sensitive, which is what this projection exists to avoid.

**Components are replaced, never elided**, so the path keeps its depth. Dropping
one would make a mapping indistinguishable from a plain nested field, hiding a
mapping precisely where an engineer needs to see one.

Measured through the real projection. A record with a mapping keyed by an
intra-community VAT identifier and a nested row previously emitted that
identifier verbatim in the path. With the model supplied it now reads
`by_party.<key>` and `rows.0.quantity` -- the identifier gone, the declared field
names and the list index intact. With no model it reads `<key>.<key>` and
`<key>.0.<key>`, carrying nothing.

**Coverage, stated rather than implied:** of the three raise sites reaching this
boundary, one validates exactly one model and now names it. The other two guard
blocks in which several models are validated and cannot say which failed, so they
name none and take the redacted path. Narrowing those blocks would change
behaviour beyond this row.

## Verification

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests -n0 -q -m unit
    15 failed, 748 passed, 3027 deselected in 306.17s (0:05:06)

Every one of the fifteen is a single uncommitted peer file: a registry export
layout TOML is mid-edit and currently unparseable, raising
`invalid TOML: duplicate key: 'required' ... at line 329`, which fails any test
that builds a catalogue invoice. HEAD's copy of that file parses. This is a
tree-wide breakage owned elsewhere, not a consequence of this change.

    uv run --no-sync pytest src/cadrumo/entrypoints/cli/tests/test_internal_fault_context_withholds_the_value.py -n0 -q
    11 passed in 1.28s

Mutation-proved from outside the repository, asserting the leak was observably
restored before reporting: projecting the path verbatim again reds 3 cases,
including both the model-supplied and the no-model direction.

## Notes

One in-scope regression, absorbed rather than worked around: a case landed with
the message vector asserted a literal field name while supplying no model, so the
new default correctly redacted it. The fixture now names the model, which is what
a real caller does, and the fail-safe direction is asserted separately instead of
being the accidental default of every case.
