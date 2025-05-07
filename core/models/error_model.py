#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""错误相关数据模型和枚举"""

from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum, auto


class ErrorCategory(Enum):
    """错误类别枚举"""
    GENERAL = auto()  # 通用错误
    TRANSCRIPTION = auto()  # 转录错误
    AUDIO = auto()  # 音频处理错误
    MODEL = auto()  # 模型错误
    FILE_IO = auto()  # 文件I/O错误
    NETWORK = auto()  # 网络错误
    ENVIRONMENT = auto()  # 环境错误
    CONFIGURATION = auto()  # 配置错误
    RESOURCE = auto()  # 资源错误
    TIMEOUT = auto()  # 超时错误
    NOT_FOUND = auto()  # 未找到错误
    VALIDATION = auto()  # 验证错误
    PARSING = auto()  # 解析错误


class ErrorPriority(Enum):
    """错误优先级枚举"""
    CRITICAL = auto()  # 严重错误，需要立即处理
    HIGH = auto()      # 高优先级错误，影响主要功能
    MEDIUM = auto()    # 中等优先级错误，影响部分功能
    LOW = auto()       # 低优先级错误，不影响主要功能
    DEBUG = auto()     # 调试级别错误，主要用于开发


@dataclass
class ErrorInfo:
    """错误信息数据类"""
    message: str
    category: ErrorCategory = ErrorCategory.GENERAL
    priority: ErrorPriority = ErrorPriority.MEDIUM
    code: str = "ERROR"
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    stack_trace: Optional[str] = None
    handled: bool = False
    user_visible: bool = True 