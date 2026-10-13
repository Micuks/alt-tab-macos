# Window thumbnail capture eligibility

- With the switcher closed and background captures disabled, focus changes must not dispatch screenshots.
- Native-tab preservation obeys the same preference; an uncaptured background tab can use its previous
  thumbnail or app icon. Focused captures do not override the user's energy/privacy setting.
- Opening the switcher permits thumbnails even when background capture is off.
- Turning background capture off while a focused-window throttle tail is queued prevents that tail from
  dispatching another screenshot.
- Every screenshot producer and the final OS dispatch boundary recheck live eligibility. Requests queued
  during a switcher session cannot become hidden background captures after that session closes.
- Full-resolution Preview captures are useful only during a live switcher session.
- A revoked screen-recording permission, a locked screen, or shortcuts configured without captures blocks
  requests regardless of session/background settings.

`WindowThumbnailsCaptureTests.swift` is a standalone macOS regression harness, compiled together with the
production `WindowThumbnails`, `Throttler`, and `SchedulingPolicy` implementations. Only OS/UI dependencies
are replaced with spies. It exercises the real focus producer and preference changes while a real throttle
tail is pending. Run `bash scripts/fork/test_window_captures.sh`; the fork release workflow also runs it.
