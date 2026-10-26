import { expect, test } from "@playwright/test";

test("document removal distinguishes a stored name from the whole store, and policy comes from the host", async ({
  page,
}) => {
  await page.goto("/scenarios.html");
  const result = await page.evaluate(async () => {
    const calls: { command: string; args: unknown }[] = [];
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "b".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          calls.push({ command, args });
          return command === "agent_attachment_policy"
            ? { max_file_bytes: 25, extensions: ["pdf", "txt"] }
            : null;
        },
      },
    });
    const modulePath = "/src/shell/tauriHost.ts";
    const { tauriHost } = (await import(
      modulePath
    )) as typeof import("../../src/shell/tauriHost");
    const session = tauriHost().agentSession!;
    await session.removeDocuments!("r-docs", "factura ñ.pdf");
    await session.removeDocuments!("r-docs");
    const policy = await session.attachmentPolicy!();
    return { calls, policy };
  });
  expect(result.calls).toEqual([
    {
      command: "agent_documents_remove",
      args: {
        conversationId: "r-docs",
        name: "factura ñ.pdf",
        token: "b".repeat(64),
      },
    },
    {
      command: "agent_documents_remove",
      args: { conversationId: "r-docs", token: "b".repeat(64) },
    },
    { command: "agent_attachment_policy", args: { token: "b".repeat(64) } },
  ]);
  expect(result.policy).toEqual({
    max_file_bytes: 25,
    extensions: ["pdf", "txt"],
  });
});

// Presentation/transport evidence only: exercise the real Tauri adapter with
// a recording invoke boundary. Backend deletion is tested against real stores.
test("the Tauri session forwards archive and delete, including refusals", async ({
  page,
}) => {
  await page.goto("/scenarios.html");
  const result = await page.evaluate(async () => {
    const calls: { command: string; args: unknown }[] = [];
    let fail = false;
    Object.assign(window, {
      __CADRUMO_SHELL__: { token: "a".repeat(64) },
      __TAURI_INTERNALS__: {
        async invoke(command: string, args: unknown) {
          calls.push({ command, args });
          if (fail) throw { code: "agent_conversation_delete_incomplete" };
          return null;
        },
      },
    });
    const modulePath = "/src/shell/tauriHost.ts";
    const { tauriHost } = (await import(
      modulePath
    )) as typeof import("../../src/shell/tauriHost");
    const session = tauriHost().agentSession!;
    await session.archive!("r-archive");
    await session.delete!("r-delete");
    fail = true;
    let refusal: unknown;
    try {
      await session.delete!("r-partial");
    } catch (error) {
      refusal = error;
    }
    return { calls, refusal };
  });
  expect(result.calls).toEqual([
    {
      command: "agent_conversation_archive",
      args: { conversationId: "r-archive", token: "a".repeat(64) },
    },
    {
      command: "agent_conversation_delete",
      args: { conversationId: "r-delete", token: "a".repeat(64) },
    },
    {
      command: "agent_conversation_delete",
      args: { conversationId: "r-partial", token: "a".repeat(64) },
    },
  ]);
  expect(result.refusal).toEqual({
    code: "agent_conversation_delete_incomplete",
  });
});
