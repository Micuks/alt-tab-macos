#!/usr/bin/env python3
import base64
from datetime import datetime, timezone
from email.utils import format_datetime
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
CONFIG = json.loads((ROOT / 'scripts/fork/config.json').read_text())
REPOSITORY = CONFIG['repository']
FEED_URL = f'https://github.com/{REPOSITORY}/releases/latest/download/appcast.xml'
SPARKLE = 'http://www.andymatuschak.org/xml-namespaces/sparkle'
ET.register_namespace('sparkle', SPARKLE)


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def validate_source(root=ROOT):
    info = plistlib.loads((root / 'Info.plist').read_bytes())
    require(info['SUFeedURL'] == FEED_URL, 'Bundle update feed must belong to the fork')
    require(info['SUPublicEDKey'] == CONFIG['public_key'], 'Sparkle signing key changed')
    require(len(base64.b64decode(info['SUPublicEDKey'], validate=True)) == 32, 'Invalid Sparkle public key')
    require(info.get('SUVerifyUpdateBeforeExtraction') is True, 'Archives must be verified before extraction')
    require(FEED_URL in (root / 'src/api/Endpoints.swift').read_text(), 'Delegate update feed must belong to the fork')
    delegate = (root / 'src/vendors/SparkleDelegate.swift').read_text()
    require('return Endpoints.appcastUrl' in delegate, 'Sparkle delegate must select the fork feed')
    manager = (root / 'src/pro/license/LicenseManager.swift').read_text()
    require(re.search(r'func initialize\(\)\s*\{\s*state = \.pro\s*\}', manager), 'Fork initialization patch lost')
    require(re.search(r'func computeState\(\) -> LicenseState\s*\{\s*return \.pro\s*\}', manager), 'Fork Pro patch lost')
    app = (root / 'src/App.swift').read_text()
    require('ProTransitionManager.shared.onAction =' not in app, 'Fork prompt suppression patch lost')
    require('handleCustomUrl' not in app, 'Fork activation URL patch lost')
    thumbnails = (root / 'src/switcher/state/WindowThumbnails.swift').read_text()
    require('func capturesAreAllowed' in thumbnails and 'force: true' not in thumbnails, 'Fork background capture policy lost')
    capture = (root / 'src/events/WindowCaptureEvents.swift').read_text()
    require(capture.count('WindowThumbnails.capturesAreAllowed') >= 6, 'Queued captures must recheck live eligibility')
    applications = (root / 'src/switcher/state/Applications.swift').read_text()
    require('makeLiveApplication(runningApp, pid)' in applications and 'processIdentifier.isAlive(), !processIdentifier.isZombie()' in applications,
            'Fork process admission liveness checks lost')
    config = (root / 'config/base.xcconfig').read_text()
    require(re.search(r'^PRODUCT_BUNDLE_IDENTIFIER = ' + re.escape(CONFIG['bundle_id']) + r'$', config, re.M), 'Bundle identifier changed')
    workflow = (root / '.github/workflows/ci_cd.yml').read_text()
    require("if: github.repository == 'lwouis/alt-tab-macos'" in workflow, 'Upstream release workflow must not run in the fork')


def prepare():
    validate_source()
    tag = (ROOT / 'UPSTREAM_TAG.txt').read_text().strip()
    require(re.fullmatch(r'v\d+\.\d+\.\d+', tag), 'Invalid upstream tag')
    upstream_version = tag[1:]
    revision = int(os.environ['GITHUB_RUN_NUMBER'])
    version = f'{upstream_version}.{revision}'
    release_tag = f'{tag}-fork.{revision}'
    (ROOT / 'config/local.xcconfig').write_text(f'CURRENT_PROJECT_VERSION = {version}\nMARKETING_VERSION = {upstream_version}\n')
    with open(os.environ['GITHUB_OUTPUT'], 'a') as output:
        output.write(f'version={version}\ntag={release_tag}\n')


def make_appcast(info, release_tag, archive_name, length, signature):
    require(len(base64.b64decode(signature, validate=True)) == 64, 'Invalid update signature')
    require(re.fullmatch(r'v\d+\.\d+\.\d+-fork\.\d+', release_tag), 'Invalid fork tag')
    require(Path(archive_name).name == archive_name, 'Archive name must be a basename')
    rss = ET.Element('rss', {'version': '2.0'})
    channel = ET.SubElement(rss, 'channel')
    ET.SubElement(channel, 'title').text = 'AltTab — Micuks fork'
    ET.SubElement(channel, 'link').text = f'https://github.com/{REPOSITORY}'
    ET.SubElement(channel, 'description').text = 'AltTab builds with fork patches'
    ET.SubElement(channel, 'language').text = 'en'
    item = ET.SubElement(channel, 'item')
    ET.SubElement(item, 'title').text = f'AltTab {info["CFBundleShortVersionString"]} (fork build {info["CFBundleVersion"]})'
    ET.SubElement(item, 'pubDate').text = format_datetime(datetime.now(timezone.utc), usegmt=True)
    ET.SubElement(item, 'link').text = f'https://github.com/{REPOSITORY}/releases/tag/{release_tag}'
    ET.SubElement(item, 'description').text = f'Official {(ROOT / "UPSTREAM_TAG.txt").read_text().strip()} with the fork patches retained.'
    for name, value in [('version', info['CFBundleVersion']), ('shortVersionString', info['CFBundleShortVersionString']), ('minimumSystemVersion', info['LSMinimumSystemVersion'])]:
        ET.SubElement(item, f'{{{SPARKLE}}}{name}').text = value
    ET.SubElement(item, 'enclosure', {
        'url': f'https://github.com/{REPOSITORY}/releases/download/{release_tag}/{archive_name}',
        f'{{{SPARKLE}}}edSignature': signature,
        'length': str(length),
        'type': 'application/octet-stream',
    })
    ET.indent(rss, space='  ')
    return ET.tostring(rss, encoding='utf-8', xml_declaration=True)


def package():
    validate_source()
    app = ROOT / 'DerivedData/Build/Products/Release/AltTab.app'
    info = plistlib.loads((app / 'Contents/Info.plist').read_bytes())
    require(info['CFBundleIdentifier'] == CONFIG['bundle_id'], 'Built bundle identifier changed')
    require(info['SUFeedURL'] == FEED_URL, 'Built app uses an unexpected feed')
    require(info['SUPublicEDKey'] == CONFIG['public_key'], 'Built app uses an unexpected public key')
    require(info['CFBundleVersion'] == os.environ['FORK_VERSION'], 'Built app version differs from release version')
    subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    identity = subprocess.run(['codesign', '-dvv', str(app)], capture_output=True, text=True, check=True).stderr
    require('Signature=adhoc' in identity and 'TeamIdentifier=not set' in identity, 'Fork code-signing identity changed')
    architectures = run('lipo', '-archs', str(app / 'Contents/MacOS/AltTab')).split()
    require(set(architectures) == {'arm64', 'x86_64'}, 'Release must support Intel and Apple silicon')
    output = ROOT / 'build/fork-release'
    output.mkdir(parents=True, exist_ok=True)
    archive = output / f'AltTab-{os.environ["FORK_TAG"]}.zip'
    subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app), str(archive)], check=True)
    key = os.environ['SPARKLE_ED_PRIVATE_KEY']
    signature = run(str(ROOT / 'vendor/Sparkle/bin/sign_update'), '--ed-key-file', '-', '-p', str(archive), input=key + '\n')
    subprocess.run(['swift', str(ROOT / 'scripts/fork/verify_update.swift'), info['SUPublicEDKey'], signature, str(archive)], check=True)
    (output / 'appcast.xml').write_bytes(make_appcast(info, os.environ['FORK_TAG'], archive.name, archive.stat().st_size, signature))
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / 'SHA256SUMS').write_text(f'{digest}  {archive.name}\n')
    upstream_tag = (ROOT / 'UPSTREAM_TAG.txt').read_text().strip()
    commit = run('git', 'rev-parse', 'HEAD')
    (output / 'release-notes.md').write_text(
        f'Built from official [{upstream_tag}](https://github.com/{CONFIG["upstream"]}/releases/tag/{upstream_tag}) with our fork patches retained.\n\n'
        f'Source commit: `{commit}`. Supports Intel and Apple silicon; requires macOS {info["LSMinimumSystemVersion"]} or later.\n\n'
        'Download the ZIP, unzip, and move `AltTab.app` to `/Applications`. This personal build uses ad-hoc signing and is not notarized.\n\n'
        'Install the first fork-update-enabled build manually once. Subsequent manual and automatic update checks use this repository and verify updates with our own Sparkle key.\n'
    )


if __name__ == '__main__':
    commands = {'validate': validate_source, 'prepare': prepare, 'package': package}
    commands[sys.argv[1]]()
