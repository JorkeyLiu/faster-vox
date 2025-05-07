#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""数据模型模块，包含各种数据结构定义"""

# 导入通知模型
from core.models.notification_model import NotificationContent, NotificationTitle

# 导入错误模型
from core.models.error_model import ErrorInfo, ErrorCategory, ErrorPriority

# 导入环境模型

# 导入模型数据
from core.models.model_data import ModelData, ModelSize

# 导入任务模型
from core.models.task_model import Task, ProcessStatus

# 导入转录模型
from core.models.transcription_model import (
    TranscriptionSegment, TranscriptionResult, 
    TranscriptionError, TranscriptionParameters
)

# 导入配置模型
from core.models.config import AppConfig

# 导出所有模型
__all__ = [
    'NotificationContent', 'NotificationTitle',
    'ErrorInfo', 'ErrorCategory', 'ErrorPriority',
    'ModelData', 'ModelSize',
    'Task', 'ProcessStatus',
    'TranscriptionSegment', 'TranscriptionResult', 
    'TranscriptionError', 'TranscriptionParameters',
    'AppConfig'
]
