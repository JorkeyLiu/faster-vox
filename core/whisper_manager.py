#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Whisper管理器 - 混合架构设计，支持Python库和预编译应用
负责智能选择最佳转录实现方式，提供统一接口
"""

import os
import glob
import io
import shutil
import json
import tempfile
import subprocess
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple, Callable
import platform
import time
from loguru import logger
from PySide6.QtCore import QObject, QThread, Signal
from abc import ABC, abstractmethod

from core.models.config import APP_ENV_DIR, WHISPER_EXE_PATH # WHISPER_EXE_PATH is an absolute path
from core.models.error_model import ErrorInfo, ErrorCategory, ErrorPriority
from core.services.config_service import ConfigService
from core.services.notification_service import NotificationService
from core.services.error_handling_service import ErrorHandlingService
from core.models.transcription_model import TranscriptionParameters
from core.events import event_bus, EventTypes, TaskStateChangedEvent, WorkerCompletedEvent, WorkerFailedEvent, WorkerCancelledEvent

from core.utils.parser_utils import ProgressCalculator
# Removed commented out import of get_resource_path as it's confirmed not needed here.


class TranscriptionContext:
    """转录上下文类 - 封装转录相关的共享数据和操作"""
    
    def __init__(self, audio_file: str, model_path: str, output_path: str,
                 parameters: Optional['TranscriptionParameters'] = None,
                 audio_duration: float = 0.0):
        """初始化转录上下文
        
        Args:
            audio_file: 音频文件路径
            model_path: 模型路径
            output_path: 输出文件路径
            parameters: 转录参数对象
            audio_duration: 音频文件时长(秒)
        """
        self.audio_file = audio_file
        self.model_path = model_path
        self.output_path = output_path
        self.parameters = parameters
        self.temp_dir = None
        self.audio_duration = audio_duration
        
        # 任务元数据
        self.task_id = None  # 任务ID
        self.worker_id = None  # 工作线程ID
        
        # 取消控制
        self._is_canceled = False  # 内部取消标志
        self._cancel_check = lambda: False  # 取消检查回调
        
    def prepare(self) -> bool:
        """准备转录环境
        
        Returns:
            bool: 准备是否成功
        """
        try:
            # 创建临时目录
            self.temp_dir = tempfile.mkdtemp(prefix="whisper_temp_")
            
            # 确保parameters不为None
            if self.parameters is None:
                from core.models.transcription_model import TranscriptionParameters
                self.parameters = TranscriptionParameters()
            
            return True
        except Exception as e:
            logger.error(f"准备转录环境失败: {str(e)}")
            return False
            
    def cleanup(self):
        """清理临时文件"""
        if self.temp_dir and os.path.exists(self.temp_dir):
            try:
                shutil.rmtree(self.temp_dir)
                logger.debug(f"已清理临时目录: {self.temp_dir}")
            except Exception as e:
                logger.error(f"清理临时目录失败: {str(e)}")
    
    def set_cancel_check(self, cancel_check: Callable[[], bool]):
        """设置取消检查回调
        
        Args:
            cancel_check: 返回是否应该取消的回调函数
        """
        self._cancel_check = cancel_check
        
    def should_cancel(self) -> bool:
        """检查是否应该取消转录
        
        Returns:
            bool: 是否应该取消
        """
        # 首先检查内部取消标志
        if self._is_canceled:
            return True
        # 然后调用回调检查
        return self._cancel_check() if callable(self._cancel_check) else False
        
    def cancel(self):
        """标记转录为已取消"""
        self._is_canceled = True
                
            
    def update_progress_with_cancel_check(self, position, text: str, check_interval: int = 5, counter: int = None, always_check: bool = True) -> bool:
        """更新进度并检查是否需要取消
        
        Args:
            position: 当前处理位置（秒）或进度值（0-1）
            text: 当前文本
            check_interval: 检查取消的间隔
            counter: 调用计数器（如果提供，则根据counter判断是否检查取消）
            always_check: 当counter为None时是否始终检查取消状态
            
        Returns:
            bool: 是否应该继续（False表示需要取消）
        """

        if counter is not None:
            if counter % check_interval == 0 and self.should_cancel():
                logger.debug("[DEBUG] 通过计数器检测到取消请求")
                return False
        elif always_check and self.should_cancel():
            logger.debug("[DEBUG] 通过始终检查标志检测到取消请求")
            return False
            
        # 如果position是时间位置，则计算进度值
        if position <= 1.0:  # 如果已经是0-1之间的值，则直接使用
            progress = position
        else:  # 否则，将位置转换为进度值
            # 使用 ProgressCalculator 计算进度
            progress = ProgressCalculator.calculate(
                end_time=position,
                audio_duration=self.audio_duration
            )
        
        # 广播统一事件
        try:
            from core.events import event_bus
            from core.events.event_types import EventTypes, TranscriptionProcessInfoEvent
            if self.task_id:
                event_bus.publish(
                    EventTypes.TRANSCRIPTION_PROCESS_INFO,
                    TranscriptionProcessInfoEvent(
                        task_id=self.task_id,
                        process_text=text,
                        progress=progress
                    )
                )
            # logger.debug(f"[DEBUG] 广播转录进度事件: 任务ID={self.task_id}, 进度={progress:.2f}, 文本='{text[:30] + '...' if len(text) > 30 else text}'")
        except Exception as e:
            logger.error(f"广播转录进度事件失败: {str(e)}")
        return True
            
    def get_temp_json_path(self) -> str:
        """获取临时JSON文件路径
        
        Returns:
            str: 临时JSON文件路径
        """
        return os.path.join(self.temp_dir, "output.json") if self.temp_dir else None


class TranscriptionWorker(QThread):
    """转录工作线程"""
    
    # 自定义信号 - 用于工作线程结果通知
    # finished = Signal(bool, str, dict)  # 移除旧信号
    
    def __init__(self, audio_file: str, model_path: str, strategy,
                 audio_duration: float = 0.0, parameters: Optional['TranscriptionParameters'] = None, 
                 task_id: str = None, worker_id: str = None):
        """初始化转录工作线程
        
        Args:
            audio_file: 音频文件路径
            model_path: 模型路径
            strategy: 转录策略
            audio_duration: 音频时长（秒）
            parameters: 转录参数对象
            task_id: 任务ID
            worker_id: 工作线程ID
        """
        super().__init__()
        
        # 基本参数
        self.audio_file = audio_file
        self.model_path = model_path
        self.strategy = strategy
        self.audio_duration = audio_duration
        self.parameters = parameters
        self.task_id = task_id
        self.worker_id = worker_id or f"worker_{int(time.time())}"
        
        # 状态控制
        self._is_canceled = False
        
        logger.info(f"任务 {self.task_id} 的音频时长: {self.audio_duration}秒")
    
    
    def run(self):
        """运行转录线程"""
        logger.info(f"开始执行转录任务：{self.task_id}, 文件: {self.audio_file}")
        
        # 创建转录上下文
        context = TranscriptionContext(
            audio_file=self.audio_file,
            model_path=self.model_path,
            output_path=None,  # 使用临时输出
            parameters=self.parameters,
            audio_duration=self.audio_duration
        )
        
        # 设置任务ID
        context.task_id = self.task_id
        context.worker_id = self.worker_id
        
        # 设置取消检查回调
        context.set_cancel_check(lambda: self._is_canceled)
        
        try:
            # 打印传递给策略的参数
            logger.debug(f"任务 {self.task_id}: 使用转录参数: {vars(context.parameters)}")

            # 调用策略执行转录
            success, error_message, result_data = self.strategy.execute(context)

            # 根据结果发布事件
            if self._is_canceled:
                logger.info(f"任务 {self.task_id} 已取消，发布 WorkerCancelledEvent")
                event_bus.publish(EventTypes.WORKER_CANCELLED, WorkerCancelledEvent(task_id=self.task_id, worker_id=self.worker_id))
                return # 取消后直接返回
                
            if success:
                # 增加音频文件信息
                result_data["audio_file"] = self.audio_file
                logger.info(f"任务 {self.task_id} 成功完成，发布 WorkerCompletedEvent")
                event_bus.publish(EventTypes.WORKER_COMPLETED, WorkerCompletedEvent(task_id=self.task_id, worker_id=self.worker_id, data=result_data))
            else:
                logger.error(f"任务 {self.task_id} 失败: {error_message}，发布 WorkerFailedEvent")
                # 注意：失败时 result_data 可能为空或包含部分信息，放入 details
                event_bus.publish(EventTypes.WORKER_FAILED, WorkerFailedEvent(task_id=self.task_id, worker_id=self.worker_id, error=error_message, details=result_data or {}))
                
        except Exception as e:
            logger.error(f"转录过程中发生异常: {str(e)}")
            # 异常也视为失败
            logger.error(f"任务 {self.task_id} 异常: {str(e)}，发布 WorkerFailedEvent")
            event_bus.publish(EventTypes.WORKER_FAILED, WorkerFailedEvent(task_id=self.task_id, worker_id=self.worker_id, error=f"转录异常: {str(e)}", details={}))
    
    def cancel(self):
        """取消转录任务"""
        logger.info(f"取消转录任务: {self.task_id}")
        self._is_canceled = True


class TranscriptionStrategy(ABC):
    """转录策略抽象基类"""
    
    def __init__(self):
        """初始化转录策略"""
        pass
    
    def execute(self, context: TranscriptionContext) -> Tuple[bool, str, Dict[str, Any]]:
        """执行转录 - 模板方法
        
        Args:
            context: 转录上下文
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (是否成功, 错误消息, 结果数据)
        """
        try:
            # 共同的准备环境逻辑
            if not context.prepare():
                return False, "准备转录环境失败", {}
                
            # 检查是否取消
            if context.should_cancel():
                return False, "转录已取消", {}
            
            # 调用子类实现的具体执行逻辑
            return self._execute_internal(context)
            
        except Exception as e:
            logger.error(f"转录执行异常: {str(e)}")
            return False, f"{self._get_strategy_name()}失败: {str(e)}", {}
        finally:
            # 共同的清理环境逻辑
            context.cleanup()
    
    @abstractmethod
    def _execute_internal(self, context: TranscriptionContext) -> Tuple[bool, str, Dict[str, Any]]:
        """实际执行转录的内部方法 - 由子类实现
        
        Args:
            context: 转录上下文
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (是否成功, 错误消息, 结果数据)
        """
        pass
        
    def _get_strategy_name(self) -> str:
        """获取策略名称，用于错误消息
        
        Returns:
            str: 策略名称
        """
        return self.__class__.__name__
        
    def safe_terminate_process(self, process):
        """安全地终止进程
        
        Args:
            process: 要终止的进程
            
        Returns:
            bool: 是否成功终止
        """
        if not process:
            logger.debug("尝试终止空进程实例，已跳过")
            return True
            
        if process.poll() is None:
            try:
                logger.debug(f"正在尝试正常终止进程...")
                process.terminate()
                process.wait(timeout=5)
                logger.debug(f"进程已成功终止")
                return True
            except Exception as e:
                logger.error(f"终止进程失败: {str(e)}")
                try:
                    logger.debug(f"尝试强制终止进程...")
                    process.kill()  # 强制终止
                    logger.debug(f"进程已被强制终止")
                    return True
                except Exception as e:
                    logger.error(f"强制终止进程失败: {str(e)}")
                    return False
        else:
            logger.debug(f"进程已不存在或已终止，无需操作")
        return True  # 进程已不存在或已终止


class PythonTranscriptionStrategy(TranscriptionStrategy):
    """Python库转录策略"""
    
    def __init__(self):
        """初始化Python库转录策略
        """
        super().__init__()
    
    def _process_segments(self, segments, word_timestamps=True) -> List[Dict[str, Any]]:
        """处理转录片段，将其转换为可序列化的字典格式
        
        Args:
            segments: 转录结果中的片段列表
            word_timestamps: 是否包含词级时间戳
            
        Returns:
            List[Dict[str, Any]]: 处理后的片段列表
        """
        result = []
        for segment in segments:
            # 格式化时间戳函数 (辅助)
            def format_timestamp(seconds: float) -> str:
                milliseconds = int(seconds * 1000)
                minutes = milliseconds // 60000
                seconds = (milliseconds % 60000) // 1000
                ms = milliseconds % 1000
                return f"{minutes:02d}:{seconds:02d}.{ms:03d}"

            # 将片段对象转换为字典
            segment_dict = {
                "id": segment.id,
                "seek": segment.seek,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text, # 保留原始文本
                # 新增格式化文本字段
                "formatted_text": f"[{format_timestamp(segment.start)} --> {format_timestamp(segment.end)}] {segment.text}",
                "tokens": segment.tokens,
                "temperature": segment.temperature,
                "avg_logprob": segment.avg_logprob,
                "compression_ratio": segment.compression_ratio,
                "no_speech_prob": segment.no_speech_prob,
            }
            
            # 如果有词级时间戳，添加到结果中
            if word_timestamps and hasattr(segment, "words") and segment.words:
                segment_dict["words"] = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "probability": word.probability
                    }
                    for word in segment.words
                ]
            
            result.append(segment_dict)
        
        return result
    
    def _execute_internal(self, context: TranscriptionContext) -> Tuple[bool, str, Dict[str, Any]]:
        """实际执行转录的内部方法 - 由子类实现
        
        Args:
            context: 转录上下文
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (是否成功, 错误消息, 结果数据)
        """
        model = None # Ensure model is defined in the scope
        try:
            # 导入faster-whisper 和 torch (如果需要清理缓存)
            try:
                from faster_whisper import WhisperModel
                logger.debug("成功导入 faster_whisper")
            except ImportError as import_err:
                logger.error(f"导入依赖库失败: {import_err}")
                return False, f"缺少依赖库: {import_err}", {}
                
            # 记录开始时间
            start_time = time.time()
            
            # 模型加载信息日志
            logger.info(f"任务 {context.task_id}: 开始加载Whisper模型: {context.model_path}")
            
            device = context.parameters.device if hasattr(context.parameters, 'device') else "auto"
            compute_type = context.parameters.compute_type
            
            # 初始化WhisperModel
            model = WhisperModel(
                context.model_path,
                device=device,
                compute_type=compute_type
            )

            # 模型加载完成日志
            load_time = time.time() - start_time
            logger.info(f"任务 {context.task_id}: 模型加载完成，用时: {load_time:.2f} 秒")
            
            # 检查是否已取消
            if context.should_cancel():
                logger.info(f"任务 {context.task_id}: 在转录开始前检测到取消请求")
                return False, "转录已取消", {}
            
            # 开始转录
            logger.info(f"任务 {context.task_id}: 开始转录音频文件: {context.audio_file}")

            segments_generator, info = model.transcribe( # 修改变量名
                context.audio_file,
                language=context.parameters.language,
                task=context.parameters.task,
                beam_size=context.parameters.beam_size,
                word_timestamps=context.parameters.word_timestamps,
                vad_filter=context.parameters.vad_filter,
                no_speech_threshold=context.parameters.no_speech_threshold,
                condition_on_previous_text=context.parameters.condition_on_previous_text,
                temperature=context.parameters.temperature
            )

            # 初始化收集变量
            processed_segments = []
            full_text = ""
            
            # 添加新的实时处理循环
            segment_counter = 0
            for segment in segments_generator:
                segment_counter += 1
                # 处理当前 segment
                # 注意：_process_segments 期望一个列表，所以传入 [segment]
                processed_segment_list = self._process_segments([segment], context.parameters.word_timestamps)
                
                formatted_text_for_progress = segment.text # 默认使用原始文本以防处理失败
                if processed_segment_list:
                    current_processed_segment = processed_segment_list[0]
                    processed_segments.append(current_processed_segment)
                    # 获取格式化后的文本用于进度更新
                    formatted_text_for_progress = current_processed_segment.get("formatted_text", segment.text)
                
                full_text += segment.text

                # 实时更新进度和文本（使用格式化后的文本），并检查取消
                if not context.update_progress_with_cancel_check(
                    position=segment.end,
                    text=formatted_text_for_progress, # 使用格式化后的文本
                    always_check=True # 每次迭代都检查取消
                ):
                    logger.info(f"任务 {context.task_id}: 在处理片段 {segment_counter} 时检测到取消请求")
                    return False, "转录已取消", {}

            logger.info(f"任务 {context.task_id}: 所有片段处理完毕，共 {segment_counter} 个片段。")

            # 记录完成时间
            end_time = time.time()
            transcription_time = end_time - start_time - load_time # 仅计算转录时间
            logger.info(f"任务 {context.task_id}: 转录处理完成，用时: {transcription_time:.2f} 秒 (不含模型加载)")

            # 更新最终结果构建
            adapted_result = {
                "results": processed_segments,  # 使用收集到的处理后片段
                "language": info.language,
                "text": full_text,             # 使用拼接的完整文本
                "audio_file": context.audio_file,
                # 添加更多信息
                "duration": info.duration,
                "language_probability": info.language_probability
            }
            logger.debug(f"任务 {context.task_id}: Python策略适配后的结果键: {list(adapted_result.keys())}")
            return True, "", adapted_result

        except Exception as e:
             logger.error(f"任务 {context.task_id}: 在 PythonTranscriptionStrategy._execute_internal 中发生错误: {e}")
             logger.exception(e) # 记录堆栈跟踪
             return False, f"转录执行失败: {e}", {}
        # Removed the finally block that incorrectly unloaded the model after each task


class PrecompiledTranscriptionStrategy(TranscriptionStrategy):
    """预编译应用转录策略"""
    
    def __init__(self, config_service: ConfigService):
        """初始化预编译应用转录策略

        Args:
            config_service: 配置服务实例
        """
        super().__init__()
        self.config_service = config_service
    
    def _execute_internal(self, context: TranscriptionContext) -> Tuple[bool, str, Dict[str, Any]]:
        """实际执行转录的内部方法 - 由子类实现
        
        Args:
            context: 转录上下文
        
        Returns:
            Tuple[bool, str, Dict[str, Any]]: (是否成功, 错误消息, 结果数据)
        """
        process = None
        try:
            # 准备输出JSON路径
            temp_json = context.get_temp_json_path()
            
            # WHISPER_EXE_PATH is an absolute path imported from core.models.config
            # No need for get_resource_path here.
            whisper_exe = str(WHISPER_EXE_PATH)
            
            # 获取预编译应用路径
            if not os.path.exists(whisper_exe):
                return False, f"预编译应用不存在: {whisper_exe}", {} # Removed reference to RELATIVE_WHISPER_EXE_PATH
            
            # 构建命令行参数
            cmd = [
                str(whisper_exe),  # 确保是字符串
                "--model", str(getattr(context.parameters, "model_name", "tiny")),
                "--output_dir", context.temp_dir,  # 使用临时目录作为输出目录
                "--output_format", "json"
            ]
            
            # 添加模型目录参数（动态获取）
            if self.config_service:
                model_dir = self.config_service.get_model_directory()
                cmd.extend(["--model_dir", model_dir])
                logger.debug(f"[DEBUG] 使用模型目录: {model_dir}")

            # 添加其他选项
            if context.parameters.language:
                cmd.extend(["--language", context.parameters.language])
            
            cmd.extend(["--task", context.parameters.task])
            cmd.extend(["--beam_size", str(context.parameters.beam_size)]) # 使用下划线
            
            if context.parameters.word_timestamps:
                cmd.extend(["--word_timestamps", str(context.parameters.word_timestamps)]) # 显式传递True/False
            
            cmd.extend(["--no_speech_threshold", str(context.parameters.no_speech_threshold)]) # 使用下划线

            # --- 添加缺失的参数检查和命令行标志 ---
            if context.parameters.temperature is not None:
                cmd.extend(["--temperature", str(context.parameters.temperature)])
            # 修正布尔参数传递方式
            if context.parameters.condition_on_previous_text is not None: # 检查是否存在，以防万一
                cmd.extend(["--condition_on_previous_text", str(context.parameters.condition_on_previous_text)])
            if context.parameters.vad_filter is not None: # 检查是否存在
                cmd.extend(["--vad_filter", str(context.parameters.vad_filter)])
            if context.parameters.compute_type:
                cmd.extend(["--compute_type", str(context.parameters.compute_type)])
            if context.parameters.device:
                cmd.extend(["--device", str(context.parameters.device)])
            
            # 音频文件参数必须放在最后
            cmd.append(str(context.audio_file))
            
            # 执行命令
            creation_flags = 0
            if platform.system() == "Windows":
                creation_flags = subprocess.CREATE_NO_WINDOW
            
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=creation_flags
            )
            
            # 添加调试日志
            logger.debug(f"[DEBUG] 启动预编译应用进程，命令: {' '.join(cmd)}")
            
            # 检查是否已取消
            if process.poll() is not None:
                return False, f"预编译应用启动失败，返回码: {process.returncode}", {}
            
            # 同时启动stderr读取
            import threading
            def read_stderr(proc):
                # 尝试使用系统首选编码解码，失败则忽略错误
                import locale
                preferred_encoding = locale.getpreferredencoding(False)
                try:
                    # 使用io.TextIOWrapper指定编码和错误处理
                    for err_line in io.TextIOWrapper(proc.stderr, encoding=preferred_encoding, errors='ignore'):
                        err_line = err_line.strip()
                        if err_line:
                            logger.warning(f"[STDERR] {err_line}")
                except Exception as e:
                    logger.error(f"读取stderr失败: {str(e)}")

            stderr_thread = threading.Thread(target=read_stderr, args=(process,), daemon=True)
            stderr_thread.start()

            # 使用io.TextIOWrapper读取stdout，保持utf-8
            for line in io.TextIOWrapper(process.stdout, encoding='utf-8', errors='ignore'):
                # 定期检查是否取消
                if context.should_cancel():
                    # 主动终止进程
                    self.safe_terminate_process(process)
                    return False, "转录已取消", {}
                
                line = line.strip()
                logger.debug(f"[STDOUT] {line}")
                
                # 使用新工具类解析Whisper输出行
                try:
                    from core.utils.parser_utils import TranscriptParser, ProgressCalculator
                    parsed = TranscriptParser.parse_line(line)
                    if parsed:
                        # logger.debug(f"[DEBUG] 解析Whisper输出: {parsed}")
                        end_time = parsed["end"]
                        percentage = ProgressCalculator.calculate(end_time, context.audio_duration)
                        # 使用原始行文本（包含时间戳等信息）更新进度
                        if not context.update_progress_with_cancel_check(percentage, line):
                            self.safe_terminate_process(process)
                            return False, "转录已取消", {}
                except Exception as e:
                    logger.error(f"解析Whisper输出失败: {str(e)}")
            
            # 等待进程完成
            return_code = process.wait()
            process = None  # 进程已结束，清除引用
            
            # 检查进程是否成功
            if return_code != 0 and return_code != 3221226505:
                stderr_output = "" 
                if process and process.stderr:
                    stderr_output = process.stderr.read()
                return False, f"预编译应用执行失败，返回码: {return_code}, 错误: {stderr_output}", {}
                
            # 根据音频文件名推测结果文件路径
            audio_name = os.path.splitext(os.path.basename(context.audio_file))[0]
            candidate_json = os.path.join(context.temp_dir, f"{audio_name}.json")

            if os.path.exists(candidate_json):
                result_json_path = candidate_json
            else:
                # 备选方案：取目录下最新的json文件
                json_files = glob.glob(os.path.join(context.temp_dir, "*.json"))
                if not json_files:
                    return False, f"预编译应用未生成任何JSON结果文件，目录: {context.temp_dir}", {}
                json_files.sort(key=os.path.getmtime, reverse=True)
                result_json_path = json_files[0]

            # 读取JSON结果
            with open(result_json_path, 'r', encoding='utf-8') as f:
                result_data = json.load(f)
                # 适配TranscriptionService预期格式
                adapted_result = {
                    "results": result_data.get("segments", []),
                    "language": result_data.get("language"),
                    "text": result_data.get("text"),
                    "audio_file": context.audio_file
                }
                return True, "", adapted_result
            return True, "", result_data
        finally:
            # 确保进程被正确关闭
            self.safe_terminate_process(process)


class WhisperManager(QObject):
    """Whisper管理器 - 纯执行转录功能
    
    提供转录执行功能：
    1. 使用Python库实现 (faster-whisper)
    2. 使用预编译Whisper应用（当TranscriptionService选择时）
    """
    
    def __init__(self, 
                config_service: ConfigService, 
                error_service: ErrorHandlingService,
                notification_service: NotificationService):
        """初始化Whisper管理器
        
        Args:
            config_service: 配置服务
            error_service: 错误处理服务
            notification_service: 通知服务
        """
        super().__init__()
        
        # 保存依赖服务
        self.config_service = config_service
        self.error_service = error_service
        self.notification_service = notification_service
        
        # 内部状态
        self.tasks = {}  # 存储当前正在运行的任务
        self.env_dir = APP_ENV_DIR
        
        # 初始化策略
        self.python_strategy = PythonTranscriptionStrategy()
        self.precompiled_strategy = PrecompiledTranscriptionStrategy(config_service)
        
    
    def create_transcription_worker(self, audio_file: str, model_path: str, 
                                   audio_duration: float = 0.0,
                                   parameters: Optional[TranscriptionParameters] = None, 
                                   task_id: str = None, worker_id: str = None) -> TranscriptionWorker:
        """创建转录工作线程
        
        Args:
            audio_file: 音频文件路径
            model_path: 模型路径
            audio_duration: 音频时长（秒）
            parameters: 转录参数对象
            task_id: 任务ID
            worker_id: 工作线程ID
            
        Returns:
            TranscriptionWorker: 转录工作线程
        """
        # 选择策略 - 由TranscriptionService决定
        if parameters is None:
            from core.models.transcription_model import TranscriptionParameters
            parameters = TranscriptionParameters()
        
        # 根据use_precompiled参数选择策略
        strategy = self.precompiled_strategy if parameters.use_precompiled else self.python_strategy
        
        worker = TranscriptionWorker(
            audio_file=audio_file,
            model_path=model_path,
            strategy=strategy,
            audio_duration=audio_duration,
            parameters=parameters,
            task_id=task_id,
            worker_id=worker_id
        )
        
        return worker
    
    