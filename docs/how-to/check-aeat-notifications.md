# Check AEAT notifications

Use this guide when you want to review locally saved DEHu notification
snapshots. This is separate from the local filing calendar: calendar commands
plan obligations from profile facts and registry rules, while notification
commands read or show DEHu notification snapshots.

Live notification capture is read-only. It does not file, answer, accept, or
reject a notification.

## Before you start

You need:

- an [active profile](profile-setup.md#what-the-active-profile-means)
- AEAT live-read authentication; see [Authenticate with AEAT](authenticate-with-aeat.md)

## Show the latest saved snapshot

Start with the latest saved snapshot:

```bash
aeat app live notifications latest
```

If no snapshot exists, the command reports an empty result instead of fetching
new data.

## Capture a fresh snapshot

Capture DEHu notifications and save them under the
[active profile](profile-setup.md#what-the-active-profile-means) bucket:

```bash
aeat app live notifications capture
```

This command runs the AEAT authentication preflight and then live-fetches the
notification snapshot. The saved row data can include certificate id, type,
concept, taxpayer names or identifiers, issue date, notification date, read
state, source URL, and mode.

## List and view snapshots

List saved snapshots:

```bash
aeat app live notifications list
```

View one snapshot by id or unambiguous prefix:

```bash
aeat app live notifications view <snapshot-id>
```

## Where this fits

Use [Plan your filing calendar](filing-calendar.md) for obligations, due dates,
overdue items, and upcoming modelos. Use this page when the question is about
DEHu messages or saved notification snapshots.

## Next steps

- [Plan your filing calendar](filing-calendar.md)
- [Authenticate with AEAT](authenticate-with-aeat.md)
- [Set up your taxpayer profile](profile-setup.md)
