#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
主窗口 - 应用程序的主窗口
"""

from PySide6.QtCore import Signal, Qt, Slot
from dependency_injector.wiring import Provide, inject

from qfluentwidgets import (
    NavigationItemPosition, FluentWindow, FluentIcon,
    setTheme, Theme, InfoBar, InfoBarPosition
)

from core.models.notification_model import NotificationContent, NotificationTitle
from ui.views.home_view import HomeView
from ui.views.task_view import TaskView
from ui.views.settings_view import SettingsView
from core.services.model_management_service import ModelManagementService
from core.services.notification_service import NotificationService
from core.services.task_service import TaskService
from core.services.config_service import ConfigService
from core.containers import AppContainer
from core.models.task_model import ProcessStatus
from core.events import event_bus, EventTypes, TaskStateChangedEvent, TaskAddedEvent
from core.models.config import cfg

from loguru import logger


class MainWindow(FluentWindow):
    """主窗口类"""
    
    # 信号定义
    filesDropped = Signal(list)  # 文件拖放信号，参数为文件路径列表
    
    @inject
    def __init__(self,
                 translator: callable = Provide[AppContainer.translation_function],
                 model_service: ModelManagementService = Provide[AppContainer.model_service],
                 notification_service: NotificationService = Provide[AppContainer.notification_service],
                 task_service: TaskService = Provide[AppContainer.task_service],
                 config_service: ConfigService = Provide[AppContainer.config_service]
                 ):
        """初始化主窗口"""
        super().__init__()
        self._ = translator # 赋值翻译函数
        
        # 设置对象名称，用于通知管理器识别主窗口
        self.setObjectName("mainWindow")
        
        # 初始化服务 (通过构造函数注入)
        self.model_service = model_service
        self.notification_service = notification_service
        self.task_service = task_service
        self.config_service = config_service
        # self._init_services() # 不再需要单独调用

        # 初始化UI
        self._init_ui()
        
        # 初始化窗口设置
        self._init_window()
        
        # 设置信号连接
        self._setup_connections()

    # @inject # _init_services 方法不再需要，服务已在 __init__ 中注入
    # def _init_services(
    #     self,
    #     model_service: ModelManagementService = Provide["model_service"],
    #     notification_service: NotificationService = Provide["notification_service"],
    #     task_service: TaskService = Provide["task_service"],
    #     config_service: ConfigService = Provide["config_service"]
    # ):
    #     """初始化服务，通过依赖注入获取"""
    #     # 使用依赖注入获取服务
    #     self.model_service = model_service
    #     self.notification_service = notification_service
    #     self.task_service = task_service
    #     self.config_service = config_service
    
    def _init_ui(self):
        """初始化UI"""
        # 创建视图 - 先创建任务视图，再创建主页视图
        # 注意：TaskView, HomeView, SettingsView 的构造函数也需要修改以接收 translator
        self.task_view = TaskView(self)
        self.task_view.setObjectName("task-view")
        
        self.home_view = HomeView(self)
        self.home_view.setObjectName("home-view")
        
        self.settings_view = SettingsView(self)
        self.settings_view.setObjectName("settings-view")
        
        # 初始化导航
        self._init_navigation()
    
    def _init_navigation(self):
        """初始化导航"""
        # 添加主页
        self.addSubInterface(self.home_view, FluentIcon.HOME, self._("首页"))
        
        # 添加任务视图
        self.addSubInterface(self.task_view, FluentIcon.DOCUMENT, self._("任务列表"))
        
        # 添加分隔线
        self.navigationInterface.addSeparator()

        # 添加语言切换按钮
        self.navigationInterface.addItem(
            routeKey='language_switcher',
            icon=FluentIcon.LANGUAGE,
            text=self._('切换语言'),
            onClick=self._toggle_language,
            position=NavigationItemPosition.BOTTOM
        )
        
        # 添加主题切换按钮
        self.navigationInterface.addItem(
            routeKey='theme',
            icon=FluentIcon.CONSTRACT,
            text=self._('深浅主题'),
            onClick=self._toggle_theme,
            position=NavigationItemPosition.BOTTOM
        )
        
        # 添加设置（在底部）
        self.addSubInterface(
            self.settings_view,
            FluentIcon.SETTING,
            self._("设置"),
            NavigationItemPosition.BOTTOM
        )
    
    def _init_window(self):
        """初始化窗口"""
        # 设置窗口标题
        self.setWindowTitle(self._("Faster Vox - 语音转文字工具"))
        
        # 设置窗口最小尺寸
        self.setMinimumSize(900, 650)
        
        # 设置默认主题
        theme = cfg.theme.value
        if theme == "dark":
            setTheme(Theme.DARK)
        else:
            setTheme(Theme.LIGHT)
    
    def _setup_connections(self):
        """设置信号连接"""
        # 订阅事件总线事件
        event_bus.subscribe(EventTypes.TASK_STATE_CHANGED, self.handle_task_state_changed_event)
        
        # 订阅任务添加事件
        event_bus.subscribe(EventTypes.TASK_ADDED, self._handle_task_added_event)
        
        # 订阅通知事件
        event_bus.subscribe(EventTypes.NOTIFICATION_INFO, self._handle_notification_info)
        event_bus.subscribe(EventTypes.NOTIFICATION_SUCCESS, self._handle_notification_success)
        event_bus.subscribe(EventTypes.NOTIFICATION_WARNING, self._handle_notification_warning)
        event_bus.subscribe(EventTypes.NOTIFICATION_ERROR, self._handle_notification_error)
    
    def _display_info(self, title: str, content: str):
        """显示信息通知
        
        Args:
            title: 标题
            content: 内容
        """
        InfoBar.info(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=False,
            duration=3500,
            position=InfoBarPosition.TOP,
            parent=self
        )
    
    def _display_success(self, title: str, content: str):
        """显示成功通知
        
        Args:
            title: 标题
            content: 内容
        """
        InfoBar.success(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=False,
            duration=3500,
            position=InfoBarPosition.TOP,
            parent=self
        )
    
    def _display_warning(self, title: str, content: str):
        """显示警告通知
        
        Args:
            title: 标题
            content: 内容
        """
        InfoBar.warning(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=False,
            duration=5000,
            position=InfoBarPosition.TOP,
            parent=self
        )
    
    def _display_error(self, title: str, content: str):
        """显示错误通知
        
        Args:
            title: 标题
            content: 内容
        """
        InfoBar.error(
            title=title,
            content=content,
            orient=Qt.Horizontal,
            isClosable=True,
            duration=5000,
            position=InfoBarPosition.TOP,
            parent=self
        )
    
    def _toggle_theme(self):
        """切换深色/浅色主题"""
        current_theme = cfg.theme.value
        
        # 切换主题
        if current_theme == "dark":
            new_theme = "light"
            setTheme(Theme.LIGHT)
        else:
            new_theme = "dark"
            setTheme(Theme.DARK)
        
        # 保存主题设置
        self.config_service.set_theme(new_theme)

    def _toggle_language(self):
        """切换界面语言并提示用户重启"""
        current_lang = self.config_service.get_ui_language()
        
        title = ("")
        if current_lang == "zh_CN":
            new_lang = "en_US"
            content = "Interface language has been switched to English. Restart to take effect."
        else:
            new_lang = "zh_CN"
            content = "界面语言已切换为中文，重启后生效。"
        
        self.config_service.set_ui_language(new_lang)
        
        # 使用 InfoBar 显示通知
        self._display_info(title, content)

    def _on_system_error(self, error_message: str):
        """系统错误回调
        
        Args:
            error_message: 错误消息
        """
        # 显示系统错误提示
        self.notification_service.error(
            title=NotificationTitle.NONE_TITLE.value,
            content=NotificationContent.SYSTEM_ERROR.value.format(error_message=error_message)
        )

    def handle_task_state_changed_event(self, event: TaskStateChangedEvent):
        """处理任务状态变更事件
        
        Args:
            event: 任务状态变更事件对象
        """
        # 处理状态变化
        if event.status is not None:
            self.handle_process_status(event.task_id, event.status, event.progress)
        
        # 处理错误
        if event.error:
            self.handle_process_error(event.task_id, event.error)
        
        # 处理输出文件
        if event.output_path:
            self.handle_process_completed(event.task_id, event.output_path)
    
    @Slot(str, ProcessStatus, float, str, str)
    def handle_task_state_changed(self, task_id: str, status: ProcessStatus, 
                            progress: float, error: str, output_path: str):
        """处理任务状态变化信号（向后兼容方法）
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度
            error: 错误信息
            output_path: 输出文件路径
        """
        # 处理状态变化
        if status is not None:
            self.handle_process_status(task_id, status, progress)
        
        # 处理错误
        if error:
            self.handle_process_error(task_id, error)
        
        # 处理输出文件
        if output_path:
            self.handle_process_completed(task_id, output_path)
    
    def handle_process_status(self, task_id: str, status: ProcessStatus, progress: float):
        """处理任务状态更新
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 进度
        """
        # 实现状态处理逻辑
        pass
    
    def handle_process_error(self, task_id: str, error: str):
        """处理任务错误
        
        Args:
            task_id: 任务ID
            error: 错误信息
        """
        # 实现错误处理逻辑
        pass
    
    def handle_process_completed(self, task_id: str, output_path: str):
        """处理任务完成
        
        Args:
            task_id: 任务ID
            output_path: 输出文件路径
        """
        # 实现完成处理逻辑
        pass
    
    def _handle_notification_info(self, event):
        """处理信息通知事件
        
        Args:
            event: 信息通知事件
        """
        title = event.title or NotificationTitle.NONE_TITLE.value
        content = event.content or ""
        self._display_info(title, content)

    def _handle_notification_success(self, event):
        """处理成功通知事件
        
        Args:
            event: 成功通知事件
        """
        title = event.title or NotificationTitle.NONE_TITLE.value
        content = event.content or ""
        self._display_success(title, content)

    def _handle_notification_warning(self, event):
        """处理警告通知事件
        
        Args:
            event: 警告通知事件
        """
        title = event.title or NotificationTitle.NONE_TITLE.value
        content = event.content or ""
        self._display_warning(title, content)

    def _handle_notification_error(self, event):
        """处理错误通知事件
        
        Args:
            event: 错误通知事件
        """
        title = event.title or NotificationTitle.NONE_TITLE.value
        content = event.content or ""
        self._display_error(title, content)

    def _handle_task_added_event(self, event: TaskAddedEvent):
        """处理任务添加事件，切换到任务视图
        
        Args:
            event: 任务添加事件
        """
        # 切换到任务视图
        self.switchTo(self.task_view)
        logger.debug(f"任务添加，切换到任务视图: {event.task_id}")