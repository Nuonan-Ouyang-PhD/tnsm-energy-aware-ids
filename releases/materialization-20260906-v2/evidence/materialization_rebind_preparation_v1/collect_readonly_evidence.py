"""Collect archive and mounted-volume metadata; never open dataset CSVs.

The only write is a new JSON evidence file in this preparation directory.
This does not perform a capability probe, rebind, or authorize execution.
"""
import datetime
import hashlib
import json
import plistlib
import stat
import subprocess
import zipfile
from pathlib import Path, PurePosixPath


HERE = Path(__file__).resolve().parent
WORKSPACE = HERE.parent
REVIEW = Path('/Users/nuonanouyang/Downloads/MATERIALIZATION_EXECUTOR_V1R2_INDEPENDENT_REVIEW.zip')
BASELINE = WORKSPACE / 'MATERIALIZATION_EXECUTOR_EVIDENCE_V1R2.zip'
EXPECTED_BASELINE = '760163ee757620422d0eb013b8c7574015a01b40326021c21c891a097dfd29df'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def command(args):
    result = subprocess.run(args, capture_output=True, timeout=30, check=True)
    return result.stdout


def archive_identity(path, manifest_name):
    data = path.read_bytes()
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        assert len(names) == len(set(names)), 'duplicate ZIP member'
        for info in archive.infolist():
            name = PurePosixPath(info.filename)
            assert not name.is_absolute() and '..' not in name.parts
            assert not stat.S_ISLNK(info.external_attr >> 16)
        assert archive.testzip() is None, 'CRC failure'
        manifest = archive.read(manifest_name)
        root = manifest_name.rsplit('/', 1)[0] + '/'
        checked = []
        for line in manifest.decode().splitlines():
            digest, name = line.split(None, 1)
            name = name.lstrip('*')
            member = name if name in names else root + name
            assert sha(archive.read(member)) == digest, member
            checked.append(member)
        files = {i.filename for i in archive.infolist() if not i.is_dir()}
        assert len(checked) == len(set(checked))
        assert set(checked) == files - {manifest_name}
    return {'path': str(path), 'sha256': sha(data), 'bytes': len(data),
            'entries': len(names), 'manifest_sha256': sha(manifest),
            'manifest_verified_files': len(checked),
            'crc_paths_duplicates_symlinks_and_manifest': 'PASS'}


def main():
    report = {
        'observed_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status': 'preparation_only_actual_volume_and_probe_pending',
        'authorization': {'materialization': False, 'splitting': False, 'training': False},
        'output_root': None, 'staging_root': None, 'native_new_volume_probe': 'NOT_RUN',
        'minimum_free_bytes_required': 26745491380,
        'output_hard_limit_bytes': 25671749556,
        'real_csv_access': False, 'formal_output_or_staging_created': False,
        'review': archive_identity(REVIEW, 'materialization_executor_v1r2_review/REVIEW_MANIFEST_SHA256.txt'),
        'baseline': archive_identity(BASELINE, 'materialization_executor_evidence_v1r2/MANIFEST_SHA256.txt'),
    }
    assert report['baseline']['sha256'] == EXPECTED_BASELINE
    report['git_head_observed_only'] = command(['git', '-C', str(WORKSPACE), 'rev-parse', 'HEAD']).decode().strip()
    report['git_worktree_status'] = 'not established; broad status checks did not finish and were terminated'
    # -plist must precede the diskutil list filters on this macOS version.
    report['external_physical_listing'] = plistlib.loads(command(['diskutil', 'list', '-plist', 'external', 'physical']))
    report['mounted_volumes'] = []
    keys = ['DeviceIdentifier', 'MountPoint', 'VolumeName', 'VolumeUUID', 'DiskUUID',
            'TotalSize', 'VolumeSize', 'VolumeFreeSpace', 'FilesystemType',
            'BusProtocol', 'VirtualOrPhysical', 'Internal', 'Writable', 'ReadOnlyVolume']
    for volume in sorted(Path('/Volumes').iterdir()):
        info = plistlib.loads(command(['diskutil', 'info', '-plist', str(volume)]))
        report['mounted_volumes'].append({'listed_path': str(volume),
                                          **{key: info.get(key) for key in keys}})
    report['new_volume_binding'] = 'UNSET; no volume is automatically selected by this collector'
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    destination = HERE / ('readonly_observation_' + stamp + '.json')
    with destination.open('x') as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write('\n')
    print(destination)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
