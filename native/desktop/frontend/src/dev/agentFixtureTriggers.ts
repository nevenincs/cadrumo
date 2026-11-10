// The messages the scenario agent's triggers are written in, and what each
// makes a reply do. Everything it says is synthetic.

import type { AgentToolRefusal } from "../shell/agentSession";

/** The messages the fixture's triggers are written in, as an agent would be
 * asked: each makes the reply do something the real one can. */
export const FAILS_FIRST = /falla antes de escribir/i;
export const AUTHENTICATION_REQUIRED = /requiere iniciar sesión/i;
export const UNEXPECTED_PROVIDER_CONDITION = /condición desconocida/i;
export const TOOL_FAILS = /herramienta falla/i;
// A reply that thinks aloud, records what its tool call took and gave, and
// answers in the Markdown a real agent writes.
export const RICH = /con formato/i;
export const RICH_THOUGHTS = [
  "Busco los apuntes del tercer trimestre.",
  "Sumo el IVA repercutido de las facturas emitidas.",
];
export const RICH_TOOL_DETAILS = [
  '{"trimestre":"3T","ejercicio":2026}',
  "Tool result:\n42 apuntes",
];
export const RICH_REPLY = [
  "## Resumen del trimestre",
  "El IVA **repercutido** es de *3.150,00 €*.",
  "- 42 apuntes leídos\n- 1 factura por revisar: `2026-031`",
  "| Casilla | Importe |\n|:--|--:|\n| 27 | 3.150,00 |",
  "Más en [la sede electrónica](https://sede.agenciatributaria.gob.es).",
  "[Set up AEAT access](cadrumo://view/profile/aeat-access).",
].join("\n\n");
// A reply that links to views of the window and to one it does not draw, a
// refusal and a link in the retired profile form.
export const LINKS = /con enlaces/i;
export const LINKS_REPLY = [
  "Puedes seguir en:",
  "- [el calendario](cadrumo://view/calendar)",
  "- [los movimientos](cadrumo://view/ledger/movements)",
  "- [las operaciones](cadrumo://view/operations)",
  "- [los datos de la AEAT](cadrumo://view/aeat-sync)",
  "- [el espacio de trabajo](cadrumo://view/terminal)",
  "- [una vista que no existe](cadrumo://view/nowhere)",
  "- [un enlace antiguo](cadrumo://profiles/5aa00000-0000-4000-8000-0000000000aa/ledger)",
].join("\n");
// A reply that links to exactly the view the person names, so a scenario
// can link to a row it read from the page.
export const LINK_TO = /^enlaza (cadrumo:\S+)$/i;
// A tool the product refuses, as the host passes the refusal on: for a
// component that is not set up, for something setup does not recover, and
// one whose recovery is not an action the window knows, as though it got
// past the host's own check.
export const TOOL_REFUSALS: readonly (readonly [
  RegExp,
  string,
  AgentToolRefusal,
])[] = [
  [
    /falta el navegador/i,
    "aeat_capture_censo",
    {
      code: "operation_not_successful",
      recovery_action_id: "operator.provision.browser",
    },
  ],
  [
    /rechazo ajeno/i,
    "ledger_import",
    {
      code: "operation_not_successful",
      recovery_action_id: "operator.ledger.review",
    },
  ],
  [
    /rechazo malformado/i,
    "aeat_capture_censo",
    {
      code: "OPERATION_NOT_SUCCESSFUL",
      recovery_action_id: "OPERATOR.PROVISION.BROWSER",
    },
  ],
];
export const BUSY_ELSEWHERE = /ocupado/i;
/** A message the made-up agent refuses because the chosen model does not fit
 * this computer. */
export const MODEL_DOES_NOT_FIT = /no cabe/i;
