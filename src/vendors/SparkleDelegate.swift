import Cocoa
import Sparkle

class SparkleDelegate: NSObject, SPUUpdaterDelegate {
    enum UpdateCheckResult {
        case updateAvailable(SUAppcastItem)
        case upToDate
    }

    /// Shared across feedback, manual, and scheduled checks; each launch starts with a fresh cache.
    var cachedResult: UpdateCheckResult?

    var onNextCheckCompletion: ((UpdateCheckResult) -> Void)?

    func feedURLString(for updater: SPUUpdater) -> String? {
        return Endpoints.appcastUrl
    }

    func updater(_ updater: SPUUpdater, didFindValidUpdate item: SUAppcastItem) {
        store(.updateAvailable(item))
    }

    func updaterDidNotFindUpdate(_ updater: SPUUpdater) {
        store(.upToDate)
    }

    private func store(_ result: UpdateCheckResult) {
        cachedResult = result
        let cb = onNextCheckCompletion
        onNextCheckCompletion = nil
        cb?(result)
    }
}
