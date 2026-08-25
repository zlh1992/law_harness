# DeepSeek Harness 本地安装、界面、办公能力与 GPT-5.6 Sol 接入报告

调研与实测日期：2026-08-14

## 结论

DeepSeek Harness 已发布开发者预览版并开源，定位是可组合的 Agent 执行框架，而不只是聊天客户端。官方的一行安装命令可在本机启动 Web UI；本机固定并实测 `0.1.0-rc.7`，包含 persistent Bash 提示符就绪修复，服务地址为 `http://127.0.0.1:3080`。[官方发布页](https://deepseek.com/harness/)｜[官方仓库](https://github.com/deepseek-ai/deepseek-harness)

本次已按目标实现“复用当前 ChatGPT/Codex 订阅”的本地兼容桥：Harness 连接本机 OpenAI 风格端点，代理调用已登录 ChatGPT 的 `codex exec`，由 `gpt-5.6-sol` 生成回复或工具调用决策。OpenAI 官方文档明确说明 Codex CLI 支持“Sign in with ChatGPT for subscription access”，且 `codex exec` 是稳定的非交互入口。[OpenAI 身份验证](https://learn.chatgpt.com/docs/auth)｜[Codex 开发者命令](https://learn.chatgpt.com/docs/developer-commands?surface=cli)

DeepSeek Harness 自己仍未提供 `openai-codex` OAuth 登录和刷新存储，因此本实现没有把订阅 token 填入 Harness；而是在本机加了适配层，让 Codex CLI 自己管理登录。该适配层不是 OpenAI 官方 Platform API，也不是官方承诺的 OpenAI 兼容 Codex 服务。

## 本地安装

快速体验：

```bash
npx @deepseek-ai/dsh web
```

默认访问地址：`http://127.0.0.1:3080`。首次启动会下载较多依赖，本机的 npx 缓存约 359 MB；不同系统会有差异。官方也支持从源码安装：

```bash
git clone https://github.com/deepseek-ai/deepseek-harness.git
cd deepseek-harness
pnpm install
pnpm run build
pnpm dsh web
```

官方文档要求先安装 Node.js；本机用 Node.js `25.6.0` 验证通过。[Web UI 指南](https://deepseek-harness.github.io/deepseek-harness/guide/quickstart)

## 界面实测

![DeepSeek Harness 主界面](./deepseek-harness-gpt56-bridge/deepseek-harness-home.png)

主界面是深色优先的本地 Web 应用：左侧是工作区、会话搜索和会话树；中间是工作区选择、Agent 模式和任务输入框；右下或设置页控制模型、权限、语言、主题、插件与 Agent 预设。未选择工作区前，输入框和发送按钮不可用。

首次运行先显示开发者预览声明，再提示填写 DeepSeek API Key；可以选择稍后配置。默认权限选项是 Workspace Write，涉及更高权限的操作会按策略请求审批。

模型页支持 DeepSeek、OpenAI、Anthropic 等目录提供方，也支持自定义 OpenAI 兼容端点；凭据写入 `.credentials.yaml`，设置文件只保存凭据引用。[模型配置指南](https://deepseek-harness.github.io/deepseek-harness/guide/providers)

![本地代理已接入模型页](./deepseek-harness-gpt56-bridge/deepseek-harness-models.png)

本机基础 Web 组合实测列出 133 个插件。四种内置 Agent 预设为：

- 标准模式：文件编辑、Shell、文件与网页检索、Skills、计划、目标、子代理和工作流。
- PTC 模式：具备标准模式能力，并让模型用 TypeScript 程序组合多轮工具调用。
- 极简模式：只保留持久 bash 与 `str_replace_editor`。
- 创造模式：检查运行时、试验插件并创建自定义 Agent preset。

## 能完成哪些办公任务

### 开箱即可做

- 阅读、归纳和改写工作区内的文本、Markdown、代码与配置文件。
- 从网页和本地资料整理调研报告、会议纪要、方案、SOP、FAQ 和任务清单。
- 批量重命名、分类、检索、去重和转换文件。
- 通过 Shell/Python/Node 处理 CSV、日志和结构化数据，生成统计结果和图表数据。
- 维护计划、目标、长任务状态，或把独立工作委派给子 Agent。
- 对软件项目做代码阅读、修改、测试、重构和文档生成；这是当前最成熟的场景。

### 装技能或插件后可做

- 生成或编辑 DOCX、XLSX、PPTX、PDF，并执行格式与渲染检查。
- 连接企业知识库、数据库、MCP 服务或自建 API。
- 构建定时或多步骤工作流，把多个工具组合成可复用的办公流程。

这些能力取决于具体技能、运行库和插件，并非基础 Harness 自动具备；尤其 Office 文件需要专用库与视觉 QA，不能只靠模型输出文本。

### 需要外部连接，不能只靠本地安装

- 收发邮件、改日历、操作飞书/Slack/Notion/Google Drive、CRM 或审批系统。
- 操作原生 Word/Excel/PowerPoint 图形界面。
- 自动登录网站、提交表单或跨应用点击。

这些任务需要对应的插件、MCP/连接器、浏览器自动化能力和账户授权。默认 Web 组合只有文件、Shell、检索和 Agent 编排能力，不应把“可扩展”误解为“所有办公系统已接通”。

## GPT-5.6 Sol 接入方案

### 已完成且实测工作的方案

```text
DeepSeek Harness
  -> http://127.0.0.1:4010/v1
  -> 本地桥接代理
  -> codex exec（当前 ChatGPT 订阅登录）
  -> gpt-5.6-sol
```

代理固定模型为 `gpt-5.6-sol`，支持模型列表、Chat Completions JSON/SSE、Responses JSON/SSE，以及 OpenAI 风格函数工具调用。它只监听回环地址，不读取或复制 Codex OAuth 凭据，也不需要 `OPENAI_API_KEY`。Harness 内配置的 API Key 只是本机代理口令。

为避免双重工具执行，代理把每次 Codex 运行限制为只读、临时会话，并明确禁止其内部工具；Codex 只输出“回复”或“调用哪个 Harness 工具及参数”的结构化决策，真正的文件、Shell、检索等操作仍由 Harness 执行。

真实端到端验证已通过：当前 CLI 状态为 `Logged in using ChatGPT`；普通 Chat Completions 返回“订阅代理成功”，函数调用测试正确返回 `tool_calls` 和 JSON 参数；Responses SSE 可被 OpenAI SDK 6.26 正常迭代，DeepSeek Harness headless 实际返回“Harness流成功”。离线测试 3/3 通过。

### 兼容边界

- 这是自行实现的本地适配器，不是 OpenAI 官方 Platform API。
- Codex 完成一次决策后代理才输出 SSE，不是真正逐 token 转发。
- 每个请求启动一个 `codex exec`，延迟与吞吐低于直接 API；默认并发为 1。
- 使用量、模型权限和限额遵循当前 ChatGPT/Codex 订阅。
- Harness 或 Codex CLI 预览版本升级后可能需要更新适配代码。

## 成本与安全提示

这条路径使用 ChatGPT/Codex 订阅额度，不使用 OpenAI Platform API Key；具体可用量和限额由当前订阅决定。Harness 的长会话、工具结果和子 Agent 会增加上下文用量，建议默认串行并从低或中等推理强度试跑。

只把必要目录加入工作区；保留 Workspace Write/审批策略；不要把代理绑定到 `0.0.0.0`；不要读取、复制或外发 Codex 本地认证文件；预览版升级前备份 DSH_HOME，因为官方明确提示可能出现破坏性变更。
