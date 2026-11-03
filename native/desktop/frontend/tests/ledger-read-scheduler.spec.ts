import { expect, test } from "@playwright/test";
import {
  ReadSessionScheduler,
  type ScheduledReadReply,
  type ScheduledReadView,
} from "../src/shell/readSessionScheduler";

type Question = { id: string; caption?: string };
const turn = () => new Promise((resolve) => setTimeout(resolve, 5));
const idle: ScheduledReadView<number> = {
  shown: null,
  current: null,
  updating: false,
  failed: false,
};

function held(pauseMs = 0) {
  const asked: Question[] = [];
  const replies: ((reply: ScheduledReadReply<number>) => void)[] = [];
  const session = new ReadSessionScheduler({
    ask: (request: Question) => {
      asked.push(request);
      return new Promise<ScheduledReadReply<number>>((resolve) =>
        replies.push(resolve),
      );
    },
    // Identity belongs to the owner, rather than to the question's incidental text.
    keyOf: (request) => request.id,
    answer: (result: number) => result,
    present: (view) => view,
    empty: (request) => (request.id === "" ? { answer: 0 } : null),
    initial: idle,
    pauseMs,
  });
  return { session, asked, replies };
}

test("injected identity reuses a settled answer despite incidental question changes", async () => {
  const { session, asked, replies } = held();
  session.want({ id: "one", caption: "before" });
  await turn();
  replies[0]!({ kind: "answer", result: 12 });
  await turn();
  session.want({ id: "one", caption: "after" });
  await turn();
  expect(asked).toHaveLength(1);
  expect(session.snapshot()).toEqual({
    shown: 12,
    current: 12,
    updating: false,
    failed: false,
  });
  session.stop();
});

test("commit ends the typing pause while a stopped timer sends nothing", async () => {
  const { session, asked, replies } = held(10_000);
  session.want({ id: "one" });
  expect(asked).toEqual([]);
  session.commit();
  expect(asked.map((request) => request.id)).toEqual(["one"]);
  replies[0]!({ kind: "answer", result: 1 });
  await turn();
  session.want({ id: "two" });
  session.stop();
  session.commit();
  expect(asked).toHaveLength(1);
});

test("an in-flight reply delivered while stopped is ignored and restarting can ask again", async () => {
  const { session, asked, replies } = held();
  session.want({ id: "one" });
  await turn();
  session.stop();
  replies[0]!({ kind: "answer", result: 1 });
  await turn();
  expect(session.snapshot().current).toBeNull();
  session.start();
  session.want({ id: "one" });
  await turn();
  expect(asked).toHaveLength(2);
  replies[1]!({ kind: "answer", result: 2 });
  await turn();
  expect(session.snapshot().current).toBe(2);
  session.stop();
});

test("an immediate empty answer supersedes an outstanding reply without another read", async () => {
  const { session, asked, replies } = held();
  session.want({ id: "one" });
  await turn();
  session.want({ id: "" });
  expect(session.snapshot()).toEqual({
    shown: 0,
    current: 0,
    updating: false,
    failed: false,
  });
  replies[0]!({ kind: "answer", result: 99 });
  await turn();
  expect(asked).toHaveLength(1);
  expect(session.snapshot().current).toBe(0);
  session.stop();
});

test("a newer failed read clears retained display data and retry sends only once", async () => {
  const { session, asked, replies } = held();
  session.want({ id: "one" });
  await turn();
  replies[0]!({ kind: "answer", result: 1 });
  await turn();
  session.want({ id: "two" });
  expect(session.snapshot()).toEqual({
    shown: 1,
    current: null,
    updating: true,
    failed: false,
  });
  await turn();
  replies[1]!({ kind: "failed" });
  await turn();
  expect(session.snapshot()).toEqual({
    shown: null,
    current: null,
    updating: false,
    failed: true,
  });
  session.retry();
  session.retry();
  expect(asked.map((request) => request.id)).toEqual(["one", "two", "two"]);
  replies[2]!({ kind: "answer", result: 2 });
  await turn();
  expect(session.snapshot().current).toBe(2);
  session.stop();
});
