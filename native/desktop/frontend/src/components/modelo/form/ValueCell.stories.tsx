import type { Meta, StoryObj } from "@storybook/react-vite";
import { useState } from "react";
import form130 from "../../../dev/fixtures/modelo/modelo-130-1T-en.json";
import type {
  ModeloEditValueGrammarV1,
  ModeloWorkbenchFormProjectionV1,
  PublicModeloFormField,
} from "../../../shell/modeloContract";
import { placedFields, type StagedEdit } from "./session";
import { ValueCell, type EditRequest } from "./ValueCell";

// A box's editor for each kind of value, on grammars in the shape the edit
// baseline serves; the application's reads hold no address of most of these
// kinds. Nothing is read or sent from these stories.

const F130 = form130 as unknown as ModeloWorkbenchFormProjectionV1;
const BASE = placedFields(F130.form.form).find(
  ({ field }) => field.takes_typed_value,
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

const choices = (...codes: string[]) => ({
  choices: codes.map((code) => ({ code })),
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

const opened = (served: ModeloEditValueGrammarV1): Story => ({
  render: () => <Cell served={served} />,
});

export const Money = opened(figure("money", { max_fraction_digits: 2 }));
export const Decimal = opened(figure("decimal"));
export const Integer = opened(
  grammar("integer", {
    family: "integer",
    channel: "decimal",
    max_fraction_digits: 0,
  }),
);
export const RatioPercent = opened(
  figure("ratio", { ratio_unit: "percent", maximum: "100" }),
);
export const RatioFraction = opened(
  figure("ratio", { ratio_unit: "fraction", maximum: "1" }),
);
export const RatioUndeclared = opened(
  figure("ratio", { ratio_unit: "undeclared" }),
);
export const Boolean = opened(
  grammar("boolean", { family: "boolean", channel: "decimal" }),
);
export const Text = opened(grammar("text"));
export const Name = opened(grammar("name"));
export const Nif = opened(grammar("nif"));
export const NifIva = opened(grammar("nif_iva"));
export const Iban = opened(grammar("iban"));
export const Bic = opened(grammar("bic"));
export const CountryCode = opened(grammar("country_code"));
export const CountryCodeChoices = opened(
  grammar("country_code", choices("ES", "PT", "FR")),
);
export const PeriodCode = opened(
  grammar("period_code", choices("1T", "2T", "3T", "4T")),
);
export const CcaaCode = opened(grammar("ccaa_code", choices("01", "02", "09")));
export const ProvinceCode = opened(
  grammar("province_code", choices("08", "17", "25", "43")),
);
export const PostalCode = opened(grammar("postal_code"));
export const MunicipalityCode = opened(grammar("municipality_code"));

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
        normalisations: [],
        beforeChanged: false,
      })}
    />
  ),
};

export const DateReadOnly: Story = {
  render: () => (
    <Cell
      served={grammar("date", { family: "date", channel: "unavailable" })}
      editable={false}
    />
  ),
};
