# 通知系统使用指南

## 1. 概述

通知系统是应用程序中用于向用户提供反馈的核心组件。它基于事件总线架构，提供了统一的接口来发送不同类型的通知，并在 UI 层统一展示。通知系统的主要目标是提供一致、友好的用户反馈体验。

### 1.1 系统架构

```
┌────────────────┐    ┌─────────────┐    ┌─────────────┐
│ 业务服务/组件   │───>│ 通知服务     │───>│  事件总线    │
└────────────────┘    └─────────────┘    └──────┬──────┘
                                                │
                                                ▼
                                         ┌─────────────┐
                                         │   UI 展示    │
                                         └─────────────┘
```

- **通知服务 (NotificationService)**: 提供发送各类通知的统一接口
- **事件总线 (EventBus)**: 提供发布-订阅机制，负责消息传递
- **UI 展示**: 使用 InfoBar 组件展示通知内容

## 2. 通知类型

系统支持四种类型的通知，每种类型有不同的视觉样式和用途：

| 类型 | 方法 | 视觉样式 | 用途 |
|------|------|---------|------|
| 信息 | `info()` | 蓝色 | 中性信息，一般通知 |
| 成功 | `success()` | 绿色 | 操作成功的反馈 |
| 警告 | `warning()` | 黄色 | 需要注意但不影响使用的问题 |
| 错误 | `error()` | 红色 | 错误信息，操作失败 |

## 3. 使用方法

### 3.1 基本用法

通知服务通过依赖注入获取，使用 PySide6 的 Provide 机制：

```python
from core.services.notification_service import NotificationService
from PySide6.QtCore import Slot
from dependency_injector.wiring import inject, Provide

@inject
def __init__(self, notification_service: NotificationService = Provide["notification_service"]):
    super().__init__()
    self.notification_service = notification_service
```

### 3.2 发送通知

发送通知有两种方式：

#### 3.2.1 使用通用方法

直接调用对应类型的通知方法：

```python
# 发送信息通知
self.notification_service.info(title="标题", content="这是一条信息通知")

# 发送成功通知
self.notification_service.success(title="标题", content="操作成功")

# 发送警告通知
self.notification_service.warning(title="标题", content="警告信息")

# 发送错误通知
self.notification_service.error(title="标题", content="发生错误")
```

#### 3.2.2 使用预定义内容模板

从 NotificationContent 和 NotificationTitle 枚举中使用预定义的内容：

```python
from core.models.notification_model import NotificationTitle, NotificationContent

# 使用预定义模板发送通知
self.notification_service.success(
    title=NotificationTitle.NONE_TITLE.value,
    content=NotificationContent.SETTINGS_SAVED.value.format(setting_name="模型目录")
)

# 发送错误通知
self.notification_service.error(
    title=NotificationTitle.NONE_TITLE.value,
    content=NotificationContent.FILE_ADD_FAILED.value.format(error_message=str(e))
)
```

### 3.3 特定场景通知方法

通知服务还提供了一些特定场景的便捷方法：

```python
# 模型加载相关
self.notification_service.model_loading("模型名称")
self.notification_service.model_loaded("模型名称", success=True)

# 模型下载相关
self.notification_service.model_download_started("模型名称")
self.notification_service.model_download_completed("模型名称", success=True)
```

## 4. 扩展通知内容

如需添加新的通知内容模板，请在 `core/models/notification_model.py` 中的 `NotificationContent` 枚举中添加：

```python
class NotificationContent(Enum):
    # 现有内容...
    
    # 添加新的通知内容模板
    MY_NEW_NOTIFICATION = "这是一个新的通知内容：{custom_param}"
```

## 5. 最佳实践

### 5.1 使用预定义内容

为了保持应用程序通知的一致性，尽量使用 `NotificationContent` 中的预定义内容模板，而不是硬编码通知内容。

### 5.2 通知类型选择

- **信息 (Info)**: 用于中性的信息展示，不表达成功或失败
- **成功 (Success)**: 用于操作成功的反馈
- **警告 (Warning)**: 用于可能有问题但不影响主要功能的情况
- **错误 (Error)**: 用于操作失败或需要用户立即注意的问题

### 5.3 通知内容格式

- 保持内容简洁明了
- 使用动词开头来描述动作（"已完成..."、"正在处理..."）
- 错误通知应包含简要的错误原因和可能的解决方法
- 使用参数化模板以便于本地化和内容一致性

### 5.4 避免过多通知

避免在短时间内发送大量通知，以免干扰用户体验：
- 批量操作考虑使用单一总结性通知
- 进度类操作只在开始和结束时发送通知
- 对于频繁变化的状态，考虑使用进度条或状态栏代替通知

## 6. 示例场景

### 6.1 文件操作

```python
# 文件添加失败
self.notification_service.error(
    title=NotificationTitle.NONE_TITLE.value,
    content=NotificationContent.FILE_ADD_FAILED.value.format(error_message=str(e))
)

# 任务完成
self.notification_service.success(
    title=NotificationTitle.NONE_TITLE.value,
    content=NotificationContent.TASK_COMPLETED.value.format(
        file_name=file_name,
        output_name=output_name
    )
)
```

### 6.2 设置更新

```python
# 设置已保存
self.notification_service.success(
    title=NotificationTitle.NONE_TITLE.value,
    content=NotificationContent.SETTINGS_SAVED.value.format(setting_name="输出目录")
)

# 设置已重置
self.notification_service.success(
    title=NotificationTitle.NONE_TITLE.value,
    content=NotificationContent.SETTINGS_RESET.value
)
```

### 6.3 模型操作

```python
# 模型加载
self.notification_service.model_loading("Whisper Medium")
self.notification_service.model_loaded("Whisper Medium", success=True)

# 模型下载
self.notification_service.model_download_started("Whisper Large")
self.notification_service.model_download_completed("Whisper Large", success=True)
```

## 7. 通知内容参考

以下是预定义的通知内容（从 `NotificationContent` 枚举）：

### 模型相关
- MODEL_LOADING = "正在加载 {model_name} 模型，请稍候..."
- MODEL_LOADED = "模型 {model_name} 已成功加载"
- MODEL_LOADING_FAILED = "模型 {model_name} 加载失败，请检查模型文件或重新下载"
- MODEL_DOWNLOADING = "正在下载 {model_name} 模型，请稍候..."
- MODEL_DOWNLOADED = "模型 {model_name} 已成功下载"
- MODEL_DOWNLOADING_FAILED = "模型 {model_name} 下载失败，请检查网络连接或重新下载"
- MODEL_DOWNLOAD_STARTED = "模型 {model_name} 开始下载，请耐心等待下载完成"
- MODEL_DOWNLOAD_COMPLETED = "模型 {model_name} 已下载完成"
- MODEL_DOWNLOAD_NOT_FOUND = "未找到模型 {model_name} 的下载信息"

### 文件操作
- FILE_ADD_FAILED = "添加文件失败: {error_message}"
- FILE_OPEN_FAILED = "打开文件失败: {file_path}"
- FILE_NOT_EXIST = "输出文件不存在"
- DIRECTORY_OPEN_FAILED = "打开目录失败: {directory_path}"

### 设置相关
- SETTINGS_SAVED = "{setting_name}已更新"
- SETTINGS_RESET = "已将所有设置恢复为默认值"
- OUTPUT_DIR_RESET = "已恢复为默认输出目录设置"

### 任务相关
- TASK_STARTED = "开始处理文件: {file_name}"
- TASK_COMPLETED = "任务完成: {file_name} -> {output_name}"
- TASK_CANCELLED = "用户取消了所有处理任务"
- ALL_TASKS_COMPLETED = "所有任务处理完成"

### 环境相关
- ENV_SETUP_STARTED = "开始设置独立Python环境..."
- ENV_SETUP_COMPLETED = "独立Python环境设置完成"
- ENV_SETUP_FAILED = "独立Python环境设置失败: {error_message}"
- ENV_ALREADY_SETUP = "独立Python环境已经设置完成"
- ENV_NOT_READY = "独立Python环境未准备好，请先设置环境" 