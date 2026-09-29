# 按参赛须知重构的 Agent 初稿

本目录是通用智能体代码。它在运行时读取需求并调用模型生成目标应用，没有包含预写的赛题页面、种子数据、业务逻辑、旧演示工程或针对两题的固定方案。`../arcbench-v0` 仅保留为本地学习演示，禁止复制进本包或在参赛运行时读取它。

状态：已完成离线验证、最小 ZIP 打包、真实模型连通检查（1 次请求，124 tokens）和官方模拟器 prepare-only 工作区组装；尚未用 Docker Runner 生成和评测应用，不能据此声称具备正式通过率或已通过赛事审核。真实费用待 Meter 核对。

## 本次纠正

- 官方统一入口：`python3 main.py <requirements_dir> --output-dir <output_dir>`。
- 每次只读本次传入的 `requirements.yaml`。两题由平台分别调用同一 Agent，不在代码里判断题目名称。
- 模型先规划，再逐模块生成、读回修改，最后复核全部需求并进行构建与修复；没有复制应用答案的后备路径。
- 要求生成 `frontend/package.json` 的 `build` 和 `backend/package.json` 的 `start`，服务监听 3000。采用标准 npm 部署方式。
- 写文件工具限制在本次输出目录的 frontend/backend 中；不提供读取外部文件或隐藏测试的工具。
- 保留需求 SHA-256、模型调用指纹/回复/用量、模块报告和本地检查日志，存放于产物 `.agent-evidence/`。
- ZIP 用明确文件名单打包，只有 `main.py`、`requirements.txt`。不包含文档、测试夹具、旧应用、API Key 或题目需求。

运行契约依据：<https://github.com/code-philia/hackathon-local-simulation>，核对于 2026-09-29。仓库当前明确提示自定义 deploy.sh 仅适用于本地模拟环境，正式环境应走 frontend/backend 标准流程；以主办方后续公告为准。

## 现在先做什么

1. 已从官方课程 Lab02 确认练习服务 Base URL 为 `https://api.arc-bench.com/v1`，默认模型为 `deepseek-v4-flash`。配置模板已填入这两项。队长持有 Key，请在本机填写 `OPENAI_API_KEY`；无需把 Key 发到聊天。实际账号权限、价格和连通性仍需首次实测确认。
2. 准备 Docker Desktop 的 Linux containers 和 WSL 2。当前本机未在 PATH 中找到 docker，尚未确认官方容器能运行。
3. 获取官方模拟仓库，使用其公开练习题，先做一次真实生成、部署、公开测试全流程。不要一开始就用正式两题消耗比赛券。
4. 公开练习跑通后，分别用两题公开需求运行，记录费用和应用产物；不传隐藏测试，未提供公开测试时只有部署结果。
5. 队长在截止前提交一次正式评测；等待两题都结束再决定下一次。正式提交平台注入自己的 Key，不上传练习 Key。

## 不花模型额度的检查

在本目录运行：

```powershell
python -m unittest discover -s tests -v
python main.py 'D:\arcbench-hackathon-requirements\hackathon--sheet' --output-dir '..\..\work\preflight-sheet' --preflight
python package_agent.py
```

`--preflight` 仅检查输入，不生成应用、不写输出目录、不请求模型。它不是可提交的运行结果。打包输出 `../arcbench-agent.zip` 和 SHA-256 文件，ZIP 根目录直接是入口文件。

## 真实本地联调

复制 `env.example` 到官方模拟仓库中的 `.env`，只在本机补上赛事发放的 Key。地址和默认模型已经按[官方课程 Lab02](https://github.com/code-philia/agentic-software-engineering-hackathon/blob/main/Lab/Lab02/README.md#第六步配置模型接口)填写。课程使用小写变量名，本 Agent 和 Runner 使用 `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`MODEL`，不要直接照抄课程的小写名称。不要把真实 Key 放入聊天、代码或 ZIP。

从官方模拟仓库目录执行下列命令。先安装并启动 Docker，再构建镜像。`-Agent` 请填写本项目 ZIP 的实际绝对路径。

```powershell
.\build-image.ps1
.\submit.ps1 `
  -Agent 'C:\Users\celine\Documents\Codex\2026-09-28\wo\outputs\arcbench-agent.zip' `
  -RequirementsDir "$PWD\public-exercise\keep\requirements" `
  -TestsDir "$PWD\public-exercise\keep\tests" `
  -OutputDir "$PWD\runs\practice-001" `
  -EnvFile "$PWD\.env"
```

官方容器会调用入口并部署生成应用。输出目录必须不存在或为空。不要直接在日常使用的 Windows 主机执行真实生成流程：构建会运行模型生成的 npm 脚本，文件工具的路径检查不是操作系统沙箱。实际运行依赖 Runner 的文件/网络隔离。

当前下载的官方仓库版本为 `4e62690ef0af48601150f248e1f993a300533357`，实际公开练习为 `keep` 和 `bookstack`；其 README 中旧的 `public-exercise/requirements` 路径不存在，上述命令已按实际目录修正。

本机快捷入口（Docker 安装启动后，在本 Agent 目录执行）：

```powershell
.\run_local.ps1 -Task public -BuildImage
.\run_local.ps1 -Task github
.\run_local.ps1 -Task sheet
```

先检查公开练习结果，再运行两题。后两条仅执行真实生成和部署，因为没有官方隐藏测试；不可把“部署成功”记为赛题通过。脚本为每次运行创建新的输出目录。`-PrepareOnly` 不启动 Docker、不调用模型。

## 预算和验收边界

默认每任务最多 100 次模型请求、累计报告 token 到 800000 后停止继续请求、3 小时运行；单回复最多 12000 tokens。总 token 检查在请求间进行，最后一个请求可能超过累计阈值。它不是人民币硬限额；费率、缓存、平台计费以 Meter 为准。未拿到价格前不能据此推算会花多少元。失败请求不自动重试，以免在已计费的超时响应上反复花费。

目前使用标准兼容接口的非流式文本 JSON 回复。默认配置采用官方课程提供的 deepseek-v4-flash；仍需首次实测确认账号权限、最大输入上下文和输出参数。每个模块保留完整公开需求以防漏约束，大题会重复输入较多文本，后续应根据真实用量优化。

本地检查包括前端构建、backend npm test、启动后首页 HTTP 200。npm test 由本轮模型编写，不是独立的官方测试；首页就绪也不代表交互正确。真正的公开 Playwright 验证交给官方模拟 Runner。当前未接入参考图视觉模型，也未验证长任务恢复、复杂浏览器交互或真实生成质量。

## 规则提醒

依据用户提供的《参赛须知(2).pdf》四页及后续群公告；截止时间以用户提供的最新群公告更新：

- 初赛提交截止时间更新为 **北京时间 2026 年 10 月 1 日 23:59**（用户提供的最新群公告，覆盖旧 PDF 的 9 月 30 日日期）。PDF 说明截止时已在运行的任务继续至完成或超时。网站活动页另显示更宽日期，不应当作初赛提交截止。
- 每次正式提交同时跑两题，汇总通过率和费用计分；同队不能同时发起两次正式评测；取历史最高分。
- 练习券为 100 元 × 5 次，正式比赛券另有 500 元（规则说明均为暂定保底）；个人 Key 的练习提交成绩不计入最终排名。
- 前 20 队晋级；单任务最长 48 小时。当前 Agent 自设更短的 3 小时限制，可按实测调整。
- 通用脚手架允许，预置本题页面/业务逻辑/组件不允许；必须实际用模型完成需求，不能以象征性调用包装预制代码。
- 只能使用允许的软件源、模型/Meter 网络服务；不获取、推测或绕过隐藏测试。测试以公开需求及场景为依据。

计分：令 p 为两题合计通过数 / 合计测试数 × 100，b 为两题总费用。p=0 时得分0；p>0 且 b>0 时，得分为 p / (b/(1.2p))^a，费用不超过1.2p时 a=0.1，超过时 a=0.2。p>0 且 b=0 的除零边界没有在 PDF 中解释，不应擅自当作可得无限分。优先提高真实需求覆盖，再优化单位费用。
