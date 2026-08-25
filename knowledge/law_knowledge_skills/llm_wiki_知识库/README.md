# startup-legal-knowledgebase-v1

目标：为“企业法务 / 初创企业 / 小微企业咨询”建立可持续更新的 `llm_wiki` 知识库，并配套 `cangjie-skill` 的流程化技能化蒸馏。

## 1) 任务范围（基于本次搜索）

- 企业法务启动阶段：设立、税务、合规、劳动、人事、常用合同、数据合规、融资。
- 初创企业高频咨询：
  - “我应该先做哪些法务底座动作？”
  - “员工是员工还是承包人？”
  - “种子轮要准备哪些文件？”
  - “跨境/跨域数据是否要做 DPA、隐私条款？”
  - “商标/IP 怎么抢占先发？”
  - “律师事务所怎么选服务模式？”
- 小微企业场景：企业开局期、融资期、增长期、IPO/合规压力上升期。
- 法务新闻与监管变化：SEC 资本市场、FTC / GDPR / EDPB、EU AI、春雨润苗、CNIPA 及 CAC 动态。

## 2) 知识源与蒸馏决策

- 纯知识类（进入 `llm_wiki`）：
  - 固定规则、模板清单、法规条文、定义、流程标准、可归档问答。
  - 例：Cac 的小型个人信息处理者简化规则、CNIPA 办事指南、SBA/IRS/DOL 用工与税务要点、SEC 合规框架介绍。
- 流程化/决策类（进入 `cangjie-skill`）：
  - 需要“输入->判断->输出->边界”的执行化场景。
  - 例：合同/劳动关系识别、融资尽调清单生成、新闻风险映射到行动计划。

## 3) llm_wiki 目录建议（可直接创建）

- `purpose.md`：问题域与优先级（含 `US / CN / EU` 参考）
- `schema.md`：实体与类型定义（问题、流程、文档模板、风险项、新闻）
- `overview.md`：知识总览与交付边界
- `index.md`：检索入口
- `wiki/entities`：
  - `jurisdiction/`（jurisdiction_us.md、jurisdiction_cn.md、jurisdiction_eu.md）
  - `founding/`（注册形态、许可、税号、BOI/税务）
  - `workplace/`（劳动关系、社保、外包/派遣边界）
  - `capital/`（融资、尽调、信息披露）
  - `ip/`（商标、版权、合约归属）
  - `compliance/`（隐私、AI、数据安全）
  - `incidents/`（SEC/FTC/EDPB/AI Act/春雨润苗要闻）
- `wiki/concepts`：法务概念定义与对照表
- `wiki/sources`：原始来源的快照索引（带发布时间）
- `wiki/queries`：高频咨询 Q&A（面向咨询问句）

## 4) Ingest / 更新节奏

- 第一阶段（周1）：先建 `purpose + schema + overview`，先导入静态法源（SBA、IRS、DOL、CNIPA、CAC、SEC、GDPR/AI/EDPB 源）。
- 第二阶段（周2）：补齐服务目录与模板（合同、商标、章程、劳动关系自检清单）。
- 第三阶段（周3）：建立新闻事件索引并绑定“影响域”标签（融资、劳动、数据、IP、税务）。
- 第四阶段（周4+）：每月回看新法更新，跑一次 cross-check（知识与 skill 的重叠条目做去重）。

## 5) 下一步落盘动作（建议）

1. 先从 `outputs/cangjie_skills/manifest.md` 逐条确认哪些是 pipeline。
2. 将每条 pipeline 在知识库中的源事实页先创建，再执行 distill。
3. 将所有来源用统一格式追加到 `sources_index.md`（已含可追溯链接与日期）。
4. 每次新增新闻优先更新 `wiki/incidents`，并触发 `cangjie_skills/skill_7_合规事件新闻跟踪.md`。
