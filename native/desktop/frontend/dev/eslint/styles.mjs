const entrySheets = new Set(["src/index.css", "src/dev/index.css"]);

/** Fonts have descriptors; theme owns scrim/alpha colors; tokens own scales. */
export function styleViolations(path, source) {
  const problems = [];
  if (
    !entrySheets.has(path) &&
    !/^src\/styles\/[a-z]+(?:-[a-z]+)*\.css$/.test(path)
  )
    problems.push("Place shared styles in src/styles with a kebab-case name.");
  const css = source.replace(/\/\*[\s\S]*?\*\//g, "");
  if (path !== "src/styles/tokens.css") {
    for (const match of css.matchAll(
      /(?<![\w-])(-?\d+(?:\.\d+)?)(?:px|rem|em|ms|s)\b/g,
    ))
      if (Number(match[1]) !== 0) {
        problems.push("Declare dimensional and motion scales in tokens.css.");
        break;
      }
  }
  if (
    path !== "src/styles/theme.css" &&
    /#[\da-f]{3,8}\b|\b(?:rgb|hsl|oklch)\(/i.test(css)
  )
    problems.push(
      "Colors come from palette roles; alpha colors belong in theme.css.",
    );
  return problems;
}
