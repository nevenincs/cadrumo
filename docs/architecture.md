# Architecture

`aeat` follows the ADR hard-cutover hexagonal layout:

- `aeat.domain.schema`
- `aeat.adapters.inbound.schema`
- `aeat.adapters.inbound.justificante`
- `aeat.adapters.outbound.aeat.auth`
- `aeat.adapters.outbound.aeat.browser`
- `aeat.adapters.outbound.aeat.sede`
- `aeat.adapters.outbound.aeat.export`
- `aeat.adapters.persistence.storage`
- `aeat.adapters.persistence.profile`
- `aeat.application.auth`
- `aeat.application.filing`
- `aeat.application.filing.testing`
- `aeat.entrypoints.cli`
- `aeat.core.i18n`

Domain packages own business records and pure rules. Inbound adapters
parse external inputs, outbound adapters talk to AEAT, Google, and LLM
providers, persistence adapters own disk state, and application packages
orchestrate use cases.

The import-contract tests enforce the accepted hard cut: deleted root
modules do not reappear, moved parser/extraction/persistence surfaces
stay at their canonical destinations, and public imports use the ADR
package paths.
