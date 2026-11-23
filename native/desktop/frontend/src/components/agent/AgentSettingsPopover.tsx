import {
  useEffect,
  useId,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { NativeSelect } from "@/components/ui/native-select";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { listOf } from "@/shared/lists";
import { TextEditor } from "@/components/editors/TextEditor";
import { startingSelection } from "../../shell/agentCatalog";
import { heldModel } from "../../shell/agentOffer";
import { described, labelled } from "../../shell/compose";
import { connectionWords } from "../../shell/providerConnection";
import { useStrings } from "../../shell/strings";
import { ModelListNotice } from "./ModelListNotice";
import { ProviderSelect } from "./ProviderSelect";
import type { AgentSelection, ModelOption, ProviderOption } from "./types";

/**
 * The provider, the model and the effort of the conversation, chosen in a
 * popover opened from `children`. Every list is what it is given, however
 * long: the providers there are, the models of the one chosen, and the
 * efforts of the model chosen. A provider reached more than one way is more
 * than one entry of the first list, and choosing an entry chooses the way.
 * It holds no choice of its own: every change is handed to `onChange`, and
 * what it shows is `selection`. A model the catalog says this computer does
 * not hold is listed and cannot be chosen; the way on is downloading it,
 * which `onDownloadModels` opens.
 */
export function AgentSettingsPopover({
  providers,
  models,
  selection,
  onChange,
  fixedWayId,
  children,
  openRequests = 0,
  onClosed,
  onOpened,
  onDownloadModels,
  onRetryCatalog,
  onSignIn,
  listsFailure = null,
  onRetryLists,
}: {
  providers: readonly ProviderOption[];
  /** Each way's models, by way id. */
  models: Readonly<Record<string, readonly ModelOption[]>>;
  selection: AgentSelection;
  onChange: (selection: AgentSelection) => void;
  /** The lane the conversation is fixed to, by way id: every other lane is
   * offered as a new conversation. */
  fixedWayId?: string;
  /** The one element that opens the popover. */
  children: ReactElement;
  /** Counts the asks from elsewhere to open the popover that no close has
   * answered yet. A new one opens it, and so does one waiting when the
   * popover mounts, as it does when the column it is in is first shown. */
  openRequests?: number;
  /** Called when the person closes the popover. */
  onClosed?: () => void;
  /** Called each time the popover opens, however it was asked to. */
  onOpened?: () => void;
  /** Opens the settings where a model this computer lacks is downloaded. */
  onDownloadModels?: () => void;
  /** Reads the catalog again, the way on for a lane whose models could not
   * be read. */
  onRetryCatalog?: () => void;
  /** Opens the settings where a lane that is signed out is signed in. */
  onSignIn?: () => void;
  /** Why the person's model lists could not be read: until they are, a lane
   * on this computer offers what the catalog lists rather than the person's
   * list, which is said here. Null once they are read. */
  listsFailure?: string | null;
  /** Reads the person's model lists again. */
  onRetryLists?: () => void;
}) {
  const t = useStrings();
  const [open, setOpen] = useState(false);
  const [requestsSeen, setRequestsSeen] = useState(0);
  if (requestsSeen !== openRequests) {
    setRequestsSeen(openRequests);
    if (openRequests > 0) setOpen(true);
  }
  // The newest `onOpened`, so an opening is told once whatever the parent
  // renders in between.
  const opening = useRef(onOpened);
  useLayoutEffect(() => {
    opening.current = onOpened;
  }, [onOpened]);
  useEffect(() => {
    if (open) opening.current?.();
  }, [open]);
  const providerId = useId();
  const modelId = useId();
  const effortId = useId();
  const provider = providers.find((held) => held.id === selection.providerId);
  const way = provider?.ways.find((held) => held.id === selection.wayId);
  const offered = models[selection.wayId] ?? [];
  const model = offered.find((option) => option.id === selection.modelId);
  const efforts = way?.modelWritten?.efforts ?? model?.efforts ?? [];
  const hasDefault = Boolean(model?.defaultEffort);
  // The way to download is offered where the chosen way is one whose models
  // are downloaded to this computer and lists one it lacks. With no way
  // chosen it is offered where some way cannot be chosen until one is
  // downloaded. Under a way whose models are not downloaded it is never.
  const download =
    onDownloadModels &&
    (way
      ? way.modelsToDownload === true
      : providers.some((held) =>
          held.ways.some((each) => !each.selectable && each.modelsToDownload),
        ))
      ? () => {
          setOpen(false);
          onClosed?.();
          onDownloadModels();
        }
      : undefined;

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
  // The lanes held back that the catalog's own reason has a step for, said
  // with that reason: asking again, or signing in.
  const heldLanes = providers.flatMap((held) =>
    held.ways.flatMap((each) =>
      !each.selectable &&
      ((each.heldStep === "retry" && onRetryCatalog) ||
        (each.heldStep === "sign_in" && onSignIn))
        ? [{ provider: held, way: each }]
        : [],
    ),
  );
  const chooseModel = (next: string) => {
    const chosen = offered.find((option) => option.id === next);
    if (!chosen || !heldModel(chosen)) return;
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
    <Popover
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) onClosed?.();
      }}
    >
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
            fixedWayId={fixedWayId}
            onChange={chooseEntry}
          />
          {/* What the lane has been proven to do on this computer. */}
          {way?.capabilities && way.capabilities.length > 0 && (
            <FieldDescription>
              {t("desktop.agent.capabilities", {
                list: listOf(t.locale, way.capabilities),
              })}
            </FieldDescription>
          )}
          {heldLanes.map(({ provider: held, way: each }) => (
            <div
              key={each.id}
              data-held-way={each.id}
              className="grid justify-items-start gap-1.5"
            >
              <FieldDescription>
                {labelled(
                  t,
                  described(t, held.name, connectionWords(t, each)),
                  each.unavailableReason ?? t("desktop.agent.unavailable"),
                )}
              </FieldDescription>
              <Button
                variant="outline"
                size="xs"
                data-held-step={each.heldStep}
                onClick={
                  each.heldStep === "sign_in"
                    ? () => {
                        setOpen(false);
                        onClosed?.();
                        onSignIn?.();
                      }
                    : onRetryCatalog
                }
              >
                {each.heldStep === "sign_in"
                  ? t("desktop.providers.sign_in_action")
                  : t("desktop.agent.retry")}
              </Button>
            </div>
          ))}
        </Field>
        <Field>
          <FieldLabel htmlFor={modelId}>{t("desktop.agent.model")}</FieldLabel>
          {way?.modelWritten ? (
            <>
              <TextEditor
                id={modelId}
                controlSize="sm"
                value={selection.modelId}
                onChange={(modelId) => onChange({ ...selection, modelId })}
              />
              <FieldDescription>
                {t("desktop.agent.model_written")}
              </FieldDescription>
            </>
          ) : !way ? (
            <p className="text-sm text-muted-foreground">
              {t("desktop.agent.choose_provider_first")}
            </p>
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
              {offered.map((option) =>
                heldModel(option) ? (
                  <option key={option.id} value={option.id}>
                    {option.name}
                  </option>
                ) : (
                  <option
                    key={option.id}
                    value={option.id}
                    disabled
                    data-installed="false"
                  >
                    {t("desktop.agent.model_not_installed", {
                      name: option.name,
                    })}
                  </option>
                ),
              )}
            </NativeSelect>
          )}
          {model?.description && (
            <FieldDescription>{model.description}</FieldDescription>
          )}
          {listsFailure !== null && (
            <ModelListNotice
              code={listsFailure}
              fault={t("desktop.providers.local_models_failed")}
              onRetry={onRetryLists}
              slot="picker-lists"
            />
          )}
          {download && (
            <div className="grid justify-items-start gap-1.5">
              <FieldDescription>
                {t("desktop.agent.models_to_download")}
              </FieldDescription>
              <Button variant="outline" size="xs" onClick={download}>
                {t("desktop.agent.download_models")}
              </Button>
            </div>
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
