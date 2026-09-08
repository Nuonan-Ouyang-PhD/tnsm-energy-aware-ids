"""Source location evidence: directory enumeration and lstat only for real data."""
import hashlib
import json
import os
import plistlib
import stat
import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

WORK = Path(__file__).resolve().parent.parent
PACKAGE = WORK / 'materialization_rebind_evidence_v1'
OUT = WORK / 'materialization_final_request_v1'
PROJECT = Path('/Volumes/RESEARCH_DATA/10_PROJECTS/COMPLETE_RESEARCH_BY_SOURCE_PATH/Downloads/tnsm-energy-aware-ids')
LOGS = Path('/Volumes/RESEARCH_DATA/00_ADMIN/MIGRATIONS')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def save(name, value):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    data = value if isinstance(value, bytes) else (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()
    with path.open('xb') as handle:
        handle.write(data)
    path.chmod(0o644)


def main():
    roots = {k: PROJECT / suffix for k, suffix in {
        'ton_iot': 'datasets/incoming/ton_iot',
        'ciciot2023': 'datasets/extracted/ciciot2023',
        'n_baiot': 'datasets/extracted/n_baiot'}.items()}
    contract = json.loads((PACKAGE / 'contract/materialization_contract_v1r2.json').read_bytes())
    request = json.loads((WORK / 'materialization_authorization_draft_v1/request_draft.json').read_bytes())
    report = {'observed_at_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'real CSV directory entries and lstat only; no CSV open/hash/header/row read', 'datasets': {}}
    for key, root in roots.items():
        inventory = json.loads((PACKAGE / contract['input_binding']['inventories'][key]['file']).read_bytes())
        expected = {x['relative_path']: x for x in inventory['files']}
        observed = {}
        links = []
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                path = Path(directory) / name
                st = path.lstat()
                if stat.S_ISLNK(st.st_mode):
                    links.append(str(path))
                if name.lower().endswith('.csv'):
                    assert stat.S_ISREG(st.st_mode), str(path)
                    observed[path.relative_to(root).as_posix()] = {
                        'bytes': st.st_size, 'device': st.st_dev, 'inode': st.st_ino,
                        'mtime_ns': st.st_mtime_ns, 'mode': stat.S_IMODE(st.st_mode)}
        missing = sorted(set(expected) - set(observed))
        extra = sorted(set(observed) - set(expected))
        mismatches = [name for name in expected if name in observed and expected[name]['bytes'] != observed[name]['bytes']]
        assert not missing and not extra and not mismatches and not links, (key, missing, extra, mismatches, links)
        output = Path(request['output_root']); staging = Path(request['staging_root'])
        resolved = root.resolve(strict=True)
        assert root == resolved
        for target in (output, staging):
            assert target != resolved and target not in resolved.parents and resolved not in target.parents
        report['datasets'][key] = {'source_root': str(root), 'resolved_path': str(resolved),
            'selected_copy': 'complete external project tree; original Downloads path is a symlink entrance',
            'inventory_sha256': sha((PACKAGE / contract['input_binding']['inventories'][key]['file']).read_bytes()),
            'csv_count': len(observed), 'source_bytes': sum(v['bytes'] for v in observed.values()),
            'relative_path_set_matches': True, 'all_stat_sizes_match': True,
            'symlink_entries': links, 'source_output_nonoverlap': True, 'files': observed,
            'current_content_hash_and_row_checks': 'not performed; reserved for separately authorized execution preflight'}
    report['total_csv_count'] = sum(x['csv_count'] for x in report['datasets'].values())
    report['total_bytes'] = sum(x['source_bytes'] for x in report['datasets'].values())
    assert report['total_csv_count'] == 400 and report['total_bytes'] == 17114499704
    migration = {}
    for name, listkey in [('WHOLE_RESEARCH_COMPLETED_VERIFICATION.json', 'directories'),
                          ('WHOLE_PROJECTS_PLAN/result.json', 'items')]:
        path = LOGS / name
        data = path.read_bytes(); document = json.loads(data)
        matches = [x for x in document[listkey] if x.get('destination') == str(PROJECT)]
        assert len(matches) == 1
        migration[name] = {'existing_log_path': str(path), 'existing_log_sha256': sha(data),
                           'selected_project_record': matches[0],
                           'evidence_scope': 'pre-existing migration log claims, not current CSV hash verification'}
    report['migration_status'] = 'existing logs report MOVED_VERIFIED_ORIGINAL_PATH_LINKED and final PASS; current 400 paths and stat sizes independently match'
    entrance = Path('/Users/nuonanouyang/Downloads/tnsm-energy-aware-ids')
    assert entrance.is_symlink() and entrance.resolve() == PROJECT
    report['original_project_entrance'] = {'path': str(entrance), 'symlink_target': os.readlink(entrance)}
    volume = Path('/Volumes/RESEARCH_DATA')
    info = plistlib.loads(subprocess.check_output(['diskutil', 'info', '-plist', str(volume)], timeout=30))
    assert info['VolumeUUID'] == request['volume_uuid'] and info['Writable'] and not info['Locked']
    vfs = os.statvfs(volume)
    free = vfs.f_bavail * vfs.f_frsize
    assert free >= request['minimum_free_bytes']
    assert not os.path.lexists(request['output_root']) and not os.path.lexists(request['staging_root'])
    report['volume_refresh'] = {'volume_uuid': info['VolumeUUID'], 'mount_point': info['MountPoint'],
        'filesystem': info['FilesystemType'], 'writable': info['Writable'], 'locked': info['Locked'],
        'available_bytes': free, 'formal_paths_absent': True,
        'source_root_devices': {k: p.stat().st_dev for k,p in roots.items()}, 'output_parent_device': volume.stat().st_dev}
    review_path = Path('/Users/nuonanouyang/Downloads/MATERIALIZATION_REBIND_V1_INDEPENDENT_REVIEW.zip')
    review = review_path.read_bytes()
    assert sha(review) == '9fbf01f7c383bc4f9496e86a4c5411a3a00f3937a2d66d267e84474385b21dac'
    baseline = (WORK / 'MATERIALIZATION_REBIND_EVIDENCE_V1.zip').read_bytes()
    assert sha(baseline) == request['executor_evidence_zip_sha256']
    request.update({'kind': 'materialization_only_final_execution_request',
        'status': 'source_metadata_complete_pending_explicit_user_authorization',
        'source_roots': {k: str(v) for k,v in roots.items()},
        'source_migration_status': report['migration_status'],
        'rebind_independent_review': {'file': review_path.name, 'sha256': sha(review), 'decision': 'PASS; output rebind and native probe prerequisite accepted'},
        'source_metadata_report_sha256': sha((json.dumps(report, ensure_ascii=False, indent=2)+'\n').encode()),
        'current_source_content_verification': 'not performed; all 400 hashes/headers/row counts remain execution preflight',
        'volume_observation': report['volume_refresh']})
    OUT.mkdir()
    save('source_metadata_report.json', report)
    save('migration_log_excerpts.json', migration)
    save('final_request.json', request)
    save('evidence/MATERIALIZATION_REBIND_V1_INDEPENDENT_REVIEW.zip', review)
    save('evidence/MATERIALIZATION_REBIND_EVIDENCE_V1.zip', baseline)
    save('scripts/prepare_final_source_request.py', Path(__file__).read_bytes())
    print(json.dumps({'output': str(OUT), 'datasets': {k:{n:v[n] for n in ('source_root','csv_count','source_bytes')} for k,v in report['datasets'].items()}, 'free_bytes': free, 'migration_status': report['migration_status']},indent=2))


if __name__ == '__main__':
    main()
