#!/usr/bin/env bash
set -euo pipefail

capture_test_dir=$(mktemp -d)
trap 'rm -rf "$capture_test_dir"' EXIT
swiftc -swift-version 5 -D WINDOW_CAPTURE_TESTS -parse-as-library \
  src/util/SchedulingPolicy.swift src/util/Throttler.swift \
  src/switcher/state/WindowThumbnails.swift src/switcher/state/WindowThumbnailsCaptureTests.swift \
  -o "$capture_test_dir/capture-tests"
"$capture_test_dir/capture-tests"
