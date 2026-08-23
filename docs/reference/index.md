# Cadrumo reference

Use this collection to look up exact Cadrumo names, boundaries, and generated
technical surfaces while you work. For installation and first use, start with
the [installation guide](../workstation-setup.md) and
[quickstart](../how-to/quickstart.md). For a task, choose a
[how-to guide](../how-to/index.md). For the relationships between stages, read
[how imports, exports, and evidence differ](import-export-and-evidence.md).

The Agencia Estatal de Administración Tributaria (AEAT) is the external tax
authority. The command-line interface (CLI) and application programming
interface (API) are Cadrumo product surfaces.

## Lookup map

- [Import, export, and evidence](import-export-and-evidence.md) - supported
  source material, authority boundaries, export purposes, and the evidence
  required for filing review or audit.
- [Identity and naming](identity-and-naming.md) - canonical product identifiers
  and the Cadrumo-versus-AEAT vocabulary.
- [Commands and configuration](commands-and-configuration.md) - CLI,
  workflow-stage, schema, and configuration lookups.
- [Filesystem, state, and safety](filesystem-state-and-safety.md) - storage
  layout, former-state refusal, local export, live-read, and filing boundaries.
- [Registry, legal sources, and Python API](registry-legal-api.md) - grounding
  sources and generated public API pages.
- [Environment overrides](environment-overrides.md) - every environment
  variable the application reads, generated from the live settings model.
  Advanced deployment and development configuration; no user workflow needs
  them.

Terms are defined in the {doc}`glossary </_generated/glossary>`. For ordinary
failures, use [Diagnose and repair](../how-to/troubleshooting.md) and then the
[public issue tracker](https://github.com/nevenincs/cadrumo/issues) with redacted
output. Never publish taxpayer data, credentials, or vulnerability details.
Use the [security policy](https://github.com/nevenincs/cadrumo/blob/main/SECURITY.md) for private security reporting and
its fallback when private reporting is unavailable.

```{toctree}
:hidden:

identity-and-naming
import-export-and-evidence
commands-and-configuration
filesystem-state-and-safety
registry-legal-api
environment-overrides
```
