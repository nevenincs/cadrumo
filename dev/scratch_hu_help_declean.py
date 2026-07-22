"""De-scaffold key-echo/mirror [help] entries from the 44 flagged Hungarian
modelo sidecars. Uses the canonical ModeloLocaleManager writer so output
formatting matches the manager's own render exactly. [labels] tables are
loaded and passed through unchanged.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path("src").resolve()))

from cadrumo.locales._modelo_manager import ModeloLocaleManager, _render_translation_toml  # noqa: E402
from cadrumo.core.atomic_write import atomic_write_text  # noqa: E402
from cadrumo.core.external_constants import UTF_8_ENCODING  # noqa: E402
import tomllib  # noqa: E402

FILES = [
    "src/cadrumo/_data/registry/aeat/modelos/036/revisions/2025-02-03-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/038/revisions/2002-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/121/revisions/2017-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/122/revisions/2017-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/123/revisions/2019-2023/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/140/revisions/2020-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/143/revisions/2014-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/151/revisions/2025-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/156/revisions/2003-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/165/revisions/2013-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/179/revisions/2021-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/181/revisions/2009-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/185/revisions/2025-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/186/revisions/2003-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/187/revisions/2019-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/188/revisions/2019-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/189/revisions/2025/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/194/revisions/2019-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/216/revisions/2024-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/220/revisions/2024-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/222/revisions/2025-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/231/revisions/2021-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/232/revisions/2016-2017/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/233/revisions/2018-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/234/revisions/2021-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/238/revisions/2024-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/270/revisions/2013-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/296/revisions/2024-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/308/revisions/2009-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/309/revisions/2004-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/322/revisions/2008-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/341/revisions/2000-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/347/revisions/2008-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/360/revisions/2010-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-exterior/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/369/revisions/esquema-importacion/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/380/revisions/2005-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/490/revisions/2021-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/576/revisions/2007-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/592/revisions/2022-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/604/revisions/2021-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/763/revisions/2011-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/840/revisions/2003-y-siguientes/locales/hu.toml",
    "src/cadrumo/_data/registry/aeat/modelos/848/revisions/2003-y-siguientes/locales/hu.toml",
]

DRY_RUN = "--apply" not in sys.argv

total_removed = 0
total_files_changed = 0
results = []

for rel in FILES:
    path = Path(rel)
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    labels = dict(data.get("labels", {}))
    help_text = dict(data.get("help", {}))
    before = dict(help_text)
    filtered = {
        k: v
        for k, v in help_text.items()
        if not (v == k or v == labels.get(k))
    }
    removed = len(before) - len(filtered)
    if removed == 0:
        results.append((rel, 0, "no-op (nothing echoed)"))
        continue
    total_removed += removed
    total_files_changed += 1
    if not DRY_RUN:
        ModeloLocaleManager._write_translation_path(path, labels=labels, help_text=filtered)
        # verify labels untouched and help now clean
        reread = tomllib.loads(path.read_text(encoding="utf-8"))
        assert reread.get("labels", {}) == labels, f"labels drifted for {path}"
        assert all(v != k and v != labels.get(k) for k, v in reread.get("help", {}).items()), (
            f"echo survived in {path}"
        )
    results.append((rel, removed, "cleaned" if not DRY_RUN else "would clean"))

print(f"{'DRY RUN' if DRY_RUN else 'APPLIED'}: {total_files_changed} files, {total_removed} help entries removed\n")
for rel, removed, status in results:
    if removed:
        print(f"  {status:12} {removed:3} removed  {rel}")
