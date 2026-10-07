const FAMILY = "JetBrains Mono";
const FALLBACK = '"Cascadia Code", Consolas, monospace';
let loaded: Promise<string> | undefined;

/** xterm caches glyph metrics when opened. Load every bundled subset first:
 * document.fonts.ready alone only waits for fonts already used by the page. */
export function terminalFont(): Promise<string> {
  return (loaded ??= Promise.all(
    [...document.fonts]
      .filter((face) => face.family.replace(/["']/g, "") === FAMILY)
      .map((face) => face.load()),
  ).then(
    (faces) => (faces.length ? `"${FAMILY}", ${FALLBACK}` : FALLBACK),
    // Exclude the failed family permanently for this document: a later partial
    // load must not swap fonts underneath cached terminal measurements.
    () => FALLBACK,
  ));
}
