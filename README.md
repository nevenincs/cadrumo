<p align="center">
  <img src="docs/_static/readme/cadrumo-logo.svg" alt="Cadrumo logo" width="136">
</p>

# Cadrumo: turn Spanish tax records into locally verified filing artifacts

[![Apache 2.0 license](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)
![Project status: beta](https://img.shields.io/badge/status-beta-yellow)

Cadrumo turns local financial records into calculated, checked, and exportable artifacts for supported Spanish tax forms. It keeps the calculation path deterministic and preserves each result's sources.

Use Cadrumo to prepare a filing workspace, review the figures, and export a local file. You remain responsible for deciding what to file.

> [!IMPORTANT]
> Cadrumo never submits a filing. Review every result, then file through official Agencia Estatal de Administración Tributaria (AEAT) channels.
>
> Cadrumo is independent from AEAT and isn't affiliated with or endorsed by the authority. It doesn't provide tax, legal, accounting, or financial advice.

Public publishing remains blocked while package, repository, marketplace, domain, executable, and trademark gates are unresolved. Install Cadrumo only from an authorized source checkout.

## Understand the names

- **Cadrumo** is the product. Its package, distribution, repository, and plugin use the machine identifier `cadrumo`. Its permanent command-line interface (CLI) command is `aeat`.
- **AEAT** is Spain's tax authority. The name remains in official portals, credentials, evidence, citations, and legal terminology.
- A **profile** isolates one taxpayer's local settings, records, and filing workspaces.
- A **modelo** is a Spanish tax form. A **casilla** is one registered field in that form.
- A **verified calculation revision** is a saved calculation for which Cadrumo recorded a complete verification report. It isn't proof of filing or AEAT acceptance.

## Run Cadrumo from source

Cadrumo requires Python 3.13 or later and uses [`uv`](https://docs.astral.sh/uv/) for its local environment.

From an authorized source checkout, run:

```console
python --version
uv sync
uv run aeat --version
uv run aeat --help
```

The `aeat --version` command verifies that `aeat` launches the Cadrumo CLI and reports `CADRUMO` followed by the installed version. The `aeat --help` command displays the Cadrumo command tree and options.

If you choose encrypted file storage, or Cadrumo falls back to it, the first command that opens local storage asks for a master-key passphrase. That passphrase unlocks the locally encrypted records. Operating-system-backed secret stores use their own unlock flow.

Don't install from the Python Package Index or a public plugin marketplace yet. A successful local build doesn't clear Cadrumo's publication gates.

## Complete one local filing path

The following example uses fictional data to prepare Modelo 130 for the first quarter of 2026. It writes a local fichero-BOE, an AEAT-compatible, fixed-width filing file with the `.boe` extension. BOE stands for Boletín Oficial del Estado.

Long PowerShell commands use backticks for line continuation. Copy each complete block, including every backtick.

### 1. Create a profile

```powershell
uv run aeat config profile create demo `
  --quiet --accept-defaults `
  --entity-type natural_person `
  --tax-id 12345678Z --name Ana --surnames "García López" `
  --activity consultoria --activity-start-date 2026-01-01 `
  --irpf-income-categories actividad_economica `
  --tax-residence-ccaa madrid
```

The profile becomes active. It is the storage authority for records you create or change and for the filing workspace. Read-only commands inspect that profile without creating records. Export writes the cleartext `.boe` file to the path you choose with `--output`.

### 2. Add two classified records

```powershell
uv run aeat app ledger add `
  --date 2026-02-10 --amount 1210 --direction INCOMING `
  --description venta --classification BUSINESS `
  --taxable-base 1000 --iva-rate 0.21 --iva-amount 210

uv run aeat app ledger add `
  --date 2026-02-11 --amount 500 --direction OUTGOING `
  --description compra --classification BUSINESS `
  --category-id material_oficina --taxable-base 500

uv run aeat app ledger list
```

`--amount` is the transaction total. The fictional income records its taxable base and value-added tax (IVA) breakdown.

The fictional expense claims no deductible IVA quota. Its amount and Impuesto sobre la Renta de las Personas Físicas (IRPF) expense base are therefore both `500`.

### 3. Create and calculate the filing workspace

The `--binding` options supply calculation inputs that don't come from these two ledger records.

```powershell
uv run aeat app modelo work create --modelo 130 --year 2026 --period 1T

uv run aeat app modelo work calculate `
  --modelo 130 --year 2026 --period 1T `
  --binding modelo-130-resultados-negativos-anteriores=0 `
  --binding modelo-130-pagos-fraccionados-anteriores=0 `
  --binding irpf.previous_year_economic_activity_net_income=0

uv run aeat app modelo work revision --modelo 130 --year 2026 --period 1T
```

The two `modelo-130-*` bindings declare that this fictional first-quarter filing has no negative result or fractional payment carried from an earlier quarter.

`irpf.previous_year_economic_activity_net_income=0` is different. It supplies the prior-year economic-activity income used to determine the low-income reduction; it isn't a quarterly carry.

### 4. Verify the calculation revision and export

```powershell
uv run aeat app modelo work verify --modelo 130 --year 2026 --period 1T

uv run aeat app modelo export `
  --modelo 130 --year 2026 --period 1T `
  --output ./modelo-130-2026-1T.boe
```

Verification is local. It saves a report tied to the calculation revision and grants `Verificado completo` only when `granted_verificado_completo` is true.

Export selects that verified calculation revision and refuses an unverified draft. Before writing the file, it also checks the profile, required bindings, earlier-period state, saved ledger evidence, and evidence for any deductible IVA claimed.

For this input, the deterministic calculation reports:

```text
casilla 03  500.00  net result
casilla 04  100.00  instalment amount
casilla 19    0.00  final result
```

The export command reports the output path, byte size, and 256-bit Secure Hash Algorithm (SHA-256) digest. The `.boe` file is cleartext and remains on your computer. It's a local AEAT-compatible artifact, not official filing evidence.

Official evidence comes from AEAT after filing. A justificante is AEAT's receipt confirming submission. A filed-declaration query shows AEAT's record of the filing.

A cotejo checks a document's authenticity using its Código Seguro de Verificación (CSV). Here, CSV is a security code, not a comma-separated-values file.

This result demonstrates the workflow, not the correct tax treatment for your circumstances. Review the full revision and resolve every blocker before using an export.

## Choose a deeper route

| Goal | Documentation |
| --- | --- |
| Work through the longer tutorial | [Quickstart](docs/how-to/quickstart.md) |
| Find task-specific commands | [How-to guides](docs/how-to/index.md) |
| Configure read-only AEAT access | [Authenticate with AEAT](docs/how-to/authenticate-with-aeat.md) |
| Inspect the command tree | [Command-line interface (CLI) reference](docs/cli/index.rst) |
| Integrate Python code | [Application programming interface (API) entry point](docs/api/cadrumo.rst) |
| Understand records, formulas, and provenance | [From records to figures](docs/explanation/from-records-to-figures.md) |
| Determine which modelos apply and inspect support | [Choose a modelo](docs/how-to/choose-modelo.md) |
| Understand architecture and boundaries | [Architecture](docs/architecture/index.md) |
| Diagnose a local problem | [Troubleshooting](docs/how-to/troubleshooting.md) |

The CLI and Python modules use the same deterministic application and calculation services.

## Protect your data

- Cadrumo encrypts app-managed financial records and evidence at rest in the active profile's local storage.
- Original imported files stay at their source paths. Local exports are cleartext at the paths you choose.
- Authenticated AEAT retrieval runs only when you invoke it. Those operations are read-only and cannot submit a filing.
- Optional cloud classifiers receive the words, figures, and transaction fields you send to their providers.
- Evidence text reaches a cloud classifier only after profile permission and invocation confirmation. Image evidence uses a local Ollama workflow.

Before using real data, read the [filing boundary](docs/explanation/recording-a-filing-and-the-boundary.md), [security policy](SECURITY.md), and [full disclaimer](docs/disclaimer.md).

## Get help or contribute

The repository remains private during the beta. If you have access, use these routes to report defects, handle security concerns, set up a workstation, and review changes:

- [Open an issue](https://github.com/nevenincs/cadrumo/issues) for bugs and documentation problems
- Follow [`SECURITY.md`](SECURITY.md) for vulnerability reporting
- Use the [workstation setup guide](docs/workstation-setup.md) before contributing code
- Review shipped changes in the [changelog](CHANGELOG.md)

Don't publish vulnerability details in an issue. A public support channel and guaranteed confidential contact aren't available yet.

## Status, license, and disclaimer

Cadrumo is beta software. Behavior, schemas, commands, and persisted state may change without compatibility support before 1.0.

Cadrumo is available under the [Apache License 2.0](LICENSE). It's provided as-is, without warranties or guarantees.

You are responsible for reviewing calculations, meeting deadlines, and filing through official AEAT channels. Read the [full disclaimer](docs/disclaimer.md) for the advice, affiliation, responsibility, and liability boundaries.
