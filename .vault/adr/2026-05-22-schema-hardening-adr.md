---
tags:
  - '#adr'
  - '#schema-hardening'
date: '2026-05-22'
modified: '2026-05-22'
related:
  - "[[2026-05-22-schema-hardening-research]]"
---



# `schema-hardening` adr: Warning-sidecar broad suppressor burn-down | (**status:** `accepted`)

## Problem Statement

The semantic-role typo-warning surface now has a zero-warning current state for
Modelos 100 and 200, but W14 showed that the state is partly maintained by two
legacy broad suppressors:

- `optional_or_numeric_token_strip`, which strips optional words and all
  numeric tokens.
- `axis_token_group`, which suppresses one-token differences across mixed
  token groups.

This is risky in a registry derived from law and regulatory publications. Year
tokens, line numbers, article/regime context, internal/international
distinctions, and source-family terms can be legally meaningful. A broad
warning suppressor can hide a legitimate singleton just as surely as it can
hide a typo-warning false positive.

The project needs a policy for reducing these broad suppressors without
blindly rewriting registry semantic roles or inventing legal equivalence.

## Considerations

The W14 debrief found that disabling `optional_or_numeric_token_strip` would
expose 36 independent Modelo 100 and Modelo 200 warnings. These include
C Valenciana public-aid years, estimacion objetiva agricultural variants,
prizes/gambling public-source or line variants, cadastral slots, generated and
pending rows, quoted-fund `coti` branches, and Modelo 200
`con/sin mantenimiento de empleo` correction families.

The same debrief found that disabling `axis_token_group` would expose 17
independent warnings. These include Anexo C `periodo`/`aplicado`, RIC Canarias
type letters, birth/death dates, ascendiente/descendiente fields, liquidacion
roman numerals, internal/international DI, and detail/other corrections.

Prior successful slices established a safer pattern:

- Broad CCAA normalization was removed and legitimate region-local singletons
  were marked explicitly.
- Broad legal-reference stripping was removed and legitimate legal-reference
  singletons were marked explicitly.
- Exact source-backed helpers were accepted for Anexo C carryforward baskets,
  deferred-imputation slots, and approved family-local generated/pending
  families.

Three options were considered:

- Keep broad helpers indefinitely. This preserves a quiet warning count but
  leaves legal identity hidden in validator internals.
- Remove broad helpers immediately. This maximizes visibility but produces a
  large warning spike before source policy can distinguish true typos from
  legitimate singletons.
- Burn down broad helpers family by family. This keeps the warning surface
  usable while replacing generic suppression with exact source-backed
  decisions.

## Constraints

All legal semantics must be grounded in committed registry source, AEAT
publications, BOE/legal references, or prior approved vault audit records.

No code path may treat a repeated label or similar role spelling as legal
equivalence on its own.

Warning suppression is not metadata extraction and is not a registry role
rewrite. Any future structured extraction needs its own source-backed policy.

Plan rows must be managed through `vaultspec-core vault plan`, not hand-edited.

Tests must exercise real code and committed registry behavior. They must not
use mocks, stubs, monkeypatching, skipped assertions, or tautological mirrored
business logic.

## Implementation

Adopt family-by-family burn-down for broad warning suppressors.

The first follow-on sub-plan should target `optional_or_numeric_token_strip`
because it has the highest-risk current exposure. The plan should:

- inventory the 36 exposed optional/numeric warnings into source families,
- manually look up official source context for candidate families,
- replace generic suppression only for approved exact families,
- mark legitimate one-off source-specific rows as intentional singletons when
  exact-family suppression is not appropriate,
- add boundary tests that prove adjacent legal/year/field concepts remain
  non-siblings,
- keep the broad helper in place until enough exact replacements exist to
  remove or shrink it without uncontrolled warning noise.

The second follow-on should target `axis_token_group` token group by token
group, not as one global helper.

The W14 debrief research and the schema-hardening reference are the authority
for the initial candidate ranking and boundary rules.

## Rationale

Family-by-family burn-down is the only option that satisfies both safety
requirements:

- It prevents the validator from hiding legal identity behind generic token
  stripping.
- It avoids a blind removal that would turn all source-specific singleton
  cases into undifferentiated warnings.

The approach repeats the successful W12 and W13 pattern: remove or narrow broad
normalization only after source-visible legitimate singletons have an explicit
policy, and only after tests prove the legal boundary.

Prior exact helpers show that warning-sidecar behavior can be useful when the
preserved base is source-grounded and narrow. Broad helpers should converge
toward that shape.

## Consequences

The warning count may remain artificially quiet during transition because the
broad helper stays in place until replacements exist. Each slice must therefore
report both current emitted warnings and simulated warnings with the target
helper disabled.

The work will be repetitive. That is intentional: each family must carry its
own source lookup, examples, tests, and vault audit trail.

Some exposed pairs will become exact source-backed warning siblings. Others
will become explicit intentional singletons. Some may reveal true role typos or
registry modelling defects and need separate correction policy.

The ADR does not authorize global normalization of numeric tokens, optional
words, `interna`/`internacional`, roman numerals, `detalle`/`otras`, or
relationship/event tokens.
