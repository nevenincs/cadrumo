import { expect, type Page, test } from "@playwright/test";
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
  recovery,
  review,
  stage,
} from "../support/scenarioModeloWrites";

// -- a declaration that moved under the staged edits -------------------------

type RebaseEntry = {
  address: { kind: string; casilla_id?: string };
  kind: string;
  outcome: "kept" | "changed" | "dropped";
};

/** What the check on the declaration read again found of the change held
 * on the box printed `box`, as the application judged it. */
function rebaseOf(box: string): RebaseEntry["outcome"] {
  const entry = envelope<{ rebase: RebaseEntry[] }>(
    "preflight-130-1T-rebased-review-06clear-16set-18set-from-130-1T-rebase",
  ).rebase.find((item) => item.address.casilla_id === box);
  if (!entry) throw new Error(`the review says nothing of box ${box}`);
  return entry.outcome;
}

/** Stages, on the read the declaration then moves under, a clear of box 06
 * and typed values in boxes 16 and 18, and opens their review. */
async function stageUnderRebase(target: Page) {
  await openDeclaration(target, "130", { shape: "rebase" });
  // The filer's own value comes out of a box with Delete on its row.
  await boxRow(target, "06").getByRole("gridcell").nth(1).click();
  await target.keyboard.press("Delete");
  await expect(boxRow(target, "06")).toContainText(
    label("workspace.modelo.staged.clear"),
  );
  await stage(target, "16", "250");
  await stage(target, "18", "75");
  return review(target, 3);
}

test("a declaration that moved under the staged edits says what became of them", async ({
  page: target,
}) => {
  expect([rebaseOf("06"), rebaseOf("16"), rebaseOf("18")]).toEqual([
    "dropped",
    "changed",
    "kept",
  ]);
  const dialog = await stageUnderRebase(target);
  await expect(
    dialog
      .getByRole("alert")
      .or(dialog.getByRole("status"))
      .filter({
        hasText: label("workspace.modelo.rebase.moved"),
      }),
  ).toContainText(
    [
      label("workspace.modelo.rebase.moved"),
      label("workspace.modelo.rebase.changed", { count: 1 }),
      label("workspace.modelo.rebase.dropped", { count: 1 }),
    ].join(" "),
  );
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
});

test("a staged edit the renewal dropped is no longer staged", async ({
  page: target,
}) => {
  const dialog = await stageUnderRebase(target);
  // Two of the three changes are left to apply.
  await expect(dialog.getByRole("listitem")).toHaveCount(2);
  await expect(
    dialog.getByRole("listitem").filter({ hasText: "06" }),
  ).toHaveCount(0);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "06")).not.toContainText(
    label("workspace.modelo.staged.clear"),
  );
});

test("a staged edit the renewal kept is staged again against the box as it now stands", async ({
  page: target,
}) => {
  const now = fields(form("130-1T-rebased").form.form.pages).find(
    (field) => field.box === "18",
  );
  if (!now) throw new Error("the moved 130 holds no box 18");
  const dialog = await stageUnderRebase(target);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  const row = boxRow(target, "18");
  await expect(row).toContainText(label("workspace.modelo.attention.staged"));
  await expect(row).toContainText(
    label("workspace.modelo.was", { value: now.value_text ?? "—" }),
  );
});

test("a changed edit stays marked until the filer acknowledges it", async ({
  page: target,
}) => {
  const dialog = await stageUnderRebase(target);
  const changed = dialog.getByRole("listitem").filter({ hasText: "16" });
  await expect(changed).toContainText(
    label("workspace.modelo.review.before_changed"),
  );
  await expect(applyButton(dialog)).toBeDisabled();
  // Looking again keeps the mark: it holds until it is acknowledged.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  const again = await review(target, 2);
  await expect(
    again.getByRole("listitem").filter({ hasText: "16" }),
  ).toContainText(label("workspace.modelo.review.before_changed"));
  await expect(applyButton(again)).toBeDisabled();
  await again
    .getByRole("checkbox", {
      name: label("workspace.modelo.review.acknowledge"),
    })
    .check();
  await expect(applyButton(again)).toBeEnabled();
});

test("a stale check whose renewal is refused reads the declaration again once, and the check on it stands", async ({
  page: target,
}) => {
  const stale = envelope<{
    outcome: { refusal?: { kind: string } };
    rebase: RebaseEntry[];
  }>("preflight-130-1T-rebase-stale");
  // The stale refusal says nothing of the held changes; only the check on
  // the declaration read again does.
  expect(stale.outcome.refusal?.kind).toBe("stale_edit_baseline");
  expect(stale.rebase).toEqual([]);
  // More than the baseline's lifetime moved, so renewing it is refused.
  const renewal = envelope<{ renewed_baseline: unknown; refusal: unknown }>(
    "renew-130-1T-rebase",
  );
  expect(renewal.renewed_baseline).toBeNull();
  expect(renewal.refusal).not.toBeNull();
  const dialog = await stageUnderRebase(target);
  // Stale check, the refused renewal, one read of the declaration, the
  // check again.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  const renewed = sequence.indexOf("modelo submit modelo.edit.renew");
  expect(renewed).toBeGreaterThan(0);
  expect(sequence[renewed - 1]).toBe("modelo edit modelo.edit.preflight");
  const after = sequence.slice(renewed + 1);
  expect(after.filter((call) => call.startsWith("modelo form "))).toHaveLength(
    1,
  );
  expect(after[0]).toMatch(/^modelo form /);
  expect(after.slice(1)).toContain("modelo edit modelo.edit.preflight");
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  // What the check on the declaration read again reported stands: the
  // dropped change is said, the changed one is marked and holds the apply
  // until it is acknowledged.
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.dropped", { count: 1 }),
  );
  const changed = dialog.getByRole("listitem").filter({ hasText: "16" });
  await expect(changed).toContainText(
    label("workspace.modelo.review.before_changed"),
  );
  await expect(applyButton(dialog)).toBeDisabled();
  await dialog
    .getByRole("checkbox", {
      name: label("workspace.modelo.review.acknowledge"),
    })
    .check();
  await expect(applyButton(dialog)).toBeEnabled();
});

test("a declaration still changing after it was read again stops after that one read and says so", async ({
  page: target,
}) => {
  // The real sequence: stale on the read the edits were staged on, its
  // renewal refused, and stale again on the declaration read again, since
  // it moved once more.
  for (const name of [
    "preflight-130-1T-rebase-stale",
    "preflight-130-1T-moving-stale",
  ]) {
    const stale = envelope<{
      outcome: { refusal?: { kind: string } };
      rebase: RebaseEntry[];
    }>(name);
    expect(stale.outcome.refusal?.kind).toBe("stale_edit_baseline");
    expect(stale.rebase).toEqual([]);
  }
  await openDeclaration(target, "130", { shape: "moving" });
  await boxRow(target, "06").getByRole("gridcell").nth(1).click();
  await target.keyboard.press("Delete");
  await stage(target, "16", "250");
  await stage(target, "18", "75");
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  // One renewal and one read of the declaration, and nothing after them.
  const sequence = (
    await target.evaluate(() => window.__scenarioHostCalls ?? [])
  ).filter(
    (call) =>
      call === "modelo edit modelo.edit.preflight" ||
      call === "modelo submit modelo.edit.renew" ||
      call.startsWith("modelo form "),
  );
  const renewed = sequence.indexOf("modelo submit modelo.edit.renew");
  expect(sequence.slice(renewed + 1)).toEqual([
    "modelo form en",
    "modelo edit modelo.edit.preflight",
  ]);
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  await expect(applyButton(dialog)).toHaveCount(0);
  // The edits are still the filer's: nothing was applied or let go.
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "16")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});

/** Stages the rebase changes in the `moving` shape and reviews them until
 * the window says the declaration is still changing. */
async function stillMoving(target: Page) {
  await openDeclaration(target, "130", { shape: "moving" });
  await boxRow(target, "06").getByRole("gridcell").nth(1).click();
  await target.keyboard.press("Delete");
  await stage(target, "16", "250");
  await stage(target, "18", "75");
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  const dialog = target.getByRole("dialog");
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  return dialog;
}

/** What a review asked of the host after its last renewal. */
async function afterLastRenewal(target: Page) {
  const sequence = await recovery(target);
  return sequence.slice(
    sequence.lastIndexOf("modelo submit modelo.edit.renew") + 1,
  );
}

test("checking again after the declaration is still changing renews and reads once more, then stops", async ({
  page: target,
}) => {
  // Each renewal is refused, and each read finds the declaration moved again.
  for (const name of ["renew-130-1T-rebase", "renew-130-1T-moving"])
    expect(
      envelope<{ renewed_baseline: unknown }>(name).renewed_baseline,
    ).toBeNull();
  const dialog = await stillMoving(target);
  expect(await calls(target, "modelo submit modelo.edit.renew")).toHaveLength(
    1,
  );
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.check_again") })
    .click();
  await expect(dialog).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  await expect
    .poll(
      async () =>
        (await calls(target, "modelo submit modelo.edit.renew")).length,
    )
    .toBe(2);
  // One more renewal, one more read, the check on it, and nothing after.
  await expect
    .poll(() => afterLastRenewal(target))
    .toEqual(["modelo form en", "modelo edit modelo.edit.preflight"]);
  await expect(applyButton(dialog)).toHaveCount(0);
});

test("reopening the review after the declaration is still changing reads it again once", async ({
  page: target,
}) => {
  const dialog = await stillMoving(target);
  await dialog
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(dialog).toBeHidden();
  await target
    .getByRole("button", { name: label("workspace.modelo.next_button.apply") })
    .first()
    .click();
  const again = target.getByRole("dialog");
  await expect(again).toContainText(
    label("workspace.modelo.rebase.still_moving"),
  );
  await expect
    .poll(
      async () =>
        (await calls(target, "modelo submit modelo.edit.renew")).length,
    )
    .toBe(2);
  await expect
    .poll(() => afterLastRenewal(target))
    .toEqual(["modelo form en", "modelo edit modelo.edit.preflight"]);
  // The edits are still staged throughout.
  await again
    .getByRole("button", { name: label("workspace.modelo.review.back") })
    .click();
  await expect(boxRow(target, "16")).toContainText(
    label("workspace.modelo.attention.staged"),
  );
});
