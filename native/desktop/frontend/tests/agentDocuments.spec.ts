import { expect, test } from "@playwright/test";
import {
  documentMatches,
  extensionOf,
  fileKindOf,
  readAllDocuments,
} from "../src/shell/agentDocuments";
import { uploadRefusalWords } from "../src/shell/agentStaging";
import type {
  AgentDocumentPage,
  AgentDocumentRecord,
  AgentDocumentsQuery,
} from "../src/shell/agentViews";

// How the agent column reads a conversation's stored documents for `@`, and
// words why a file was not stored. Words are left as their keys.

const words = (key: string) => key;

const record = (name: string): AgentDocumentRecord => ({
  name,
  size_bytes: 1,
  modified_at: "2026-10-18T10:00:00Z",
  sha256: "0".repeat(64),
  media_type: null,
});

test("every page is read, in order, until the storage says there is no more", async () => {
  const asked: AgentDocumentsQuery[] = [];
  const pages: Record<string, AgentDocumentPage> = {
    "": { documents: [record("a"), record("b")], next_after: "b" },
    b: { documents: [record("c")], next_after: "c" },
    c: { documents: [], next_after: null },
  };
  const all = await readAllDocuments(async (query) => {
    asked.push(query);
    return pages[query.after ?? ""] ?? { documents: [], next_after: null };
  }, "r1");
  expect(all.map((document) => document.name)).toEqual(["a", "b", "c"]);
  expect(asked).toEqual([
    { conversation_id: "r1" },
    { conversation_id: "r1", after: "b" },
    { conversation_id: "r1", after: "c" },
  ]);
});

test("a page that names itself as the next ends the read rather than loop", async () => {
  let reads = 0;
  const all = await readAllDocuments(async () => {
    reads += 1;
    return { documents: [record("a")], next_after: "a" };
  }, "r1");
  expect(reads).toBe(2);
  expect(all).toHaveLength(2);
});

test("a failed page fails the whole read", async () => {
  await expect(
    readAllDocuments(async (query) => {
      if (query.after) throw new Error("agent_gateway_attachments_unavailable");
      return { documents: [record("a")], next_after: "a" };
    }, "r1"),
  ).rejects.toThrow("agent_gateway_attachments_unavailable");
});

test("what follows the @ is found anywhere in a name, ignoring case", () => {
  expect(documentMatches("Factura-2026.PDF", "2026.pdf")).toBe(true);
  expect(documentMatches("notas del trimestre.txt", "DEL T")).toBe(true);
  expect(documentMatches("extracto.csv", "factura")).toBe(false);
  expect(documentMatches("extracto.csv", "")).toBe(true);
});

test("a file's kind comes from its type, then its extension", () => {
  expect(extensionOf("informe.final.pdf")).toBe("pdf");
  expect(extensionOf(".oculto")).toBe("");
  expect(extensionOf("sin-extension")).toBe("");
  expect(fileKindOf("foto", "image/heic")).toBe("image");
  expect(fileKindOf("datos.bin", "text/csv")).toBe("sheet");
  expect(fileKindOf("libro.ods", null)).toBe("sheet");
  expect(fileKindOf("notas.md", null)).toBe("text");
  expect(fileKindOf("raro.xyz", "text/plain")).toBe("text");
  expect(fileKindOf("contrato.docx", null)).toBe("document");
});

test("every refusal of an upload has words of its own", () => {
  const refusals: [string, string][] = [
    ["agent_attachment_too_large", "desktop.agent.upload_too_large"],
    ["agent_gateway_attachment_too_large", "desktop.agent.upload_too_large"],
    ["agent_attachment_format_refused", "desktop.agent.upload_format_refused"],
    [
      "agent_gateway_attachment_format_refused",
      "desktop.agent.upload_format_refused",
    ],
    [
      "agent_gateway_attachment_quota_exceeded",
      "desktop.agent.upload_quota_exceeded",
    ],
    [
      "agent_gateway_conversation_deleting",
      "desktop.agent.conversation_deleting",
    ],
    [
      "agent_gateway_conversation_id_taken",
      "desktop.agent.conversation_id_taken",
    ],
    ["agent_attachment_unreadable", "desktop.agent.upload_unreadable"],
    ["agent_attachment_name_refused", "desktop.agent.upload_name_refused"],
    ["agent_gateway_attachment_refused", "desktop.agent.upload_failed"],
    ["agent_gateway_unreachable", "desktop.agent.upload_failed"],
  ];
  for (const [code, key] of refusals)
    expect(uploadRefusalWords(words, code), code).toBe(key);
});
