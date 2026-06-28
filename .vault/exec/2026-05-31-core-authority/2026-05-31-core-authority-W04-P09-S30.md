---
step_id: S30
tags:
  - '#exec'
  - '#core-authority'
date: '2026-05-31'
modified: '2026-05-31'
related:
  - '[[2026-05-31-core-authority-plan]]'
  - '[[2026-05-31-core-authority-adr]]'
  - '[[2026-05-31-core-authority-action-tracker-v2-reference]]'
---

# core-authority W04.P09.S30 — CCAA placement audit (RELOC-021)

## Outcome

**Placement decision (one sentence):** CCAA stays in `domain/profile/_ccaa.py`; Rule 1(a) is satisfied (3 application-layer consumers confirmed), but the ADR explicitly defers promotion to `core/` until adapters or `core/` also consume it directly.

## Evidence

Consumer scan via ripgrep against production imports (non-test, non-pycache):

- `src/aeat/application/modelo/_actions.py:108` — `from ...domain.profile._ccaa import CCAA`
- `src/aeat/application/wizard/_catalogue.py:31` — `from ...domain.profile._ccaa import CCAA`
- `src/aeat/application/wizard/_commands.py:62` — `from ...domain.profile._ccaa import CCAA` (TYPE_CHECKING guard)
- `src/aeat/core/profile.py:153` — lazy accessor comment only (no direct import)
- `src/aeat/domain/calculations/registry/_schema.py:376` — uses CCAA values via `_CCAA_CODES` frozenset (string literals, no import)

Rule 1 clause (a) is triggered: CCAA is imported by code outside `domain/` (application layer). The ADR rationale (§Rule 7): "CCAA stays in domain/profile/ because it is not currently consumed outside the domain layer (Rule 1 clause (a) not satisfied; reassess if adapters or core/ begin consuming it)." This ADR text predates the full scan; the actual state shows 3 application consumers. However the ADR's explicit decision to defer promotion to a future reassessment is preserved — core/ and adapters/ do not consume CCAA directly, and the application-layer consumers are legitimate downward imports under the hexagonal direction (application → domain is legal). No Rule 2 violation exists.

**Promotion decision:** DEFERRED. Promotion to `core/geography.py` is warranted by Rule 1(a) but not executed in W04 because: (1) the application→domain direction is legal per Rule 2 (no violation); (2) the ADR's explicit decision recorded at §Rule 7 is to reassess at adapters/core consumption; (3) no adapters or core modules import CCAA. Document as a follow-up trigger: when any adapter or core module imports CCAA, promote to `core/geography.py`.

## CalendarCCAA / CCAA semantic divergence finding (input to S31)

The semantic audit classified CalendarCCAA as "100% geographic duplicate" of CCAA. Direct code inspection refutes this:

| Attribute | CalendarCCAA | CCAA |
|---|---|---|
| Value format | ISO 3166-2:ES codes (ES-AN, ES-MD) | lowercase Spanish names (andalucia, madrid) |
| Member count | 19 (all communities + Ceuta + Melilla + País Vasco + Navarra) | 15 (common-regime only, foral excluded) |
| Domain | BOE holiday calendar parsing | Tax-residence filing profile |
| TOML usage | `ccaa_code = "ES-MD"` in festivos-*.toml | `value = "madrid"` in dispatch tables |

These enums are NOT semantically identical. Merging them would require changing TOML data files or adding ISO-code members to CCAA (violating "Do NOT change enum values"). S31-S32 are blocked by this finding and are deferred to a follow-up plan with explicit scoping.

## Files touched

None (audit-only step).

## Commit

Audit-only; no commit required for this step. Decision is documented here and referenced in S31 block record.
