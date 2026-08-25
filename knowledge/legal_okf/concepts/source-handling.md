---
title: 来源、信任信号与时效处理
type: Governance Rule
description: 规定来源登记、OKF verified 信号、过期时间和回答引用之间的关系。
status: draft
tags: ["sources", "trust", "staleness", "citation"]
generated:
  by: process:legacy-migration
  at: "2026-08-22T00:00:00Z"
law:
  jurisdictions: ["CN", "US", "EU"]
  authority_level: "governance"
  topics: ["provenance", "citation", "staleness"]
---

# 来源、信任信号与时效处理

`sources[]` 记录概念依赖的资源，`id` 应稳定，`resource` 必须可定位。它不证明资源已在本轮读取，也不等于内容正确或仍然有效。

信任层级只从 OKF 元数据推导：无 `verified` 是 `unverified`；存在非人工核验是 `machine-confirmed`；存在 `human:` 参与者才是 `human-reviewed`。这些是建议性信号，不是权限控制，不能伪造人工复核。

对于含 `stale_after` 的概念，过期后应提示重新核验。对监管新闻、征求意见、实施日期和地域性规则尤其如此。已登记来源见 [监管与公共法律服务来源登记](../sources/regulatory-source-register.md)。
