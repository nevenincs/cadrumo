import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import { expect, waitFor } from "storybook/test";
import form130 from "@fixtures/modelo/modelo-130-1T-en.json" with { type: "json" };
import type { ModeloEditValueGrammarV1 } from "../../../shell/modeloContract/modeloEditWork";
import type {
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract/modeloWorkForm";
import { placedFields, type StagedEdit } from "./session";
import { ValueCell, type EditRequest } from "./ValueCell";

// A box's editor for each kind of value, on grammars in the shape the edit
// baseline serves; the application's reads hold no address of most of these
// kinds. Nothing is read or sent from these stories.

const F130 = form130 as unknown as ModeloWorkbenchFormProjectionV1;
// A box whose value is typed in directly: a box fed by a source asks first
// whether to correct it there, and shows no editor until that is answered.
const BASE = placedFields(F130.form.form).find(
  ({ field }) =>
    field.takes_typed_value && field.editability === "editable_value",
)?.field as PublicModeloFormField;

const grammar = (
  data_type: string,
  over: Partial<ModeloEditValueGrammarV1> = {},
): ModeloEditValueGrammarV1 => ({
  data_type,
  family: "text",
  channel: "text",
  max_fraction_digits: null,
  sign: "any",
  minimum: null,
  maximum: null,
  choices: null,
  min_length: null,
  max_length: null,
  pattern: null,
  ratio_unit: null,
  money_operand_bound: false,
  required: false,
  constraints_declared: false,
  ...over,
});

const figure = (
  data_type: string,
  over: Partial<ModeloEditValueGrammarV1> = {},
) => grammar(data_type, { family: "decimal", channel: "decimal", ...over });

const provinces = (...codes: string[]) => ({
  choices: codes.map((code) => ({
    code,
    word: `application.modelo.edit_choice.province_code.${code}`,
  })),
});

function Cell({
  served,
  staged,
  editable = true,
}: {
  served: ModeloEditValueGrammarV1;
  staged?: (field: PublicModeloFormField) => StagedEdit;
  editable?: boolean;
}) {
  const field = {
    ...BASE,
    data_type: served.data_type,
  } as PublicModeloFormField;
  const [editing, setEditing] = useState<EditRequest | null>(
    editable && !staged ? {} : null,
  );
  return (
    <div className="flex justify-start p-4">
      <ValueCell
        field={field}
        staged={staged?.(field)}
        grammar={served}
        editable={editable}
        editing={editing}
        onEditingChange={setEditing}
        enter={async () => ({ kind: "staged" })}
        onDone={() => undefined}
      />
    </div>
  );
}

const meta: Meta = {
  title: "Modelo/Form/Value cell",
  parameters: { layout: "padded" },
};
export default meta;
type Story = StoryObj;

/** What the open editor holds: the control, the keyboard it asks for, and the
 * list a choice offers. */
type Editor = {
  control: "input" | "select";
  inputMode?: "decimal" | "numeric";
  capitals?: true;
  options?: string[];
};

// The editor is what each story is for, so a story that shows anything else
// (a box fed by a source asks first, one that takes nothing shows a dash)
// fails its play.
const showsEditor =
  (expected: Editor): Story["play"] =>
  async ({ canvasElement }) => {
    await waitFor(() =>
      expect(
        canvasElement.querySelector('[data-slot="modelo-value-editor"]'),
      ).not.toBeNull(),
    );
    const holder = canvasElement.querySelector<HTMLElement>(
      '[data-slot="modelo-value-editor"]',
    )!;
    const control = holder.querySelector<HTMLElement>("input, select")!;
    await expect(control.tagName.toLowerCase()).toBe(expected.control);
    await expect(control.getAttribute("inputmode")).toBe(
      expected.inputMode ?? null,
    );
    await expect(control.getAttribute("autocapitalize")).toBe(
      expected.capitals ? "characters" : null,
    );
    if (control instanceof HTMLSelectElement)
      await expect([...control.options].map((option) => option.value)).toEqual([
        "",
        ...(expected.options ?? []),
      ]);
    await expect(holder.contains(document.activeElement)).toBe(true);
    await expect(document.querySelector('[role="dialog"]')).toBeNull();
  };

const opened = (served: ModeloEditValueGrammarV1, expected: Editor): Story => ({
  render: () => <Cell served={served} />,
  play: showsEditor(expected),
});

const typing = (inputMode?: "decimal" | "numeric"): Editor => ({
  control: "input",
  inputMode,
});
const capitals: Editor = { control: "input", capitals: true };

export const Money = opened(
  figure("money", { max_fraction_digits: 2 }),
  typing("decimal"),
);
export const Decimal = opened(figure("decimal"), typing("decimal"));
export const Integer = opened(
  grammar("integer", {
    family: "integer",
    channel: "decimal",
    max_fraction_digits: 0,
  }),
  typing("numeric"),
);
export const RatioPercent = opened(
  figure("ratio", { ratio_unit: "percent", maximum: "100" }),
  typing("decimal"),
);
export const RatioFraction = opened(
  figure("ratio", { ratio_unit: "fraction", maximum: "1" }),
  typing("decimal"),
);
export const RatioUndeclared = opened(
  figure("ratio", { ratio_unit: "undeclared" }),
  typing("decimal"),
);
export const Boolean = opened(
  grammar("boolean", { family: "boolean", channel: "decimal" }),
  { control: "select", options: ["1", "0"] },
);
export const Text = opened(grammar("text"), typing());
export const Name = opened(grammar("name"), typing());
export const Nif = opened(grammar("nif"), capitals);
export const NifIva = opened(grammar("nif_iva"), capitals);
export const Iban = opened(grammar("iban"), capitals);
export const Bic = opened(grammar("bic"), capitals);
export const CountryCode = opened(grammar("country_code"), capitals);
export const PeriodCode = opened(grammar("period_code"), typing());
export const CcaaCode = opened(grammar("ccaa_code"), typing());
export const ProvinceCode = opened(
  grammar("province_code", provinces("08", "17", "25", "43")),
  { control: "select", options: ["08", "17", "25", "43"] },
);
export const PostalCode = opened(grammar("postal_code"), typing());
export const MunicipalityCode = opened(grammar("municipality_code"), typing());

export const BooleanStaged: Story = {
  render: () => (
    <Cell
      served={grammar("boolean", { family: "boolean", channel: "decimal" })}
      staged={(field) => ({
        key: "c:synthetic",
        address: { kind: "scalar", casilla_id: "synthetic" },
        field,
        intent: {
          kind: "set_typed_value",
          change: "set",
          value: true,
          comparable: true,
        },
        entry: "1",
        read: null,
        normalisations: [],
        beforeChanged: false,
      })}
    />
  ),
  play: async ({ canvasElement }) => {
    // The staged answer is shown in place of the box's value, no editor.
    const face = canvasElement.querySelector("button")!;
    await expect(face.disabled).toBe(false);
    await expect(face.textContent).not.toBe(BASE.value_text);
    await expect(
      canvasElement.querySelector('[data-slot="modelo-value-editor"]'),
    ).toBeNull();
  },
};

export const DateReadOnly: Story = {
  render: () => (
    <Cell
      served={grammar("date", { family: "date", channel: "unavailable" })}
      editable={false}
    />
  ),
  play: async ({ canvasElement }) => {
    const face = canvasElement.querySelector("button")!;
    await expect(face.disabled).toBe(true);
    await expect(
      canvasElement.querySelector('[data-slot="modelo-value-editor"]'),
    ).toBeNull();
  },
};
