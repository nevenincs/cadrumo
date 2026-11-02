import { useId, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio";
import { Switch } from "@/components/ui/switch";
import { useStrings } from "@/shell/strings";
import type { ElectionWords } from "./fixtures";
import { Gap } from "./Gap";

// The imputation criterion of an economic activity, one dated profile fact
// per tax year. Undeclared is its own state: nothing is chosen, the proposed
// answer is marked as the backend proposes it, and the boxes that read the
// criterion stay unresolved. Saving needs an operation the backend does not
// register yet, so the button is drawn and disabled.

export type ElectionState =
  { kind: "undeclared" } | { kind: "stated"; value: string; year: number };

export function Election({
  words,
  state,
}: {
  words: ElectionWords;
  state: ElectionState;
}) {
  const t = useStrings();
  const titleId = useId();
  const yearId = useId();
  const [choice, setChoice] = useState(
    state.kind === "stated" ? state.value : "",
  );
  const { question } = words;
  return (
    <section
      aria-labelledby={titleId}
      className="flex max-w-2xl flex-col gap-4 p-4"
    >
      <h2 id={titleId} className="text-lg font-semibold">
        {t("workspace.renta.election.title")}
      </h2>
      <div
        data-state={state.kind}
        className="rounded-md border border-border px-3 py-2 text-sm"
      >
        {state.kind === "undeclared"
          ? t("workspace.renta.election.undeclared")
          : t("workspace.renta.election.stated", { year: state.year })}
      </div>
      <p className="text-sm">{question.prompt}</p>
      <p className="text-sm text-muted-foreground">{question.help}</p>
      <RadioGroup
        value={choice}
        onValueChange={setChoice}
        aria-labelledby={titleId}
      >
        {question.choices.map((option) => (
          <label
            key={option.value}
            className="flex items-start gap-2 rounded-md border border-border p-2"
          >
            <RadioGroupItem value={option.value} className="mt-0.5" />
            <span className="flex min-w-0 flex-col gap-0.5">
              <span className="flex items-center gap-2 text-sm font-medium">
                {option.label}
                {option.value === question.proposed && (
                  <Badge variant="soft">
                    {t("workspace.renta.election.proposed")}
                  </Badge>
                )}
              </span>
              <span className="text-xs text-muted-foreground">
                {option.description}
              </span>
            </span>
          </label>
        ))}
      </RadioGroup>
      <div className="flex flex-col gap-1">
        <label htmlFor={yearId} className="text-sm font-medium">
          {t("desktop.renta.proto.election.year")}
        </label>
        <Input
          id={yearId}
          inputMode="numeric"
          className="w-28"
          defaultValue={state.kind === "stated" ? String(state.year) : ""}
          aria-describedby={`${yearId}-help`}
        />
        <span id={`${yearId}-help`} className="text-xs text-muted-foreground">
          {words.year.help}
        </span>
      </div>
      <label className="flex items-start gap-2 text-sm">
        <Switch className="mt-0.5" />
        {words.accounting.prompt}
      </label>
      <Button disabled className="self-start">
        {t("desktop.renta.proto.election.save")}
      </Button>
      <Gap operation="user-profile: a registered write for irpf.activity_income_imputation_criterion" />
    </section>
  );
}
