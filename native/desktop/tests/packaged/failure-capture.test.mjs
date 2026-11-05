import assert from "node:assert/strict";
import { describe, test } from "node:test";

import {
  CAPTURED,
  CAPTURE_FAILED,
  PAGE_CLOSED,
  capturePageEvidence,
  captureProvisioningFailure,
  pageGone,
} from "./failure-capture.mjs";

function recorderOf() {
  const written = new Map();
  return {
    written,
    evidence(name, value) {
      written.set(name, JSON.parse(JSON.stringify(value)));
    },
  };
}

const CLOSED = "page.evaluate: Target page, context or browser has been closed";
const closed = () => Promise.reject(new Error("page.evaluate: Target closed"));

describe("failure evidence capture", () => {
  test("recognises the closed-page messages", () => {
    assert.ok(pageGone(new Error("page.evaluate: Target closed")));
    assert.ok(pageGone(new Error(CLOSED)));
    assert.ok(pageGone(new Error("Browser has been closed")));
    assert.ok(
      !pageGone(new Error("locator.waitFor: Timeout 30000ms exceeded.")),
    );
  });

  test("a live page is captured under its name", async () => {
    const results = recorderOf();
    const status = await capturePageEvidence(
      results,
      "x-ui.json",
      async () => ({
        a: 1,
      }),
    );
    assert.equal(status, CAPTURED);
    assert.deepEqual(results.written.get("x-ui.json"), { a: 1 });
  });

  test("a closed page records page_closed and does not throw", async () => {
    const results = recorderOf();
    const status = await capturePageEvidence(results, "x-ui.json", () => {
      throw new Error(CLOSED);
    });
    assert.equal(status, PAGE_CLOSED);
    assert.equal(results.written.get("x-ui.json").status, PAGE_CLOSED);
  });

  test("Target closed from every session read is page_closed", async () => {
    const results = recorderOf();
    const session = { shell: closed, call: closed, docs: closed };
    const statuses = await captureProvisioningFailure(
      session,
      results,
      "provisioning-3-x",
    );
    assert.deepEqual(statuses, {
      "provisioning-3-x-ui.json": PAGE_CLOSED,
      "provisioning-3-x-diagnostics.json": PAGE_CLOSED,
      "provisioning-3-x-models.json": PAGE_CLOSED,
    });
    assert.equal(results.written.size, 3);
  });

  test("a live fake session is captured in full", async () => {
    const results = recorderOf();
    const session = {
      shell: async () => ({ language: "es" }),
      call: async (command) => ({ ok: true, command }),
    };
    const statuses = await captureProvisioningFailure(
      session,
      results,
      "provisioning-3-x",
    );
    assert.equal(Object.keys(statuses).length, 3);
    assert.ok(Object.values(statuses).every((s) => s === CAPTURED));
    assert.equal(
      results.written.get("provisioning-3-x-models.json").command,
      "agent_local_models",
    );
  });

  test("another read error is recorded as capture_failed, never thrown", async () => {
    const results = recorderOf();
    const status = await capturePageEvidence(results, "y.json", () => {
      throw new Error("No documentation frame");
    });
    assert.equal(status, CAPTURE_FAILED);
    assert.equal(
      results.written.get("y.json").reason,
      "No documentation frame",
    );
  });

  test("an unwritable evidence store does not throw", async () => {
    const results = {
      evidence() {
        throw new Error("disk full");
      },
    };
    assert.equal(
      await capturePageEvidence(results, "z.json", async () => 1),
      CAPTURE_FAILED,
    );
  });

  test("no session captures nothing", async () => {
    assert.deepEqual(
      await captureProvisioningFailure(null, recorderOf(), "i"),
      {},
    );
  });
});
