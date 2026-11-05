import { expect, test } from "@playwright/test";
import type {
  AgentServiceStatus,
  AgentSession,
} from "../src/shell/agentSession";
import { watchStatus } from "../src/shell/agentLive";

// One host watch of the agent's status for every reader of a session. The
// stand-in host keeps a single listener, as the desktop host does: a
// subscription replaces the earlier one, sends the current status at once,
// and an unsubscription ends only the listener it made.

const STARTING: AgentServiceStatus = { state: "starting" };
const READY: AgentServiceStatus = { state: "ready", agent_version: "1.0.0" };

function host(current: AgentServiceStatus = STARTING) {
  const state = {
    current,
    listener: null as ((status: AgentServiceStatus) => void) | null,
    subscriptions: 0,
    unsubscriptions: 0,
    refuse: false,
  };
  const session = {
    observeStatus(listener: (status: AgentServiceStatus) => void) {
      state.subscriptions += 1;
      if (state.refuse) return Promise.reject(new Error("refused"));
      state.listener = listener;
      listener(state.current);
      return Promise.resolve(() => {
        state.unsubscriptions += 1;
        if (state.listener === listener) state.listener = null;
      });
    },
  } as unknown as AgentSession;
  const publish = (next: AgentServiceStatus) => {
    state.current = next;
    state.listener?.(next);
  };
  return { state, session, publish };
}

const heard = () => {
  const seen: AgentServiceStatus[] = [];
  return {
    seen,
    listener: (status: AgentServiceStatus) => void seen.push(status),
  };
};

test("every reader hears each change although the host keeps one listener", async () => {
  const { state, session, publish } = host();
  const first = heard();
  const second = heard();
  await watchStatus(session, first.listener);
  await watchStatus(session, second.listener);
  publish(READY);
  expect(first.seen.at(-1)).toEqual(READY);
  expect(second.seen.at(-1)).toEqual(READY);
  expect(state.subscriptions).toBe(1);
});

test("a reader that joins later hears the last status at once, without another host subscription", async () => {
  const { state, session, publish } = host();
  const first = heard();
  await watchStatus(session, first.listener);
  publish(READY);
  const late = heard();
  await watchStatus(session, late.listener);
  expect(late.seen).toEqual([READY]);
  expect(state.subscriptions).toBe(1);
});

test("the host is unsubscribed only when the last reader leaves", async () => {
  const { state, session } = host();
  const stopFirst = await watchStatus(session, heard().listener);
  const stopSecond = await watchStatus(session, heard().listener);
  stopFirst();
  await Promise.resolve();
  expect(state.unsubscriptions).toBe(0);
  stopSecond();
  await Promise.resolve();
  await Promise.resolve();
  expect(state.unsubscriptions).toBe(1);
  expect(state.listener).toBeNull();
});

test("readers that left hear nothing more", async () => {
  const { session, publish } = host();
  const staying = heard();
  const leaving = heard();
  await watchStatus(session, staying.listener);
  const stop = await watchStatus(session, leaving.listener);
  stop();
  publish(READY);
  expect(staying.seen.at(-1)).toEqual(READY);
  expect(leaving.seen.at(-1)).toEqual(STARTING);
});

test("after every reader left, a new reader gets a fresh subscription and the current status, not the old last one", async () => {
  const { state, session, publish } = host();
  const stop = await watchStatus(session, heard().listener);
  publish(READY);
  stop();
  await Promise.resolve();
  await Promise.resolve();
  state.current = STARTING;
  const next = heard();
  await watchStatus(session, next.listener);
  expect(state.subscriptions).toBe(2);
  expect(next.seen).toEqual([STARTING]);
});

test("a watch the host refused is dropped, so the next reader asks again", async () => {
  const { state, session } = host();
  state.refuse = true;
  await expect(
    watchStatus(session, heard().listener).then((stop) => stop),
  ).resolves.toBeInstanceOf(Function);
  await Promise.resolve();
  await Promise.resolve();
  state.refuse = false;
  const next = heard();
  await watchStatus(session, next.listener);
  expect(state.subscriptions).toBe(2);
  expect(next.seen).toEqual([STARTING]);
});

test("another session has its own subscription", async () => {
  const one = host();
  const two = host(READY);
  const first = heard();
  const second = heard();
  await watchStatus(one.session, first.listener);
  await watchStatus(two.session, second.listener);
  expect(one.state.subscriptions).toBe(1);
  expect(two.state.subscriptions).toBe(1);
  expect(first.seen).toEqual([STARTING]);
  expect(second.seen).toEqual([READY]);
});
