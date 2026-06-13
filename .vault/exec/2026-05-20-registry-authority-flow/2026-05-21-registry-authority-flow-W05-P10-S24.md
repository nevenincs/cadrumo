---
tags: ["#exec", "#registry-authority-flow"]
date: '2026-05-21'
modified: '2026-05-21'
step_id: 'S24'
related:
  - '[[2026-05-20-registry-authority-flow-plan]]'
---

# `registry-authority-flow` `W05.P10.S24`

Lowered the registry TOML fragment line threshold to 1,750.

- Modified: `src/aeat/domain/calculations/registry/test_loader_directory_mode.py`
- Modified: `src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml`
- Modified: this execution record

## Description

Lowered `_MAX_TOML_FRAGMENT_LINES` from 2,000 to 1,750 in the committed
registry reviewability gate. The stricter threshold exposed the Modelo 100
2025 completeness manifest as the only remaining over-threshold TOML file.
That manifest's repetitive `casillas` table-array entries were mechanically
compacted into an inline array under the existing
`[revisions."2025".completeness_manifest]` table, preserving the parsed TOML
shape while reducing the file to 697 lines and keeping 613 manifest casillas.

## Tests

`uv run python -c "import tomllib; from pathlib import Path; p=Path('src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml'); data=tomllib.loads(p.read_text(encoding='utf-8')); print(len(p.read_text(encoding='utf-8').splitlines()), len(data['revisions']['2025']['completeness_manifest']['casillas']))"` printed `697 613`.

`uv run pytest -q src/aeat/domain/calculations/registry/test_loader_directory_mode.py::test_committed_registry_toml_files_stay_reviewable` passed with 1 test.

`uv run pytest -q src/aeat/domain/calculations/registry/test_loader_directory_mode.py src/aeat/domain/calculations/registry/test_modelo_100_registry.py src/aeat/domain/calculations/registry/test_modelo_200_registry.py` passed with 63 tests in 77.11s.

`git diff --check -- src/aeat/_data/registry/aeat/modelos/100/revisions/2025/completeness-manifest.toml src/aeat/domain/calculations/registry/test_loader_directory_mode.py` passed.
