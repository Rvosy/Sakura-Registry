# 开发与构建 Registry

本页面向修改 Registry 工具的贡献者。提交插件请阅读 [投稿指南](../CONTRIBUTING.md)。

## 本地检查

使用 Python 3.12 或以上版本，在仓库根目录执行：

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python -m registry validate
```

`registry/` 负责记录校验、下载、打包和 Catalog 生成，`tests/` 验证这些行为。`tools/check_history.py` 供 CI 对比变更前的版本记录。

## 处理投稿 Issue

作者打开、编辑或重新打开投稿 Issue 时，`submission.yml` 自动解析版本并试打包，回贴结果和预览包。留空版本先取最新正式 Release，没有 Release 则使用默认分支；实际收录记录始终固定完整 commit。

| Issue 评论 | 操作 |
|---|---|
| `/recheck` | 作者或维护者重新检查当前投稿 |
| `/approve 检查编号` | 维护者批准机器人回贴的检查结果，随后自动校验、合并并发布 |
| `/reject 原因` | 维护者关闭投稿及其尚未合并的自动收录 PR |

审批使用仓库的 write、maintain 或 admin 权限，读取对应成功检查的 artifact。Issue 正文变更后需要重新检查。每个检查编号对应独立分支，重跑时复用同一个收录 PR。同一 Issue 已有另一个未关闭的收录 PR 时，先处理或关闭它，再审批新的检查。

审批流程调用 `validate.yml` 校验收录 PR 的固定提交，合并前再确认 Issue 正文和 PR 提交。通过后自动 squash 合并，并调用 `publish.yml` 发布 main 中的目录。只有发布成功才回贴发布链接并关闭投稿。

审批流程直接调用校验和发布工作流。PR 页面可能显示 GitHub 自带的工作流审批按钮，收录流程会使用审批运行里的校验结果和发布结果。参见 [GitHub 工作流触发规则](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow)。

失败后按 Issue 里的运行链接查看原因，修正后可选择 “Re-run failed jobs”。如果发布前 main 的收录记录已变更，选择 “Re-run all jobs” 重新构建当前目录，已合并的收录 PR 会被复用。

新版本追加到 `versions`；撤回和恢复通过版本变更表单，沿用检查、审批、PR 流程。资料更正和仓库迁移由维护者手动处理。相互冲突的收录 PR 按普通 Git 冲突处理，不增加自动重试或重写分支机制。

仓库需开启 Actions 的 “Allow GitHub Actions to create and approve pull requests”，并允许 Actions 使用仓库令牌合并通过校验的收录 PR。源码校验和构建只使用读权限，创建 PR、合并、发布和回贴分别由对应任务申请写权限。

代码落点：`registry/submissions.py` 处理 GitHub 数据和候选记录，`tools/submission.py` 是工作流入口。检查 artifact 保留 30 天，过期直接重新检查。基础设施故障保留失败日志，查明原因后再手动恢复，不自动重试测试到成功。

## 构建目录

构建正式收录记录：

```sh
python -m registry build --output dist/registry --base-url https://example.invalid
```

运行现成的 Spine 样板：

```sh
python -m registry build --registry examples/spine.json --output dist/sample --base-url https://example.invalid
```

输出目录需尚不存在，再次构建可指定新目录。构建失败会报错，可能留下已生成的 ZIP；仅全部成功后才生成 Catalog。`example.invalid` 用于本地预览，正式分发时替换成下载站 HTTPS 根地址。

产物结构：

```text
catalog/v1/catalog.json
plugins/<id>/<version>/<完整 commit>/plugin.zip
```

GitHub Actions 在 Windows、Linux 上运行单元测试，再构建正式目录和 Spine 样板。成功后的 `registry-preview` artifact 可从对应 Actions run 下载，目前不会自动发布到 CDN。

## 验证安装

使用 Sakura 的 bundled Runtime 或装有 Sakura 依赖的环境执行：

```sh
python tools/verify_install.py --sakura-root ../sakura --distribution dist/sample
```

脚本调用现有 `LocalPluginInstaller`，在临时根中检查 ID、版本和安装后未启用状态。当前探针针对无 Python 依赖的样板；需要依赖的插件请在自己的开发环境中安装验证。脚本不会启动插件。

部分 Windows embedded Runtime 的搜索路径固定到 Sakura。使用该 Runtime 运行 Registry 模块时，可显式加入当前仓库，不修改 Runtime 配置：

```powershell
..\sakura\runtime\python.exe -X utf8 -c "import sys,runpy; sys.path.insert(0,'.'); runpy.run_module('registry',run_name='__main__')" validate
..\sakura\runtime\python.exe -X utf8 -c "import sys,runpy; sys.path.insert(0,'.'); runpy.run_module('unittest',run_name='__main__')" discover -s tests -v
```

## 修改原则

这是个人维护的项目，以当前需要为准，保持实现简单。检查放在真正消费数据的边界：Registry 校验收录字段、源码与索引中的 ID、版本是否一致，以及安装包所需的路径、文件类型和大小；宿主完整的 manifest 与运行兼容性由 Sakura 负责。已排除的文件不再做安装包检查。

使用标准 JSON 和 `yaml.safe_load`，不另造解析规则。不按扩展名猜测资源是否敏感，不增加自定义摘要、自动重试或自愈流程。保留固定源码引用和安装路径安全；补充说明留在投稿 Issue，索引仅保存来源、版本引用和必要的撤回记录。

字段定义见 [Registry v1](registry-v1.md)，Sakura 侧的已有能力见 [现状与差异](current-state.md)。

## GitHub 分发

`publish.yml` 在 main 的 `plugins.json` 改变时运行，也支持手动启动。首次建立目录入口时可手动运行一次；空索引会发布空目录，不会收录 `examples/` 中的插件。

读权限任务测试并构建已收录插件，写权限任务使用 `tools/release_assets.py` 转成 GitHub 附件布局，再创建草稿 Release、上传全部 ZIP 和 Catalog，最后公开并设为最新。每次发布使用独立 Tag，失败后保留日志和草稿，查明原因后处理，不自动重试到成功。

客户端读取 latest Release 的 `catalog.json`，安装包链接固定到生成它的具体 Release。当前采用 GitHub 镜像回退，不上传到 CDN。
