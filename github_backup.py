"""Background GitHub snapshots. Only explicit run files are uploaded, never the worktree."""
import argparse
import base64
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import threading
import uuid
import zipfile

from run_support import write_metadata

DEFAULT_REPO = 'memo-ozdincer/cmp-resistivity'
BRANCH = 'main'
MAX_INPUT_BYTES = 40 * 1024 * 1024


class GitHubError(RuntimeError):
    pass


def complete_csv_prefix(content):
    """Preserve complete records, including quoted fields containing line breaks."""
    # Drop a byte-incomplete UTF-8 suffix before parsing; the next snapshot catches it.
    text = content.decode('utf-8', errors='ignore')
    stream = io.StringIO(text, newline='')
    reader = csv.reader(stream, strict=True)
    end = 0
    width = None
    try:
        for row in reader:
            position = stream.tell()
            if text[position - 1:position] != '\n':
                break
            if width is None:
                width = len(row)
            if len(row) != width:
                break
            end = position
    except csv.Error:
        pass  # A record in flight will be included once complete.
    return text[:end].encode('utf-8')


def github_api(endpoint, method='GET', payload=None):
    command = ['gh', 'api', '--hostname', 'github.com', endpoint, '--method', method,
               '-H', 'Accept: application/vnd.github.object+json']
    if payload is not None:
        command += ['--input', '-']
    try:
        result = subprocess.run(command, input=json.dumps(payload) if payload is not None else None,
                                text=True, encoding='utf-8', capture_output=True, timeout=20)
    except FileNotFoundError as exc:
        raise GitHubError('Install GitHub CLI (gh), reopen PowerShell, and run gh auth login.') from exc
    except subprocess.TimeoutExpired as exc:
        raise GitHubError('GitHub request timed out; local data is preserved.') from exc
    if result.returncode:
        # Do not echo arbitrary CLI output, credentials or request bodies to run metadata.
        match = re.search(r'HTTP (\d{3})', result.stderr)
        raise GitHubError('GitHub request failed' + (f' (HTTP {match[1]})' if match else '') +
                          '; check internet, gh auth status, and repository write access.')
    return json.loads(result.stdout)


def validate_access(repo):
    if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repo):
        raise ValueError('GitHub repository must be OWNER/REPO.')
    info = github_api(f'repos/{repo}')
    if not info.get('permissions', {}).get('push'):
        raise GitHubError(f'The gh account needs write access to {repo}. Run gh auth login.')


class GitHubBackup:
    def __init__(self, path, repo=DEFAULT_REPO, interval=300, api=github_api):
        self.path = Path(path)
        self.repo, self.interval, self.api = repo, interval, api
        self.status_path = self.path.with_suffix(self.path.suffix + '.backup.json')
        self.snapshot_path = self.path.with_suffix(self.path.suffix + '.backup.zip')
        previous = json.loads(self.status_path.read_text(encoding='utf-8')) if self.status_path.exists() else {}
        self.run_id = previous.get('run_id') or uuid.uuid4().hex
        if not re.fullmatch(r'[0-9a-f]{32}', self.run_id):
            raise ValueError('Invalid backup run ID in local sidecar.')
        self.remote_path = f'live/{self.run_id}/snapshot.zip'
        self.status = dict(previous, run_id=self.run_id, repository=repo, branch=BRANCH,
                           remote_path=self.remote_path,
                           url=f'https://github.com/{repo}/blob/{BRANCH}/{self.remote_path}')
        self.wake = threading.Event()
        self.stopping = threading.Event()
        self.thread = None

    def _snapshot(self):
        """Read bounded prefixes. A CSV/event record being written is deferred to the next backup."""
        entries = {}
        remaining = MAX_INPUT_BYTES
        for path in [self.path, self.path.with_suffix(self.path.suffix + '.json'),
                     self.path.with_suffix(self.path.suffix + '.events.jsonl')]:
            if not path.exists():
                continue
            size = path.stat().st_size
            if size > remaining:
                raise GitHubError('Run exceeds 40 MiB snapshot limit; local data remains intact. Start a new segment.')
            with path.open('rb') as stream:
                content = stream.read(size)
            remaining -= len(content)
            if path == self.path:
                content = complete_csv_prefix(content)
            elif path.suffix == '.jsonl':
                content = content[:content.rfind(b'\n') + 1]
            else:
                json.loads(content)  # Never upload a truncated metadata file.
            entries[path.name] = content
        if self.path.name not in entries or not entries[self.path.name]:
            raise GitHubError('No complete CSV header/rows available yet.')
        manifest = {'snapshot_utc': datetime.now(timezone.utc).isoformat(),
                    'run_id': self.run_id, 'source_csv': self.path.name,
                    'note': 'CSV and sidecars are sequential snapshots, not simultaneous instrument readings.',
                    'files': {name: {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                              for name, data in entries.items()}}
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, content in entries.items():
                archive.writestr(name, content)
            archive.writestr('backup_manifest.json', json.dumps(manifest, indent=2))
        content = buffer.getvalue()
        temporary = self.snapshot_path.with_name(self.snapshot_path.name + '.tmp')
        temporary.write_bytes(content)
        temporary.replace(self.snapshot_path)
        return content, manifest

    def upload_once(self):
        self.status.update(state='uploading', last_attempt_utc=datetime.now(timezone.utc).isoformat())
        try:
            content, manifest = self._snapshot()
            endpoint = f'repos/{self.repo}/contents/{self.remote_path}'
            payload = {'message': f'Back up {self.path.name}', 'branch': BRANCH,
                       'content': base64.b64encode(content).decode('ascii')}
            try:
                previous = self.api(endpoint + f'?ref={BRANCH}')
                payload['sha'] = previous['sha']
            except GitHubError as exc:
                if 'HTTP 404' not in str(exc):
                    raise
            result = self.api(endpoint, 'PUT', payload)
            self.status.update(state='uploaded', last_success_utc=datetime.now(timezone.utc).isoformat(),
                               snapshot_utc=manifest['snapshot_utc'], files=manifest['files'],
                               commit_sha=result['commit']['sha'], error=None)
            print(f"GitHub backup uploaded: {self.status['url']}", flush=True)
            success = True
        except Exception as exc:
            self.status.update(state='pending_retry', error=f'{type(exc).__name__}: {exc}')
            print(f'GitHub backup pending: {exc} Local acquisition is unaffected.', flush=True)
            success = False
        write_metadata(self.status_path, self.status)
        return success

    def _worker(self):
        while True:
            self.wake.wait(self.interval)
            self.wake.clear()
            final = self.stopping.is_set()
            try:
                self.upload_once()
            except Exception as exc:
                print(f'GitHub backup could not save its status: {type(exc).__name__}. Local acquisition continues.', flush=True)
            if final:
                return

    def start(self):
        self.thread = threading.Thread(target=self._worker, name='github-backup', daemon=True)
        self.thread.start()
        self.wake.set()

    def finish(self):
        self.stopping.set()
        self.wake.set()
        self.thread.join(timeout=30)
        if self.thread.is_alive() or self.status.get('state') != 'uploaded':
            print(f'Final GitHub backup not confirmed. Keep local files; retry: uv run python github_backup.py "{self.path}"', flush=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='Upload/retry a saved run and its sidecars to GitHub.')
    parser.add_argument('csv', type=Path)
    parser.add_argument('--repo', default=DEFAULT_REPO)
    args = parser.parse_args(argv)
    try:
        validate_access(args.repo)
        if not args.csv.is_file():
            parser.error(f'CSV does not exist: {args.csv}')
        return 0 if GitHubBackup(args.csv, repo=args.repo).upload_once() else 1
    except (GitHubError, ValueError) as exc:
        parser.exit(1, f'{exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
