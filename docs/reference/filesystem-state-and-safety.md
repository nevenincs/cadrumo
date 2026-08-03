# Filesystem, state, and safety

The Agencia Estatal de Administración Tributaria (AEAT) is the external tax
authority referenced by the filing and live-read boundaries on this page.

## Local state layout

`CADRUMO_LOCAL_STORAGE_ROOT` selects the root of Cadrumo-owned local state. The
default depends on how Cadrumo runs:

| Platform | Default storage root |
| --- | --- |
| Windows | `%LOCALAPPDATA%/cadrumo/storage` |
| Linux | `$XDG_DATA_HOME/cadrumo/storage`, or `~/.local/share/cadrumo/storage` |
| macOS | `~/Library/Application Support/cadrumo/storage` |

The root is the same whether Cadrumo runs from a source checkout or an
installed distribution. Running from a checkout does not move it: set
`CADRUMO_LOCAL_STORAGE_ROOT` to put the tree inside the checkout.

Cadrumo creates the root and the directories below it when a command that
uses them runs. The state-free surfaces — `--help`, `--version`, and a bare
invocation — do not create anything, so browsing the command tree leaves no
state behind.

Profile state is bucket-scoped under
`<root>/buckets/<bucket-id>/`. The bucket contains `db/cadrumo.db`, encrypted
blobs, audit material, `manifest.toml`, `.lock`, and an output-language hint.
Key material is rooted under `<root>/keystore/<bucket-id>/`. Tokens, logs,
secrets, blobs, and audit paths derive from the same product root unless an
explicit Cadrumo setting overrides them.

Google Drive mirroring uses a Cadrumo-owned `cadrumo-vault/` folder. A former
`aeat-vault/` folder is not adopted.

## Old `aeat`-named storage is refused, not migrated

Cadrumo refuses recognizable former product state. This includes a sibling
`aeat` application-state directory, an `aeat.db` database, `aeat.*`,
`aeat-test.*`, or `aeat-tests.*` secure-object namespaces, and former bundle or
Drive-folder names.

The refusal is non-destructive. Cadrumo does not read, connect to, copy, move,
re-key, delete, migrate, or adopt that state. Detection leaves the former bytes
untouched and requires the operator to choose a separate, explicit disposition.

## Safety and filing scope

| Surface | Cadrumo behavior |
| --- | --- |
| Calculation and verification | Local; evaluates saved records against bundled registry rules and evidence |
| Export | Writes an AEAT-compatible local file after verification and required evidence gates pass; portal acceptance is not guaranteed |
| Live AEAT access | Separately invoked, authenticated, and read-only |
| Submission | Forbidden; no Cadrumo submission command exists |
| Official filing | Performed by a human through an official AEAT channel |
| Filing history | Recorded locally after the human filing; reconciliation compares totals and, for enrolled modelos, captured per-casilla values |
| Responsibility | The taxpayer or authorized filer reviews figures, meets deadlines, uploads, and retains the justificante |

See [Protect access to your data](../how-to/protect-data-access.md) for recovery,
locking, export, and reset tasks. The [filing-boundary
explanation](../explanation/recording-a-filing-and-the-boundary.md) explains why
submission stays outside Cadrumo.
