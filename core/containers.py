#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
依赖注入容器 - 负责项目中所有依赖关系的管理
"""

import os
from dependency_injector import containers, providers
from core.utils.file_utils import get_resource_path

# 导入服务类
from core.services.config_service import ConfigService
from core.services.model_management_service import ModelManagementService
from core.services.task_service import TaskService
from core.services.transcription_service import TranscriptionService
from core.services.audio_service import AudioService
from core.whisper_manager import WhisperManager
from core.services.notification_service import NotificationService
from core.services.error_handling_service import ErrorHandlingService
from core.models.config import cfg, APP_MODELS_DIR # Added APP_MODELS_DIR
from core.events import event_bus
from core.services.environment_service import EnvironmentService
from .i18n import initialize_translation

class AppContainer(containers.DeclarativeContainer):
    """应用程序容器 - 管理所有服务和配置的依赖注入"""

    # 定义Wiring配置：需要函数级注入的模块
    wiring_config = containers.WiringConfiguration(
        modules=[
            'ui.main_window',
            'ui.views.task_view',
            'ui.components.drop_area',
            'ui.views.home_view',
            'ui.views.settings_view',
            'ui.components.task_table_manager',
            'ui.components.transcript_viewer',
            'ui.components.model_selection_card',

            'core.services.transcription_service',
            'core.services.error_handling_service',
        ]
    )
    
    # 定义错误处理服务
    error_handling_service = providers.Singleton(
        ErrorHandlingService
    )

    # 定义配置服务 - 依赖app_config
    config_service = providers.Singleton(
        ConfigService,
        config=providers.Object(cfg) # 直接使用 Object Provider
    )

    # 定义翻译函数 provider - 依赖 config_service
    translation_function = providers.Singleton(
        initialize_translation,
        config_service=config_service,
        error_service=error_handling_service
    )

    # 定义配置提供者
    config = providers.Configuration(name="config")
    
    # 设置默认配置值
    # model_dir is now managed by AppConfig's model_path default (APP_MODELS_DIR)
    # and ModelManagementService which uses config_service.get_model_directory().
    # No need to set a default for "model_dir" here in the container's config provider directly,
    # as it would override or conflict with the AppConfig logic.
    # The ConfigService will provide the correct model directory based on AppConfig.
    config.from_dict({
        "general": {
            # "model_dir": str(APP_MODELS_DIR) # Corrected: model_dir default comes from AppConfig
        },
        "ui": {
            "theme": "light"
        }
    })
    
    # 定义通知服务 - 依赖翻译函数
    notification_service = providers.Singleton(
        NotificationService,
        translator=translation_function
    )
    
    # 定义事件总线（单例）
    event_bus_instance = providers.Object(event_bus)
    
    # 定义音频服务 - 依赖错误处理服务
    audio_service = providers.Singleton(
        AudioService,
        error_service=error_handling_service
    )
    
    # 注册环境服务 - 依赖配置服务
    environment_service = providers.Singleton(
        EnvironmentService,
        config_service=config_service
    )
    
    # 定义Whisper管理器
    whisper_manager = providers.Factory(
        WhisperManager,
        config_service=config_service,
        error_service=error_handling_service,
        notification_service=notification_service
    )
    
    # 注册模型管理服务 - 移除了whisper_manager依赖
    model_service = providers.Singleton(
        ModelManagementService,
        config_service=config_service,
        environment_service=environment_service,
        notification_service=notification_service,
        error_service=error_handling_service
    )
    
    # 定义任务服务 - 依赖音频服务和其他服务
    task_service = providers.Singleton(
        TaskService,
        config_service=config_service,
        audio_service=audio_service,
        error_service=error_handling_service
    )
    
    # 定义转录服务 - 依赖配置服务、模型服务、音频服务和Whisper管理器
    transcription_service = providers.Singleton(
        TranscriptionService,
        config_service=config_service,
        model_service=model_service,
        audio_service=audio_service,
        whisper_manager=whisper_manager,
        environment_service=environment_service,
        error_service=error_handling_service,
        task_service=task_service  # Inject TaskService
    )