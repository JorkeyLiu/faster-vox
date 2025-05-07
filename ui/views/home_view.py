#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主页视图 - 包含文件拖放区域
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout
from dependency_injector.wiring import Provide, inject

from core.services.audio_service import AudioService
from core.services.config_service import ConfigService
from core.services.error_handling_service import ErrorHandlingService, ErrorCategory, ErrorPriority, ErrorInfo
from core.events import event_bus
from core.events.event_types import EventTypes, RequestAddTasksEvent, ConfigChangedEvent, ErrorEvent, FilesDroppedEvent
from loguru import logger
from ui.components.drop_area import DropArea

class HomeView(QWidget):
    """主页视图"""
    
    def __init__(
        self, 
        parent=None
    ):
        super().__init__(parent)
        
        # 设置对象名称
        self.setObjectName("homeView")
        
        # 初始化服务
        self._init_services()

        # 从父组件获取任务视图
        self.task_view = None
        if parent and hasattr(parent, 'task_view'):
            self.task_view = parent.task_view
        
        # 初始化UI
        self._init_ui()
    
    @inject
    def _init_services(
        self, 
        config_service: ConfigService = Provide["config_service"],
        audio_service: AudioService = Provide["audio_service"],
        error_service: ErrorHandlingService = Provide["error_service"]
    ):
        self.config_service = config_service
        self.audio_service = audio_service
        self.error_service = error_service
        
        # 订阅文件拖放事件
        event_bus.subscribe(EventTypes.FILES_DROPPED, self._on_files_dropped)

    def _init_ui(self):
        """初始化UI"""
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(50, 50, 50, 50)  # 增加外边距
        layout.setSpacing(20)
        layout.setAlignment(Qt.AlignCenter)
        
        # 创建拖放区域
        self.drop_area = DropArea(self)
        
        # 添加到布局
        layout.addStretch()
        layout.addWidget(self.drop_area, 0, Qt.AlignCenter)
        layout.addStretch()
    
    def _on_files_dropped(self, event):
        """处理文件拖放事件
        
        Args:
            event: 文件拖放事件对象
        """
        file_paths = event.file_paths
        
        # 更新上次打开的目录
        if file_paths and file_paths[0]:
            try:
                path = os.path.dirname(file_paths[0]) if os.path.isfile(file_paths[0]) else file_paths[0]
                self.config_service.set_last_directory(path)
            except Exception as e:
                logger.error(f"更新目录出错: {e}")
                # 使用错误处理服务
                error_info = ErrorInfo(
                    message=f"更新目录出错: {str(e)}",
                    category=ErrorCategory.CONFIGURATION,
                    priority=ErrorPriority.LOW,
                    code="CONFIG_UPDATE_ERROR",
                    user_visible=False
                )
                self.error_service.handle_error(error_info)
        
        # 发布添加任务请求事件
        event_data = RequestAddTasksEvent(
            file_paths=file_paths
        )
        event_bus.publish(EventTypes.REQUEST_ADD_TASKS, event_data)

    def __del__(self):
        """组件销毁时清理资源"""
        try:
            # 取消事件订阅
            event_bus.unsubscribe(EventTypes.FILES_DROPPED, self._on_files_dropped)
        except:
            # 忽略可能的异常
            pass 