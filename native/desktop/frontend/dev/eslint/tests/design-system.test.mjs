import assert from "node:assert/strict";
import { test } from "node:test";
import { ESLint } from "eslint";

const lint = new ESLint();
async function violations(source, filePath = "src/components/Fixture.tsx") {
  const [result] = await lint.lintText(source, { filePath });
  assert.equal(result.fatalErrorCount, 0);
  return result.messages.filter((message) =>
    message.ruleId?.startsWith("design-system/"),
  );
}

test("rejects literals in classes, variants and templates", async () => {
  for (const value of [
    '"w-[37px]"',
    '"@max-[4.5rem]:hidden"',
    '"grid-cols-[8em_1fr]"',
    '"bg-[#abc123]"',
    '"hover:text-red-500"',
    '"z-50"',
    '"duration-150"',
    "`p-2 max-w-[19rem]`",
  ]) {
    const found = await violations(`export const variant = ${value};`);
    assert.ok(
      found.some((item) => item.ruleId === "design-system/token-styles"),
    );
  }
});

test("rejects inline design dimensions and colors", async () => {
  for (const value of [
    'width: "37px"',
    "width: 37",
    'color: "#abc123"',
    'color: "red"',
  ]) {
    const found = await violations(
      `export const Fixture = () => <div style={{ ${value} }} />;`,
    );
    assert.ok(
      found.some((item) => item.ruleId === "design-system/token-styles"),
    );
  }
  const styleObject = await violations(
    'export const style = { padding: "3rem" };',
  );
  assert.ok(
    styleObject.some((item) => item.ruleId === "design-system/token-styles"),
  );
});

test("admits tokens, computed geometry, structural grids and system colors", async () => {
  assert.deepEqual(
    await violations(`export const Fixture = ({ column }: { column: number }) => (
      <div
        className="calendar-month-grid p-4 text-sm bg-card w-dialog z-(--layer-modal) max-w-[calc(100%-var(--overlay-gutter))] grid-cols-[auto_1fr] forced-colors:bg-[Highlight]"
        style={{ gridColumn: column, width: "var(--spacing-field)" }}
      />
    );`),
    [],
  );
});

test("enforces product and primitive file naming", async () => {
  for (const file of [
    "src/components/bad-name.tsx",
    "src/components/ui/BadName.tsx",
    "src/components/calendar/calendarMonth.tsx",
  ]) {
    const found = await violations(
      "export const Fixture = () => <div />;",
      file,
    );
    assert.ok(
      found.some((item) => item.ruleId === "design-system/component-names"),
    );
  }
  for (const file of [
    "src/components/calendar/CalendarMonth.tsx",
    "src/components/SignIn.stories.tsx",
    "src/components/ui/icon-button.tsx",
    "src/dev/main.tsx",
  ])
    assert.deepEqual(
      await violations("export const Fixture = () => <div />;", file),
      [],
    );
});

test("primitives cannot reach product, shell or host layers", async () => {
  for (const source of [
    'import { Account } from "@/components/SignIn";',
    'import { Account } from "../SignIn";',
    'import { useHostLogs } from "@/shell/useHostLogs";',
    'import { invoke } from "@tauri-apps/api/core";',
  ]) {
    const [result] = await lint.lintText(source, {
      filePath: "src/components/ui/fixture.tsx",
    });
    assert.ok(
      result.messages.some((item) => item.ruleId === "no-restricted-imports"),
    );
  }
});

test("components cannot depend on composition or forwarding modules", async () => {
  for (const source of [
    'import { App } from "../App";',
    'export * from "./SignIn";',
    'export { Account } from "./SignIn";',
  ]) {
    const [result] = await lint.lintText(source, {
      filePath: "src/components/Fixture.tsx",
    });
    assert.ok(
      result.messages.some((item) =>
        ["no-restricted-imports", "no-restricted-syntax"].includes(item.ruleId),
      ),
    );
  }
});

test("shared helpers cannot depend on presentation, shell, IPC or host layers", async () => {
  for (const source of [
    'import { App } from "../App";',
    'import { useHostLogs } from "../shell/useHostLogs";',
    'import { entryKey } from "@/shell/calendarEntries";',
    'import { Button } from "@/components/ui/button";',
    'import type { LogRecord } from "../ipc/contract";',
    'import { invoke } from "@tauri-apps/api/core";',
  ]) {
    const [result] = await lint.lintText(source, {
      filePath: "src/shared/fixture.ts",
    });
    assert.ok(
      result.messages.some((item) => item.ruleId === "no-restricted-imports"),
    );
  }
  const [result] = await lint.lintText('import { isoDay } from "./dates";', {
    filePath: "src/shared/fixture.ts",
  });
  assert.equal(
    result.messages.filter((item) => item.ruleId === "no-restricted-imports")
      .length,
    0,
  );
});
