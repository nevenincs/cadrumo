import { expect, test } from "@playwright/test";
import {
  applyStreamEvent,
  coalesceStreamEvents,
  NO_TURNS,
} from "../src/shell/agentLive";
import {
  createTranscriptProjection,
  type AgentTurnRecord,
} from "../src/shell/agentViews";
import type { AgentStreamEvent } from "../src/shell/agentSession";
import { label } from "./support/strings";

const now = new Date("2026-10-20T12:00:00Z");
const t = (key: string, values?: Record<string, string | number>) =>
  label(key, values);

test("a burst of text becomes one update without replaying duplicate chunks", () => {
  const events: AgentStreamEvent[] = Array.from({ length: 5_000 }, (_, i) => ({
    type: "text",
    reply_id: "r1",
    message_id: "m1",
    sequence: i + 1,
    delta: "x",
  }));
  const merged = coalesceStreamEvents(events, { r1: 100 });
  expect(merged).toEqual([
    {
      type: "text",
      reply_id: "r1",
      message_id: "m1",
      sequence: 5_000,
      delta: "x".repeat(4_900),
    },
  ]);
  expect(
    coalesceStreamEvents([events[3]!, events[2]!, events[4]!], {}),
  ).toEqual([
    {
      type: "text",
      reply_id: "r1",
      message_id: "m1",
      sequence: 5,
      delta: "xx",
    },
  ]);
});

test("batched thoughts, text, decisions and recovery keep their stream order", () => {
  const events: AgentStreamEvent[] = [
    {
      type: "text",
      reply_id: "r1",
      message_id: "m1",
      sequence: 1,
      delta: "First ",
    },
    {
      type: "text",
      reply_id: "r1",
      message_id: "m1",
      sequence: 2,
      delta: "answer",
    },
    {
      type: "thought",
      reply_id: "r1",
      message_id: "t1",
      sequence: 3,
      delta: "Checking",
    },
    { type: "text", reply_id: "r1", message_id: "m1", sequence: 4, delta: "." },
    { type: "settled", reply_id: "r1", status: "completed" },
  ];
  const apply = (stream: AgentStreamEvent[]) =>
    stream.reduce(
      (live, event) => applyStreamEvent(live, event).live,
      NO_TURNS,
    );
  expect(apply(coalesceStreamEvents(events, {}))).toEqual(apply(events));
  const recovery: AgentStreamEvent[] = [
    ...events,
    { type: "lost" },
    events[0]!,
  ];
  expect(apply(coalesceStreamEvents(recovery, {}))).toEqual(apply(recovery));
});

test("streaming changes only the active row in a long transcript", () => {
  const records: AgentTurnRecord[] = Array.from({ length: 1_000 }, (_, i) => ({
    kind: "agent",
    id: `m${i}`,
    reply_id: `r${i}`,
    text: `Completed ${i}`,
  }));
  const project = createTranscriptProjection();
  const before = project(records, "en", t, now);
  const next: AgentTurnRecord[] = [
    ...records,
    {
      kind: "agent",
      id: "current",
      reply_id: "current",
      text: "Writing",
    },
  ];
  const during = project(next, "en", t, now);
  expect(during.slice(0, 1_000).every((item, i) => item === before[i])).toBe(
    true,
  );
  next[next.length - 1] = {
    kind: "agent",
    id: "current",
    reply_id: "current",
    text: "Writing more",
  };
  const after = project(next, "en", t, now);
  expect(after.slice(0, 1_000).every((item, i) => item === during[i])).toBe(
    true,
  );
  expect(after.at(-1)).toMatchObject({ text: "Writing more" });
  expect(after.at(-1)).not.toBe(during.at(-1));
});

test("cached rows follow reply state, thoughts, locale, day and duplicate occurrence", () => {
  const project = createTranscriptProjection();
  const person: AgentTurnRecord = {
    kind: "person",
    id: "same",
    reply_id: "r1",
    text: "Hello",
    sent_at: now.toISOString(),
  };
  const reply: AgentTurnRecord = { kind: "reply", id: "r1", status: "running" };
  const message: AgentTurnRecord = {
    kind: "agent",
    id: "m1",
    reply_id: "r1",
    text: "Hello back",
  };
  const waiting = project([person, reply], "en", t, now);
  expect(waiting.at(-1)).toMatchObject({ id: "reply:r1", state: "working" });
  const writing = project([person, message, reply], "en", t, now);
  expect(writing).toHaveLength(2);
  expect(writing[0]).toBe(waiting[0]);
  expect(writing[1]).toMatchObject({ id: "agent:r1:m1", state: "working" });
  const done: AgentTurnRecord[] = [
    person,
    person,
    message,
    { ...reply, status: "completed" },
  ];
  const finished = project(done, "en", t, now);
  expect(finished.map((item) => item.id)).toEqual([
    "person:r1:same",
    "person:r1:same#1",
    "agent:r1:m1",
  ]);
  expect(finished.at(-1)).toMatchObject({ state: "complete" });
  const thought: AgentTurnRecord = {
    kind: "thought",
    id: "t1",
    reply_id: "r1",
    text: "Checked",
  };
  expect(project([...done, thought], "en", t, now).at(-1)).toMatchObject({
    thinking: "Checked",
  });
  const spanish = project(done, "es", t, now);
  expect(spanish[0]).not.toBe(finished[0]);
  const tomorrow = project(done, "es", t, new Date("2026-10-21T12:00:00Z"));
  expect(tomorrow[0]).not.toBe(spanish[0]);
  expect(tomorrow[0]).not.toMatchObject({
    sentAtLabel: (spanish[0] as { sentAtLabel: string }).sentAtLabel,
  });
});
