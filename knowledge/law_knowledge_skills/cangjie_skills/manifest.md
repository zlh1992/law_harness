# cangjie-skill manifest（v1）

- 目标：将初创企业高频法务咨询中“动作化”内容蒸馏为可触发的技能。
- 基准来源：llm_wiki 的来源索引 + 监管资讯源（见 `../llm_wiki_知识库/sources_index.md`）。
- 命名约定：`snake_case`，与输入场景和输出契约一一对应。

| Skill ID | 名称 | 适用范围 | 触发类型 | 去向 |
| --- | --- | --- | --- | --- |
| startup_foundation_compliance_audit | 成立法务体检 | US / CN / EU | 创业初期体检、成立前体检 | 技能（cangjie） |
| workforce_classification_and_labour_contract | 用工关系与合同风控 | US / CN / EU | 外包/承包/员工边界咨询 | 技能（cangjie） |
| seed_due_diligence_pack | 融资尽职文件包 | US / CN / EU | 种子轮/天使轮融资索取材料 | 技能（cangjie） |
| cross_jurisdiction_privacy_router | 数据合规路由 | CN / US / EU | 隐私/数据合规咨询 | 技能（cangjie） |
| ip_protect_and_registration_playbook | IP 与商标保护 | CN / US / EU | 创业商标/IP 保护提问 | 技能（cangjie） |
| legal_service_matcher_for_startups | 律所服务匹配 | US / CN / EU | 咨询“找谁做什么”的入口判断 | 技能（cangjie） |
| legal_news_to_risk_signal | 合规新闻到风险信号 | US / CN / EU | 监管新闻后判断影响动作 | 技能（cangjie） |

## 发布顺序建议
1. `startup_foundation_compliance_audit`
2. `workforce_classification_and_labour_contract`
3. `seed_due_diligence_pack`
4. `cross_jurisdiction_privacy_router`
5. `ip_protect_and_registration_playbook`
6. `legal_service_matcher_for_startups`
7. `legal_news_to_risk_signal`

## 与 `llm_wiki` 的联动规则
- 每个 skill 只输出可执行清单、决策路径和边界，不替代律师意见。
- skill 所需事实依据应优先引用 `llm_wiki` 实体页（实体：`workplace`、`capital`、`ip`、`compliance`）。
