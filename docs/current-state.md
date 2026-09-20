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

作者通过 Issue 表单投稿，Actions 自动解析版本、生成 manifest 快照、试打包并回贴结果。维护者批准具体检查后生成收录 PR，也支持重新检查、拒绝、新版本、撤回和恢复。生产 `plugins.json` 仍需通过 PR 审核合并；样板独立放在 `examples/`。

## 验证范围

单元测试覆盖打包保留与排除、禁止执行上游代码的构建路径、路径穿越、Unicode/大小写冲突、链接、嵌套 manifest、体积约束、快照匹配、版本历史保护和失败时不生成 Catalog。

`tools/verify_install.py` 使用已有 `LocalPluginInstaller` 和 `PluginDiscovery`，每个包使用全新临时根，检查 ID、版本、未启用状态。重复安装属于 Sakura 安装器已有测试的范围，不在 Registry 探针中重复验证。脚本拒绝带 Python 依赖声明的包，避免将依赖构建执行混入首轮验收。

安装成功不代表 Spine 渲染、角色资源、宿主服务或所有平台运行正常。GitHub CI 执行 Windows/Linux 单元测试与线上固定源码构建；当前没有在 CI 安装完整 Sakura。真实 Windows 安装器的本地结果单独记录，不代替 CI 平台验证。

2026-09-20 本地验证结果：14 项测试通过；在线下载固定 commit 后生成样板 ZIP，真实安装器验证通过，插件 `sakura.visual.spine` 版本为 `0.2.6`，安装后未启用，重复安装返回 `PLUGIN_ID_CONFLICT`。安装验证使用临时目录，未加载插件代码或读写真实用户配置。

开发过程中，路径回归测试首次暴露 Windows `ZipInfo` 会将反斜杠转换成斜杠的问题。打包器已增加 `orig_filename` 与规范化文件名的检查，回归用例保留原始 ZIP 文件名；修复后通过。测试入口首次使用 bundled Runtime 时缺少新仓库搜索路径，已通过显式加入当前目录解决，未修改 Runtime 配置。

尚未实现多吉云上传、生产不可覆盖对象、客户端缓存下载、来源持久化、兼容解析、更新回滚或角色 Hub。
