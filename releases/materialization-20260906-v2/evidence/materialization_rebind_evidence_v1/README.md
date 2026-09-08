# 新卷输出路径重绑定候选 V1

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
