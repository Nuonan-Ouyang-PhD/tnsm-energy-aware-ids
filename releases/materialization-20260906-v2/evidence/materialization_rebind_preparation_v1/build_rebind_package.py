"""Build a review candidate, run authorized artificial probes, never materialize."""
import copy
import hashlib
import io
import json
import os
import stat
import zipfile
from pathlib import Path, PurePosixPath

from probe_new_volume import run, VOLUME, UUID

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
NAME = 'materialization_rebind_evidence_v1'
ROOT = WORK / NAME
BASE_NAME = 'materialization_executor_evidence_v1r2'
BASE_SHA = '760163ee757620422d0eb013b8c7574015a01b40326021c21c891a097dfd29df'
REVIEW_SHA = '0366bcb46caac7a0afef9fc3a3fd2de42cc38b6e6644cf35adb4a96305823576'
CONTRACT = 'contract/materialization_contract_v1r2.json'
EXECUTOR = 'scripts/materialize_dataset_native_v1r2.py'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(relative, data):
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as handle:
        handle.write(data)
    path.chmod(0o644)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def main():
    base = (WORK / 'MATERIALIZATION_EXECUTOR_EVIDENCE_V1R2.zip').read_bytes()
    assert sha(base) == BASE_SHA
    review = Path('/Users/nuonanouyang/Downloads/MATERIALIZATION_EXECUTOR_V1R2_INDEPENDENT_REVIEW.zip').read_bytes()
    assert sha(review) == REVIEW_SHA
    archive = zipfile.ZipFile(io.BytesIO(base))
    assert archive.testzip() is None
    assert len(archive.namelist()) == len(set(archive.namelist()))
    for member in archive.infolist():
        assert not PurePosixPath(member.filename).is_absolute()
        assert '..' not in PurePosixPath(member.filename).parts
        assert not stat.S_ISLNK(member.external_attr >> 16)
    original = json.loads(archive.read(BASE_NAME + '/' + CONTRACT))
    manifest = archive.read(BASE_NAME + '/MANIFEST_SHA256.txt').decode()
    checked = set()
    for line in manifest.splitlines():
        digest, relative = line.split('  ', 1)
        assert sha(archive.read(BASE_NAME + '/' + relative)) == digest
        checked.add(relative)
    assert checked == {i.filename[len(BASE_NAME)+1:] for i in archive.infolist()
                       if not i.is_dir()} - {'MANIFEST_SHA256.txt'}
    # All candidate files are new; never overwrite a previous evidence package.
    ROOT.mkdir(mode=0o755)
    for relative in original['runtime_evidence_binding']['required_local_files']:
        if relative != CONTRACT:
            write(relative, archive.read(BASE_NAME + '/' + relative))
    write('baseline/MATERIALIZATION_EXECUTOR_EVIDENCE_V1R2.zip', base)
    write('reviews/MATERIALIZATION_EXECUTOR_V1R2_INDEPENDENT_REVIEW.zip', review)
    write('scripts/probe_new_volume.py', (HERE / 'probe_new_volume.py').read_bytes())
    print('Baseline ZIP and 46 manifest entries verified; starting native artificial probe.', flush=True)
    probe = run(ROOT / EXECUTOR)
    write('reports/native_volume_probe.json', json_bytes(probe))
    final = VOLUME / 'TNSM-MATERIALIZATION-20260906-V1'
    staging = VOLUME / ('.' + final.name + '.staging')
    assert not os.path.lexists(final) and not os.path.lexists(staging)
    candidate = copy.deepcopy(original)
    candidate['contract_id'] = 'MATERIALIZATION-EXECUTOR-20260906-V1R2-REBIND1-PROPOSED'
    candidate['runtime_evidence_binding']['archive_root'] = NAME
    output = candidate['output_binding']
    output['root'], output['staging_root'] = str(final), str(staging)
    output['binding_status'] = 'actual_new_volume_probed; rebind_candidate_pending_independent_review_and_separate_user_authorization'
    output['new_disk_note'] = 'RESEARCH_DATA APFS encrypted volume; UUID ' + UUID + '; native RENAME_EXCL probe passed. Refresh UUID, mount identity, available space and path absence before any separately authorized execution.'
    candidate['storage']['current_location_observation_passes'] = True
    write(CONTRACT, json_bytes(candidate))
    changes = []
    def compare(left, right, path=''):
        if isinstance(left, dict) and isinstance(right, dict):
            for key in sorted(set(left) | set(right)):
                compare(left.get(key), right.get(key), path + '/' + key)
        elif left != right:
            changes.append({'path': path, 'before': left, 'after': right})
    compare(original, candidate)
    write('reports/contract_semantic_diff.json', json_bytes(changes))
    observed = probe['after']
    request = {
        'kind': 'output_volume_rebind_candidate', 'status': 'pending_independent_review_and_user_authorization',
        'baseline_zip_sha256': BASE_SHA, 'accepted_review_zip_sha256': REVIEW_SHA,
        'contract_id': candidate['contract_id'], 'contract_sha256': sha(json_bytes(candidate)),
        'executor_sha256': sha((ROOT / EXECUTOR).read_bytes()),
        'evidence_archive_root': NAME, 'request_zip_sha256': original['baseline_request']['request_zip_sha256'],
        'volume_uuid': UUID, 'mount_point': str(VOLUME),
        'observed_at_utc': observed['observed_at_utc'],
        'volume_device': observed['volume']['DeviceIdentifier'],
        'physical_devices': [x['DeviceIdentifier'] for x in observed['physical_devices']],
        'filesystem': observed['volume']['FilesystemType'], 'encryption': observed['volume']['Encryption'],
        'writable': observed['volume']['Writable'],
        'available_bytes_observed': observed['statvfs_available_bytes'],
        'volume_capacity_bytes': observed['volume']['APFSContainerSize'],
        'minimum_free_bytes': 26745491380, 'output_hard_cap_bytes': 25671749556,
        'output_root': str(final), 'staging_root': str(staging),
        'same_parent': True, 'parent_device': observed['parent_device'], 'parent_inode': observed['parent_inode'],
        'output_and_staging_absent_at_preparation': True,
        'same_filesystem_scope': 'both planned siblings resolve to the same existing parent; neither directory created',
        'probe_report_sha256': sha(json_bytes(probe)),
        'authorization_granted': False,
        'authorized_operations_now': {'materialization': False, 'splitting': False, 'training': False},
        'future_requested_operation_only': 'materialization',
        'source_binding_status': 'frozen metadata unchanged; real source paths/CSVs not inspected; any source relocation requires an additional explicit reviewed source binding',
        'before_execution': ['independent rebind review accepted',
            'verify mounted volume UUID and physical backing again; volatile disk numbers are observations, not persistent identity',
            'repeat current free-space and output/staging absence checks',
            'confirm exact separately authorized source roots without inferring them from this output-only rebind',
            'explicit user materialization authorization bound to this final ZIP, manifest, contract, executor, request and output path and appended in DECISIONS.md'],
    }
    write('rebind_request.json', json_bytes(request))
    write('scripts/verify_rebind.py', (HERE / 'verify_rebind.py').read_bytes())
    readme = '''# 新卷输出路径重绑定候选 V1

状态：新卷原生人工探测通过；等待独立复验与单项物化授权。

基线为已获接受的 V1R2。执行源码及八个运行元数据文件逐字节保留，两个冻结 config、32/39/115 特征、标签、三条例外均不变。合同仅七项部署字段改变：contract_id、归档根、output/staging 路径、绑定状态、新盘说明及当前空间通过标记。逐项差异见 reports/contract_semantic_diff.json。

候选 output：`/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1`。
候选 staging：`/Volumes/RESEARCH_DATA/.TNSM-MATERIALIZATION-20260906-V1.staging`。
两者共用已存在的卷根作为父目录，均未创建。持久卷标识及实时空间观测见 rebind_request.json；设备编号可能因重挂载改变。

reports/native_volume_probe.json 记录原生 Darwin 成功发布及四类晚到目标拒绝，共五项原生调用；另有替代 staging 的身份保护和注入 ENOTSUP 的无回退检查。ENOTSUP 项明确为人工故障注入，不是声称该 APFS 卷不支持。全部使用少量人工文件，保留在报告指定的独立 .tnsm-rebind-probe-* 目录；无自动清理，无真实 CSV 读取或正式目录创建。

最低可用空间 26,745,491,380 B，输出硬上限 25,671,749,556 B。当前可用空间是时点观测，运行前必须重查；空间满足不构成运行授权。卷上现有资料目录不属于此次探测。源绑定沿用冻结元数据；本包仅重绑定输出，不证明原始源路径仍可用，也不把新卷上的资料自动作为输入。

验证：`python3 -B scripts/verify_rebind.py --root . --zip ../MATERIALIZATION_REBIND_EVIDENCE_V1.zip`。该验证器只检查包内证据/元数据，不运行物化或新卷探测。再次运行 scripts/probe_new_volume.py 会在指定新卷创建新人工探测目录，不属于只读验证。无需重复创建探测目录来校验本包。

baseline/ 保留已验收 V1R2 原 ZIP；reviews/ 保存实际独立复验 ZIP。原基线中的 37/37、187/187 属于既有验证记录，本轮不冒称再次执行全部旧测试。原 V1R2 验证器针对旧路径的断言不适用于本候选；本包验证器严格约束七项差异并验证十文件运行归档绑定。

正式授权应在独立复验通过后追加至 DECISIONS.md，绑定最终候选 ZIP、其 MANIFEST、合同、执行器、原请求 ZIP、输出路径和 operation map。此包不包含 authorized_by_user=true 的授权记录；materialization、splitting、training 均未获执行授权。
'''
    write('README.md', readme.encode())
    paths = sorted(p for p in ROOT.rglob('*') if p.is_file())
    text = ''.join(sha(p.read_bytes()) + '  ' + p.relative_to(ROOT).as_posix() + '\n' for p in paths)
    write('MANIFEST_SHA256.txt', text.encode())
    destination = WORK / 'MATERIALIZATION_REBIND_EVIDENCE_V1.zip'
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as out:
        for path in sorted([ROOT] + list(ROOT.rglob('*'))):
            name = path.relative_to(WORK).as_posix() + ('/' if path.is_dir() else '')
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = ((stat.S_IFDIR | 0o755) if path.is_dir() else (stat.S_IFREG | 0o644)) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, b'' if path.is_dir() else path.read_bytes())
    print(json.dumps({'package': str(destination), 'sha256': sha(destination.read_bytes()),
                      'bytes': destination.stat().st_size, 'manifest_sha256': sha(text.encode()),
                      'request': request, 'probe_root': probe['probe_root']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
