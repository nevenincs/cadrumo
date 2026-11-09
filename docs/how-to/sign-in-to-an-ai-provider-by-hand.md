# Sign in to an AI provider by hand

Cadrumo signs in to an AI provider (Claude, Codex or Antigravity) from the
desktop application, under Ajustes > Proveedores de IA. When that sign-in
fails, it names this guide. The command below does the same sign-in from a
console, with the provider's own login in your terminal. You sign in once; the
application finds the result the next time it reads the provider's status.

## Before you start

You need:

- A profile that has already been opened in Cadrumo, so the application has
  started its agent for it. The command refuses a profile whose agent has never
  started.
- The desktop application's sign-in dialog closed. The dialog and this command
  share one sign-in at a time, and the command refuses while the dialog is open.
- An installed Cadrumo package. A source checkout has no bundled agent, so the
  command refuses there.
- A storage folder outside any Git project. The provider's login refuses a
  folder inside one.

The command runs against the profile you have selected in Cadrumo. Pass
`--profile` with a profile's UUID or exact label to use another.

## Sign in

Run the command for your provider:

```text
cadrumo-agent-service provider-login --provider claude
cadrumo-agent-service provider-login --provider codex
cadrumo-agent-service provider-login --provider antigravity
```

Codex also offers a device-code sign-in, for a machine where the browser
cannot open a local address:

```text
cadrumo-agent-service provider-login --provider codex --device
```

The provider's own login takes over the terminal. It may open your browser or
print a code and an address to enter on another device. Follow its prompts
there. Cadrumo does not read, store or log what the provider prints.

## What success looks like

When the provider's login ends, Cadrumo checks the result and prints one line,
`<provider> sign-in status: signed in`, then the command exits with status 0.
A line that says `signed out` or `unknown`, with its cause, means the sign-in
did not complete; the command then exits with a non-zero status. Run it again
after fixing the cause.

Reopen the provider settings in Cadrumo. The application reads the sign-in on
its next status read and shows the provider as signed in.

## Refusals

The command stops before it runs the provider's login, and says why, when:

- the provider is not `claude`, `codex` or `antigravity`, or `--device` is
  used with a provider other than `codex`;
- no profile is selected and `--profile` is not given;
- the profile's agent has not started yet: open Cadrumo with that profile
  selected, then run the command again;
- the agent folder sits inside a Git project: point `CADRUMO_STORAGE_ROOT` at a
  folder outside any Git project;
- the installation has no bundled agent;
- the application's sign-in dialog is still open: close it and run the command
  again.

## See also

- [Diagnose and repair your local setup](troubleshooting.md)
- [Environment overrides](../reference/environment-overrides.md)
