# AutoDL Server Keeper

这个仓库包含了一个 Python 脚本，它的作用是定期唤醒 [AutoDL](https://www.autodl.com/) 的服务器实例，以避免在不活跃14天后被自动销毁。

## 功能

- 定时触发服务器实例的电源操作，确保服务器不会因长时间不活跃而被销毁。
- 自动登录并发送 HTTP 请求来管理服务器电源状态。
- 日志记录每次操作的状态，便于追踪和调试。

## 使用方法

在开始使用之前，你需要配置几个环境变量。这些环境变量将用于脚本中，以确保你的认证信息安全。

创建一个 `.env` 文件，并填写你的 `AUTHORIZATION` token：

```plaintext
# .env 文件内容
AUTHORIZATION=你的认证token
```

**注意：** 切记不要将 `.env` 文件推送到你的公开仓库。

## 如何使用

1. 克隆此仓库到你的本地或服务器上。
2. 安装必要的依赖：

```bash
pip install -r requirements.txt
```


3. 运行 `main.py` 脚本：

```bash
python main.py
```

4. 脚本会开始按照预设的间隔时间唤醒和关闭指定的服务器实例。

## 配置

- 确保你的 `main.py` 文件中的 `headers` 和 `manage_power` 函数里的参数配置正确。
- 你可以修改调度器 `scheduler` 的时间间隔，来设置唤醒服务器的频率。


## 自动化保活工作流

为了防止 [AutoDL](https://www.autodl.com/) 服务器在不活跃14天后自动销毁，本仓库配置了一个自动化的 GitHub Actions 工作流，该工作流会定时执行一个简单的 Python 脚本来启动服务器。

### 工作流描述

- **名称**: AutoDL Keep Alive
- **触发时间**: 每天北京时间早上4点
- **工作流任务**:
  1. 检出仓库代码
  2. 设置 Python 环境
  3. 安装所需依赖
  4. 执行 `main.py` 中的 `change` 函数，触发服务器的启动和关闭操作

### 安全性说明

为了保护敏感信息，如 `authorization` 令牌，我们不将其直接存储在代码或工作流文件中。相反，我们使用 GitHub 仓库的 Secrets 功能来安全地存储并在工作流中引用这些值。

在创建了这个工作流文件之后，你需要在 GitHub 仓库的 Settings -> Secrets 部分添加名为 AUTHORIZATION 的 secret。这个 secret 应该包含你的授权令牌，它会在工作流运行时被设置为环境变量。

![](https://raw.githubusercontent.com/glwhappen/images/main/img/202311081933806.png)

## 安全和隐私

- 确保你的 `authorization` 令牌安全，不要公开在互联网上。
- 不要在任何地方公开你的个人密钥和敏感数据。

## 贡献

如果你有任何改进建议或功能请求，请创建一个 Issue 或者提交一个 Pull Request。

## 本地复现（Windows PowerShell）

安装依赖后，在仓库目录运行以下命令。提示出现时粘贴 AutoDL 网页请求的
`authorization` 值，输入不会回显。

```powershell
$env:AUTHORIZATION = Read-Host 'AutoDL 网页令牌' -MaskInput
python main.py --list
```

列表会分页读取账号下的全部实例，仅显示实例 UUID 和状态。
指定要保活的实例后，可手动执行一次无卡开机和关机：

```powershell
$env:AUTODL_INSTANCE_UUID = Read-Host '实例 UUID'
$env:RUN_CHANGE_FUNCTION = '1'
python main_scheduler.py
Remove-Item Env:RUN_CHANGE_FUNCTION
```

持续运行 `python main_scheduler.py` 会每 5 分钟检查指定实例。脚本只尝试
启动已关机的实例，接口接受开机请求后等待 60 秒再发送关机请求。
`python main.py --shutdown_all` 会关闭当前查询结果中所有运行中的实例。

## 本地控制面板插件

在仓库目录运行 `..venvScriptspython.exe keeper_web.py`，然后打开
`http://127.0.0.1:8765/`。输入网页登录令牌，查询并勾选已关机的实例，
确认后按列表顺序逐台测试。面板会显示每台机器的无卡运行与关机确认结果。

关闭页面后，正在运行的批次继续在本地服务内执行。请在批次完成后再退出服务。
令牌通过本地表单提交，服务不写入文件。可在 Python 中直接调用
`keeper_plugin.run_sequence(token, uuids, report)` 复用同一批次流程。

## Microsoft Edge 扩展

1. 在仓库目录运行 `..venvScriptspython.exe keeper_web.py`。
2. 打开 Edge 的 `edge://extensions/`，开启「开发人员模式」。
3. 点「加载解压缩的扩展」，选择仓库内的 `edge_extension` 文件夹。
4. 点击工具栏中的 **AutoDL 续航** 图标打开弹窗，从左下角「设置」保存令牌。
   返回首页查看倒计时和实例健康，或勾选实例后手动运行。

扩展只连接本机服务 `127.0.0.1:8765`，网页和扩展共用一套控制台。
首次加载的扩展 ID 应为 `obkehkidojnnmljfckkneckcgicikddm`。
八天一次的 Windows 定时任务需要单独配置。

### 自动保活与实例健康

在 Edge 的扩展管理页重新加载扩展，再打开弹窗。首次在左下角「设置」点击「保存令牌」
后，会用当前 Windows 用户的 DPAPI 加密保存令牌，并安排八天后的首次执行。
更新令牌会沿用原定时间。「停用自动保活」会清除已保存的令牌和计划。

自动批次会重新分页列出账号内实例，按顺序处理已关机的实例。页面关闭后，本机服务仍会
执行计划。电脑休眠或关机期间无法执行，恢复服务后会补跑一次错过的批次。
可运行 `enable_keeper_startup.ps1` 注册当前 Windows 用户登录时启动的任务。
无需保持 Edge 打开。令牌过期后，需要在控制台保存新的令牌。

到期标记综合 API 提供的租期和关机释放估算，取最早时间。剩余三天或已到期的实例
标红。磁盘健康来自 AutoDL 的 `disk_health_status`。

本机服务每 15 分钟检查关机释放时间。剩余 72 小时以内的实例会提前执行无卡开关机，
完成后复查释放时间，八天计划照常。若未确认释放时间延后，最早一小时后重试。
租期到期与主机下架仍显示红色提醒。

## GitHub Actions 云端保活

将本项目的修改放进你自己的私有 GitHub 仓库，并将工作流合并到默认分支。
在仓库的 Settings → Secrets and variables → Actions 中创建 `AUTHORIZATION`，
值为 AutoDL 网页令牌。令牌过期后在这里更新。

在 Actions → AutoDL 续航 → Run workflow 保持「仅检查」勾选，可先验证
GitHub runner 能查询实例。之后定时任务每六小时检查一次，遇到连续关机满八天或
距预计释放不超过 72 小时的实例就逐台无卡开关机。每台的计时基于 AutoDL 返回的
最后关机时间，漏掉一次定时运行后会在下次检查重新判断。

云端结果可在 Actions 日志查看。Edge 弹窗当前显示的是本机计划。
云端验证通过后，可在扩展设置中停用本机自动保活，避免两套任务同时操作实例。
