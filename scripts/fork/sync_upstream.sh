#!/usr/bin/env bash
set -euo pipefail

upstream=$(python3 -c 'import json; print(json.load(open("scripts/fork/config.json"))["upstream"])')
tag=$(gh api "repos/$upstream/releases/latest" --jq .tag_name)
if [[ ! "$tag" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "::error::Unsupported upstream release tag: $tag"
  exit 1
fi
git fetch --no-tags "https://github.com/$upstream.git" "refs/tags/$tag:refs/remotes/upstream/latest-release"
if git merge-base --is-ancestor refs/remotes/upstream/latest-release HEAD; then
  python3 scripts/fork/release.py validate
  exit 0
fi
if [[ -n "$(git status --porcelain)" ]]; then
  echo "::error::Commit or stash local changes before merging an official release."
  exit 1
fi
abort_merge() {
  if git rev-parse -q --verify MERGE_HEAD >/dev/null; then git merge --abort; fi
}
trap abort_merge EXIT
if ! git merge --no-ff --no-commit refs/remotes/upstream/latest-release; then
  echo "::error::Upstream merge conflicts; fork patches were not overwritten. Resolve the merge locally before publishing."
  git diff --name-only --diff-filter=U
  exit 1
fi
python3 - "$tag" <<'PY'
import re
import sys
from pathlib import Path
tag = sys.argv[1]
path = Path('config/base.xcconfig')
text = re.sub(r'^(CURRENT_PROJECT_VERSION|MARKETING_VERSION) = .*$', lambda m: m[1] + ' = ' + tag[1:], path.read_text(), flags=re.M)
path.write_text(text)
Path('UPSTREAM_TAG.txt').write_text(tag + '\n')
PY
git add config/base.xcconfig UPSTREAM_TAG.txt
python3 scripts/fork/release.py validate
git commit -m "chore: sync official $tag while preserving fork patches [skip ci]"
