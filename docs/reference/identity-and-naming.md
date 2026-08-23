# Identity and naming

The Agencia Estatal de Administración Tributaria (AEAT) is the external tax
authority. CLI means command-line interface.

## Canonical product identity

| Surface | Canonical value |
| --- | --- |
| Display name | `Cadrumo` |
| Python package | `cadrumo` |
| Root distribution | `cadrumo` |
| Human CLI executable | `aeat` |
| Repository | `nevenincs/cadrumo` |
| Product environment prefix | `CADRUMO_` |
| Companion distributions | `cadrumo-data-manuals`, `cadrumo-data-official` |
| Companion Python namespace | `cadrumo_data` |

These values identify one product. There is no alternate human CLI spelling or
Python import alias.

## Product and authority names

| Referent | Use | Examples |
| --- | --- | --- |
| Cadrumo product | `Cadrumo` or the canonical identifier in the identity table | Cadrumo CLI, Cadrumo profile, `cadrumo` package, `CADRUMO_LOCAL_STORAGE_ROOT` |
| Spanish tax authority | `AEAT` | AEAT portal, AEAT credentials, AEAT official file, AEAT legal source, AEAT taxonomy |

AEAT is an external authority and counterparty, not the application name. Authority-owned
terms such as *modelo*, *casilla*, *justificante*, and official period or
classification tokens keep their AEAT meaning inside Cadrumo.
