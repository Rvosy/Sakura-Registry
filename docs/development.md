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

这是个人维护的项目，以当前需要为准，保持实现简单。检查放在真正消费数据的边界：Registry 校验收录字段、源码与快照的一致性，以及安装包所需的路径、文件类型和大小；宿主完整的 manifest 与运行兼容性由 Sakura 负责。已排除的文件不再做安装包检查。

使用标准 JSON 和 `yaml.safe_load`，不另造解析规则。不按扩展名猜测资源是否敏感，不增加自定义摘要、自动重试或自愈流程。保留固定源码引用和安装路径安全；版本说明等可编辑资料不作为不可变源码的一部分。

字段定义见 [Registry v1](registry-v1.md)，Sakura 侧的已有能力见 [现状与差异](current-state.md)。
