---
title: 法务 OKF 知识包目的与使用边界
type: Bundle Purpose
description: 说明本地法务知识包的用途、读写边界和人工复核要求。
status: draft
tags: ["governance", "legal", "controlled-write"]
generated:
  by: process:legacy-migration
  at: "2026-08-22T00:00:00Z"
law:
  jurisdictions: ["CN", "US", "EU"]
  authority_level: "governance"
  topics: ["knowledge-governance", "legal-advice-boundary"]
---

# 法务 OKF 知识包目的与使用边界

本包服务于初创企业法务问题的知识定位、行动清单路由、来源登记和回答审计。它不替代律师对事实、适用法和时效的判断。

运行时提供读取、检索、校验和可视化；显式请求的概念 CRUD 经过路径安全、版本检查、原子写入和完整 OKF 校验，失败自动回滚。批准和发布仍应由独立的受控维护流程完成。任何标为 `draft` 或 `unverified` 的内容只能作为待核验线索。

阅读前先从 [来源使用规则](concepts/source-handling.md) 确认引用边界，再按具体问题进入 [执行问题路由](index.md#可执行问题路由)。
