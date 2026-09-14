"""A synthetic authored modelo for the binding-rewrite tools' fixtures.

The two authored-binding rewrite tools -- the provider-shape converter and the
row-set value-contract normaliser -- read and write a ``modelos/`` tree
directly, so their tests need a tree on disk. Seeding that tree from the shipped
corpus made the fixture's meaning depend on what the corpus happened to author
that day: which revision carried both families, which binding a casilla
consumed, which member a later edition rewrote. A fixture whose shapes move
under it cannot be a gate, so the tree is built here instead, carrying exactly
the shapes the two tools are asked about.

The tree is one modelo, one edition, one bindings fragment and one casillas
fragment, in the TOML grammar the loader accepts. Each test states the binding
rows it is about by rewriting the bindings fragment; what this module
guarantees is the surroundings -- the directory shape both tools walk, and one
typed consumer, a casilla declaring ``money`` and naming
:data:`CONSUMED_BINDING`, which is the evidence the converter reads a row's
data type from.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

__all__ = [
    "BASE_TAIL",
    "CONSUMED_BINDING",
    "LEGAL_REF",
    "MODELO",
    "REVISION",
    "SOURCE_REF",
    "write_seed_tree",
]

MODELO: Final = "151"
"""The synthetic modelo's number. Nothing is read from the shipped modelo 151."""

REVISION: Final = "2025"
"""The single edition the seeded modelo declares."""

CONSUMED_BINDING: Final = "modelo-151-impatriado-base-liquidable-general"
"""The binding id the seeded revision's casilla names, declared ``money``."""

LEGAL_REF: Final = "ley-35-2006:art-93"
SOURCE_REF: Final = "aeat-modelo-151-procedure"

BASE_TAIL: Final = f'legal_refs = ["{LEGAL_REF}"]\nsource_refs = ["{SOURCE_REF}"]\n'
"""The reference tail every authored member of the seeded edition carries."""

_MANIFEST: Final = f"""[modelo]
id = "{MODELO}"
tax_domain = "renta"
cadence = "annual"
jurisdiction = "ES-AEAT"
legal_refs = ["{LEGAL_REF}"]
source_refs = ["{SOURCE_REF}"]
"""

_REVISION_MANIFEST: Final = f"""[revisions."{REVISION}"]
valid_from = 2025-01-01
valid_to = 2025-12-31
period_selector = {{ years = [2025], periods = ["0A"] }}
legal_refs = ["{LEGAL_REF}"]
source_refs = ["{SOURCE_REF}"]
"""

_CASILLAS: Final = f"""[[revisions."{REVISION}".casillas]]
id = "impatriado.base-liquidable-general"
number = "13"
section = ["liquidacion"]
data_type = "money"
continuidad_id = "impatriado-base-liquidable-general"
input_kind = "bound"
binding = "{CONSUMED_BINDING}"
{BASE_TAIL}"""

_BINDINGS: Final = f"""[[revisions."{REVISION}".bindings]]
id = "{CONSUMED_BINDING}"
provider = {{ kind = "ledger_impatriado_income_aggregation", modelo = "{MODELO}", \
target_casilla_id = "impatriado.base-liquidable-general", fact = "ingresos_integros_sum" }}
value = {{ data_type = "money", channel = "decimal" }}
aggregation = {{ op = "sum" }}
{BASE_TAIL}"""


def write_seed_tree(tmp_path: Path) -> Path:
    """Build the synthetic modelos tree below ``tmp_path`` and return its root."""
    modelos_root = tmp_path / "modelos"
    modelo_dir = modelos_root / MODELO
    revision_dir = modelo_dir / "revisions" / REVISION
    (revision_dir / "bindings").mkdir(parents=True)
    (revision_dir / "casillas").mkdir(parents=True)
    (modelo_dir / "manifest.toml").write_text(_MANIFEST, encoding="utf-8", newline="\n")
    (revision_dir / "revision.toml").write_text(_REVISION_MANIFEST, encoding="utf-8", newline="\n")
    (revision_dir / "casillas" / "0001-casillas.toml").write_text(_CASILLAS, encoding="utf-8", newline="\n")
    (revision_dir / "bindings" / "0001-bindings.toml").write_text(_BINDINGS, encoding="utf-8", newline="\n")
    return modelos_root
