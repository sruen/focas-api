# FOCAS_ENGINE v1.1.5

完整工程由四个隔离模块组成：

- `focas_prematch`：调用原 `focas_engine` 赛前 pipeline，输出不可变 `prematch_snapshot.json`。
- `focas_postmatch`：读取赛前快照和 `result.json`，自动生成 v0.2 事实样本并写入本地 JSONL。
- `focas_experience`：只读历史赛后样本，按赛前 fingerprint 输出分级经验报告。
- `shared`：跨模块 schema、枚举、验证器与赔率坐标类型。

原 `focas_engine` 保持为赛前核心实现。赛后复盘逻辑不会写入 `focas_engine/pipeline.py`、`engine.py` 或 P1-P9 赛前规则。

## 统一 CLI

赛前分析：

```bash
python -m focas_prematch.cli analyze \
  --match-package examples/valid_complete_match_package.zip \
  --out prematch_snapshot.json \
  --fingerprint-out prematch_fingerprint.json \
  --experience-out experience_report.json \
  --with-experience
```

## 三项题材审计与 PASS

- `natural_pulls` 仍兼容旧输入，但只视为聚合题材。没有逐条来源时，正式结论必须降级为 `PASS` 或 `OBSERVE`。
- 新输入可增加 `narrative_materials`。主胜、平局、客胜都应提供至少一条题材，并记录 `topic`、`facts`、`source`、`published_at`、`visibility`、`strength`、`strength_alignment`。
- 题材存在不等于影响市场；影响市场不等于机构已经利用；机构利用题材不等于该赛果必然兑现。
- 当前现代骨架表只有主赔精确轴。平赔或客赔成为最低项时，程序保留组合参考并输出 `HOME_AXIS_ONLY_REVIEW_REQUIRED`，不得冒充三项精确骨架。

示例：

```json
{
  "narrative_materials": [
    {
      "direction": "主胜",
      "topic": "主队近期连胜与排名优势",
      "facts": "来源核验后的事实摘要",
      "source": "source URL or verified manual source",
      "published_at": "2026-06-02T10:00:00+08:00",
      "visibility": "高",
      "strength": "强",
      "strength_alignment": "与真实实力一致",
      "institution_use_status": "UNCONFIRMED",
      "institution_use_evidence": []
    }
  ]
}
```

赛后复盘和入库：

```bash
python -m focas_postmatch.cli review \
  --prematch prematch_snapshot.json \
  --result examples/result.json \
  --out postmatch_sample.json
python -m focas_postmatch.cli validate --file postmatch_sample.json
python -m focas_postmatch.cli add --file postmatch_sample.json
python -m focas_postmatch.cli rebuild-index
```

历史经验查询：

```bash
python -m focas_experience.cli query --fingerprint prematch_fingerprint.json
```

赛后数据固定写入：

```text
data/postmatch/postmatch_samples.jsonl
data/postmatch/postmatch_sample_index.json
```

## 经验边界

- 原始分布用于第一层粗结构匹配。
- `distribution_fingerprint` 使用 `fingerprint_version=0.3`。`dispersion_sides` 只记录非主要信心承载、非自然热度方向的可分流侧；主要承载方向不会反向写入分流列表。
- 相同现代骨架理论区间和相同现实开赔坐标用于第二层精确结构匹配。
- 变赔路径只用于第三层确认，不得以赔率动作小数或动作标签代替原始分布匹配。
- 相同赛前方向的 `decision_key` 只能观察历史同决策表现，不能作为主匹配入口，避免自我证明。
- 经验报告只能校准赛前判断，不能单独决定方向。
- A 级经验可以作为 P8 第二阶段相对主线选择的辅助证据。
- B 级经验只能提示风险。
- C 级经验只展示。
- D 级经验不进入赛前判断。
- 任何经验等级都不得单独决定最终方向。

`--with-experience` 在正常赛前分析、快照写出和 fingerprint 写出之后生成旁路经验报告。它不会修改 `prematch_snapshot.final_direction`，也不会修改原 `focas_engine/pipeline.py`。

## 高质量赛后复盘

`focas_postmatch review` 会自动生成事实记录模板。为了形成适合长期经验沉淀的高质量样本，建议在 `result.json` 的 `review` 字段中人工补充：

- `three_way_review`
- `logic_audit`
- `error_or_success`
- `tags`
- `lesson`

未补充时仍可自动生成和入库，但样本只适合作为事实记录，不适合直接视为高质量经验。

---

# 原赛前引擎说明

# FOCAS Engine Clean Source

正式锁定口径：

```text
Main_Rule = v1.7_MAINLINE_ADVERSE_DIRECTION_LOCK
Engine_Patch = FOCAS_ENGINE_EXECUTION_PATCH_v1.0.2
Engine_Package = focas_engine_v1_0_2_clean_project_source.zip
Hard_Data_Source = FOCAS_89_96_MODERN_SKELETON_INTERVAL_COMPACT_v5_CORRECTED_MARKET_LADDER.xlsx
Original_Book_Source = 欧赔核心思维完整版共24章416页-8MB.doc
Build_Status = CLEAN_SOURCE
Engine_Runtime = v1.0.2
Rule_Lock = v1.7_MAINLINE_ADVERSE_DIRECTION_LOCK
Betting_Permission = NO
Signal_Permission = NO
Formal_Prediction = NO
```

## 推理顺序

```text
基本面硬闸门 → 广义实力来源 → 三项自然拉力 → 原始分布 → 原书模式
→ P4 表驱动理论区间 → 机构返还率体系识别 → 按机构体系读取理论骨架区间赔率 → 机构原始初赔合理性审计 → 原始赔率按体系查表
→ 赔率动作、赔面与公司目的拆解 → 综合结构判断 → 第二阶段相对结构选择
→ 中文前台报告
```

## 运行

```bash
python -m focas_engine.cli examples/valid_complete_match_input.json \
  --table FOCAS_89_96_MODERN_SKELETON_INTERVAL_COMPACT_v5_CORRECTED_MARKET_LADDER.xlsx
```

后台审计：

```bash
python -m focas_engine.cli examples/valid_complete_match_input.json \
  --table FOCAS_89_96_MODERN_SKELETON_INTERVAL_COMPACT_v5_CORRECTED_MARKET_LADDER.xlsx \
  --backend-audit
```

## 关键边界

- 基本面缺项、实力需要人工复核、硬判断公司返还率体系不可识别或新版 xlsx 查表失败时，前台只输出 `STOP_REPORT_ONLY`。
- William 与 Ladbrokes 必须先完成 `ReturnRateSystemGate` 再按实际 89-96 体系 sheet 查表。Avg 只进入市场背景层。
- 联赛、杯赛、国家队和中立场属性只参与语义修正，不参与现代骨架查表准入。
- P4 理论区间来自 `focas_engine/data/p4_strength_interval_table.csv` 内置 strength interval bridge。现实赔率落点来自新版 xlsx，二者不得混写。
- 初赔合理性审计是机构动机判断的前置硬步骤：先按 William / Ladbrokes 各自初赔返还率识别 89-96 体系，再从该体系 sheet 读取 P4 理论区间的主赔精确范围和平负档口参考范围，最后比较机构发布的原始初赔。赔率数值不做二次转换；返还率差异已经体现在各体系骨架表中。骨架缺失或不可调用时，机构动机必须标记复核，不得猜测。
- P4 桥接键缺失时标记 `EXPECTED_INTERVAL_STATUS = REVIEW_REQUIRED`；已经成立的 William / Ladbrokes 新版 xlsx 现实归位仍保留。
- 抬高 / 拉低只是动作，必须经过信心承载、分散有效性、自然拉力、表内区间和公司目的五道门。
- 初赔必须先结合基本面、广义实力、原始分布、P4 理论区间和主客场拉力解释。双公司初赔若对同一方向形成利诱 / 过热候选，后续没有双公司反转确认时，不得仅凭基本面高分把该方向重新选回最终结构方向。
- 未确认不能排除。第二阶段相对弱不等于不利排除。
- 工程不输出投注建议、买入建议、主推、稳胆、资金分配、自动信号或正式预测包装。

## 测试

```bash
pytest -q
```

## 网页版 ChatGPT GPT Action

`focas_api` 将赛前分析封装为 JSON API。赔率数值不做二次转换；返还率只用于将每个机构快照路由到对应 `89系-96系` 骨架表。

本地启动：

```bash
set FOCAS_API_KEY=replace-with-a-long-random-secret
python -m focas_api.server --host 127.0.0.1 --port 8787
```

健康检查：

```bash
curl http://127.0.0.1:8787/health
```

分析接口：

```text
POST /v1/analyze
Authorization: Bearer replace-with-a-long-random-secret
Content-Type: application/json
```

请求体：

```json
{
  "match_input": {
    "match": {},
    "home_context": {},
    "away_context": {},
    "h2h": {},
    "strength": {},
    "natural_pulls": [],
    "odds": []
  },
  "include_report": false
}
```

部署到公网 HTTPS 后：

1. 将 `focas_api/openapi.yaml` 中的 `https://YOUR_DOMAIN` 替换为真实域名。
2. 在网页版 ChatGPT 创建 GPT，并把 `focas_api/gpt_instructions.md` 放入 Instructions。
3. 新增 Action，导入 `focas_api/openapi.yaml`。
4. 将认证方式配置为 API Key，并选择 Bearer。GPT Actions 不支持自定义 Header。
5. 使用长随机值设置服务器环境变量 `FOCAS_API_KEY`，并在 GPT Action 中填入相同值。

生产环境必须使用公网域名、TLS 1.2 以上、有效证书和 `443` 端口。GPT Actions 单次请求与响应均应小于 `100000` 字符，并在 `45` 秒内返回。

容器部署入口：

```bash
docker build -t focas-api .
docker run --rm -p 8787:8787 -e FOCAS_API_KEY=replace-with-a-long-random-secret focas-api
```
