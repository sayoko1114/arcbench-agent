# 团队开发交接文档

更新：2026-09-29。适用对象：队友及其 Codex。第一目标是跑通真实生成与官方模拟评测，再根据公开需求改进通用 Agent。不是继续手写两个赛题应用然后上传。

## 1. 当前进度和最重要的边界

| 项目 | 已做 | 未做 |
|---|---|---|
| 规则 | 阅读 PDF、课程 Lab02、官方模拟仓库；按新群公告更新截止时间 | 主办方正式合规审核 |
| 需求 | 原始两题保留；GitHub 47、Sheet 24 个原子需求，各100个声明场景 | 两题由当前 Agent 真实生成 |
| Agent | 统一入口、模型规划、模块代码生成、读回/精确替换、构建检查、有限修复、证据记录 | 大任务实际覆盖率、上下文优化、稳定恢复 |
| 测试 | 11 项离线单元测试通过；模型小请求真实成功，124 tokens | 官方 Runner 内构建和公开 Playwright |
| 模拟器 | 官方仓库已克隆；公开练习和两题的 prepare-only 工作区组装成功 | Docker 镜像构建、容器运行 |
| 提交 | Agent ZIP 已打包检查 | 任何正式提交或正式得分 |

截至本记录，不能说“两题已经完成”，也不能把 prepare-only 当运行通过。小请求的金额尚未从 Meter 核对。

旧 `arcbench-v0` 是手写的本地演示，已标记禁止提交。它的代码、测试结果不能作为本 Agent 生成能力或比赛得分的证据。不要把该应用作为模板、few-shot 代码或运行时答案来源。

## 2. 官方资料与已确认配置

- 赛事：https://create.gosim.org/factory26/
- 比赛平台：https://arc-bench.com/
- 课程：https://github.com/code-philia/agentic-software-engineering-hackathon
- 模拟环境：https://github.com/code-philia/hackathon-local-simulation
- 用量：https://meter.arc-bench.com/user
- 课程 Lab02 给出的 Base URL：`https://api.arc-bench.com/v1`，默认模型：`deepseek-v4-flash`。
- 本项目变量名：`OPENAI_API_KEY`、`OPENAI_BASE_URL`、`MODEL`。课程小写名称不能直接用于本入口。
- 截止：**北京时间 2026-10-01 23:59**，依据队友在本对话提供的最新群公告；旧 PDF 写9月30日，已被新公告更新。

队长 shallyxie 有练习 Key，成员账号没有不影响协作。正式提交由队长操作，平台使用独立比赛 Key；练习与正式额度分开。每次正式提交跑两题，同队不能同时跑两次，取历史最高分。

## 3. 目录和职责

| 文件 | 职责 |
|---|---|
| main.py | 通用模型协议、文件工具、阶段控制、验证、CLI |
| requirements.txt | Agent Python 依赖，目前仅标准库 |
| package_agent.py | 正式候选 ZIP 白名单，目前仅 main.py 和 requirements.txt |
| run_local.ps1 | Windows 下调用官方模拟器；支持 public/github/sheet |
| check_connection.py | 单次小型真实请求，验证配置，可能产生少量费用 |
| env.example | 无密钥的配置模板 |
| .env | 本机真实配置，不分享、不上传、不提交 Git |
| tests/test_agent.py | Agent 本身的离线测试，不是赛题验收 |
| AGENTS.md | Codex 接手约束 |
| VERIFICATION.md | 实际验证结果与未验证范围 |

当前电脑的 Agent 目录为 `C:\Users\celine\Documents\Codex\2026-09-28\wo\outputs\arcbench-agent`；模拟器在同项目的 `work\hackathon-local-simulation`；运行产物在 `work\runs`。队友不必复制这个绝对目录，使用下文参数传入自己的路径。

## 4. 队友从零开始

1. 解压团队开发包，或者由团队维护者把其中无密钥的开发文件提交到自建 Git 仓库。当前没有为团队创建/推送远程仓库。
2. 安装 Python 3.10+、Git、Docker Desktop（Linux containers / WSL 2），启动 Docker。`docker info --format '{{.OSType}}'` 应返回 linux。需要重启时先重启。
3. 克隆主办方模拟仓库（这是工具，不是参赛应用答案）：

```powershell
git clone https://github.com/code-philia/hackathon-local-simulation.git D:\arc-simulation
```

4. 在 Agent 文件夹将 `env.example` 复制为 `.env`，在本机填写 Key。不要把 env.example 改成带密钥的版本后提交给队友。
5. 在 Agent 文件夹运行：

```powershell
python -m unittest discover -s tests -v
python package_agent.py
.\run_local.ps1 -Task public -SimulationDir D:\arc-simulation -RunsDir D:\arc-runs -PrepareOnly
.\run_local.ps1 -Task public -SimulationDir D:\arc-simulation -RunsDir D:\arc-runs -BuildImage
```

第二条实际生成参赛 ZIP；prepare-only 只检查工作区；最后一条才构建镜像并真实调用模型、部署和执行公开测试，会产生练习费用。Windows 如果阻止执行脚本，可仅为当前 PowerShell 窗口设置 `Set-ExecutionPolicy -Scope Process Bypass` 后再运行。

下载版本 `4e62690ef0af48601150f248e1f993a300533357` 的公开练习是 keep/bookstack，并不存在其旧 README 写的 public-exercise/requirements。脚本选择 keep，不使用该目录下的示例应用答案。若上游更新目录，需要先核对再调整路径。

6. 公开练习结果可用后，分别运行两题：

```powershell
.\run_local.ps1 -Task github -SimulationDir D:\arc-simulation -RequirementsDir D:\arcbench-hackathon-requirements\hackathon--github -RunsDir D:\arc-runs
.\run_local.ps1 -Task sheet -SimulationDir D:\arc-simulation -RequirementsDir D:\arcbench-hackathon-requirements\hackathon--sheet -RunsDir D:\arc-runs
```

两个正式题未提供隐藏测试，这两条只能得到生成和部署结果。不要将缺少评测的 skipped 状态记作通过。可以另写基于公开需求的独立测试，但必须标明自建，不能猜测或获取隐藏用例。

## 5. Agent 执行链和输出契约

官方调用：`python3 main.py REQUIREMENTS_DIR --output-dir OUTPUT_DIR`。

1. 检查 requirements.yaml，拒绝复用已经存在的应用目录。
2. 调用模型规划1到10个模块及共同架构。
3. 各模块使用独立会话，模型按 JSON 动作写文件、读回、精确替换、请求检查。
4. 最后进行全需求复核；执行前端安装/构建、后端安装/npm test、端口3000启动和首页HTTP检查。
5. 失败最多追加两轮修复，仍失败则非零退出。证据保存在产物 `.agent-evidence`。
6. Agent 退出后，官方 Runner 再执行部署和独立公开 Playwright 测试。

产物必须有 frontend/package.json 的 build 脚本及 backend/package.json 的 start 脚本，后端监听 HOST=0.0.0.0 PORT=3000 并提供前端页面。不要依赖本地特有 deploy.sh 分支。

当前模型生成的 npm test 与实现来自同一 Agent，只是内部自检；不能替代独立验收。文件工具限制相对路径，但 npm 运行的是任意生成代码，真正隔离由官方 Linux 容器提供；不要直接在宿主机运行真实生成流程。

## 6. 建议三人分工

| 负责人 | 工作 | 建议改动范围 | 完成标准 |
|---|---|---|---|
| A：入口与模型 | 真实联调、模型输出截断/格式恢复、上下文与成本控制 | main.py 的 Model/phase，未来可拆模块 | 接口证据、错误测试、用量记录 |
| B：验证质量 | 通用验证框架、公开需求导出的独立行为测试、失败诊断 | tests/、验证模块、报告 | 公共练习实际 Playwright 结果，不改官方测试 |
| C：工程与提交 | Docker、官方 Runner、打包隔离、队长提交准备 | run_local.ps1、package_agent.py、文档 | ZIP白名单、容器部署日志、可复现指令 |

main.py 目前职责集中，首次拆分由A统一做；B先以独立测试或验证模块开发，避免多人同时覆盖同一段代码。新增运行时模块时同步 ZIP 白名单与打包测试。采用短分支、小提交，合并前跑相关测试并更新验证记录。

## 7. 下一轮优先级

P0：解决 Docker 安装/启动，跑一次官方公共练习端到端；记录原始报告，不承诺高通过率。

P1：根据真实失败修复生成流程。当前每轮携带完整 YAML，大题输入29万/20万字节，可能昂贵或超过模型上下文。应通用地解析需求树、保留父级约束与依赖、按模块筛选输入，并用完整覆盖表防止漏项；不要改成按题名硬编码提示或代码。

P1：完善验证。HTTP首页200只能证明启动；需要针对可访问性、持久化和真实用户行为的公开需求测试。模型对自己测试的修复不能悄悄删除断言，变更应记录。

P2：更好的调用失败恢复、输出截断恢复、检查点恢复、按实际费率做预算预估和停止。当前 token 阈值在请求间检查，最后一次可能越界，不是人民币硬预算；缺少 usage 会停止，不自动重试已可能计费的超时请求。

默认上限是每题100次调用、80万报告 tokens、3小时，尚未经过长任务调优。不要把它当作两题能完成的保证。先量小再放大。

## 8. 可以直接发给队友 Codex 的接手提示

> 请先阅读 AGENTS.md、DEVELOPMENT.md、README.md 和 VERIFICATION.md，检查当前工作区及未提交修改。我们开发通用参赛 Agent，禁止内嵌或复制具体赛题的预制实现。先检查 Docker Linux engine、官方模拟器路径和 .env 是否配置，只报告配置是否存在，绝不打印密钥。当前已通过11项离线测试、一次124 tokens的真实接口检查和prepare-only；尚无官方Runner完整运行或赛题成绩。先跑公开练习，按实际日志修复；不要直接在宿主机执行生成的npm应用。改动应通用、可验证，补相应测试和证据。不要自动正式提交或推送远程仓库。完成后报告改了什么、真实运行结果、花费记录和仍未验证的部分。

分工时在上述提示末尾追加负责人A/B/C的具体范围，避免三个人同时做全工程。

## 9. Git、下载和分享

- 官方 GitHub 仓库可以 git clone；比赛网站的下载按钮用于需求、智能体运行产物等，具体以页面开放项为准。
- 尚未确认比赛网站支持“填写 Git URL 直接提交”。当前已确认的是上传 Agent ZIP，根目录包含 main.py、requirements.txt。
- `arcbench-agent.zip` 是候选提交包，不是完整开发仓库；`arcbench-agent-team.zip` 才是给队友的无密钥开发包。
- 分享前运行 package_team.py。它也使用白名单，不包含.env、模拟器、安装包、运行产物、旧应用或需求答案。
- 正式提交前必须至少完成真实公共练习和两题生成/部署，并由队长核对余额、当前无运行中的正式提交及截止时间。
