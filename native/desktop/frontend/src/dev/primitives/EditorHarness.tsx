import { useMemo, useState } from "react";
import { checkField } from "@/components/editors/fieldCheck";
import { TypedField } from "@/components/editors/TypedField";
import { TooltipProvider } from "@/components/ui/tooltip";
import type { FieldSpec } from "@/shared/fieldKind";
import { StringsContext, translator } from "@/shell/strings";

/** One typed editor alone, with what it holds and what its check says beside
 * it, from the page's address. */
export function EditorHarness({ params }: { params: URLSearchParams }) {
  const translate = useMemo(
    () => translator(params.get("locale") ?? "en"),
    [params],
  );
  const field = useMemo(
    () => JSON.parse(params.get("field") ?? "{}") as FieldSpec,
    [params],
  );
  const [value, setValue] = useState(params.get("value") ?? "");
  const [blurs, setBlurs] = useState(0);
  const checked = checkField(field, value);
  return (
    <StringsContext.Provider value={translate}>
      <TooltipProvider>
        <main className="max-w-80 p-6">
          <label htmlFor="entry">Entry</label>
          <TypedField
            id="entry"
            field={field}
            value={value}
            onChange={setValue}
            onBlur={() => setBlurs((count) => count + 1)}
            required
            mode={params.get("mode") === "lexeme" ? "lexeme" : "normalise"}
          />
          <button type="button">Elsewhere</button>
          <output data-testid="held">{value}</output>
          <output data-testid="blurs">{blurs}</output>
          <output data-testid="checked">
            {checked.kind === "value"
              ? `value ${checked.value}`
              : checked.kind === "empty"
                ? "empty"
                : `refused ${checked.refusal.key}`}
          </output>
        </main>
      </TooltipProvider>
    </StringsContext.Provider>
  );
}
