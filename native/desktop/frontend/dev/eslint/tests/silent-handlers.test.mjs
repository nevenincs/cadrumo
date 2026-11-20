import assert from "node:assert/strict";
import { test } from "node:test";
import { ESLint } from "eslint";

const lint = new ESLint();
const MESSAGE = "An event handler must not drop a failure";

async function dropped(handler) {
  const [result] = await lint.lintText(
    `export function Fixture({ port }: { port: { cancel(): Promise<void> } }) {\n  return <button onClick={${handler}}>x</button>;\n}\n`,
    { filePath: "src/components/Fixture.tsx" },
  );
  assert.equal(result.fatalErrorCount, 0);
  return result.messages.filter((m) => m.message.startsWith(MESSAGE)).length;
}

test("a handler that drops its failure is refused", async () => {
  for (const handler of [
    "() => void port.cancel().catch(() => undefined)",
    "() => void port.cancel().catch(() => null)",
    "() => void port.cancel().catch(() => {})",
    "async () => { try { await port.cancel(); } catch {} }",
    "async () => { try { await port.cancel(); } catch (error) { /* ignored */ } }",
  ])
    assert.equal(await dropped(handler), 1, handler);
});

test("a handler that shows its failure is admitted", async () => {
  for (const handler of [
    "() => void port.cancel().catch((error) => say(String(error)))",
    "async () => { try { await port.cancel(); } catch { setFailed(true); } }",
  ])
    assert.equal(await dropped(handler), 0, handler);
});
