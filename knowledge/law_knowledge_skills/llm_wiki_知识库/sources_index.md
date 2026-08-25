# Sources Index（2026-08-16）

## 项目层（先确认项目身份）

- llm_wiki
  - 代码库： https://github.com/nashsu/llm_wiki
  - 官方说明： https://github.com/nashsu/llm_wiki/blob/main/README_CN.md
  - DeepWiki： https://deepwiki.com/nashsu/llm_wiki
- cangjie-skill
  - 代码库（工程实现）： https://github.com/Yeadon8888/cangjie-skill
  - 另一个实现（更接近 skill 工厂结构）： https://github.com/kangarooking/cangjie-skill

## A. 适合进入 `llm_wiki` 的知识类（可检索事实/规则）

| 日期 | 来源 | 法域 | 说明 |
| --- | --- | --- | --- |
| 持续更新（2026） | https://www.sba.gov/business-guide/launch-your-business | US | 创业起步、选型、合规通用流程 |
| 持续更新（2026） | https://www.sba.gov/business-guide/manage-your-business | US | 税务、用工、日常经营合规框架 |
| 2026-05-19 | https://www.sec.gov/newsroom/press-releases/2026-46-sec-proposes-transformative-reforms-help-public-companies-conduct-registered-offerings-simplify | US | 证券发行与披露制度更新 |
| 2026-07-16 | https://www.sec.gov/newsroom/press-releases/2026-67-sec-proposes-new-e-delivery-approach-make-information-more-readily-accessible-useful-investors | US | 信息递送与披露流程更新 |
| 2026-07 | https://www.sec.gov/rules-regulations/2026/07/s7-2026-25 | US | SEC rulemaking 页面，含实施规则文本位置 |
| 2026-07-24 | https://www.cac.gov.cn/2026-07/24/c_1786638889576451.htm | CN | 小型个人信息处理者简化措施（征求意见稿） |
| 2026-07-24 | https://www.cac.gov.cn/2026-07/24/c_1786639233707663.htm | CN | 简化措施答记者问，适合补充解释边界 |
| 2024-08-01 起（EU） | https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai | EU | AI Act 框架、实施路径与高风险类别 |
| 2026 | https://www.edpb.europa.eu/news/cef-2026-edpb-launches-coordinated-enforcement-action-on-transparency-and-information-obligations_en | EU | GDPR 信息透明与告知义务执行方向 |
| 常态更新 | https://www.cnipa.gov.cn/ | CN | 商标/IP 官方服务总入口（需结合当期政策） |
| 常态更新 | https://www.cnipa.gov.cn/col/col139/index.html | CN | 商标与专利服务分类入口 |
| 2026-02 | https://www.irs.gov/forms-pubs/about-form-ss-4 | US | 企业税务身份（EIN）申请条款说明 |
| 常态更新 | https://www.irs.gov/businesses/small-businesses-self-employed/independent-contractor-vs-employee-self-employment-tax | US | 独立承包人与雇员边界及税务影响 |
| 常态更新 | https://www.dol.gov/agencies/whd/fact-sheets/13-flsa-employment-relationship | US | FLSA 雇佣关系判定逻辑 |
| 常态更新 | https://www.dol.gov/agencies/whd/flsa/misclassification/small-entity-compliance-guide | US | 小企业用工分类风险控制参考 |
| 常态更新 | https://www.12348.gov.cn/ | CN | 小微企业公共法律服务入口 |
| 常态更新 | https://sh.12348.gov.cn/index.jsp | CN | 上海法网：小微企业法律咨询入口 |

## B. 适合蒸馏到 `cangjie-skill` 的 pipeline 类（动作流）

| 触发问题 | 来源 | 对应 skill | 蒸馏方式 |
| --- | --- | --- | --- |
| “公司开局先做什么（注册、税号、许可）” | https://www.sba.gov/business-guide/launch-your-business 与 /manage-your-business；https://www.sba.gov/business-guide/launch-your-business/get-federal-state-tax-id-numbers | startup_foundation_compliance_audit | 把流程拆成 `前置条件 -> 第一步 -> 风险分支 -> 交付项` |
| “员工/外包边界” | https://www.irs.gov/businesses/small-businesses-self-employed/independent-contractor-vs-employee-self-employment-tax；https://www.dol.gov/agencies/whd/fact-sheets/13-flsa-employment-relationship | workforce_classification_and_labour_contract | 将控制因素、报酬方式、合同形式转为判定规则树 |
| “融资尽调清单” | https://www.cooleygo.com/wp-content/uploads/2014/07/Cooley-GO-Tip-Sample-VC-Due-Diligence-Request-List.pdf；https://www.orrick.com/en/Insights/Startup-Legal-Essentials-The-Conversation-Series | seed_due_diligence_pack | 输出缺口清单 + 轮次优先级 + 缺失项风险 |
| “隐私合规该先做什么” | https://www.cac.gov.cn/2026-07/24/c_1786639233707663.htm；https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai | cross_jurisdiction_privacy_router | 做成“场景路由（是否小型处理者/是否跨境）+ 最低动作” |
| “IP 和商标保护起步顺序” | https://www.cnipa.gov.cn/col/col139/index.html；https://www.uspto.gov/trademarks/basics | ip_protect_and_registration_playbook | 形成检索 -> 申请 -> 观察异议 -> 维权的执行序列 |
| “找律师/法务入口怎么选” | https://sh.12348.gov.cn/index.jsp；https://www.12348.gov.cn/ | legal_service_matcher_for_startups | 依据问题类型、预算、地域、风险等级路由到服务层级 |
| “监管新闻怎么影响我当前业务” | https://www.sec.gov/newsroom/press-releases/2026-46-sec-proposes-transformative-reforms-help-public-companies-conduct-registered-offerings-simplify；https://www.edpb.europa.eu/news/cef-2026-edpb-launches-coordinated-enforcement-action-on-transparency-and-information-obligations_en；https://www.sec.gov/rules-regulations/2026/07/s7-2026-25 | legal_news_to_risk_signal | 新闻->影响域标注（融资/劳动/数据）-> 处置动作清单 |

## C. 执行口径（本轮）

- `llm_wiki` 负责保存：法规文本、解释、流程定义、时效与边界。
- `cangjie-skill` 负责保存：输入字段、判定逻辑、动作输出、边界条件。
- 每条 skill 输入 `sources[]`，确保可追溯，便于后续人工法务复核。
