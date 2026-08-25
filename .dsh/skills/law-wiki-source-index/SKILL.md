---
name: law-wiki-source-index
description: 使用本地 llm_wiki 的来源索引、法域范围和知识库边界，为法务回答提供可复核的本地来源入口。
whenToUse: 需要列出依据、定位本地知识库来源、说明资料覆盖范围或发现来源不足时使用。
metadata:
  source: legal_okf/sources/regulatory-source-register.md
---

# 本地法务知识库来源索引

本地知识库覆盖初创企业的设立、劳动、融资、知识产权、数据合规与监管新闻；其内容是风险识别与行动清单，不是律师意见。回答应优先采用监管机构、法定规则和本地 OKF 来源登记中可复核的一手来源；资料不包含的问题应明确标注为“需进一步核验”，不要补造引用。

需要知识库依据时，必须先调用 `mcp__law_wiki__okf_search` 使用业务关键词检索，再按返回的 `id` 调用 `mcp__law_wiki__okf_read_concept`。至少读取一个与问题直接相关的业务概念；如果结果只是治理、来源登记或导航概念，应换用更具体的主题词再次检索。旧版 `mcp__law_wiki__search` 与 `mcp__law_wiki__read_page` 仅用于兼容旧技能。

输出依据时，列出 OKF 概念 ID、页面标题、与结论的关系；若读取 `sources/regulatory-source-register`，还应列出来源名称/链接、适用法域及日期（文件有记录时）。只把工具实际返回的正文作为已知内容；仅登记在索引中的链接不等于已读取其网页正文。需要审计上下文时，调用 `mcp__law_wiki__okf_trace_context`，但不要把其信任状态误说成外部网页已被读取。
