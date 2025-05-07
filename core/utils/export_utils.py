#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""转录结果导出工具函数"""

import os
import json
from pathlib import Path
from loguru import logger

from core.models.transcription_model import TranscriptionResult


from core.models.transcription_model import TranscriptionResult

def dict_to_transcription_result(data: dict) -> TranscriptionResult:
    """将字典转换为TranscriptionResult对象"""
    from types import SimpleNamespace
    segs = data.get("results") or data.get("segments") or []
    # 将字典转换为具备属性的对象
    segments = []
    for seg in segs:
        if isinstance(seg, dict):
            segments.append(SimpleNamespace(**seg))
        else:
            segments.append(seg)
    return TranscriptionResult(
        segments=segments,
        language=data.get("language"),
        language_probability=data.get("language_probability"),
        duration=data.get("duration"),
        source_file=data.get("audio_file")
    )

def export_transcription(result: TranscriptionResult, output_path: str, format_type: str = "srt") -> bool:
    """导出转录结果到文件
    
    Args:
        result: 转录结果对象
        output_path: 输出文件路径
        format_type: 输出格式类型，支持 "srt", "vtt", "txt", "json", "tsv"
    
    Returns:
        bool: 是否成功导出
    """
    try:
        # 自动替换扩展名，避免覆盖原始媒体文件
        base, _ = os.path.splitext(output_path)
        ext_map = {
            "srt": ".srt",
            "vtt": ".vtt",
            "txt": ".txt",
            "json": ".json",
            "tsv": ".tsv"
        }
        suffix = ext_map.get(format_type.lower(), ".srt")
        output_path = base + suffix

        # 如果没有结果，返回失败
        if not result or not result.segments:
            logger.error("导出失败：转录结果为空")
            return False
        
        # 确保输出目录存在
        output_path = Path(output_path)
        os.makedirs(output_path.parent, exist_ok=True)
        
        # 根据格式类型选择导出函数
        format_handlers = {
            "srt": _export_srt,
            "vtt": _export_vtt,
            "txt": _export_txt,
            "json": _export_json,
            "tsv": _export_tsv,
        }
        
        # 检查格式是否支持
        if format_type.lower() not in format_handlers:
            logger.error(f"不支持的导出格式: {format_type}")
            return False
        
        # 调用相应的导出函数
        return format_handlers[format_type.lower()](result, output_path)
    
    except Exception as e:
        logger.error(f"导出转录结果失败: {str(e)}")
        return False


def _export_srt(result: TranscriptionResult, output_path: str) -> bool:
    """导出为SRT格式
    
    Args:
        result: 转录结果对象
        output_path: 输出文件路径
    
    Returns:
        bool: 是否成功导出
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, segment in enumerate(result.segments):
                # 序号
                f.write(f"{i+1}\n")
                
                # 时间码
                start_time = _format_timestamp(segment.start, format_type="srt")
                end_time = _format_timestamp(segment.end, format_type="srt")
                f.write(f"{start_time} --> {end_time}\n")
                
                # 文本
                f.write(f"{segment.text}\n\n")
        
        logger.info(f"成功导出为SRT格式: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"导出SRT格式失败: {str(e)}")
        return False


def _export_vtt(result: TranscriptionResult, output_path: str) -> bool:
    """导出为VTT格式
    
    Args:
        result: 转录结果对象
        output_path: 输出文件路径
    
    Returns:
        bool: 是否成功导出
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入VTT头部
            f.write("WEBVTT\n\n")
            
            for i, segment in enumerate(result.segments):
                # 可选的标记
                f.write(f"{i+1}\n")
                
                # 时间码
                start_time = _format_timestamp(segment.start, format_type="vtt")
                end_time = _format_timestamp(segment.end, format_type="vtt")
                f.write(f"{start_time} --> {end_time}\n")
                
                # 文本
                f.write(f"{segment.text}\n\n")
        
        logger.info(f"成功导出为VTT格式: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"导出VTT格式失败: {str(e)}")
        return False


def _export_txt(result: TranscriptionResult, output_path: str) -> bool:
    """导出为纯文本格式
    
    Args:
        result: 转录结果对象
        output_path: 输出文件路径
    
    Returns:
        bool: 是否成功导出
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            for segment in result.segments:
                f.write(f"{segment.text}\n")
        
        logger.info(f"成功导出为TXT格式: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"导出TXT格式失败: {str(e)}")
        return False


def _export_json(result: TranscriptionResult, output_path: str) -> bool:
    """导出为JSON格式
    
    Args:
        result: 转录结果对象
        output_path: 输出文件路径
    
    Returns:
        bool: 是否成功导出
    """
    try:
        # 创建结果字典
        result_dict = {
            "segments": [
                {
                    "id": segment.id,
                    "start": segment.start,
                    "end": segment.end,
                    "text": segment.text,
                    "words": segment.words
                }
                for segment in result.segments
            ],
            "language": result.language,
            "language_probability": result.language_probability,
            "duration": result.duration,
            "source_file": result.source_file
        }
        
        # 写入JSON文件
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=2)
        
        logger.info(f"成功导出为JSON格式: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"导出JSON格式失败: {str(e)}")
        return False


def _export_tsv(result: TranscriptionResult, output_path: str) -> bool:
    """导出为TSV格式
    
    Args:
        result: 转录结果对象
        output_path: 输出文件路径
    
    Returns:
        bool: 是否成功导出
    """
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            # 写入表头
            f.write("start\tend\ttext\n")
            
            # 写入数据
            for segment in result.segments:
                f.write(f"{segment.start}\t{segment.end}\t{segment.text}\n")
        
        logger.info(f"成功导出为TSV格式: {output_path}")
        return True
    
    except Exception as e:
        logger.error(f"导出TSV格式失败: {str(e)}")
        return False


def _format_timestamp(seconds: float, format_type: str = "srt") -> str:
    """格式化时间戳
    
    Args:
        seconds: 秒数
        format_type: 格式类型，"srt" 或 "vtt"
    
    Returns:
        str: 格式化后的时间戳
    """
    milliseconds = int((seconds - int(seconds)) * 1000)
    
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    
    if format_type == "vtt":
        return f"{h:02d}:{m:02d}:{s:02d}.{milliseconds:03d}"
    else:  # srt
        return f"{h:02d}:{m:02d}:{s:02d},{milliseconds:03d}" 