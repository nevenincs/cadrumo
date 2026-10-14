import { expect, test } from "@playwright/test";
import {
  FIXTURE_RUNS,
  SEED_DEPTH,
  conversationRecords,
  messageDigest,
  seeded,
  type FixtureMessage,
  type FixtureRun,
} from "../src/dev/fixtures/agent";
import {
  NO_TURNS,
  applyStreamEvent,
  resubscribeDelay,
  withHistory,
  withSent,
  type LiveTurns,
} from "../src/shell/agentLive";
import type { AgentStreamEvent } from "../src/shell/agentSession";
import {
  conversationGroups,
  replyFacts,
  transcriptItems,
  type AgentConversationRecord,
  type AgentTurnRecord,
} from "../src/shell/agentViews";
import { conditionWords, toolKindWords } from "../src/shell/agentWords";
import { label } from "./support/strings";

// What the column does with a conversation as cadrumo-agent serves it: the
// stream's text applied by sequence, a lost stream recovered, what the person
// sent shown until the history has it, and every state of a run worded. The
// expected values are written out here, from the agent's contract and from the
// column's words, and not taken from the code under test.

const t = (key: string, values?: Record<string, string | number>) =>
  label(key, values);
const NOW = new Date("2026-10-13T12:00:00Z");

const text = (
  reply_id: string,
  message_id: string,
  sequence: number,
  delta: string,
): AgentStreamEvent => ({
  type: "text",
  reply_id,
  message_id,
  sequence,
  delta,
});

/** `events` applied one after another, from `from`. */
const play = (events: AgentStreamEvent[], from: LiveTurns = NO_TURNS) =>
  events.reduce((live, event) => applyStreamEvent(live, event).live, from);

const agentTexts = (live: LiveTurns) =>
  live.turns.flatMap((record) =>
    record.kind === "agent" ? [record.text] : [],
  );

const kinds = (turns: readonly AgentTurnRecord[]) =>
  turns.map((record) => record.kind);

const person = (
  reply_id: string,
  words: string,
  id = messageDigest("user", words),
): AgentTurnRecord => ({
  kind: "person",
  id,
  reply_id,
  text: words,
  sent_at: null,
});
const reply = (
  id: string,
  status: Extract<AgentTurnRecord, { kind: "reply" }>["status"],
  more: Partial<Extract<AgentTurnRecord, { kind: "reply" }>> = {},
): AgentTurnRecord => ({ kind: "reply", id, status, ...more });

const nothingPending = { questionnaires: [], approvals: [] };

test.describe("the text of a reply, as the stream sends it", () => {
  test("is applied in the order of its sequence, and a duplicate is dropped", () => {
    const live = play([
      text("r1", "m1", 1, "Ho"),
      text("r1", "m1", 2, "la"),
      // The same frame again, and an earlier one: both have been applied.
      text("r1", "m1", 2, "la"),
      text("r1", "m1", 3, " mundo"),
      text("r1", "m1", 1, "Ho"),
    ]);
    expect(agentTexts(live)).toEqual(["Hola mundo"]);
    expect(live.applied).toEqual({ r1: 3 });
  });

  test("keeps one message across a tool call, and puts the call before it", () => {
    const call = (status: "pending" | "in_progress" | "completed") =>
      ({
        type: "tool",
        reply_id: "r1",
        tool: {
          id: "t1",
          title: "ledger_list",
          tool_kind: "read",
          status,
        },
      }) satisfies AgentStreamEvent;
    const live = play([
      text("r1", "m1", 1, "Antes."),
      call("pending"),
      call("in_progress"),
      call("completed"),
      text("r1", "m1", 5, "\n\nDespués."),
    ]);
    // The agent keeps no position of a call among the text.
    expect(kinds(live.turns)).toEqual(["tool", "agent", "reply"]);
    expect(agentTexts(live)).toEqual(["Antes.\n\nDespués."]);
  });

  test("of two messages of one reply is two messages", () => {
    const live = play([
      text("r1", "m1", 1, "Necesito un dato."),
      text("r1", "m2", 2, "Con eso basta."),
    ]);
    expect(agentTexts(live)).toEqual(["Necesito un dato.", "Con eso basta."]);
  });

  test("of a message the history holds is not added to it", () => {
    const held = withHistory(
      NO_TURNS,
      [
        person("r1", "Hola"),
        { kind: "agent", id: "m1", reply_id: "r1", text: "Hecho." },
        reply("r1", "completed"),
      ],
      nothingPending,
    );
    const live = play([text("r1", "m1", 1, "Hecho.")], held);
    expect(agentTexts(live)).toEqual(["Hecho."]);
  });

  test("of a reply the history does not know starts a reply that is running", () => {
    const live = play([text("r9", "m1", 1, "Hola")]);
    expect(live.turns.at(-1)).toEqual({
      kind: "reply",
      id: "r9",
      status: "running",
    });
  });
});

test.describe("a lost stream", () => {
  test("is recovered by reading the history again and watching anew, and the replay rebuilds the text", () => {
    const written = play([
      text("r1", "m1", 1, "ab"),
      text("r1", "m1", 2, "cd"),
    ]);
    expect(agentTexts(written)).toEqual(["abcd"]);

    const step = applyStreamEvent(written, { type: "lost", reply_id: "r1" });
    expect(step.reread).toBe(true);
    expect(step.resubscribe).toBe(true);
    // What was applied is forgotten: the replay begins at the run's first
    // frame.
    expect(step.live.applied).toEqual({});

    // The reply in progress is not in the history.
    const read = withHistory(
      step.live,
      [person("r1", "Hola"), reply("r1", "running")],
      nothingPending,
    );
    expect(agentTexts(read)).toEqual([]);

    // The new watch is replayed the run from its first frame, and goes on.
    const replayed = play(
      [
        text("r1", "m1", 1, "ab"),
        text("r1", "m1", 2, "cd"),
        text("r1", "m1", 3, "ef"),
      ],
      read,
    );
    expect(agentTexts(replayed)).toEqual(["abcdef"]);
  });

  test("is watched anew at once the first time, and then after a growing wait", () => {
    expect([0, 1, 2, 3, 4, 5, 6, 7, 20].map(resubscribeDelay)).toEqual([
      0, 0, 1_000, 2_000, 4_000, 8_000, 16_000, 30_000, 30_000,
    ]);
  });
});

test.describe("a tool call", () => {
  const call = (status: "pending" | "in_progress" | "completed" | "failed") =>
    ({
      type: "tool",
      reply_id: "r1",
      tool: { id: "t1", title: "ledger_list", tool_kind: "read", status },
    }) satisfies AgentStreamEvent;
  const states = (live: LiveTurns) =>
    live.turns.flatMap((record) =>
      record.kind === "tool" ? [record.status] : [],
    );

  test("does not go back to an earlier state", () => {
    expect(
      states(play([call("pending"), call("completed"), call("in_progress")])),
    ).toEqual(["completed"]);
    expect(states(play([call("failed"), call("pending")]))).toEqual(["failed"]);
  });

  test("that failed is shown as failed, with the tool's own name and kind", () => {
    const live = play([call("pending"), call("in_progress"), call("failed")]);
    const items = transcriptItems(live.turns, "en", t, NOW);
    expect(items.filter((item) => item.kind === "tool")).toEqual([
      {
        kind: "tool",
        id: "tool:r1:t1",
        label: "ledger_list",
        state: "failed",
        detail: "Reads",
      },
    ]);
  });

  test("is worded by cadrumo-agent's ten kinds, one word each", () => {
    const words = {
      read: "Reads",
      edit: "Edits",
      delete: "Deletes",
      move: "Moves",
      search: "Searches",
      execute: "Runs",
      think: "Thinks",
      fetch: "Fetches",
      switch_mode: "Switches mode",
      other: "Other",
    } as const;
    for (const [kind, expected] of Object.entries(words))
      expect(toolKindWords(t, kind as keyof typeof words)).toBe(expected);
  });
});

test.describe("a run, in words", () => {
  test("that failed before the agent wrote has no message, and says why from its state", () => {
    const items = transcriptItems(
      [
        person("r1", "Calcula el 130."),
        reply("r1", "failed", {
          provider_condition: "throttled",
          failure_reason: "Rate limit reached.",
        }),
      ],
      "en",
      t,
      NOW,
    );
    expect(items.map((item) => item.kind)).toEqual(["person", "agent"]);
    expect(items[1]).toEqual({
      kind: "agent",
      id: "reply:r1",
      text: "",
      state: "failed",
      failureReason: "The provider is limiting requests: Rate limit reached.",
    });
  });

  test("that failed after the agent wrote says why on its last message", () => {
    const items = transcriptItems(
      [
        person("r1", "Hola"),
        { kind: "agent", id: "m1", reply_id: "r1", text: "Empiezo" },
        reply("r1", "failed", { provider_condition: "network_unreachable" }),
      ],
      "en",
      t,
      NOW,
    );
    expect(items.at(-1)).toMatchObject({
      kind: "agent",
      text: "Empiezo",
      state: "failed",
      failureReason: "The provider can't be reached",
    });
    // No second item for the same reply.
    expect(items).toHaveLength(2);
  });

  test("that is going draws Working, and waiting on the person says so", () => {
    expect(
      transcriptItems(
        [person("r1", "Hola"), reply("r1", "running")],
        "en",
        t,
        NOW,
      ).at(-1),
    ).toMatchObject({ kind: "agent", text: "", state: "working" });
    const waiting = transcriptItems(
      [
        person("r1", "Hola"),
        { kind: "agent", id: "m1", reply_id: "r1", text: "Necesito un dato." },
        reply("r1", "input_required"),
      ],
      "en",
      t,
      NOW,
    ).at(-1);
    expect(waiting).toMatchObject({
      state: "working",
      waitingOnPerson: true,
    });
  });

  test("that was stopped by the person, with nothing written, says it was stopped", () => {
    expect(
      transcriptItems(
        [person("r1", "Hola"), reply("r1", "cancelled")],
        "en",
        t,
        NOW,
      ).at(-1),
    ).toMatchObject({ kind: "agent", text: "", state: "stopped" });
  });

  test("that is stopping, repaired or reconciled draws no indicator in the transcript", () => {
    for (const status of [
      "cancelling",
      "repair_needed",
      "reconciling",
    ] as const) {
      const items = transcriptItems(
        [
          person("r1", "Hola"),
          { kind: "agent", id: "m1", reply_id: "r1", text: "Hecho a medias." },
          reply("r1", status),
        ],
        "en",
        t,
        NOW,
      );
      expect(items.at(-1)).toEqual({
        kind: "agent",
        id: "agent:r1:m1",
        text: "Hecho a medias.",
        state: "complete",
      });
    }
  });

  test("has one word for each provider condition", () => {
    const words = {
      network_unreachable: "The provider can't be reached",
      provider_overloaded: "The provider is overloaded",
      unauthenticated: "Not authenticated with the provider",
      throttled: "The provider is limiting requests",
      usage_exhausted: "Usage limit reached",
      credits_exhausted: "Out of credits",
      budget_exhausted: "Budget used up",
      invalid_request: "The provider rejected the request",
      unknown: "Unknown cause",
    } as const;
    for (const [condition, expected] of Object.entries(words))
      expect(conditionWords(t, condition as keyof typeof words)).toBe(expected);
  });
});

test.describe("what the person sent, shown until the history has it", () => {
  const sent = (
    live: LiveTurns,
    reply_id: string,
    words: string,
    at: "start" | "end" = "start",
  ) => withSent(live, { reply_id, text: words, at }, NOW);
  const personTexts = (live: LiveTurns) =>
    live.turns.flatMap((record) =>
      record.kind === "person" ? [record.text] : [],
    );
  const local = (live: LiveTurns) =>
    live.turns.filter(
      (record) => record.kind === "person" && record.id.startsWith("local:"),
    );

  test("is replaced by the history's record of it", () => {
    const shown = sent(NO_TURNS, "r1", "Hola");
    expect(personTexts(shown)).toEqual(["Hola"]);
    expect(local(shown)).toHaveLength(1);
    const read = withHistory(
      shown,
      [person("r1", "Hola", "h1"), reply("r1", "running")],
      nothingPending,
    );
    expect(
      read.turns.flatMap((record) =>
        record.kind === "person" ? [record.id] : [],
      ),
    ).toEqual(["h1"]);
    expect(local(read)).toHaveLength(0);
  });

  test("stays while the history does not have it yet", () => {
    const read = withHistory(
      sent(NO_TURNS, "r1", "Hola"),
      [reply("r1", "running")],
      nothingPending,
    );
    expect(personTexts(read)).toEqual(["Hola"]);
    expect(kinds(read.turns)).toEqual(["person", "reply"]);
  });

  test("is told from an identical earlier message by its reply, so that two are two", () => {
    // The history ids are a digest of role and content, so both share one.
    const first = [
      person("r1", "Hola"),
      { kind: "agent", id: "m1", reply_id: "r1", text: "Buenas." } as const,
      reply("r1", "completed"),
    ];
    const held = withHistory(NO_TURNS, first, nothingPending);
    const second = sent(held, "r2", "Hola");
    expect(personTexts(second)).toEqual(["Hola", "Hola"]);

    // The history still has only the first: the second stays on screen.
    const early = withHistory(
      second,
      [...first, reply("r2", "running")],
      nothingPending,
    );
    expect(personTexts(early)).toEqual(["Hola", "Hola"]);
    expect(local(early)).toHaveLength(1);

    // And once it has both, each stands for one message.
    const both = withHistory(
      early,
      [...first, person("r2", "Hola"), reply("r2", "running")],
      nothingPending,
    );
    expect(personTexts(both)).toEqual(["Hola", "Hola"]);
    expect(local(both)).toHaveLength(0);
    const items = transcriptItems(both.turns, "en", t, NOW);
    const ids = items.map((item) => item.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  test("takes, within one reply, the next message the history lists and no earlier one took", () => {
    // An answer in words that says what the first message said.
    const shown = sent(sent(NO_TURNS, "r1", "Sí"), "r1", "Sí", "end");
    expect(personTexts(shown)).toEqual(["Sí", "Sí"]);
    const afterFirst = withHistory(
      shown,
      [person("r1", "Sí"), reply("r1", "running")],
      nothingPending,
    );
    expect(personTexts(afterFirst)).toEqual(["Sí", "Sí"]);
    expect(local(afterFirst)).toHaveLength(1);
    const afterBoth = withHistory(
      afterFirst,
      [person("r1", "Sí"), person("r1", "Sí"), reply("r1", "running")],
      nothingPending,
    );
    expect(local(afterBoth)).toHaveLength(0);
    expect(personTexts(afterBoth)).toEqual(["Sí", "Sí"]);
    // Two messages of one reply, one id between them: each item has its own.
    const ids = transcriptItems(afterBoth.turns, "en", t, NOW)
      .filter((item) => item.kind === "person")
      .map((item) => item.id);
    expect(ids).toEqual([
      `person:r1:${messageDigest("user", "Sí")}`,
      `person:r1:${messageDigest("user", "Sí")}#1`,
    ]);
  });

  test("goes before what the stream already sent of its reply, and a continuation after", () => {
    const streamed = play([text("r2", "m1", 1, "Respuesta.")]);
    const shown = sent(streamed, "r2", "Pregunta");
    expect(kinds(shown.turns)).toEqual(["person", "agent", "reply"]);
    const continued = sent(shown, "r2", "Y esto", "end");
    expect(kinds(continued.turns)).toEqual([
      "person",
      "agent",
      "person",
      "reply",
    ]);
  });

  test("keeps the order it was sent in when the history has none of it", () => {
    const shown = sent(sent(NO_TURNS, "r1", "Uno"), "r2", "Dos");
    const read = withHistory(
      shown,
      [reply("r1", "completed"), reply("r2", "running")],
      nothingPending,
    );
    expect(personTexts(read)).toEqual(["Uno", "Dos"]);
  });
});

test.describe("a conversation composed from its runs", () => {
  const turn = (role: "user" | "assistant", words: string): FixtureMessage => ({
    role,
    text: words,
  });
  const run = (id: string, messages: FixtureMessage[]): FixtureRun => ({
    id,
    status: "completed",
    messages,
    tools: [],
  });
  const wordsOf = (records: readonly AgentTurnRecord[]) =>
    records.flatMap((record) =>
      record.kind === "person" || record.kind === "agent" ? [record.text] : [],
    );

  test("lists each message once: a run that continues another is seeded with its last", () => {
    const first = run("r1", [turn("user", "uno"), turn("assistant", "dos")]);
    const second = run(
      "r2",
      seeded(first.messages, [
        turn("user", "tres"),
        turn("assistant", "cuatro"),
      ]),
    );
    // The agent's checkpoint of the second has four messages beside them.
    expect(second.messages).toHaveLength(4);
    expect(wordsOf(conversationRecords([first, second]))).toEqual([
      "uno",
      "dos",
      "tres",
      "cuatro",
    ]);
  });

  test("seeds no more than twenty, and the third run drops what the second was seeded with", () => {
    const long = Array.from({ length: 30 }, (_, index) =>
      turn(index % 2 === 0 ? "user" : "assistant", `a${index}`),
    );
    const first = run("r1", long);
    const second = run(
      "r2",
      seeded(first.messages, [turn("user", "b0"), turn("assistant", "b1")]),
    );
    expect(second.messages).toHaveLength(SEED_DEPTH + 2);
    const third = run(
      "r3",
      seeded(second.messages, [turn("user", "c0"), turn("assistant", "c1")]),
    );
    expect(third.messages).toHaveLength(SEED_DEPTH + 2);
    expect(wordsOf(conversationRecords([first, second, third]))).toEqual([
      ...long.map((one) => one.text),
      "b0",
      "b1",
      "c0",
      "c1",
    ]);
  });

  test("puts a reply's tool calls before its first agent message and its own record last", () => {
    const records = conversationRecords([
      {
        ...run("r1", [turn("user", "uno"), turn("assistant", "dos")]),
        tools: [
          {
            id: "t1",
            title: "ledger_list",
            tool_kind: "read",
            status: "failed",
          },
        ],
      },
    ]);
    expect(kinds(records)).toEqual(["person", "tool", "agent", "reply"]);
  });

  test("is served for the fixture's own conversations the same way", () => {
    const records = conversationRecords(FIXTURE_RUNS["c-iva-t3"] ?? []);
    expect(
      records.flatMap((record) =>
        record.kind === "person" ? [record.text] : [],
      ),
    ).toEqual([
      "Aquí van las facturas y el extracto del trimestre. ¿Me preparas el 303?",
      "¿Y qué parte del soportado es deducible?",
    ]);
    expect(records.filter((record) => record.kind === "reply")).toHaveLength(2);
  });
});

test.describe("what a conversation's replies served about themselves", () => {
  const ran = {
    provider: "alpha",
    transport: "api",
    provider_display_name: "Example Alpha",
    model: "m",
    model_display_name: "Fixture Deep",
    effort: "high",
  } as const;

  test("is what the newest ran with, and the tokens of them all", () => {
    const facts = replyFacts(
      [
        reply("r1", "completed", {
          selection: {
            ...ran,
            model_display_name: "Fixture Quick",
            effort: "low",
          },
          usage: { input_tokens: 1_000, output_tokens: 200 },
        }),
        reply("r2", "completed", {
          selection: ran,
          usage: { input_tokens: 2_500, output_tokens: 300 },
        }),
      ],
      "en",
      t,
    );
    expect(facts).toEqual({
      ranWith: "Ran with: Example Alpha, Fixture Deep, High",
      usage: "Tokens: 3,500 in, 500 out",
    });
  });

  test("is nothing where the agent served nothing", () => {
    expect(replyFacts([reply("r1", "completed")], "en", t)).toEqual({
      ranWith: null,
      usage: null,
    });
  });

  test("names the provider and the model by their ids where the agent gave no display names", () => {
    const facts = replyFacts(
      [
        reply("r1", "completed", {
          selection: {
            provider: "gateway",
            transport: "cli",
            model: "gateway-x",
          },
        }),
      ],
      "en",
      t,
    );
    expect(facts.ranWith).toBe("Ran with: gateway, gateway-x");
  });
});

test.describe("the conversations the history lists", () => {
  const record = (
    id: string,
    title: string,
    archived = false,
  ): AgentConversationRecord => ({
    id,
    title,
    last_active_at: "2026-10-13T09:00:00Z",
    archived,
  });

  test("name one whose first run has no title as the column says it is not available yet", () => {
    const groups = conversationGroups(
      [
        record("a", "Con título"),
        record("b", ""),
        record("c", "Archivada", true),
      ],
      {
        locale: "en",
        archived: false,
        currentId: "b",
        untitled: label("desktop.agent.unavailable"),
        now: NOW,
      },
    );
    const rows = groups.flatMap((group) => group.conversations);
    expect(rows.map((row) => row.title).sort()).toEqual([
      "Con título",
      "Not available yet",
    ]);
    expect(rows.find((row) => row.id === "b")?.current).toBe(true);
    // Cadrumo's custody serves no documents, so none is counted.
    expect(rows.every((row) => row.documentCount === 0)).toBe(true);
  });
});
