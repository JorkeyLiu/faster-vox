#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
错误处理服务 - 集中管理和处理应用程序错误
"""

import traceback
from typing import List, Callable, Dict, Any, Optional
from datetime import datetime
from collections import deque
from loguru import logger
from PySide6.QtCore import QObject, Signal

from core.models.error_model import ErrorInfo, ErrorCategory, ErrorPriority
from core.services.notification_service import NotificationService

from dependency_injector.wiring import inject


class ErrorHandlingService(QObject):
    """错误处理服务，集中处理和记录应用程序错误"""
    
    # 错误信号
    error_occurred = Signal(ErrorInfo)
    
    def __init__(self, max_history_size: int = 100):
        """初始化错误处理服务
        
        Args:
            max_history_size: 最大错误历史记录数量
        """
        super().__init__()
        
        # 错误处理器列表
        self.handlers: List[Callable[[ErrorInfo], None]] = []
        
        # 错误历史记录
        self.error_history = deque(maxlen=max_history_size)
        
        # 通知服务引用，后续注入
        self.notification_service = None

    @inject
    def _init_service(self, notification_service: NotificationService): 
        """设置通知服务
        
        Args:
            notification_service: 通知服务实例
        """
        self.notification_service = notification_service
    
    def register_handler(self, handler: Callable[[ErrorInfo], None]):
        """注册错误处理器
        
        Args:
            handler: 错误处理函数，接收ErrorInfo参数
        """
        if handler not in self.handlers:
            self.handlers.append(handler)
            logger.debug(f"注册错误处理器: {handler}")
    
    def unregister_handler(self, handler: Callable[[ErrorInfo], None]):
        """取消注册错误处理器
        
        Args:
            handler: 错误处理函数
        """
        if handler in self.handlers:
            self.handlers.remove(handler)
            logger.debug(f"取消注册错误处理器: {handler}")
    
    def handle_error(self, error_info: ErrorInfo):
        """处理错误信息
        
        Args:
            error_info: 错误信息对象
        """
        # 记录到历史
        self.error_history.append(error_info)
        
        # 根据优先级记录日志
        self._log_error(error_info)
        
        # 发送错误信号
        self.error_occurred.emit(error_info)
        
        # 调用所有处理器
        for handler in self.handlers:
            try:
                handler(error_info)
            except Exception as e:
                logger.error(f"错误处理器失败: {str(e)}")
        
        # 如果错误需要用户通知且通知服务可用，发送通知
        if error_info.user_visible and self.notification_service:
            self.notification_service.error(
                title=error_info.category.name if hasattr(error_info.category, 'name') else "错误", 
                content=error_info.message
            )
        
        # 标记为已处理
        error_info.handled = True
    
    def handle_exception(self, exception: Exception, category: ErrorCategory,
                      priority: ErrorPriority, source: str = "", user_visible: bool = False):
        """处理异常
        
        Args:
            exception: 异常对象
            category: 错误类别
            priority: 错误优先级
            source: 错误来源
            user_visible: 是否向用户显示错误
        """
        # 获取堆栈跟踪
        stack_trace = traceback.format_exc()
        
        # 创建错误信息
        error_info = ErrorInfo(
            message=str(exception),
            category=category,
            priority=priority,
            code=exception.__class__.__name__,
            details={"exception_type": exception.__class__.__name__},
            source=source,
            stack_trace=stack_trace,
            user_visible=user_visible
        )
        
        # 处理错误
        self.handle_error(error_info)
    
    def get_error_history(self) -> List[ErrorInfo]:
        """获取错误历史记录
        
        Returns:
            List[ErrorInfo]: 错误历史记录列表
        """
        return list(self.error_history)
    
    def clear_error_history(self):
        """清除错误历史记录"""
        self.error_history.clear()
        logger.debug("清除错误历史记录")
    
    def _log_error(self, error_info: ErrorInfo):
        """根据错误优先级记录日志
        
        Args:
            error_info: 错误信息对象
        """
        log_message = f"[{error_info.category.name}] {error_info.message}"
        if error_info.source:
            log_message += f" (来源: {error_info.source})"
        
        if error_info.priority == ErrorPriority.CRITICAL:
            logger.critical(log_message)
            if error_info.stack_trace:
                logger.critical(f"堆栈跟踪:\n{error_info.stack_trace}")
        
        elif error_info.priority == ErrorPriority.HIGH:
            logger.error(log_message)
            if error_info.stack_trace:
                logger.error(f"堆栈跟踪:\n{error_info.stack_trace}")
        
        elif error_info.priority == ErrorPriority.MEDIUM:
            logger.warning(log_message)
        
        elif error_info.priority == ErrorPriority.LOW:
            logger.info(log_message)
        
        else:  # DEBUG
            logger.debug(log_message) 