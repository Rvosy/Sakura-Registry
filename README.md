# Sakura Registry

Sakura 插件市场的收录记录、版本校验和分发构建工具。GitHub 保存审核事实，构建工具从固定 commit 生成 ZIP 和静态 Catalog，客户端复用 Sakura 安装器。

当前完成第一阶段：一个真实插件从源仓库到可安装 ZIP 的链路。尚未接入多吉云和客户端网络数据源。

## 当前内容

- `plugins.json`：正式收录记录，目前为空。维护者审核合并具体版本后才加入。
- `examples/spine.json`：`Rvosy/Sakura-Spine` 的 `0.2.6` 样板，固定完整 commit 和 manifest 快照。它不代表生产上架。
- `registry/`：记录校验、历史保护、受限源码下载、安全 ZIP 打包和 Catalog 生成。
- `tools/verify_install.py`：调用 Sakura 的真实安装器，在临时根中验证首次安装、默认未启用和重复安装拒绝。
- GitHub Actions：Windows、Linux 测试，样板构建和可下载的预览产物。工作流没有云发布凭据，也不会执行上游代码。

## 本地运行

使用 Python 3.12 或以上版本，在本仓库根目录执行：

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m registry validate
python -m registry build --registry examples/spine.json --output dist/sample --base-url https://example.invalid
python tools/verify_install.py --sakura-root ../sakura --distribution dist/sample
```

安装验证需使用 Sakura 的 bundled Runtime 或装有 Sakura 依赖的环境。部分 Windows embedded Python 的搜索路径固定到 Sakura；这种情况下用下面的入口显式加入当前仓库路径，不修改 Runtime：

```powershell
D:\Project\sakura\runtime\python.exe -X utf8 -c "import sys,runpy; sys.path.insert(0,'.'); runpy.run_module('registry',run_name='__main__')" build --registry examples/spine.json --output dist/sample --base-url https://example.invalid
D:\Project\sakura\runtime\python.exe -X utf8 -c "import sys,runpy; sys.path.insert(0,'.'); runpy.run_module('unittest',run_name='__main__')" discover -s tests -v
D:\Project\sakura\runtime\python.exe -X utf8 tools/verify_install.py --sakura-root D:\Project\sakura --distribution dist/sample
```

输出目录必须不存在；再次构建换一个目录。失败时可能留下部分 ZIP，但不会生成 Catalog，不能把失败目录发布出去。`example.invalid` 是保留的无效域名，预览产物不提供线上下载服务。

实际发布时指定下载站的 HTTPS 根地址。产物结构：

```text
catalog/v1/catalog.json
plugins/<id>/<version>/<完整 commit>/plugin.zip
```

## 收录与版本管理

目前通过 PR 修改 `plugins.json`。每个版本包含完整 commit、原始 manifest 的结构化快照、更新说明和撤回状态。新版本需要新的审核，不能只审核仓库地址后自动上架后续提交。

CI 对比 PR 目标提交或 push 前的记录，拒绝删除历史、修改旧版本 commit、快照、说明或源仓库。已有版本只允许调整 `yanked` 和 `yank_reason`。撤回版本保留记录，不再生成安装目标。

维护者需检查具体源码和依赖；结构校验不能证明插件安全。`CODEOWNERS` 提供审阅归属，强制审核需要另行启用 GitHub 分支保护。首轮不自动处理 Issue 评论中的 `/approve`。

源码只从 GitHub codeload 的完整 commit 地址读取。构建保留运行资源和许可证，不执行 `setup.py`、npm scripts 或插件代码，不安装插件依赖。嵌套插件、符号链接、特殊文件、路径冲突、越界路径和超限包会被拒绝。秘密文件的按名排除不等于全面的秘密扫描。

本项目不新增自定义包摘要。Git commit 是 Git 协议中的源码引用；它与 HTTPS、不可覆盖的发布路径、包大小和 manifest 匹配一起记录来源，并不替代发布者签名。CDN 上传的禁止覆盖约束需在分发阶段落实。

## 后续顺序

1. GitHub 投稿与维护者逐版本审核，审核结果写入 PR。
2. 多吉云上传：先上传不可覆盖的包，全部成功后切换 Catalog，配置流量控制和告警。
3. Sakura 接入 Catalog、有效缓存、兼容选择、下载和首次安装，记录来源。
4. 独立实现更新事务和失败回退。

契约见 [Registry v1](docs/registry-v1.md)，实现依据和验证边界见 [现状与差异](docs/current-state.md)。
