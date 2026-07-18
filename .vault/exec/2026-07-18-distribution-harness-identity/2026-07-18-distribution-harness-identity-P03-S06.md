---
tags:
  - '#exec'
  - '#distribution-harness-identity'
date: '2026-07-18'
modified: '2026-07-18'
step_id: 'S06'
related:
  - "[[2026-07-18-distribution-harness-identity-plan]]"
---

<!-- FRONTMATTER RULES:
     tags: one directory tag (hardcoded #exec) and one feature tag.
     Replace distribution-harness-identity with a kebab-case feature tag, e.g. #foo-bar.
     Additional tags may be appended below the required pair.

     modified: CLI-maintained last-modified stamp; set at scaffold time,
     refreshed by mutating CLI verbs and vault check fix; never hand-edit.

     step_id is the originating Step's canonical identifier, e.g. S01.
     The S06 and 2026-07-18-distribution-harness-identity-plan placeholders are machine-filled by
     `vaultspec-core vault add exec`; do not fill them by hand.

     Related: use wiki-links as '[[yyyy-mm-dd-foo-bar-plan]]' and link the
     parent plan.

     DO NOT add fields beyond those scaffolded; metadata lives
     only in the frontmatter. -->

<!-- LINK RULES:
     - [[wiki-links]] are ONLY for .vault/ documents in the related: field above.
     - NEVER use [[wiki-links]] or markdown links in the document body.
     - NEVER reference file paths in the body. If you must name a source file,
       class, or function, use inline backtick code: `src/module.py`. -->

<!-- STEP RECORD:
     This file represents one Step from the originating plan. Identified
     by its canonical leaf identifier (S##) and ancestor display path.
     The Author and approve the product-reviewed bilingual product-description copy for the four client-display blocks (plugin, marketplace, MCPB description, MCPB long_description), each carrying labeled English and Spanish text covering the six required claims (capability, safety, privacy, on-host storage, human confirmation, never-files-live) as a docs-authority approval act producing the exact wording with no code change and ## Scope

- `.vault/exec/2026-07-18-distribution-harness-identity/` placeholders below are machine-filled
     by `vaultspec-core vault add exec` from the originating Step row;
     do not fill them by hand. -->

# Author and approve the product-reviewed bilingual product-description copy for the four client-display blocks (plugin, marketplace, MCPB description, MCPB long_description), each carrying labeled English and Spanish text covering the six required claims (capability, safety, privacy, on-host storage, human confirmation, never-files-live) as a docs-authority approval act producing the exact wording with no code change

## Scope

- `.vault/exec/2026-07-18-distribution-harness-identity/`

## Description

- Author and approve the bilingual (English + Spanish) product-description copy
  for every client-display field, as the coordinator's documentation-authority
  act. The wiring steps (S07-S09) enroll these exact texts as the verifier's
  approved pairs; any wording change re-enters through this record.

## Outcome

The four approved copy blocks. Spanish is European Spanish with AEAT
terminology; the full-length fields carry all six required claims (tax
capability, read-only safety toward AEAT, provider privacy boundary, on-host
encrypted storage, human confirmation, never-files-live); the short fields
carry the compact core claims honestly, and their approved pairs enroll as
limited-scope fields.

### 1. Plugin description (plugin and marketplace-plugin fields)

English: Operate Cadrumo, the deterministic Spanish-tax CLI, from Claude:
grounded search over the bundled BOE/AEAT legal corpus, situation-keyed guided
workflows, and human-confirmed execution of every state-changing step. Cadrumo
never files to AEAT - the taxpayer files outside the app - and all financial
data stays on-host in encrypted storage; only what the conversation shows
reaches the model provider. The server advertises an orientation core by
default (overview + contract + search/execute); set the surface option to
'full' to advertise every verb up front.

Español: Opera Cadrumo, la CLI determinista de impuestos españoles, desde
Claude: búsqueda fundamentada sobre el corpus legal BOE/AEAT incluido, flujos
guiados según la situación del contribuyente y ejecución con confirmación
humana de cada paso que modifica el estado. Cadrumo nunca presenta
declaraciones ante la AEAT - el contribuyente presenta fuera de la aplicación -
y todos los datos financieros permanecen en el equipo en almacenamiento
cifrado; solo lo que muestra la conversación llega al proveedor del modelo. El
servidor anuncia por defecto un núcleo de orientación (visión general +
contrato + buscar/ejecutar); configura la opción de superficie en 'full' para
anunciar todos los verbos desde el inicio.

### 2. Marketplace description

English: Neve plugin marketplace - Claude plugins including the Cadrumo
Spanish-tax assistant (read-only toward AEAT: it never files; financial data
stays on-host).

Español: Marketplace de plugins de Neve - plugins de Claude, incluido el
asistente de impuestos españoles Cadrumo (solo lectura frente a la AEAT: nunca
presenta declaraciones; los datos financieros permanecen en el equipo).

### 3. MCPB description (short)

English: Operate Cadrumo, a deterministic Spanish-tax CLI, as an MCP tool
surface: grounded search over the bundled BOE/AEAT legal corpus,
situation-keyed guided workflows, and gated execution that never files to
AEAT.

Español: Opera Cadrumo, una CLI determinista de impuestos españoles, como
superficie de herramientas MCP: búsqueda fundamentada sobre el corpus legal
BOE/AEAT incluido, flujos guiados según la situación del contribuyente y
ejecución controlada que nunca presenta declaraciones ante la AEAT.

### 4. MCPB long description (all six claims)

English: The Cadrumo console exposes a deterministic Spanish-tax CLI to any
MCP client. It carries the operator rules, the taxpayer-situation skills, and
guided-workflow prompts; a read-only corpus and terminology search for legal
grounding; and a human-in-the-loop confirmation gate on every state-changing
verb. Live submission to AEAT is permanently impossible - no such tool exists;
the taxpayer files outside the app. All financial data stays on-host in
encrypted storage; only the conversation and the figures the assistant sees
reach the LLM client's provider. The bundle contains the exact digest-pinned
Cadrumo distribution cohort.

Español: La consola de Cadrumo expone una CLI determinista de impuestos
españoles a cualquier cliente MCP. Incorpora las reglas del operador, las
habilidades por situación del contribuyente y los avisos de flujo guiado; una
búsqueda de solo lectura sobre el corpus legal y la terminología para la
fundamentación jurídica; y una puerta de confirmación humana en cada verbo que
modifica el estado. La presentación en vivo ante la AEAT es permanentemente
imposible - no existe tal herramienta; el contribuyente presenta fuera de la
aplicación. Todos los datos financieros permanecen en el equipo en
almacenamiento cifrado; solo la conversación y las cifras que ve el asistente
llegan al proveedor del cliente LLM. El paquete contiene exactamente la
cohorte de distribución de Cadrumo, fijada por sus resúmenes criptográficos.

## Notes

- No signing or verified-publisher claim appears in any block, per the
  accepted unsigned-MCPB posture ADR.
- The wiring steps must enroll each field's EXACT extracted English and
  Spanish texts as the approved pair for that specific surface and field; a
  later wording edit is a new approval through this record, never an in-place
  tweak at the enrollment site.

## Revision 2 (2026-07-18): six-claim parity for the short fields

The verifier requires all six claims on every client-display field; the
original short blocks carried a subset. The long description (block 4) is
unchanged. The following REPLACE blocks 1-3; the wiring re-enrolls these exact
texts.

### 1r. Plugin description (plugin and marketplace-plugin fields)

English: Operate Cadrumo, the deterministic Spanish-tax CLI, from Claude:
grounded search over the bundled BOE/AEAT legal corpus, situation-keyed guided
workflows, and human-confirmed execution of every state-changing step. Cadrumo
is read-only toward AEAT and never files - live submission is impossible and
the taxpayer files outside the app. All financial data stays on-host in
encrypted storage; only what the conversation shows reaches the model
provider. The server advertises an orientation core by default (overview +
contract + search/execute); set the surface option to 'full' to advertise
every verb up front.

Español: Opera Cadrumo, la CLI determinista de impuestos españoles, desde
Claude: búsqueda fundamentada sobre el corpus legal BOE/AEAT incluido, flujos
guiados según la situación del contribuyente y ejecución con confirmación
humana de cada paso que modifica el estado. Cadrumo es de solo lectura frente
a la AEAT y nunca presenta declaraciones - la presentación en vivo es
imposible y el contribuyente presenta fuera de la aplicación. Todos los datos
financieros permanecen en el equipo en almacenamiento cifrado; solo lo que
muestra la conversación llega al proveedor del modelo. El servidor anuncia por
defecto un núcleo de orientación (visión general + contrato + buscar/
ejecutar); configura la opción de superficie en 'full' para anunciar todos los
verbos desde el inicio.

### 2r. Marketplace description

English: Neve plugin marketplace - Claude plugins including the Cadrumo
Spanish-tax assistant: read-only toward AEAT, it never files (the taxpayer
files outside the app), every state change needs human confirmation, financial
data stays on-host in encrypted storage, and only the conversation reaches the
model provider.

Español: Marketplace de plugins de Neve - plugins de Claude, incluido el
asistente de impuestos españoles Cadrumo: de solo lectura frente a la AEAT,
nunca presenta declaraciones (el contribuyente presenta fuera de la
aplicación), cada cambio de estado requiere confirmación humana, los datos
financieros permanecen en el equipo en almacenamiento cifrado y solo la
conversación llega al proveedor del modelo.

### 3r. MCPB description (short)

English: Operate Cadrumo, a deterministic Spanish-tax CLI, as an MCP tool
surface: grounded search over the bundled BOE/AEAT legal corpus,
situation-keyed guided workflows, and human-confirmed execution of every
state-changing step. Read-only toward AEAT - it never files; the taxpayer
files outside the app. Financial data stays on-host in encrypted storage, and
only the conversation reaches the model provider.

Español: Opera Cadrumo, una CLI determinista de impuestos españoles, como
superficie de herramientas MCP: búsqueda fundamentada sobre el corpus legal
BOE/AEAT incluido, flujos guiados según la situación del contribuyente y
ejecución con confirmación humana de cada paso que modifica el estado. De solo
lectura frente a la AEAT - nunca presenta declaraciones; el contribuyente
presenta fuera de la aplicación. Los datos financieros permanecen en el equipo
en almacenamiento cifrado y solo la conversación llega al proveedor del
modelo.
