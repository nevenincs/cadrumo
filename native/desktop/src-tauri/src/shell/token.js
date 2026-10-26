((origins, token) => {
  "use strict";
  // WebView2 runs initialization scripts in every frame. Only the shell
  // document, as the top frame on a shell origin, may receive the token.
  if (window.top !== window || !origins.includes(window.location.origin))
    return;
  let issued = token;
  const shell = {};
  Object.defineProperty(shell, "token", {
    configurable: true,
    enumerable: false,
    get() {
      delete shell.token;
      const value = issued;
      issued = null;
      return value;
    },
  });
  Object.defineProperty(window, "__CADRUMO_SHELL__", {
    configurable: false,
    enumerable: false,
    writable: false,
    value: shell,
  });
})(__CADRUMO_SHELL_ORIGINS__, __CADRUMO_SHELL_TOKEN__);
