---
title: 法务风险信号计算说明
type: Attested Computation
description: 定义把已登记的事实变量转换为风险优先级的确定性、不可执行计算说明。
status: draft
tags: ["attested-computation", "risk", "audit"]
generated:
  by: process:legacy-migration
  at: "2026-08-22T00:00:00Z"
law:
  jurisdictions: ["CN", "US", "EU"]
  authority_level: "decision-support"
  topics: ["risk-signal", "auditability"]
---

# 法务风险信号计算说明

输入为已记录的法域数量、截止日期距离、数据敏感性、融资/执法影响和来源时效；每项先映射到离散等级。确定性规则可将等级相加后划分为低、中、高优先级，并必须输出原始输入、规则版本和运行时间。

本概念仅描述可复现计算，不执行代码、调用模型或生成法律结论。任何需要外部事实、法规解释或权重变更的步骤都必须另行记录来源和人工审批。相关问题路由见 [监管新闻到风险信号路由](../playbooks/legal-news-to-risk-signal.md)。
