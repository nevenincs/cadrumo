---
tags:
  - '#audit'
  - '#cli-action-envelope-hardening'
date: '2026-08-10'
modified: '2026-08-10'
body_schema: 'body-v1'
body_hash: 'sha256:d75f264f51ba9851f8e825b286369d1395400cf82a64c47ef9b1c6ab207b1119'
related:
  - "[[2026-08-09-cli-action-envelope-hardening-adr]]"
---

# `cli-action-envelope-hardening` audit: `S10 action contract tests review`

## Scope

Reviewed the complete `operator_actions` test package against the accepted ADR,
the S08 models, the S09 catalogue, and `W02.P03.S10`. The review covered direct
production imports, strict identities, duplicates, binding consistency,
conditionality, every no-recovery kind, XOR, deterministic serialization,
prohibited prose, and exact catalogue membership. Focused verification passed:
26 tests, Ruff, and basedpyright. Independent adversarial constructions
confirmed that production rejects the uncovered invalid states described below.

## Findings

### duplicate-verdict-members | medium | Verdict duplicate rejection is not locked by tests

Catalogue duplicate action IDs and argument specifications are covered, but
`test_models.py` does not construct duplicate evidence IDs, duplicate binding
argument names, or duplicate public missing-argument names. Production rejects
all three today; removing those validators would nevertheless leave S10 green.

Resolution: closed on 2026-08-10. A direct parameterized production-model test
now rejects duplicate evidence IDs, duplicate binding argument names, and
duplicate public missing-argument names.

### no-recovery-consistency | medium | Closed outcomes are tested only on their valid path

All three no-recovery kinds and the action/outcome XOR are covered. The tests do
not prove that no-recovery rejects bindings and missing names, that no-recovery
requires not-applicable conditionality, or that an action rejects
not-applicable. Production rejected each adversarial construction, but those
safety branches lack regression protection.

Resolution: closed on 2026-08-10. Direct production-model cases now reject a
no-recovery outcome carrying arguments, a no-recovery outcome using immediate
conditionality, and a recovery action using not-applicable conditionality. The
positive matrix still covers all three closed outcome kinds and XOR.

### strict-field-identities | low | Strict identifier coverage does not span every identifier field

Malformed action IDs, condition IDs, and argument names are tested. Direct
malformed cases are absent for failed-condition IDs, evidence IDs, source keys,
source-evidence IDs, target command keys, and catalogue source keys. Production
patterns currently reject them, so this is incomplete proof rather than an
observed acceptance defect.

Resolution: closed on 2026-08-10. Parameterized malformed-input tests now cover
failed-condition ID, evidence ID, binding source key, binding source-evidence
ID, catalogue target command key, catalogue source key, and catalogue
source-evidence ID in addition to the previously covered identities.

## Recommendations

Add direct production-model cases for all duplicate surfaces and invalid
no-recovery/action conditionality combinations, plus a compact parameterized
matrix for the remaining identifier fields. Keep the suite application-only:
it correctly contains no Click, entrypoint, live-schema, or test-side resolver
mirroring. Live result/input-schema resolution and catalogue binding
sufficiency remain explicitly owned by `W02.P04.S14`.

All recommendations are satisfied. Re-review verification passed 39 focused
tests, Ruff, and basedpyright with zero errors, warnings, or notes. The added
tests instantiate production records directly and introduce no entrypoint,
live-schema, resolver, fake, mock, patch, or mirrored validation logic.
