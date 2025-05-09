#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
拖放区域组件 - 通用的文件拖放区域
"""

import os

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtWidgets import QVBoxLayout, QLabel

from qfluentwidgets import CardWidget, FluentIcon, TitleLabel, BodyLabel
from dependency_injector.wiring import Provide, inject
from loguru import logger

from core.services.config_service import ConfigService
from core.services.notification_service import NotificationService
from core.services.error_handling_service import ErrorHandlingService
from core.containers import AppContainer # 导入 AppContainer
from core.utils import file_utils
from core.utils.file_utils import FileSystemUtils
from core.models.error_model import ErrorCategory, ErrorPriority
from core.events import event_bus, EventTypes, RequestAddTasksEvent, FilesDroppedEvent


class DropArea(CardWidget):
    """通用拖放区域，支持文件和文件夹拖放"""
    
    @inject
    def __init__(
        self,
        parent=None,
        translator: callable = Provide[AppContainer.translation_function],
        config_service: ConfigService = Provide[AppContainer.config_service],
        notification_service: NotificationService = Provide[AppContainer.notification_service],
        error_service: ErrorHandlingService = Provide[AppContainer.error_handling_service]
    ):
        """初始化拖放区域组件
        
        Args:
            parent: 父组件
        """
        super().__init__(parent)
        self._ = translator # 赋值翻译函数
        
        # 当前是否有拖拽悬停在区域上
        self._is_dragging_over = False
        
        # 当前是否有鼠标悬停在区域上
        self._is_hovered = False
        
        # 初始化服务 (通过构造函数注入)
        self.config_service = config_service
        self.notification_service = notification_service
        self.error_service = error_service
        
        # 设置对象名称
        self.setObjectName("dropArea")
        
        # 初始化UI
        self._init_ui()
        
        # 启用接收拖放
        self.setAcceptDrops(True)
        
        # 设置背景透明
        self.setStyleSheet("background-color: transparent;")
        
        # 监听主题变化
        from qfluentwidgets import qconfig
        qconfig.themeChanged.connect(self._update_icon)

    def _init_ui(self):
        """初始化UI"""
        # 设置尺寸
        self.setMinimumSize(600, 280)
        self.setMaximumWidth(800)
        
        # 创建布局
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(20)
        layout.setContentsMargins(40, 30, 40, 30)
        
        # 添加图标
        self.icon_label = QLabel()
        self._update_icon()
        self.icon_label.setAlignment(Qt.AlignCenter)
        
        # 添加标签
        self.title_label = TitleLabel(self._("拖放音频、视频文件或文件夹"))
        self.title_label.setAlignment(Qt.AlignCenter)
        
        self.or_label = BodyLabel(self._("或者"))
        self.or_label.setAlignment(Qt.AlignCenter)
        
        self.click_label = BodyLabel(self._("点击此处选择文件"))
        self.click_label.setAlignment(Qt.AlignCenter)
        
        # 暂时隐藏
        # self.right_click_label = BodyLabel(self._("右键点击选择文件夹"))
        self.right_click_label = BodyLabel("")
        self.right_click_label.setAlignment(Qt.AlignCenter)
        
        # 添加到布局
        layout.addWidget(self.icon_label)
        layout.addWidget(self.title_label)
        layout.addWidget(self.or_label)
        layout.addWidget(self.click_label)
        layout.addWidget(self.right_click_label)
    
    def _update_icon(self):
        """更新图标，根据当前主题设置合适的图标"""
        self.icon_label.setPixmap(FluentIcon.FOLDER_ADD.icon().pixmap(64, 64))
    
    def _process_selected_paths(self, paths, last_directory_update=None):
        """处理选择的文件或文件夹路径
        
        Args:
            paths: 文件或文件夹路径列表
            last_directory_update: 用于更新上次目录的路径，如果为None则不更新
        """
        if not paths:
            # 用户取消选择，静默忽略
            logger.debug("用户取消了选择")
            return
            
        # 过滤文件
        files = file_utils.files_filter(paths)
        
        # 发布文件拖放事件
        if files:
            # 创建文件拖放事件
            files_dropped_event = FilesDroppedEvent(
                file_paths=files
            )
            # 发布事件
            event_bus.publish(EventTypes.FILES_DROPPED, files_dropped_event)

            # 更新上次打开的目录
            if last_directory_update and files:
                self.config_service.set_last_directory(last_directory_update)
    
    def _select_files(self):
        """打开文件选择对话框"""
        try:
            # 从配置服务获取上次打开的目录
            last_directory = self.config_service.get_last_directory()
            
            # 使用FileSystemUtils的通用方法创建文件对话框
            files, _ = FileSystemUtils.create_file_dialog(
                parent=self,
                title=self._("选择音频/视频文件"),
                last_directory=last_directory
            )
            
            # 如果有选择文件
            if files:
                # 保存最后打开的目录
                directory = os.path.dirname(files[0])
                self.config_service.set_last_directory(directory)
                
                # 发布文件拖放事件
                files_dropped_event = FilesDroppedEvent(
                    file_paths=files
                )
                event_bus.publish(EventTypes.FILES_DROPPED, files_dropped_event)
                
        except Exception as e:
            logger.error(f"选择文件失败: {str(e)}")
            # 使用错误处理服务处理异常
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.GENERAL,
                    ErrorPriority.MEDIUM,
                    "DropArea._select_files",
                    user_visible=True
                )
    
    def _select_folder(self):
        """打开文件夹选择对话框"""
        try:
            # 从配置服务获取上次打开的目录
            last_directory = self.config_service.get_last_directory()
            
            # 使用FileSystemUtils的通用方法创建文件夹对话框
            folder = FileSystemUtils.create_folder_dialog(
                parent=self,
                title=self._("选择包含音频/视频文件的文件夹"),
                last_directory=last_directory
            )
            
            # 处理选择的文件夹
            self._process_selected_paths([folder], folder if folder else None)
        except Exception as e:
            logger.error(f"选择文件夹失败: {str(e)}")
            # 使用错误处理服务处理异常
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.GENERAL,
                    ErrorPriority.MEDIUM,
                    "DropArea._select_folder",
                    user_visible=True
                )
    
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            self._select_files()
        elif event.button() == Qt.RightButton:
            # 右键点击选择文件夹
            self._select_folder()
        super().mousePressEvent(event)
    
    def dragEnterEvent(self, event):
        """处理拖拽进入事件"""
        # 检查是否包含文件
        if event.mimeData().hasUrls():
            # 检查是否有支持的文件或文件夹
            has_valid_item = False
            
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                
                # 检查是否是文件或目录
                if os.path.isfile(file_path):
                    # 如果是文件，检查是否有效
                    ext = file_utils.get_file_extension(file_path)
                    if ext in file_utils.get_supported_media_extensions():
                        has_valid_item = True
                        break
                elif os.path.isdir(file_path):
                    # 目录始终接受
                    has_valid_item = True
                    break
            
            if has_valid_item:
                self._is_dragging_over = True
                
                # 更新标签文本和图标
                self._update_icon()
                self.title_label.setText(self._("释放鼠标添加文件"))
                self.or_label.setText("")
                self.click_label.setText("")
                self.right_click_label.setText("")
                
                # 接受事件
                event.acceptProposedAction()
                
                # 重绘组件
                self.update()
                return
        
        # 如果没有支持的文件，忽略事件
        event.ignore()
    
    def dragLeaveEvent(self, event):
        """处理拖拽离开事件"""
        self._is_dragging_over = False
        
        # 恢复标签文本和图标
        self._update_icon()
        self.title_label.setText(self._("拖放音频、视频文件或文件夹"))
        self.or_label.setText(self._("或者"))
        self.click_label.setText(self._("点击此处选择文件"))
        # 暂时隐藏
        # self.right_click_label.setText(self._("右键点击选择文件夹"))
        self.right_click_label.setText("")
        
        # 重绘组件
        self.update()
    
    def dropEvent(self, event):
        """处理拖拽放置事件"""
        # 重置拖拽悬停状态
        self._is_dragging_over = False
        
        # 获取拖放的URL
        urls = event.mimeData().urls()
        
        # 提取本地文件路径
        file_paths = [url.toLocalFile() for url in urls]
        
        # 使用文件工具类处理文件路径
        files = file_utils.files_filter(file_paths)
        
        # 如果有文件
        if files:
            # 更新上次目录
            first_path = files[0]
            if os.path.isfile(first_path):
                self.config_service.set_last_directory(os.path.dirname(first_path))
            else:
                self.config_service.set_last_directory(first_path)
            
            # 发布文件拖放事件
            files_dropped_event = FilesDroppedEvent(
                file_paths=files
            )
            event_bus.publish(EventTypes.FILES_DROPPED, files_dropped_event)
        
        # 接受事件
        event.acceptProposedAction()
        
        # 恢复标签文本和图标
        self._update_icon()
        self.title_label.setText(self._("拖放音频、视频文件或文件夹"))
        self.or_label.setText(self._("或者"))
        self.click_label.setText(self._("点击此处选择文件"))
        # 暂时隐藏
        # self.right_click_label.setText(self._("右键点击选择文件夹"))
        self.right_click_label.setText("")
        
        # 重绘组件
        self.update()
    
    def enterEvent(self, event):
        """鼠标进入事件"""
        self._is_hovered = True
        self.setCursor(Qt.PointingHandCursor)  # 设置为手型光标
        
        # 更新图标
        self._update_icon()
        
        self.update()  # 重绘组件
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """鼠标离开事件"""
        self._is_hovered = False
        self.setCursor(Qt.ArrowCursor)  # 恢复默认光标
        
        # 更新图标
        self._update_icon()
        
        self.update()  # 重绘组件
        super().leaveEvent(event)
    
    def paintEvent(self, event):
        """绘制组件"""
        # 不调用父类的paintEvent，以避免绘制卡片背景
        # super().paintEvent(event)
        
        # 创建绘制器
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # 设置边框参数
        margin = 10
        radius = 15  # 圆角半径
        
        # 根据状态绘制不同效果
        if self._is_dragging_over:
            # 拖拽状态下使用半透明蓝色背景和蓝色虚线边框
            # 先绘制圆角矩形背景
            painter.setBrush(QColor(52, 152, 219, 30))  # 更淡的蓝色背景
            painter.setPen(Qt.NoPen)  # 无边框
            painter.drawRoundedRect(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin, radius, radius)
            
            # 再绘制蓝色虚线边框
            pen = QPen(QColor(52, 152, 219))
            pen.setStyle(Qt.DashLine)
            pen.setWidth(3)
            pen.setDashPattern([8, 4])  # 8像素线段，4像素空白
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)  # 清除画刷
            painter.drawRoundedRect(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin, radius, radius)
        else:
            # 非拖拽状态
            if self._is_hovered:
                # 悬停状态下使用淡灰色背景
                painter.setBrush(QColor(200, 200, 200, 20))  # 非常淡的灰色背景
                painter.setPen(Qt.NoPen)  # 无边框
                painter.drawRoundedRect(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin, radius, radius)
            
            # 绘制灰色虚线边框
            pen = QPen(QColor(120, 120, 120))  # 灰色边框
            pen.setStyle(Qt.DashLine)  # 设置为虚线
            pen.setWidth(2)  # 设置线宽
            pen.setDashPattern([8, 4])  # 8像素线段，4像素空白
            painter.setPen(pen)
            painter.setBrush(Qt.NoBrush)  # 清除画刷
            painter.drawRoundedRect(margin, margin, self.width() - 2 * margin, self.height() - 2 * margin, radius, radius)
        
        # 结束绘制器
        painter.end() 