---
title: AEAT locale catalogue authoring brief
date: 2026-05-18
audience: external translation / copywriting team
contact: hello@gergely-wootsch.com
---

# AEAT locale catalogue authoring brief

## What this is

The `aeat` CLI ships with a four-language operator-facing catalogue
(`es`, `en`, `ca`, `hu`). The translation framework is in place; the
codebase produces canonical i18n keys; the runtime resolves them
through a layered fallback chain. **What is missing is the actual
Spanish-first copy for ~219 keys per locale.** The placeholder
convention is intentional: every untranslated key currently carries a
value that mirrors its own dotted path (e.g.
`add_help: cli.app.ledger.collectible_invoice.add_help`). The runtime
detects this convention and gracefully degrades to either the inline
English `default=` string (the CLI verb's typer kwarg) or a humanised
form of the last key segment, so operators never see literal key paths
in production. **The task is to replace each placeholder with the real
operator-facing copy in the right register and language.**

## Headline numbers

- **777 total placeholder slots** across the four locales
- **219 keys × 4 languages = 876 strings** in scope (rounding includes
  a handful of keys present in one locale but not another — the CLI
  audit will reconcile these on each commit)
- ~349 keys are already real translations — the catalogue is
  ~62% complete

## Tooling — the only surface translators touch

The repository ships a small CLI at `python -m aeat.locales` with two
commands:

```
python -m aeat.locales audit       # report drift between codebase keys and locale yml
python -m aeat.locales scaffold    # regenerate yml files from codebase keys
```

**Workflow per translation slice:**

1. `python -m aeat.locales audit` → must report all four locales `ok`
   before starting (clean baseline).
2. Pick a slice (see "Suggested chunking" below). Open the four
   locale files in parallel:
   ```
   src/aeat/locales/es.yml    ← Spanish (Spain) — Spanish-first authoring
   src/aeat/locales/en.yml    ← English (UK preferred, US accepted)
   src/aeat/locales/ca.yml    ← Catalan (Catalonia)
   src/aeat/locales/hu.yml    ← Hungarian
   ```
3. Locate each placeholder. Placeholders look like:
   ```yaml
       add_help: cli.app.ledger.collectible_invoice.add_help
   ```
   The value mirrors the dotted path. Replace the value with the
   actual operator-facing string:
   ```yaml
       add_help: Registra una nueva factura cobrable
   ```
4. After each slice (don't wait until the end), run:
   ```
   python -m aeat.locales audit
   ```
   All four files must remain `ok`.
5. **Never run `scaffold` after authoring.** Scaffold regenerates
   placeholders for any new codebase keys; it does not destroy
   authored strings, but rerunning it is unnecessary unless the
   codebase has added new keys.
6. Commit each slice with a single Git commit. Example:
   ```
   git add src/aeat/locales/*.yml
   git commit -m "locales: authoring slice — ledger.collectible_invoice (4 langs)"
   ```

## What "Spanish-first" means

The product targets self-employed Spanish taxpayers (autónomos)
interacting with AEAT (the Spanish tax agency). Spanish is the
canonical reference voice. **Author Spanish first; mirror the meaning
into the other three languages.** Do not translate from English back
into Spanish — the English column is downstream of Spanish, not its
source. Catalan should be authored by a Catalan speaker familiar with
Catalan tax terminology, not auto-translated from Spanish.

### Voice / register

- Operator is a working professional, not a layperson. **Imperative
  mood for verb help** ("Registra…", "Elimina…", not "Esto te permite
  registrar…").
- AEAT-canonical terminology — use the exact terms AEAT itself uses
  on its sede and in BOE-published material (e.g. *justificante*,
  *padrón*, *casilla*, *epígrafe IAE*, *autoliquidación*). When in
  doubt, prefer the AEAT term over a generic alternative.
- One sentence per help string. No periods at the end of single-line
  CLI verb descriptions; periods are fine inside multi-sentence
  explanatory strings.
- Keep parameter `--help` strings short (under 80 chars where
  possible). Group help (`group_help`) can be slightly longer (one
  short sentence describing the verb family).
- No emojis. No exclamation marks. No "please" or politeness markers.
- Refer to the operator as second-person singular (Spanish `tú`,
  Catalan `tu`, Hungarian `te` form), not the formal `usted`.

### Domain glossary (non-negotiable terms)

| English-ish | Spanish | Catalan | Hungarian |
|---|---|---|---|
| invoice | factura | factura | számla |
| collectible invoice | factura cobrable | factura cobrable | beszedhető számla |
| payable invoice | factura pagable | factura pagable | fizetendő számla |
| ledger | libro | llibre | főkönyv |
| transaction | transacción | transacció | tranzakció |
| draft (filing) | borrador | esborrany | piszkozat |
| filing / submission | presentación | presentació | benyújtás |
| modelo (the form itself) | modelo | model | "modelo" (do not translate) |
| casilla | casilla | casella | "casilla" (do not translate) |
| ejercicio (tax year) | ejercicio | exercici | adóév |
| autónomo | autónomo | autònom | egyéni vállalkozó |
| census | censo | cens | nyilvántartás |
| epígrafe IAE | epígrafe IAE | epígraf IAE | IAE-szakasz |
| justificante | justificante | justificant | "justificante" (do not translate) |

When a term is "do not translate", keep the Spanish word verbatim in
all four locales — these are AEAT-defined product surfaces and
translating them confuses operators.

## Suggested chunking

The 219 missing keys fall into a small number of coherent CLI
verb-groups. Author one slice at a time, commit, move on. The
chunking is the same across all four locales.

| slice | key prefix | rough count | priority |
|---|---|---|---|
| ledger collectible-invoice verbs | `cli.app.ledger.collectible_invoice.*` | 8 | high |
| ledger payable-invoice verbs | `cli.app.ledger.payable_invoice.*` | ~8 | high |
| ledger purchase-invoice verbs | `cli.app.ledger.purchase_invoice_evidence.*` | ~8 | high |
| aggregation per-modelo errors | `aggregation.per_modelo.*` | ~15 | medium |
| ledger ratios verbs | `cli.app.ledger.ratios.*` | ~10 | high |
| review verbs | `cli.app.review.*` | ~20 | high |
| registry verbs | `cli.app.registry.*` | ~15 | medium |
| modelo verbs | `cli.app.modelo.*` | ~25 | high |
| config verbs (various sub-trees) | `cli.config.*` | ~40 | medium |
| overview verbs | `cli.app.overview.*` | ~15 | high |
| live verbs | `cli.app.live.*` | ~15 | medium |
| remainder | scattered | ~40 | low |

Run this command to get the live list of placeholders by prefix for a
given locale:

```bash
python -c "
import yaml, pathlib
data = yaml.safe_load(pathlib.Path('src/aeat/locales/es.yml').read_text(encoding='utf-8'))
def walk(node, path=''):
    if isinstance(node, dict):
        for k, v in node.items():
            yield from walk(v, f'{path}.{k}' if path else k)
    elif isinstance(node, str):
        yield (path, node)
for k, v in walk(data):
    if v == k:
        print(k)
" | sort | uniq -c | head -40
```

## Acceptance gates

A slice is complete when **all four** of the following hold:

1. `python -m aeat.locales audit` reports every locale `ok`.
2. **No string in the slice still mirrors its dotted path.** Grep
   for the slice's prefix in each locale; every leaf value must be
   real human text.
3. The CLI surface tests still pass for the verbs the slice covers
   (find them under `src/aeat/entrypoints/cli/test_*.py`):
   ```bash
   uv run --no-sync pytest src/aeat/entrypoints/cli/ -q
   ```
4. Manual sanity render: invoke the verb with `--help` and read the
   output:
   ```bash
   AEAT_OUTPUT_LANGUAGE=es uv run aeat app ledger collectible-invoice --help
   AEAT_OUTPUT_LANGUAGE=en uv run aeat app ledger collectible-invoice --help
   AEAT_OUTPUT_LANGUAGE=ca uv run aeat app ledger collectible-invoice --help
   AEAT_OUTPUT_LANGUAGE=hu uv run aeat app ledger collectible-invoice --help
   ```
   The rendered help must be operator-readable in each language with
   no leaked dotted paths or jargon.

## What to never do

- Never hand-edit the **structure** of the yml files (key names, key
  nesting, key paths). Only the **values** are editable. Adding,
  removing, or moving a key is a code change, not a translation
  change, and must come through `python -m aeat.locales scaffold`
  after a corresponding python source edit.
- Never run `git stash`, `git reset --hard`, `git checkout`, `git
  clean`, or any destructive Git command. The repository is a shared
  worktree; destructive operations destroy other agents' work.
- Never commit the four locale files separately. Always commit them
  in one atomic Git commit per slice so the audit stays consistent.
- Never leave a slice half-done. If you cannot complete a slice in one
  session, commit the partial work AND open a note documenting the
  next-up keys so the next session picks up cleanly.
- Never use machine translation for Catalan or Hungarian without a
  human pass. Spanish-to-Catalan via MT regularly produces wrong tax
  vocabulary; Hungarian MT is unreliable for technical content.

## Reference material the team should consult

- AEAT sede (`https://sede.agenciatributaria.gob.es/`) — for canonical
  Spanish tax terminology
- BOE (`https://www.boe.es/`) — for legal-text vocabulary in Spanish
  and Catalan
- The AEAT Manual Práctico de IRPF / IVA (annual editions) — the
  vocabulary used in these PDFs is the canonical Spanish operator
  voice
- Existing real translations in `src/aeat/locales/*.yml` — these are
  ~349 already-authored keys. Match their tone exactly.

## Sample slice (do this first as a calibration)

The `cli.app.ledger.collectible_invoice.*` group is 8 keys and
represents the canonical pattern for verb-groups. Author it, commit
it, then pause for review before continuing. The Spanish copy below
is a starting point — the translator should refine to match register:

```yaml
# src/aeat/locales/es.yml — fragment under cli.app.ledger.collectible_invoice
group_help: Facturas que un cliente te debe pagar
add_help: Registra una nueva factura cobrable
view_help: Muestra los datos de una factura cobrable
list_help: Lista las facturas cobrables registradas
update_help: Actualiza los datos de una factura cobrable
remove_help: Elimina una factura cobrable registrada
invoice_id_help: Identificador de la factura (o prefijo no ambiguo)
invoice_date_help: Fecha de emisión de la factura (AAAA-MM-DD)
```

After committing the first slice with all four locales, send the
diff back for review before continuing to the second slice. Once the
pattern is approved, the remaining slices follow the same shape.

## Outstanding questions worth flagging back

- Catalan / Hungarian register: do we want `tú`-equivalent informality
  in all four locales, or formal `vosté` / `Ön` in CA / HU? Default
  assumption is informal across the board.
- Whether to keep AEAT-specific Spanish terms verbatim in HU vs.
  attempt a Hungarian gloss (current default: keep verbatim, since
  Hungarian operators interacting with AEAT will recognise the
  Spanish term anyway).
- Whether the team should also touch the ~349 already-translated
  keys for consistency (current default: do not; only fill
  placeholders).
