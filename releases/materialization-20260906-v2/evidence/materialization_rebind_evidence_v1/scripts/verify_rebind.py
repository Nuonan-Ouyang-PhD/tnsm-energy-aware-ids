"""Read-only, package-only verification; does not inspect real source paths."""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
import stat
import sys
import zipfile
from pathlib import Path, PurePosixPath

BASE_SHA = '760163ee757620422d0eb013b8c7574015a01b40326021c21c891a097dfd29df'
REVIEW_SHA = '0366bcb46caac7a0afef9fc3a3fd2de42cc38b6e6644cf35adb4a96305823576'
BASE_ROOT = 'materialization_executor_evidence_v1r2'
ROOT_NAME = 'materialization_rebind_evidence_v1'
CP = 'contract/materialization_contract_v1r2.json'
EP = 'scripts/materialize_dataset_native_v1r2.py'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def verify(root, archive_path):
    base_bytes = (root / 'baseline/MATERIALIZATION_EXECUTOR_EVIDENCE_V1R2.zip').read_bytes()
    assert sha(base_bytes) == BASE_SHA
    assert sha((root / 'reviews/MATERIALIZATION_EXECUTOR_V1R2_INDEPENDENT_REVIEW.zip').read_bytes()) == REVIEW_SHA
    base = zipfile.ZipFile(io.BytesIO(base_bytes))
    original = json.loads(base.read(BASE_ROOT + '/' + CP))
    candidate = json.loads((root / CP).read_bytes())
    expected = copy.deepcopy(original)
    expected['contract_id'] = 'MATERIALIZATION-EXECUTOR-20260906-V1R2-REBIND1-PROPOSED'
    expected['runtime_evidence_binding']['archive_root'] = ROOT_NAME
    expected['output_binding'].update({
        'root': '/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1',
        'staging_root': '/Volumes/RESEARCH_DATA/.TNSM-MATERIALIZATION-20260906-V1.staging',
        'binding_status': 'actual_new_volume_probed; rebind_candidate_pending_independent_review_and_separate_user_authorization',
        'new_disk_note': 'RESEARCH_DATA APFS encrypted volume; UUID FBCBD1E6-330C-452B-AD79-EF7F74B6464B; native RENAME_EXCL probe passed. Refresh UUID, mount identity, available space and path absence before any separately authorized execution.'})
    expected['storage']['current_location_observation_passes'] = True
    assert candidate == expected, 'unapproved contract difference'
    unchanged = []
    for relative in original['runtime_evidence_binding']['required_local_files']:
        if relative != CP:
            assert (root / relative).read_bytes() == base.read(BASE_ROOT + '/' + relative), relative
            unchanged.append(relative)
    manifest_bytes = (root / 'MANIFEST_SHA256.txt').read_bytes()
    entries = {}
    for line in manifest_bytes.decode().splitlines():
        digest, name = line.split('  ', 1)
        assert name not in entries
        assert not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
        entries[name] = digest
        assert sha((root / name).read_bytes()) == digest, name
    assert set(entries) == {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file()} - {'MANIFEST_SHA256.txt'}
    blob = archive_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        infos = archive.infolist()
        assert len(infos) == len({i.filename for i in infos})
        assert archive.testzip() is None
        files = set()
        for info in infos:
            assert info.filename.startswith(ROOT_NAME + '/')
            assert '..' not in PurePosixPath(info.filename).parts
            assert not stat.S_ISLNK(info.external_attr >> 16)
            assert stat.S_IMODE(info.external_attr >> 16) == (0o755 if info.is_dir() else 0o644)
            if not info.is_dir():
                name = info.filename[len(ROOT_NAME)+1:]
                files.add(name)
                assert archive.read(info) == (root / name).read_bytes()
        assert files == set(entries) | {'MANIFEST_SHA256.txt'}
    probe = json.loads((root / 'reports/native_volume_probe.json').read_bytes())
    assert probe['status'] == 'PASS' and probe['native_syscall_cases_passed'] == 5
    assert probe['guard_or_injected_cases_passed'] == 2 and len(probe['cases']) == 7
    expected_cases = ['absent', 'empty_directory', 'nonempty_directory', 'file', 'symlink', 'replaced_staging', 'injected_ENOTSUP']
    assert [c['case'] for c in probe['cases']] == expected_cases
    assert all(c['pass'] for c in probe['cases'])
    assert all(c['before'] == c['after'] and c['rejection'] for c in probe['cases'][1:])
    assert probe['cases'][0]['rejection'] is None
    assert probe['cases'][0]['before']['children']['.candidate.staging'] == probe['cases'][0]['after']['children']['candidate']
    after = probe['after']
    assert after['volume']['VolumeUUID'] == 'FBCBD1E6-330C-452B-AD79-EF7F74B6464B'
    assert after['volume']['FilesystemType'] == 'apfs' and after['volume']['Writable']
    assert after['statvfs_available_bytes'] >= candidate['storage']['minimum_free_bytes']
    request = json.loads((root / 'rebind_request.json').read_bytes())
    assert request['contract_sha256'] == sha((root / CP).read_bytes())
    assert request['executor_sha256'] == sha((root / EP).read_bytes())
    assert request['probe_report_sha256'] == sha((root / 'reports/native_volume_probe.json').read_bytes())
    assert request['available_bytes_observed'] == after['statvfs_available_bytes']
    assert request['output_root'] == candidate['output_binding']['root']
    assert request['staging_root'] == candidate['output_binding']['staging_root']
    assert request['authorization_granted'] is False
    assert not any(request['authorized_operations_now'].values())
    assert candidate['authorization']['granted'] is False
    spec = importlib.util.spec_from_file_location('rebind_verification_executor', root / EP)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    exec(compile((root / EP).read_bytes(), str(root / EP), 'exec'), module.__dict__)
    module.validate_contract_shape(candidate)
    module.validate_bound_metadata(candidate, root)
    # Only the archive binding helper is called: no authorization grant, no
    # source-root inspection, no materializer execution and no output creation.
    binding_values = {'evidence_archive_root': ROOT_NAME,
                      'evidence_manifest_sha256': sha(manifest_bytes),
                      'contract_sha256': request['contract_sha256'],
                      'executor_sha256': request['executor_sha256']}
    runtime = module.validate_runtime_archive(candidate, root / CP, blob, sha(blob), binding_values)
    module.validate_runtime_files_unchanged(runtime)
    assert len(runtime.local_file_hashes) == 10
    return {'status': 'PASS', 'manifest_files': len(entries),
            'archive_entries': len(infos), 'unchanged_runtime_files': len(unchanged),
            'runtime_bound_files': 10, 'exact_allowed_contract_changes': 7,
            'recorded_native_cases': 5, 'recorded_guard_or_injected_cases': 2,
            'archive_sha256': sha(blob), 'archive_bytes': len(blob),
            'manifest_sha256': sha(manifest_bytes), 'contract_sha256': request['contract_sha256'],
            'authorization_granted': False, 'real_csv_access': False,
            'scope': 'package-only verification of recorded evidence; no new volume probe or live volume check'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--zip', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.root.resolve(), args.zip.resolve()), indent=2))
