import base64
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

import release


SOURCE_FILES = ['Info.plist', 'src/api/Endpoints.swift', 'src/vendors/SparkleDelegate.swift',
                'src/pro/license/LicenseManager.swift', 'src/App.swift', 'config/base.xcconfig',
                '.github/workflows/ci_cd.yml', 'UPSTREAM_TAG.txt']


def copy_sources(destination):
    for name in SOURCE_FILES:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(release.ROOT / name, target)
    shutil.copytree(release.ROOT / 'scripts/fork', destination / 'scripts/fork', ignore=shutil.ignore_patterns('__pycache__'))


class ReleaseTests(unittest.TestCase):
    def test_current_source_preserves_patches_and_fork_feed(self):
        release.validate_source()

    def test_rejects_upstream_feed_and_key(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            copy_sources(root)
            info_path = root / 'Info.plist'
            info = plistlib.loads(info_path.read_bytes())
            info['SUFeedURL'] = 'https://alt-tab.app/appcast.xml'
            info_path.write_bytes(plistlib.dumps(info))
            with self.assertRaisesRegex(ValueError, 'feed must belong'):
                release.validate_source(root)
            info['SUFeedURL'] = release.FEED_URL
            info['SUPublicEDKey'] = '2e9SQOBoaKElchSa/4QDli/nvYkyuDNfynfzBF6vJK4='
            info_path.write_bytes(plistlib.dumps(info))
            with self.assertRaisesRegex(ValueError, 'signing key changed'):
                release.validate_source(root)

    def test_appcast_uses_exact_fork_binary_version_and_compatibility(self):
        info = {'CFBundleVersion': '11.9.1.42', 'CFBundleShortVersionString': '11.9.1', 'LSMinimumSystemVersion': '12.0'}
        signature = base64.b64encode(b's' * 64).decode()
        xml = release.make_appcast(info, 'v11.9.1-fork.42', 'AltTab.zip', 123, signature)
        item = ET.fromstring(xml).find('channel/item')
        self.assertEqual(item.find(f'{{{release.SPARKLE}}}version').text, '11.9.1.42')
        self.assertEqual(item.find(f'{{{release.SPARKLE}}}minimumSystemVersion').text, '12.0')
        enclosure = item.find('enclosure')
        self.assertEqual(enclosure.attrib['url'], 'https://github.com/Micuks/alt-tab-macos/releases/download/v11.9.1-fork.42/AltTab.zip')
        self.assertEqual(enclosure.attrib['length'], '123')
        self.assertEqual(enclosure.attrib[f'{{{release.SPARKLE}}}edSignature'], signature)

    def test_appcast_rejects_invalid_signatures_and_upstream_tags(self):
        with self.assertRaises(ValueError):
            release.make_appcast({}, 'v11.9.1-fork.42', 'AltTab.zip', 1, 'invalid')
        with self.assertRaisesRegex(ValueError, 'Invalid fork tag'):
            release.make_appcast({}, 'v11.9.1', 'AltTab.zip', 1, base64.b64encode(b's' * 64).decode())


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.upstream = self.root / 'upstream'
        self.upstream.mkdir()
        copy_sources(self.upstream)
        self.git(self.upstream, 'init', '-b', 'master')
        self.configure_git(self.upstream)
        (self.upstream / 'shared.txt').write_text('base\n')
        self.git(self.upstream, 'add', '.')
        self.git(self.upstream, 'commit', '-m', 'chore: baseline')
        self.git(self.root, 'clone', str(self.upstream), 'fork')
        self.fork = self.root / 'fork'
        self.configure_git(self.fork)
        self.git(self.fork, 'config', f'url.{self.upstream}.insteadOf', 'https://github.com/lwouis/alt-tab-macos.git')
        (self.fork / 'fork-patch.txt').write_text('retain me\n')
        self.git(self.fork, 'add', '.')
        self.git(self.fork, 'commit', '-m', 'feat: fork patch')
        self.original_head = self.git(self.fork, 'rev-parse', 'HEAD')
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        gh = bin_dir / 'gh'
        gh.write_text('#!/bin/sh\nprintf "v11.9.2\\n"\n')
        gh.chmod(0o755)
        self.env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ['PATH'])

    def tearDown(self):
        self.temp.cleanup()

    def git(self, cwd, *args):
        return subprocess.check_output(['git', *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL).strip()

    def configure_git(self, cwd):
        self.git(cwd, 'config', 'user.name', 'Test')
        self.git(cwd, 'config', 'user.email', 'test@example.com')

    def upstream_release(self):
        self.git(self.upstream, 'add', '.')
        self.git(self.upstream, 'commit', '-m', 'fix: upstream release')
        self.git(self.upstream, 'tag', 'v11.9.2')

    def sync(self):
        return subprocess.run(['bash', 'scripts/fork/sync_upstream.sh'], cwd=self.fork,
                              env=self.env, text=True, capture_output=True)

    def assert_aborted(self):
        self.assertEqual(self.git(self.fork, 'rev-parse', 'HEAD'), self.original_head)
        self.assertFalse((self.fork / '.git/MERGE_HEAD').exists())
        self.assertEqual(self.git(self.fork, 'status', '--porcelain'), '')

    def test_merge_retains_patch_updates_version_and_is_idempotent(self):
        (self.upstream / 'official-fix.txt').write_text('new fix\n')
        self.upstream_release()
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((self.fork / 'fork-patch.txt').read_text(), 'retain me\n')
        self.assertEqual((self.fork / 'official-fix.txt').read_text(), 'new fix\n')
        self.assertEqual((self.fork / 'UPSTREAM_TAG.txt').read_text(), 'v11.9.2\n')
        self.assertIn('CURRENT_PROJECT_VERSION = 11.9.2', (self.fork / 'config/base.xcconfig').read_text())
        merged_head = self.git(self.fork, 'rev-parse', 'HEAD')
        result = self.sync()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.git(self.fork, 'rev-parse', 'HEAD'), merged_head)

    def test_conflict_aborts_without_losing_fork_patch(self):
        (self.fork / 'shared.txt').write_text('fork\n')
        self.git(self.fork, 'add', '.')
        self.git(self.fork, 'commit', '-m', 'fix: fork change')
        self.original_head = self.git(self.fork, 'rev-parse', 'HEAD')
        (self.upstream / 'shared.txt').write_text('upstream\n')
        self.upstream_release()
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('merge conflicts', result.stdout)
        self.assert_aborted()
        self.assertEqual((self.fork / 'shared.txt').read_text(), 'fork\n')

    def test_patch_regression_aborts_even_when_git_merge_is_clean(self):
        path = self.upstream / 'src/pro/license/LicenseManager.swift'
        path.write_text(path.read_text().replace('return .pro\n    }', 'return .trialExpired\n    }'))
        self.upstream_release()
        result = self.sync()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Fork Pro patch lost', result.stderr)
        self.assert_aborted()


if __name__ == '__main__':
    unittest.main()
