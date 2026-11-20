// What the scenario agent's replies ask: the questions and permission
// requests the fixture makes, checked against the bounds the agent holds
// for them, and the refusals it reports.

import {
  characters,
  questionnaireFaults,
  type AnswerFault,
} from "../shell/agentClarification";
import type { AttachmentCardAnswer } from "../shell/attachmentAdminContract";
import type { BarCode, BarredRead } from "../shell/attachmentRefusals";
import type {
  AgentApproval,
  AgentApprovalOption,
  AgentQuestion,
  AgentQuestionnaire,
} from "../shell/agentSnapshotContract";

// The questions, as cadrumo-agent serves them: every field present, a text
// question's options null. A reply that asks is given these unless its
// message asks for the most the agent can: four questions of four options,
// a prompt and an option at the longest they can be.
export const QUESTIONS: AgentQuestion[] = [
  {
    id: "q-trimestre",
    prompt: "¿Qué trimestre preparo?",
    kind: "choice",
    options: ["Primer trimestre", "Segundo trimestre", "Tercer trimestre"],
    required: true,
  },
  {
    id: "q-notas",
    prompt: "¿Algo más que deba saber?",
    kind: "text",
    options: null,
    required: false,
  },
];

/** `words` repeated, and ended with a full stop, to exactly `length`
 * characters. */
export const exactly = (words: string, length: number) =>
  `${words.repeat(Math.ceil(length / words.length)).slice(0, length - 1)}.`;

export const MOST_QUESTIONS: AgentQuestion[] = [
  {
    id: "q-trimestre",
    prompt: exactly(
      "¿Para qué trimestre preparo la declaración, y por qué? ",
      512,
    ),
    kind: "choice",
    options: [
      "Primer trimestre",
      "Segundo trimestre",
      "Tercer trimestre",
      exactly("Cuarto trimestre, con el ajuste de fin de año incluido ", 128),
    ],
    required: true,
  },
  {
    id: "q.nif_2",
    prompt: "¿Cuál es el NIF del cliente de la factura 2026-031?",
    kind: "text",
    options: null,
    required: true,
  },
  {
    id: "q-prorrata",
    prompt: "¿Aplicas la prorrata del IVA?",
    kind: "choice",
    options: ["Sí", "No"],
    required: false,
  },
  {
    id: "q-notas",
    prompt: "¿Algo más que deba saber?",
    kind: "text",
    options: null,
    required: false,
  },
];

// The options of a permission request, in the order the agent lists them,
// each under its own name. The agent offers only options that answer the call
// or the session alone. Their order on the card is decided by kind.
export const TOOL_OPTIONS: AgentApprovalOption[] = [
  { option_id: "allow-once", name: "Allow this read", kind: "allow_once" },
  { option_id: "reject-once", name: "Skip this read", kind: "reject_once" },
];

// Built-in options from cadrumo-agent's graph/acp_options.py: every tool call,
// a mounted server's included, offers exactly these three.
export const CANONICAL_OPTIONS: AgentApprovalOption[] = [
  { option_id: "allow_once", name: "Allow once", kind: "allow_once" },
  {
    option_id: "allow_session",
    name: "Allow for this session",
    kind: "allow_session",
  },
  { option_id: "reject_once", name: "Reject", kind: "reject_once" },
];

export const PERMISSION_TARGETS: Record<
  string,
  { tool: string; description: string }
> = {
  status: { tool: "status", description: "Permission required: status" },
  file: {
    tool: "write_file",
    description:
      'Permission required: write_file; workspace file path: "reports/2026 IVA.csv"',
  },
  attachment: {
    tool: "read_attachment",
    description:
      'Permission required: read_attachment; attachment: "invoice.pdf"',
  },
  operation: {
    tool: "execute",
    description: "Cadrumo operation: user-profile.censo-prepare",
  },
};

// Options the agent gives no name: null, empty or only spaces.
export const UNNAMED_OPTIONS: AgentApprovalOption[] = [
  { option_id: "a", name: "", kind: "allow_once" },
  { option_id: "b", name: null, kind: "reject_once" },
  { option_id: "c", name: null, kind: "allow_once" },
  { option_id: "d", name: "   ", kind: "reject_once" },
];

// The most a request can hold: sixteen options, alternating kinds, the first
// of each named at the longest, around a tool name and a description at theirs.
export const MOST_OPTIONS: AgentApprovalOption[] = [
  1, 2, 3, 4, 5, 6, 7, 8,
].flatMap((number) =>
  (["allow_once", "reject_once"] as const).map((kind): AgentApprovalOption => ({
    option_id: `${kind.replace("_", "-")}-${number}`,
    name:
      number === 1
        ? exactly(`${kind} with a name that goes on and on `, 128)
        : `${kind} ${number}`,
    kind,
  })),
);
export const MOST_TOOL_CALL = exactly(
  "ledger_list_every_entry_of_the_quarter_",
  128,
);
export const MOST_DESCRIPTION = exactly(
  "Permission required: ledger_list_every_entry_of_the_quarter. ",
  4096,
);

// What the agent bounds on a permission request.
const PERMISSION_OPTIONS_MAX = 16;
export const PERMISSION_OPTION_ID_MAX = 64;
const PERMISSION_OPTION_NAME_MAX = 128;
const PERMISSION_TOOL_CALL_MAX = 128;
const PERMISSION_DESCRIPTION_MAX = 4096;

/** Why cadrumo-agent could not have asked for this permission. */
function approvalFaults(approval: AgentApproval): string[] {
  const notes: string[] = [];
  const { options } = approval;
  if (options.length < 1 || options.length > PERMISSION_OPTIONS_MAX)
    notes.push("a request offers one to sixteen options");
  if (new Set(options.map((option) => option.option_id)).size < options.length)
    notes.push("option ids repeat");
  for (const option of options) {
    if (
      option.option_id === "" ||
      characters(option.option_id) > PERMISSION_OPTION_ID_MAX
    )
      notes.push("an option id is empty or longer than 64");
    if (characters(option.name ?? "") > PERMISSION_OPTION_NAME_MAX)
      notes.push("an option name is longer than 128");
  }
  if (characters(approval.tool_call ?? "") > PERMISSION_TOOL_CALL_MAX)
    notes.push("the tool name is longer than 128");
  if (characters(approval.description ?? "") > PERMISSION_DESCRIPTION_MAX)
    notes.push("the description is longer than 4096");
  return notes;
}

/** What the agent's answer route says when it refuses an answer. A question
 * that is not answered as the questions require is explained in a sentence
 * of its own; an answer whose shape is wrong is refused by the schema. Either
 * way it is a 422 with prose, never a code, and the host can pass on only
 * the status. */
export function refusalProse(fault: AnswerFault): string {
  switch (fault.kind) {
    case "unknown_question":
      return `unknown question id '${fault.id}'`;
    case "missing":
      return `question '${fault.id}' is required and unanswered`;
    case "not_an_option":
      return `answer to question '${fault.id}' is not one of its declared options`;
    case "control_characters":
      return "clarification text must not contain control characters";
    case "too_long":
      return "String should have at most 2048 characters";
    case "invalid_id":
      return "String should match pattern for a question id";
    case "too_many":
      return "Dictionary should have at most 4 items after validation";
  }
}

/** A refusal the way the host reports the agent's: by the status alone. */
export const refusedWith = (status: number, prose: string) =>
  Object.assign(new Error(prose), { code: `agent_gateway_${status}` });

/** What the fixture asks, checked as the agent checks what it asks: a
 * request it would not have built is a mistake of the fixture. */
export function asked(questionnaire: AgentQuestionnaire): AgentQuestionnaire {
  const notes = questionnaireFaults(questionnaire);
  if (notes.length > 0)
    throw new Error(`The fixture asks what the agent would not: ${notes}`);
  return questionnaire;
}

/** What the fixture requests permission for, checked the same way. */
export function requested(approval: AgentApproval): AgentApproval {
  const notes = approvalFaults(approval);
  if (notes.length > 0)
    throw new Error(`The fixture requests what the agent would not: ${notes}`);
  return approval;
}

// A message that asks the agent to read files the service refuses to release,
// by the bar it names (the profile's when it names none): one parked read per
// file, as the agent parks them when it reads each attached file.
const BARRED_READS =
  /adjuntos sin enviar(?: \((gestor_mode|cloud_upload_not_permitted|profile_not_eligible)\))?/i;
const BARRED_FILES = ["escaneo.pdf", "foto.jpg", "factura.xml", "gastos.xlsx"];

/** The reads `text` asks for, as the agent requests permission for each, and
 * what the service says of each in `reads`; null when it asks for none. */
export function barredAsk(
  text: string,
  replyId: string,
  nextId: (prefix: string) => string,
  reads: Map<string, BarredRead>,
): AgentApproval[] | null {
  const asked = BARRED_READS.exec(text);
  if (!asked) return null;
  const code = (asked[1] ?? "profile_not_eligible") as BarCode;
  return BARRED_FILES.map((name) => {
    const request_id = nextId("p");
    reads.set(request_id, { requestId: request_id, code, name });
    return requested({
      request_id,
      reply_id: replyId,
      source: "agent_tool",
      tool_call: "read_attachment",
      tool_kind: "other",
      tool_server: null,
      description: `Permission required: read_attachment; attachment: "${name}"`,
      options: CANONICAL_OPTIONS,
    });
  });
}

/** What the service answers for the card of the read `requestId`. */
export function barredCard(
  reads: ReadonlyMap<string, BarredRead>,
  requestId: string,
): AttachmentCardAnswer {
  const read = reads.get(requestId);
  return read
    ? { kind: "refused", code: read.code, name: read.name }
    : { kind: "not_required" };
}
