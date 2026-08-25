---
title: LLM Wiki 兼容层与原生 OKF 边界
type: Integration Contract
description: 说明旧 LLM Wiki 工具别名与 OKF 原生查询之间的兼容关系。
status: draft
tags: ["llm-wiki", "mcp", "compatibility", "okf"]
generated:
  by: process:legacy-migration
  at: "2026-08-22T00:00:00Z"
---

# LLM Wiki 兼容层与原生 OKF 边界

MCP 的 `search`、`read_page` 和 `catalog` 被保留，以保证既有技能仍能工作。它们全部只读，并由同一个 OKF 解析器提供结果。

新调用方应优先使用 `okf_search`、`okf_read_concept`、`okf_list_concepts`、`okf_validate`、`okf_graph` 和 `okf_trace_context`。原生接口以概念 ID、元数据、链接、来源、信任信号和分页内容作为稳定契约；旧接口仅返回面向过渡期的路径视图。

可视化也基于这些概念 ID，而不是宿主机绝对路径。详见 [法务 OKF 模式与扩展](../schema.md)。
