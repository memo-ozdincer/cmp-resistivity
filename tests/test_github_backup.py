import base64
import io
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import threading
import unittest
from unittest.mock import patch
import zipfile

import daq_example
from github_backup import BRANCH, GitHubBackup, GitHubError, complete_csv_prefix, github_api


class FakeGitHub:
    def __init__(self):
        self.branch = False
        self.content = None
        self.puts = []

    def __call__(self, endpoint, method='GET', payload=None):
        if endpoint.endswith('/git/ref/heads/' + BRANCH):
            if not self.branch:
                raise GitHubError('GitHub request failed (HTTP 404)')
            return {'object': {'sha': 'base'}}
        if endpoint.endswith('/git/ref/heads/main'):
            return {'object': {'sha': 'base'}}
        if endpoint.endswith('/git/refs'):
            self.branch = True
            return {}
        if '/contents/' not in endpoint:
            return {'default_branch': 'main'}
        if method == 'GET':
            if self.content is None:
                raise GitHubError('GitHub request failed (HTTP 404)')
            return {'sha': str(len(self.puts))}
        self.puts.append(payload)
        self.content = base64.b64decode(payload['content'])
        return {'commit': {'sha': str(len(self.puts))}}


class BackupTests(unittest.TestCase):
    def test_multiline_partial_csv_record_is_deferred(self):
        full = b'a,b\n0,"line one\nline two"\n'
        self.assertEqual(complete_csv_prefix(full + b'1,"unfinished\n'), full)
        self.assertEqual(complete_csv_prefix(full + b'1,'), full)

    def fixture(self, directory):
        path = Path(directory) / 'run.csv'
        path.write_bytes(b'sample_index,value\r\n0,1\r\n1,incomplete')
        path.with_suffix('.csv.json').write_text('{"status":"running"}')
        path.with_suffix('.csv.events.jsonl').write_bytes(b'{"label":"cold"}\n{"partial":')
        (path.parent / 'unrelated-secret.txt').write_text('must not upload')
        return path

    def test_snapshot_exact_allowlist_complete_rows_and_retry_same_identity(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(directory)
            before = path.read_bytes()
            api = FakeGitHub()
            backup = GitHubBackup(path, api=api)
            self.assertTrue(backup.upload_once())
            with zipfile.ZipFile(io.BytesIO(api.content)) as archive:
                self.assertEqual(set(archive.namelist()), {'run.csv', 'run.csv.json',
                                 'run.csv.events.jsonl', 'backup_manifest.json'})
                self.assertEqual(archive.read('run.csv'), b'sample_index,value\r\n0,1\r\n')
                self.assertEqual(archive.read('run.csv.events.jsonl'), b'{"label":"cold"}\n')
            self.assertEqual(path.read_bytes(), before)
            second = GitHubBackup(path, api=api)
            self.assertEqual(second.remote_path, backup.remote_path)
            self.assertTrue(second.upload_once())
            self.assertEqual(api.puts[-1]['sha'], '1')
            self.assertEqual(api.puts[-1]['branch'], BRANCH)

    def test_offline_preserves_local_snapshot_then_catches_up(self):
        with TemporaryDirectory() as directory:
            path = self.fixture(directory)
            def offline(*args):
                raise GitHubError('offline')
            backup = GitHubBackup(path, api=offline)
            self.assertFalse(backup.upload_once())
            self.assertTrue(backup.snapshot_path.exists())
            self.assertEqual(json.loads(backup.status_path.read_text())['state'], 'pending_retry')
            with path.open('ab') as stream:
                stream.write(b'\r\n2,3\r\n')
            api = FakeGitHub()
            backup.api = api
            self.assertTrue(backup.upload_once())
            with zipfile.ZipFile(io.BytesIO(api.content)) as archive:
                self.assertEqual(archive.read('run.csv'), path.read_bytes())

    def test_slow_network_does_not_block_sample_callbacks_final_metadata_uploaded(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'SIMULATED_test.csv'
            api = FakeGitHub()
            entered, release = threading.Event(), threading.Event()
            def slow_api(*args):
                entered.set()
                if not release.wait(5):
                    raise AssertionError('Sampling blocked on network')
                return api(*args)
            backup = GitHubBackup(path, api=slow_api)
            original = daq_example.display
            observations = []
            def display(row):
                observations.append(row)
                if len(observations) == 2:
                    self.assertTrue(entered.wait(2))
                    release.set()
                original(row)
            clock = [0.]
            with patch('github_backup.validate_access'), patch('github_backup.GitHubBackup', return_value=backup), patch('daq_example.display', display), patch(
                    'event_handler.time.monotonic', side_effect=lambda: clock[0]), patch(
                    'event_handler.time.sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0]+seconds)):
                result = daq_example.main(['--simulate', '--duration', '.06', '--period', '.01',
                    '--console-every', '.001', '--github-backup', '--output', str(path)])
            self.assertEqual(result, 0)
            self.assertGreaterEqual(len(observations), 2)
            self.assertFalse(backup.thread.is_alive())
            with zipfile.ZipFile(io.BytesIO(api.content)) as archive:
                final_metadata = json.loads(archive.read('SIMULATED_test.csv.json'))
                self.assertEqual(final_metadata['status'], 'complete')
                self.assertEqual(final_metadata['sensor_calibration']['profile']['sensors']['sample']['channel'], 2)
                self.assertEqual(archive.read('SIMULATED_test.csv'), path.read_bytes())

    def test_auth_failure_before_hardware_and_no_credentials_in_errors(self):
        with patch('github_backup.validate_access', side_effect=GitHubError('not authenticated')):
            with self.assertRaises(SystemExit):
                daq_example.main(['--github-backup'])
        with patch('github_backup.subprocess.run') as run:
            run.return_value.returncode = 1
            run.return_value.stderr = 'SECRET TOKEN HTTP 403'
            with self.assertRaisesRegex(GitHubError, 'HTTP 403') as caught:
                github_api('repos/example/repo')
            self.assertNotIn('SECRET', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
