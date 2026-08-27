# law_knowledge_skills 集成说明

本目录已整合以下两类资产（按“知识库 + Skill”合并）：

- `llm_wiki_知识库/`：纯知识型资产（法规解释、常见问答、合规清单、风险点、来源索引）
- `cangjie_skills/`：可蒸馏为 pipeline 的可执行技能草案（含 `manifest.md`）

目录内文件来自本机历史产物：
- `knowledge/law_knowledge_skills/llm_wiki_知识库`
- `knowledge/law_knowledge_skills/cangjie_skills`

建议下一步：
1. 先导入 `llm_wiki_知识库/README.md` 与 `sources_index.md` 到你的知识检索层。
2. 再逐个梳理 `cangjie_skills/` 下 `manifest.md` 映射到具体执行器（或转写为系统中的 SKILL 规范）。
