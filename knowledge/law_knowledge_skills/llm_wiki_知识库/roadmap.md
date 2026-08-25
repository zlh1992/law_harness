# llm_wiki import roadmap（v3）

## 交付结果（已完成）

- `llm_wiki` 侧：建立了《startup-legal-knowledgebase-v1》及知识源索引。
- `cangjie-skill` 侧：保留 7 个蒸馏技能（清单见 `outputs/cangjie_skills/manifest.md`）。

## 执行策略（知识库 vs Skill）

- 判定规则：
  - 知识库 = 可被问答检索的事实、定义、法规、时间线。
  - Skill = 可执行动作链、分支决策、风险分级、输出清单。
- 映射策略：
  - 成立与合规底座 → `startup_foundation_compliance_audit`
  - 用工关系识别 → `workforce_classification_and_labour_contract`
  - 融资材料包 → `seed_due_diligence_pack`
  - 数据合规分流 → `cross_jurisdiction_privacy_router`
  - IP与商标策略 → `ip_protect_and_registration_playbook`
  - 咨询入口路由 → `legal_service_matcher_for_startups`
  - 新闻风险解读 → `legal_news_to_risk_signal`

## 本轮已抓素材（含新闻）

- 法规与制度：SBA、IRS、DOL、SEC、CNIPA、CAC、EDPB、EU AI Act、12348
- 资讯信号：SEC 2026 系列规则更新、EDPB 2026 协调执法、CAC 个体处理者隐私简化路径

## 后续持续机制

- 每周：新增 2-4 条可验证来源，先入 `sources_index.md`，再决定知识/Skill 归属。
- 每月：运行一次 `legal_news_to_risk_signal` 场景测试，检查是否需要更新风险阈值。
- 每季度：补全 10%-20% 高频咨询模板，更新 skill 的“缺口-优先级-动作模板”。
