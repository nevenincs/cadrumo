import { expect, type Locator, type Page, test } from "@playwright/test";
import { label } from "../support/strings";
import {
  boxRow,
  envelope,
  fields,
  form,
  openDeclaration,
} from "../support/scenarioModelo";
import {
  applyButton,
  calls,
  review,
  stage,
  TYPED_06,
} from "../support/scenarioModeloWrites";

// -- writes ------------------------------------------------------------------
// Each write answers what the application answered for it (envelopes under
// the generated envelopes read through the registered operations); a write
// whose settlement was not seen, or that was refused before it ran, is the
// host's own answer.

test("an applied edit settles, clears what was staged and shows what was stored", async ({
  page: target,
}) => {
  const after = fields(form("130-1T-applied").form.form.pages).find(
    (field) => field.box === "06",
  );
  if (!after?.value_text) throw new Error("the applied 130 holds no box 06");
  await openDeclaration(target, "130", { shape: "edit" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.done")),
  ).toBeVisible();
  await dialog
    .getByRole("button", { name: label("workspace.modelo.key.close") })
    .last()
    .click();
  await expect(boxRow(target, "06")).toContainText(after.value_text);
  await expect(boxRow(target, "06")).not.toContainText(
    label("workspace.modelo.attention.staged"),
  );
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
});

test("staged edits survive a renewal of a baseline that went stale", async ({
  page: target,
}) => {
  const stale = envelope<{
    outcome: { outcome: string; refusal?: { kind: string } };
  }>("preflight-130-1T-expiring-stale");
  expect(stale.outcome.refusal?.kind).toBe("stale_edit_baseline");
  await openDeclaration(target, "130", { shape: "renewal" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  // The check answered stale, the baseline was renewed, the declaration read
  // again and the edits checked again: nothing staged was lost.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  const renewed = sequence.indexOf("modelo submit modelo.edit.renew");
  expect(sequence.slice(renewed - 1, renewed + 3)).toEqual([
    "modelo edit modelo.edit.preflight",
    "modelo submit modelo.edit.renew",
    "modelo form en",
    "modelo edit modelo.edit.preflight",
  ]);
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  // The check on the renewed baseline was answered for the form that admits
  // it, which the renewal named, not found by reading every written form.
  expect(await calls(target, "modelo scan written forms")).toHaveLength(0);
  await expect(dialog.getByRole("listitem")).toHaveCount(1);
  await expect(dialog.getByRole("listitem")).toContainText("06");
  // The check on the renewed baseline was evaluated: the edit may be applied.
  await expect(applyButton(dialog)).toBeEnabled();
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

test("an entry typed after the form's baseline ran out is read again on its renewal and staged", async ({
  page: target,
}) => {
  const late = envelope<{
    outcome: { outcome: string; refusal?: { kind: string } };
    refusal_words: string | null;
  }>("preflight-130-1T-expiring-entry-06-en-late");
  // Typed only now, the entry is answered stale, as the application answers it.
  expect(late.outcome.refusal?.kind).toBe("stale_edit_baseline");
  const staleWords = late.refusal_words;
  if (!staleWords) throw new Error("the stale entry check served no words");
  await openDeclaration(target, "130", { shape: "renewal-entry" });
  await stage(target, "06", TYPED_06);
  // Nothing moved, so the baseline was renewed and the entry read again on
  // the renewal: the filer was never told the declaration changed.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  expect(sequence.slice(-3)).toEqual([
    "modelo edit modelo.edit.preflight",
    "modelo submit modelo.edit.renew",
    "modelo edit modelo.edit.preflight",
  ]);
  await expect(target.getByText(staleWords)).toHaveCount(0);
  // The review checks on the renewed baseline the entry was read on: it
  // needs no renewal of its own.
  const dialog = await review(target);
  await expect(applyButton(dialog)).toBeEnabled();
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
});

test("an apply refused because its baseline went stale is renewed and applied once more", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "renewal-apply" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.done")),
  ).toBeVisible();
  // The stale refusal wrote nothing, so the apply was sent again on the
  // renewal: once refused, once applied.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.apply" ||
      call === "modelo submit modelo.edit.renew",
  );
  expect(sequence.slice(-3)).toEqual([
    "modelo edit modelo.edit.apply",
    "modelo submit modelo.edit.renew",
    "modelo edit modelo.edit.apply",
  ]);
  await expect(
    dialog.getByText(label("workspace.modelo.operation.not_done")),
  ).toHaveCount(0);
});

test("an unknown apply stays held until terminal observation and a successful fresh form read", async ({
  page: target,
}) => {
  const unknown = (where: Locator | Page) =>
    where.getByRole("alert").filter({
      hasText: label("workspace.modelo.write_hold.unknown"),
    });
  await openDeclaration(target, "130", { shape: "unknown" });
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const form = port.form;
    const recovery = (window.__modeloWorkRecovery = {
      terminal: false,
      failReads: 0,
    });
    port.observe = async (operation) =>
      recovery.terminal
        ? {
            kind: "refused",
            operation_id: operation,
            revision: 2,
            reason: null,
            detail: null,
          }
        : {
            kind: "running",
            operation_id: operation,
            revision: 1,
            cancellable: false,
          };
    port.form = async (...args) => {
      if (recovery.failReads > 0) {
        recovery.failReads--;
        throw Object.assign(new Error("fixture read failure"), {
          code: "unavailable",
        });
      }
      return form(...args);
    };
  });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(unknown(dialog)).toBeVisible();
  await expect(applyButton(dialog)).toBeDisabled();
  // Closing and reviewing again sends nothing: it may have committed.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.key.close") })
    .last()
    .click();
  await review(target);
  await expect(unknown(dialog)).toBeVisible();
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
  const preflights = (await calls(target, "modelo edit modelo.edit.preflight"))
    .length;
  const check = dialog.getByRole("button", {
    name: label("workspace.modelo.write_hold.check_status"),
  });
  await check.click();
  await expect(check).toBeEnabled();
  await expect(applyButton(dialog)).toBeDisabled();
  await expect(
    dialog.getByRole("button", { name: label("workspace.modelo.read_again") }),
  ).toHaveCount(0);
  await target.evaluate(() => {
    window.__modeloWorkRecovery!.terminal = true;
    window.__modeloWorkRecovery!.failReads = 1;
  });
  await check.click();
  const reload = dialog.getByRole("button", {
    name: label("workspace.modelo.read_again"),
  });
  await reload.click();
  await expect(reload).toBeEnabled();
  await expect(dialog.locator(".modelo-write-hold")).toBeVisible();
  await expect(applyButton(dialog)).toBeDisabled();
  await reload.click();
  await expect(unknown(target)).toHaveCount(0);
  await expect
    .poll(
      async () =>
        (await calls(target, "modelo edit modelo.edit.preflight")).length,
    )
    .toBeGreaterThan(preflights);
  expect(await calls(target, "modelo edit modelo.edit.apply")).toHaveLength(1);
});

test("a refused apply names the earlier filing it waits on", async ({
  page: target,
}) => {
  const held = envelope<{
    prerequisite: { casilla_id: string; words: string | null } | null;
  }>("apply-prerequisite-130-3T-prerequisite").prerequisite;
  if (!held?.words) throw new Error("the refused apply holds no prerequisite");
  await openDeclaration(target, "130", { shape: "prerequisite" });
  await stage(target, "06", TYPED_06);
  const dialog = await review(target);
  await applyButton(dialog).click();
  await expect(
    dialog.getByText(label("workspace.modelo.operation.not_done")),
  ).toBeVisible();
  for (const line of held.words.split("\n"))
    await expect(dialog).toContainText(line);
  await expect(
    dialog.getByRole("button", {
      name: label("workspace.modelo.apply_prerequisite.action"),
    }),
  ).toBeVisible();
  // Nothing was applied: the edit stays staged.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

test("the real Modelo 303 takes a typed value and checks it as staged", async ({
  page: target,
}) => {
  const typed = envelope<{
    parsed: { value_text: string | null }[];
  }>("preflight-303-1T-entry-42-en").parsed[0];
  if (!typed?.value_text) throw new Error("the 303 entry read no value");
  await openDeclaration(target, "303");
  // The form draws its sections as they scroll in: find the box by number.
  await target
    .getByRole("searchbox", { name: label("desktop.modelo.search.label") })
    .fill("42");
  // The application read the entry as a figure; the box says it as read.
  await stage(target, "42", "1,234.56");
  await expect(boxRow(target, "42")).toContainText(typed.value_text);
  const dialog = await review(target);
  await expect(dialog.getByRole("listitem")).toContainText("42");
  await expect(applyButton(dialog)).toBeVisible();
  // Each body the window sent was within the host's bound and answered.
  await expect(
    dialog.getByText(label("workspace.modelo.review.check_failed")),
  ).toHaveCount(0);
});
