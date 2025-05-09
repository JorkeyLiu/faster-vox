#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模型选择卡片组件 - 支持显示下载按钮和进度
"""

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QWidget, QLabel

from qfluentwidgets import (ComboBoxSettingCard, TransparentToolButton, 
                           FluentIcon, ToolTipFilter, ToolTipPosition)

from core.models.model_data import ModelData, ModelSize
from core.services.model_management_service import ModelManagementService
from dependency_injector.wiring import inject, Provide
from core.containers import AppContainer

from core.events import event_bus
from core.events.event_types import EventTypes, ModelEvent

class ModelSelectionCard(ComboBoxSettingCard):
    """模型选择卡片，支持显示下载按钮和进度"""
    
    @inject
    def __init__(self, configItem, icon, title, content=None, texts=None, parent=None,
                 translator: callable = Provide[AppContainer.translation_function],
                 model_service: ModelManagementService = Provide[AppContainer.model_service]): # model_service注入
        """初始化
        
        Args:
            configItem: 配置项
            icon: 图标
            title: 标题
            content: 内容描述
            texts: 选项文本列表
            parent: 父部件
            translator: 翻译函数
            model_service: 模型服务
        """
        self._ = translator # 赋值翻译函数
        self.model_service = model_service # 保存模型服务

        # 保存texts参数
        self.texts = texts or []
        
        # 调用父类构造函数
        # title 和 content 应该在 SettingsView 中被翻译后传入
        super().__init__(configItem, icon, title, content, texts, parent)
        
        # 创建下载按钮
        self.downloadButton = TransparentToolButton(FluentIcon.DOWNLOAD, self)
        self.downloadButton.setFixedSize(35, 35)
        self.downloadButton.setIconSize(QSize(16, 16))
        self.downloadButton.setToolTip(self._("下载模型"))
        self.downloadButton.installEventFilter(ToolTipFilter(self.downloadButton, 1000, ToolTipPosition.TOP))
        self.downloadButton.clicked.connect(self._on_download_clicked)
        
        # 创建同步按钮（重新下载）
        self.syncButton = TransparentToolButton(FluentIcon.SYNC, self)
        self.syncButton.setFixedSize(35, 35)
        self.syncButton.setIconSize(QSize(16, 16))
        self.syncButton.setToolTip(self._("重新下载模型"))
        self.syncButton.installEventFilter(ToolTipFilter(self.syncButton, 1000, ToolTipPosition.TOP))
        self.syncButton.clicked.connect(self._on_download_clicked)
        
        # 创建进度标签
        self.progressLabel = QLabel("0%", self)
        self.progressLabel.setFixedSize(35, 35)
        self.progressLabel.setAlignment(Qt.AlignCenter)
        
        # 获取下拉框的位置
        comboBoxIndex = self.hBoxLayout.indexOf(self.comboBox)
        
        # 如果找到下拉框
        if comboBoxIndex >= 0:
            # 添加一个弹性空间，使按钮靠近下拉框
            spacer = QWidget()
            spacer.setFixedWidth(10)  # 设置按钮和下拉框之间的间距
            
            # 在下拉框前插入按钮和标签
            self.hBoxLayout.insertWidget(comboBoxIndex, spacer)
            self.hBoxLayout.insertWidget(comboBoxIndex, self.downloadButton)
            self.hBoxLayout.insertWidget(comboBoxIndex, self.syncButton)
            self.hBoxLayout.insertWidget(comboBoxIndex, self.progressLabel)
            
            # 设置下拉框的最小宽度，确保它不会被挤压
            self.comboBox.setMinimumWidth(120)
        
        # 初始隐藏所有按钮和标签
        self.downloadButton.hide()
        self.syncButton.hide()
        self.progressLabel.hide()
        
        # 连接下拉框变更信号
        self.comboBox.currentTextChanged.connect(self._on_model_changed)
        
        # 订阅模型数据变更事件
        event_bus.subscribe(EventTypes.MODEL_DATA_CHANGED, self._on_model_data_changed)
        event_bus.subscribe(EventTypes.CUDA_ENV_INSTALL_COMPLETED, self._on_cuda_env_install_completed)

        # 初始化 UI
        self.init_ui()

    # init_ui 现在在 __init__ 中被调用，并且 model_service 已经通过构造函数注入
    def init_ui(self): # 移除 model_service 参数
        """初始化 UI"""
        self.current_model = self.get_selected_model()
        # self.model_service is already set in __init__
        self.update_ui(self.current_model, self.model_service.get_model_data(self.current_model))
    
    def _on_model_data_changed(self, event):
        """模型数据变更事件处理
        
        直接响应MODEL_DATA_CHANGED事件，不再依赖外部调用
        
        Args:
            event: 事件数据，包含model_name和model_data
        """
        self.update_ui(event.model_name, event.model_data)
    
    def set_download_progress(self, progress: float):
        """设置下载进度
        
        Args:
            model_name: 模型名称
            progress: 进度百分比 (0.0-1.0)
        """
        # 如果当前选中的是这个模型，更新进度显示
        progress_percent = int(progress * 100)
        self.progressLabel.setText(f"{progress_percent}%")
        
        # 确保下拉框在下载过程中保持禁用状态
        self.comboBox.setEnabled(False)
    
    def get_selected_model(self) -> str:
        """获取当前选中的模型名称"""
        # 直接获取当前文本
        display_name = self.comboBox.currentText()
        
        # 如果文本为空，返回默认值
        if not display_name:
            return ""
            
        # 将显示名称转换为模型名称
        model_name = None
        for size in ModelSize:
            if display_name == ModelSize.get_display_name(size.value):
                model_name = size.value
                break
                
        # 如果找不到对应的枚举值，则直接使用小写的文本
        if model_name is None:
            model_name = display_name.lower()
            
        return model_name
    
    def update_ui(self, model_name: str, model_data: ModelData):
        """根据模型数据更新UI
        
        Args:
            model_name: 模型名称
            model_data: 模型数据对象
        """
        # 如果当前选中的不是这个模型，直接返回
        self.current_model = self.get_selected_model()
        if self.current_model != model_name:
            return
        
        # 隐藏所有按钮和标签
        self.downloadButton.hide()
        self.syncButton.hide()
        self.progressLabel.hide()
        
        # 根据模型数据显示相应的按钮或标签
        if model_data.is_loading:
            # 正在加载中
            self.progressLabel.setText("·····")
            self.progressLabel.show()
            # 禁用下拉框和按钮，防止用户在加载过程中切换模型
            self.comboBox.setEnabled(False)
        elif model_data.is_downloading:
            # 正在下载
            self.progressLabel.setText(f"{model_data.download_progress}%")
            self.progressLabel.show()
            # 禁用下拉框
            self.comboBox.setEnabled(False)
        elif model_data.is_exists:
            # 模型存在
            self.syncButton.show()
            # 启用下拉框
            self.comboBox.setEnabled(True)
        else:
            # 模型不存在
            self.downloadButton.show()
            # 启用下拉框
            self.comboBox.setEnabled(True)
    
    def _on_model_changed(self, text: str):
        """模型变更事件
        
        Args:
            text: 选中的文本
        """
        # 重新扫描模型
        self.model_service.scan_models()

        # 查找对应的原始模型名称
        model_name = None
        for size in ModelSize:
            if text == ModelSize.get_display_name(size.value):
                model_name = size.value
                break
                
        # 如果找不到对应的枚举值，则直接使用小写的文本
        if model_name is None:
            model_name = text.lower()
        
        # 获取模型数据并更新UI
        model_data = self.model_service.get_model_data(model_name)
        if model_data:
            # 更新UI
            self.update_ui(model_name, model_data)
    
    def _on_download_clicked(self):
        """下载按钮点击事件"""
        model_name = self.get_selected_model()
        
        # 立即禁用下拉框，不等待状态更新
        self.comboBox.setEnabled(False)
        
        # 发布模型下载请求事件
        event_data = ModelEvent(
            event_type=EventTypes.MODEL_DOWNLOAD_REQUESTED,
            model_name=model_name
        )
        event_bus.publish(EventTypes.MODEL_DOWNLOAD_REQUESTED, event_data)

    def _on_cuda_env_install_completed(self, event):
        """CUDA环境安装完成事件"""
        self.update_ui(self.current_model, self.model_service.get_model_data(self.current_model))
    
    def __del__(self):
        """组件销毁时清理资源"""
        try:
            # 断开信号连接
            self.downloadButton.clicked.disconnect()
            self.syncButton.clicked.disconnect()
            self.comboBox.currentTextChanged.disconnect()
            
            # 取消事件订阅
            event_bus.unsubscribe(EventTypes.MODEL_DATA_CHANGED, self._on_model_data_changed)
        except:
            # 忽略可能的异常
            pass 