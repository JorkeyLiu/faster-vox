#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
事件类型定义 - 应用程序事件数据模型
提供标准化的事件数据类型，确保类型安全和一致性
"""

import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from enum import Enum

from core.models.task_model import ProcessStatus
from core.models.transcription_model import TranscriptionParameters
from core.models.environment_model import EnvironmentInfo


@dataclass
class BaseEvent:
    """所有事件的基类"""
    pass


@dataclass
class TaskEvent(BaseEvent):
    """任务相关事件的基类"""
    task_id: str  # 任务ID


@dataclass
class TaskStateChangedEvent(TaskEvent):
    """任务状态变更事件"""
    status: ProcessStatus  # 任务状态
    progress: float = 0.0  # 任务进度
    error: str = ""  # 错误信息
    output_path: str = ""  # 输出文件路径


@dataclass
class TaskAddedEvent(TaskEvent):
    """任务添加事件"""
    file_path: str  # 文件路径
    file_name: str  # 文件名


@dataclass
class TaskRemovedEvent(TaskEvent):
    """任务移除事件"""
    pass


@dataclass
class TranscriptionProgressEvent(TaskEvent):
    """转录进度事件"""

    text: str


@dataclass
class TranscriptionCompletedEvent(BaseEvent):
    """转录完成事件 - 表示所有任务已完成"""
    # Removed total_duration as it was unused and always 0.0


@dataclass
class TranscriptionErrorEvent(TaskEvent):
    """转录错误事件"""
    error: str  # 错误信息
    details: Dict[str, Any] = field(default_factory=dict)  # 错误详情


@dataclass
class EnvironmentEvent(BaseEvent):
    """环境相关事件"""
    status: str  # 环境状态
    message: str = ""  # 状态消息


@dataclass
class WorkerEvent(TaskEvent):
    """工作线程相关事件基类"""
    worker_id: str  # 工作线程ID


@dataclass
class WorkerRegisteredEvent(WorkerEvent):
    """工作线程注册事件"""
    source_file: str = ""  # 源文件路径
    worker_type: str = ""  # 工作线程类型


@dataclass
class WorkerUnregisteredEvent(WorkerEvent):
    """工作线程注销事件"""
    pass


@dataclass
class WorkerProgressEvent(WorkerEvent):
    """工作线程进度事件"""
    message: str  # 进度消息
    progress: float = 0.0  # 进度值


@dataclass
class WorkerCompletedEvent(WorkerEvent):
    """工作线程成功完成事件"""
    data: Dict[str, Any] = field(default_factory=dict)  # 结果数据

@dataclass
class WorkerFailedEvent(WorkerEvent):
    """工作线程失败事件"""
    error: str  # 错误信息
    details: Dict[str, Any] = field(default_factory=dict)  # 错误详情

@dataclass
class WorkerCancelledEvent(WorkerEvent):
    """工作线程取消事件"""
    pass


@dataclass
class ErrorEvent(BaseEvent):
    """错误事件"""
    message: str  # 错误消息
    category: str  # 错误类别
    priority: str  # 优先级
    code: str = ""  # 错误代码
    details: Dict[str, Any] = field(default_factory=dict)  # 错误详情
    source: str = ""  # 错误来源
    stack_trace: str = ""  # 堆栈跟踪


@dataclass
class ConfigChangedEvent(BaseEvent):
    """配置变更事件"""
    key: str  # 设置键名
    value: Any  # 新的设置值
    source: str = ""  # 变更来源


# 新增请求事件数据类

@dataclass
class RequestAddTasksEvent(BaseEvent):
    """请求添加任务事件"""
    file_paths: List[str]  # 文件路径列表


@dataclass
class RequestRemoveTaskEvent(TaskEvent):
    """请求移除任务事件"""
    pass


@dataclass
class RequestClearTasksEvent(BaseEvent):
    """请求清空所有任务事件"""
    pass


@dataclass
class RequestStartProcessingEvent(BaseEvent):
    """请求开始处理任务事件"""
    model_name: str = ""  # 模型名称，可选


@dataclass
class RequestCancelProcessingEvent(BaseEvent):
    """请求取消处理任务事件"""
    pass


@dataclass
class AudioExtractedEvent(BaseEvent):
    """音频提取完成事件"""
    file_path: str  # 原始文件路径
    audio_path: str  # 提取后的音频路径


@dataclass
class TaskTimerUpdatedEvent(TaskEvent):
    """任务计时器更新事件"""
    duration: str  # 任务持续时间


@dataclass
class ModelEvent(BaseEvent):
    """统一的模型事件数据类"""
    event_type: str  # 事件类型，使用EventTypes中的常量
    model_name: str  # 模型名称
    # 可选字段
    progress: int = 0  # 进度 (用于MODEL_DOWNLOAD_PROGRESS)
    success: bool = False  # 成功标志 (用于MODEL_DOWNLOAD_COMPLETED, MODEL_LOADED)
    error: str = ""  # 错误信息 (用于MODEL_DOWNLOAD_ERROR)
    status_message: str = ""  # 状态消息
    model_data: Optional[Any] = None  # 模型数据对象 (用于MODEL_DATA_CHANGED)
    model_path: Optional[str] = None  # 模型路径 (用于MODEL_LOADED)


@dataclass
class ModelDownloadErrorEvent(BaseEvent):
    """模型下载错误事件"""
    model_name: str  # 模型名称
    error: str  # 错误信息


@dataclass
class TaskAssignedEvent(TaskEvent):
    """任务分配事件，通知转录服务开始处理特定任务"""
    file_path: str  # 文件路径


@dataclass
class TranscriptionStartedEvent(BaseEvent):
    """全局转录开始事件，包含转录参数信息"""
    parameters: TranscriptionParameters  # 转录参数
# 新增：单个任务处理开始事件
@dataclass
class TaskStartedEvent(TaskEvent):
    """单个任务处理开始事件"""
    file_path: str  # 文件路径




@dataclass
class CudaEnvDownloadStartedEvent(BaseEvent):
    """CUDA环境下载开始事件"""
    app_name: str  # 应用名称


@dataclass
class CudaEnvDownloadProgressEvent(BaseEvent):
    """CUDA环境下载进度事件"""
    app_name: str  # 应用名称
    progress: float  # 进度值 (0-100)
    message: str  # 进度消息


@dataclass
class CudaEnvDownloadCompletedEvent(BaseEvent):
    """CUDA环境下载完成事件"""
    app_name: str  # 应用名称
    success: bool  # 是否成功
    error: str = ""  # 错误信息


@dataclass
class CudaEnvDownloadErrorEvent(BaseEvent):
    """CUDA环境下载错误事件"""
    app_name: str  # 应用名称
    error: str  # 错误信息
    details: Dict[str, Any] = field(default_factory=dict)  # 错误详情


@dataclass
class CudaEnvInstallStartedEvent(BaseEvent):
    """CUDA环境安装开始事件"""
    app_name: str  # 应用名称


@dataclass
class CudaEnvInstallProgressEvent(BaseEvent):
    """CUDA环境安装进度事件"""
    app_name: str  # 应用名称
    progress: float  # 进度值 (0-100)
    message: str  # 进度消息


@dataclass
class CudaEnvInstallCompletedEvent(BaseEvent):
    """CUDA环境安装完成事件"""
    app_name: str  # 应用名称
    success: bool  # 是否成功
    error: str = ""  # 错误信息


@dataclass
class CudaEnvInstallErrorEvent(BaseEvent):
    """CUDA环境安装错误事件"""
    app_name: str  # 应用名称
    error: str  # 错误信息
    details: Dict[str, Any] = field(default_factory=dict)  # 错误详情


@dataclass
class EnvironmentStatusEvent(BaseEvent):
    """环境状态事件 - 报告当前环境状态
    
    此事件包含环境信息对象，提供系统环境的完整状态。
    订阅者可以通过此事件获取最新的环境状态，包括GPU兼容性、
    CUDA版本、预编译应用可用性等信息。
    """
    environment_info: EnvironmentInfo  # 环境信息对象

class DownloadType(Enum):
    """下载类型"""
    MODEL = "model"
    ENV = "env"
    BUNDLED = "bundled"

@dataclass
class DownloadForTaskEvent(BaseEvent):
    """点击处理后的下载事件"""
    download_type: DownloadType  # 下载类型

# 定义事件类型的常量
class EventTypes:
    """事件类型常量，用于统一事件名称"""
    
    # 任务事件
    TASK_ADDED = "task_added"
    TASK_REMOVED = "task_removed"
    TASK_STATE_CHANGED = "task_state_changed"
    TASK_TIMER_UPDATED = "task_timer_updated"
    TASK_ASSIGNED = "task_assigned"  # 任务分配事件
    TASK_STARTED = "task_started" # 单个任务处理开始事件
    
    # 转录事件
    TRANSCRIPTION_STARTED = "transcription_started"
    TRANSCRIPTION_PROGRESS = "transcription_progress"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    TRANSCRIPTION_ERROR = "transcription_error"
    TRANSCRIPTION_CANCELLED = "transcription_cancelled"
    TRANSCRIPTION_PROCESS_INFO = "transcription_process_info" # 新增统一事件
    # 音频事件
    AUDIO_EXTRACTED = "audio_extracted"
    AUDIO_INFO_READY = "audio_info_ready" # 新增
    AUDIO_INFO_FAILED = "audio_info_failed" # 新增
    
    # 环境事件
    ENVIRONMENT_SETUP_STARTED = "environment_setup_started"
    ENVIRONMENT_SETUP_COMPLETED = "environment_setup_completed"
    ENVIRONMENT_STATUS_CHANGED = "environment_status_changed"
    
    # 模型事件
    MODEL_DOWNLOAD_REQUESTED = "model_download_requested"
    MODEL_DOWNLOAD_STARTED = "model_download_started"
    MODEL_DOWNLOAD_PROGRESS = "model_download_progress"
    MODEL_DOWNLOAD_COMPLETED = "model_download_completed"
    MODEL_DOWNLOAD_ERROR = "model_download_error"
    MODEL_LOAD_REQUESTED = "model_load_requested"
    MODEL_LOADING = "model_loading"
    MODEL_LOADED = "model_loaded"
    MODEL_UNLOADED = "model_unloaded"
    MODEL_DATA_CHANGED = "model_data_changed"
    
    # 工作线程事件
    WORKER_REGISTERED = "worker_registered"
    WORKER_UNREGISTERED = "worker_unregistered"
    WORKER_PROGRESS = "worker_progress"
    WORKER_COMPLETED = "worker_completed"
    WORKER_FAILED = "worker_failed"
    WORKER_CANCELLED = "worker_cancelled"
    
    # 系统事件
    ERROR_OCCURRED = "error_occurred"
    CONFIG_CHANGED = "config_changed"
    
    # 请求事件 - 用于UI到服务层的操作请求
    REQUEST_ADD_TASKS = "request_add_tasks"
    REQUEST_REMOVE_TASK = "request_remove_task"
    REQUEST_CLEAR_TASKS = "request_clear_tasks"
    REQUEST_START_PROCESSING = "request_start_processing"
    REQUEST_CANCEL_PROCESSING = "request_cancel_processing"
    
    # UI事件
    FILES_DROPPED = "files_dropped"
    
    # 通知事件
    NOTIFICATION_INFO = "notification_info"
    NOTIFICATION_SUCCESS = "notification_success"
    NOTIFICATION_WARNING = "notification_warning"
    NOTIFICATION_ERROR = "notification_error"
    
    # CUDA环境下载事件
    CUDA_ENV_DOWNLOAD_STARTED = "cuda_env_download_started"
    CUDA_ENV_DOWNLOAD_PROGRESS = "cuda_env_download_progress"
    CUDA_ENV_DOWNLOAD_COMPLETED = "cuda_env_download_completed"
    CUDA_ENV_DOWNLOAD_ERROR = "cuda_env_download_error"
    
    # CUDA环境安装事件
    CUDA_ENV_INSTALL_STARTED = "cuda_env_install_started"
    CUDA_ENV_INSTALL_PROGRESS = "cuda_env_install_progress"
    CUDA_ENV_INSTALL_COMPLETED = "cuda_env_install_completed"
    CUDA_ENV_INSTALL_ERROR = "cuda_env_install_error"
    
    # 下载事件
    DOWNLOAD_FOR_TASK_REQUESTED = "download_for_task_requested"
    DOWNLOAD_FOR_TASK_COMPLETED = "download_for_task_completed"
    DOWNLOAD_FOR_TASK_ERROR = "download_for_task_error"


@dataclass
class NotificationEvent(BaseEvent):
    """通知事件基类"""
    title: str  # 标题
    content: str  # 内容

@dataclass
class NotificationInfoEvent(NotificationEvent):
    """信息通知事件"""
    pass

@dataclass
class NotificationSuccessEvent(NotificationEvent):
    """成功通知事件"""
    pass

@dataclass
class NotificationWarningEvent(NotificationEvent):
    """警告通知事件"""
    pass

@dataclass
class NotificationErrorEvent(NotificationEvent):
    """错误通知事件"""
    pass

@dataclass
class FilesDroppedEvent(BaseEvent):
    """文件拖放事件"""
    file_paths: List[str]  # 文件路径列表


@dataclass
class TranscriptionProcessInfoEvent(TaskEvent):
    """统一的转录进度与文本事件数据"""
    process_text: str  # 当前处理的文本片段
    progress: float  # 当前任务进度 (0-1)


@dataclass
class AudioInfoReadyEvent(TaskEvent):
    """音频信息获取成功事件"""
    file_path: str # 新增
    audio_info: Dict[str, Any]


@dataclass
class AudioInfoFailedEvent(TaskEvent):
    """音频信息获取失败事件"""
    file_path: str # 新增
    error: str