# 事件总线架构文档

## 概述

事件总线是Faster Vox应用程序中的核心通信机制，它为应用程序内的各个组件提供了统一的通信方式。通过事件总线，不同的组件可以发布事件并订阅感兴趣的事件，从而实现解耦和灵活的通信方式。

本文档介绍事件总线架构的设计原则、使用方法、事件类型和示例，以帮助开发人员理解和使用事件总线。

## 设计原则

事件总线架构基于以下核心设计原则：

1. **解耦性**：事件发布者和订阅者之间不直接依赖，从而降低组件间的耦合度
2. **可扩展性**：容易添加新的事件类型和处理器，无需修改现有代码
3. **可测试性**：便于单元测试，可以模拟事件发布和监听事件调用
4. **类型安全**：使用类型化事件数据，提供更好的数据完整性和IDE支持
5. **一致性**：提供统一的通信机制，简化应用程序的通信模型
6. **向后兼容**：支持从旧的信号-槽机制过渡到事件总线

## 核心组件

### EventBus

`EventBus`类是事件总线架构的核心，实现为单例模式，提供事件发布和订阅功能：

```python
from core.events import event_bus

# 发布事件
event_bus.publish(EventTypes.TASK_ADDED, task_added_event)

# 订阅事件
event_bus.subscribe(EventTypes.TASK_ADDED, handle_task_added)
```

### 事件类型

事件类型定义在`EventTypes`类中，作为事件的标识符：

```python
class EventTypes:
    """事件类型常量，用于统一事件名称"""
    
    # 任务事件
    TASK_ADDED = "task_added"
    TASK_REMOVED = "task_removed"
    TASK_STATE_CHANGED = "task_state_changed"
    
    # 转录事件
    TRANSCRIPTION_STARTED = "transcription_started"
    TRANSCRIPTION_PROGRESS = "transcription_progress"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    # ...其他事件类型
```

### 事件数据类

事件数据类定义了事件的数据结构，使用`dataclass`装饰器实现：

```python
@dataclass
class TaskAddedEvent(TaskEvent):
    """任务添加事件"""
    file_path: str  # 文件路径
    file_name: str  # 文件名
```

所有事件数据类继承自`BaseEvent`，具有以下基本属性：

```python
@dataclass
class BaseEvent:
    """所有事件的基类"""
    timestamp: float = field(default_factory=time.time)  # 事件时间戳
```

## 使用方法

### 发布事件

要发布事件，首先创建一个事件数据对象，然后使用`event_bus`发布：

```python
from core.events import event_bus, EventTypes, TaskAddedEvent

# 创建事件数据
event_data = TaskAddedEvent(
    task_id="task_123",
    file_path="/path/to/file.mp3",
    file_name="file.mp3"
)

# 发布事件
event_bus.publish(EventTypes.TASK_ADDED, event_data)
```

### 订阅事件

要订阅事件，定义一个处理函数并使用`event_bus`订阅：

```python
from core.events import event_bus, EventTypes

def handle_task_added(event):
    print(f"任务已添加: {event.task_id}, 文件: {event.file_name}")

# 订阅事件
event_bus.subscribe(EventTypes.TASK_ADDED, handle_task_added)
```

### 取消订阅

如果不再需要处理某个事件，可以取消订阅：

```python
event_bus.unsubscribe(EventTypes.TASK_ADDED, handle_task_added)
```

### 调试模式

事件总线提供调试模式，记录事件发布和处理信息：

```python
# 开启调试模式
event_bus.set_debug(True)

# 获取事件历史
event_history = event_bus.get_event_history()

# 清除事件历史
event_bus.clear_event_history()
```

## 事件类型参考
下列仅供参考，具体定义请查阅 @event_types.py

### 任务事件

| 事件类型 | 事件数据类 | 说明 |
|---------|-----------|------|
| `TASK_ADDED` | `TaskAddedEvent` | 任务添加事件 |
| `TASK_REMOVED` | `TaskRemovedEvent` | 任务移除事件 |
| `TASK_STATE_CHANGED` | `TaskStateChangedEvent` | 任务状态变更事件 |

### 转录事件

| 事件类型 | 事件数据类 | 说明 |
|---------|-----------|------|
| `TRANSCRIPTION_STARTED` | `TranscriptionStartedEvent` | 转录开始事件 |
| `TRANSCRIPTION_PROGRESS` | `TranscriptionProgressEvent` | 转录进度事件 |
| `TRANSCRIPTION_COMPLETED` | `TranscriptionCompletedEvent` | 转录完成事件 |
| `TRANSCRIPTION_ERROR` | `TranscriptionErrorEvent` | 转录错误事件 |

### 工作线程事件

| 事件类型 | 事件数据类 | 说明 |
|---------|-----------|------|
| `WORKER_REGISTERED` | `WorkerRegisteredEvent` | 工作线程注册事件 |
| `WORKER_UNREGISTERED` | `WorkerUnregisteredEvent` | 工作线程注销事件 |
| `WORKER_PROGRESS` | `WorkerProgressEvent` | 工作线程进度事件 |
| `WORKER_COMPLETED` | `WorkerCompletedEvent` | 工作线程完成事件 |

### 系统事件

| 事件类型 | 事件数据类 | 说明 |
|---------|-----------|------|
| `ERROR_OCCURRED` | `ErrorEvent` | 错误事件 |
| `CONFIG_CHANGED` | `ConfigChangedEvent` | 配置变更事件 |

## 示例

### 服务层示例

在服务层中发布事件：

```python
def update_task_state(self, task_id: str, status: ProcessStatus, progress: float = None, 
                      error: str = None, output_path: str = None):
    # 更新任务状态...
    
    # 发布任务状态变化事件
    event_data = TaskStateChangedEvent(
        task_id=task_id,
        status=status,
        progress=task.progress,
        error=error or task.error,
        output_path=output_path or task.output_path
    )
    event_bus.publish(EventTypes.TASK_STATE_CHANGED, event_data)
```

### UI层示例

在UI层中订阅事件：

```python
def _setup_connections(self):
    # 订阅事件总线事件
    event_bus.subscribe(EventTypes.TASK_STATE_CHANGED, self._handle_task_state_changed)
    event_bus.subscribe(EventTypes.TRANSCRIPTION_COMPLETED, self._handle_transcription_completed)
    event_bus.subscribe(EventTypes.TRANSCRIPTION_PROGRESS, self._handle_transcription_progress)

def _handle_task_state_changed(self, event):
    # 更新任务状态
    self._on_task_status_updated(event.task_id, event.status)
    
    # 如果任务完成，处理完成逻辑
    if event.status == ProcessStatus.COMPLETED and event.output_path:
        self._on_task_completed(event.task_id, event.output_path)
```

## 最佳实践

1. **命名事件类型**：使用描述性的名称，遵循`OBJECT_ACTION`模式
2. **事件粒度**：选择合适的事件粒度，既不过细也不过粗
3. **事件数据类设计**：只包含必要的数据，避免过度依赖
4. **避免循环依赖**：注意避免通过事件总线创建循环依赖
5. **异常处理**：在事件处理器中添加适当的异常处理
6. **线程安全**：注意多线程环境下的事件处理
7. **事件版本管理**：如果需要改变事件数据结构，考虑版本管理
8. **命名约定**：
   - 事件类型常量使用大写加下划线
   - 事件数据类使用驼峰命名法
   - 处理函数使用`handle_[event_name]`或`_handle_[event_name]`

## 迁移指南

从旧的信号-槽机制迁移到事件总线：

1. **定义事件数据类**：为每个信号创建对应的事件数据类
2. **添加事件发布**：在原信号发射的地方添加事件发布
3. **保留原有信号**：暂时保留原有信号作为向后兼容
4. **添加事件订阅**：为现有组件添加事件订阅
5. **逐步替换**：逐步将信号-槽依赖替换为事件总线
6. **移除信号**：完全迁移后，移除旧的信号定义

## 总结

事件总线架构为Faster Vox应用程序提供了一种统一、灵活的通信机制，使各组件能够在松耦合的状态下有效通信。通过使用事件总线，我们简化了应用程序的通信模型，提高了代码的可维护性和可扩展性。 