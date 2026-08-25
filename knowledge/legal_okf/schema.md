---
title: 法务 OKF 模式与扩展
type: Schema
description: 定义本包如何采用 OKF v0.2，并限定法务领域扩展字段。
status: draft
tags: ["okf", "schema", "law"]
generated:
  by: process:legacy-migration
  at: "2026-08-22T00:00:00Z"
---

# 法务 OKF 模式与扩展

每个非保留 Markdown 文件都是一个概念，概念 ID 等于相对路径去除 `.md`。每页需要 YAML frontmatter 的 `type`，并建议有 `title`、`description`、`sources`、`generated`、`verified`、`status` 与 `stale_after`。

本包使用开放的 `law` 命名空间存放 `jurisdictions`、`authority_level`、`effective_from`、`effective_to` 和 `topics`。这些字段描述适用边界，不是访问控制，也不替代对具体情形的法律判断。

标准 Markdown 链接表达概念关系；`sources[].resource` 可指向包内概念或外部权威页面。详见 [来源使用规则](concepts/source-handling.md)。
