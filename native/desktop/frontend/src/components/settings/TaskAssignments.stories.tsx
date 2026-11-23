import type { Meta, StoryObj } from "@storybook/react-vite";
import { useMemo, useRef, useState } from "react";
import { userEvent } from "storybook/test";
import {
  fixtureOfferReads,
  type FixtureOfferScene,
} from "@/dev/agentFixtureModels";
import { agentOffer } from "../../shell/agentOffer";
import { AgentOfferContext } from "../../shell/agentOfferContext";
import type { LocalModelHost } from "../../shell/localModels";
import type { LocalModelListStatus } from "../../shell/localModelsContract";
import { useStrings } from "../../shell/strings";
import { TaskAssignments } from "./TaskAssignments";

// Appearance and interaction. What each task runs with, over the offer the
// column works out from made-up reads: six "Example" providers out of the
// fixture catalog. The lists are kept in memory, so a change made here is
// stored and said; a scene can have the made-up service refuse every change
// or hold a record it cannot read. Nothing reaches a provider.

type Args = {
  scene?: FixtureOfferScene;
  /** The made-up service refuses each change, as out of date. */
  refuses?: boolean;
  /** The stored record cannot be read until it is reset. */
  unreadable?: boolean;
};

const refusal = () =>
  Object.assign(new Error("agent_local_models_revision_conflict"), {
    code: "agent_local_models_revision_conflict",
  });

function Assignments({ scene, refuses = false, unreadable = false }: Args) {
  const t = useStrings();
  const reads = useMemo(() => fixtureOfferReads(scene), [scene]);
  const [lists, setLists] = useState<LocalModelListStatus>(() =>
    unreadable
      ? { ...reads.lists, unreadable: true, tasks: [], reading: null }
      : reads.lists,
  );
  const offer = useMemo(
    () => agentOffer(t, reads.catalog, lists, reads.settings),
    [t, reads, lists],
  );
  // The made-up service: what it stores is the story's lists.
  const kept = useRef(lists);
  const host = useMemo((): LocalModelHost => {
    const current = async () => kept.current;
    const store = (next: LocalModelListStatus) => {
      kept.current = next;
      setLists(next);
      return next;
    };
    return {
      read: current,
      add: current,
      remove: current,
      reset: async () =>
        store({ ...reads.lists, unreadable: false, tasks: [], reading: null }),
      chooseTask: async (taskKind, choice) => {
        if (refuses) throw refusal();
        const stored = kept.current;
        const tasks = stored.tasks.filter(
          (entry) => entry.task_kind !== taskKind,
        );
        return store({
          ...stored,
          tasks: choice
            ? [...tasks, { task_kind: taskKind, ...choice }]
            : tasks,
        });
      },
    };
  }, [reads, refuses]);
  return (
    <AgentOfferContext.Provider value={offer}>
      <div className="w-160 max-w-full">
        <TaskAssignments
          host={host}
          catalogStatus="ready"
          onRetryCatalog={() => undefined}
          onShowProvider={() => undefined}
        />
      </div>
    </AgentOfferContext.Provider>
  );
}

const meta = {
  title: "Settings/Models per task",
  args: {},
  render: (args: Args) => <Assignments {...args} />,
} satisfies Meta<Args>;
export default meta;
type Story = StoryObj<typeof meta>;

const change: NonNullable<Story["play"]> = async ({ canvasElement }) => {
  const button = canvasElement.querySelector<HTMLElement>(
    "[data-task-kind=extraction] button",
  );
  if (button) await userEvent.click(button);
};

export const ReadingDefault: Story = {
  name: "Reading model, a default standing in",
};

export const ReadingChosen: Story = {
  name: "Reading model, chosen",
  args: { scene: { reading: "chosen" } },
};

export const AssignedWithEffort: Story = {
  name: "Set to a model and effort",
  args: {
    scene: {
      tasks: [
        {
          task_kind: "extraction",
          lane: "kimi_api",
          model: "fixture-quick",
          effort: "low",
        },
        {
          task_kind: "classification",
          lane: "kimi_api",
          model: "fixture-quick",
          effort: null,
        },
      ],
    },
  },
};

export const StaleStored: Story = {
  name: "Stored setting no longer offered",
  args: {
    scene: {
      tasks: [
        {
          task_kind: "classification",
          lane: "kimi_api",
          model: "example-retired",
          effort: "high",
        },
      ],
    },
  },
};

export const ChangeOpen: Story = {
  name: "Change, the shared matrix open",
  args: AssignedWithEffort.args,
  play: change,
};

export const SaveRefused: Story = {
  name: "A change refused",
  args: { refuses: true },
  play: async (context) => {
    await change(context);
    const cell = context.canvasElement.ownerDocument.querySelector<HTMLElement>(
      "[data-slot=model-matrix] [data-model=fixture-quick] [data-column=default]",
    );
    if (cell) await userEvent.click(cell);
    await userEvent.keyboard("{Escape}");
  },
};

export const ListsUnreadable: Story = {
  name: "Lists record unreadable",
  args: { unreadable: true },
};
