// URL.origin is "null" for the custom scheme used by the macOS and Linux
// documentation webviews. Compare the parsed scheme and authority instead.
export function onDocsOrigin(url: URL, origin: string): boolean {
  let expected: URL;
  try {
    expected = new URL(origin);
  } catch {
    return false;
  }
  return (
    !!expected.host &&
    !expected.username &&
    !expected.password &&
    !expected.search &&
    !expected.hash &&
    (expected.pathname === "" || expected.pathname === "/") &&
    url.protocol === expected.protocol &&
    url.host === expected.host &&
    !url.username &&
    !url.password
  );
}
