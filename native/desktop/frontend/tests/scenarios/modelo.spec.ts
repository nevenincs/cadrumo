import { expect, test } from "@playwright/test";
import { ASSET_NOTES } from "../../src/dev/modeloAssetNotes";
import { label } from "../support/strings";
import { seedLayout } from "../support/layout";
import {
  boxRow,
  fields,
  form,
  formPanel,
  list,
  openDeclaration,
  openFromDialog,
  openList,
  RAW,
  rowsOf,
  rulesIncomplete,
  tab,
  views,
} from "../support/scenarioModelo";
import { calls, stage, TYPED_06 } from "../support/scenarioModeloWrites";

// The Modelo workspace across its states, over the envelopes the
// application read for a synthetic taxpayer (the generated envelopes):
// a modelo whose rules are incomplete, a filled Modelo 130 with held zeros,
// the check's findings, a file for the AEAT left out of date by a later
// change, a filing recorded with and without a verified receipt, the list's
// rows that may apply, every state in all four languages, and a gate that
// no raw catalogue key or internal identifier reaches the screen. What the
// screen says is compared with what the envelope says: the window renders
// the read model's words and decides none of its own.

// -- the states ------------------------------------------------------------

test("a modelo whose rules are incomplete opens read only, without a next step", async ({
  page: target,
}) => {
  const read = form(`${rulesIncomplete.modelo}-${rulesIncomplete.period_code}`);
  await openFromDialog(target, rulesIncomplete.modelo);
  const banner = target
    .getByRole("status")
    .filter({ hasText: label("workspace.modelo.editor.rules_incomplete") });
  await expect(banner).toBeVisible();
  // The read model names no next step and no result box for it.
  expect(read.next_step).toBeNull();
  for (const action of ["calculate", "verify", "resolve", "fill", "export"])
    await expect(
      target.getByRole("button", {
        name: label(`workspace.modelo.next_button.${action}`),
      }),
    ).toHaveCount(0);
  await expect(
    target.getByText(label("workspace.modelo.header.result.no_result_box")),
  ).toBeVisible();
  if (read.header.deadline)
    await expect(
      target.getByText(read.header.deadline.text, { exact: true }),
    ).toBeVisible();
  // Nothing on the form takes a value.
  await expect(formPanel(target).getByRole("textbox")).toHaveCount(0);
  await expect(
    target.getByText(label("workspace.modelo.editability.no_admission")),
  ).toHaveCount(0);
});

test("a calculated Modelo 130 shows its figures, and its held zeros as zero", async ({
  page: target,
}) => {
  // The quarter's activity income is booked and nothing is checked or filed:
  // the capped boxes carry the figures the backend calculated.
  const calculated = fields(form("130-1T-income").form.form.pages);
  const figure = calculated.find(
    (field) =>
      field.box &&
      !field.held_zero &&
      field.value?.kind === "decimal" &&
      field.value_text &&
      field.value_text !== "0.00 €",
  );
  const held = calculated.find(
    (field) => field.box && field.held_zero && field.value_text,
  );
  if (!figure?.value_text || !held?.value_text)
    throw new Error("the calculated 130 holds no figure and no held zero");
  await openDeclaration(target, "130", { shape: "income" });
  await expect(boxRow(target, figure.box!)).toContainText(figure.value_text);
  await expect(boxRow(target, held.box!)).toContainText(held.value_text);
});

test("a Modelo 130 recorded as filed shows its proven-zero quarter as zero", async ({
  page: target,
}) => {
  const filed = form("130-1T-filed");
  const zero = fields(filed.form.form.pages).find(
    (field) => field.box && field.held_zero,
  );
  if (!zero?.value_text) throw new Error("the filed 130 holds no held zero");
  await openDeclaration(target, "130", { shape: "filed" });
  await expect(boxRow(target, zero.box!)).toContainText(zero.value_text);
  // The header states the result the read model stated: its amount where it
  // served one, else its sentence.
  const result = filed.header.result;
  const stated = result?.amount_text ?? result?.short_text;
  if (!stated) throw new Error("the filed 130 states no result");
  await expect(target.getByText(stated, { exact: true }).first()).toBeVisible();
});

test("a box shows the help the read serves for it, and its details in words only", async ({
  page: target,
}) => {
  const all = fields(form("130-1T").form.form.pages);
  const helped = all.find((field) => field.box && field.help);
  if (!helped?.help) throw new Error("the 130 serves no help for any box");
  await openDeclaration(target, "130");
  const row = boxRow(target, helped.box!);
  // The help sits under the box's words on the form itself.
  await expect(row).toContainText(helped.help);
  await row
    .getByRole("button", { name: label("workspace.modelo.field.details") })
    .click();
  const facts = target.getByRole("dialog", {
    name: label("workspace.modelo.field.details"),
  });
  await expect(facts).toContainText(helped.label.text);
  await expect(facts).toContainText(helped.help);
  // Legal references and the formula are served as identifiers: never drawn.
  for (const reference of helped.legal_refs)
    await expect(facts).not.toContainText(reference);
  const said = await facts.innerText();
  expect(
    RAW.flatMap(([kind, source]) =>
      [...said.matchAll(new RegExp(source, "g"))].map(
        (match) => `${kind}: ${match[0]}`,
      ),
    ),
  ).toEqual([]);
});

test("failed box help can be retried without leaving the selected box", async ({
  page: target,
}) => {
  const helped = fields(form("130-1T").form.form.pages).find(
    (field) => field.box && field.help && field.address.kind === "casilla",
  )!;
  await openDeclaration(target, "130");
  await target.evaluate(() => {
    const port = window.__fixtureModelo!;
    const read = port.casillaHelp.bind(port);
    window.__modeloHelpGate = { failed: true, reads: 0 };
    port.casillaHelp = async (request) => {
      const gate = window.__modeloHelpGate!;
      gate.reads += 1;
      if (gate.failed)
        throw Object.assign(new Error("Help unavailable"), {
          code: "unavailable",
        });
      return read(request);
    };
  });
  await boxRow(target, helped.box!).click();
  const details = target.locator("[data-modelo-details]:visible");
  await expect(details).toContainText(
    label("workspace.modelo.details.card_unavailable"),
  );
  const before = await target.evaluate(() => {
    window.__modeloHelpGate!.failed = false;
    return window.__modeloHelpGate!.reads;
  });
  await details
    .getByRole("button", {
      name: label("desktop.declarations.retry"),
      exact: true,
    })
    .click();
  await expect(details).not.toContainText(
    label("workspace.modelo.details.card_unavailable"),
  );
  await expect(details).not.toContainText(
    label("workspace.modelo.details.reading"),
  );
  await expect(details).toContainText(helped.label.text);
  await expect(details).toContainText("Real Decreto 439/2007, art. 110");
  expect(await target.evaluate(() => window.__modeloHelpGate!.reads)).toBe(
    before + 1,
  );
  expect(await calls(target, "modelo submit")).toEqual([]);
});

test("one details panel survives responsive changes without rereading its help", async ({
  page: target,
}, info) => {
  await seedLayout(target, {
    layout: {
      agentShown: false,
      tuiShown: false,
      docsShown: true,
      page: "docs",
    },
  });
  await target.setViewportSize({ width: 1600, height: 900 });
  await openDeclaration(target, "130", { shape: "edit" });
  await stage(target, "06", TYPED_06);
  await boxRow(target, "01").click();
  const details = target.locator("[data-modelo-details]");
  await expect(details).toHaveCount(1);
  await expect(details).toContainText("Real Decreto 439/2007, art. 110");
  const reads = (await calls(target, "modelo casillaHelp")).length;
  for (const width of [600, 1000, 1200, 1600]) {
    await target.setViewportSize({ width, height: width === 600 ? 700 : 900 });
    await expect(details).toHaveCount(1);
    await expect(details).toBeVisible();
    const panel = target.locator(
      ".declarations-workspace [role=tabpanel][data-details]",
    );
    await expect(
      panel.getByRole("button", {
        name: label("workspace.modelo.next_button.apply"),
        exact: true,
      }),
    ).toBeInViewport();
    expect(
      await panel.evaluate(
        (element) => element.scrollWidth - element.clientWidth,
      ),
    ).toBeLessThanOrEqual(1);
    expect((await calls(target, "modelo casillaHelp")).length).toBe(reads);
    if (width === 600 || width === 1600)
      await target.screenshot({
        path: info.outputPath(`details-${width}.png`),
      });
  }
});

test("a box whose kind of value cannot be typed says why on the form", async ({
  page: target,
}) => {
  const page = form("303-1T").form.form.pages[0]!;
  const blocks = page.sections.flatMap((section) => section.blocks);
  const ownLine = blocks.flatMap((block) =>
    block.kind === "field" && block.field.takes_typed_value
      ? [block.field]
      : [],
  )[0];
  const inGrid = blocks
    .flatMap((block) => (block.kind === "grid" ? block.rows : []))
    .flatMap((row) => row.cells)
    .find((cell) => cell.field?.takes_typed_value)?.field;
  if (!ownLine?.box || !inGrid?.box)
    throw new Error("the first page holds no typed box of each layout");
  const reason = label(
    "workspace.modelo.not_writable.value_channel_unavailable",
  );
  await openDeclaration(target, "303", { shape: "read-only-boxes" });
  // The form draws its sections as they scroll in: find each box by number.
  const search = target.getByRole("searchbox", {
    name: label("desktop.modelo.search.label"),
  });

  // On its own line the reason sits beside the box, and the box takes nothing.
  await search.fill(ownLine.box);
  const row = boxRow(target, ownLine.box);
  await expect(row).toContainText(reason);
  const face = row.getByRole("gridcell").nth(2).getByRole("button");
  await expect(face).toBeDisabled();
  await expect(formPanel(target).getByRole("textbox")).toHaveCount(0);

  // In a grid, where a line has no room for it, the box shows it on hover.
  await search.fill(inGrid.box);
  const cell = formPanel(target).getByRole("cell", {
    name: label("workspace.modelo.section.box", { box: inGrid.box }),
  });
  await expect(cell).not.toContainText(reason);
  // The box's own face, not the button beside it that opens its details.
  await cell.locator("button:not([data-field-facts])").hover();
  await expect(target.getByRole("tooltip")).toContainText(reason);
});

test("a box with no value is drawn as missing, never as a zero", async ({
  page: target,
}) => {
  const draft = form("303-1T");
  // A box on its own line, as the first page lists it.
  const missing = draft.form.form.pages[0]!.sections.flatMap(
    (section) => section.blocks,
  )
    .flatMap((block) => (block.kind === "field" ? [block.field] : []))
    .find(
      (field) =>
        field.box &&
        (field.value === null || field.value.kind === "null") &&
        !field.value_text,
    );
  if (!missing) throw new Error("the 303's first page has no missing box");
  await openDeclaration(target, "303");
  // The form draws its sections as they scroll in: find the box by number.
  await target
    .getByRole("searchbox", { name: label("desktop.modelo.search.label") })
    .fill(missing.box!);
  const row = boxRow(target, missing.box!);
  await expect(row).toContainText("—");
  await expect(row).not.toContainText(/\b0[.,]00\b/);
});

test("the check lists every finding under its level, in plain words only", async ({
  page: target,
}) => {
  const read = form("130-1T-checked");
  await openDeclaration(target, "130", { shape: "checked" });
  await tab(target, "workspace.modelo.step.review").click();
  await expect(target.getByText(read.verdict.words)).toBeVisible();
  for (const line of read.issue_lines) {
    const level = target.getByRole("region", {
      name: label(`workspace.modelo.level.${line.level}`),
    });
    // Two findings may share a sentence; each is told apart by where it is.
    const said = level.getByRole("listitem").filter({ hasText: line.message });
    const item = line.where ? said.filter({ hasText: line.where }) : said;
    await expect(item).toContainText(line.action);
    // A calculation note's own account, worded for the filer, is drawn under
    // its sentence, as a finding's kind is.
    if (line.detail) await expect(item).toContainText(line.detail);
    await expect(item).not.toContainText(line.technical);
  }
});

test("the check draws each asset note as its own line to read, asking for nothing and counting nothing", async ({
  page: target,
}) => {
  const read = form("130-1T-checked");
  await openDeclaration(target, "130", { shape: "check-notes" });
  await tab(target, "workspace.modelo.step.review").click();
  const level = target.getByRole("region", {
    name: label("workspace.modelo.level.check"),
  });
  // Two elements with a gap of one kind are two lines, each stating its own
  // element and dates, and the kind of thing it is as the second line.
  for (const note of ASSET_NOTES) {
    const item = level.getByRole("listitem").filter({ hasText: note.message });
    await expect(item).toHaveCount(1);
    await expect(item).toContainText(note.detail);
    // It leads nowhere to fill, and it is not a button to press.
    await expect(item.getByRole("button")).toHaveCount(0);
  }
  await expect(level.getByRole("listitem")).toHaveCount(ASSET_NOTES.length);
  // The verdict is the read model's, as without the notes: the check was
  // refused on the blocking note the calculation left at a box, so nothing
  // was checked.
  await expect(target.getByText(read.verdict.words)).toBeVisible();
  expect(read.verdict.status).toBeNull();
  expect(
    read.issue_lines.some(
      (line) =>
        line.level === "blocks" &&
        line.from_calculation &&
        line.address?.kind === "casilla",
    ),
  ).toBe(true);
});

test("a check line whose source is the suffered withholding opens that register in the Ledger", async ({
  page: target,
}) => {
  await openDeclaration(target, "130", { shape: "withholding-link" });
  await tab(target, "workspace.modelo.step.review").click();
  await target
    .getByRole("button", {
      name: label("workspace.modelo.surface.open.withholding"),
    })
    .click();
  // The Ledger opens on Registers, on the withholding area.
  await expect(target.locator(".ledger-setup-registers")).toBeVisible();
  await expect(
    target.getByRole("tab", {
      name: label("desktop.ledger.registers.area.withholding"),
      exact: true,
    }),
  ).toHaveAttribute("aria-selected", "true");
  await expect(
    target.locator(".ledger-withholding-class").first(),
  ).toBeVisible();
});

test("a file made before a conflicting edit stays out of date until its export hold is resolved", async ({
  page: target,
}, info) => {
  const read = form("130-1T-stale");
  if (!read.header.file || read.header.file.current)
    throw new Error("the stale 130 has no out-of-date file");
  await openDeclaration(target, "130", { shape: "stale" });
  await expect(target.getByText(read.header.file.words)).toBeVisible();
  await tab(target, "workspace.modelo.filing.title").click();
  await expect(tab(target, "workspace.modelo.filing.title")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    target.getByText(label("workspace.modelo.filing.file_earlier")),
  ).toBeVisible();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
    }),
  ).toBeDisabled();
  expect(read.header.export_hold?.reason).toBe("blocks");
  if (!read.header.export_hold)
    throw new Error("the changed 130 has no export hold");
  const words = read.header.export_hold.words;
  await expect(target.getByText(words, { exact: true })).toHaveCount(1);
  for (const key of [
    "workspace.modelo.filing.export_again",
    "workspace.modelo.filing.record_as_filed",
    "workspace.modelo.filing.copy.package.action",
  ]) {
    const action = target.getByRole("button", {
      name: label(key),
      exact: true,
    });
    await expect(action).toBeDisabled();
    await expect(action).toHaveAccessibleDescription(words);
  }
  await expect(
    target.getByRole("region", {
      name: label("workspace.modelo.filing.file_title"),
      exact: true,
    }),
  ).toHaveAccessibleDescription(words);
  await expect(
    target.getByRole("region", {
      name: label("workspace.modelo.filing.after_filed_title"),
      exact: true,
    }),
  ).toHaveAccessibleDescription(words);
  await expect(
    target.getByRole("region", {
      name: label("workspace.modelo.filing.compare_declaration_title"),
      exact: true,
    }),
  ).not.toHaveAttribute("aria-describedby");
  await target.screenshot({ path: info.outputPath("filing-shared-hold.png") });
  // The hold names the action that lifts it; resolving what blocks is done
  // on the check.
  expect(read.header.export_hold.action).toBe("resolve");
  await target
    .getByRole("tabpanel")
    .getByRole("button", {
      name: label(
        `workspace.modelo.next_button.${read.header.export_hold.action}`,
      ),
      exact: true,
    })
    .click();
  await expect(tab(target, "workspace.modelo.step.review")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

test("a filing action keeps its distinct refusal beside the shared export hold", async ({
  page: target,
}) => {
  const grid = await openList(target, { shape: "stale" });
  const separate = "A separate filing requirement remains unresolved.";
  await target.evaluate((words) => {
    const port = window.__fixtureModelo!;
    const original = port.form;
    port.form = async (...args) => {
      const read = await original(...args);
      if (!read.export_offer)
        throw new Error("The fixture has no export offer");
      return {
        ...read,
        export_offer: {
          ...read.export_offer,
          artefacts: read.export_offer.artefacts.map((option) =>
            option.artefact === "fichero_boe"
              ? { ...option, availability: { ...option.availability, words } }
              : option,
          ),
        },
      };
    };
  }, separate);
  const local = list().rows.find(
    (row) => row.modelo === "130" && row.opens_local_work,
  );
  if (!local) throw new Error("The fixture has no local 130");
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
      exact: true,
    })
    .fill("130");
  await rowsOf(grid, "130")
    .filter({ hasText: local.period_words ?? local.modelo_title })
    .filter({ hasText: local.state_words })
    .first()
    .dblclick();
  await tab(target, "workspace.modelo.filing.title").click();
  const region = target.getByRole("region", {
    name: label("workspace.modelo.filing.file_title"),
    exact: true,
  });
  await expect(region.getByText(separate, { exact: true })).toBeVisible();
  await expect(
    region.getByRole("button", {
      name: label("workspace.modelo.filing.export_again"),
      exact: true,
    }),
  ).toBeDisabled();
  const hold = form("130-1T-stale").header.export_hold;
  if (!hold) throw new Error("The fixture has no export hold");
  await expect(target.getByText(hold.words, { exact: true })).toHaveCount(1);
});

test("a filing recorded without a verified receipt asks for it", async ({
  page: target,
}) => {
  const read = form("130-1T-filed");
  if (!read.receipt || read.receipt.verified)
    throw new Error("the filed 130's receipt is not unverified");
  await openDeclaration(target, "130", { shape: "filed" });
  await expect(target.getByText(read.receipt.words).first()).toBeVisible();
  await target
    .getByRole("button", {
      name: label("workspace.modelo.next_button.add_receipt"),
    })
    .click();
  await expect(tab(target, "workspace.modelo.filing.title")).toHaveAttribute(
    "aria-selected",
    "true",
  );
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    }),
  ).toBeEnabled();
  await expect(
    target.getByText(label("workspace.modelo.filing.not_confirmed_yet")),
  ).toBeVisible();
  // It is recorded here: nothing offers to record it again.
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.record_as_filed"),
    }),
  ).toHaveCount(0);
});

test("a filing whose receipt is verified says when, and asks for nothing", async ({
  page: target,
}) => {
  const read = form("130-1T-receipt");
  if (!read.receipt?.verified)
    throw new Error("the receipt 130's receipt is not verified");
  await openDeclaration(target, "130", { shape: "receipt" });
  await expect(target.getByText(read.receipt.words).first()).toBeVisible();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.next_button.add_receipt"),
    }),
  ).toHaveCount(0);
  await tab(target, "workspace.modelo.filing.title").click();
  await expect(
    target.getByRole("button", {
      name: label("workspace.modelo.filing.add_receipt_pdf"),
    }),
  ).toBeDisabled();
});

test("a row that may apply says why and opens nothing", async ({
  page: target,
}) => {
  const maybe = list().rows.filter((row) => row.group === "maybe");
  expect(maybe.length).toBeGreaterThan(0);
  const grid = await openList(target);
  const row = maybe[0]!;
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill(row.modelo);
  await expect(
    grid.getByRole("row").filter({ hasText: row.group_words }),
  ).toBeVisible();
  const shown = rowsOf(grid, row.modelo).filter({ hasText: row.state_words });
  await expect(shown).toBeVisible();
  if (row.advice_words) await expect(shown).toContainText(row.advice_words);
  await shown.dblclick();
  if (row.help_words)
    await expect(
      target.getByRole("status").filter({ hasText: row.help_words }),
    ).toBeVisible();
  await expect(views(target)).toHaveCount(0);
});

test("a return the AEAT holds that nothing here is linked to opens to read only", async ({
  page: target,
}) => {
  const aeat = list().rows.find((row) => row.group === "aeat_unlinked");
  if (!aeat) throw new Error("the list holds no return seen only at the AEAT");
  const grid = await openList(target);
  await target
    .getByRole("searchbox", {
      name: label("desktop.declarations.search.label"),
    })
    .fill(aeat.modelo);
  await expect(
    grid.getByRole("row").filter({ hasText: aeat.group_words }).first(),
  ).toBeVisible();
  await rowsOf(grid, aeat.modelo)
    .filter({ hasText: aeat.state_words })
    .dblclick();
  const dialog = target.getByRole("dialog", { name: aeat.modelo_title });
  await expect(dialog).toContainText(aeat.state_words);
  if (aeat.period_words) await expect(dialog).toContainText(aeat.period_words);
  for (const note of aeat.aeat_filing?.notes ?? [])
    await expect(dialog).toContainText(note);
  // Nothing is linked, made or sent from it: closing is all it offers.
  for (const name of await dialog.getByRole("button").allInnerTexts())
    expect([label("workspace.modelo.key.close"), ""]).toContain(name.trim());
  await expect(views(target)).toHaveCount(0);
});
