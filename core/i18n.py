#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
国际化 (i18n) 相关功能，例如 gettext 初始化。

相关指令：
    提取所有标记的字符串到 locales/messages.pot 文件：
        pybabel extract -F babel.cfg -o locales/messages.pot .
    初始化翻译文件:
        pybabel init -i locales/messages.pot -d locales -l zh_CN
        pybabel init -i locales/messages.pot -d locales -l en
    更新翻译文件：
        pybabel update -i locales/messages.pot -d locales
    编译：
        pybabel compile -d locales
"""

import os
import gettext
from loguru import logger
from .services.config_service import ConfigService
from .models.config import cfg
from .services.error_handling_service import ErrorHandlingService
from .models.error_model import ErrorCategory, ErrorPriority

def initialize_translation(config_service: ConfigService, error_service: ErrorHandlingService):
    """
    根据配置初始化 gettext 翻译函数。

    Args:
        config_service: 配置服务实例，用于获取当前语言设置。

    Returns:
        callable: gettext 翻译函数 (_) 或一个空操作 lambda 函数。
    """
    lang_code = config_service.get_ui_language()
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    locales_dir = os.path.join(project_root, 'locales')
    
    logger.info(f"Initializing gettext for language: {lang_code}, locales_dir: {locales_dir}")

    try:
        lang_translation = gettext.translation(
            'messages',                # .mo 文件的基础名称
            localedir=locales_dir,
            languages=[lang_code]
        )
        logger.info(f"Successfully loaded translation for {lang_code}")
        # 返回 gettext 函数本身
        return lang_translation.gettext
    except FileNotFoundError as e:
        error_service.handle_exception(e, category=ErrorCategory.FILE_SYSTEM, priority=ErrorPriority.MEDIUM, source="i18n.initialize_translation", user_visible=False)
        # 返回一个什么都不做的函数
        return lambda s: s
    except Exception as e:
        error_service.handle_exception(e, category=ErrorCategory.SYSTEM, priority=ErrorPriority.HIGH, source="i18n.initialize_translation", user_visible=False)
        return lambda s: s