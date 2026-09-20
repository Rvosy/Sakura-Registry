# 当前能力与第一阶段差异

2026-09-20 检查的 Sakura 工作区基线是 `25334813ce4d3ad11eb2bdd26be2c5c02619d994`，另有上一任务留下的市场界面改动。远端 main 当时为 `ec41d39af0c78d7b2e183c8b3c6d91146b9d5891`。本阶段安装验证针对本地工作区，不将其写成远端 main 验证。

## 已确认能力

| Sakura 入口 | 当前行为 |
|---|---|
| `app/plugins/installer.py` | 本地 ZIP/目录安装，路径与体积约束，安装后默认未启用，重复 ID 拒绝 |
| `app/plugins/discovery.py` | 解析 Plugin API v4、入口及服务声明 |
| `app/plugins/dependencies.py` | 单独处理 requirements/pyproject 依赖；源码固定不等于依赖已锁定 |
| `app/storage/runtime_roots.py` | distribution_root 与 user_root 分离，可在临时根验收 |
| `tools/release/package_optional_plugin.py` | 本地目录打包，不负责 Registry 固定源码或版本治理 |
| `desktop/frontend/settings/plugin-marketplace-runtime.js` | 前端数据源适配接口；不是网络协议或完整兼容选择器 |

样板采用独立插件 [Sakura-Spine 0.2.6](https://github.com/Rvosy/Sakura-Spine/tree/6f17c62310c5a7fdd60c7aab82391572db2d9031)。它是项目作者维护的真实插件，不是来自外部贡献者的首次投稿。无 Python 依赖声明，可直接验证安装而不启动插件。根 LICENSE、NOTICE 和 `vendor/SPINE-LICENSE` 随包保留；vendor 的 Spine 运行时不适用根 MIT 许可证。

## 对架构草案的调整

原讨论文档中的反向域名 ID、最低 Sakura 版本和包摘要不能直接当作现有契约。当前 ID 兼容下划线，manifest 使用 API v4；本阶段不引入自定义内容摘要。完整 Git commit 是 Git 协议要求的引用，不生成另一份内容摘要。

目录计划直接通过下载域名静态分发。没有新增 FastAPI、数据库、账号、投稿凭据或云厂商 SDK。首轮只构建预览，`example.invalid` 不是真实服务地址。

作者通过 Issue 表单投稿，Actions 自动解析版本、固定 commit、试打包并回贴结果。维护者批准具体检查后生成收录 PR，也支持重新检查、拒绝、新版本、撤回和恢复。生产 `plugins.json` 仍需通过 PR 审核合并；样板独立放在 `examples/`。

## 验证范围

单元测试覆盖打包保留与排除、禁止执行上游代码的构建路径、路径穿越、Unicode/大小写冲突、链接、嵌套 manifest、体积约束、源码 ID 与版本匹配、版本历史保护和失败时不生成 Catalog。

`tools/verify_install.py` 使用已有 `LocalPluginInstaller` 和 `PluginDiscovery`，每个包使用全新临时根，检查 ID、版本、未启用状态。重复安装属于 Sakura 安装器已有测试的范围，不在 Registry 探针中重复验证。脚本拒绝带 Python 依赖声明的包，避免将依赖构建执行混入首轮验收。

安装成功不代表 Spine 渲染、角色资源、宿主服务或所有平台运行正常。GitHub CI 执行 Windows/Linux 单元测试与线上固定源码构建；当前没有在 CI 安装完整 Sakura。真实 Windows 安装器的本地结果单独记录，不代替 CI 平台验证。

2026-09-20 本地验证结果：14 项测试通过；在线下载固定 commit 后生成样板 ZIP，真实安装器验证通过，插件 `sakura.visual.spine` 版本为 `0.2.6`，安装后未启用，重复安装返回 `PLUGIN_ID_CONFLICT`。安装验证使用临时目录，未加载插件代码或读写真实用户配置。

开发过程中，路径回归测试首次暴露 Windows `ZipInfo` 会将反斜杠转换成斜杠的问题。打包器已增加 `orig_filename` 与规范化文件名的检查，回归用例保留原始 ZIP 文件名；修复后通过。测试入口首次使用 bundled Runtime 时缺少新仓库搜索路径，已通过显式加入当前目录解决，未修改 Runtime 配置。

尚未实现多吉云上传、生产不可覆盖对象、客户端缓存下载、来源持久化、兼容解析、更新回滚或角色 Hub。

## GitHub 投稿流程验收

2026-09-20 使用 [投稿 Issue #1](https://github.com/Rvosy/Sakura-Registry/issues/1) 验证自动检查、回贴、维护者审批与 `/recheck`。[自动生成的 PR #2](https://github.com/Rvosy/Sakura-Registry/pull/2) 只修改 `plugins.json`，保持未合并。其自动分支校验 [35500815024](https://github.com/Rvosy/Sakura-Registry/actions/runs/35500815024) 通过；下载该次 CI 的正式目录产物后，Windows Sakura 安装器验证 Spine 0.2.6 安装成功且未启用。

普通 PR 工作流 [35500815902](https://github.com/Rvosy/Sakura-Registry/actions/runs/35500815902) 首次状态为 `action_required`，提交为 `4245dd2ded898b3968a066870986f534776e2437`，attempt 1，job 数为 0。原因已由 GitHub 官方触发规则确认：`GITHUB_TOKEN` 创建的 PR 要求维护者批准工作流。批准执行一次后，Windows/Linux 校验及样板构建通过；不是测试失败后重跑。本仓库保留平台审批，自动分支校验通过 workflow_dispatch 独立运行。

撤回、恢复、权限限制、过期检查、Issue 编辑后拒绝旧审批、重复审批和拒绝投稿关闭相关 PR 均有本地回归覆盖。本次未实际合并收录 PR，也未启用 CDN；合并后的自动关闭由 GitHub 的 `Closes` 关联处理，main 构建沿用已有工作流。

## 索引精简

索引现在仅保存 ID、仓库、版本到 commit 的映射，撤回时才添加原因。完整 manifest 由构建时读取源码生成，不再重复存入索引。当前正式索引尚无已合并插件，无需迁移已发布数据；格式调整前的检查产物请通过 `/recheck` 重新生成。

精简后本地 29 项测试通过；从相同固定源码构建 Spine 0.2.6 后，真实 Windows 安装器验证安装成功且未启用。

## GitHub 镜像分发

2026-09-20 增加 GitHub Releases 发布工作流，复用已有 ZIP 构建，不新增客户端源码打包器或服务端。Sakura 工作区接入两个镜像和官方源、下载源配置、目录读取、安装及停用插件更新。GitHub 主分支当前仍是空索引，Spine 收录 PR 保持待审核，因此首次发布的是空目录。
