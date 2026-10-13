# Process admission and startup lifetime

- Install the running-application observer before reading the initial snapshot, so processes exiting
  during startup still have an observed removal.
- A LaunchServices application object is metadata, not proof of a live process. On macOS 27.0
  (26A5425a), a fresh AltTab launch admitted six already-exited processes from the initial snapshot;
  those entries remained in the AX recovery table.
- Initial/batched admission checks kernel liveness before asynchronous classification. It rechecks at
  application creation because termination can be processed while classification is in flight.
- The synchronous AX/WindowServer lookup path uses the same creation gate. It rejects invalid, exited,
  and zombie processes without creating a new tracked application.
- Recheck after reading AppKit properties in the constructor, since those reads can block. Rejecting
  the object clears attention state, and its generation-aware deinitializer clears AX subscriptions.
- Existing tracked applications keep their fast lookup path and are removed by the existing process
  observer. This adds no periodic polling.

The OS-facing creation path is verified with the live `--qa-state` snapshot: compare every tracked pid
to kernel liveness immediately after obtaining the snapshot, and repeat after normal process churn.
`ProcessLivenessTests` pins the kernel semantics, including EPERM, invalid pids, reaped children and
zombies. Application construction registers real AX/AppKit observers, so a pure boolean admission test
would not reproduce the callback/creation ordering; the live startup check is the regression signal.
