---
okf_version: "0.2"
---

# 法务 OKF 知识包

本包以 Google OKF v0.2 的 Markdown/YAML 契约保存可复核的本地法务知识；它用于问题定位、来源追溯和风险分流，不构成法律意见。

## 知识与治理

- [包目的](purpose.md) — 使用边界、读写分离与人工复核原则。
- [包模式](schema.md) — 本包采用的 OKF 与 `law` 扩展字段。
- [法域覆盖](jurisdictions/coverage.md) — 当前覆盖范围与失效处理规则。
- [来源登记](sources/regulatory-source-register.md) — 已登记的监管与服务入口。
- [来源使用规则](concepts/source-handling.md) — 引用、时效与信任信号的解释。
- [兼容层](concepts/llm-wiki-compatibility.md) — 旧版 `search/read_page/catalog` 的迁移边界。

## 可执行问题路由

- [设立合规体检](playbooks/startup-foundation-compliance-audit.md)
- [用工分类与合同](playbooks/workforce-classification-and-labour-contract.md)
- [种子轮尽调](playbooks/seed-due-diligence-pack.md)
- [跨法域隐私](playbooks/cross-jurisdiction-privacy-router.md)
- [知识产权与商标](playbooks/ip-protect-and-registration-playbook.md)
- [法律服务匹配](playbooks/legal-service-matcher-for-startups.md)
- [监管新闻风险信号](playbooks/legal-news-to-risk-signal.md)

## 计算与审计

- [风险信号计算说明](computations/legal-risk-signal-spec.md) — 可复现的规则计算边界。
- [变更记录](log.md) — 导入与人工复核记录。
