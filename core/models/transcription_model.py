#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
转录模型 - 数据类定义
"""

from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class TranscriptionSegment:
    """转录片段数据类"""
    id: int
    start: float
    end: float
    text: str
    words: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class TranscriptionResult:
    """转录结果数据类"""
    segments: List[TranscriptionSegment] = field(default_factory=list)
    language: str = ""
    language_probability: float = 0.0
    duration: float = 0.0
    source_file: str = ""
    task_id: str = ""


@dataclass
class TranscriptionError:
    """转录错误"""
    task_id: str
    message: str
    code: str = "TRANSCRIPTION_ERROR"
    details: Dict[str, Any] = field(default_factory=dict)
    source_file: Optional[str] = None


@dataclass
class TranscriptionParameters:
    """Transcription parameters data class."""
    
    model_name: str = "medium"
    language: Optional[str] = None
    task: str = "transcribe"
    beam_size: int = 5
    best_of: Optional[int] = None
    patience: Optional[float] = None
    temperature: float = 0.0
    compression_ratio_threshold: Optional[float] = None
    log_prob_threshold: Optional[float] = None
    no_speech_threshold: float = 0.6
    condition_on_previous_text: bool = True
    vad_filter: bool = True
    vad_threshold: Optional[float] = None
    initial_prompt: Optional[str] = None
    word_timestamps: bool = True
    include_punctuation: bool = False
    output_format: str = "txt"
    compute_type: str = "float16"
    device: str = "auto"  # 新增设备选择参数
    use_precompiled: bool = False  # 是否使用预编译应用
    apply_standard_formatting: bool = False  # 是否应用标准格式化（例如 --standard 预设）
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert parameters to dictionary.

        Returns:
            Dict[str, Any]: Dictionary representation of parameters.
        """
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptionParameters":
        """Create parameters from dictionary.
        
        Args:
            data: Dictionary containing parameter values.
            
        Returns:
            TranscriptionParameters: Parameter object.
        """
        # 过滤掉不在类属性中的键
        valid_params = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**valid_params) 