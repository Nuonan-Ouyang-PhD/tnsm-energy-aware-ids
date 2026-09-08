**批准。最终申请已复核通过，现明确授权按 `MATERIALIZATION_FINAL_REQUEST_V1.zip` 执行 materialization 单项任务，包括真实输入预检、确定性转换、验证重放及不覆盖发布。**

**本条就是本次所需的明确执行批准，不再只是同意准备申请。执行前置检查全部通过后，可以直接继续转换、验证和发布，无需在预检后再次等待批准。** 划分、训练、编码器拟合和模型拟合仍不在授权范围内。

## 一、最终申请复核通过

本次批准绑定的最终申请为：
MATERIALIZATION_FINAL_REQUEST_V1.zip
SHA-256: b123293dfe331d59393688d07c799c1fdb42f0df2367ef919c2f949843bff655

文件大小与结构：321,196 B；11 条目＝8 文件（含 MANIFEST）＋3 目录。
权限、CRC、重复成员、越界路径、符号链接及垃圾文件：通过。
最终申请 MANIFEST：7/7 OK。内嵌重绑定包 MANIFEST：18/18 OK。
内嵌重绑定包及既有独立复验包：与此前实际保存的文件字节级完全一致。
三个源根、输出位置及执行绑定：与申请、元数据报告及已验收合同一致。
400 项记录的相对路径及文件大小：逐项与冻结 inventory 匹配，400/400。
审阅前后输入文件：成员、内容及权限均未改变。

记录中的字节数重新求和为 17,114,499,704 B。本轮重跑了包内的只读重绑定验证器，结果为 PASS；没有重新打开已经关闭的执行器审查。

需要区分：本次独立核对的是提交的目录元数据与冻结清单，不是远程检查了真实 CSV 内容。迁移摘录中的 MOVED_VERIFIED_ORIGINAL_PATH_LINKED 和后续 PASS 记录，与所选项目路径一致；真实文件当前的哈希、表头和行数，正是本次获准执行的预检内容。申请正文也明确保留了这一边界。

## 二、授权绑定的输入、输出和范围

三个源根逐字采用 final_request.json 中的 source_roots。共同项目根为：
/Volumes/RESEARCH_DATA/10_PROJECTS/COMPLETE_RESEARCH_BY_SOURCE_PATH/Downloads/tnsm-energy-aware-ids

--ton-root: datasets/incoming/ton_iot，1 CSV。
--cic-root: datasets/extracted/ciciot2023，309 CSV。
--nb-root: datasets/extracted/n_baiot，90 CSV。

使用上述外盘实际路径，不改用原 Downloads 符号链接入口。CIC 根保持为 CSV 的父目录；三个源根与 output／staging 不重叠。

output: /Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1
staging: /Volumes/RESEARCH_DATA/.TNSM-MATERIALIZATION-20260906-V1.staging

materialization = true
splitting = false
training = false
encoder_fitting = false
model_fitting = false

允许读取并核验全部 400 个真实 CSV，随后按已验收合同转换，预期生成 399 对特征／标签分片、54,050,346 行，保留 32／39／115 个原生特征。唯一数据行排除仍是三条精确登记的 CIC 截断尾行；零行结构文件必须先验证，再不生成分片。

不允许额外抽样、平衡、填补、编码、跨数据集拼接、修改冻结配置，或复制、移动、删除源数据。这些边界与申请正文一致。

## 三、按以下顺序执行，不再增加申请轮次

### 1. 先记录本次授权

授权 ID 使用：MATERIALIZATION-ONLY-20260906-B123293DFE33-AUTHORIZED

按既有执行器要求，在证据包外生成有效授权记录，并将本条批准原文、最终申请 SHA、全部既有执行绑定、三个源根及操作范围追加到实际 DECISIONS.md。

不要修改原申请包中的 authorized_by_user=false，也不要修改合同或冻结 config 来表示本次获准。它们是提交时的历史状态，本次授权由新增的包外记录表达。

--request-zip：原始 MATERIALIZATION_EXECUTION_REQUEST_V1.zip，SHA 55c3c6ee…71c63。
--executor-evidence-zip：已验收 MATERIALIZATION_REBIND_EVIDENCE_V1.zip，SHA 509074b8…223e。
本次最终申请绑定：MATERIALIZATION_FINAL_REQUEST_V1.zip，SHA b123293d…ff655，另行记入授权记录。

这与现有执行器的绑定要求一致，不需要修改执行器参数定义或重打包。

### 2. 刷新现场条件，然后完成真实输入预检

执行前刷新卷 UUID、物理后端、可写／解锁状态、剩余空间、源输出不重叠关系，以及 output／staging 均不存在。

申请记录于 2026 年 9 月 6 日墨尔本时间 20:17:30 的可用空间为 890,136,494,080 B，高于最低要求；但执行时仍以重新测得的值为准。
最低可用空间：26,745,491,380 B
输出硬上限：25,671,749,556 B
保留空间：1,073,741,824 B

随后预检全部 400 项真实输入的身份、哈希、表头、行数及精确异常。全部通过后才创建 staging；通过即继续执行，不再另设一次审批停点。

### 3. 转换、验证并发布

按既定合同保留原生特征及原始单元格文本，生成分片、标签旁表、来源账本和清单；完成零落盘哈希重放，以及字节、行数、标签计数和输出哈希核对。全部通过后，使用已验证的原生 RENAME_EXCL 路径发布。

任何绑定、输入、空间、验证或路径条件失败，都应停止、保留并报告现场；不得覆盖目标、扩大排除集合、自动删除 staging、自动重试或临时修改合同。

## 四、完成后提交结果，不继续启动划分或训练

成功后提交实际授权记录、执行版本及参数、现场刷新记录、400 项预检结果、分片与数据集清单、行数／标签／字节／哈希对账、重放和发布结果。不必为验收上传完整的大体积物化数据树。

本次独立复核和批准记录已整理为：下载最终物化申请复核及批准记录包。

结论：可以开始这一轮真实数据物化了。本次授权覆盖“预检 → 转换 → 验证 → 发布”的完整单项流程；物化完成后停止，划分和训练继续未授权。
