/* Serves one immutable release of the Cadrumo documentation out of R2, below
 * the canonical host's mount and below the mirror host's mount.
 *
 * Every release lives under its own key prefix, `releases/<RELEASE_ID>/`, and
 * RELEASE_ID is a plain binding on the deployed Worker. Moving the site to
 * another release is a Worker deploy and rolling back is a redeploy of an
 * earlier id; nothing in the bucket is ever overwritten.
 *
 * The built site is mount-relative, so the same bytes serve both mounts: the
 * mount is stripped before the key is formed, and only the 404 page, whose
 * links must be absolute, is re-rooted for the mirror. A missing path answers
 * the release's own 404 page with status 404, never a 200, because a 200 for a
 * missing page is how a broken link hides. An apex path that names no language
 * root redirects to the same page under the source-language root.
 *
 * Every response carries the release header. It is what the publisher polls
 * after a deploy to prove the new release is the one being served.
 */

export const RELEASE_HEADER = "x-cadrumo-docs-release";

const NOT_FOUND_CACHE_CONTROL = "public, max-age=60";
const REDIRECT_CACHE_CONTROL = "public, max-age=300";
const SITE_HEADERS = {
  "x-content-type-options": "nosniff",
  "referrer-policy": "strict-origin-when-cross-origin",
  "strict-transport-security": "max-age=31536000",
};

function withSiteHeaders(headers, release) {
  for (const [name, value] of Object.entries(SITE_HEADERS)) headers.set(name, value);
  if (release) headers.set(RELEASE_HEADER, release);
  return headers;
}

function textResponse(status, body, release, extra = {}) {
  const headers = new Headers({ "content-type": "text/plain; charset=utf-8", "cache-control": "no-store", ...extra });
  return new Response(body, { status, headers: withSiteHeaders(headers, release) });
}

function redirect(location, release) {
  const headers = new Headers({ location, "cache-control": REDIRECT_CACHE_CONTROL });
  return new Response(null, { status: 301, headers: withSiteHeaders(headers, release) });
}

function normalizeMount(mount) {
  return String(mount || "").replace(/\/+$/, "");
}

/* Which release path a request maps to. The mount comparison is against the
   mount plus its slash, so `/docsfoo` is not under `/docs`. A host naming
   neither declared target is refused rather than served permissively. */
export function route(url, env) {
  const host = url.hostname.toLowerCase().replace(/\.$/, "");
  let mount = null;
  if (host === String(env.CANONICAL_HOST).toLowerCase()) mount = normalizeMount(env.CANONICAL_MOUNT);
  else if (host === String(env.MIRROR_HOST).toLowerCase()) mount = normalizeMount(env.MIRROR_MOUNT);
  if (!mount) return { kind: "not-found" };
  if (url.pathname === mount) return { kind: "redirect", location: `${mount}/${url.search}` };
  if (url.pathname.startsWith(`${mount}/`)) return { kind: "serve", path: url.pathname.slice(mount.length) };
  return { kind: "not-found" };
}

/* The URL path as the object key's tail. Keys are stored decoded, so the path
   is decoded too; a path that does not decode, or that names a dot segment
   once decoded, addresses nothing a release could carry. */
export function keyTail(path) {
  let decoded;
  try {
    decoded = decodeURIComponent(path);
  } catch {
    return null;
  }
  if (decoded.includes("\0")) return null;
  if (decoded.split("/").some((segment) => segment === "." || segment === "..")) return null;
  return decoded.endsWith("/") ? `${decoded}index.html` : decoded;
}

function lastSegmentHasExtension(path) {
  return path.slice(path.lastIndexOf("/") + 1).includes(".");
}

function onMirror(url, env) {
  return url.hostname.toLowerCase().replace(/\.$/, "") === String(env.MIRROR_HOST).toLowerCase();
}

/* The 404 page is served at whatever path missed, so its links are absolute and
   built for the canonical mount. On the mirror host they are re-rooted onto the
   mirror mount; this is the one response whose bytes the Worker changes. */
async function notFound(env, release, method, url) {
  const page = await env.SITE.get(`releases/${release}/404.html`);
  if (page === null) return textResponse(404, "Not Found\n", release, { "cache-control": NOT_FOUND_CACHE_CONTROL });
  const headers = new Headers();
  page.writeHttpMetadata(headers);
  if (!headers.has("content-type")) headers.set("content-type", "text/html; charset=utf-8");
  headers.set("cache-control", NOT_FOUND_CACHE_CONTROL);
  withSiteHeaders(headers, release);
  if (method === "HEAD") {
    await page.body.cancel();
    return new Response(null, { status: 404, headers });
  }
  const canonical = normalizeMount(env.CANONICAL_MOUNT);
  const mirror = normalizeMount(env.MIRROR_MOUNT);
  if (url && onMirror(url, env) && canonical && mirror && canonical !== mirror) {
    const body = (await page.text()).replaceAll(`"${canonical}/`, `"${mirror}/`);
    return new Response(body, { status: 404, headers });
  }
  return new Response(page.body, { status: 404, headers });
}

function languageRoots(env) {
  return String(env.LANGUAGE_ROOTS || "")
    .split(",")
    .map((root) => root.trim())
    .filter(Boolean);
}

/* The apex holds only the language entry; every page lives under a language
   root. A miss on an apex path that names no language root is the same page
   under the source-language root, where links from before the roots existed
   now live. Redirecting rather than serving a copy keeps one URL per page. */
async function sourceRootRedirect(env, release, url, path, tail) {
  const source = String(env.SOURCE_ROOT || "").trim();
  const first = tail.split("/")[1] || "";
  if (!source || languageRoots(env).includes(first)) return null;
  const candidate = `releases/${release}/${source}${tail}`;
  let found = await env.SITE.head(candidate);
  if (found === null && !lastSegmentHasExtension(tail)) found = await env.SITE.head(`${candidate}/index.html`);
  if (found === null) return null;
  const mount = url.pathname.slice(0, url.pathname.length - path.length);
  return redirect(`${mount}/${source}${path}${url.search}`, release);
}

async function serve(request, env, path, release) {
  const url = new URL(request.url);
  const tail = keyTail(path);
  if (tail === null) return notFound(env, release, request.method, url);
  const key = `releases/${release}${tail}`;
  const object = await env.SITE.get(key, { onlyIf: request.headers });
  if (object === null) {
    /* `/docs/es` is the directory `/docs/es/` when the release carries its
       index. Redirecting keeps relative references resolving against the
       directory, which a mount-relative site depends on. A pathname starting
       with `//` would make the redirect scheme-relative, so it is refused. */
    if (!path.endsWith("/") && !lastSegmentHasExtension(tail) && !url.pathname.startsWith("//")) {
      const index = await env.SITE.head(`${key}/index.html`);
      if (index !== null) return redirect(`${url.pathname}/${url.search}`, release);
    }
    if (!url.pathname.startsWith("//")) {
      const moved = await sourceRootRedirect(env, release, url, path, tail);
      if (moved !== null) return moved;
    }
    return notFound(env, release, request.method, url);
  }
  const headers = new Headers();
  object.writeHttpMetadata(headers);
  headers.set("etag", object.httpEtag);
  withSiteHeaders(headers, release);
  if (!("body" in object)) {
    const conditional = request.headers.has("if-none-match") || request.headers.has("if-modified-since");
    return new Response(null, { status: conditional ? 304 : 412, headers });
  }
  if (request.method === "HEAD") {
    await object.body.cancel();
    headers.set("content-length", String(object.size));
    return new Response(null, { status: 200, headers });
  }
  return new Response(object.body, { status: 200, headers });
}

export default {
  async fetch(request, env) {
    const release = String(env.RELEASE_ID || "").trim();
    try {
      if (request.method !== "GET" && request.method !== "HEAD") {
        return textResponse(405, "Method Not Allowed\n", release, { allow: "GET, HEAD" });
      }
      if (!release) return textResponse(503, "Service Unavailable: no release is configured\n", release);
      const target = route(new URL(request.url), env);
      if (target.kind === "redirect") return redirect(target.location, release);
      if (target.kind === "not-found") return await notFound(env, release, request.method, new URL(request.url));
      return await serve(request, env, target.path, release);
    } catch (err) {
      /* Only the error's own name and message are logged: the request, and
         every header it carries, must never reach the log. */
      const { name, message } = err instanceof Error ? err : { name: "Error", message: String(err) };
      console.error(`${name}: ${message}`);
      return textResponse(500, "Internal Server Error\n", release);
    }
  },
};
