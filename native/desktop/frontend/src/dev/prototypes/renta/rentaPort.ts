import type { ModeloPort } from "@/shell/modelo";
import type { ModeloWorkbenchFormProjectionV1 } from "@/shell/modeloContract";

// The modelo port the prototypes hand the real form: it answers the form it
// was given and nothing else. A prototype submits nothing, so every other
// call is refused rather than answered with a made-up result.

const refused = () =>
  Promise.reject(new Error("The Renta prototypes submit nothing."));

export function prototypePort(
  envelope: ModeloWorkbenchFormProjectionV1,
): ModeloPort {
  return {
    declarations: refused,
    form: () => Promise.resolve(envelope),
    casillaHelp: refused,
    submit: refused,
    edit: refused,
    observe: refused,
    review: refused,
    answer: refused,
    cancel: refused,
    pickFile: refused,
    saveFile: refused,
    forgetFiles: () => Promise.resolve(),
    revealFile: refused,
  };
}
