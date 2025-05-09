#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
任务表格管理器 - 负责处理表格相关操作
"""

from typing import Optional, Dict, List, Tuple, Callable
from loguru import logger

from PySide6.QtCore import Qt, QObject, Slot
from PySide6.QtWidgets import QWidget, QHBoxLayout, QTableWidgetItem, QHeaderView, QAbstractItemView
from qfluentwidgets import TableWidget, ToolButton, FluentIcon, SmoothMode

from core.models.task_model import ProcessStatus, Task
from core.utils.file_utils import FileSystemUtils
from core.services.task_service import TaskService
from dependency_injector.wiring import Provide, inject
from core.containers import AppContainer
from core.events import event_bus, EventTypes, TaskStateChangedEvent, TaskAddedEvent, TaskRemovedEvent, TaskTimerUpdatedEvent

class TaskTableManager(QObject):
    """任务表格管理器，负责处理表格相关操作"""
    
    @inject
    def __init__(
        self,
        table_widget: TableWidget,
        parent: QObject = None,
        translator: callable = Provide[AppContainer.translation_function],
        task_service: TaskService = Provide[AppContainer.task_service] # 直接注入task_service
    ):
        """初始化任务表格管理器
        
        Args:
            table_widget: 表格控件实例
            parent: 父对象
            translator: 翻译函数
            task_service: 任务服务实例
        """
        super().__init__(parent)
        self._ = translator # 赋值翻译函数
        self.table = table_widget
        
        # 设置表格外观和对齐方式
        self._setup_table_appearance()
        
        # 存储按钮回调函数，key为动作名称，value为回调函数
        self.button_callbacks = {}
        
        self.task_service = task_service
        self.initialize_from_task_service() # 直接调用初始化
        
    def initialize_from_task_service(self):
        """从任务服务初始化表格数据"""
        if not self.task_service:
            return
            
        # 清空表格
        self.clear_table()
        
        # 获取所有任务并添加到表格
        all_tasks = self.task_service.get_all_tasks()
        for task_id, task in all_tasks.items():
            file_path = task.file_path
            status_text = self._get_status_display_text(task.status)
            duration = self.task_service.get_task_duration(task_id)
            
            # 添加到表格
            self._add_task_to_table(
                task_id, 
                file_path,
                status_text,
                duration
            )
    
    def _get_status_display_text(self, status: ProcessStatus) -> str:
        """获取状态的显示文本
        
        Args:
            status: 状态枚举
            
        Returns:
            str: 状态显示文本
        """
        # 使用枚举的显示文本方法
        return ProcessStatus.get_display_text(status)
    
    def _on_button_clicked(self):
        """按钮点击事件处理函数
        
        使用事件委托模式处理按钮点击事件
        """
        # 获取发送信号的按钮
        button = self.sender()
        if not button:
            return
            
        # 获取按钮属性
        task_id = button.property("task_id")
        action = button.property("action")
        
        # 调用对应的回调函数
        if action in self.button_callbacks and task_id:
            self.button_callbacks[action](task_id)
    
    def add_task_to_table(self, task_id: str, file_path: str, status: str, duration: str = "00:00") -> int:
        """添加任务到表格
        
        Args:
            task_id: 任务ID
            file_path: 文件路径
            status: 状态文本
            duration: 时长文本，默认为"00:00"
            
        Returns:
            int: 添加的行索引
        """
        # 获取文件名
        file_name = FileSystemUtils.get_file_name(file_path)
        
        # 添加到表格
        row = self.table.rowCount()
        self.table.insertRow(row)
        
        # 设置文件名单元格 - 左对齐
        file_item = QTableWidgetItem(file_name)
        file_item.setData(Qt.UserRole, task_id)  # 存储任务ID
        file_item.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)  # 文件名左对齐
        self.table.setItem(row, 0, file_item)
        
        # 设置时长单元格 - 居中对齐
        duration_item = QTableWidgetItem(duration)
        duration_item.setTextAlignment(Qt.AlignCenter)  # 居中对齐
        self.table.setItem(row, 1, duration_item)
        
        # 设置状态单元格 - 居中对齐
        status_item = QTableWidgetItem(status)
        status_item.setTextAlignment(Qt.AlignCenter)  # 居中对齐
        self.table.setItem(row, 2, status_item)
        
        # 设置操作单元格
        self._create_action_buttons(row, task_id)
        
        return row
    
    def _create_action_buttons(self, row: int, task_id: str):
        """创建操作按钮
        
        Args:
            row: 行索引
            task_id: 任务ID
            is_active: 是否处于活动状态
        """
        # 创建操作按钮容器
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)  # 减小边距以便居中
        action_layout.setSpacing(4)
        action_layout.setAlignment(Qt.AlignCenter)  # 设置布局居中对齐
        
        # 添加删除按钮
        delete_button = ToolButton(FluentIcon.DELETE)
        delete_button.setToolTip(self._("删除"))
        delete_button.setProperty("task_id", task_id)
        delete_button.setProperty("action", "delete")
        delete_button.setEnabled(True)
        
        # 直接在创建按钮时连接信号
        if "delete" in self.button_callbacks:
            delete_button.clicked.connect(self._on_button_clicked)
        
        # 居中添加按钮
        action_layout.addWidget(delete_button, 0, Qt.AlignCenter)
        
        # 设置操作单元格
        self.table.setCellWidget(row, 3, action_widget)

        # 强制表格更新布局：确保按钮不会因为初始化时序问题而错位
        self.table.resizeRowToContents(row)
        
    def update_task_action_buttons(self, task_id: str, is_active: bool):
        """更新任务操作按钮状态
        单一任务颗粒度的更新，任务状态发生变化时，更新按钮状态
        
        Args:
            task_id: 任务ID
            is_active: 是否处于活动状态
        """
        row = self.find_task_row(task_id)
        if row < 0:
            return
            
        # 获取按钮容器
        button_container = self.table.cellWidget(row, 3)
        if not button_container:
            return
            
        # 更新删除按钮状态
        for button in button_container.findChildren(ToolButton):
            if button.property("action") == "delete":
                button.setEnabled(not is_active)
    
    def update_all_action_buttons(self, is_active: bool = False):
        """更新所有操作按钮状态
        整体任务颗粒度的更新，整体任务状态发生变化时，更新按钮状态  
        
        Args:
            is_active: 是否处于活动状态
        """
        for row in range(self.table.rowCount()):
            button_container = self.table.cellWidget(row, 3)
            if button_container:
                for button in button_container.findChildren(ToolButton):
                    if button.property("action") == "delete":
                        button.setEnabled(not is_active)
    
    def update_task_status(self, task_id: str, status_text: str) -> bool:
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status_text: 状态文本
            
        Returns:
            bool: 是否成功更新
        """
        row = self.find_task_row(task_id)
        if row < 0:
            return False
        
        # 更新状态单元格
        status_item = self.table.item(row, 2)
        if status_item:
            status_item.setText(status_text)
            status_item.setTextAlignment(Qt.AlignCenter)  # 确保居中对齐
            return True
        
        return False
    
    def update_task_progress(self, task_id: str, progress: float) -> bool:
        """更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度值 (0.0-1.0)
            
        Returns:
            bool: 是否成功更新
        """
        row = self.find_task_row(task_id)
        if row < 0:
            return False
        
        # 更新状态单元格，显示进度百分比
        status_item = self.table.item(row, 2)
        if status_item:
            progress_percent = int(progress * 100)
            status_item.setText(f"{progress_percent}%")
            return True
        
        return False
    
    def update_task_duration(self, task_id: str, duration_text: str) -> bool:
        """更新任务时长
        
        Args:
            task_id: 任务ID
            duration_text: 时长文本
            
        Returns:
            bool: 是否成功更新
        """
        row = self.find_task_row(task_id)
        if row < 0:
            return False
        
        # 更新时长单元格
        duration_item = self.table.item(row, 1)
        if duration_item:
            duration_item.setText(duration_text)
            duration_item.setTextAlignment(Qt.AlignCenter)  # 确保居中对齐
            return True
        
        return False
    
    def remove_task(self, task_id: str) -> bool:
        """从表格中删除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功删除
        """
        row = self.find_task_row(task_id)
        if row < 0:
            return False
        
        # 从表格中删除该行
        self.table.removeRow(row)
        return True
    
    def find_task_row(self, task_id: str) -> int:
        """查找任务在表格中的行索引
        
        Args:
            task_id: 任务ID
            
        Returns:
            int: 行索引，如果未找到则返回-1
        """
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.data(Qt.UserRole) == task_id:
                return row
        return -1
    
    def clear_table(self):
        """清空表格"""
        self.table.setRowCount(0)
    
    def get_all_task_ids(self) -> List[str]:
        """获取表格中所有任务ID
        
        Returns:
            List[str]: 任务ID列表
        """
        task_ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                task_id = item.data(Qt.UserRole)
                if task_id:
                    task_ids.append(task_id)
        return task_ids
    
    def get_task_id_at_row(self, row: int) -> Optional[str]:
        """获取指定行的任务ID
        
        Args:
            row: 行索引
            
        Returns:
            Optional[str]: 任务ID，如果未找到则返回None
        """
        if row < 0 or row >= self.table.rowCount():
            return None
        
        item = self.table.item(row, 0)
        if item:
            return item.data(Qt.UserRole)
        
        return None
    
    def connect_button_clicked(self, action: str, callback: Callable[[str], None]):
        """注册按钮点击事件回调函数
        
        使用事件委托模式处理按钮点击事件，提高效率
        
        Args:
            action: 按钮动作，如"delete"
            callback: 回调函数，接收task_id参数
        """
        # 保存回调函数
        self.button_callbacks[action] = callback
        
        # 为已有按钮连接信号
        self._connect_existing_buttons(action)
    
    def _connect_existing_buttons(self, action: str):
        """为已有的按钮连接信号
        
        Args:
            action: 按钮动作，如"delete"
        """
        # 仅在初始化表格内容时需要调用一次
        for row in range(self.table.rowCount()):
            button_container = self.table.cellWidget(row, 3)
            if button_container:
                for button in button_container.findChildren(ToolButton):
                    if button.property("action") == action and not button.receivers(button.clicked):
                        button.clicked.connect(self._on_button_clicked)
    
    def _setup_table_appearance(self):
        """设置表格外观和对齐方式"""
        # 设置表格选择行为 - 选择整行而非单个单元格
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        # self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        
        # 设置表格不可编辑
        self.table.setEditTriggers(TableWidget.NoEditTriggers)
        
        # 启用边框并设置圆角
        self.table.setBorderVisible(True)
        self.table.setBorderRadius(8)
        
        # 禁用自动换行
        self.table.setWordWrap(False)
        
        
        # 设置行高和垂直表头
        self.table.verticalHeader().setVisible(True)  # 显示行号
        self.table.verticalHeader().setDefaultSectionSize(40)  # 设置默认行高
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)  # 固定行高
        
        # 禁用平滑滚动以提高性能
        self.table.scrollDelagate.verticalSmoothScroll.setSmoothMode(SmoothMode.NO_SMOOTH)
        
        # 确保表头已经设置
        if self.table.horizontalHeader().count() >= 4:
            # 设置表头对齐方式 - 所有表头居中对齐
            for col in range(self.table.columnCount()):
                header_item = self.table.horizontalHeaderItem(col)
                if header_item:
                    header_item.setTextAlignment(Qt.AlignCenter | Qt.AlignVCenter)  # 所有表头居中对齐
            
            # 设置列宽和调整模式
            header = self.table.horizontalHeader()
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)  # 文件名列自适应宽度
            
            # 如果需要固定其他列宽
            if self.table.columnCount() > 1:
                header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)  # 时长列固定宽度
                self.table.setColumnWidth(1, 80)  # 时长列宽
            
            if self.table.columnCount() > 2:
                header.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)  # 状态列固定宽度
                self.table.setColumnWidth(2, 115)  # 状态列宽
            
            if self.table.columnCount() > 3:
                header.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)  # 操作列固定宽度
                self.table.setColumnWidth(3, 80)  # 操作列宽 

    def get_status_item(self, task_id: str) -> Optional[QTableWidgetItem]:
        """获取任务状态单元格
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[QTableWidgetItem]: 状态单元格，如果未找到则返回None
        """
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 2)
            if item and item.data(Qt.UserRole) == task_id:
                return item
        return None 