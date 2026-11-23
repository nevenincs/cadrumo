import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";
import { FieldDescription } from "@/components/ui/field";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { listOf } from "@/shared/lists";
import { useAgentOffer } from "../../shell/agentOfferContext";
import { useStrings } from "../../shell/strings";
import { ModelListNotice } from "./ModelListNotice";
import { ModelMatrix } from "./ModelMatrix";
import type { AgentSelection } from "./types";

/**
 * The provider, the model and the effort of the conversation, chosen in one
 * press of the model matrix, in a popover opened from `children`. The lanes,
 * models and efforts are the agent's offer, however many there are. It holds
 * no choice of its own: every change is handed to `onChange`, and what it
 * shows is `selection`. A lane that cannot be chosen yet is listed with the
 * step that brings it into use: signing in or setting it up in the settings,
 * asking again, or downloading a model this computer lacks.
 */
export function AgentSettingsPopover({
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
  /** Opens the settings where a lane is signed in to, set up or turned on. */
  onSignIn?: () => void;
  /** Why the person's model lists could not be read: until they are, a lane
   * on this computer offers what the catalog lists rather than the person's
   * list, which is said here. Null once they are read. */
  listsFailure?: string | null;
  /** Reads the person's model lists again. */
  onRetryLists?: () => void;
}) {
  const t = useStrings();
  const offer = useAgentOffer();
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
  const lane = [...(offer?.lanes.values() ?? [])].find(
    (held) => held.wayId === selection.wayId,
  );
  // A step taken in the settings closes the popover first.
  const away = (act: (() => void) | undefined) =>
    act
      ? () => {
          setOpen(false);
          onClosed?.();
          act();
        }
      : undefined;
  const settingsStep = away(onSignIn);
  const downloadStep = away(onDownloadModels);

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
        <ModelMatrix
          mode="conversation"
          label={t("desktop.agent.model_matrix_label")}
          value={
            lane
              ? {
                  lane: lane.id,
                  model: selection.modelId,
                  effort: selection.effort ?? null,
                }
              : null
          }
          fixedWayId={fixedWayId}
          onChoose={({ lane: chosen, model, effort }) => {
            if (chosen.wayId === null) return;
            onChange({
              providerId: chosen.provider,
              wayId: chosen.wayId,
              modelId: model,
              ...(effort ? { effort } : {}),
            });
          }}
          steps={{
            ...(settingsStep
              ? { sign_in: settingsStep, set_up: settingsStep }
              : {}),
            ...(onRetryCatalog ? { retry: onRetryCatalog } : {}),
            ...(downloadStep ? { download: downloadStep } : {}),
          }}
          onOpenProviders={settingsStep}
        />
        {/* What the lane has been proven to do on this computer. */}
        {lane && lane.capabilities.length > 0 && (
          <FieldDescription>
            {t("desktop.agent.capabilities", {
              list: listOf(t.locale, lane.capabilities),
            })}
          </FieldDescription>
        )}
        {listsFailure !== null && (
          <ModelListNotice
            code={listsFailure}
            fault={t("desktop.providers.local_models_failed")}
            onRetry={onRetryLists}
            slot="picker-lists"
          />
        )}
      </PopoverContent>
    </Popover>
  );
}
