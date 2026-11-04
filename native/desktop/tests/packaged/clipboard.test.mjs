import assert from "node:assert/strict";
import test from "node:test";
import { preserveTextClipboard } from "./clipboard.mjs";
import { DesktopInput } from "./os.mjs";

test("restores after an early UI exception before host and input cleanup", async () => {
  const events = [];
  let clipboard = "original private text";
  const restore = await preserveTextClipboard({
    read: async () => clipboard,
    registerSecret: (text) => events.push(["secret", text]),
    write: async (text) => {
      events.push("restore");
      clipboard = text;
    },
  });
  await assert.rejects(async () => {
    try {
      clipboard = "temporary test text";
      throw new Error("obsolete UI selector");
    } finally {
      try {
        await restore();
      } finally {
        events.push("host cleanup", "input cleanup");
      }
    }
  }, /obsolete UI selector/);
  assert.equal(clipboard, "original private text");
  assert.deepEqual(events, [
    ["secret", "original private text"],
    "restore",
    "host cleanup",
    "input cleanup",
  ]);
});

for (const original of ["", "Español 日本語 🧾\r\nsecond line\nthird line"]) {
  test(`round trips ${original === "" ? "empty" : "Unicode multiline"} text once`, async () => {
    const registered = [];
    const written = [];
    const restore = await preserveTextClipboard({
      read: () => original,
      registerSecret: (text) => registered.push(text),
      write: async (text) => written.push(text),
    });
    assert.equal(typeof restore, "function");
    assert.deepEqual(registered, [original]);
    assert.deepEqual(written, []);
    await restore();
    await restore();
    assert.deepEqual(written, [original]);
  });
}

test("capture and registration failures never write or expose secret errors", async () => {
  const secret = "PRIVATE_CLIPBOARD_SENTINEL";
  for (const read of [
    () => {
      throw new Error(secret);
    },
    () => undefined,
    () => null,
    () => 42,
    () => ({ text: secret }),
    () => secret,
  ]) {
    let writes = 0;
    await assert.rejects(
      preserveTextClipboard({
        read,
        write: () => {
          writes += 1;
        },
        registerSecret: () => {
          throw new Error(secret);
        },
      }),
      (error) => {
        assert.equal(error.message, "Clipboard text capture failed");
        assert.equal(error.cause, undefined);
        assert.equal(error.stack.includes(secret), false);
        return true;
      },
    );
    assert.equal(writes, 0);
  }
});

test("failed restoration is visible, permits cleanup and can retry", async () => {
  const secret = "PRIVATE_RESTORE_SENTINEL";
  let attempts = 0;
  let cleaned = false;
  const restore = await preserveTextClipboard({
    read: () => secret,
    registerSecret: () => {},
    write: async (text) => {
      assert.equal(text, secret);
      if (++attempts === 1) throw new Error(secret);
    },
  });
  await assert.rejects(
    async () => {
      try {
        await restore();
      } finally {
        cleaned = true;
      }
    },
    (error) => {
      assert.equal(error.message, "Clipboard text restoration failed");
      assert.equal(error.cause, undefined);
      assert.equal(error.stack.includes(secret), false);
      return true;
    },
  );
  assert.equal(cleaned, true);
  await restore();
  await restore();
  assert.equal(attempts, 2);
});

test("concurrent restorations share one write", async () => {
  let finish;
  let writes = 0;
  const restore = await preserveTextClipboard({
    read: () => "private",
    registerSecret: () => {},
    write: () => {
      writes += 1;
      return new Promise((resolve) => {
        finish = resolve;
      });
    },
  });
  const first = restore();
  const second = restore();
  assert.equal(writes, 1);
  finish();
  await Promise.all([first, second]);
  await restore();
  assert.equal(writes, 1);
});

test("native write sends Unicode and empty text only through the stdin JSON request", async () => {
  for (const text of ["", "é 🧾\nline\r\nend"]) {
    const transport = {
      next: 0,
      pending: new Map(),
      child: {
        stdin: {
          write(line) {
            assert.equal(line.split("\n").length, 2);
            const request = JSON.parse(line);
            assert.deepEqual(request, { id: 1, op: "clipboard-write", text });
            transport.pending.get(request.id).resolve({ matches: true });
            transport.pending.delete(request.id);
          },
        },
      },
      request: DesktopInput.prototype.request,
    };
    await DesktopInput.prototype.clipboardWrite.call(transport, text);
    assert.equal(transport.pending.size, 0);
  }
});

test("native write requires verified equality and hides transport errors", async () => {
  for (const result of [
    undefined,
    {},
    { matches: false },
    { matches: "true" },
  ]) {
    await assert.rejects(
      DesktopInput.prototype.clipboardWrite.call(
        { request: async () => result },
        "private",
      ),
      { message: "Clipboard text write failed" },
    );
  }
  await assert.rejects(
    DesktopInput.prototype.clipboardWrite.call(
      {
        request: async () => {
          throw new Error("PRIVATE_TRANSPORT_SENTINEL");
        },
      },
      "private",
    ),
    (error) => {
      assert.equal(error.message, "Clipboard text write failed");
      assert.equal(error.stack.includes("PRIVATE_TRANSPORT_SENTINEL"), false);
      assert.equal(error.cause, undefined);
      return true;
    },
  );
  let requested = false;
  await assert.rejects(
    DesktopInput.prototype.clipboardWrite.call(
      {
        request: () => {
          requested = true;
        },
      },
      null,
    ),
    { message: "Clipboard text write failed" },
  );
  assert.equal(requested, false);
});
