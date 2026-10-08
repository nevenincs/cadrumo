import type { Terminal } from "@xterm/xterm";
import { WebglAddon } from "@xterm/addon-webgl";

/** Fixed cell positions and custom box/block glyphs for full-screen TUIs.
 * Keep xterm's DOM renderer available on machines without a usable GPU. */
export function terminalRenderer(
  term: Terminal,
  refit: () => void,
): () => void {
  let addon: WebglAddon | undefined;
  let loss: { dispose(): void } | undefined;
  let release: WEBGL_lose_context | null = null;
  const dispose = () => {
    loss?.dispose();
    loss = undefined;
    const active = addon;
    addon = undefined;
    active?.dispose();
    // The pinned addon removes its canvas but leaves context release to GC.
    // Release it now so repeated TUI sessions cannot evict a still-live pane.
    release?.loseContext();
    release = null;
  };
  try {
    addon = new WebglAddon();
    loss = addon.onContextLoss(() => {
      dispose();
      refit();
      term.refresh(0, term.rows - 1);
    });
    term.loadAddon(addon);
    // The addon appends its drawing canvas after its 2D link layer. This is
    // the existing browser context, not a second GPU allocation.
    release =
      term.element
        ?.querySelector<HTMLCanvasElement>(".xterm-screen > canvas:last-child")
        ?.getContext("webgl2")
        ?.getExtension("WEBGL_lose_context") ?? null;
  } catch {
    dispose();
  }
  return dispose;
}
