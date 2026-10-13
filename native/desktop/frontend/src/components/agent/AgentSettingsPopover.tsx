import { useId, useState, type ReactElement } from "react";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { useStrings } from "../../shell/strings";
import type {
  AgentSelection,
  ModelControl,
  ModelOption,
  ProviderOption,
} from "./types";

/** The effort a model starts at: its default where it accepts that, else
 * its first, else none. */
function startingEffort(model: ModelOption | undefined): string | undefined {
  if (!model) return undefined;
  if (
    model.defaultEffort &&
    model.efforts.some((effort) => effort.id === model.defaultEffort)
  )
    return model.defaultEffort;
  return model.efforts[0]?.id;
}

/** The settings a model starts with, keeping any still offered. */
function startingControls(
  model: ModelOption,
  held: AgentSelection["controls"],
): Record<string, string> | undefined {
  if (!model.controls?.length) return undefined;
  return Object.fromEntries(
    model.controls.map((control) => {
      const kept = held?.[control.id];
      const offered = control.options.some((option) => option.id === kept);
      return [
        control.id,
        offered && kept
          ? kept
          : (control.defaultOptionId ?? control.options[0]?.id ?? ""),
      ];
    }),
  );
}

/** The model a provider starts with: its recommended one, else its first. */
function startingModel(
  provider: ProviderOption | undefined,
  models: readonly ModelOption[],
): ModelOption | undefined {
  return (
    models.find((model) => model.id === provider?.defaultModelId) ?? models[0]
  );
}

/** One of a model's own settings, as a list to choose from. */
function ControlField({
  control,
  value,
  onChange,
}: {
  control: ModelControl;
  value: string | undefined;
  onChange: (optionId: string) => void;
}) {
  const id = useId();
  const chosen = control.options.find((option) => option.id === value);
  return (
    <Field>
      <FieldLabel htmlFor={id}>{control.name}</FieldLabel>
      <NativeSelect
        id={id}
        controlSize="sm"
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value)}
      >
        {control.options.map((option) => (
          <option key={option.id} value={option.id}>
            {option.name}
          </option>
        ))}
      </NativeSelect>
      {(chosen?.description ?? control.description) && (
        <FieldDescription>
          {chosen?.description ?? control.description}
        </FieldDescription>
      )}
    </Field>
  );
}

/**
 * The provider, model, effort and model settings of the conversation,
 * chosen in a popover opened from `children`. Every list is what it is
 * given, however long: the providers there are, each one's models, and the
 * efforts and settings of the model chosen. It holds no choice of its own:
 * every change is handed to `onChange`, and what it shows is `selection`.
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
  const provider = providers.find((held) => held.id === selection.providerId);
  const offered = models[selection.providerId] ?? [];
  const model = offered.find((option) => option.id === selection.modelId);
  const efforts = model?.efforts ?? [];

  const chooseProvider = (next: string) => {
    const chosen = providers.find((held) => held.id === next);
    const first = startingModel(chosen, models[next] ?? []);
    if (!chosen?.selectable || !first) return;
    const controls = startingControls(first, undefined);
    onChange({
      providerId: next,
      modelId: first.id,
      effort: startingEffort(first),
      ...(controls ? { controls } : {}),
    });
  };
  const chooseModel = (next: string) => {
    const chosen = offered.find((option) => option.id === next);
    if (!chosen) return;
    // The effort and settings carry over where the new model takes them.
    const effort =
      selection.effort &&
      chosen.efforts.some((held) => held.id === selection.effort)
        ? selection.effort
        : startingEffort(chosen);
    const controls = startingControls(chosen, selection.controls);
    onChange({
      providerId: selection.providerId,
      modelId: chosen.id,
      effort,
      ...(controls ? { controls } : {}),
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
          <NativeSelect
            id={providerId}
            controlSize="sm"
            value={selection.providerId}
            onChange={(event) => chooseProvider(event.target.value)}
          >
            {!provider && (
              <option value="">{t("desktop.agent.choose_model")}</option>
            )}
            {providers.map((option) => {
              const empty = (models[option.id] ?? []).length === 0;
              const reason = !option.selectable
                ? (option.unavailableReason ?? t("desktop.agent.unavailable"))
                : empty
                  ? t("desktop.agent.no_models")
                  : null;
              return (
                <option key={option.id} value={option.id} disabled={!!reason}>
                  {reason
                    ? t("desktop.agent.provider_unavailable", {
                        provider: option.name,
                        reason,
                      })
                    : option.name}
                </option>
              );
            })}
          </NativeSelect>
        </Field>
        <Field>
          <FieldLabel htmlFor={modelId}>{t("desktop.agent.model")}</FieldLabel>
          {offered.length === 0 ? (
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
          {model?.capabilities && model.capabilities.length > 0 && (
            <FieldDescription>
              {t("desktop.agent.capabilities", {
                list: new Intl.ListFormat(undefined, {
                  type: "conjunction",
                }).format(model.capabilities),
              })}
            </FieldDescription>
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
              value={selection.effort ?? ""}
              onChange={(event) => {
                const effort = event.target.value;
                if (efforts.some((held) => held.id === effort))
                  onChange({ ...selection, effort });
              }}
            >
              {efforts.map((effort) => (
                <option key={effort.id} value={effort.id}>
                  {effort.name}
                </option>
              ))}
            </NativeSelect>
          </Field>
        )}
        {model?.controls?.map((control) => (
          <ControlField
            key={control.id}
            control={control}
            value={selection.controls?.[control.id]}
            onChange={(optionId) =>
              onChange({
                ...selection,
                controls: { ...selection.controls, [control.id]: optionId },
              })
            }
          />
        ))}
      </PopoverContent>
    </Popover>
  );
}
