#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
应用程序配置模型和常量定义
"""

import os
import json
from enum import Enum
from pathlib import Path
import platform
from qfluentwidgets import (qconfig, QConfig, ConfigItem, OptionsConfigItem, 
                           RangeConfigItem, BoolValidator, OptionsValidator, 
                           RangeValidator, EnumSerializer)

# 从 enums 导入 ModelSize 枚举
from core.models.model_data import ModelSize

# 应用程序名称和组织名
APP_NAME = "FasterVox"  # 使用驼峰命名避免兼容性问题
APP_ORGANIZATION = "FasterVox"

# 根据操作系统确定应用程序根目录
system = platform.system()
if system == "Windows":
    # Windows 路径
    APP_ROOT_DIR = Path.home() / "AppData" / "Local" / APP_NAME
elif system == "Darwin":  # macOS
    # macOS 路径
    APP_ROOT_DIR = Path.home() / "Library" / "Application Support" / APP_NAME
else:  # Linux 和其他系统
    # Linux 路径
    APP_ROOT_DIR = Path.home() / ".config" / APP_NAME

# 定义子目录
APP_CONFIG_DIR = APP_ROOT_DIR
APP_MODELS_DIR = APP_ROOT_DIR / "models"
APP_LOGS_DIR = APP_ROOT_DIR / "logs"
APP_CACHE_DIR = APP_ROOT_DIR / "cache"
APP_ENV_DIR = APP_ROOT_DIR / "env"

WHISPER_EXE_PATH = APP_ENV_DIR / "Faster-Whisper-XXL" / "faster-whisper-xxl.exe"

# 根据操作系统确定默认文档目录
if system == "Windows":
    APP_DEFAULT_DOC_DIR = str(Path.home() / "Documents")
elif system == "Darwin":  # macOS
    APP_DEFAULT_DOC_DIR = str(Path.home() / "Documents")
else:  # Linux 和其他系统
    APP_DEFAULT_DOC_DIR = str(Path.home() / "Documents")

# 支持的音频格式（文件扩展名，包含点）
SUPPORTED_AUDIO_FORMATS = ['.mp3', '.wav', '.ogg', '.flac', '.m4a', '.aac', '.wma']

# 支持的视频格式（文件扩展名，包含点）
SUPPORTED_VIDEO_FORMATS = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm']

# 支持的导出格式（文件扩展名，包含点）
SUPPORTED_EXPORT_FORMATS = ['.srt', '.vtt', '.txt', '.json', '.tsv']

# 转录任务默认超时时间（秒）
DEFAULT_TRANSCRIPTION_TIMEOUT = 3600

# 默认日志级别
DEFAULT_LOG_LEVEL = "INFO"

# 默认配置目录
DEFAULT_CONFIG_DIRECTORY = "config"

# 默认模型目录
DEFAULT_MODEL_DIRECTORY = "models"

# 默认输出目录
DEFAULT_OUTPUT_DIRECTORY = "output"

# 默认临时目录
DEFAULT_TEMP_DIRECTORY = "temp"

# 默认模型名称
DEFAULT_MODEL_NAME = "small"

# 默认语言代码（自动检测）
DEFAULT_LANGUAGE_CODE = None


class ComputeType(Enum):
    """计算精度枚举"""
    FLOAT32 = "float32"
    FLOAT16 = "float16"
    INT8 = "int8"
    
    @staticmethod
    def values():
        return [t.value for t in ComputeType]


class Device(Enum):
    """计算设备枚举"""
    AUTO = "auto"
    CPU = "cpu"
    CUDA = "cuda"
    ROCM = "rocm"
    
    @staticmethod
    def values():
        return [d.value for d in Device]
    
    @staticmethod
    def display_name(value):
        """获取显示名称"""
        name_map = {
            "auto": "自动选择",
            "cpu": "CPU",
            "cuda": "CUDA (GPU)",
            "rocm": "ROCm (AMD GPU)"
        }
        return name_map.get(value, value)


class OutputFormat(Enum):
    """输出格式枚举"""
    SRT = "srt"
    VTT = "vtt"
    TXT = "txt"
    JSON = "json"
    
    @staticmethod
    def values():
        return [f.value for f in OutputFormat]


class Language(Enum):
    """语言枚举"""
    AUTO = "auto"
    ZH = "zh"
    EN = "en"
    JA = "ja"
    KO = "ko"
    FR = "fr"
    DE = "de"
    ES = "es"
    
    @staticmethod
    def values():
        return [l.value for l in Language]
    
    @staticmethod
    def display_name(value):
        """获取显示名称"""
        name_map = {
            "auto": "自动检测",
            "zh": "中文 (zh)",
            "en": "英语 (en)",
            "ja": "日语 (ja)",
            "ko": "韩语 (ko)",
            "fr": "法语 (fr)",
            "de": "德语 (de)",
            "es": "西班牙语 (es)"
        }
        return name_map.get(value, value)

    @staticmethod
    def from_display_name(display_name: str):
        """根据显示名称获取枚举值"""
        for lang_member in Language:
            if Language.display_name(lang_member.value) == display_name:
                return lang_member.value
        return None


class AppConfig(QConfig):
    """应用程序配置类"""

    # 常规设置
    theme = OptionsConfigItem("general", "theme", "light", OptionsValidator(["light", "dark"]))
    ui_language = OptionsConfigItem("general", "ui_language", "zh_CN", OptionsValidator(["zh_CN", "en_US"])) # Renamed from 'language'
    last_output_dir = ConfigItem("general", "last_output_dir", str(Path.home() / "Documents"))
    
    # 转录设置
    model_name = OptionsConfigItem(
        "transcription", "model_name", ModelSize.MEDIUM, 
        OptionsValidator(ModelSize), EnumSerializer(ModelSize)
    )
    model_path = ConfigItem(
        "transcription", "model_path", 
        str(APP_MODELS_DIR)
    )
    compute_type = OptionsConfigItem(
        "transcription", "compute_type", ComputeType.FLOAT16, 
        OptionsValidator(ComputeType), EnumSerializer(ComputeType)
    )
    device = OptionsConfigItem(
        "transcription", "device", Device.AUTO,
        OptionsValidator(Device), EnumSerializer(Device)
    )
    cpu_threads = RangeConfigItem("transcription", "cpu_threads", 4, RangeValidator(1, 16))
    num_workers = RangeConfigItem("transcription", "num_workers", 1, RangeValidator(1, 8))
    beam_size = RangeConfigItem("transcription", "beam_size", 5, RangeValidator(1, 10))
    vad_filter = ConfigItem("transcription", "vad_filter", True, BoolValidator())
    word_timestamps = ConfigItem("transcription", "word_timestamps", True, BoolValidator())
    punctuation = ConfigItem("transcription", "punctuation", False, BoolValidator())
    
    # 新增设置项
    task = OptionsConfigItem("transcription", "task", "transcribe", 
                             OptionsValidator(["transcribe", "translate"]))
    temperature = RangeConfigItem("transcription", "temperature", 0.0, RangeValidator(0.0, 1.0))
    condition_on_previous_text = ConfigItem("transcription", "condition_on_previous_text", 
                                          True, BoolValidator())
    no_speech_threshold = RangeConfigItem("transcription", "no_speech_threshold", 
                                         0.6, RangeValidator(0.1, 1.0))
    
    # 输出设置
    default_format = OptionsConfigItem(
        "output", "default_format", OutputFormat.SRT, 
        OptionsValidator(OutputFormat), EnumSerializer(OutputFormat)
    )
    default_language = OptionsConfigItem(
        "output", "default_language", Language.AUTO, 
        OptionsValidator(Language), EnumSerializer(Language)
    )
    output_directory = ConfigItem("output", "output_directory", "", None)  # 指定输出目录，为空则使用源文件目录
    
    def __init__(self):
        """初始化配置对象"""
        super().__init__()
        # 配置文件路径
        self.config_dir = APP_CONFIG_DIR
        self.config_file = self.config_dir / "config.json"
        
        # 确保配置目录存在
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def get_last_directory(self) -> str:
        """获取上次使用的目录"""
        return self.get(self.last_output_dir)
    
    def set_last_directory(self, directory: str) -> None:
        """设置上次使用的目录"""
        self.set(self.last_output_dir, directory)
        self.save()
    
    def get_model_name(self) -> str:
        """获取模型名称"""
        return self.get(self.model_name).value
    
    def get_model_path(self) -> str:
        """获取模型路径"""
        return self.get(self.model_path)
    
    def get_compute_type(self) -> str:
        """获取计算精度"""
        return self.get(self.compute_type).value
    
    def get_device(self) -> str:
        """获取计算设备"""
        return self.get(self.device).value
    
    def get_cpu_threads(self) -> int:
        """获取CPU线程数"""
        return self.get(self.cpu_threads)
    
    def get_num_workers(self) -> int:
        """获取工作线程数"""
        return self.get(self.num_workers)
    
    def get_beam_size(self) -> int:
        """获取波束大小"""
        return self.get(self.beam_size)
    
    def get_vad_filter(self) -> bool:
        """获取是否使用VAD过滤"""
        return self.get(self.vad_filter)
    
    def get_word_timestamps(self) -> bool:
        """获取是否生成单词时间戳"""
        return self.get(self.word_timestamps)
    
    def get_punctuation(self) -> bool:
        """获取是否添加标点符号"""
        return self.get(self.punctuation)
    
    def get_task(self) -> str:
        """获取任务类型"""
        return self.get(self.task)
    
    def get_temperature(self) -> float:
        """获取温度参数"""
        return self.get(self.temperature)
    
    def get_condition_on_previous_text(self) -> bool:
        """获取是否基于前文生成"""
        return self.get(self.condition_on_previous_text)
    
    def get_no_speech_threshold(self) -> float:
        """获取无语音阈值"""
        return self.get(self.no_speech_threshold)
    
    def get_default_format(self) -> str:
        """获取默认输出格式"""
        return self.get(self.default_format).value
    
    def get_default_language(self) -> str:
        """获取默认语言"""
        return self.get(self.default_language).value
    
    def get_output_directory(self) -> str:
        """获取输出目录"""
        return self.get(self.output_directory)
    
    def reset_to_defaults(self) -> None:
        """恢复默认设置"""
        self.set(self.theme, "light")
        self.set(self.ui_language, "zh_CN") # Renamed from 'language', set default UI language
        self.set(self.model_name, ModelSize.MEDIUM)
        self.set(self.compute_type, ComputeType.INT8)
        self.set(self.device, Device.CPU)
        self.set(self.cpu_threads, 4)
        self.set(self.num_workers, 1)
        self.set(self.beam_size, 5)
        self.set(self.vad_filter, True)
        self.set(self.word_timestamps, True)
        self.set(self.punctuation, False)
        self.set(self.task, "transcribe")
        self.set(self.temperature, 0.0)
        self.set(self.condition_on_previous_text, True)
        self.set(self.no_speech_threshold, 0.6)
        self.set(self.default_format, OutputFormat.SRT)
        self.set(self.default_language, Language.AUTO)
        self.set(self.output_directory, "")
        self.save()
        
# 全局配置对象
cfg = AppConfig()

# 加载配置
qconfig.load(str(cfg.config_file), cfg) 