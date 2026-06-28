---
tags:
  - '#exec'
  - '#fichero-boe-export-layouts'
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S22'
related:
  - '[[2026-05-21-fichero-boe-export-layouts-plan]]'
---

# `fichero-boe-export-layouts` `P04.S22`

Loaded the full registry snapshot confirming all 26 modelos remain
valid with the new and amended export layouts present.

## Verification

```python
from aeat.application.filing.runtime import build_runtime_schema_provider
provider = build_runtime_schema_provider()
# provider.collections has 26 entries — all modelos load without error
```

Output:
```
Total collections: 26
Keys: ['036', '115', '130', '184', '190', '193', '303', '308', '309', '322', ...]
```

The `build_runtime_schema_provider()` call exercises the full
validation pipeline: legal catalogue checks, export layout
referential integrity, casilla export_refs cross-referencing. All 26
modelos load without ValidationError.

Additional: 95 registry long-tail data-type tests pass.

```
95 passed in 0.21s
```
