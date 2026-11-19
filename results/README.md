# 已有结果导航

优先读以下材料，不重新运行已保存的模型请求。原始输入、回答、评分及账本按原相对路径保留。

- [历史角色推荐](../output/integration/capstone_retrieval_improvement_20261106/summary.json)：用于检索支撑，Hit@5为66.05%；与LLM业务回答评价分开。
- [业务首轮比较](../Capstone报告/验证体系/实验/2026-11-13_总实验收尾/CP01首轮业务结果_001.md)：相同题面下原生成与当前生成实现的成对业务评价，保存初始回答。
- [定向修正结果](../Capstone报告/验证体系/实验/2026-11-13_总实验收尾/CP01修复后业务结果_001.md)：95对修正前后回答单列，不替代首轮成绩。
- [宏观首个固定来源块](../Capstone报告/验证体系/实验/2026-11-13_总实验收尾/宏观首块业务结果_001.md)：四种机制在当前来源块的轨迹相同；保留该结果与解释边界。
- [可读与已评数量](../Capstone报告/验证体系/实验/2026-11-13_总实验收尾/business_readiness_CP08_review_progress_005.json)：区分已返回、可读与已复核，避免把请求提交当作实验完成。
- [停止状态记录](../Capstone报告/验证体系/实验/2026-11-13_总实验收尾/serial_pipeline_003/state.json)：历史流水线已停止，本记录不构成重新启动指令。
- [确定性反馈对照](../output/integration/capstone_validation_20261105/feedback/summary.json)：6个窗口、18次条件运行；说明规则应变，不表述为模型学会盈利。
- [生成校验增强（门禁／评分表／锚点／去标识／覆盖／专家切片）](experiments/generation_validation_enhancement_20261117/index.json)：前向评阅流程与离线演示产物；0次新模型调用；不改写既有冻结评分。
- [2026-11-17线程摘要](experiments/generation_validation_enhancement_20261117/THREAD_SUMMARY.md)；[裁决批次](experiments/generation_validation_enhancement_20261117/adjudication_progress_20261117.json)／[wave2](experiments/generation_validation_enhancement_20261117/adjudication_progress_20261117_wave2.json)／[wave3](experiments/generation_validation_enhancement_20261117/adjudication_progress_20261117_wave3.json)／[wave4](experiments/generation_validation_enhancement_20261117/adjudication_progress_20261117_wave4.json)／[wave5](experiments/generation_validation_enhancement_20261117/adjudication_progress_20261117_wave5.json)：累计新增1036份有引文业务评阅；可读且门禁通过的待评积压已清零；评阅身份为独立第二LLM提供方（[身份更正记录](experiments/generation_validation_enhancement_20261117/reviewer_identity_correction_20261118.json)）；[专家切片](experiments/generation_validation_enhancement_20261117/expert_slice_reviews/summary.json)同身份填槽，非人类外部专家。
- [组织审议对照指标（D3 vs S/S4）](experiments/org_deliberation_metrics_20261119/index.json)：冻结CP07与宏观首块的离线指标电池（配对质量、缺资料敏感性、过程代理、12窗LLM评阅）；0次新模型调用；不改写既有业务评分。见[SUMMARY](experiments/org_deliberation_metrics_20261119/SUMMARY.md)。
- [组织消融／输入敏感性（待授权运行）](experiments/org_ablation_sensitivity_20261119/index.json)：在冻结CP07终稿提示上做dropout／顺序／门禁bit-flip；`prepare`/`dry-run`离线，`run`需显式双门禁。PIC说明见[README](experiments/org_ablation_sensitivity_20261119/README.md)。

## 当前完成度

先期两批可读首轮188+190均已逐项评分复核；当前模型其中162/189行动适当，85.7%不是全量成功率。CP08业务评阅现约926份，可读且门禁通过待评约0；组织CP07已评286、可读且门禁通过待评约0。定向修正95对单列。

宏观保留已启动链的实际输入与运行目录，未执行链仅保留配置和生成工具。首固定四机制块已提取八类指标，轨迹相同；历史连续案例与付款子链是补充证据，不拼接为同一因果实验。

总进度文件含早于停止事件的“运行中”字段，不能直接当最新状态。原始暂停标记及流水线停止记录均保留；本仓库不自动恢复运行。

原运行JSON中的旧绝对路径属于历史记录。浏览或再分析时使用仓库内相对路径，迁移映射见 `provenance/relocation.json`。本次没有改写原评分、哈希或失败。

## 连续案例与补充证据

| 保存区 | 用途 |
|---|---|
| `output/integration/linked_case0014_20261102/` | 已有联动案例及其核对，不作为新增独立项目累加 |
| `output/integration/origin_lifecycle_20261025_09/` | 原生规则连续链、事件与反馈 |
| `output/integration/origin_model_lifecycle_20261025_03/` | 已有有限选项模型参与连续链 |
| `output/integration/case0005_model_lifecycle_20261026_08/` | 另一来源的模型连续案例 |
| `output/integration/case0005_payment_continuation_20261026_02/` | 付款子链及其核对 |
| `Capstone报告/验证体系/实验/` | 当前冻结设计、原始模型回答、评分、复核、账本与宏观已启动链 |
| `validation/` | 现有结论需要的历史采样与来源追溯 |

内部日期用于区分证据来源，日常工作从本页进入。补充案例不与不同实验设置下的结果直接合并计算总准确率。

## 2026-11-19 实验结果

组织机制有两条并行证据线，**分数不可合并**：上方索引中的 CP07 `org_deliberation_metrics_20261119`／`org_ablation_sensitivity_20261119`（冻结业务卡 S/D3/S4），与下方 `micro-org-*`（招标管线 single/solo/multi + rubric v2）。臂名仅可作叙述类比（S≈single，S4≈solo，D3≈multi）。

- [单智能体与多智能体微观评分](experiments/micro-org-1118/REPORT.md)
- [真实模型端到端跑通](experiments/e2e-case0014-1119/README.md)
- [真实模型端到端跑通（第二案例）](experiments/e2e-case0001-1119/README.md)
- [单 agent 与多 agent 宏微观衔接对照](experiments/paired-full-case0014-20261119/COMPARISON.md)
- [352-case ground-truth evaluation](experiments/full352-groundtruth-20261119/REPORT.md)
- [CASE-0049 paired real-model lifecycle cost](experiments/paired-full-case0049-20261119/cost.json)
- [精选六例微宏观衔接结果](experiments/selected-six-20261119/REPORT.md)
- [微观采购评分独立扩样与九例汇总](experiments/micro-org-replication-20261119/比较结果.md)
- [十二例微观采购评分对照](experiments/micro-org-extension12-20261119/十二例评分汇总_核定.md)
- [352-case DBB 初始输入清单](experiments/full352-dbb-inputs-20261119/manifest.csv)
