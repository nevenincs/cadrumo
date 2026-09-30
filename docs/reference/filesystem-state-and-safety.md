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
uses them runs. The state-free surfaces (`--help`, `--version`, and a bare
invocation) do not create anything, so browsing the command tree leaves no
state behind.

Profile state is bucket-scoped under
`<root>/buckets/<bucket-id>/`. The bucket contains `db/cadrumo.db`, encrypted
blobs under `data/`, the `custody/` envelopes that hold the wrapped data key
for the passphrase and the recovery code, `manifest.toml`,
`profile.commit.v1.json`, `.lock`, and an `output-language.hint` file.
Session and login-throttle state live under `<root>/keystore/<bucket-id>/`. Tokens, logs,
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
| Export | Writes an AEAT-compatible local file after verification and required evidence gates pass; refuses to overwrite an existing file without `--replace`; portal acceptance is not guaranteed, and files for modelos whose record design reserves a software identity, such as Modelo 303 and 390, carry a development identity that AEAT does not accept |
| Live AEAT access | Separately invoked, authenticated, and read-only |
| Submission | Forbidden; no Cadrumo submission command exists |
| Official filing | Performed by a human through an official AEAT channel; for modelos whose file AEAT does not accept, the human keys the calculated values into the portal form |
| Filing history | Recorded locally after the human filing; reconciliation compares header fields, the result total where the modelo declares its result box, and, for enrolled modelos, casilla values from a filed declaration |
| Responsibility | The taxpayer or authorized filer reviews figures, meets deadlines, uploads, and retains the justificante |

See [Protect access to your data](../how-to/protect-data-access.md) for recovery,
locking, export, and reset tasks. The [filing-boundary
explanation](../explanation/recording-a-filing-and-the-boundary.md) explains why
submission stays outside Cadrumo.
