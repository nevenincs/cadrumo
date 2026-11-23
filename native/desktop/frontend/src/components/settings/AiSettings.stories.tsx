import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useRef, useState } from "react";
import { agentAccessFixture } from "@/dev/agentAccessFixture";
import { fixtureOfferReads } from "@/dev/agentFixtureModels";
import { useAgentAccess } from "../../shell/agentAccess";
import { agentOffer } from "../../shell/agentOffer";
import { AgentOfferContext } from "../../shell/agentOfferContext";
import type { LocalModelHost } from "../../shell/localModels";
import type { LocalModelListStatus } from "../../shell/localModelsContract";
import {
  useProviderSettings,
  type ProviderSettings,
} from "../../shell/providerSettings";
import type { ProviderSettingsRecord } from "../../shell/providerSettingsContract";
import { useStrings } from "../../shell/strings";
import { AgentSettingsPanel } from "../agent/AgentSettingsPanel";

// Appearance and interaction: the agent's settings as the agent column shows
// them, in its width and in the column's order -- the search, the AI
// providers, the agent API keys and the models per task -- over the same
// made-up reads the sections' own stories use: the agent specimen's six
// "Example" providers and a made-up profile's keys. What each task runs with
// is kept in memory; a provider change answers with the lane as it was, so
// nothing is stored, and no key is shown or reaches a provider.

/** The made-up profile the sections read. */
const READER = "example-profile";

const NOOP = () => undefined;

function WholeSection({ locale }: { locale: string }) {
  const t = useStrings();
  const reads = useMemo(() => fixtureOfferReads(), []);
  const [lists, setLists] = useState<LocalModelListStatus>(reads.lists);
  const offer = useMemo(
    () => agentOffer(t, reads.catalog, lists, reads.settings),
    [t, reads, lists],
  );
  const providerHost = useMemo((): ProviderSettings => {
    const lane = async ({
      provider,
    }: {
      provider: string;
    }): Promise<ProviderSettingsRecord> => {
      const held = reads.settings.providers.find(
        (record) => record.id === provider,
      );
      if (!held) throw Object.assign(new Error("unknown"), { code: "unknown" });
      return held;
    };
    return {
      status: async () => ({
        providers: reads.settings.providers,
        reads_pending: false,
      }),
      set: lane,
      turnOff: lane,
      turnOn: lane,
      reset: lane,
      signOut: lane,
    };
  }, [reads]);
  const accessHost = useMemo(
    () =>
      agentAccessFixture({
        say: NOOP,
        wait: async () => undefined,
        readable: () => true,
      }),
    [],
  );
  // The made-up service: what it stores is the story's lists.
  const kept = useRef(lists);
  const localModelHost = useMemo((): LocalModelHost => {
    const current = async () => kept.current;
    return {
      read: current,
      add: current,
      remove: current,
      reset: current,
      chooseTask: async (taskKind, choice) => {
        const stored = kept.current;
        const tasks = stored.tasks.filter(
          (entry) => entry.task_kind !== taskKind,
        );
        const next = {
          ...stored,
          tasks: choice
            ? [...tasks, { task_kind: taskKind, ...choice }]
            : tasks,
        };
        kept.current = next;
        setLists(next);
        return next;
      },
    };
  }, []);
  const settings = useProviderSettings(providerHost, READER, true, 1, null);
  const access = useAgentAccess(accessHost, READER, true, 1);
  const [query, setQuery] = useState("");
  const [providerMatches, setProviderMatches] = useState(true);
  const [accessMatches, setAccessMatches] = useState(true);
  return (
    <AgentOfferContext.Provider value={offer}>
      <aside className="flex min-h-dvh w-full flex-col border-r bg-background sm:w-(--agent-w)">
        <section
          aria-label={t("desktop.pane.agent")}
          className="agent-body flex flex-1 flex-col"
        >
          <AgentSettingsPanel
            query={query}
            onQuery={setQuery}
            providerMatches={providerMatches}
            onProviderMatch={setProviderMatches}
            accessMatches={accessMatches}
            onAccessMatch={setAccessMatches}
            providerSettings={providerHost}
            settings={settings}
            agentAccess={accessHost}
            access={access}
            reader={READER}
            locale={locale}
            onSignInTerminal={async () => undefined}
            localModelHost={localModelHost}
            localProviderId="llamacpp_api"
            catalogStatus="ready"
            onRetryCatalog={NOOP}
            onLocalModelRemoved={NOOP}
          />
        </section>
      </aside>
    </AgentOfferContext.Provider>
  );
}

const meta = {
  title: "Settings/AI settings (whole section)",
  parameters: {
    surface: "chrome",
    docs: {
      description: {
        component:
          "The whole AI settings section as the agent column shows it: AI providers, agent API keys and models per task, in the column's order and width.",
      },
    },
  },
  render: (_args, { globals }) => (
    <WholeSection locale={String(globals.locale)} />
  ),
} satisfies Meta;
export default meta;
type Story = StoryObj<typeof meta>;

export const AiSettings: Story = {
  name: "AI settings",
};
