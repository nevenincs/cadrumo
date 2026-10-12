import type {
  AgentConversationRecord,
  AgentDocumentRecord,
  AgentTurnRecord,
} from "../../shell/agentViews";

// The agent column's conversations and documents in the shapes a host
// answers with, for the scenario host. Times are set back from the moment
// the page loads, so the history's headings read today, yesterday and
// earlier months on any day. Each conversation's document count is the
// length of its list below. Nothing here is a real taxpayer's.

const HOUR = 3_600_000;
const DAY = 24 * HOUR;
const ago = (ms: number) => new Date(Date.now() - ms).toISOString();

export const FIXTURE_CONVERSATIONS: AgentConversationRecord[] = [
  {
    id: "c-iva-t3",
    title: "IVA del tercer trimestre",
    last_active_at: ago(2 * HOUR),
    document_count: 4,
    archived: false,
  },
  {
    id: "c-gastos-vehiculo",
    title: "¿Puedo deducir los gastos del coche?",
    last_active_at: ago(5 * HOUR),
    document_count: 0,
    archived: false,
  },
  {
    id: "c-modelo-130",
    title: "Pago fraccionado del 130",
    last_active_at: ago(DAY + 3 * HOUR),
    document_count: 2,
    archived: false,
  },
  {
    id: "c-facturas-septiembre",
    title: "Facturas de septiembre",
    last_active_at: ago(26 * DAY),
    document_count: 0,
    archived: false,
  },
  {
    id: "c-renta-2025",
    title: "Borrador de la renta 2025",
    last_active_at: ago(140 * DAY),
    document_count: 0,
    archived: true,
  },
  {
    id: "c-alta-autonomo",
    title: "Alta como autónomo",
    last_active_at: ago(300 * DAY),
    document_count: 0,
    archived: true,
  },
];

const PDF = "application/pdf";

export const FIXTURE_DOCUMENTS: Record<string, AgentDocumentRecord[]> = {
  "c-iva-t3": [
    {
      id: "d-factura-031",
      name: "factura-2026-031.pdf",
      media_type: PDF,
      size_bytes: 184_320,
      role: "ledger",
      status: "needsReview",
    },
    {
      id: "d-ticket",
      name: "ticket-gasolinera.jpg",
      media_type: "image/jpeg",
      size_bytes: 1_245_184,
      role: "ledger",
      status: "ready",
    },
    {
      id: "d-extracto",
      name: "extracto-tercer-trimestre.xlsx",
      media_type:
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      size_bytes: 52_224,
      role: "information",
      status: "extracting",
    },
    {
      id: "d-facturas-zip",
      name: "facturas-proveedores.zip",
      media_type: "application/zip",
      size_bytes: 2_621_440,
      role: "context",
      status: "ready",
      members: [
        {
          id: "d-zip-1",
          name: "proveedor-a-julio.pdf",
          media_type: PDF,
          size_bytes: 98_304,
          role: "context",
          status: "ready",
        },
        {
          id: "d-zip-2",
          name: "proveedor-b-agosto.pdf",
          media_type: PDF,
          size_bytes: 112_640,
          role: "context",
          status: "failed",
        },
      ],
    },
  ],
  "c-modelo-130": [
    {
      id: "d-130-borrador",
      name: "borrador-130-3T.pdf",
      media_type: PDF,
      size_bytes: 76_800,
      role: "context",
      status: "ready",
    },
    {
      id: "d-ingresos",
      name: "ingresos-julio-septiembre.csv",
      media_type: "text/csv",
      size_bytes: 8_192,
      role: "information",
      status: "ready",
    },
  ],
};

const MINUTE = 60_000;

/** Each conversation's turns, oldest first. A conversation without its own
 * list here has had none. */
export const FIXTURE_HISTORY: Record<string, AgentTurnRecord[]> = {
  "c-iva-t3": [
    {
      kind: "person",
      id: "t-iva-1",
      text: "Aquí van las facturas y el extracto del trimestre. ¿Me preparas el 303?",
      sent_at: ago(2 * HOUR + 20 * MINUTE),
      files: [
        { id: "d-factura-031", name: "factura-2026-031.pdf", media_type: PDF },
        {
          id: "d-ticket",
          name: "ticket-gasolinera.jpg",
          media_type: "image/jpeg",
        },
        {
          id: "d-extracto",
          name: "extracto-tercer-trimestre.xlsx",
          media_type:
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        },
      ],
    },
    {
      kind: "tool",
      id: "t-iva-2",
      label: "Leer los apuntes del libro del tercer trimestre",
      state: "done",
    },
    {
      kind: "tool",
      id: "t-iva-3",
      label: "Registrar la factura 2026-031",
      state: "refused",
      detail: "Registrar un apunte lo confirmas tú en la TUI.",
    },
    {
      kind: "agent",
      id: "t-iva-4",
      text: "He leído 42 apuntes del trimestre. La factura 2026-031 necesita tu revisión antes de contarla: el NIF del emisor no coincide con el del contrato. Con lo demás, el IVA repercutido es de 3.150,00 € y el soportado deducible de 1.204,35 €.",
      state: "complete",
    },
  ],
  "c-gastos-vehiculo": [
    {
      kind: "person",
      id: "t-coche-1",
      text: "Uso el coche para visitar clientes. ¿Puedo deducir la gasolina?",
      sent_at: ago(5 * HOUR),
    },
    {
      kind: "agent",
      id: "t-coche-2",
      text: "Depende de cómo uses el vehículo. Para el IVA, si lo usas también",
      state: "working",
    },
  ],
  "c-modelo-130": [
    {
      kind: "person",
      id: "t-130-1",
      text: "Calcula el pago fraccionado del tercer trimestre.",
      sent_at: ago(DAY + 3 * HOUR + 5 * MINUTE),
    },
    {
      kind: "agent",
      id: "t-130-2",
      text: "",
      state: "failed",
      failure_reason: "El servicio del modelo no respondió a tiempo.",
    },
  ],
};
