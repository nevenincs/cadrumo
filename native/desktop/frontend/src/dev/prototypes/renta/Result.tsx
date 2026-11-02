import { useId } from "react";
import { BoxNumber } from "@/components/modelo/form/BoxNumber";
import { cn } from "@/components/ui/cn";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio";
import type {
  ModeloFormElectionQuestion,
  ModeloFormResultView,
  PublicModeloFormField,
} from "@/shell/modeloContract";
import { useStrings } from "@/shell/strings";
import { BoxLine } from "./BoxLine";
import { Gap } from "./Gap";

// The result of the return and how it is settled. The header line is the
// served result view in its own words; a result that could not be
// calculated reads so, never as zero. Settlement questions are drawn from
// whatever elections the export offer serves, by their served words, so the
// window holds no list of its own.

function ResultLine({
  view,
  note,
}: {
  view: ModeloFormResultView;
  note?: string;
}) {
  return (
    <div
      data-state={view.state}
      data-direction={view.direction}
      className="flex flex-col gap-1 rounded-md border border-border px-3 py-2"
    >
      <div className="flex items-center gap-3">
        <BoxNumber box={view.box} />
        <span
          className={cn(
            "text-base font-semibold",
            view.state !== "stated" && "text-muted-foreground",
          )}
        >
          {view.short_text}
        </span>
      </div>
      {view.help.map((line) => (
        <span key={line} className="text-xs text-muted-foreground">
          {line}
        </span>
      ))}
      {note && <span className="text-xs text-faint">{note}</span>}
    </div>
  );
}

function Elections({
  questions,
}: {
  questions: readonly ModeloFormElectionQuestion[];
}) {
  const base = useId();
  return (
    <div className="flex flex-col gap-3">
      {questions.map((question) => (
        <fieldset key={question.election} className="flex flex-col gap-1.5">
          <legend
            id={`${base}-${question.election}`}
            className="text-sm font-medium"
          >
            {question.words}
          </legend>
          <RadioGroup
            defaultValue={question.default ?? undefined}
            aria-labelledby={`${base}-${question.election}`}
          >
            {question.choices.map((choice) => (
              <label
                key={choice.value}
                className="flex items-center gap-2 text-sm"
              >
                <RadioGroupItem value={choice.value} />
                {choice.words}
              </label>
            ))}
          </RadioGroup>
        </fieldset>
      ))}
    </div>
  );
}

export function Result({
  header,
  fields,
  composed = false,
  elections,
  example,
}: {
  header: ModeloFormResultView;
  fields: readonly PublicModeloFormField[];
  composed?: boolean;
  elections: readonly ModeloFormElectionQuestion[];
  example?: readonly ModeloFormElectionQuestion[];
}) {
  const t = useStrings();
  return (
    <section className="flex max-w-3xl flex-col gap-4 p-4">
      <h2 className="text-lg font-semibold">
        {t("workspace.renta.outline.result")}
      </h2>
      <ResultLine
        view={header}
        note={composed ? t("desktop.renta.proto.result.composed") : undefined}
      />
      <ul className="rounded-md border border-border px-3">
        {fields.map((field) => (
          <BoxLine key={field.state_digest} field={field} />
        ))}
      </ul>
      <Gap operation="modelo.work.form: box 0700 served as optional with no formula" />
      <h3 className="text-base font-semibold">
        {t("workspace.renta.result.settlement")}
      </h3>
      {elections.length > 0 ? (
        <Elections questions={elections} />
      ) : (
        <Gap operation="modelo.work.form export_offer.elections for Modelo 100 (refund account, direct debit, 60/40 split)" />
      )}
      {example && (
        <div className="flex flex-col gap-2 rounded-md border border-dashed border-border p-3">
          <span className="text-xs text-faint">
            {t("desktop.renta.proto.result.example")}
          </span>
          <Elections questions={example} />
        </div>
      )}
    </section>
  );
}
