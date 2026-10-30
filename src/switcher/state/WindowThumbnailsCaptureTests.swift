#if WINDOW_CAPTURE_TESTS
import Cocoa

final class Window {
    var cgWindowId: CGWindowID?
    var size: CGSize? = CGSize(width: 800, height: 600)
    var position: CGPoint? = .zero
    var screenId: CGDirectDisplayID?
    var isWindowlessApp = false
    var isFullscreen = false
    var thumbnail: CALayerContents?
    var capturedArea: CGRect?
    var frame: CGRect? {
        guard let position, let size else { return nil }
        return CGRect(origin: position, size: size)
    }
    var debugId: String { String(cgWindowId ?? 0) }
    init(_ wid: CGWindowID) { cgWindowId = wid }
}
enum CALayerContents {
    case cgImage(CGImage)
    func size() -> CGSize? { nil }
}
final class Session {
    var shortcutIndex = 0
    func previewFrame(_ wid: CGWindowID) -> (contents: CALayerContents, area: CGRect?)? { nil }
    func hasPreviewFrame(_ wid: CGWindowID) -> Bool { false }
}
enum SwitcherSession {
    static var current: Session?
    static var isActive: Bool { current != nil }
}
enum Preferences {
    static var captureWindowsInBackground = false
    static var anyShortcutShowsWindowCaptures = true
    static func effectivePreviewSelectedWindow(_ index: Int) -> Bool { false }
}
enum ScreenRecordingPermission {
    enum Status { case granted, notGranted }
    static var status = Status.granted
}
enum ScreenLockEvents { static var isScreenLocked = false }
enum Windows {
    static var list = [Window]()
    static func selectedWindow() -> Window? { nil }
    static func selectedNeighborhoodIds() -> [CGWindowID] { [] }
}
enum Screens { static var all = [CGDirectDisplayID: NSScreen]() }
extension NSScreen { static var preferred: NSScreen { NSScreen.main! } }
final class TilesPanel {
    static let shared = TilesPanel()
    var isKeyWindow = false
    static var maxPossibleThumbnailSize = CGSize(width: 400, height: 300)
}
enum PreviewPanel {
    static func hide() { }
    static func show(_ id: CGWindowID, _ preview: CALayerContents, _ area: CGRect) { }
}
enum RefreshCausedBy { case refreshUiAfterExternalEvent, refreshOnlyThumbnailsAfterShowUi }
enum Logger { static func debug(_ text: () -> String) { } }
final class LabeledOperationQueue: OperationQueue, @unchecked Sendable {
    var strongUnderlyingQueue: DispatchQueue { .main }
}
enum WindowCaptureScreenshots {
    static var requests = 0
    static func oneTimeScreenshots(_ windows: [Window], _ source: RefreshCausedBy, prioritizedIds: Set<CGWindowID>? = nil, fullRes: Bool = false) {
        requests += windows.count
    }
}
enum WindowCaptureScreenshotsPrivateApi {
    static func oneTimeScreenshots(_ windows: [Window], _ source: RefreshCausedBy, prioritizedIds: Set<CGWindowID>? = nil) {
        WindowCaptureScreenshots.requests += windows.count
    }
}

@main
struct WindowThumbnailsCaptureTests {
    static func main() {
        reset()
        WindowThumbnails.captureFocusedInBackground(Window(1))
        expect(0, "Background disabled must suppress focused captures")
        reset()
        Preferences.captureWindowsInBackground = true
        WindowThumbnails.captureFocusedInBackground(Window(2))
        expect(1, "Background enabled must preserve focused captures")
        WindowThumbnails.captureFocusedInBackground(Window(2))
        Preferences.captureWindowsInBackground = false
        RunLoop.main.run(until: Date().addingTimeInterval(0.95))
        expect(1, "Disabling background capture must cancel a queued throttle tail")
        reset()
        SwitcherSession.current = Session()
        WindowThumbnails.refreshAsync([Window(3)], .refreshOnlyThumbnailsAfterShowUi)
        expect(1, "An open switcher must capture thumbnails with background disabled")
        SwitcherSession.current = nil
        WindowThumbnails.refreshAsync([Window(3)], .refreshUiAfterExternalEvent)
        expect(1, "An external refresh must stop when the switcher closes")
        reset()
        Preferences.captureWindowsInBackground = true
        guard !WindowThumbnails.capturesAreAllowed(fullRes: true) else { fail("Preview captures require an active switcher") }
        SwitcherSession.current = Session()
        guard WindowThumbnails.capturesAreAllowed(fullRes: true) else { fail("Active Preview captures must be permitted") }
        ScreenLockEvents.isScreenLocked = true
        WindowThumbnails.refreshAsync([Window(4)], .refreshUiAfterExternalEvent)
        expect(0, "A locked screen must block screenshots")
        ScreenLockEvents.isScreenLocked = false
        ScreenRecordingPermission.status = .notGranted
        WindowThumbnails.refreshAsync([Window(4)], .refreshUiAfterExternalEvent)
        expect(0, "Revoked recording permission must block screenshots")
        ScreenRecordingPermission.status = .granted
        Preferences.anyShortcutShowsWindowCaptures = false
        WindowThumbnails.refreshAsync([Window(4)], .refreshUiAfterExternalEvent)
        expect(0, "Icon-only shortcuts must block screenshots")
        print("Passed 10 window capture regression cases")
    }
    static func reset() {
        WindowCaptureScreenshots.requests = 0
        WindowThumbnails.focusedCaptureThrottler.removeEntries(withPrefix: "")
        SwitcherSession.current = nil
        Preferences.captureWindowsInBackground = false
        Preferences.anyShortcutShowsWindowCaptures = true
        ScreenRecordingPermission.status = .granted
        ScreenLockEvents.isScreenLocked = false
    }
    static func expect(_ count: Int, _ message: String) {
        guard WindowCaptureScreenshots.requests == count else { fail(message + ": got \(WindowCaptureScreenshots.requests) requests, expected \(count)") }
    }
    static func fail(_ message: String) -> Never {
        fputs(message + "\n", stderr)
        exit(1)
    }
}
#endif
