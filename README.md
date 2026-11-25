# AutoDL Keeper

AutoDL 实例保活工具。Edge 弹窗查看实例状态、磁盘健康和预计释放时间，
也可手动执行无卡开关机。自动保活可由 Windows 本机服务或 GitHub Actions 执行。

## 一、在 Edge 安装

需要 Windows、Microsoft Edge 和 Python 3.12。下载或克隆项目，解压后保留整个目录。

在项目根目录打开 PowerShell，首次安装时运行：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

启动本机服务：

```powershell
.\.venv\Scripts\python.exe keeper_web.py
```

1. 在 Edge 打开 `edge://extensions/`，开启「开发人员模式」。
2. 选择「加载解压缩的扩展」，选中项目里的 `edge_extension` 文件夹。
3. 点击工具栏的 **AutoDL Keeper** 图标，打开左下角「设置」。
4. 在 AutoDL 网页登录后，打开开发人员工具的「网络」面板，刷新实例列表。
   选中发送给 `www.autodl.com` 的实例列表请求，在「请求标头」中复制
   `authorization` 的值，填入扩展并点击「保存设置」。

令牌使用当前 Windows 用户的 DPAPI 加密保存在本机，过期后从设置中更新。
扩展只连接本机 `127.0.0.1:8765`。如果显示「无法连接本机服务」，先检查
上面的 Python 命令是否仍在运行。更新项目后，重启本机服务，并在 Edge 扩展管理页
点击「重新加载」。

## 二、选择自动保活方式

### GitHub Actions

适合电脑常关机、希望任务在云端运行的用户。可使用 GitHub Actions 免费额度。
AutoDL 无卡开机按平台规则计费。

1. 把项目复制到你有写权限的 GitHub 仓库，并确认默认分支包含
   `.github/workflows/AutoDL-Keeper.yml`。
2. 在仓库进入 **Settings → Secrets and variables → Actions → New repository secret**。
   名称填 `AUTHORIZATION`，值填 AutoDL 网页令牌。令牌过期后也在这里更新。
3. 打开 **Actions → AutoDL Keeper → Run workflow**，首次保留「仅检查实例和保活条件」勾选。
   日志应显示查到的实例数和符合保活条件的实例数。
4. 云端检查成功后，在 Edge 弹窗的「设置」中取消勾选「启用本机自动保活」并保存。
   Edge 仍可查询实例和手动运行；云端执行历史在 GitHub Actions 查看。

工作流每 6 小时检查一次。已关机的实例连续关机满 8 天，或距预计释放不超过 72 小时，
就逐台无卡开机，确认运行后关机。GitHub 的定时触发可能延迟；公开仓库持续 60 天无活动
时，GitHub 可能停用定时工作流。详见 [GitHub 定时工作流文档](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

### Windows 本机

在扩展设置中勾选「启用本机自动保活」并保存。弹窗会显示下次本机保活的倒计时。
本机服务每 8 天批量处理一次已关机的实例，并每 15 分钟检查是否有实例距预计释放
只剩 72 小时。关闭 Edge 不影响本机服务。电脑关机时无法执行，服务恢复后会补跑错过
的批次。

如需 Windows 登录后自动启动本机服务，在项目根目录运行：

```powershell
.\enable_keeper_startup.ps1
```

该命令注册名为 `AutoDL Keeper` 的 Windows 计划任务。

## 三、健康提示与执行记录

- 距预计释放或 API 返回的租期、主机下架时间不超过 72 小时的实例会标红。
  租期与主机下架期限无法通过开关机延长。
- 批次按顺序处理已关机的实例，确认一台恢复关机后才处理下一台。
- 本机日志在执行时自动展开，结束后可手动打开「执行日志」查看。
- 「清除令牌」只清除本机设置。云端令牌由 GitHub Actions Secret 单独管理。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `edge_extension/` | 可加载的 Manifest V3 Edge 扩展 |
| `keeper_web.py`、`keeper_schedule.py` | Windows 本地 API、加密凭据与调度 |
| `autodl/`、`keeper_plugin.py` | AutoDL 接口、分页、实例健康和逐台电源操作 |
| `keeper_actions.py`、`.github/workflows/AutoDL-Keeper.yml` | 云端保活入口和工作流 |

项目地址 [austinbf/autodl-keeper](https://github.com/austinbf/autodl-keeper)。
