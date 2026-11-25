import { expect, test, type Page } from "@playwright/test";
import { label } from "../support/strings";

// The scenario host records the protocol inputs. CDP drives Chromium's native
// editor/IME machinery against the same editable sink the packaged webview
// uses; this does not contact Sede or claim to exercise an OS input method.
const surface = (page: Page) => page.locator("[data-browser-surface]");
const sink = (page: Page) => surface(page).locator("textarea");
const inputs = (page: Page) =>
  page.evaluate(() => window.__scenarioSedeView?.inputs() ?? []);
const textInputs = async (page: Page) =>
  (await inputs(page)).filter((event) => event.type === "text");

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => localStorage.clear());
  await page.goto("/scenarios.html?scenario=signed-in&latency=0&bar=off");
  await page
    .getByRole("navigation", { name: label("desktop.rail.label") })
    .getByRole("button", { name: label("desktop.browser.title"), exact: true })
    .click();
  await expect(sink(page)).toBeEditable();
  await surface(page).focus();
  await expect(sink(page)).toBeFocused();
});

test("native editable composition keeps candidates local and commits its final text once", async ({
  page,
}) => {
  const session = await page.context().newCDPSession(page);
  await session.send("Input.imeSetComposition", {
    text: "に",
    selectionStart: 1,
    selectionEnd: 1,
  });
  await expect(sink(page)).toHaveValue("に");
  expect(await textInputs(page)).toEqual([]);

  await session.send("Input.imeSetComposition", {
    text: "日本",
    selectionStart: 2,
    selectionEnd: 2,
  });
  await expect(sink(page)).toHaveValue("日本");
  expect(await textInputs(page)).toEqual([]);
  await session.send("Input.insertText", { text: "日本語" });
  await expect
    .poll(() => textInputs(page))
    .toEqual([{ type: "text", text: "日本語" }]);
  await expect(sink(page)).toHaveValue("");
  expect((await inputs(page)).filter((event) => event.type === "key")).toEqual(
    [],
  );

  // An independent native insertion with the same value is a new edit.
  await page.keyboard.insertText("日本語");
  await expect.poll(() => textInputs(page)).toHaveLength(2);
  await expect(sink(page)).toHaveValue("");
});

test("cancelled native composition sends no text", async ({ page }) => {
  const session = await page.context().newCDPSession(page);
  await session.send("Input.imeSetComposition", {
    text: "候補",
    selectionStart: 2,
    selectionEnd: 2,
  });
  await expect(sink(page)).toHaveValue("候補");
  await session.send("Input.imeSetComposition", {
    text: "",
    selectionStart: 0,
    selectionEnd: 0,
  });
  await expect(sink(page)).toHaveValue("");
  expect(await textInputs(page)).toEqual([]);
});

for (const finalInput of ["before-end", "after-end", "none"] as const)
  test(`composition commits once when the final input is ${finalInput}`, async ({
    page,
  }) => {
    const defaults = await sink(page).evaluate((element, order) => {
      if (!(element instanceof HTMLTextAreaElement))
        throw new Error("No editable input sink.");
      element.dispatchEvent(
        new CompositionEvent("compositionstart", { bubbles: true }),
      );
      const initiating = new KeyboardEvent("keydown", {
        key: "a",
        code: "KeyA",
        keyCode: 229,
        bubbles: true,
        cancelable: true,
      });
      const accept = new KeyboardEvent("keydown", {
        key: "Enter",
        code: "Enter",
        bubbles: true,
        cancelable: true,
      });
      element.dispatchEvent(initiating);
      element.dispatchEvent(accept);
      const final = () => {
        element.value = "é😀";
        element.dispatchEvent(
          new InputEvent("input", {
            inputType: "insertText",
            data: "é😀",
            isComposing: false,
            bubbles: true,
          }),
        );
      };
      if (order === "before-end") final();
      element.dispatchEvent(
        new CompositionEvent("compositionend", {
          data: "é😀",
          bubbles: true,
        }),
      );
      if (order === "after-end") final();
      return [initiating.defaultPrevented, accept.defaultPrevented];
    }, finalInput);
    expect(defaults).toEqual([false, false]);
    await expect
      .poll(() => textInputs(page))
      .toEqual([{ type: "text", text: "é😀" }]);
    expect(
      (await inputs(page)).filter((event) => event.type === "key"),
    ).toEqual([]);
    await expect(sink(page)).toHaveValue("");
    await page.keyboard.type("a");
    await expect
      .poll(() => textInputs(page))
      .toEqual([
        { type: "text", text: "é😀" },
        { type: "text", text: "a" },
      ]);
  });

test("blur forgets unfinished text and releases held keys", async ({
  page,
}) => {
  await page.keyboard.down("Shift");
  await sink(page).evaluate((element) => {
    if (!(element instanceof HTMLTextAreaElement))
      throw new Error("No editable input sink.");
    element.dispatchEvent(
      new CompositionEvent("compositionstart", { bubbles: true }),
    );
    element.value = "private unfinished text";
    element.dispatchEvent(
      new InputEvent("input", {
        inputType: "insertCompositionText",
        data: element.value,
        isComposing: true,
        bubbles: true,
      }),
    );
  });
  await page
    .getByRole("region", { name: label("desktop.browser.title"), exact: true })
    .focus();
  await expect(sink(page)).toHaveValue("");
  await sink(page).dispatchEvent("compositionend", {
    data: "private unfinished text",
  });
  await expect
    .poll(async () =>
      (await inputs(page)).filter((event) => event.type === "key"),
    )
    .toEqual([
      expect.objectContaining({ type: "key", action: "down", key: "Shift" }),
      expect.objectContaining({ type: "key", action: "up", key: "Shift" }),
    ]);
  await page.keyboard.up("Shift");
  expect(await textInputs(page)).toEqual([]);
  const storage = await page.evaluate(() =>
    JSON.stringify({ ...localStorage, ...sessionStorage }),
  );
  expect(storage).not.toContain("private unfinished text");
  await expect(sink(page)).toHaveAttribute("autocomplete", "off");
  await expect(sink(page)).not.toHaveAttribute("name");
});

test("text without key events is forwarded and immediately cleared", async ({
  page,
}) => {
  await page.keyboard.insertText("árvíztűrő 😀");
  await expect
    .poll(() => textInputs(page))
    .toEqual([{ type: "text", text: "árvíztűrő 😀" }]);
  await expect(sink(page)).toHaveValue("");
});

const clipboardCalls = (page: Page) =>
  page.evaluate(() =>
    (window.__scenarioHostCalls ?? []).filter((call) =>
      call.startsWith("sedeViewClipboard "),
    ),
  );

test("clipboard keyboard shortcuts request copy and cut once without sending their keys", async ({
  page,
}) => {
  await page.keyboard.press("ControlOrMeta+KeyC");
  await page.keyboard.press("ControlOrMeta+KeyX");
  await expect
    .poll(() => clipboardCalls(page))
    .toEqual(["sedeViewClipboard copy", "sedeViewClipboard cut"]);
  const keys = (await inputs(page)).filter(
    (event) =>
      event.type === "key" && ["c", "x"].includes(event.key.toLowerCase()),
  );
  expect(keys).toEqual([]);
  expect(await textInputs(page)).toEqual([]);
  await expect(sink(page)).toHaveValue("");
});

test("native clipboard events prevent the sink default and ignore active composition", async ({
  page,
}) => {
  const prevented = await sink(page).evaluate((element) => {
    const clipboard = (action: "copy" | "cut") => {
      const event = new ClipboardEvent(action, {
        bubbles: true,
        cancelable: true,
      });
      element.dispatchEvent(event);
      return event.defaultPrevented;
    };
    const defaults = [clipboard("copy"), clipboard("cut")];
    element.dispatchEvent(
      new CompositionEvent("compositionstart", { bubbles: true }),
    );
    defaults.push(clipboard("copy"), clipboard("cut"));
    element.dispatchEvent(
      new CompositionEvent("compositionend", { data: "", bubbles: true }),
    );
    return defaults;
  });
  expect(prevented).toEqual([true, true, true, true]);
  await expect
    .poll(() => clipboardCalls(page))
    .toEqual(["sedeViewClipboard copy", "sedeViewClipboard cut"]);
  expect(await textInputs(page)).toEqual([]);
});
