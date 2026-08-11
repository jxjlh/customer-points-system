# Crayotter 原生 Streamlit 集成设计

## 目标

把现有不可用的 Crayotter iframe 板块重构为原生 Streamlit 工作台，在不暴露额外公网端口的情况下完成素材上传、AI 剪辑任务创建、任务进度查看、任务控制、成片预览与下载，并允许管理员在页面中随时更换模型 API。

## 已确认问题

1. 旧页面把工作台 iframe 指向 `http://127.0.0.1:18765/ui/`。浏览器无法通过该回环地址访问云端容器中的 Crayotter 服务。
2. 根目录 `requirements.txt` 没有安装 Crayotter 运行依赖，导致部署环境缺少模型、视频处理和下载组件。
3. Python 3.13 已移除标准库 `cgi`，旧上传接口在未安装兼容包时无法导入。
4. API 配置直接围绕本地 `.env` 展开，缺少面向用户的安全保存和状态反馈。

## 采用方案

### 架构

- Streamlit 继续作为唯一公开 Web 服务和用户入口。
- Crayotter 后端作为同一容器内的本地子进程，仅监听 `127.0.0.1`。
- Streamlit 服务器通过 HTTP 调用本地 Crayotter API；浏览器不直接访问 Crayotter 端口。
- 原生 Streamlit 页面替代 iframe，并围绕 Crayotter 的现有 `/config`、`/uploads`、`/jobs`、`/events`、`/artifacts` 和 `/files` 接口构建。

### 页面结构

1. **创建任务**：填写剪辑要求、上传本地视频、设置目标时长和处理模式，然后创建 Agent 任务。
2. **任务中心**：显示历史任务、状态、阶段、错误信息、取消/恢复操作和手动刷新。
3. **成片与日志**：展示任务产物，视频可直接预览，其他文件可以下载；事件以时间线表格显示。
4. **API 配置**：支持主模型、视频理解模型和 TTS 模型的 API Key、Base URL 与模型名称；密码输入留空表示保留原值。
5. **运行诊断**：展示后端健康、FFmpeg、依赖状态和最近日志，但不显示 API Key 明文。

## 配置与安全

- API 配置由 Streamlit 服务端提交给本地 `/config`，不在浏览器中暴露后端地址。
- API Key 输入框默认留空；保存时只有明确输入的新值才覆盖旧值。
- 工作台只展示“已配置/未配置”，不回显完整密钥。
- Crayotter 后端继续使用 `crayotter_runtime/.env` 保存运行配置；云端重启可能清空运行盘，因此同时允许使用 Streamlit Secrets/环境变量作为初始默认值。
- 后端监听地址固定为 `127.0.0.1`，页面不允许改成公网地址。

## 部署依赖

- 根依赖文件包含 Crayotter 的部署依赖。
- `packages.txt` 安装系统 FFmpeg。
- Python 3.13 环境安装 `legacy-cgi`，保证现有 multipart 上传路径可运行。
- 启动后端失败时，页面显示可操作的诊断信息，而不是空白 iframe。

## 验收标准

1. 导入 `modules.video_editor` 不依赖浏览器访问本地端口。
2. 页面源代码中不再包含 Crayotter iframe。
3. 后端能在 Python 3.13 下导入并通过 `/health`。
4. API 配置可更新，并且空密码输入不会清除已有 Key。
5. 可保存上传文件、创建任务、查看任务详情与事件、取消或恢复任务。
6. 完成任务的 MP4/MOV/WebM 可预览并下载。
7. 单元测试、Crayotter 后端测试和 Python 编译检查通过。

