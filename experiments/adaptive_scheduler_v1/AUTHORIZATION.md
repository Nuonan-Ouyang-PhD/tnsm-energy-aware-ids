# Execution authorization record

Campaign: `TNSM-ADAPTIVE-SCHEDULER-20260907-V1`

Recorded on 2026-09-07 Australia/Melbourne time from the current Codex task.

The user instructed:

> 按附件推进自适应调度主线，不重做已经验收的分类、物化和十五段静态功耗实验。并行完成已有汇总修正、资源成本登记和调度器实现；用训练／验证数据及适用的实测成本训练策略，固定后再评估测试轨迹。先交付一次完整端到端小试，方案、小试和有效授权齐备后执行 40 轮配对物理实验。不要改变已看过的测试划分或阈值，不要把 TON 功耗冒充三个数据集的实测成本，不要只交审批文档而没有运行成果。

This is the effective authorization for the bounded sequence in `PLAN.md`:
implementation, policy fitting on allowed data, software evaluation after policy
freeze, one excluded pilot, and—only after all gates pass—the forty preplanned
TON-IoT paired physical runs. It does not authorize changing accepted classifier
splits/thresholds/artifacts, inventing measurements, destructive source-data
operations, or expanding the physical claim to other datasets or devices.

Earlier user instructions in this task also explicitly allowed all experiments
without repeated approval and accepted the observed power-supply condition. The
current instruction supplies the narrower stage-specific ordering and controls.
