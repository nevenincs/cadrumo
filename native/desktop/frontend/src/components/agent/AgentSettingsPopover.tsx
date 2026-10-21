import { useId, useState, type ReactElement } from "react";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { startingSelection } from "../../shell/agentCatalog";
import { useStrings } from "../../shell/strings";
import { ProviderSelect } from "./ProviderSelect";
import type { AgentSelection, ModelOption, ProviderOption } from "./types";

/**
 * The provider, the model and the effort of the conversation, chosen in a
 * popover opened from `children`. Every list is what it is given, however
 * long: the providers there are, the models of the one chosen, and the
 * efforts of the model chosen. A provider reached more than one way is more
 * than one entry of the first list, and choosing an entry chooses the way.
 * It holds no choice of its own: every change is handed to `onChange`, and
 * what it shows is `selection`.
 */
export function AgentSettingsPopover({
  providers,
  models,
  selection,
  onChange,
  children,
}: {
  providers: readonly ProviderOption[];
  /** Each way's models, by way id. */
  models: Readonly<Record<string, readonly ModelOption[]>>;
  selection: AgentSelection;
  onChange: (selection: AgentSelection) => void;
  /** The one element that opens the popover. */
  children: ReactElement;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const providerId = useId();
  const modelId = useId();
  const effortId = useId();
  const provider = providers.find((held) => held.id === selection.providerId);
  const way = provider?.ways.find((held) => held.id === selection.wayId);
  const offered = models[selection.wayId] ?? [];
  const model = offered.find((option) => option.id === selection.modelId);
  const efforts = way?.modelWritten?.efforts ?? model?.efforts ?? [];
  const hasDefault = Boolean(model?.defaultEffort);

  // An entry of the list is one lane of one provider, and it starts with
  // that lane's own starting model.
  const chooseEntry = (wayId: string) => {
    for (const next of providers) {
      const chosen = next.ways.find((held) => held.id === wayId);
      if (!chosen) continue;
      if (!chosen.selectable) return;
      const first = startingSelection(next, chosen, models[chosen.id] ?? []);
      if (first) onChange(first);
      return;
    }
  };
  const chooseModel = (next: string) => {
    const chosen = offered.find((option) => option.id === next);
    if (!chosen) return;
    // An effort the person chose carries over where the new model takes it;
    // otherwise the new model's own default applies.
    const effort =
      selection.effort &&
      chosen.efforts.some((held) => held.id === selection.effort)
        ? selection.effort
        : undefined;
    onChange({
      providerId: selection.providerId,
      wayId: selection.wayId,
      modelId: chosen.id,
      ...(effort ? { effort } : {}),
    });
  };

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        side="top"
        align="start"
        aria-label={t("desktop.agent.settings_title")}
        className="grid w-settings grid-cols-1 gap-3"
      >
        <Field>
          <FieldLabel htmlFor={providerId}>
            {t("desktop.agent.provider")}
          </FieldLabel>
          <ProviderSelect
            id={providerId}
            providers={providers}
            value={selection.wayId}
            onChange={chooseEntry}
          />
          {/* What the lane has been proven to do on this computer. */}
          {way?.capabilities && way.capabilities.length > 0 && (
            <FieldDescription>
              {t("desktop.agent.capabilities", {
                // In the language the shell shows, which the page carries.
                list: new Intl.ListFormat(
                  document.documentElement.lang || undefined,
                  { type: "conjunction" },
                ).format(way.capabilities),
              })}
            </FieldDescription>
          )}
        </Field>
        <Field>
          <FieldLabel htmlFor={modelId}>{t("desktop.agent.model")}</FieldLabel>
          {way?.modelWritten ? (
            <>
              <Input
                id={modelId}
                controlSize="sm"
                value={selection.modelId}
                spellCheck={false}
                autoCapitalize="off"
                autoCorrect="off"
                autoComplete="off"
                onChange={(event) =>
                  onChange({ ...selection, modelId: event.target.value })
                }
              />
              <FieldDescription>
                {t("desktop.agent.model_written")}
              </FieldDescription>
            </>
          ) : offered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.agent.no_models")}
            </p>
          ) : (
            <NativeSelect
              id={modelId}
              controlSize="sm"
              value={selection.modelId}
              onChange={(event) => chooseModel(event.target.value)}
            >
              {offered.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.name}
                </option>
              ))}
            </NativeSelect>
          )}
          {model?.description && (
            <FieldDescription>{model.description}</FieldDescription>
          )}
        </Field>
        {efforts.length > 0 && (
          <Field>
            <FieldLabel htmlFor={effortId}>
              {t("desktop.agent.effort")}
            </FieldLabel>
            <NativeSelect
              id={effortId}
              controlSize="sm"
              value={selection.effort ?? model?.defaultEffort ?? ""}
              onChange={(event) => {
                const effort = event.target.value;
                if (effort === "")
                  onChange({
                    providerId: selection.providerId,
                    wayId: selection.wayId,
                    modelId: selection.modelId,
                  });
                else if (efforts.some((held) => held.id === effort))
                  onChange({ ...selection, effort });
              }}
            >
              {/* The provider's own default, where the catalog names none. */}
              {!hasDefault && (
                <option value="">{t("desktop.agent.effort_default")}</option>
              )}
              {efforts.map((effort) => (
                <option key={effort.id} value={effort.id}>
                  {effort.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
      </PopoverContent>
    </Popover>
  );
}
