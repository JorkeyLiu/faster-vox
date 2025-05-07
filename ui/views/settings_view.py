#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
设置视图 - 包含转录设置和界面设置
"""

from pathlib import Path
from loguru import logger

from PySide6.QtCore import Qt, Signal, QTimer, QSize
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFileDialog, QHBoxLayout, QLabel, QMessageBox
from dependency_injector.wiring import inject, Provide

from qfluentwidgets import (
    ScrollArea, FluentIcon, SettingCardGroup, SwitchSettingCard,
    ComboBoxSettingCard, RangeSettingCard, PushSettingCard,
    SettingCard, TitleLabel, TransparentToolButton, ToolTipFilter, ToolTipPosition,
    PrimaryPushButton
)

from ui.components.double_spinbox_setting_card import DoubleSpinBoxSettingCard
from ui.components.model_selection_card import ModelSelectionCard
from core.models.config import ComputeType, Language, OutputFormat, cfg, ModelSize, Device # 添加 Device, 移到顶部
from core.models.notification_model import NotificationTitle, NotificationContent
from core.services.model_management_service import ModelManagementService
from core.services.environment_service import EnvironmentService
from core.models.environment_model import EnvironmentInfo
from core.services.notification_service import NotificationService
from core.services.error_handling_service import ErrorHandlingService, ErrorCategory, ErrorPriority, ErrorInfo
from core.services.config_service import ConfigService # 添加 ConfigService
from core.events import event_bus
from core.events.event_types import (
    EventTypes, NotificationSuccessEvent, NotificationErrorEvent, ModelEvent, EnvironmentStatusEvent,
    ConfigChangedEvent, ErrorEvent
) # 导入 qconfig
from qfluentwidgets import qconfig

class SettingsView(ScrollArea):
    """设置视图"""
    
    def __init__(
        self, 
        parent=None, 
    ):
        super().__init__(parent)
        
        # 设置对象名称
        self.setObjectName("settingsView")
        
        # 创建主部件
        self.scroll_widget = QWidget()
        
        # 创建标题标签
        self.title_label = TitleLabel("设置", self)

        # 初始化服务
        self._init_services()
        
        # 初始化所有设置组
        self._init_groups()
        
        # 初始化所有配置卡片
        self._init_cards()

        # 初始化界面
        self._init_widget()
        
        # 初始化布局
        self._init_layout()

        # 连接信号和槽
        self._connect_signals()
        
        # 初始化CUDA状态UI
        self._update_cuda_status_ui()
        self._update_compute_precision_options() # Add call here
        
    @inject
    def _init_services(
        self,
        model_service: ModelManagementService = Provide["model_service"],
        environment_service: EnvironmentService = Provide["environment_service"],
        notification_service: NotificationService = Provide["notification_service"],
        error_service: ErrorHandlingService = Provide["error_service"],
        config_service: ConfigService = Provide["config_service"] # 注入 ConfigService
    ):
        self.model_service = model_service
        self.environment_service = environment_service
        self.notification_service = notification_service
        self.error_service = error_service
        self.config_service = config_service # 保存 ConfigService 实例
        
        # 订阅模型事件
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_STARTED, self._on_model_downloading)
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_PROGRESS, self._on_model_download_progress)
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self._on_download_completed)
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_ERROR, self._on_model_download_error)
        event_bus.subscribe(EventTypes.CUDA_ENV_DOWNLOAD_STARTED, self._on_cuda_env_download_started)
        event_bus.subscribe(EventTypes.CUDA_ENV_DOWNLOAD_PROGRESS, self._on_cuda_env_download_progress)
        event_bus.subscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._on_cuda_env_download_completed)
        event_bus.subscribe(EventTypes.CUDA_ENV_DOWNLOAD_ERROR, self._on_cuda_env_download_error)
        event_bus.subscribe(EventTypes.CUDA_ENV_INSTALL_STARTED, self._on_cuda_env_install_started)
        event_bus.subscribe(EventTypes.CUDA_ENV_INSTALL_PROGRESS, self._on_cuda_env_install_progress)
        event_bus.subscribe(EventTypes.CUDA_ENV_INSTALL_COMPLETED, self._on_cuda_env_install_completed)
        event_bus.subscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._on_environment_status_changed)
    
    def _init_groups(self):
        """初始化所有设置组"""
        # 模型设置组
        self.model_group = SettingCardGroup("模型设置", self.scroll_widget)
        
        # 转录设置组
        self.transcription_group = SettingCardGroup("转录设置", self.scroll_widget)
        
        # 高级设置组
        self.advanced_group = SettingCardGroup("高级设置", self.scroll_widget)
    
    def _init_cards(self):
        """初始化所有配置卡片"""
        # 模型设置卡片
        self._init_model_cards()
        
        # 转录设置卡片
        self._init_transcription_cards()
        
        # 高级设置卡片
        self._init_advanced_cards()
    
    def _init_model_cards(self):
        """初始化模型设置卡片"""
        # 模型选择卡片
        model_choices = [ModelSize.get_display_name(size.value) for size in ModelSize]  # 获取所有模型大小的显示名称
        self.model_choice_card = ModelSelectionCard(
            cfg.model_name,
            FluentIcon.LIBRARY,
            "模型选择",
            "模型越大，转录速度越慢，但准确率越高",
            model_choices,
            self.model_group
        )
        self.model_group.addSettingCard(self.model_choice_card)
        
        # 模型目录设置
        self.model_directory_card = PushSettingCard(
            "选择目录",
            FluentIcon.FOLDER,
            "模型目录",
            "设置模型文件的存储位置",
            self.model_group
        )
        self.model_directory_card.clicked.connect(self._on_select_model_directory)
        self.model_group.addSettingCard(self.model_directory_card)
    
    def _init_transcription_cards(self):
        """初始化转录设置卡片"""
        # --- 转录设备卡片 ---
        # 获取初始环境信息
        env_info = self.environment_service.get_environment_info()
        # 设置初始设备名称为默认值，将在 _update_cuda_status_ui 中更新
        initial_device_name = "CPU"

        # 创建PushSettingCard而不是SettingCard（类似于输出目录卡片）
        self.device_info_card = PushSettingCard(
            "启用CUDA加速", # 初始按钮文本（将在_update_cuda_status_ui中更新）
            FluentIcon.VIDEO,
            "转录设备",
            f"当前设备: {initial_device_name}", # 初始设备名称作为内容
            self.transcription_group
        )
        
        # 创建PrimaryPushButton并替换原有按钮
        primary_button = PrimaryPushButton("启用CUDA加速", self.device_info_card)
        primary_button.clicked.connect(self._on_toggle_gpu_preference_clicked) # 修改连接的槽函数
        
        # 获取卡片布局
        card_layout = self.device_info_card.hBoxLayout
        
        # 获取原有按钮位置
        button_index = card_layout.indexOf(self.device_info_card.button)
        
        # 替换按钮
        if button_index >= 0:
            # 移除原有按钮
            old_button = self.device_info_card.button
            card_layout.removeWidget(old_button)
            old_button.deleteLater()
            
            # 添加新按钮
            card_layout.insertWidget(button_index, primary_button)
            self.device_info_card.button = primary_button
        
        # 创建进度标签（用于下载/安装进度）
        self.cuda_progress_label = QLabel("0%", self)
        self.cuda_progress_label.setFixedSize(35, 35)
        self.cuda_progress_label.setAlignment(Qt.AlignCenter)
        
        # 在按钮前添加进度标签
        if button_index >= 0:
            # 添加空白组件保持一致的间距
            spacer = QWidget()
            spacer.setFixedWidth(10)
            
            # 插入进度标签和空白组件
            card_layout.insertWidget(button_index, self.cuda_progress_label)
            card_layout.insertWidget(button_index + 1, spacer)
        
        # 初始时隐藏进度标签
        self.cuda_progress_label.hide()
        
        self.transcription_group.addSettingCard(self.device_info_card)
        
        # 语言选择
        languages = [Language.display_name(lang.value) for lang in Language]
        self.language_card = ComboBoxSettingCard(
            cfg.default_language,
            FluentIcon.LANGUAGE,
            "语言",
            "选择音频的主要语言，自动检测可能不够准确",
            languages,
            self.transcription_group
        )
        # Removed connection: lambda text: self.config_service.set_default_language(text)
        self.transcription_group.addSettingCard(self.language_card)
        
        # 输出格式设置
        formats = [fmt.value.upper() for fmt in OutputFormat]
        self.format_card = ComboBoxSettingCard(
            cfg.default_format,
            FluentIcon.DOCUMENT,
            "输出格式",
            "选择转录结果的输出格式",
            formats,
            self.transcription_group
        )
        # Removed connection: lambda text: self.config_service.set_default_format(text.lower())
        self.transcription_group.addSettingCard(self.format_card)
        
        # 输出目录设置
        self.output_directory_card = PushSettingCard(
            "选择目录",
            FluentIcon.FOLDER,
            "输出目录",
            cfg.output_directory.value if cfg.output_directory.value else "默认（输出至与源文件相同目录）",
            self.transcription_group
        )
        self.output_directory_card.clicked.connect(self._on_select_output_directory)
        
        # 添加重置按钮
        self.reset_output_dir_button = TransparentToolButton(FluentIcon.SYNC, self)
        self.reset_output_dir_button.setFixedSize(35, 35)
        self.reset_output_dir_button.setToolTip("重置为默认")
        self.reset_output_dir_button.clicked.connect(self._on_reset_output_directory)
        
        # 获取卡片布局
        card_layout = self.output_directory_card.hBoxLayout
        
        # 获取按钮的位置
        button_index = card_layout.indexOf(self.output_directory_card.button)
        
        # 在按钮前插入重置按钮
        if button_index >= 0:
            # 添加一个弹性空间，使按钮靠近
            spacer = QWidget()
            spacer.setFixedWidth(10)  # 设置按钮之间的间距
            
            # 在按钮前插入重置按钮和间距
            card_layout.insertWidget(button_index, self.reset_output_dir_button)
            card_layout.insertWidget(button_index + 1, spacer)
        
        self.transcription_group.addSettingCard(self.output_directory_card)
        
        # 任务类型设置
        tasks = [
            "转录 (transcribe)",
            "翻译成英文 (translate)"
        ]
        self.task_card = ComboBoxSettingCard(
            cfg.task,
            FluentIcon.LANGUAGE,
            "任务类型",
            "选择转录或翻译任务",
            tasks,
            self.transcription_group
        )
        # Removed connection: lambda text: self.config_service.set_task(text.split(" ")[0])
        self.transcription_group.addSettingCard(self.task_card)
        
        # 标点符号设置
        self.punctuation_card = SwitchSettingCard(
            FluentIcon.EDIT,
            "标点符号",
            "在转录结果中添加标点符号",
            configItem=cfg.punctuation,
            parent=self.transcription_group
        )
        # Removed connection: lambda checked: self.config_service.set_punctuation(checked)
        self.transcription_group.addSettingCard(self.punctuation_card)

    def _init_advanced_cards(self):
        """初始化高级设置卡片"""
        # 波束搜索宽度设置
        self.beam_size_card = RangeSettingCard(
            cfg.beam_size,
            FluentIcon.SEARCH,
            "波束搜索宽度",
            "值越大准确性越高但速度越慢（建议值：5）",
            self.advanced_group
        )
        # Removed connection: lambda value: self.config_service.set_beam_size(value)
        self.advanced_group.addSettingCard(self.beam_size_card)
        
        # 温度设置
        self.temperature_card = DoubleSpinBoxSettingCard(
            cfg.temperature,
            FluentIcon.CALORIES,
            "采样温度",
            "控制生成的随机性，0表示确定性输出（建议值：0.0-0.4）",
            minimum=0.0,
            maximum=1.0,
            decimals=2,
            step=0.05,
            parent=self.advanced_group
        )
        # Removed connection: lambda value: self.config_service.set_temperature(value)
        self.advanced_group.addSettingCard(self.temperature_card)
        
        # 基于前文预测设置
        self.condition_card = SwitchSettingCard(
            FluentIcon.LINK,
            "基于前文预测",
            "使用前文内容提高转录连贯性",
            configItem=cfg.condition_on_previous_text,
            parent=self.advanced_group
        )
        # Removed connection: lambda checked: self.config_service.set_condition_on_previous_text(checked)
        self.advanced_group.addSettingCard(self.condition_card)
        
        # 计算精度设置 (选项将在 _update_compute_precision_options 中动态过滤)
        self.compute_type_card = ComboBoxSettingCard(
            cfg.compute_type, # ConfigItem for value binding
            FluentIcon.SPEED_HIGH,
            "计算精度",
            "选择计算精度", # Default description, will be updated dynamically
            [ct.value for ct in ComputeType], # Pass all possible options initially
            self.advanced_group
        )
        # Removed connections related to compute_type_card signals
        self.advanced_group.addSettingCard(self.compute_type_card)
        
        # 单词时间戳设置
        self.word_timestamps_card = SwitchSettingCard(
            FluentIcon.STOP_WATCH,
            "单词时间戳",
            "生成单词级别的时间戳信息",
            configItem=cfg.word_timestamps,
            parent=self.advanced_group
        )
        # Removed connection: lambda checked: self.config_service.set_word_timestamps(checked)
        self.advanced_group.addSettingCard(self.word_timestamps_card)
        
        # VAD过滤设置
        self.vad_card = SwitchSettingCard(
            FluentIcon.FILTER,
            "VAD过滤",
            "过滤无语音部分，提高转录质量",
            configItem=cfg.vad_filter, # 恢复绑定
            parent=self.advanced_group
        )
        self.vad_card.checkedChanged.connect(self._on_vad_filter_changed)
        self.advanced_group.addSettingCard(self.vad_card)
        
        # 无语音阈值设置
        self.no_speech_card = DoubleSpinBoxSettingCard(
            cfg.no_speech_threshold,
            FluentIcon.MICROPHONE,
            "无语音阈值",
            "控制无语音检测的灵敏度，值越低越敏感（建议值：0.6）",
            minimum=0.1,
            maximum=1.0,
            decimals=2,
            step=0.05,
            parent=self.advanced_group
        )
        # Removed connection: lambda value: self.config_service.set_no_speech_threshold(value)
        self.advanced_group.addSettingCard(self.no_speech_card)
        
        # 根据VAD过滤的初始状态设置无语音阈值的启用状态
        self.no_speech_card.setEnabled(cfg.vad_filter.value)

    def _init_widget(self):
        """初始化界面"""
        # 设置窗口大小
        self.resize(1000, 800)
        
        # 设置视口部件
        self.setWidget(self.scroll_widget)
        self.setWidgetResizable(True)
        
        # 设置水平滚动条策略
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # 设置视口边距
        self.setViewportMargins(0, 80, 0, 20)
        
        # 设置对象名称
        self.setObjectName("settingView")
        self.scroll_widget.setObjectName("scrollWidget")
        self.title_label.setObjectName("settingLabel")
        
        # 设置标题位置
        self.title_label.move(36, 30)
        
        # 设置样式表
        self.setStyleSheet("""
            #settingView, #scrollWidget {
                background-color: transparent;
            }
            QScrollArea {
                border: none;
                background-color: transparent;
            }
            #settingLabel {
                font: 33px 'Microsoft YaHei';
                background-color: transparent;
            }
        """)
    
    def _init_layout(self):
        """初始化布局"""
        # 创建垂直布局
        self.scroll_layout = QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(36, 10, 36, 36)
        self.scroll_layout.setSpacing(28)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        
        # 添加组到布局
        self.scroll_layout.addWidget(self.model_group)
        self.scroll_layout.addWidget(self.transcription_group)
        self.scroll_layout.addWidget(self.advanced_group)
        
        # 添加恢复默认设置按钮
        self.reset_button_layout = QHBoxLayout()
        self.reset_button_layout.setAlignment(Qt.AlignCenter)
        
        self.reset_button = PushSettingCard(
            "恢复默认设置",
            FluentIcon.SETTING,
            "恢复所有设置",
            "将所有设置恢复为默认值",
            self.scroll_widget
        )
        
        self.reset_button_layout.addWidget(self.reset_button)
        self.scroll_layout.addLayout(self.reset_button_layout)
    
    def _connect_signals(self):
        """连接信号和槽"""
        # 重置按钮信号
        self.reset_button.clicked.connect(self._on_reset_settings)

        config_items_to_connect = {
            "default_language": cfg.default_language,
            "default_format": cfg.default_format,
            "task": cfg.task,
            "punctuation": cfg.punctuation,
            "beam_size": cfg.beam_size,
            "temperature": cfg.temperature,
            "condition_on_previous_text": cfg.condition_on_previous_text,
            "compute_type": cfg.compute_type,
            "word_timestamps": cfg.word_timestamps,
            "vad_filter": cfg.vad_filter, # 添加回来，统一处理 valueChanged
            "no_speech_threshold": cfg.no_speech_threshold,
            "model_name": cfg.model_name, # 添加到字典中统一处理
        }

        for key, config_item in config_items_to_connect.items():
            if hasattr(config_item, 'valueChanged'):
                # 使用 lambda 捕获当前的 key
                config_item.valueChanged.connect(
                    lambda value, k=key: self._handle_setting_changed(k, value)
                )
            else:
                logger.warning(f"ConfigItem for key '{key}' 没有 valueChanged 信号或不存在。")

    def _on_model_download_progress(self, event):
        """模型下载进度事件"""
        # 更新模型选择卡片的进度
        self.model_choice_card.set_download_progress(event.progress / 100.0)

    def _on_model_download_error(self, event):
        """模型下载错误事件"""
        # 使用错误处理服务
        error_info = ErrorInfo(
            message=f"模型下载失败: {event.model_name}",
            category=ErrorCategory.MODEL,
            priority=ErrorPriority.MEDIUM,
            code="MODEL_DOWNLOAD_ERROR",
            user_visible=True
        )
        self.error_service.handle_error(error_info)
    
    def _on_select_model_directory(self):
        """选择模型目录"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择模型目录",
            cfg.model_path.value
        )
        
        if folder:
            cfg.model_path.value = folder
            cfg.save()
            self.model_directory_card.setContent(folder)
            
            # 更新模型服务的模型路径
            self.model_service.models_dir = Path(folder)
            
            # 重新扫描模型
            self.model_service.scan_models()
            
            # 显示成功提示
            self._publish_success_notification(
                NotificationTitle.NONE_TITLE.value,
                NotificationContent.SETTINGS_SAVED.value.format(setting_name="模型目录")
            )
    
    def _on_select_output_directory(self):
        """选择输出目录"""
        folder = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            str(Path.home())
        )
        
        if folder:
            self.output_directory_card.setContent(folder)
            self.config_service.set_output_directory(folder)
            
            # 显示成功提示
            self._publish_success_notification(
                NotificationTitle.NONE_TITLE.value,
                NotificationContent.SETTINGS_SAVED.value.format(setting_name="输出目录")
            )
    
    def _on_reset_output_directory(self):
        """重置输出目录"""
        self.output_directory_card.setContent("默认（与源文件相同目录）")
        self.config_service.set_output_directory("")
        
        # 显示成功提示
        self._publish_success_notification(
            NotificationTitle.NONE_TITLE.value,
            NotificationContent.OUTPUT_DIR_RESET.value
        )
    
    def _on_vad_filter_changed(self, checked: bool):
        """VAD过滤开关变更事件"""
        # 只更新关联UI (no_speech_card) 的状态
        self.no_speech_card.setEnabled(checked)
        # 配置更新和事件发布现在由 cfg.vad_filter.valueChanged 信号处理

    def _on_reset_settings(self):
        """恢复默认设置按钮点击事件"""
        # 恢复默认设置
        cfg.reset_to_defaults()
        
        # 显示成功提示
        self._publish_success_notification(
            NotificationTitle.NONE_TITLE.value,
            NotificationContent.SETTINGS_RESET.value
        )

    def _on_model_downloading(self, event):
        """模型开始下载回调"""
        logger.info(f"模型开始下载: {event.model_name}")

    def _on_download_completed(self, event):
        """模型下载完成事件"""
        # 触发刷新已安装的模型
        self._refresh_ui()
        
        # 检查下载是否成功
        if not event.success:
            return
        
        # 更新UI状态，但不再自动加载模型
        logger.info(f"模型下载完成: {event.model_name}")
        
    def _on_cuda_env_download_progress(self, event):
        """CUDA环境下载进度事件"""
        self.cuda_progress_label.setText(f" {event.progress}%")

    def _on_cuda_env_download_started(self, event):
        """CUDA环境开始下载回调"""
        logger.info("CUDA环境下载开始")
        self._update_cuda_status_ui()

    def _on_cuda_env_download_completed(self, event):
        """CUDA环境下载完成回调"""
        logger.info(f"CUDA环境下载完成: success={event.success}, error={event.error}")
        if not event.success:
             self._publish_error_notification(NotificationTitle.CUDA_ENV_ERROR.value, f"CUDA环境下载失败: {event.error}")
        # 无论结果如何都更新UI（下载失败时会显示按钮或转换到安装状态）
        self._update_cuda_status_ui()

    def _on_cuda_env_download_error(self, event):
        """CUDA环境下载错误回调"""
        logger.error(f"CUDA环境下载错误: {event.error}")
        self._publish_error_notification(
            NotificationTitle.CUDA_ENV_ERROR.value,
            f"CUDA环境下载错误: {event.error}"
        )
        self._update_cuda_status_ui() # 恢复UI状态

    def _on_cuda_env_install_started(self, event):
        """CUDA环境安装开始事件"""
        logger.info("CUDA环境安装开始")
        self._update_cuda_status_ui()

    def _on_cuda_env_install_progress(self, event):
        """CUDA环境安装进度事件"""
        # 更新CUDA进度标签
        self.cuda_progress_label.setText(f"{event.progress}%")

    def _on_cuda_env_install_completed(self, event):
        """CUDA环境安装完成事件"""
        logger.info(f"CUDA环境安装完成: success={event.success}, error={event.error}")
        if not event.success:
             self._publish_error_notification(NotificationTitle.CUDA_ENV_ERROR.value, f"CUDA环境安装失败: {event.error}")
        # 刷新环境信息并更新UI
        self.environment_service.refresh() # 刷新在内部处理

    def _on_toggle_gpu_preference_clicked(self):
        """切换GPU偏好设置或触发CUDA环境下载按钮点击事件"""
        logger.info("用户点击GPU设置按钮")
        
        env_info = self.environment_service.get_environment_info()
        current_device_pref = self.config_service.get_device()

        # 检查是否需要触发下载 (GPU硬件可用但环境未就绪)
        if env_info.is_windows and env_info.has_gpu and not env_info.can_use_gpu_acceleration():
            logger.info("GPU可用但环境未就绪，触发CUDA环境下载")
            # 添加即时UI反馈
            self.device_info_card.button.setText("正在准备...")
            self.device_info_card.button.setEnabled(False) # 临时禁用防止重复点击
            success = self.model_service.download_cuda_environment()
            if not success:
                # 如果立即启动失败，通知用户并恢复按钮状态
                self._publish_error_notification(
                    NotificationTitle.CUDA_ENV_ERROR.value,
                    "启动CUDA环境下载失败"
                )
                self._update_cuda_status_ui() # 恢复UI状态
            # 注意：下载是异步的，后续状态更新依赖事件（例如is_downloading变为True）
            return # 提前返回，不执行偏好切换

        # 如果不需要触发下载，则执行偏好切换逻辑
        # 禁用按钮方案时永远不会触发，但暂时保留，方便日后切换
        logger.info("切换GPU偏好设置")
        if current_device_pref == Device.CUDA.value:
            logger.info("当前偏好为CUDA，切换到CPU")
            self.config_service.set_device(Device.CPU.value)
            self._publish_success_notification("设置更新成功", "转录设备已切换为 CPU")
        else:
            logger.info(f"当前偏好为 {current_device_pref}，切换到CUDA")
            self.config_service.set_device(Device.CUDA.value)
            self._publish_success_notification("设置更新成功", "转录设备已切换为 GPU")
            
        # 立即更新UI以反映变化
        self._update_cuda_status_ui()
        self._update_compute_precision_options() # Add call here

    def _on_environment_status_changed(self, event: EnvironmentStatusEvent):
        """处理环境状态变更事件"""
        logger.info("接收到环境状态变更事件，更新UI")
        # 根据新的环境信息刷新CUDA状态UI
        self._update_cuda_status_ui()

    def __del__(self):
        """组件销毁时取消事件订阅"""
        try:
            # 取消订阅所有事件
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_STARTED, self._on_model_downloading)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_PROGRESS, self._on_model_download_progress)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self._on_download_completed)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_ERROR, self._on_model_download_error)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_STARTED, self._on_cuda_env_download_started)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_PROGRESS, self._on_cuda_env_download_progress)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._on_cuda_env_download_completed)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_ERROR, self._on_cuda_env_download_error)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_STARTED, self._on_cuda_env_install_started)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_PROGRESS, self._on_cuda_env_install_progress)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_COMPLETED, self._on_cuda_env_install_completed)
            event_bus.unsubscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._on_environment_status_changed)
        except:
            # 忽略可能的异常
            pass

    def _publish_success_notification(self, title, content):
        """发布成功通知事件"""
        event_data = NotificationSuccessEvent(
            title=title,
            content=content
        )
        event_bus.publish(EventTypes.NOTIFICATION_SUCCESS, event_data)
    
    def _publish_error_notification(self, title, content):
        """发布错误通知事件"""
        event_data = NotificationErrorEvent(
            title=title,
            content=content
        )
        event_bus.publish(EventTypes.NOTIFICATION_ERROR, event_data)

    def _set_ui_for_gpu_unavailable(self, button):
        """Sets UI elements when GPU hardware is unavailable."""
        button.setText("CUDA加速不可用")
        button.setToolTip("仅支持Windows + NVIDIA GPU")
        button.setEnabled(False)
        return "CPU (未检测到兼容GPU)"

    def _set_ui_for_busy(self, button, is_downloading):
        """Sets UI elements when CUDA environment is downloading or installing."""
        if is_downloading:
            button.setText("正在下载...")
            button.setToolTip("CUDA环境下载中")
            device_display_name = "CPU (CUDA环境下载中)"
        else: # is_installing
            button.setText("正在安装...")
            button.setToolTip("CUDA环境安装中")
            device_display_name = "CPU (CUDA环境安装中)"
        button.setEnabled(False)
        return device_display_name

    def _set_ui_for_device_switch(self, button, current_device_pref, env_info):
        """用于可切换设备时的UI显示"""
        if current_device_pref == Device.CUDA.value:
            button.setText("禁用GPU加速")
            button.setToolTip("切换回CPU进行转录")
            device_display_name = f"NVIDIA GPU ({env_info.gpu_name})"
        else: # 偏好是 CPU 或 auto
            button.setText("启用GPU加速")
            button.setToolTip("切换到GPU进行转录")
            device_display_name = "CPU"
        button.setEnabled(True)
        return device_display_name
    
    def _set_ui_for_gpu_ready(self, button, current_device_pref, env_info):
        device_display_name = f"NVIDIA GPU ({env_info.gpu_name})"
        button.setText("GPU加速已启用")
        button.setEnabled(False)
        return device_display_name

    def _set_ui_for_env_not_ready(self, button):
        """Sets UI elements when GPU hardware is available but CUDA env is not ready."""
        button.setText("启用CUDA加速")
        button.setToolTip("下载并安装必要的CUDA环境")
        button.setEnabled(True) # Allow user to click to trigger download
        return "CPU (CUDA环境未就绪)"

    def _update_cuda_status_ui(self):
        """根据环境、配置和下载/安装状态更新CUDA按钮和进度标签 (Refactored)"""
        env_info = self.environment_service.get_environment_info()
        model_service = self.model_service
        current_device_pref = self.config_service.get_device()
        button = self.device_info_card.button

        is_downloading = "cuda_env" in model_service.active_downloaders and model_service.active_downloaders["cuda_env"].isRunning()
        is_installing = "cuda_env_installer" in model_service.active_downloaders and model_service.active_downloaders["cuda_env_installer"].isRunning()
        is_busy = is_downloading or is_installing

        gpu_hardware_available = env_info.is_windows and env_info.has_gpu

        device_display_name = "CPU" # Default

        if not gpu_hardware_available:
            device_display_name = self._set_ui_for_gpu_unavailable(button)
        elif is_busy:
            device_display_name = self._set_ui_for_busy(button, is_downloading)
        else: # GPU hardware available and not busy
            cuda_env_ready = env_info.can_use_gpu_acceleration()
            if cuda_env_ready:
                # device_display_name = self._set_ui_for_device_switch(button, current_device_pref, env_info) # 需要切换设备时启用这一行，并注释掉下一行
                device_display_name = self._set_ui_for_gpu_ready(button, current_device_pref, env_info)
            else: # Env not ready
                device_display_name = self._set_ui_for_env_not_ready(button)
        # Update device name content
        try:
            self.device_info_card.setContent(f"当前设备: {device_display_name}")
        except AttributeError:
            logger.warning("PushSettingCard可能没有setContent方法，无法更新设备显示名称。")
            pass

        # Update progress label visibility
        if is_busy:
            self.cuda_progress_label.show()
        else:
            self.cuda_progress_label.hide()

    def _update_compute_precision_options(self):
        """根据当前生效的设备模式动态更新计算精度选项"""
        if not hasattr(self, 'compute_type_card'): # Ensure card exists
             logger.warning("compute_type_card尚未初始化，无法更新精度选项。")
             return
             
        env_info = self.environment_service.get_environment_info()
        # 获取用户当前的设备偏好和实际GPU加速能力
        current_device_pref = self.config_service.get_device()
        gpu_acceleration_actually_available = env_info.can_use_gpu_acceleration()

        # 确定最终生效的模式：必须实际可用 且 用户意图是使用 CUDA
        should_use_gpu_mode = gpu_acceleration_actually_available and current_device_pref == Device.CUDA.value

        precisions = []
        precision_description = ""

        if should_use_gpu_mode:
            precisions = [precision.value for precision in ComputeType]
            precision_description = "选择计算精度（GPU加速已启用）"
            logger.debug("更新计算精度选项为 GPU 模式")
        else:
            # CPU 模式下支持 float32 和 int8
            precisions = [ComputeType.FLOAT32.value, ComputeType.INT8.value]
            precision_description = "选择计算精度（CPU模式，推荐int8）"
            logger.debug("更新计算精度选项为 CPU 模式")

        # 获取当前配置值
        current_compute_type = self.config_service.get_compute_type()
        new_compute_type = current_compute_type # 默认为当前值

        # 检查当前配置值是否在新的允许列表中，如果不在则重置
        if current_compute_type not in precisions:
            reset_target = ComputeType.FLOAT32.value # 默认重置为 float32
            # 如果是CPU模式且int8可用，优先重置为int8 (如果需要)
            if not should_use_gpu_mode and ComputeType.INT8.value in precisions:
                reset_target = ComputeType.INT8.value
                
            logger.warning(f"当前计算精度 '{current_compute_type}' 在当前设备模式下无效，将重置为 '{reset_target}'")
            # self.config_service.set_compute_type(reset_target) # 注释掉，避免冲突，让库或valueChanged处理
            new_compute_type = reset_target # 更新待选中的值
            # 注意：这里直接修改了配置，如果希望只临时调整UI，逻辑会更复杂

        # 更新下拉框
        self.compute_type_card.comboBox.blockSignals(True) # 阻止信号触发配置更改
        self.compute_type_card.comboBox.clear()
        # --- 修改开始 ---
        # 创建文本到枚举成员的映射 (需要确保 ComputeType 已在文件顶部导入)
        text_to_enum = {member.value: member for member in ComputeType}

        for precision_text in precisions:
            enum_member = text_to_enum.get(precision_text)
            if enum_member:
                # 使用 addItem 并显式设置 userData
                self.compute_type_card.comboBox.addItem(precision_text, userData=enum_member)
            else:
                logger.warning(f"无法为精度文本 '{precision_text}' 找到对应的枚举成员")
        # --- 修改结束 ---

        self.compute_type_card.comboBox.setCurrentText(new_compute_type)
        self.compute_type_card.comboBox.blockSignals(False) # 恢复信号

        # 更新描述文本 (假设 contentLabel 是描述标签)
        try:
            self.compute_type_card.contentLabel.setText(precision_description)
        except AttributeError:
             logger.warning("无法更新 compute_type_card 的描述文本。")

    def _on_environment_status_changed(self, event: EnvironmentStatusEvent):
        """处理环境状态变更事件"""
        logger.info("接收到环境状态变更事件，更新UI")
        # 根据新的环境信息刷新CUDA状态UI
        self._update_cuda_status_ui()

    def _handle_setting_changed(self, config_key: str, new_value: any):
        """处理 ConfigItem.valueChanged 信号或手动触发，发布配置变更事件"""
        # 从枚举或ConfigItem获取实际值用于发布
        value_to_publish = new_value.value if hasattr(new_value, 'value') else new_value
        logger.debug(f"Setting changed: key={config_key}, new_value={value_to_publish}")
        # 调用 ConfigService 的发布方法
        if hasattr(self, 'config_service') and hasattr(self.config_service, '_publish_config_change_event'):
            self.config_service._publish_config_change_event(config_key, value_to_publish)
        else:
            logger.error("ConfigService 或其 _publish_config_change_event 方法在 SettingsView 中不可用。")

    def __del__(self):
        try:
            # 取消订阅所有事件
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_STARTED, self._on_model_downloading)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_PROGRESS, self._on_model_download_progress)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_PROGRESS, self._on_cuda_env_download_progress)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self._on_download_completed)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_ERROR, self._on_model_download_error)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_STARTED, self._on_cuda_env_download_started)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._on_cuda_env_download_completed)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_ERROR, self._on_cuda_env_download_error)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_STARTED, self._on_cuda_env_install_started)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_PROGRESS, self._on_cuda_env_install_progress)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_COMPLETED, self._on_cuda_env_install_completed)
            event_bus.unsubscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._on_environment_status_changed)
        except:
            # 忽略可能的异常
            pass

