import { useId, useState, type ReactElement } from "react";
import { RadioGroup as RadioGroupPrimitive } from "radix-ui";
import { Field, FieldLabel } from "@/components/ui/field";
import { Icon } from "@/components/ui/icon";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import {
  SegmentedControl,
  SegmentedControlItem,
} from "@/components/ui/segmented-control";
import { useStrings } from "../../shell/strings";
import type { AgentSelection, ModelOption, ProviderOption } from "./types";

/** The effort a model starts at: its default where it accepts that, else
 * its first, else none. */
function startingEffort(model: ModelOption | undefined): string | undefined {
  if (!model) return undefined;
  if (model.defaultEffort && model.efforts.includes(model.defaultEffort))
    return model.defaultEffort;
  return model.efforts[0];
}

/**
 * The provider, model and effort of the conversation, chosen in a popover
 * opened from `children`. It holds no choice of its own: every change is
 * handed to `onChange`, and what it shows is `selection`.
 */
export function AgentSettingsPopover({
  providers,
  models,
  selection,
  onChange,
  children,
}: {
  providers: readonly ProviderOption[];
  /** Each provider's models, by provider id. */
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
  const reasonsId = useId();
  const offered = models[selection.providerId] ?? [];
  const model = offered.find((option) => option.id === selection.modelId);
  const efforts = model?.efforts ?? [];
  // A provider with nothing to choose from cannot be chosen either.
  const reasons = providers.flatMap((provider) => {
    const empty = (models[provider.id] ?? []).length === 0;
    if (provider.selectable && !empty) return [];
    const reason = !provider.selectable
      ? (provider.unavailableReason ?? t("desktop.agent.unavailable"))
      : t("desktop.agent.no_models");
    return [{ id: provider.id, name: provider.name, reason }];
  });

  const chooseProvider = (next: string) => {
    const first = (models[next] ?? [])[0];
    if (!first) return;
    onChange({
      providerId: next,
      modelId: first.id,
      effort: startingEffort(first),
    });
  };
  const chooseModel = (next: string) => {
    const chosen = offered.find((option) => option.id === next);
    if (!chosen) return;
    // The effort carries over where the new model accepts it.
    const effort =
      selection.effort && chosen.efforts.includes(selection.effort)
        ? selection.effort
        : startingEffort(chosen);
    onChange({ ...selection, modelId: chosen.id, effort });
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
          <FieldLabel id={providerId}>{t("desktop.agent.provider")}</FieldLabel>
          <SegmentedControl
            aria-labelledby={providerId}
            aria-describedby={reasons.length > 0 ? reasonsId : undefined}
            value={selection.providerId}
            onValueChange={chooseProvider}
          >
            {providers.map((provider) => (
              <SegmentedControlItem
                key={provider.id}
                value={provider.id}
                disabled={reasons.some((entry) => entry.id === provider.id)}
              >
                {provider.name}
              </SegmentedControlItem>
            ))}
          </SegmentedControl>
          {reasons.length > 0 && (
            <ul id={reasonsId} className="grid gap-0.5 text-sm text-faint">
              {reasons.map((entry) => (
                <li key={entry.id}>
                  {t("desktop.agent.provider_unavailable", {
                    provider: entry.name,
                    reason: entry.reason,
                  })}
                </li>
              ))}
            </ul>
          )}
        </Field>
        <Field>
          <FieldLabel id={modelId}>{t("desktop.agent.model")}</FieldLabel>
          {offered.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.agent.no_models")}
            </p>
          ) : (
            <RadioGroupPrimitive.Root
              aria-labelledby={modelId}
              orientation="vertical"
              value={selection.modelId}
              onValueChange={chooseModel}
              className="grid gap-0.5"
            >
              {offered.map((option) => (
                <RadioGroupPrimitive.Item
                  key={option.id}
                  value={option.id}
                  className="flex w-full cursor-pointer items-start gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-accent data-[state=checked]:bg-selected forced-colors:data-[state=checked]:bg-[Highlight] forced-colors:data-[state=checked]:text-[HighlightText]"
                >
                  <span className="grid min-w-0 flex-1 gap-0.5">
                    <span className="truncate font-medium text-foreground">
                      {option.name}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {option.description}
                    </span>
                  </span>
                  <span className="flex size-icon-md shrink-0 items-center justify-center pt-0.5">
                    <RadioGroupPrimitive.Indicator>
                      <Icon name="check" className="text-foreground" />
                    </RadioGroupPrimitive.Indicator>
                  </span>
                </RadioGroupPrimitive.Item>
              ))}
            </RadioGroupPrimitive.Root>
          )}
        </Field>
        {efforts.length > 0 && (
          <Field>
            <FieldLabel id={effortId}>{t("desktop.agent.effort")}</FieldLabel>
            <SegmentedControl
              aria-labelledby={effortId}
              value={selection.effort ?? ""}
              onValueChange={(effort) => {
                if (efforts.includes(effort))
                  onChange({ ...selection, effort });
              }}
            >
              {efforts.map((effort) => (
                <SegmentedControlItem key={effort} value={effort}>
                  {effort}
                </SegmentedControlItem>
              ))}
            </SegmentedControl>
          </Field>
        )}
      </PopoverContent>
    </Popover>
  );
}
