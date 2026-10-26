import type { IconName } from "@/components/ui/icon";
import type { ModeloFormOrigin } from "../../../shell/modeloContract";

// How each origin the application reports is drawn: an icon and a tone that
// reinforce its words, never replace them. The words are the field's own.

export type Tone = "attention" | "danger" | "mine" | "source" | "quiet";

export const TONE_TEXT: Record<Tone, string> = {
  attention: "text-warning",
  danger: "text-destructive",
  mine: "text-foreground",
  source: "text-muted-foreground",
  quiet: "text-faint",
};

export const ORIGIN_LOOK: Record<
  ModeloFormOrigin,
  { tone: Tone; icon: IconName }
> = {
  needs_input: { tone: "attention", icon: "edit" },
  default_to_confirm: { tone: "attention", icon: "tick" },
  calculation_failed: { tone: "danger", icon: "alert" },
  entered: { tone: "mine", icon: "person" },
  cleared: { tone: "mine", icon: "erase" },
  overrides_source: { tone: "attention", icon: "swap" },
  imported: { tone: "source", icon: "download" },
  not_imported_yet: { tone: "quiet", icon: "clock" },
  calculated: { tone: "source", icon: "sync" },
  not_calculated_yet: { tone: "quiet", icon: "clock" },
  informational: { tone: "quiet", icon: "info" },
  optional_empty: { tone: "quiet", icon: "page" },
  not_applicable: { tone: "quiet", icon: "close" },
};
