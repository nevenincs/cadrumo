import { seededUnit } from "@/dev/seededUnits";
import type { Meta, StoryObj } from "@storybook/react-vite";
import { useRef } from "react";
import { expect, userEvent, waitFor, within } from "storybook/test";
import { modeloFixture, type ModeloShape } from "@/dev/modeloFixture";
import { translator } from "../../../shell/strings";
import type { ModeloPort } from "../../../shell/modelo";
import type { OutputLanguage } from "../../../shell/modeloContract/modelo";
import { WorkspaceScreen } from "./WorkspaceScreen";

// A source disagreement answered in the real workspace, over the envelopes
// the application read for a synthetic filer: the first-quarter Modelo 130
// after a value typed over box 06 replaced a different ledger figure. The
// check line states the disagreement and offers the answer the application
// says it takes; accepting it with a reason, revoking the acceptance and the
// refusals are answered as the application answered them.

const UNIT = seededUnit("130");

const language = (globals: Record<string, unknown>) =>
  String(globals.locale ?? "en") as OutputLanguage;

function Check({
  shape,
  locale,
}: {
  shape: ModeloShape;
  locale: OutputLanguage;
}) {
  const port = useRef<ModeloPort | null>(null);
  port.current ??= modeloFixture({
    say: () => undefined,
    translate: translator,
    wait: async () => undefined,
    signedIn: () => true,
    shape,
  });
  return (
    <div className="flex h-full min-h-0 flex-col">
      <WorkspaceScreen
        port={port.current}
        workUnitId={UNIT}
        language={locale}
        locale={locale}
        onBack={() => undefined}
        onOpenSurface={() => undefined}
        canOpenSurface={() => true}
        openLink={() => undefined}
        initialView="check"
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Disagreements",
  parameters: { fill: true, layout: "fullscreen" },
};
export default meta;
type Story = StoryObj;

/** The answer the check offers, once the workspace has read the form. */
const offered = (canvasElement: HTMLElement, answer: "accept" | "revoke") =>
  waitFor(
    () => {
      const found = canvasElement.querySelector<HTMLElement>(
        `[data-answer-offered=${answer}]`,
      );
      if (!found) throw new Error(`the check offers no ${answer}`);
      return found;
    },
    { timeout: 15_000 },
  );

/** The dialog the offered answer opened. */
const dialog = () =>
  waitFor(() => {
    const found = document.querySelector<HTMLElement>("[data-disagreement]");
    if (!found) throw new Error("the answer is not open");
    return found;
  });

/** The button that sends the answer the dialog holds. */
const answerButton = (open: HTMLElement) => {
  const found = open.querySelector<HTMLElement>("[data-answer-confirm]");
  if (!found) throw new Error("the dialog offers no way to answer");
  return found;
};

/** Accepts the disagreement with a reason and waits for the form read again. */
const accept = async (canvasElement: HTMLElement) => {
  await userEvent.click(await offered(canvasElement, "accept"));
  const open = await dialog();
  const confirm = answerButton(open);
  // Nothing is sent without a reason.
  expect(confirm).toBeDisabled();
  await userEvent.type(
    within(open).getByRole("textbox"),
    "The ledger misses an invoice booked late.",
  );
  await userEvent.click(confirm);
};

export const Offered: Story = {
  name: "A disagreement holding the check offers to accept it",
  render: (_, { globals }) => (
    <Check shape="disagreement" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    const button = await offered(canvasElement, "accept");
    // The line is the application's own: its sentence names box 06.
    expect(button.closest("li")?.textContent).toContain("06");
    expect(
      canvasElement.querySelector("[data-answer-offered=revoke]"),
    ).toBeNull();
    // No answer was given yet, so none is listed.
    expect(canvasElement.querySelector("[data-answer-state]")).toBeNull();
  },
};

export const Accepted: Story = {
  name: "Accepted with a reason: the line offers to revoke, the answer is listed",
  render: (_, { globals }) => (
    <Check shape="disagreement" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await accept(canvasElement);
    await offered(canvasElement, "revoke");
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-answer-state=active]"),
      ).not.toBeNull(),
    );
    expect(document.querySelector("[data-disagreement]")).toBeNull();
  },
};

export const Revoked: Story = {
  name: "Revoked at the revision the list served: the line offers to accept again",
  render: (_, { globals }) => (
    <Check shape="disagreement" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await accept(canvasElement);
    await userEvent.click(await offered(canvasElement, "revoke"));
    const open = await dialog();
    // What the acceptance covers is the application's sentence.
    await waitFor(() =>
      expect(open.querySelector("[data-answer]")).not.toBeNull(),
    );
    const confirm = answerButton(open);
    await waitFor(() => expect(confirm).toBeEnabled());
    await userEvent.click(confirm);
    await offered(canvasElement, "accept");
    await waitFor(() =>
      expect(
        canvasElement.querySelector("[data-answer-state=revoked]"),
      ).not.toBeNull(),
    );
  },
};

export const Raced: Story = {
  name: "Refused as already accepted elsewhere: the application's words",
  render: (_, { globals }) => (
    <Check shape="disagreement-raced" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await accept(canvasElement);
    const open = await dialog();
    await waitFor(() =>
      expect(within(open).getAllByRole("alert")[0]?.textContent).toBeTruthy(),
    );
    // Read again, the declaration shows the acceptance made elsewhere.
    await offered(canvasElement, "revoke");
  },
};

export const Unknown: Story = {
  name: "An acceptance whose settlement was not seen is sent no more",
  render: (_, { globals }) => (
    <Check shape="disagreement-unknown" locale={language(globals)} />
  ),
  play: async ({ canvasElement }) => {
    await accept(canvasElement);
    const open = await dialog();
    await waitFor(() => expect(answerButton(open)).toBeDisabled());
  },
};
