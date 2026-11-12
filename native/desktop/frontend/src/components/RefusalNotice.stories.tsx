import type { Meta, StoryObj } from "@storybook/react-vite";
import { expect, fn, within } from "storybook/test";
import type { ActionArgumentSnapshot } from "../shell/modeloContract/modelo";
import type { ServedRefusal, ServedVerdict } from "../shell/refusal";
import { RefusalNotice } from "./RefusalNotice";

// The refusal notice over fixture verdicts that already carry the words the
// backend is to serve on each action. Every sentence here is fixture text;
// the notice adds none of its own beyond the generic unroutable reason.

const REFUSAL = "Fixture refusal: this step cannot go ahead yet.";

const bound = (argument_name: string): ActionArgumentSnapshot => ({
  argument_name,
  status: "resolved",
  value: "fixture-value",
  source: null,
  source_key: null,
  source_evidence_id: null,
});

const missing = (argument_name: string): ActionArgumentSnapshot => ({
  argument_name,
  status: "missing",
  value: null,
  source: null,
  source_key: null,
  source_evidence_id: null,
});

function verdict(fields: Partial<ServedVerdict>): ServedVerdict {
  return {
    failed_condition_id: "fixture.condition",
    evidence: [],
    action_id: null,
    argument_bindings: [],
    missing_argument_names: [],
    conditionality: "not_applicable",
    no_recovery_outcome: null,
    no_recovery_words: null,
    no_recovery_words_language: null,
    action_words: null,
    action_words_language: null,
    target_operation_ids: [],
    ...fields,
  };
}

const primary = {
  action_id: "operator.fixture.create",
  target_operation_ids: ["modelo.work.create"],
  argument_bindings: [bound("work_unit_id")],
  missing_argument_names: [],
  conditionality: "immediate",
  action_words: "Create the earlier record",
  action_words_language: "en",
} satisfies Partial<ServedVerdict>;

const refused = (v: ServedVerdict | null): ServedRefusal => ({
  refusal_words: REFUSAL,
  refusal_words_language: "en",
  verdict: v,
});

const meta = {
  title: "Shared/RefusalNotice",
  component: RefusalNotice,
  parameters: { surface: "card" },
  args: { onAction: fn(), refusal: refused(null) },
  decorators: [
    (Story) => (
      <div className="max-w-dialog">
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof RefusalNotice>;
export default meta;
type Story = StoryObj<typeof meta>;

/** Refusal words only: no verdict, so no way out is drawn. */
export const WordsOnly: Story = {};

export const PrimaryOnly: Story = {
  args: { refusal: refused(verdict(primary)) },
  play: async ({ canvasElement, args }) => {
    const button = within(canvasElement).getByRole("button", {
      name: "Create the earlier record",
    });
    button.click();
    await expect(args.onAction).toHaveBeenCalledWith(
      expect.objectContaining({
        kind: "follow",
        target_operation_ids: ["modelo.work.create"],
        place: { page: "declarations", definition: "modelo.work.create" },
      }),
    );
  },
};

/** The primary way out first, then the alternatives in the order served. */
export const PrimaryAndTwoAlternatives: Story = {
  args: {
    refusal: refused(
      verdict({
        ...primary,
        alternative_actions: [
          {
            action_id: "operator.fixture.review",
            target_operation_ids: ["ledger.evidence.review.list"],
            argument_bindings: [],
            missing_argument_names: [],
            conditionality: "immediate",
            action_words: "Review the documents",
            action_words_language: "en",
          },
          {
            action_id: "operator.fixture.verify",
            target_operation_ids: [
              "modelo.work.revision",
              "modelo.work.verify",
            ],
            argument_bindings: [bound("work_unit_id")],
            missing_argument_names: [],
            conditionality: "immediate",
            action_words: "Check it again",
            action_words_language: "en",
          },
        ],
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    const names = within(canvasElement)
      .getAllByRole("button")
      .map((button) => button.textContent);
    await expect(names).toEqual([
      "Create the earlier record",
      "Review the documents",
      "Check it again",
    ]);
  },
};

/** Served as needing arguments: marked as opening a form, never as certain. */
export const ConditionalAction: Story = {
  args: {
    refusal: refused(
      verdict({
        ...primary,
        conditionality: "requires_arguments",
        argument_bindings: [bound("work_unit_id"), missing("period")],
        missing_argument_names: ["period"],
      }),
    ),
  },
};

/** Missing arguments: the control asks for the destination's form, with the
 * names it lacks, and never submits. */
export const MissingArguments: Story = {
  args: {
    refusal: refused(
      verdict({
        ...primary,
        conditionality: "requires_arguments",
        argument_bindings: [missing("value")],
        missing_argument_names: ["value"],
      }),
    ),
  },
  play: async ({ canvasElement, args }) => {
    within(canvasElement)
      .getByRole("button", { name: "Create the earlier record" })
      .click();
    await expect(args.onAction).toHaveBeenCalledWith(
      expect.objectContaining({ kind: "form", missing: ["value"] }),
    );
  },
};

/** An action the window admits no place for: its words, disabled, with the
 * generic reason. */
export const UnroutableAction: Story = {
  args: {
    refusal: refused(
      verdict({
        ...primary,
        alternative_actions: [
          {
            action_id: "operator.fixture.attest",
            target_operation_ids: ["live.notifications.list"],
            argument_bindings: [],
            missing_argument_names: ["value"],
            conditionality: "requires_arguments",
            action_words: "State the value yourself",
            action_words_language: "en",
          },
        ],
      }),
    ),
  },
  play: async ({ canvasElement, args }) => {
    const button = within(canvasElement).getByRole("button", {
      name: "State the value yourself",
    });
    await expect(button).toHaveAttribute("aria-disabled", "true");
    button.click();
    await expect(args.onAction).not.toHaveBeenCalled();
  },
};

/** No way out: the served sentence, and no control. */
export const NoWayOut: Story = {
  args: {
    refusal: refused(
      verdict({
        no_recovery_outcome: "terminal",
        no_recovery_words:
          "Fixture outcome: nothing in the app can change this.",
        no_recovery_words_language: "en",
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    const canvas = within(canvasElement);
    await expect(
      canvas.getByText("Fixture outcome: nothing in the app can change this."),
    ).toBeInTheDocument();
    await expect(canvas.queryByRole("button")).not.toBeInTheDocument();
    await expect(
      canvasElement.querySelector("[data-no-recovery='terminal']"),
    ).not.toBeNull();
  },
};

/** The served operations route the action: the first the window admits, in
 * served order, names its place. */
export const RoutedByServedOperations: Story = {
  args: {
    refusal: refused(
      verdict({
        ...primary,
        target_operation_ids: ["live.notifications.list", "modelo.work.amend"],
      }),
    ),
  },
  play: async ({ canvasElement, args }) => {
    const button = within(canvasElement).getByRole("button", {
      name: "Create the earlier record",
    });
    await expect(button).toHaveAttribute(
      "data-target-operation",
      "modelo.work.amend",
    );
    button.click();
    await expect(args.onAction).toHaveBeenCalledWith(
      expect.objectContaining({
        place: { page: "declarations", definition: "modelo.work.amend" },
      }),
    );
  },
};

/** A place the host cannot open from here: the words stand, disabled, with
 * the generic reason. */
export const HostCannotOpen: Story = {
  args: {
    refusal: refused(verdict(primary)),
    opens: () => false,
  },
  play: async ({ canvasElement, args }) => {
    const button = within(canvasElement).getByRole("button", {
      name: "Create the earlier record",
    });
    await expect(button).toHaveAttribute("aria-disabled", "true");
    button.click();
    await expect(args.onAction).not.toHaveBeenCalled();
  },
};

/** The decision is the person's own: shown as served, never as an action. */
export const OperatorDecision: Story = {
  args: {
    refusal: refused(
      verdict({
        no_recovery_outcome: "operator_decision",
        no_recovery_words: "Fixture outcome: this is yours to decide.",
        no_recovery_words_language: "en",
      }),
    ),
  },
};

/** Before the backend serves action words: the refusal words, no control and
 * no invented label. */
export const ActionWithoutServedWords: Story = {
  args: {
    refusal: refused(
      verdict({
        ...primary,
        action_words: null,
        action_words_language: null,
      }),
    ),
  },
  play: async ({ canvasElement }) => {
    await expect(
      within(canvasElement).queryByRole("button"),
    ).not.toBeInTheDocument();
  },
};
