---
tags:
  - '#audit'
  - '#ci-lane-deconflation'
date: '2026-08-30'
modified: '2026-08-30'
body_schema: 'body-v2'
body_hash: 'sha256:ee1f035d0953b96fbb6c6e8c9f0ea0e5ed71020f39258c8e6466194d48ad842d'
related:
  - "[[2026-08-05-ci-lane-deconflation-plan]]"
  - "[[2026-08-05-ci-lane-deconflation-P02-S64]]"
---
# `ci-lane-deconflation` audit: `P02.S64 code review`

## Scope

Reviewed commit `7104ffb209c6a90c3730a524144e2ac806798268` and the predecessor exceptions cited by its P02.S64 execution record: mapping literals in `fd4b91e2f3f5ada31ebcd1a5a100d8e280a3972c` and generated-publication reconciliation/recovery in `1b937634c3869104679e2a6f18263819833ad794`. The review checked the P02.S64 row, the M184 generated provenance and official extracted design anchors, generated artifacts, stale casilla export-reference removal, transaction recovery bounds, and the P02.S69 runtime-discriminator boundary.

The literal values and generated provenance agree with the M184 authority at the affected anchors; displaced casilla references are removed; generated-tree verification passes; and the cited recovery path confines journal and rollback state to the target root, rejects links and non-regular trees, and covers recovery/refusal states. No finding was identified in those areas.

## Findings

### labelled-literal-alternative-escape | high | A decorated alternative constant is silently accepted as the first literal

`dev/registry/pipeline/_export_tree.py:296` in the reviewed commit accepts any non-empty text after a labelled literal, while the preceding alternative guard at `dev/registry/pipeline/_export_tree.py:291` only recognizes an alternative when its second quoted value ends the cell. Consequently `Constante "E". o "S". rentas.` is not rejected as ambiguous and the branch at `dev/registry/pipeline/_export_tree.py:829` emits `E`. The review reproduced those matches against the current module before the report-time remedy. This is a filing-byte parser: a later decorated alternative can therefore publish a well-formed but wrong discriminator. The new test only proves the terminal form `Constante "E". o "S".` reaches the alternative regex, so it does not make the safety boundary bite. The actual M184 2025 content is safe and is `Constante "E". rentas. DeclaraciÃ³n anual.`, but the mechanism is broader than that authority-backed case. Corrective commit `82524a31a7c6655341265e3a3e119320feff5f06` makes same-line decorated alternatives refuse, but does not close the multiline form recorded below.

### multiline-labelled-alternative-escape | high | An alternative after a newline still bypasses the corrective guard

Corrective commit `82524a31a7c6655341265e3a3e119320feff5f06` changes the alternative pattern at `dev/registry/pipeline/_export_tree.py:291` but does not compile it with `re.DOTALL`; the labelled pattern at `dev/registry/pipeline/_export_tree.py:296` does. Therefore `Constante "E". rentas.\no "S".` fails the alternative matcher but matches the labelled matcher and the renderer again emits `E`. The review executed those two matchers against the committed current module. The correction's renderer-level regression case covers only a same-line trailing alternative, so its pass does not prove the claimed any-trailing-alternative boundary.

## Recommendations

- Retain the same-line correction and make its alternative detector cover newline-separated content, or normalize the content before both literal matchers. Add a renderer-level refusal case for `Constante "E". rentas.\no "S".` while retaining the actual M184 acceptance proof. The fix must preserve P02.S69's boundary: do not repurpose a runtime `RecordDiscriminator` or introduce a filing-content inference to resolve this generated-authority parsing case.
