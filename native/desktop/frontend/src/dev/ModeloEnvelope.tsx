import { useEffect, useState, type ReactNode } from "react";
import type { ModeloWorkbenchFormProjectionV1 } from "../shell/modeloContract";

// A form envelope of ./fixtures/modelo/, read when a story asks for it: the
// largest are over a megabyte, and a story needs one of four languages.
const found = import.meta.glob<ModeloWorkbenchFormProjectionV1>(
  "./fixtures/modelo/modelo-*.json",
  { import: "default" },
);

/** The envelope stored under `name` (`modelo-130-1T-es`), or nothing while it
 * is read. `adjust`, a function that stays the same between renders, changes
 * the copy read, for a state the application's own read did not produce. A
 * name with no file is a mistake in the story, and throws. `baselineFrom`
 * names the envelope whose edit baseline this one takes: the stored edit
 * answers of every language were read on one baseline, so a story that stages
 * an edit reads its form on it. */
export function ModeloEnvelope({
  name,
  adjust,
  baselineFrom,
  children,
}: {
  name: string;
  baselineFrom?: string;
  adjust?: (envelope: ModeloWorkbenchFormProjectionV1) => void;
  children: (envelope: ModeloWorkbenchFormProjectionV1) => ReactNode;
}) {
  const [read, setRead] = useState<{
    name: string;
    envelope: ModeloWorkbenchFormProjectionV1;
  } | null>(null);
  const [failure, setFailure] = useState<Error | null>(null);
  useEffect(() => {
    const load = found[`./fixtures/modelo/${name}.json`];
    if (!load) {
      setFailure(new Error(`No envelope is stored as ${name}`));
      return;
    }
    const donor = baselineFrom
      ? found[`./fixtures/modelo/${baselineFrom}.json`]
      : undefined;
    if (baselineFrom && !donor) {
      setFailure(new Error(`No envelope is stored as ${baselineFrom}`));
      return;
    }
    let current = true;
    void Promise.all([load(), donor?.()]).then(([envelope, lent]) => {
      if (!current) return;
      const copy = structuredClone(envelope);
      if (lent)
        copy.admitted_baseline = structuredClone(lent.admitted_baseline);
      adjust?.(copy);
      setRead({ name, envelope: copy });
    });
    return () => {
      current = false;
    };
  }, [name, adjust, baselineFrom]);
  if (failure) throw failure;
  return read?.name === name ? <>{children(read.envelope)}</> : null;
}
