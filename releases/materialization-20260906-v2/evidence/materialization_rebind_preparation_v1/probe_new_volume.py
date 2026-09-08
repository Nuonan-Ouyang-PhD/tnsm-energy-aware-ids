"""Native non-data probe. Only writes under a newly allocated probe directory.

Leaves every probe object in place for audit; never opens a source CSV or calls
the materializer CLI. Executor bytes must match the accepted V1R2 digest.
"""
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
import platform
import plistlib
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

VOLUME = Path('/Volumes/RESEARCH_DATA')
UUID = 'FBCBD1E6-330C-452B-AD79-EF7F74B6464B'
EXECUTOR_SHA = 'ac9992005047bda7431abccafe8698d5b3b890efbf218605841730a5613b1c2c'
MINIMUM = 26745491380


def disk_info(target):
    return plistlib.loads(subprocess.check_output(
        ['diskutil', 'info', '-plist', str(target)], timeout=30))


def observation():
    info = disk_info(VOLUME)
    stores = [disk_info(x['APFSPhysicalStore']) for x in info['APFSPhysicalStores']]
    physical = [disk_info(x['ParentWholeDisk']) for x in stores]
    assert info['VolumeUUID'] == UUID and info['MountPoint'] == str(VOLUME)
    assert info['Writable'] and not info['Locked'] and not info['Internal']
    assert info['FilesystemType'] == 'apfs' and not VOLUME.is_symlink()
    assert all(not p['Internal'] and p['VirtualOrPhysical'] == 'Physical' for p in physical)
    vfs = os.statvfs(VOLUME)
    free = vfs.f_bavail * vfs.f_frsize
    assert free >= MINIMUM
    return {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
            'volume': info, 'physical_stores': stores, 'physical_devices': physical,
            'statvfs_available_bytes': free, 'statvfs_total_bytes': vfs.f_blocks*vfs.f_frsize,
            'parent_device': VOLUME.stat().st_dev, 'parent_inode': VOLUME.stat().st_ino}


def snapshot(path):
    st = path.lstat()
    result = {'device': st.st_dev, 'inode': st.st_ino, 'mode': st.st_mode}
    if path.is_symlink():
        result['symlink'] = os.readlink(path)
    elif path.is_dir():
        result['children'] = {p.name: snapshot(p) for p in sorted(path.iterdir())}
    else:
        result['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        result['bytes'] = st.st_size
    return result


def load_executor(path):
    data = path.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXECUTOR_SHA
    spec = importlib.util.spec_from_file_location('accepted_materializer_probe', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    # Execute the exact verified byte buffer, without a second source read.
    exec(compile(data, str(path), 'exec'), module.__dict__)
    return module


def run(executor):
    assert sys.platform == 'darwin'
    module = load_executor(executor)
    before = observation()
    root = Path(tempfile.mkdtemp(prefix='.tnsm-rebind-probe-', dir=VOLUME))
    results = []
    for kind in ('absent', 'empty_directory', 'nonempty_directory', 'file', 'symlink',
                 'replaced_staging', 'injected_ENOTSUP'):
        case = root / kind
        case.mkdir()
        final, staging = case / 'candidate', case / '.candidate.staging'
        lease = module.create_staging_lease(final, staging)
        try:
            (staging / 'invented.txt').write_bytes(b'artificial probe; no dataset records\n')
            source_before = snapshot(staging)
            if kind == 'empty_directory':
                final.mkdir()
            elif kind == 'nonempty_directory':
                final.mkdir()
                (final / 'foreign.txt').write_bytes(b'preserve this artificial sentinel\n')
            elif kind == 'file':
                final.write_bytes(b'preserve this artificial file\n')
            elif kind == 'symlink':
                (case / 'neighbor.txt').write_bytes(b'artificial symlink target\n')
                final.symlink_to('neighbor.txt')
            elif kind == 'replaced_staging':
                staging.rename(case / 'displaced-owned')
                staging.mkdir()
                (staging / 'foreign.txt').write_bytes(b'preserve replacement\n')
            tree_before = snapshot(case)
            rejection = None
            try:
                if kind == 'injected_ENOTSUP':
                    class RejectCall:
                        def __call__(self, *args):
                            ctypes.set_errno(errno.ENOTSUP)
                            return -1
                    class FakeLibC:
                        renameatx_np = RejectCall()
                    with patch.object(module.ctypes, 'CDLL', return_value=FakeLibC()):
                        module.atomic_publish_noreplace(lease, final)
                else:
                    module.atomic_publish_noreplace(lease, final)
            except module.MaterializationError as exc:
                rejection = str(exc)
            if kind == 'absent':
                assert rejection is None and not os.path.lexists(staging)
                assert snapshot(final) == source_before
            else:
                assert rejection is not None
                assert snapshot(case) == tree_before, 'failure modified a probe object'
                if kind in ('empty_directory', 'nonempty_directory', 'file', 'symlink'):
                    assert 'final output appeared' in rejection
                if kind == 'replaced_staging':
                    assert 'foreign staging identity' in rejection
            results.append({'case': kind, 'pass': True, 'rejection': rejection,
                            'syscall_mode': 'injected failure' if kind == 'injected_ENOTSUP'
                            else 'identity guard before syscall' if kind == 'replaced_staging'
                            else 'native Darwin renameatx_np RENAME_EXCL',
                            'before': tree_before, 'after': snapshot(case)})
        finally:
            os.close(lease.parent_fd)
    after = observation()
    assert (before['parent_device'], before['parent_inode']) == (after['parent_device'], after['parent_inode'])
    files = [p for p in root.rglob('*') if p.is_file() and not p.is_symlink()]
    return {'status': 'PASS', 'platform': platform.platform(), 'executor_sha256': EXECUTOR_SHA,
            'probe_root': str(root), 'before': before, 'after': after, 'cases': results,
            'native_syscall_cases_passed': 5, 'guard_or_injected_cases_passed': 2,
            'retained_regular_files': len(files), 'retained_logical_bytes': sum(p.stat().st_size for p in files),
            'retention': 'All artificial probe objects retained; no recursive cleanup',
            'real_csv_access': False, 'formal_output_or_staging_created': False,
            'authorization_granted': False}


if __name__ == '__main__':
    # Evidence is emitted to stdout; the build script saves it inside its new package.
    print(json.dumps(run(Path(sys.argv[1]).resolve()), ensure_ascii=False, indent=2))
