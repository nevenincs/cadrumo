import type {
  AgentConversationRecord,
  AgentProviderCondition,
  AgentRanWith,
  AgentRunStatus,
  AgentToolCall,
  AgentTurnRecord,
  AgentUsage,
} from "../../shell/agentViews";

// The agent column's conversations in the shapes a host answers with, for the
// scenario host. A conversation is a chain of cadrumo-agent runs, and the
// fixture keeps the runs as the agent does: each with the messages its
// checkpoint holds, its tool calls and its status. What the column is served
// is composed from them, as the desktop host composes it. Times are set back
// from the moment the page loads, so the history's headings read today,
// yesterday and earlier months on any day. Nothing here is a real taxpayer's.

const MINUTE = 60_000;
const HOUR = 60 * MINUTE;
const DAY = 24 * HOUR;
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

/** How many of its predecessor's messages cadrumo-agent seeds a run that
 * continues another with (`successor_transcript_depth`). */
export const SEED_DEPTH = 20;

/** One message of a run's checkpoint. Its id is the agent's, a hash of role
 * and content where it has none. */
export type FixtureMessage = {
  id?: string;
  role: "user" | "assistant";
  text: string;
  sent_at?: string | null;
};

/** One run as the agent keeps it. */
export type FixtureRun = {
  id: string;
  status: AgentRunStatus;
  /** What its checkpoint holds, in order. A run that continues another
   * opens with the last of its predecessor's messages, under ids of their
   * own. */
  messages: FixtureMessage[];
  tools: AgentToolCall[];
  provider_condition?: AgentProviderCondition;
  failure_reason?: string;
  queued_messages?: number;
  selection?: AgentRanWith;
  usage?: AgentUsage;
};

/** An id as the agent gives a message that has none: a digest of its role and
 * content, so that two identical messages share one. */
export function messageDigest(role: string, text: string): string {
  let high = 0x811c9dc5;
  let low = 0x01000193;
  for (const unit of `${role}:${text}`) {
    const code = unit.codePointAt(0) ?? 0;
    high = Math.imul(high ^ code, 0x01000193) >>> 0;
    low = Math.imul(low + code, 0x85ebca6b) >>> 0;
  }
  return `${high.toString(16).padStart(8, "0")}${low.toString(16).padStart(8, "0")}`.repeat(
    2,
  );
}

/** `own` after the last of `previous`, as the agent seeds a run that
 * continues another: the same words, under new ids. */
export function seeded(
  previous: readonly FixtureMessage[],
  own: FixtureMessage[],
): FixtureMessage[] {
  return [
    ...previous.slice(-SEED_DEPTH).map((message, index): FixtureMessage => ({
      ...message,
      id: `seed-${index}-${messageDigest(message.role, message.text).slice(0, 8)}`,
    })),
    ...own,
  ];
}

/**
 * A conversation's records as the desktop host composes them from its runs:
 * each message once, the reply's tool calls just before its first agent
 * message (the agent links no call to a message), and the reply's own record
 * last. A run that continues another leaves out the messages it was seeded
 * with: the first of its own are the `min(20, n)` the predecessor's `n`
 * messages gave it, and they are the predecessor's again.
 */
export function conversationRecords(
  runs: readonly FixtureRun[],
): AgentTurnRecord[] {
  const records: AgentTurnRecord[] = [];
  runs.forEach((run, index) => {
    const before = runs[index - 1];
    const own = run.messages.slice(
      before ? Math.min(SEED_DEPTH, before.messages.length) : 0,
    );
    const firstAgent = own.findIndex((message) => message.role === "assistant");
    const tools = () =>
      run.tools.map((tool): AgentTurnRecord => ({
        kind: "tool",
        reply_id: run.id,
        ...tool,
      }));
    own.forEach((message, at) => {
      if (at === firstAgent) records.push(...tools());
      const id = message.id ?? messageDigest(message.role, message.text);
      records.push(
        message.role === "user"
          ? {
              kind: "person",
              id,
              reply_id: run.id,
              text: message.text,
              sent_at: message.sent_at ?? null,
            }
          : { kind: "agent", id, reply_id: run.id, text: message.text },
      );
    });
    if (firstAgent < 0) records.push(...tools());
    records.push({
      kind: "reply",
      id: run.id,
      status: run.status,
      ...(run.provider_condition
        ? { provider_condition: run.provider_condition }
        : {}),
      ...(run.failure_reason ? { failure_reason: run.failure_reason } : {}),
      ...(run.queued_messages ? { queued_messages: run.queued_messages } : {}),
      ...(run.selection ? { selection: run.selection } : {}),
      ...(run.usage ? { usage: run.usage } : {}),
    });
  });
  return records;
}

export const FIXTURE_CONVERSATIONS: AgentConversationRecord[] = [
  {
    id: "c-iva-t3",
    title: "IVA del tercer trimestre",
    last_active_at: ago(2 * HOUR),
    archived: false,
  },
  {
    id: "c-gastos-vehiculo",
    title: "¿Puedo deducir los gastos del coche?",
    last_active_at: ago(5 * HOUR),
    archived: false,
  },
  {
    id: "c-modelo-130",
    title: "Pago fraccionado del 130",
    last_active_at: ago(DAY + 3 * HOUR),
    archived: false,
  },
  {
    id: "c-facturas-septiembre",
    title: "Facturas de septiembre",
    last_active_at: ago(26 * DAY),
    archived: false,
  },
  {
    id: "c-por-reparar",
    title: "Una respuesta que se quedó a medias",
    last_active_at: ago(27 * DAY),
    archived: false,
  },
  {
    id: "c-conciliando",
    title: "Una respuesta que se está conciliando",
    last_active_at: ago(28 * DAY),
    archived: false,
  },
  {
    id: "c-en-cola",
    title: "Una respuesta con un mensaje en cola",
    last_active_at: ago(29 * DAY),
    archived: false,
  },
  {
    id: "c-sin-titulo",
    title: "",
    last_active_at: ago(30 * DAY),
    archived: false,
  },
  {
    id: "c-renta-2025",
    title: "Borrador de la renta 2025",
    last_active_at: ago(140 * DAY),
    archived: true,
  },
  {
    id: "c-alta-autonomo",
    title: "Alta como autónomo",
    last_active_at: ago(300 * DAY),
    archived: true,
  },
];

const ALPHA_API: AgentRanWith = {
  provider: "alpha",
  transport: "api",
  provider_display_name: "Example Alpha",
  model: "fixture-deep",
  model_display_name: "Fixture Deep",
  effort: "high",
};

const user = (text: string, sent_at: string): FixtureMessage => ({
  role: "user",
  text,
  sent_at,
});
const agent = (text: string): FixtureMessage => ({ role: "assistant", text });

const IVA_QUESTION =
  "Aquí van las facturas y el extracto del trimestre. ¿Me preparas el 303?";
const IVA_ANSWER =
  "He leído 42 apuntes del trimestre. La factura 2026-031 necesita tu revisión antes de contarla: el NIF del emisor no coincide con el del contrato. Con lo demás, el IVA repercutido es de 3.150,00 € y el soportado deducible de 1.204,35 €.";

const FIRST_IVA: FixtureMessage[] = [
  user(IVA_QUESTION, ago(2 * HOUR + 20 * MINUTE)),
  agent(IVA_ANSWER),
];

/** Each conversation's runs, oldest first. A conversation without runs here
 * has had none. */
export const FIXTURE_RUNS: Record<string, FixtureRun[]> = {
  "c-iva-t3": [
    {
      id: "c-iva-t3",
      status: "completed",
      messages: FIRST_IVA,
      tools: [
        {
          id: "t-iva-1",
          title: "ledger_list",
          tool_kind: "read",
          status: "completed",
        },
        {
          id: "t-iva-2",
          title: "ledger_register_invoice",
          tool_kind: "edit",
          status: "failed",
        },
      ],
      selection: ALPHA_API,
      usage: { input_tokens: 18_240, output_tokens: 1_310 },
    },
    {
      id: "r-iva-2",
      status: "completed",
      messages: seeded(FIRST_IVA, [
        user("¿Y qué parte del soportado es deducible?", ago(2 * HOUR)),
        agent(
          "Del soportado, 1.204,35 € son deducibles: la parte del vehículo se deduce según el uso profesional que puedas demostrar.",
        ),
      ]),
      tools: [],
      selection: ALPHA_API,
      usage: { input_tokens: 21_050, output_tokens: 640 },
    },
  ],
  "c-gastos-vehiculo": [
    {
      id: "c-gastos-vehiculo",
      status: "completed",
      messages: [
        user(
          "Uso el coche para visitar clientes. ¿Puedo deducir la gasolina?",
          ago(5 * HOUR),
        ),
        agent(
          "Depende de cómo uses el vehículo. Para el IVA, si lo usas también para fines particulares, solo se deduce la parte que puedas acreditar como afecta.",
        ),
      ],
      tools: [],
    },
  ],
  "c-modelo-130": [
    {
      id: "c-modelo-130",
      // It failed before the agent wrote: no message of the agent's, only why.
      status: "failed",
      messages: [
        user(
          "Calcula el pago fraccionado del tercer trimestre.",
          ago(DAY + 3 * HOUR + 5 * MINUTE),
        ),
      ],
      tools: [],
      provider_condition: "provider_overloaded",
      failure_reason: "The provider answered 529 overloaded_error.",
    },
  ],
  "c-facturas-septiembre": [
    {
      id: "c-facturas-septiembre",
      // Stopped by the person before the agent wrote.
      status: "cancelled",
      messages: [
        user("Lista las facturas de septiembre.", ago(26 * DAY + HOUR)),
      ],
      tools: [],
    },
  ],
  "c-por-reparar": [
    {
      id: "c-por-reparar",
      status: "repair_needed",
      messages: [user("Revisa el borrador del 303.", ago(27 * DAY))],
      tools: [],
    },
  ],
  "c-conciliando": [
    {
      id: "c-conciliando",
      status: "reconciling",
      messages: [user("Compara el libro con el 130.", ago(28 * DAY))],
      tools: [],
    },
  ],
  "c-en-cola": [
    {
      id: "c-en-cola",
      status: "running",
      messages: [user("Prepara el resumen del trimestre.", ago(29 * DAY))],
      tools: [
        {
          id: "t-cola-1",
          title: "ledger_list",
          tool_kind: "read",
          status: "in_progress",
        },
      ],
      queued_messages: 2,
    },
  ],
  "c-sin-titulo": [
    {
      id: "c-sin-titulo",
      status: "completed",
      messages: [
        user("¿Cuándo vence el 303?", ago(30 * DAY)),
        agent("El 303 del tercer trimestre vence el 20 de octubre."),
      ],
      tools: [],
    },
  ],
  "c-renta-2025": [
    {
      id: "c-renta-2025",
      status: "archived",
      messages: [
        user("¿Qué falta para el borrador de la renta?", ago(140 * DAY)),
        agent("Faltan las retenciones del segundo pagador."),
      ],
      tools: [],
    },
  ],
  "c-alta-autonomo": [
    {
      id: "c-alta-autonomo",
      status: "archived",
      messages: [
        user("¿Qué modelos presento al darme de alta?", ago(300 * DAY)),
        agent("Al darte de alta presentas el modelo 036 o el 037."),
      ],
      tools: [],
    },
  ],
};
