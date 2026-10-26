---
tags:
  - '#audit'
  - '#object-name-declustering'
date: '2026-09-07'
modified: '2026-10-03'
body_schema: 'body-v2'
body_hash: 'sha256:bd074befb416d8b51705ef7baf745180be7bcbea48df67b21fab1489a2610eb2'
related:
  - "[[2026-09-02-object-name-declustering-adr]]"
  - "[[2026-09-07-object-name-declustering-s28-implementation-review-audit]]"
---

# `object-name-declustering` audit: `S29 end-to-end churn detector review`

## Scope

Started with Step S29. The review focused on detector intent, anti-vacuity, the authored/current inventory distinction, and whether the test reaches the production replay preflight. No implementation or test code was modified.

## Findings

No findings at any severity.

The detector begins with the fixture's authored manifest and its authored component. It
then writes the real Python declaration `helper_runtime` before scanning and deriving the
rehearsal component. The assertion that the rehearsal inventory digest differs from the
manifest's authored digest proves that this is inventory churn rather than unrelated byte
churn. Rehearsal is driven with that rescanned inventory and emits a receipt whose
`inventory_digest` is asserted equal to the rehearsal scan.

After the receipt is cut, the test adds the second real declaration `second_helper` to the
same unrelated module, rescans, and asserts that the replay inventory digest differs from
the receipt digest. It rebuilds the component from that current inventory and calls the
actual `replay_object_name_component` boundary with the fresh inventory, component, and
older receipt. The replay assertion proves the unrelated module retains its exact current
bytes while the reviewed declaration is transformed, so the success cannot be explained by
an absent write or a test-only preflight.

The forbidden global receipt/current-inventory equality was temporarily reintroduced in
production as a negative control. The focused detector failed with
`receipt inventory differs from the fresh replay scan`; production was restored byte-clean,
after which the focused detector passed. The full replay suite passed 66 tests, and the
reported static checks and whitespace validation were green.

## Recommendations

No remediation recommendation is required. Preserve the two real-declaration digest
assertions and the negative-control proof when future replay changes touch inventory
freshness.
