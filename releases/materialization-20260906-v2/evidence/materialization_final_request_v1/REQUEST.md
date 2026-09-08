# 最终 materialization 单项执行申请

状态：源路径及迁移说明已补齐；等待明确用户单项授权。此申请不是有效授权记录。

本次重绑定独立复验已 PASS，新卷原生能力证据前置项已关闭，不再列为待办。实际复验 ZIP SHA-256 为 `9fbf01f7c383bc4f9496e86a4c5411a3a00f3937a2d66d267e84474385b21dac`。已验收重绑定包原样附于 evidence/，未修改其合同、执行器或冻结配置。

## 输入位置及所选副本

统一项目根为：
`/Volumes/RESEARCH_DATA/10_PROJECTS/COMPLETE_RESEARCH_BY_SOURCE_PATH/Downloads/tnsm-energy-aware-ids`

| 参数 | 项目根下的源目录 | CSV 数 | 冻结/实测 stat 字节数 |
| --- | --- | ---: | ---: |
| --ton-root | datasets/incoming/ton_iot | 1 | 29,902,775 |
| --cic-root | datasets/extracted/ciciot2023 | 309 | 8,943,771,319 |
| --nb-root | datasets/extracted/n_baiot | 90 | 8,140,825,610 |

三个完整绝对路径及解析后路径见 final_request.json 和 source_metadata_report.json。选择外盘 COMPLETE_RESEARCH_BY_SOURCE_PATH 下的完整项目副本；原 `/Users/nuonanouyang/Downloads/tnsm-energy-aware-ids` 是指向该项目的符号链接。CIC 根为 CSV 的父目录，未重复拼接 CSV。源根与 output/staging 均不重叠。

本轮目录枚举及 lstat 对账：400 个 CSV，相对路径集合完全一致、全部大小一致，总计 17,114,499,704 B；未发现枚举范围内的符号链接条目。预期输出仍为 399 对分片、54,050,346 行及 32/39/115 原生特征；预期行数来自冻结清单，未在本轮读取真实 CSV 计算。

既有迁移日志记录本项目 MOVED_VERIFIED_ORIGINAL_PATH_LINKED，后续整项目验证记录 PASS。migration_log_excerpts.json 保存选定项目记录和原日志路径/哈希；这不等于本轮重新确认 CSV 内容哈希。当前文件内容、表头和行数一致性由正式授权后的全量预检验证。本轮未复制、移动或删除源文件。

## 输出、预算与行为

卷 UUID：`FBCBD1E6-330C-452B-AD79-EF7F74B6464B`，APFS 已解锁可写。

output：`/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1`。

staging：`/Volumes/RESEARCH_DATA/.TNSM-MATERIALIZATION-20260906-V1.staging`。

本轮观测两者不存在且同父目录，源所在设备与该父目录设备一致；可用空间为 890,136,494,080 B。具体观测时点见 source_metadata_report.json。执行前再刷新卷 UUID、物理后端、可写状态、空间、路径缺席及源输出不重叠关系。

输出硬上限 25,671,749,556 B，保留空间 1,073,741,824 B，最低可用 26,745,491,380 B。预算未因新盘扩大。先验证全部 400 个清单项，零行结构文件验证后不渲染；仅按冻结记录排除三条精确匹配的 CIC 无 LF 截断尾行。

遵循已验收合同：保留原生特征及原始单元格文本，确定性序列化，按冻结路径顺序逐文件处理，输出特征/标签旁表、分片来源映射及清单；流式仅计算哈希重放，核对哈希、字节、行数及标签数量。通过全部验证后使用原生 RENAME_EXCL 发布，任何已存在目标不得覆盖。

失败则停止发布，保留并报告 owned/foreign staging，无自动递归删除或自动重试。既有人工探测目录继续保留，不重复探测。输入与冻结配置不改写。

## 明确申请的授权

仅申请 materialization，包括上述真实 400 CSV 的执行前身份/哈希/表头/行数预检、转换、验证重放和不覆盖发布。splitting、training、encoder_fitting、model_fitting 均不申请；不抽样、平衡、填补、编码或跨数据集拼接。

执行绑定：

- 重绑定 ZIP：`509074b8e52786118a5b338f8e9f1b86606b999508bd9273465280d01e76223e`
- MANIFEST：`db7f28d61e52cd656c7dea2d73a55fd0c35413243c103b2ac44f721b987f33a1`
- 合同：`992790a6953e445cce444b4532d9d45995f5bea4fb9788b3c4b9e910691a0332`
- 执行器：`ac9992005047bda7431abccafe8698d5b3b890efbf218605841730a5613b1c2c`
- 原请求 ZIP：`55c3c6ee9d6e01fb764a650432b379ca41ca52b703dd33c9ec9cf17088271c63`
- 合同 ID：`MATERIALIZATION-EXECUTOR-20260906-V1R2-REBIND1-PROPOSED`
- 归档根：`materialization_rebind_evidence_v1`

用户明确批准此最终申请后，才生成有效授权 ID/记录，将用户原文、以上全部绑定、三个源根和操作范围追加至实际 DECISIONS.md，并执行预检。本包的 authorized_by_user=false；本次上传复验结论没有授予正式运行权限。

本包脚本 prepare_final_source_request.py 是现场采集过程记录，依赖原工作区及既有迁移日志，不是可移植执行入口。只读复核本包应检查 MANIFEST、JSON、内嵌已验收包和元数据对账；无需运行该采集脚本或访问真实源文件。
