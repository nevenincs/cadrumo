import type {
  FileKind,
  SentFile,
  StagedAttachment,
} from "@/components/agent/types";
import type { AgentDocumentRef } from "./agentSession";
import type {
  AgentDocumentRecord,
  AgentDocumentReference,
  AgentViews,
} from "./agentViews";

// The documents stored for a conversation, as its messages name them with `@`:
// listed in name order, filtered by the words after the `@`, and named in a
// send by name and digest. The agent reads a named document where it is
// stored, so nothing is uploaded again, whichever provider runs.

/** The most stored documents one message names: `MAX_RUN_ATTACHMENTS`. */
export const MAX_REFERENCES = 32;

const EXTENSION_KINDS: Record<string, FileKind> = {
  png: "image",
  jpg: "image",
  jpeg: "image",
  gif: "image",
  webp: "image",
  bmp: "image",
  tif: "image",
  tiff: "image",
  heic: "image",
  svg: "image",
  csv: "sheet",
  tsv: "sheet",
  xls: "sheet",
  xlsx: "sheet",
  xlsm: "sheet",
  ods: "sheet",
  txt: "text",
  md: "text",
  json: "text",
  xml: "text",
  log: "text",
  zip: "archive",
  "7z": "archive",
  rar: "archive",
  tar: "archive",
  gz: "archive",
};

/** The extension of a file name without its dot; empty where it has none. */
export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot > 0 && dot < name.length - 1 ? name.slice(dot + 1) : "";
}

/** What a stored file is, as far as how it is drawn goes: from its type
 * where the agent names one, else from its extension. */
export function fileKindOf(name: string, mediaType: string | null): FileKind {
  const type = mediaType?.toLowerCase() ?? "";
  if (type.startsWith("image/")) return "image";
  if (type === "text/csv" || type.includes("spreadsheet")) return "sheet";
  if (type.includes("zip") || type.includes("compressed")) return "archive";
  const kind = EXTENSION_KINDS[extensionOf(name).toLowerCase()];
  if (kind) return kind;
  if (type.startsWith("text/")) return "text";
  return "document";
}

/** Whether a document's name holds what was typed after the `@`, ignoring
 * case, as the agent's own filter does. */
export function documentMatches(name: string, query: string): boolean {
  return name.toLowerCase().includes(query.toLowerCase());
}

/** The documents a message named, as the transcript shows them. */
export function sentFiles(
  references: readonly AgentDocumentReference[],
): SentFile[] {
  return references.map((reference, index) => ({
    id: `${index}:${reference.name}`,
    name: reference.name,
    extension: extensionOf(reference.name),
    kind: fileKindOf(reference.name, reference.media_type),
  }));
}

/** A stored document named for the next message, as the composer stages it:
 * already stored, so ready from the start. Its id is its name, which is
 * unique where it is stored. */
export function stagedReference(
  document: AgentDocumentRecord,
): StagedAttachment {
  return {
    id: document.name,
    name: document.name,
    extension: extensionOf(document.name),
    sizeBytes: document.size_bytes,
    kind: fileKindOf(document.name, document.media_type),
    state: "ready",
  };
}

/** The references a send carries, in the order they were named. */
export const documentRefs = (
  documents: readonly AgentDocumentRecord[],
): AgentDocumentRef[] =>
  documents.map(({ name, sha256 }) => ({ name, sha256 }));

/**
 * Every document stored for a conversation, in name order: each page read
 * after the last until the storage says it has no more, so the list has no
 * end but the storage's. A page that fails fails the whole read; nothing
 * partial is offered as the whole.
 */
export async function readAllDocuments(
  documents: NonNullable<AgentViews["documents"]>,
  conversationId: string,
  signal?: AbortSignal,
): Promise<AgentDocumentRecord[]> {
  const read: AgentDocumentRecord[] = [];
  let after: string | null | undefined;
  do {
    if (signal?.aborted) throw new DOMException("aborted", "AbortError");
    const page = await documents(
      after
        ? { conversation_id: conversationId, after }
        : { conversation_id: conversationId },
    );
    read.push(...page.documents);
    // A page that names no next one, or the one it started after, ends it.
    after = page.next_after !== after ? page.next_after : null;
  } while (after);
  return read;
}

/**
 * Lists a conversation's stored documents for what follows an `@`. The whole
 * listing is read once when an `@` is begun and kept while the words after it
 * change, so narrowing it is immediate; each new `@` reads it again.
 */
export class DocumentLister {
  #held: {
    conversationId: string;
    read: Promise<AgentDocumentRecord[]>;
  } | null = null;

  readonly #documents: NonNullable<AgentViews["documents"]>;

  constructor(documents: NonNullable<AgentViews["documents"]>) {
    this.#documents = documents;
  }

  /** The stored documents whose names hold `query`, in name order. */
  async matching(
    conversationId: string,
    query: string,
    signal: AbortSignal,
  ): Promise<AgentDocumentRecord[]> {
    let held = this.#held;
    if (query === "" || held?.conversationId !== conversationId) {
      const read = readAllDocuments(this.#documents, conversationId);
      held = { conversationId, read };
      this.#held = held;
      // A failed read is never kept: the next words ask again.
      read.catch(() => {
        if (this.#held === held) this.#held = null;
      });
    }
    const all = await held.read;
    if (signal.aborted) throw new DOMException("aborted", "AbortError");
    return all.filter((document) => documentMatches(document.name, query));
  }
}
