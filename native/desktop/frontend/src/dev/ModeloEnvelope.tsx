import { useEffect, useState, type ReactNode } from "react";
import type { ModeloWorkbenchFormProjectionV1 } from "../shell/modeloContract/modeloWorkForm";
import { wholeEnvelopes } from "./modeloEnvelopePatch";
import { requireServed } from "./servedFixtures";

// A form envelope of @fixtures/modelo/, read when a story asks for it: the
// largest are over a megabyte, and a story needs one of four languages.
const found = requireServed(
  "modelo/modelo-*.json",
  import.meta.glob<unknown>("@fixtures/modelo/modelo-*.json", {
    import: "default",
  }),
);
const envelopes = wholeEnvelopes(
  Object.fromEntries(
    Object.entries(found).map(([path, load]) => [
      path.slice(path.lastIndexOf("/") + 1, -".json".length),
      load,
    ]),
  ),
);

/** The envelope stored under `name` (`modelo-130-1T-es`), or nothing while it
 * is read. `adjust`, a function that stays the same between renders, changes
 * the copy read, for a state the application's own read did not produce. A
 * name with no file is a mistake in the story, and throws. */
export function ModeloEnvelope({
  name,
  adjust,
  children,
}: {
  name: string;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
  children: (envelope: ModeloWorkbenchFormProjectionV1) => ReactNode;
}) {
  const [read, setRead] = useState<{
    name: string;
    envelope: ModeloWorkbenchFormProjectionV1;
  } | null>(null);
  const [failure, setFailure] = useState<Error | null>(null);
  useEffect(() => {
    const load = envelopes[name];
    if (!load) {
      setFailure(new Error(`No envelope is stored as ${name}`));
      return;
    }
    let current = true;
    void load().then((envelope) => {
      if (!current) return;
      const copy = structuredClone(envelope) as ModeloWorkbenchFormProjectionV1;
      adjust?.(copy);
      setRead({ name, envelope: copy });
    });
    return () => {
      current = false;
    };
  }, [name, adjust]);
  if (failure) throw failure;
  return read?.name === name ? <>{children(read.envelope)}</> : null;
}
