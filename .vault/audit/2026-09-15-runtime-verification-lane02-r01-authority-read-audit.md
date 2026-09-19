---
tags:
  - '#audit'
  - '#runtime-verification'
date: '2026-09-15'
modified: '2026-09-15'
body_schema: 'body-v2'
body_hash: 'sha256:837b3e65279936d7dfdcac0f3a3bf513874e391ce4de2f7fda9a2daf8094a475'
related:
  - "[[2026-09-15-runtime-verification-lane01-r01-cli-reachability-audit]]"
---

# `runtime-verification` audit: `lane02-r01 published authority read`

## Scope

Objective: prove that the current runtime reads one typed modelo directory from its published authority and identify the exact generation consumed. Session `lane02-r01-authority-read`, probe `L02-R01-P01`, run once with no repeat.

Checkout: branch `main`, HEAD `c36b855520f7664f57d3d5517097ab6cccefbfb9`. The worktree was dirty (110 porcelain entries from concurrent contributors), so the observation covers the working tree and not a clean commit.

Observation window (UTC): 2026-09-15T14:38:03.935Z to 2026-09-15T14:38:14.812Z.

Command, run once in PowerShell from the worktree root by the evidence agent. No pytest or other check ran:

```powershell
@'
import hashlib
import json

from cadrumo.domain.calculations.registry.authority import (
    bundled_authority_descriptor_path,
    bundled_indexed_authority,
)
from cadrumo.domain.calculations.registry.authority_store import AuthorityDescriptor

path = bundled_authority_descriptor_path()
before = path.read_bytes()
descriptor = AuthorityDescriptor.read(path)

owner = bundled_indexed_authority()
try:
    with owner.operation() as operation:
        pin = operation.pin()
        modelos = operation.modelo_ids()
        if not modelos:
            raise RuntimeError("Published authority exposes no modelo identities")

        selected = sorted(modelos)[0]
        directory = operation.modelo_directory(selected)

        if pin.logical_generation != descriptor.logical_generation:
            raise RuntimeError("Operation generation differs from observed selector")

        if path.read_bytes() != before:
            raise RuntimeError("Selector changed during observation; evidence is inconclusive")

        print(json.dumps({
            "descriptor_path": str(path.resolve()),
            "descriptor_sha256": hashlib.sha256(before).hexdigest(),
            "database": descriptor.database,
            "database_sha256": descriptor.database_sha256,
            "logical_generation": pin.logical_generation,
            "reader_incarnation": pin.reader_incarnation,
            "selected_modelo": selected,
            "decoded_type": type(directory).__name__,
            "selector_stable": True,
        }, sort_keys=True))
finally:
    owner.close()
'@ | uv run --no-sync python -
$probeExit = $LASTEXITCODE
Write-Output "probe_exit=$probeExit"
```

Exit code: 0. No stderr.

Emitted JSON:

```json
{"database": "authority-06f66544cb3f04ed5bbdd2b7ec4d33622b057fab82ee687432786dfc5cbfa2dd.sqlite3", "database_sha256": "06f66544cb3f04ed5bbdd2b7ec4d33622b057fab82ee687432786dfc5cbfa2dd", "decoded_type": "ModeloRevisionDirectory", "descriptor_path": "Y:\\code\\cadrumo-worktrees\\main\\src\\cadrumo\\_data\\registry\\authority\\authority.current.json", "descriptor_sha256": "f7c4e2c26828a9bc6a980713598673cda889cc8e5ccac5db17c2d9e99231d118", "logical_generation": "2bdbfabc832b91e9ec77345b342abc08a7416e6e84f6ceb4aa85f79af8222c66", "reader_incarnation": "17ad67e00860a4f63cd4b58c0de718583349dfc34edfed76f48ddbc0026951d8", "selected_modelo": "036", "selector_stable": true}
```

Final signal: PROVEN.

## Findings

### l02-r01-f01 | low | Runtime reads a typed modelo directory at the selected generation

Observed: the probe exited 0. The published authority returned modelo identities, and modelo `036` decoded as `ModeloRevisionDirectory`. The operation pin's logical generation `2bdbfabc…2c66` equals the one declared by `authority.current.json` (sha256 `f7c4e2c2…d118`), which selects the SQLite artifact `authority-06f66544…a2dd.sqlite3`. The selector bytes were identical before and after the read. This is a confirming finding, not a defect.

This matches the descriptor, generation, and database that the lane01 audit's `L01-R01-F02` identified by read-only SQLite inspection. Here they are confirmed through the runtime reader API instead.

Not observed: the script did not independently hash the SQLite file. `database_sha256` is the descriptor's declared value, and its match with the filename is by naming only. The probe also did not examine whether `modelo_directory` goes through `ModeloDirectoryMetadata.materialize`, the single-revision construction `L01-R01-F02` implicates. This result neither confirms nor clears that defect.

### l02-r01-f02 | low | Reader incarnation and logical generation are distinct, but incarnation lifetime is unproven

Observed: `reader_incarnation` (`17ad67e0…51d8`) and `logical_generation` are different 64-hex values, so they are separate identifiers. Unproven: whether the incarnation changes per process or per reader while the generation stays fixed. One run cannot show this.

## Recommendations

Next evidence question (from l02-r01-f01): does one registry binding resolve against generation `2bdbfabc…2c66` to a target that was stated independently before the run?

This lane does not establish binding correctness, cross-revision or temporal selection, calculation correctness, source freshness against authored registry TOML, the integrity of the SQLite bytes against `database_sha256`, or adoption by a built package (the read came from the editable worktree's `src/cadrumo/_data`). l02-r01-f02 is low value and needs no dedicated probe unless a later lane depends on reader identity.
