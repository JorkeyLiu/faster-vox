#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通知服务 - 统一管理应用程序的通知（基于事件总线）
"""

from PySide6.QtCore import QObject
from typing import Callable

from core.models.notification_model import NotificationContent, NotificationTitle
from core.events import event_bus, EventTypes
from core.events.event_types import (
    NotificationInfoEvent, 
    NotificationSuccessEvent, 
    NotificationWarningEvent, 
    NotificationErrorEvent,
    ModelEvent
)

class NotificationService(QObject):
    """通知服务，使用事件总线机制管理应用程序的通知
    
    通知机制:
    - 各个服务调用NotificationService的方法发送通知
    - 通知通过事件总线发布
    - UI组件订阅事件总线的通知事件
    """
    
    def __init__(self, translator: Callable): # 直接接收 translator
        """初始化通知服务"""
        super().__init__()
        self._ = translator # 新增赋值

    def initialize(self):
        """初始化通知服务，订阅相关事件"""
        # 订阅模型事件
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_STARTED, self._handle_model_event)
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self._handle_model_event)
    
    def _handle_model_event(self, event_data: ModelEvent):
        """统一处理模型事件
        
        Args:
            event_data: 模型事件数据
        """
        if event_data.event_type == EventTypes.MODEL_DOWNLOAD_STARTED:
            self.model_download_started(event_data.model_name)
        elif event_data.event_type == EventTypes.MODEL_DOWNLOAD_COMPLETED:
            self.model_download_completed(event_data.model_name, event_data.success)
    
    def model_download_started(self, model_name: str):
        """模型开始下载通知
        
        Args:
            model_name: 模型名称
        """
        title = NotificationTitle.NONE_TITLE.value
        content = NotificationContent.MODEL_DOWNLOAD_STARTED.get_message(self._, model_name=model_name)
        self.success(title, content)
        
    def model_download_completed(self, model_name: str, success: bool):
        """模型下载完成/失败通知
        
        Args:
            model_name: 模型名称
            success: 是否成功
        """
        if success:
            title = NotificationTitle.NONE_TITLE.value
            content = NotificationContent.MODEL_DOWNLOAD_COMPLETED.get_message(self._, model_name=model_name)
            self.success(title, content)
        else:
            title = NotificationTitle.NONE_TITLE.value
            content = NotificationContent.MODEL_DOWNLOADING_FAILED.get_message(self._, model_name=model_name)
            self.error(title, content)
    
    # 通用通知
    def info(self, title: str, content: str):
        """发送信息通知
        
        Args:
            title: 标题
            content: 内容
        """
        # 确保title和content不为None
        title = title or NotificationTitle.NONE_TITLE.value
        content = content or ""
        event_data = NotificationInfoEvent(
            title=title,
            content=content
        )
        event_bus.publish(EventTypes.NOTIFICATION_INFO, event_data)
    
    def success(self, title: str, content: str):
        """发送成功通知
        
        Args:
            title: 标题
            content: 内容
        """
        # 确保title和content不为None
        title = title or NotificationTitle.NONE_TITLE.value
        content = content or ""
        event_data = NotificationSuccessEvent(
            title=title,
            content=content
        )
        event_bus.publish(EventTypes.NOTIFICATION_SUCCESS, event_data)
    
    def warning(self, title: str, content: str):
        """发送警告通知
        
        Args:
            title: 标题
            content: 内容
        """
        # 确保title和content不为None
        title = title or NotificationTitle.NONE_TITLE.value
        content = content or ""
        event_data = NotificationWarningEvent(
            title=title,
            content=content
        )
        event_bus.publish(EventTypes.NOTIFICATION_WARNING, event_data)
    
    def error(self, title: str, content: str):
        """发送错误通知
        
        Args:
            title: 标题
            content: 内容
        """
        # 确保title和content不为None
        title = title or NotificationTitle.NONE_TITLE.value
        content = content or ""
        event_data = NotificationErrorEvent(
            title=title,
            content=content
        )
        event_bus.publish(EventTypes.NOTIFICATION_ERROR, event_data)

