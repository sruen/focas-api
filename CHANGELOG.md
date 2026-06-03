# Changelog

## FOCAS_ENGINE_EXECUTION_PATCH_v1.0.2 Clean Source

- 统一正式版本身份、包名与运行说明。
- 增加 `STOP_REPORT_ONLY`，阻断缺项输入的正文渲染。
- 增加 `Strength_Source`，区分输入校准、辅助估算与人工复核门禁。
- 增加 P4→现代骨架桥接表，正式理论区间只接受表内匹配。
- 补全 William、Ladbrokes 与 Avg 的转换后查表证据简表。
- 增加赔率动作五道门与 William / Ladbrokes 公司目的链。
- 保持第二阶段为相对结构强弱选择，不把相对弱改写成不利排除。
- 增加完整输入、基本面停止和查表停止示例。
- 将比赛包解压改为安全逐项校验解压。
- 补全门禁、表驱动、前台报告与安全解压回归测试。

## ReturnRate System Gate + Corrected Market Ladder

- 默认硬数据源切换为 `FOCAS_89_96_MODERN_SKELETON_INTERVAL_COMPACT_v5_CORRECTED_MARKET_LADDER.xlsx`。
- 新增严格 `ReturnRateSystemGate`：William / Ladbrokes 按每个快照实际返还率识别 89-96 体系，超阈值立即停止。
- P5 / P8 改为读取新版体系 sheet；联赛、杯赛、国家队与中立场只作为语义修正。
- P4 内置 strength interval bridge 与新版 xlsx 现实赔率落点分开标注。
- 前台查表证据补充返还率、识别体系和格式化边界距离。

## Opening Motive Consistency Gate

- 新增初赔目的链：在变赔解释前，先判断机构是否利用基本面、广义实力、原始分布和主客场第一眼拉力做盘。
- 双公司初赔若形成同方向利诱 / 过热候选，且后续没有双公司反转确认，第二阶段禁止仅凭基本面高分重新选回该方向。
- Avg 动作从第二阶段结构评分移除；Avg 继续只作为市场背景。
- 公司语义“确认不足”改为零权重，不再错误增加结构方向分。
- 胜韬标签只解除机械排除，不再直接增加主胜结构方向分。
