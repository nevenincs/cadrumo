# How to reconcile a filed Modelo against its justificante

After you file with the Agencia Estatal de Administración Tributaria (AEAT), download the justificante. Reconcile it against your local filing record to confirm that the receipt belongs to the expected modelo and filing year. This check is local: it reads the Portable Document Format (PDF) file you supply and never contacts AEAT.

You need an active profile, a local filing record (work unit), and the justificante PDF on disk. To set up a profile, see [Set up your taxpayer profile](profile-setup.md). To create a local filing record, see the [quickstart](quickstart.md).

## Reconstruction and Matching Algorithms

Reconciliation performs a local, field-by-field verification of your local work unit's most recent calculation revision against the values extracted from the PDF evidence.

Currently, the following fields are compared:
- **Modelo:** Verifies that the work unit's modelo (e.g. `303`, `130`) matches the modelo extracted from the justificante.
- **Ejercicio (Filing Year):** Verifies that the work unit's filing year matches the exercise year extracted from the justificante.
- **Taxpayer Identifier:** Confirms alignment of the taxpayer ID (generalized as NIF, CIF, DNI, NIE, or NII) between the active profile and the PDF.

A successful reconciliation produces a matching verdict. Any disagreement in these values generates a mismatch report indicating which fields do not align.

## Reconciliation Verbs and Commands

There are two primary commands for running a reconciliation depending on your preferred workflow.

### 1. General reconciliation command

Use `aeat app modelo reconcile` to compare a local work unit against external evidence. You must target the work unit using either its ID or specific targeting options, and specify the source of evidence.

```bash
aeat app modelo reconcile --modelo 303 --year 2026 --period 1T --from-justificante ./justificante.pdf
```

Alternatively, you can pass the work unit ID (SHA-256 or unambiguous prefix) as a positional argument:

```bash
aeat app modelo reconcile <work-unit-id> --from-justificante ./justificante.pdf
```

#### Command Options:
- `--from-justificante PATH`: Path to the AEAT justificante PDF.
- `--from-declaration PATH`: Path to the filed declaration PDF to reconcile against. 
  > [!NOTE]
  > The `--from-declaration` option is a planned extension and is currently unsupported. Invoking it will raise a clean refusal error.
- `--modelo TEXT`: Target modelo code.
- `--year INTEGER`: Target filing year.
- `--period TEXT`: Target period.
- `--revision TEXT`: Target calculation revision ID. If multiple candidates exist, specify the revision to prevent targeting conflicts.
- `--bucket-id TEXT`: Target bucket ID.
- `--by TEXT`: Optional name/label of the actor running the check (defaults to `operator`).

### 2. Justificante-centric shortcut command

Use `aeat app modelo reconcile-from-justificante` if you prefer to specify the justificante PDF as the primary positional argument:

```bash
aeat app modelo reconcile-from-justificante ./justificante.pdf --modelo 303 --year 2026 --period 1T
```

Or using the work unit ID:

```bash
aeat app modelo reconcile-from-justificante ./justificante.pdf <work-unit-id>
```

Options for targeting the work unit (`--modelo`, `--year`, `--period`, `--revision`, and `--bucket-id`) work identically to the main `reconcile` command.

## Read the verdict and audit trail

The command outputs a structured report containing:
- **Verdict:** One of `matches` (clean match), `mismatches` (field differences found), or `evidence_invalid` (the PDF could not be parsed).
- **Diffs:** A detailed list of mismatched fields, showing the work unit value alongside the value extracted from the evidence.

Every reconciliation run appends a `MODELO_RECONCILED` event to the active profile's local `BucketEventHistoryRepository` audit log. This records who performed the check, the target work unit, the source path, and the comparison verdict.

## Next steps

- [Quickstart](quickstart.md) - build and export a modelo.
- [Common filing recipes](index.md) - other modelos and tasks.
- [Command reference](../cli/index.rst) - every reconcile flag and exit code.
- [Diagnose and repair your local setup](troubleshooting.md) - fix local setup or readiness problems.
