# Fork synchronization and releases

- `Fork sync and release` checks the latest stable official GitHub release every six hours and on a push to `master`. It also supports manual runs; `rebuild` forces a new revision.
- Merge the official tag into the existing fork history. Never reset the fork to upstream, rebase published commits, or overwrite conflicted patches. `UPSTREAM_TAG.txt` records the merged official release.
- A merge conflict or a lost patch aborts the merge and fails the workflow. Resolve conflicts locally, retain the fork behavior, run checks, and push the resolved merge to `master`.
- Source checks pin Pro initialization/state computation, prompt suppression, activation URL suppression, the bundle identifier, the independent Sparkle public key, and both update-feed entry points. `ForkLicenseTests` checks Pro availability after trial expiration and with an invalid stored license without touching the stored key.
- The upstream `LicenseManagerTests` encodes paid/trial behavior and is skipped for this fork. The remaining upstream tests and `ForkLicenseTests` run normally.
- Sync commits use `[skip ci]`; the same workflow builds the merged SHA explicitly. This avoids depending on a new push event from `GITHUB_TOKEN`.
- Published source SHAs with an appcast are not rebuilt unless requested. Failed builds are retried by the next scheduled run. Workflow concurrency prevents two releases from racing.
- Release tags are `v<official version>-fork.<workflow run number>`. `CFBundleVersion` is `<official version>.<workflow run number>` so changes to the fork on the same official version are updateable. `CFBundleShortVersionString` remains the official version.
- Debug compilation uses `ai/build.sh`. Release compilation produces a universal Intel/Apple silicon app. Both retain the fork's ad-hoc signature, absent TeamID, bundle ID, and `AltTab.app` name. Do not silently switch signing identities.
- Archive with `ditto` to preserve framework symlinks. Sign the exact ZIP using `SPARKLE_ED_PRIVATE_KEY` from GitHub Secrets, provided to Sparkle through stdin. Verify that signature independently against the public key embedded in the built app before publishing.
- Stage the ZIP, `appcast.xml`, and `SHA256SUMS` in a draft release, then publish it as latest. Until publication, the previous latest release remains the update source.
- The app's plist and Sparkle delegate both select `https://github.com/Micuks/alt-tab-macos/releases/latest/download/appcast.xml`. Feed enclosures refer only to this fork's release binaries. There is no official-feed fallback. Sparkle verifies archives before extraction.
- Install the first update-enabled fork build manually. Existing fork builds still use the official feed and public key, so they cannot securely bootstrap into this new update source through the official updater.
- Preserve the Sparkle private key across all future builds. Its public half is pinned in `Info.plist` and `scripts/fork/config.json`; losing or rotating the key requires a migration. The private key must never be committed or passed in command arguments/logs.
- GitHub can disable scheduled workflows after 60 days of repository inactivity. Re-enable the workflow in Actions if GitHub suspends it.

Validation: `python3 -m unittest discover -s scripts/fork -p '*Tests.py'` exercises real git merges, conflict rollback, silent patch regression rollback, idempotency, and fork appcast metadata. GitHub macOS CI runs compilation, application tests, universal-binary checks, code signature checks, and Ed25519 verification.
