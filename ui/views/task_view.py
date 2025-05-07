#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
转写任务视图 - 处理转写任务的主视图

主要职责：
1. 提供用户界面，允许添加、删除、开始转写任务
2. 使用TaskService管理任务状态和计时器，减少冗余代码
3. 使用TaskTableManager管理任务表格显示和按钮交互
4. 使用TranscriptViewer管理转写结果的显示
5. 实现拖放功能，支持拖拽文件到视图中

优化重点：
6. 简化状态管理，使用TaskService的接口管理任务状态
7. 移除视图级别的计时器，完全依赖TaskService进行时间管理
8. 支持批量添加文件和文件夹
"""

import os
from typing import List
from loguru import logger

from PySide6.QtCore import Qt, Signal, QEvent, Slot, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QFrame, QHeaderView, QTableWidgetItem, QFileDialog, QAbstractItemView
)
from dependency_injector.wiring import Provide, inject

from qfluentwidgets import (
    TableWidget, PushButton, SubtitleLabel, 
    BodyLabel, ToolButton, FluentIcon,
    InfoBar, TextBrowser, TitleLabel, PrimaryPushButton
)

from core.models.model_data import ModelData
from core.utils.file_utils import FileSystemUtils, get_supported_media_extensions
from core.models.notification_model import NotificationTitle, NotificationContent
from core.models.task_model import ProcessStatus
from core.models.config import cfg
from core.services.config_service import ConfigService
from core.services.transcription_service import TranscriptionService
from core.services.audio_service import AudioService
from core.services.task_service import TaskService
from core.services.notification_service import NotificationService
from core.services.error_handling_service import ErrorHandlingService, ErrorCategory, ErrorPriority, ErrorInfo
from ui.components.task_table_manager import TaskTableManager
from ui.components.transcript_viewer import TranscriptViewer
from core.events import (
    event_bus, EventTypes,
    RequestAddTasksEvent, RequestRemoveTaskEvent, RequestClearTasksEvent,
    RequestStartProcessingEvent, RequestCancelProcessingEvent, TaskAddedEvent,
    TaskRemovedEvent, TaskTimerUpdatedEvent, TaskStateChangedEvent,
    TranscriptionStartedEvent, TranscriptionCompletedEvent # 添加全局事件
)
from core.models.transcription_model import TranscriptionParameters

class TaskView(QWidget):
    """任务视图"""
    # 定义用于线程安全更新TaskTableManager的信号
    requestAddTask = Signal(str, str, str, str) # task_id, file_path, status_text, duration
    requestRemoveTask = Signal(str)             # task_id
    requestUpdateStatus = Signal(str, str)      # task_id, status_text
    requestUpdateProgress = Signal(str, float)  # task_id, progress
    requestUpdateDuration = Signal(str, str)    # task_id, duration_text
    requestUpdateActionButtons = Signal(str, bool)# task_id, is_active
    
    def __init__(
        self, 
        parent=None,
    ):
        super().__init__(parent)
        
        # 设置对象名称
        self.setObjectName("taskView")

        # 启用拖拽支持
        self.setAcceptDrops(True)
        
        # 初始化服务
        self._init_services()

        # 初始化UI
        self._init_ui()
        
        # 初始化表格管理器
        self.table_manager = TaskTableManager(self.table, self) # Parent is TaskView
        
        # 初始化转录查看器
        self.transcript_viewer = TranscriptViewer(self.log_browser)

        # 添加UI计时器用于平滑更新时长
        self.ui_timer = QTimer(self)
        self.ui_timer.setInterval(1000) # 每秒触发
        self.ui_timer.timeout.connect(self._update_duration_display)

        # 初始化按钮状态
        self._update_button_states()
        
        # 模型加载等待标志
        self._is_waiting_for_model = False
        
        # 设置信号连接
        self._setup_connections()
        self._connect_table_manager_signals() # 新增：连接内部信号到TableManager的槽

    def __del__(self):
        """组件销毁时清理资源"""
        try:
            # 取消事件订阅
            event_bus.unsubscribe(EventTypes.TASK_STATE_CHANGED, self._handle_task_state_changed)
            event_bus.unsubscribe(EventTypes.TASK_ADDED, self._handle_task_added_event)
            event_bus.unsubscribe(EventTypes.MODEL_LOADED, self._handle_model_loaded)
            event_bus.unsubscribe(EventTypes.TRANSCRIPTION_PROCESS_INFO, self._handle_transcription_process_info)
            event_bus.unsubscribe(EventTypes.TASK_REMOVED, self._handle_task_removed_event)
            # 添加全局完成事件取消订阅
            event_bus.unsubscribe(EventTypes.TRANSCRIPTION_COMPLETED, self._handle_global_transcription_completed)
            # 移除对 TASK_TIMER_UPDATED 的取消订阅
            # event_bus.unsubscribe(EventTypes.TASK_TIMER_UPDATED, self._handle_task_timer_updated_event)
        except:
            # 忽略可能的异常
            pass
        
    @inject
    def _init_services(
        self, 
        config_service: ConfigService = Provide["config_service"],
        transcription_service: TranscriptionService = Provide["transcription_service"],
        task_service: TaskService = Provide["task_service"],
        notification_service: NotificationService = Provide["notification_service"],
        error_service: ErrorHandlingService = Provide["error_service"],
        model_service = Provide["model_service"]
    ):
        self.config_service = config_service
        self.transcription_service = transcription_service
        self.task_service = task_service
        self.notification_service = notification_service
        self.error_service = error_service
        self.model_service = model_service
    
    def _init_ui(self):
        """初始化UI"""
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(20)
        
        # 创建标题区域
        title_layout = QHBoxLayout()
        
        self.title_label = SubtitleLabel("任务列表", self)
        
        self.add_button = PushButton("添加", self)
        self.add_button.setIcon(FluentIcon.ADD)
        self.add_button.clicked.connect(self._on_add_clicked)
        
        self.clear_button = PushButton("清空", self)
        self.clear_button.setIcon(FluentIcon.DELETE)
        self.clear_button.setToolTip("清空列表")
        self.clear_button.clicked.connect(self._on_clear_clicked)
        
        title_layout.addWidget(self.title_label)
        title_layout.addStretch()
        title_layout.addWidget(self.add_button)
        title_layout.addWidget(self.clear_button)
        
        # 创建任务表格
        self.table = TaskTableWidget(self)
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["文件名", "处理时长", "状态", "操作"])
        
        # 连接表格点击事件
        self.table.cellClicked.connect(self._on_table_cell_clicked)
        
        # 创建处理日志区域
        log_layout = QVBoxLayout()
        log_title_layout = QHBoxLayout()
        
        self.log_title_label = SubtitleLabel("处理日志", self)
        self.clear_log_button = PushButton("清空日志", self)
        self.clear_log_button.setIcon(FluentIcon.DELETE)
        self.clear_log_button.clicked.connect(self._on_clear_log_clicked)
        
        log_title_layout.addWidget(self.log_title_label)
        log_title_layout.addStretch()
        log_title_layout.addWidget(self.clear_log_button)
        
        self.log_browser = TextBrowser(self)
        self.log_browser.setMinimumHeight(150)  # 设置最小高度
        
        log_layout.addLayout(log_title_layout)
        log_layout.addWidget(self.log_browser)
        
        # 创建开始处理按钮
        self.start_button = PrimaryPushButton("开始处理", self)
        self.start_button.setIcon(FluentIcon.PLAY)
        self.start_button.clicked.connect(self._on_start_clicked)
        
        # 添加到布局
        layout.addLayout(title_layout)
        layout.addWidget(self.table)
        layout.addLayout(log_layout)
        layout.addWidget(self.start_button, 0, Qt.AlignCenter)
    
    def _setup_connections(self):
        """设置信号连接"""
        # 连接表格管理器的按钮点击事件
        self.table_manager.connect_button_clicked("delete", self._on_delete_clicked)
        
        # 订阅事件总线事件
        event_bus.subscribe(EventTypes.TASK_STATE_CHANGED, self._handle_task_state_changed)
        event_bus.subscribe(EventTypes.TASK_ADDED, self._handle_task_added_event)
        # 添加MODEL_LOADED事件订阅
        event_bus.subscribe(EventTypes.MODEL_LOADED, self._handle_model_loaded)
        # 订阅统一的转录进度与文本事件
        event_bus.subscribe(EventTypes.TRANSCRIPTION_PROCESS_INFO, self._handle_transcription_process_info)
        event_bus.subscribe(EventTypes.TASK_REMOVED, self._handle_task_removed_event)
        # 添加全局完成事件订阅
        event_bus.subscribe(EventTypes.TRANSCRIPTION_COMPLETED, self._handle_global_transcription_completed)
        # 移除对 TASK_TIMER_UPDATED 的订阅，改用UI计时器主动更新
        # event_bus.subscribe(EventTypes.TASK_TIMER_UPDATED, self._handle_task_timer_updated_event)
    
    def _handle_task_state_changed(self, event: TaskStateChangedEvent):
        """处理任务状态变更事件 (事件总线回调)"""
        if hasattr(event, 'task_id') and hasattr(event, 'status'):
            # 发射信号，让槽函数在主线程更新UI
            self.requestUpdateStatus.emit(event.task_id, ProcessStatus.get_display_text(event.status))
            # 更新: 获取Task对象并调用is_active()方法
            task = self.task_service.get_task(event.task_id) # 依赖下一步添加 get_task 方法
            if task:
                is_active = task.is_active()
                self.requestUpdateActionButtons.emit(event.task_id, is_active)
            else:
                 logger.warning(f"无法在处理状态变更时找到任务: {event.task_id}")

            # 如果任务完成，处理完成逻辑 (这部分不直接更新UI，可以保留)
            if event.status == ProcessStatus.COMPLETED and event.output_path:
                self._on_task_completed(event.task_id, event.output_path)
        else:
             logger.warning(f"接收到无效的TASK_STATE_CHANGED事件: {event}")
    
    def _handle_transcription_process_info(self, event):
        """处理统一的转录进度与文本事件"""
        # 添加文本
        self.transcript_viewer.add_transcript_text(event.process_text)
        # 发射信号更新进度
        if hasattr(event, 'task_id') and hasattr(event, 'progress'):
             self.requestUpdateProgress.emit(event.task_id, event.progress)

    
    def _on_add_clicked(self):
        """添加按钮点击事件"""
        try:
            # 使用通用方法选择并添加文件
            self._select_files()
        except Exception as e:
            logger.error(f"添加文件失败: {str(e)}")
            
            # 使用ErrorHandlingService处理错误
            error_info = ErrorInfo(
                message=NotificationContent.FILE_ADD_FAILED.value.format(error_message=str(e)),
                exception=e,
                category=ErrorCategory.FILE_OPERATION,
                priority=ErrorPriority.MEDIUM,
                source="TaskView._on_add_clicked",
                user_visible=True
            )
            self.error_service.handle_error(error_info)
    
    def _select_files(self):
        """选择并添加文件的通用方法"""
        # 从配置服务获取上次打开的目录
        last_directory = self.config_service.get_last_directory()
        
        # 使用FileSystemUtils的通用方法创建文件对话框
        files, _ = FileSystemUtils.create_file_dialog(
            parent=self,
            title="选择音频/视频文件",
            last_directory=last_directory,
            extensions=get_supported_media_extensions()
        )
        
        # 如果有选择文件
        if files:
            # 保存最后打开的目录
            self.config_service.set_last_directory(os.path.dirname(files[0]))
            
            # 添加到任务列表
            self.add_tasks(files)
    
    def add_tasks(self, file_paths: List[str]):
        """添加任务"""
        # 发布请求添加任务事件
        event_data = RequestAddTasksEvent(file_paths=file_paths)
        event_bus.publish(EventTypes.REQUEST_ADD_TASKS, event_data)
        
        # 更新开始处理按钮状态
        self._update_button_states()
        
        logger.debug(f"发起添加任务请求: {len(file_paths)} 个文件")
    
    def _on_delete_clicked(self, task_id: str):
        """删除按钮点击事件
        
        Args:
            task_id: 任务ID
        """
        # 发布请求移除任务事件
        event_data = RequestRemoveTaskEvent(task_id=task_id)
        event_bus.publish(EventTypes.REQUEST_REMOVE_TASK, event_data)
        
        # 更新开始处理按钮状态
        self._update_button_states()
        
        logger.info(f"发起移除任务请求: {task_id}")
    
    def _on_clear_clicked(self):
        """清空按钮点击事件"""
        # 发布请求清空任务事件
        event_data = RequestClearTasksEvent()
        event_bus.publish(EventTypes.REQUEST_CLEAR_TASKS, event_data)
        
        # 更新所有按钮状态
        self._update_button_states()
        
        logger.info("发起清空任务请求")
    
    def _on_clear_log_clicked(self):
        """清空转录内容按钮点击事件"""
        self.transcript_viewer.clear_display()
    
    def _on_table_cell_clicked(self, row, column):
        """表格单元格点击事件
        
        Args:
            row: 行索引
            column: 列索引
        """
        # 只有点击文件名列(第0列)时才打开文件目录
        if column != 0:
            return
            
        # 获取任务ID
        task_id = self.table_manager.get_task_id_at_row(row)
        if not task_id:
            return
            
        # 获取文件路径
        file_path = self.task_service.get_task_file_path(task_id)
        if not file_path or not os.path.exists(file_path):
            return
            
        # 检查是否有自定义输出目录
        output_directory = ""
        if hasattr(cfg, 'output_directory') and hasattr(cfg.output_directory, 'value'):
            output_directory = cfg.output_directory.value
        
        # 确定输出文件目录
        if output_directory and os.path.isdir(output_directory):
            # 使用指定的输出目录
            file_dir = output_directory
        else:
            # 使用源文件目录
            file_dir = FileSystemUtils.get_file_dir(file_path)
        
        # 打开文件所在目录
        if not FileSystemUtils.open_directory(file_dir):
            # 使用ErrorHandlingService处理错误
            error_info = ErrorInfo(
                message=NotificationContent.DIRECTORY_OPEN_FAILED.value.format(directory_path=file_dir),
                category=ErrorCategory.FILE_OPERATION,
                priority=ErrorPriority.MEDIUM,
                source="TaskView._on_table_cell_clicked",
                user_visible=True
            )
            self.error_service.handle_error(error_info)
    
    
    def _update_button_states(self):
        """更新按钮状态"""
        # 检查是否有任务正在处理
        is_processing = len(self.task_service.get_active_tasks()) > 0
        
        # 获取待处理任务列表
        pending_tasks = self.task_service.get_pending_tasks()
        has_pending_tasks = len(pending_tasks) > 0
        
        # 更新文件操作按钮状态
        self.add_button.setEnabled(not is_processing)
        self.clear_button.setEnabled(not is_processing and self.task_service.get_task_count() > 0)
        
        # 更新表格中所有按钮状态
        self.table_manager.update_all_action_buttons(is_processing)
        
        # 更新开始处理按钮状态
        if is_processing:
            self.start_button.setText("取消处理")
            self.start_button.setIcon(FluentIcon.CANCEL)
            self.start_button.setEnabled(True)  # 确保取消按钮始终可用
        else:
            self.start_button.setText("开始处理")
            self.start_button.setIcon(FluentIcon.PLAY)
            # 只有在有待处理任务时才启用按钮
            self.start_button.setEnabled(has_pending_tasks)

        # 根据是否有任务在处理来启动或停止UI计时器
        if is_processing and not self.ui_timer.isActive():
            self.ui_timer.start()
            # 计时器启动后会在1秒内触发更新
        elif not is_processing and self.ui_timer.isActive():
            self.ui_timer.stop()
    
    def dragEnterEvent(self, event):
        """拖拽进入事件"""
        # 只接受文件拖拽
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        """拖拽移动事件"""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
    
    def dropEvent(self, event):
        """拖拽放下事件"""
        # 检查是否有任务正在处理
        if len(self.task_service.get_active_tasks()) > 0:
            return
            
        # 获取拖拽的文件URL列表
        urls = event.mimeData().urls()
        if not urls:
            return
            
        # 转换为本地文件路径
        files = []
        for url in urls:
            file_path = url.toLocalFile()
            # 接受文件和文件夹
            if os.path.exists(file_path):
                files.append(file_path)
        
        # 添加文件
        if files:
            self.add_tasks(files)
            event.acceptProposedAction()
    
    def event(self, event):
        """重写事件处理函数，用于处理鼠标悬停事件"""
        if event.type() == QEvent.HoverEnter or event.type() == QEvent.HoverMove:
            # 获取鼠标位置下的表格项
            pos = self.table.mapFromGlobal(self.cursor().pos())
            item = self.table.itemAt(pos)
            
            # 如果鼠标在文件名列上，设置为手型光标
            if item and self.table.column(item) == 0:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
                
        elif event.type() == QEvent.HoverLeave:
            # 鼠标离开时恢复默认光标
            self.setCursor(Qt.ArrowCursor)
            
        return super().event(event)
    
    def _on_task_completed(self, task_id: str, output_path: str):
        """任务完成处理
        
        Args:
            task_id: 任务ID
            output_path: 输出文件路径
        """
        # 获取任务文件名
        file_name = self.task_service.get_task_file_name(task_id)
        if file_name:
            # 添加成功消息到转录查看器
            output_name = FileSystemUtils.get_file_name(output_path)
            self.transcript_viewer.add_success_message(f"任务完成: {file_name} -> {output_name}")
        
        # 处理下一个任务
        self._process_next_task()
    
    def _process_next_task(self):
        """处理下一个任务"""
        # 获取所有待处理的任务
        pending_tasks = self.task_service.get_pending_tasks()
        
        # 如果还有待处理的任务，处理下一个
        if pending_tasks:
            # 发布请求开始处理事件
            event_data = RequestStartProcessingEvent()
            event_bus.publish(EventTypes.REQUEST_START_PROCESSING, event_data)
    
    def _on_start_clicked(self):
        """开始处理按钮点击事件"""
        # 检查是否有任务正在处理
        if len(self.task_service.get_active_tasks()) > 0:
            # 发布请求取消处理事件
            event_data = RequestCancelProcessingEvent()
            event_bus.publish(EventTypes.REQUEST_CANCEL_PROCESSING, event_data)
            
            # 更新按钮状态为"正在取消..."
            self.start_button.setText("正在取消...")
            self.start_button.setEnabled(False)  # 取消过程中禁用按钮，防止重复点击
            
            # 添加到转录查看器
            self.transcript_viewer.add_transcript_text("正在取消任务，请稍候...")
            return
        
        # 获取所有待处理的任务
        pending_tasks = self.task_service.get_pending_tasks()
        
        # 如果没有待处理的任务，记录日志并返回
        if not pending_tasks:
            logger.debug("没有待处理的任务")
            return
            
        # 获取当前要使用的模型名称
        model_name = "medium"  # 默认值
        if hasattr(self.transcription_service, 'transcription_parameters'):
            model_name = self.transcription_service.transcription_parameters.model_name
        
        # 检查模型是否存在
        model_data = self.model_service.get_model_data(model_name)

        # 如果模型存在，检查是否已加载
        if model_data and model_data.is_exists:
            # self.transcript_viewer.add_system_message(f"模型 {model_name} 已找到，准备开始处理...")
            
            # 检查模型是否已加载
            if self.model_service.is_model_loaded():
                # 如果已加载，直接开始处理任务
                self._start_processing_tasks()
            else:
                # 如果未加载，需要先加载模型
                self._is_waiting_for_model = True
                # 更新UI状态
                # self.start_button.setText("正在加载模型...")
                self.start_button.setEnabled(False)
                # 添加到转录查看器
                # self.transcript_viewer.add_system_message(f"模型 {model_name} 未加载，正在加载...")
                # 启动模型加载
                self.model_service.load_model(model_name)
        else:
            # 如果模型不存在，提示用户去设置页面下载
            error_message = f"模型 '{model_name}' 未找到或无效，请前往设置页面下载所需模型。"
            logger.warning(error_message)
            self.transcript_viewer.add_error_message(error_message)
            # 更新按钮状态，以防万一在检查期间状态未更新
            self._update_button_states()

    def _start_processing_tasks(self):

        # 发布全局开始事件
        try:
            # 确保 transcription_service 已注入
            if hasattr(self, 'transcription_service') and self.transcription_service:
                 params = self.transcription_service.transcription_parameters
                 global_start_event = TranscriptionStartedEvent(parameters=params)
                 event_bus.publish(EventTypes.TRANSCRIPTION_STARTED, global_start_event)
                 logger.debug("已发布全局 TranscriptionStartedEvent")
            else:
                 logger.warning("无法发布全局 TranscriptionStartedEvent: transcription_service 未初始化")
        except Exception as e:
            logger.error(f"发布全局 TranscriptionStartedEvent 失败: {e}")

        # 发布请求开始处理事件
        model_name = self.transcription_service.transcription_parameters.model_name
        event_data = RequestStartProcessingEvent(model_name=model_name)
        event_bus.publish(EventTypes.REQUEST_START_PROCESSING, event_data)

        # 更新按钮状态
        self._update_button_states()
        
        logger.info("已发起开始处理请求")
    
    # 移除 _on_task_status_updated 方法，逻辑已移至 _handle_task_state_changed 并通过信号触发

    def _handle_task_added_event(self, event: TaskAddedEvent):
        """处理任务添加事件 (事件总线回调)"""
        if hasattr(event, 'task_id') and hasattr(event, 'file_path'):
             # 发射信号，让槽函数在主线程更新UI
             # 使用默认等待状态，因为TaskAddedEvent不包含status
             self.requestAddTask.emit(
                 event.task_id,
                 event.file_path,
                 ProcessStatus.get_display_text(ProcessStatus.WAITING),
                 "00:00" # 初始时长
             )
             # 更新按钮状态 (可以保留，因为列表内容变化可能影响按钮)
             self._update_button_states()
             logger.debug(f"任务添加事件处理: {event.task_id}, 发射信号更新UI")
        else:
            logger.warning(f"接收到无效的TASK_ADDED事件: {event}")

    def _handle_model_loaded(self, event):
        """处理模型加载完成事件"""
        # 如果之前因为模型未加载而等待，现在开始处理
        if self._is_waiting_for_model:
            self._is_waiting_for_model = False
            self.transcript_viewer.add_system_message(f"模型 {event.model_name} 加载完成，开始处理任务...")
            self._start_processing_tasks() # 重新尝试开始处理

    def _connect_table_manager_signals(self):
        """连接内部信号到TaskTableManager的槽函数"""
        self.requestAddTask.connect(self.table_manager.add_task_to_table)
        self.requestRemoveTask.connect(self.table_manager.remove_task)
        self.requestUpdateStatus.connect(self.table_manager.update_task_status)
        self.requestUpdateProgress.connect(self.table_manager.update_task_progress)
        self.requestUpdateDuration.connect(self.table_manager.update_task_duration)
        self.requestUpdateActionButtons.connect(self.table_manager.update_task_action_buttons)

    def _handle_task_removed_event(self, event: TaskRemovedEvent):
        """处理任务移除事件 (事件总线回调)"""
        if hasattr(event, 'task_id'):
            # 发射信号，让槽函数在主线程更新UI
            self.requestRemoveTask.emit(event.task_id)
            # 更新全局按钮状态
            self._update_button_states()
        else:
            logger.warning(f"接收到无效的TASK_REMOVED事件: {event}")

    def _update_duration_display(self):
        """由ui_timer触发，主动更新活跃任务的时长显示"""
        active_id = self.task_service.active_task_id
        if active_id:
            try:
                # 主动获取最新时长
                duration = self.task_service.get_task_duration(active_id)
                # 发射信号更新UI (通过信号槽保证线程安全)
                self.requestUpdateDuration.emit(active_id, duration)
            except Exception as e:
                # 添加错误处理，防止计时器因异常停止
                logger.error(f"更新任务 {active_id} 时长显示时出错: {e}")
                # 可以考虑在这里停止计时器，避免连续出错
                # self.ui_timer.stop()
        else:
            # 如果没有活跃任务了，确保计时器停止
            if self.ui_timer.isActive():
                self.ui_timer.stop()

    def _handle_global_transcription_completed(self, event):
        """处理全局转录完成事件"""
        logger.info("收到全局转录完成事件")
        # 更新按钮状态
        self._update_button_states()
        # 记录日志
        logger.info("所有任务处理完成")
        # 显示成功消息
        self.transcript_viewer.add_success_message("所有任务处理完成")

class TaskTableWidget(TableWidget):
    """自定义表格控件，用于处理鼠标悬停事件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.viewport().setMouseTracking(True)
        self.current_column = -1
    
    def mouseMoveEvent(self, event):
        """鼠标移动事件，实现指针变化"""
        # 获取鼠标位置下的单元格
        item = self.itemAt(event.pos())
        if item:
            column = self.column(item)
            
            # 如果鼠标在文件名列上，设置为手型光标
            if column == 0:
                self.setCursor(Qt.PointingHandCursor)
                self.current_column = 0
            elif self.current_column == 0:
                self.setCursor(Qt.ArrowCursor)
                self.current_column = column
        else:
            if self.current_column == 0:
                self.setCursor(Qt.ArrowCursor)
                self.current_column = -1
        
        super().mouseMoveEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        self.setCursor(Qt.ArrowCursor)
        self.current_column = -1
        super().leaveEvent(event)
