#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
配置服务 - 负责应用程序配置管理
"""

from loguru import logger
import os
from pathlib import Path

# Import event bus and event types
from core.events import event_bus, EventTypes, ConfigChangedEvent
from core.models.config import ComputeType, Device, OutputFormat, Language


class ConfigService:
    """配置服务类，负责应用程序配置管理"""
    
    def __init__(self, config):
        """初始化配置服务
        
        Args:
            config: 配置对象
        """
        self.config = config

    def _publish_config_change_event(self, key: str, value: any) -> None:
        """发布配置变更事件的辅助方法"""
        try:
            event_bus.publish(
                EventTypes.CONFIG_CHANGED,
                ConfigChangedEvent(key=key, value=value)
            )
            logger.debug(f"Published CONFIG_CHANGED event: key={key}, value={value}")
        except Exception as e:
            logger.error(f"Failed to publish CONFIG_CHANGED event ({key}): {str(e)}")
    
    def get_theme(self) -> str:
        """获取主题
        
        Returns:
            str: 主题名称，"light"或"dark"
        """
        return self.config.get(self.config.theme)
    
    def set_theme(self, theme: str) -> None:
        """设置主题
        
        Args:
            theme: 主题名称，"light"或"dark"
        """
        # 直接设置、保存并发布事件
        self.config.set(self.config.theme, theme)
        self.config.save()
        logger.info(f"配置已更新并保存: theme = {theme}")
        self._publish_config_change_event("theme", theme)
    
    def get_ui_language(self) -> str: # Renamed from get_language
        """获取界面语言
        
        Returns:
            str: 语言代码，如"zh_CN"或"en_US"，默认为 "zh_CN"
        """
        # The AppConfig now handles dynamic default language, so this getter should directly return the configured value.
        # The fallback logic in AppConfig's __init__ is the primary source for default.
        lang = self.config.get(self.config.ui_language)
        if not lang:
            # This case should be rare now, but as a last resort, log and return a hardcoded default.
            logger.warning("UI language is unexpectedly not set in AppConfig, defaulting to 'en_US' as a final fallback.")
            return "en_US"
        return lang
    
    def set_ui_language(self, language: str) -> None: # Renamed from set_language
        """设置界面语言
        
        Args:
            language: 语言代码，如"zh_CN"或"en_US"
        """
        # 直接设置、保存并发布事件
        self.config.set(self.config.ui_language, language) # Updated reference
        self.config.save()
        logger.info(f"配置已更新并保存: ui_language = {language}") # Updated log message
        self._publish_config_change_event("ui_language", language) # Updated event key
    
    def get_last_directory(self) -> str:
        """获取上次使用的目录
        
        Returns:
            str: 目录路径
        """
        last_dir = self.config.get_last_directory()
        # 如果没有保存的目录或目录已失效，返回默认目录
        if not last_dir or not os.path.exists(last_dir) or not os.path.isdir(last_dir):
            return str(Path.home() / "Documents")
        return last_dir
    
    def set_last_directory(self, directory: str) -> None:
        """设置上次使用的目录
        
        Args:
            directory: 目录路径
        """
        # 确保目录存在
        # 直接设置、保存并发布事件 (假设 AppConfig.set_last_directory 内部会保存)
        # 注意：原逻辑包含路径检查，这里简化为直接设置，依赖调用者保证路径有效性或 AppConfig 内部处理
        if os.path.exists(directory) and os.path.isdir(directory):
             self.config.set_last_directory(directory) # This should call save() in AppConfig
             logger.info(f"配置已更新并保存: last_output_dir = {directory}")
             self._publish_config_change_event("last_output_dir", directory)
        else:
             logger.warning(f"无法设置上次目录，目录不存在或不是有效目录: {directory}")
        # 注意：原代码在路径无效时不进行任何操作，修改后如果路径有效则总是尝试设置和发布事件。
        # 如果需要严格保持原有的“仅在值改变时操作”的行为，需要调整 AppConfig.set_last_directory
    
    def get_model_name(self) -> str:
        """获取模型名称
        
        Returns:
            str: 模型名称
        """
        return self.config.get_model_name()
    
    def get_model_directory(self) -> str:
        """获取模型目录
        
        Returns:
            str: 模型目录路径
        """
        return self.config.get_model_path()
    
    def set_model_directory(self, directory: str) -> None:
        """设置模型目录
        
        Args:
            directory: 模型目录路径
        """
        # 直接设置、保存并发布事件
        self.config.set(self.config.model_path, directory)
        self.config.save()
        logger.info(f"配置已更新并保存: model_path = {directory}")
        self._publish_config_change_event("model_path", directory)
    
    def get_compute_type(self) -> str:
        """获取计算精度
        
        Returns:
            str: 计算精度，如"float16"、"int8"等
        """
        return self.config.get_compute_type()
    
    def set_compute_type(self, compute_type: str) -> None:
        """设置计算精度
        
        Args:
            compute_type: 计算精度，如"float16"、"int8"等
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_compute_type called for {compute_type}, but logic is handled by component binding.")
        pass

    def get_beam_size(self) -> int:
        """获取波束大小
        
        Returns:
            int: 波束大小
        """
        return self.config.get_beam_size()
    
    def set_beam_size(self, beam_size: int) -> None:
        """设置波束大小
        
        Args:
            beam_size: 波束大小
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_beam_size called for {beam_size}, but logic is handled by component binding.")
        pass
    
    def get_vad_filter(self) -> bool:
        """获取是否使用VAD过滤
        
        Returns:
            bool: 是否使用VAD过滤
        """
        return self.config.get_vad_filter()
    
    def set_vad_filter(self, vad_filter: bool) -> None:
        """设置是否使用VAD过滤
        
        Args:
            vad_filter: 是否使用VAD过滤
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_vad_filter called for {vad_filter}, but logic is handled by component binding.")
        pass
    
    def get_word_timestamps(self) -> bool:
        """获取是否生成单词时间戳
        
        Returns:
            bool: 是否生成单词时间戳
        """
        return self.config.get_word_timestamps()
    
    def set_word_timestamps(self, word_timestamps: bool) -> None:
        """设置是否生成单词时间戳
        
        Args:
            word_timestamps: 是否生成单词时间戳
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_word_timestamps called for {word_timestamps}, but logic is handled by component binding.")
        pass
    
    def get_punctuation(self) -> bool:
        """获取是否添加标点符号
        
        Returns:
            bool: 是否添加标点符号
        """
        return self.config.get_punctuation()
    
    def set_punctuation(self, punctuation: bool) -> None:
        """设置是否添加标点符号
        
        Args:
            punctuation: 是否添加标点符号
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_punctuation called for {punctuation}, but logic is handled by component binding.")
        pass
    
    def get_task(self) -> str:
        """获取任务类型
        
        Returns:
            str: 任务类型，"transcribe"或"translate"
        """
        return self.config.get_task()
    
    def set_task(self, task: str) -> None:
        """设置任务类型
        
        Args:
            task: 任务类型，"transcribe"或"translate"
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_task called for {task}, but logic is handled by component binding.")
        pass
    
    def get_temperature(self) -> float:
        """获取温度参数
        
        Returns:
            float: 温度参数
        """
        return self.config.get_temperature()
    
    def set_temperature(self, temperature: float) -> None:
        """设置温度参数
        
        Args:
            temperature: 温度参数
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_temperature called for {temperature}, but logic is handled by component binding.")
        pass
    
    def get_condition_on_previous_text(self) -> bool:
        """获取是否基于前文生成
        
        Returns:
            bool: 是否基于前文生成
        """
        return self.config.get_condition_on_previous_text()
    
    def set_condition_on_previous_text(self, condition: bool) -> None:
        """设置是否基于前文生成
        
        Args:
            condition: 是否基于前文生成
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_condition_on_previous_text called for {condition}, but logic is handled by component binding.")
        pass
    
    def get_no_speech_threshold(self) -> float:
        """获取无语音阈值
        
        Returns:
            float: 无语音阈值
        """
        return self.config.get_no_speech_threshold()
    
    def set_no_speech_threshold(self, threshold: float) -> None:
        """设置无语音阈值
        
        Args:
            threshold: 无语音阈值
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_no_speech_threshold called for {threshold}, but logic is handled by component binding.")
        pass
    
    def get_default_format(self) -> str:
        """获取默认输出格式
        
        Returns:
            str: 默认输出格式
        """
        return self.config.get_default_format()
    
    def set_default_format(self, format: str) -> None:
        """设置默认输出格式
        
        Args:
            format: 默认输出格式
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_default_format called for {format}, but logic is handled by component binding.")
        pass
    
    def get_default_language(self) -> str:
        """获取默认语言
        
        Returns:
            str: 默认语言
        """
        return self.config.get_default_language()
    
    def set_default_language(self, language: str) -> None:
        """设置默认语言
        
        Args:
            language: 默认语言
        """
        # Logic moved to qfluentwidgets binding and valueChanged signal handling in SettingsView
        logger.debug(f"ConfigService.set_default_language called for {language}, but logic is handled by component binding.")
        pass
    
    def get_output_directory(self) -> str:
        """获取输出目录
        
        Returns:
            str: 输出目录
        """
        return self.config.get_output_directory()
    
    def set_output_directory(self, directory: str) -> None:
        """设置输出目录
        
        Args:
            directory: 输出目录
        """
        # 直接设置、保存并发布事件
        self.config.set(self.config.output_directory, directory)
        self.config.save()
        logger.info(f"配置已更新并保存: output_directory = {directory}")
        self._publish_config_change_event("output_directory", directory)
    
    def reset_to_defaults(self) -> None:
        """恢复所有设置为默认值"""
        self.config.reset_to_defaults()
    
    def get_device(self) -> str:
        """获取计算设备
        
        Returns:
            str: 计算设备，如"auto"、"cpu"、"cuda"等
        """
        # 如果配置中有设备配置项，则使用配置中的值
        if hasattr(self.config, 'device'):
            return self.config.get(self.config.device).value
        # 否则返回默认值
        return "auto"
    
    def set_device(self, device: str) -> None:
        """设置计算设备
        
        Args:
            device: 计算设备，如"auto"、"cpu"、"cuda"等
        """
        # 如果配置中有设备配置项，则设置配置中的值
        if hasattr(self.config, 'device'):
            try:
                device_enum = Device(device)
                # 直接设置、保存并发布事件
                self.config.set(self.config.device, device_enum)
                self.config.save()
                logger.info(f"配置已更新并保存: device = {device}")
                self._publish_config_change_event("device", device)
            except ValueError:
                logger.error(f"无效的计算设备: {device}")
    
    def get_cpu_threads(self) -> int:
        """获取CPU线程数
        
        Returns:
            int: CPU线程数
        """
        # 如果配置中有CPU线程数配置项，则使用配置中的值
        if hasattr(self.config, 'cpu_threads'):
            return self.config.get(self.config.cpu_threads)
        # 否则返回默认值
        return 4
    
    def set_cpu_threads(self, threads: int) -> None:
        """设置CPU线程数
        
        Args:
            threads: CPU线程数
        """
        # This setting is not currently exposed in SettingsView via a bound ConfigItem
        # If it were, the logic would be handled by component binding.
        logger.debug(f"ConfigService.set_cpu_threads called for {threads}, but this setting might not be actively used or bound.")
        pass
    
    def get_num_workers(self) -> int:
        """获取工作线程数
        
        Returns:
            int: 工作线程数
        """
        # 如果配置中有工作线程数配置项，则使用配置中的值
        if hasattr(self.config, 'num_workers'):
            return self.config.get(self.config.num_workers)
        # 否则返回默认值
        return 1
    
    def set_num_workers(self, workers: int) -> None:
        """设置工作线程数
        
        Args:
            workers: 工作线程数
        """
        # This setting is not currently exposed in SettingsView via a bound ConfigItem
        # If it were, the logic would be handled by component binding.
        logger.debug(f"ConfigService.set_num_workers called for {workers}, but this setting might not be actively used or bound.")
        pass