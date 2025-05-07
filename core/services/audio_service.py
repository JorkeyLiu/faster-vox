#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
音频服务 - 负责音频处理和转换
"""

import os
import subprocess
import hashlib
import time
import tempfile
import json
from pathlib import Path
from typing import List, Dict, Optional, Any
from PySide6.QtCore import QObject
from loguru import logger
from core.utils.file_utils import get_supported_media_extensions
from core.models.error_model import ErrorInfo, ErrorCategory, ErrorPriority
from core.events import event_bus, EventTypes, AudioExtractedEvent

class AudioService(QObject):
    """音频服务类，负责音频处理和转换"""
    
    def __init__(self, parent=None, error_service=None):
        """初始化音频服务
        
        Args:
            parent: 父对象
            error_service: 错误处理服务，可选
        """
        super().__init__(parent)
        self.error_service = error_service
    
    # ----------------------
    # 公共方法
    # ----------------------
    
    @staticmethod
    def get_supported_formats() -> List[str]:
        """获取支持的音频和视频格式
        
        Returns:
            List[str]: 支持的音频和视频格式列表
        """
        return get_supported_media_extensions()
    
    def check_ffmpeg(self) -> bool:
        """检查FFmpeg是否可用
        
        Returns:
            bool: 如果FFmpeg可用返回True，否则返回False
        """
        result = self._check_ffmpeg()
        if not result:
            error_msg = "FFmpeg未安装或不可用，无法处理音频"
            if self.error_service:
                error_info = ErrorInfo(
                    message=error_msg,
                    category=ErrorCategory.RESOURCE,
                    priority=ErrorPriority.HIGH,
                    code="FFMPEG_NOT_AVAILABLE",
                    source="AudioService.check_ffmpeg",
                    user_visible=True
                )
                self.error_service.handle_error(error_info)
            else:
                logger.error(error_msg)
        return result
    
    def get_audio_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取音频文件信息
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            Dict[str, Any]: 包含音频信息的字典，如果获取失败则返回None
        """
        try:
            result = self._get_audio_info(file_path)
            if result is None:
                error_msg = f"获取音频信息失败: {file_path}"
                if self.error_service:
                    error_info = ErrorInfo(
                        message=error_msg,
                        category=ErrorCategory.AUDIO,
                        priority=ErrorPriority.MEDIUM,
                        code="AUDIO_INFO_FAILED",
                        details={"file_path": file_path},
                        source="AudioService.get_audio_info",
                        user_visible=True
                    )
                    self.error_service.handle_error(error_info)
                else:
                    logger.error(error_msg)
            return result
        except Exception as e:
            error_msg = f"获取音频信息失败: {str(e)}"
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.AUDIO,
                    ErrorPriority.MEDIUM,
                    "AudioService.get_audio_info",
                    user_visible=True
                )
            else:
                logger.error(error_msg)
            return None
    
    def convert_audio(
        self, 
        input_path: str, 
        output_path: str, 
        sample_rate: int = 16000,
        channels: int = 1,
        format: str = "wav"
    ) -> bool:
        """转换音频文件格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            sample_rate: 采样率
            channels: 通道数
            format: 输出格式
            
        Returns:
            bool: 转换成功返回True，否则返回False
        """
        try:
            result = self._convert_audio(
                input_path=input_path,
                output_path=output_path,
                sample_rate=sample_rate,
                channels=channels,
                format=format
            )
            if not result:
                error_msg = f"转换音频失败: {input_path} -> {output_path}"
                if self.error_service:
                    error_info = ErrorInfo(
                        message=error_msg,
                        category=ErrorCategory.AUDIO,
                        priority=ErrorPriority.MEDIUM,
                        code="AUDIO_CONVERSION_FAILED",
                        details={"input_path": input_path, "output_path": output_path},
                        source="AudioService.convert_audio",
                        user_visible=True
                    )
                    self.error_service.handle_error(error_info)
                else:
                    logger.error(error_msg)
            return result
        except Exception as e:
            error_msg = f"转换音频失败: {str(e)}"
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.AUDIO,
                    ErrorPriority.MEDIUM,
                    "AudioService.convert_audio",
                    user_visible=True
                )
            else:
                logger.error(error_msg)
            return False
    
    def extract_audio_from_video(
        self, 
        video_path: str, 
        output_path: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> Optional[str]:
        """从视频文件中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径，如果为None则自动生成
            sample_rate: 采样率
            channels: 通道数
            
        Returns:
            str: 输出音频文件路径，如果失败返回None
        """
        try:
            # 检查输入文件是否存在
            if not os.path.exists(video_path):
                error_msg = f"视频文件不存在: {video_path}"
                logger.error(error_msg)
                if self.error_service:
                    error_info = ErrorInfo(
                        message=error_msg,
                        category=ErrorCategory.FILE_IO,
                        priority=ErrorPriority.HIGH,
                        code="FILE_NOT_FOUND",
                        details={"file_path": video_path},
                        source="AudioService.extract_audio_from_video"
                    )
                    self.error_service.handle_error(error_info)
                return None
            
            result = self._extract_audio_from_video(
                video_path=video_path,
                output_path=output_path,
                sample_rate=sample_rate,
                channels=channels
            )
            
            if result:
                # 发布音频提取完成事件
                event_data = AudioExtractedEvent(
                    file_path=video_path,
                    audio_path=result
                )
                event_bus.publish(EventTypes.AUDIO_EXTRACTED, event_data)
            else:
                error_msg = f"从视频提取音频失败: {video_path}"
                if self.error_service:
                    error_info = ErrorInfo(
                        message=error_msg,
                        category=ErrorCategory.AUDIO,
                        priority=ErrorPriority.MEDIUM,
                        code="AUDIO_EXTRACTION_FAILED",
                        details={"video_path": video_path},
                        source="AudioService.extract_audio_from_video",
                        user_visible=True
                    )
                    self.error_service.handle_error(error_info)
                else:
                    logger.error(error_msg)
                
            return result
        except Exception as e:
            logger.error(f"从视频提取音频失败: {str(e)}")
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.AUDIO,
                    ErrorPriority.MEDIUM,
                    "AudioService.extract_audio_from_video"
                )
            return None
            
    def split_audio(
        self, 
        input_path: str, 
        output_dir: str,
        segment_duration: int = 300,  # 5分钟
        overlap: int = 0
    ) -> List[str]:
        """将长音频分割成较小的片段
        
        Args:
            input_path: 输入音频文件路径
            output_dir: 输出目录
            segment_duration: 每个片段的时长（秒）
            overlap: 片段之间的重叠时间（秒）
            
        Returns:
            List[str]: 生成的音频片段文件路径列表
        """
        try:
            result = self._split_audio(
                input_path=input_path,
                output_dir=output_dir,
                segment_duration=segment_duration,
                overlap=overlap
            )
            
            if not result:
                error_msg = f"分割音频失败: {input_path}"
                if self.error_service:
                    error_info = ErrorInfo(
                        message=error_msg,
                        category=ErrorCategory.AUDIO,
                        priority=ErrorPriority.MEDIUM,
                        code="AUDIO_SPLIT_FAILED",
                        details={"input_path": input_path, "output_dir": output_dir},
                        source="AudioService.split_audio",
                        user_visible=True
                    )
                    self.error_service.handle_error(error_info)
                else:
                    logger.error(error_msg)
                
            return result
        except Exception as e:
            error_msg = f"分割音频失败: {str(e)}"
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.AUDIO,
                    ErrorPriority.MEDIUM,
                    "AudioService.split_audio",
                    user_visible=True
                )
            else:
                logger.error(error_msg)
            return []
    
    # ----------------------
    # 私有方法 (从audio_utils.py移植)
    # ----------------------
    
    def _check_ffmpeg(self) -> bool:
        """检查FFmpeg是否可用
        
        Returns:
            bool: 如果FFmpeg可用返回True，否则返回False
        """
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], 
                check=True, 
                capture_output=True,
                text=False  # 使用二进制模式
            )
            # 不需要检查输出内容，只需要确认命令执行成功
            return True
        except (subprocess.SubprocessError, FileNotFoundError):
            logger.error("FFmpeg未安装或不可用")
            return False


    def _get_audio_info(self, file_path: str) -> Optional[Dict[str, Any]]:
        """获取音频文件信息
        
        Args:
            file_path: 音频文件路径
            
        Returns:
            Dict[str, Any]: 包含音频信息的字典，如果获取失败则返回None
            {
                'duration': 音频时长（秒）,
                'sample_rate': 采样率,
                'channels': 通道数,
                'bit_depth': 位深度,
                'format': 文件格式,
                'codec': 编解码器,
                'bitrate': 比特率
            }
        """
        try:
            if not self._check_ffmpeg():
                return None
            
            # 检查文件是否存在
            if not os.path.exists(file_path):
                logger.error(f"文件不存在: {file_path}")
                return None
            
            # 使用FFprobe获取音频信息
            cmd = [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                "-show_streams",
                file_path
            ]
            
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=False  # 使用二进制模式
            )
            
            # 显式解码输出
            stdout_text = result.stdout.decode('utf-8', errors='replace')
            data = json.loads(stdout_text)
            
            # 查找音频流
            audio_stream = None
            for stream in data.get("streams", []):
                if stream.get("codec_type") == "audio":
                    audio_stream = stream
                    break
            
            if audio_stream is None:
                logger.error(f"未找到音频流: {file_path}")
                return None
            
            # 提取音频信息
            format_info = data.get("format", {})
            
            audio_info = {
                "duration": float(format_info.get("duration", 0)),
                "sample_rate": int(audio_stream.get("sample_rate", 0)),
                "channels": int(audio_stream.get("channels", 0)),
                "bit_depth": int(audio_stream.get("bits_per_sample", 0)) or None,
                "format": format_info.get("format_name", ""),
                "codec": audio_stream.get("codec_name", ""),
                "bitrate": int(audio_stream.get("bit_rate", 0)) or int(format_info.get("bit_rate", 0))
            }
            
            return audio_info
        except Exception as e:
            logger.error(f"获取音频信息失败: {str(e)}")
            return None


    def _convert_audio(
        self, 
        input_path: str, 
        output_path: str, 
        sample_rate: int = 16000,
        channels: int = 1,
        format: str = "wav"
    ) -> bool:
        """转换音频文件格式
        
        Args:
            input_path: 输入文件路径
            output_path: 输出文件路径
            sample_rate: 采样率
            channels: 通道数
            format: 输出格式
            
        Returns:
            bool: 转换成功返回True，否则返回False
        """
        try:
            if not self._check_ffmpeg():
                return False
            
            # 检查输入文件是否存在
            if not os.path.exists(input_path):
                logger.error(f"输入文件不存在: {input_path}")
                return False
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # 设置音频编解码器
            codec = "pcm_s16le" if format == "wav" else "libmp3lame" if format == "mp3" else "flac"
            
            # 使用FFmpeg转换音频
            cmd = [
                "ffmpeg",
                "-i", input_path,
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-c:a", codec,
                "-y", output_path
            ]
            
            logger.info(f"转换音频: {input_path} -> {output_path}")
            
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True,
                text=False  # 使用二进制模式
            )
            
            # 如果出错，记录错误信息
            if result.stderr:
                stderr_text = result.stderr.decode('utf-8', errors='replace')
                if stderr_text.strip():
                    logger.debug(f"FFmpeg输出: {stderr_text}")
            
            return os.path.exists(output_path)
        except subprocess.CalledProcessError as e:
            # 显式解码错误输出
            stderr_text = e.stderr.decode('utf-8', errors='replace') if e.stderr else ""
            logger.error(f"转换音频失败: {stderr_text}")
            return False
        except Exception as e:
            logger.error(f"转换音频失败: {str(e)}")
            return False


    def _split_audio(
        self, 
        input_path: str, 
        output_dir: str,
        segment_duration: int = 300,  # 5分钟
        overlap: int = 0
    ) -> List[str]:
        """将长音频分割成较小的片段
        
        Args:
            input_path: 输入音频文件路径
            output_dir: 输出目录
            segment_duration: 每个片段的时长（秒）
            overlap: 片段之间的重叠时间（秒）
            
        Returns:
            List[str]: 生成的音频片段文件路径列表
        """
        try:
            if not self._check_ffmpeg():
                return []
            
            # 检查输入文件是否存在
            if not os.path.exists(input_path):
                logger.error(f"输入文件不存在: {input_path}")
                return []
            
            # 确保输出目录存在
            os.makedirs(output_dir, exist_ok=True)
            
            # 获取音频信息
            audio_info = self._get_audio_info(input_path)
            if audio_info is None:
                return []
            
            total_duration = audio_info["duration"]
            
            # 计算分割点
            segments = []
            start_time = 0
            
            while start_time < total_duration:
                end_time = min(start_time + segment_duration, total_duration)
                output_path = os.path.join(
                    output_dir, 
                    f"{Path(input_path).stem}_{int(start_time)}_{int(end_time)}.wav"
                )
                
                # 使用FFmpeg分割音频
                cmd = [
                    "ffmpeg",
                    "-i", input_path,
                    "-ss", str(start_time),
                    "-to", str(end_time),
                    "-c:a", "copy",
                    "-y", output_path
                ]
                
                logger.info(f"分割音频: {start_time}s - {end_time}s -> {output_path}")
                
                result = subprocess.run(
                    cmd, 
                    check=True, 
                    capture_output=True,
                    text=False  # 使用二进制模式
                )
                
                # 如果出错，记录错误信息
                if result.stderr:
                    stderr_text = result.stderr.decode('utf-8', errors='replace')
                    if stderr_text.strip():
                        logger.debug(f"FFmpeg输出: {stderr_text}")
                
                if os.path.exists(output_path):
                    segments.append(output_path)
                
                # 计算下一个片段的起始时间
                start_time = end_time - overlap
            
            logger.info(f"音频分割完成，生成了 {len(segments)} 个片段")
            return segments
        except subprocess.CalledProcessError as e:
            # 显式解码错误输出
            stderr_text = e.stderr.decode('utf-8', errors='replace') if e.stderr else ""
            logger.error(f"分割音频失败: {stderr_text}")
            return []
        except Exception as e:
            logger.error(f"分割音频失败: {str(e)}")
            return []

    def _extract_audio_from_video(
        self, 
        video_path: str, 
        output_path: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1
    ) -> Optional[str]:
        """从视频文件中提取音频
        
        Args:
            video_path: 视频文件路径
            output_path: 输出音频文件路径，如果为None则自动生成
            sample_rate: 采样率
            channels: 通道数
            
        Returns:
            str: 输出音频文件路径，如果失败返回None
        """
        try:
            # 检查FFmpeg是否可用
            if not self._check_ffmpeg():
                logger.error("FFmpeg未安装或不可用，无法提取音频")
                return None
            
            # 检查输入文件是否存在
            if not os.path.exists(video_path):
                error_msg = f"视频文件不存在: {video_path}"
                logger.error(error_msg)
                if self.error_service:
                    error_info = ErrorInfo(
                        message=error_msg,
                        category=ErrorCategory.FILE_IO,
                        priority=ErrorPriority.HIGH,
                        code="FILE_NOT_FOUND",
                        details={"file_path": video_path},
                        source="AudioService.extract_audio_from_video"
                    )
                    self.error_service.handle_error(error_info)
                return None
            
            # 如果未指定输出路径，则自动生成
            if output_path is None:
                # 使用系统临时目录
                temp_dir = tempfile.gettempdir()
                video_file = Path(video_path)
                
                # 使用哈希值代替文件名，避免中文路径问题
                file_hash = hashlib.md5(video_file.stem.encode('utf-8')).hexdigest()[:8]
                timestamp = int(time.time())
                output_path = str(Path(temp_dir) / f"faster_vox_temp_{file_hash}_{timestamp}.wav")
            
            # 确保输出目录存在
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            # 使用FFmpeg提取音频
            cmd = [
                "ffmpeg",
                "-i", video_path,
                "-vn",  # 禁用视频
                "-ar", str(sample_rate),
                "-ac", str(channels),
                "-c:a", "pcm_s16le",
                "-y", output_path
            ]
            
            logger.info(f"从视频提取音频: {video_path} -> {output_path}")
            
            # 执行命令并捕获输出，使用二进制模式
            result = subprocess.run(
                cmd, 
                check=True, 
                capture_output=True,
                text=False  # 使用二进制模式避免编码问题
            )
            
            # 如果有错误输出，记录到日志
            if result.stderr:
                stderr_text = result.stderr.decode('utf-8', errors='replace')
                if stderr_text.strip():
                    logger.debug(f"FFmpeg输出: {stderr_text}")
            
            # 检查输出文件是否存在且大小大于0
            if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                logger.info(f"音频提取成功: {output_path}")
                return output_path
            else:
                logger.error(f"音频提取失败，输出文件不存在或为空: {output_path}")
                # 如果文件存在但为空，尝试删除
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        logger.debug(f"删除空的输出文件: {output_path}")
                    except Exception:
                        pass
                return None
                
        except subprocess.CalledProcessError as e:
            # 显式解码错误输出
            stderr_text = e.stderr.decode('utf-8', errors='replace') if e.stderr else ""
            logger.error(f"FFmpeg命令执行失败: {e}")
            logger.debug(f"FFmpeg错误输出: {stderr_text}")
            return None
        except Exception as e:
            logger.error(f"从视频提取音频失败: {str(e)}")
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.AUDIO,
                    ErrorPriority.MEDIUM,
                    "AudioService.extract_audio_from_video"
                )
            return None 
