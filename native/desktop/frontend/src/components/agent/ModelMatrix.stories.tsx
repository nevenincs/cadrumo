import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useState } from "react";
import { userEvent } from "storybook/test";
import {
  fixtureOfferReads,
  type FixtureOfferScene,
} from "@/dev/agentFixtureModels";
import { agentOffer } from "../../shell/agentOffer";
import { AgentOfferContext } from "../../shell/agentOfferContext";
import { useStrings } from "../../shell/strings";
import { ModelMatrix, type MatrixValue } from "./ModelMatrix";
import type { MatrixMode } from "./modelMatrixView";

// Appearance and interaction. The offer is worked out by the column's own
// projection from made-up reads: six "Example" providers out of the fixture
// catalog, one ready, one with forty models, one on this computer, one not
// configured, one turned off and one local engine that does not run. The
// story holds the choice itself, so every cell can be tried; the steps only
// say they were pressed. Nothing reaches a provider.

type Args = {
  mode: MatrixMode;
  scene?: FixtureOfferScene;
  start?: MatrixValue | null;
  /** The width the matrix is drawn in. */
  narrow?: boolean;
};

function Matrix({ mode, scene, start = null, narrow = false }: Args) {
  const t = useStrings();
  const offer = useMemo(() => {
    const { catalog, lists, settings } = fixtureOfferReads(scene);
    return agentOffer(t, catalog, lists, settings);
  }, [t, scene]);
  const [value, setValue] = useState<MatrixValue | null>(start);
  const [stepped, setStepped] = useState<string | null>(null);
  const step = (lane: { id: string }) => setStepped(lane.id);
  return (
    <AgentOfferContext.Provider value={offer}>
      <div className={narrow ? "w-settings" : "w-160 max-w-full"}>
        <ModelMatrix
          mode={mode}
          label={t("desktop.agent.model_matrix_label")}
          value={value}
          onChoose={({ lane, model, effort }) =>
            setValue({ lane: lane.id, model, effort })
          }
          steps={{ sign_in: step, retry: step, download: step, set_up: step }}
          onOpenProviders={() => setStepped("providers")}
        />
        {stepped && (
          <p role="status" className="pt-2 text-sm text-muted-foreground">
            {stepped}
          </p>
        )}
      </div>
    </AgentOfferContext.Provider>
  );
}

const meta = {
  title: "Shell/Agent/Model matrix",
  args: { mode: "task" },
  render: (args: Args) => <Matrix {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

const search =
  (words: string): NonNullable<Story["play"]> =>
  async ({ canvasElement }) => {
    const field = canvasElement.querySelector<HTMLInputElement>(
      "[data-slot=model-matrix] input[type=search]",
    );
    if (field) await userEvent.type(field, words);
  };

const press =
  (selector: string): NonNullable<Story["play"]> =>
  async ({ canvasElement }) => {
    const button = canvasElement.querySelector<HTMLElement>(selector);
    if (button) await userEvent.click(button);
  };

export const Default: Story = {
  name: "Task models, lanes on",
  args: {
    start: { lane: "kimi_api", model: "fixture-quick", effort: "medium" },
  },
};

export const ConversationNarrow: Story = {
  name: "Conversation, column width",
  args: {
    mode: "conversation",
    narrow: true,
    start: { lane: "kimi_api", model: "fixture-deep", effort: null },
  },
};

export const Searching: Story = {
  name: "Search, two words",
  play: search("many high"),
};

export const NoResults: Story = {
  name: "Search, no match",
  play: search("nothing like this"),
};

export const ManyModels: Story = {
  name: "Forty models, every effort",
  args: {
    start: { lane: "qwen_api", model: "example-many-12", effort: "max" },
  },
  play: search("example many"),
};

/** Chooses `state` and `availability` in the matrix's two filters. */
const filtered =
  (state: string, availability: string): NonNullable<Story["play"]> =>
  async (context) => {
    await press(`[data-filter-axis=state] [data-filter=${state}]`)(context);
    await press(
      `[data-filter-axis=availability] [data-filter=${availability}]`,
    )(context);
  };

export const NeedsSetup: Story = {
  name: "Filtered to needs setup",
  play: filtered("on", "setup"),
};

export const UnavailableLane: Story = {
  name: "A lane not available yet, its models counted",
  play: search("llamacpp"),
};

export const FilterAllAll: Story = {
  name: "Filter: every status, every availability",
  play: filtered("all", "all"),
};
export const FilterAllReady: Story = {
  name: "Filter: every status, ready",
  play: filtered("all", "ready"),
};
export const FilterAllSetup: Story = {
  name: "Filter: every status, needs setup",
  play: filtered("all", "setup"),
};
export const FilterOnAll: Story = {
  name: "Filter: on, every availability",
  play: filtered("on", "all"),
};
export const FilterOnReady: Story = {
  name: "Filter: on, ready",
  play: filtered("on", "ready"),
};
export const FilterOffAll: Story = {
  name: "Filter: off, every availability",
  play: filtered("off", "all"),
};
export const FilterOffReady: Story = {
  name: "Filter: off, ready (nothing)",
  play: filtered("off", "ready"),
};
export const FilterOffSetup: Story = {
  name: "Filter: off, needs setup",
  play: filtered("off", "setup"),
};

export const OffShown: Story = {
  name: "Providers turned off, shown",
  play: press("[data-slot=model-matrix-off-hidden] button"),
};

export const NoneOn: Story = {
  name: "No provider on",
  args: { scene: { allOff: true } },
};

export const AgentStarting: Story = {
  name: "Agent starting, declared lanes",
  args: { scene: { declared: true } },
};

export const EmptySearch: Story = {
  name: "Search cleared",
  play: async (context) => {
    await search("many")(context);
    const field = context.canvasElement.querySelector<HTMLInputElement>(
      "[data-slot=model-matrix] input[type=search]",
    );
    if (field) await userEvent.clear(field);
  },
};
