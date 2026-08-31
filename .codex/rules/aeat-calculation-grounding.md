---
name: aeat-calculation-grounding
trigger: always_on
---

# AEAT calculation grounding

## Filing-grade authority

- A filing-affecting formula, rate, threshold, classification, or relationship must be grounded in the official AEAT/BOE authority that governs the exact modelo, revision, period, territory, and taxpayer conditions.
- Cite the specific provision, official instruction, record design, schema, or worked example used. A generic landing page, search result, third-party summary, or another year is not sufficient authority.
- Preserve provenance from source capture through the compiled registry, calculation result, explanation, and filing handoff. A value without traceable authority cannot be promoted to filing grade.
- Load behavior through the validated registry authority. Raw TOML inspection is useful for diagnosis but does not establish compiled behavior.

## Implementation

- Encode legal variation as typed registry data or a shared domain mechanism, not as duplicated modelo-specific branches.
- Keep applicability, units, sign, rounding, temporal window, dependencies, and exclusions explicit. Do not infer law from labels or field numbering.
- A total is complete only when every required component is present or explicitly classified by the governing contract. Suspicious absence must remain visible under `no-silent-under-declaration`.
- Cross-check representative live inputs against an independent official example or separately implemented oracle where one exists. Expected values copied from the implementation under test are not independent evidence.

## Change evidence

For a calculation change, retain the authoritative source reference, the registry or code location that carries it, and focused tests covering the normal case plus material boundaries and exclusions. If the official evidence is ambiguous, keep the capability advisory or unsupported rather than guessing.
