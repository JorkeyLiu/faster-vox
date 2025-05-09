#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通知相关枚举定义
"""

from enum import Enum
from typing import Callable # 新增导入
from loguru import logger

class NotificationContent(Enum):
    """通知内容模板枚举"""

    # 模型下载
    MODEL_DOWNLOADING = "notification.model_downloading"
    MODEL_DOWNLOADED = "notification.model_downloaded"
    MODEL_DOWNLOADING_FAILED = "notification.model_downloading_failed"
    MODEL_DOWNLOAD_STARTED = "notification.model_download_started"
    MODEL_DOWNLOAD_COMPLETED = "notification.model_download_completed"
    MODEL_DOWNLOAD_NOT_FOUND = "notification.model_download_not_found"

    # 系统错误
    SYSTEM_ERROR = "notification.system_error"
    
    # 文件操作
    FILE_ADD_FAILED = "notification.file_add_failed"
    FILE_OPEN_FAILED = "notification.file_open_failed"
    FILE_NOT_EXIST = "notification.file_not_exist"
    DIRECTORY_OPEN_FAILED = "notification.directory_open_failed"
    
    # 设置相关
    SETTINGS_SAVED = "notification.settings_saved"
    SETTINGS_RESET = "notification.settings_reset"
    OUTPUT_DIR_RESET = "notification.output_dir_reset"

    def get_message(self, translator: Callable, **kwargs) -> str:
        """
        获取翻译并格式化后的消息。
        
        Args:
            translator: 翻译函数 (例如 gettext 的 _)。
            **kwargs: 用于格式化模板的参数。
            
        Returns:
            翻译并格式化后的字符串。
        """
        translated_template = translator(self.value) # self.value 是翻译键
        try:
            return translated_template.format(**kwargs)
        except KeyError as e:
            logger.error(
                f"Missing key {e} for notification template '{self.value}' with args {kwargs}. "
                f"Returning unformatted template."
            )
            return translated_template # 或者 f"Error formatting notification: {self.value}"
    
class NotificationTitle(Enum):
    """通知标题枚举"""

    # 空标题
    NONE_TITLE = "" 