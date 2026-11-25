/** Capture text before any clipboard mutation; keep it only in the restore closure. */
export async function preserveTextClipboard({ read, write, registerSecret }) {
  let original;
  try {
    if (
      typeof read !== "function" ||
      typeof write !== "function" ||
      typeof registerSecret !== "function"
    )
      throw new Error();
    original = await read();
    if (typeof original !== "string") throw new Error();
    await registerSecret(original);
  } catch {
    throw new Error("Clipboard text capture failed");
  }

  let restored = false;
  let pending;
  return async function restore() {
    if (restored) return;
    if (!pending) {
      pending = (async () => {
        try {
          await write(original);
          restored = true;
          original = undefined;
        } catch {
          throw new Error("Clipboard text restoration failed");
        }
      })();
    }
    try {
      await pending;
    } finally {
      pending = undefined;
    }
  };
}
