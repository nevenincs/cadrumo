import { useMemo, useState } from "react";
import type { AgentSession } from "../../shell/agentSession";
import type { LocalModelHost } from "../../shell/localModels";
import type { ReadingModelHost } from "../../shell/readingModel";

/**
 * The models the person added to the local lanes' lists, and the model
 * documents are read with, where the host offers reading and changing them.
 * The service has no connection to the host while the agent starts and
 * refuses every list read then, so the lists are offered only once the agent
 * runs; the host changing to a readable one at ready is what reads them.
 */
export function useLocalModelHosts(
  session: AgentSession | undefined,
  ready: boolean,
) {
  // Changes made to the lists in the settings, which the picker reads again.
  const [listChanges, setListChanges] = useState(0);
  const localModelHost = useMemo((): LocalModelHost | null => {
    if (
      !ready ||
      !session?.localModels ||
      !session.addLocalModel ||
      !session.removeLocalModel ||
      !session.resetLocalModels
    )
      return null;
    const changed = <T>(made: Promise<T>) =>
      made.then((value) => {
        setListChanges((count) => count + 1);
        return value;
      });
    const add = session.addLocalModel.bind(session);
    const remove = session.removeLocalModel.bind(session);
    const reset = session.resetLocalModels.bind(session);
    return {
      read: session.localModels.bind(session),
      add: (lane, model, revision) => changed(add(lane, model, revision)),
      remove: (lane, model, revision) => changed(remove(lane, model, revision)),
      reset: (revision) => changed(reset(revision)),
    };
  }, [session, ready]);
  const readingHost = useMemo((): ReadingModelHost | null => {
    if (!ready || !session?.localModels || !session.chooseReadingModel)
      return null;
    return {
      read: session.localModels.bind(session),
      choose: session.chooseReadingModel.bind(session),
    };
  }, [session, ready]);
  return { localModelHost, readingHost, listChanges };
}
