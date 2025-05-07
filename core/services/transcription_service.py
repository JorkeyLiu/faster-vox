#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
转录服务 - 执行、取消转录任务
"""

import os
from pathlib import Path
from typing import Dict, Any
from loguru import logger
from PySide6.QtCore import QObject
import traceback
import time
import platform
import subprocess
import re
import importlib.util

from core.models.transcription_model import (
    TranscriptionResult, 
    TranscriptionSegment,
    TranscriptionParameters
)
from core.models.error_model import ErrorCategory, ErrorPriority, ErrorInfo
from core.models.task_model import ProcessStatus
from core.services.config_service import ConfigService
from core.services.model_management_service import ModelManagementService
from core.services.audio_service import AudioService
from core.services.environment_service import EnvironmentService
from core.whisper_manager import WhisperManager
from core.utils.export_utils import export_transcription as export_transcription_util, dict_to_transcription_result
from core.services.error_handling_service import ErrorHandlingService
from core.models.environment_model import EnvironmentInfo
from core.events import (
    event_bus, EventTypes,
    TranscriptionProgressEvent, TranscriptionCompletedEvent, TranscriptionErrorEvent,
    WorkerProgressEvent, WorkerCompletedEvent, WorkerFailedEvent, WorkerCancelledEvent, # 添加新事件
    RequestStartProcessingEvent, RequestCancelProcessingEvent,
    TaskStateChangedEvent, TaskAssignedEvent, TranscriptionStartedEvent, TaskStartedEvent, # 重命名 TaskProcessingStartedEvent
    EnvironmentStatusEvent
)
from core.services.task_service import TaskService

class TranscriptionService(QObject):
    """转录服务 - 处理音频转录工作，集成模型控制逻辑
    
    功能：
    1. 处理音频文件转录
    2. 提供取消和暂停功能
    3. 管理转录任务进度
    4. 生成转录结果
    5. 负责环境检测和转录策略决策
    """
    
    def __init__(self, config_service: ConfigService, model_service: ModelManagementService,
                audio_service: AudioService, whisper_manager: WhisperManager,
                environment_service: EnvironmentService,
                error_service: ErrorHandlingService = None,
                task_service = TaskService):
        """初始化转录服务
        
        Args:
            config_service: 配置服务
            model_service: 模型管理服务
            audio_service: 音频服务
            whisper_manager: Whisper管理器
            environment_service: 环境服务
            error_service: 错误处理服务
        """
        super().__init__()
        
        # 保存依赖服务
        self.config_service = config_service
        self.model_service = model_service
        self.audio_service = audio_service
        self.whisper_manager = whisper_manager
        self.environment_service = environment_service
        self.error_service = error_service
        self.task_service = task_service
        
        # 获取环境信息对象
        self.environment_info = self.environment_service.get_environment_info()
        
        # 初始化活动任务字典 - 只保存临时文件等少量信息
        self.active_tasks = {}
        
        # 活动工作线程字典
        self.active_workers = {}
        
        # 创建并初始化转录参数
        self.transcription_parameters = TranscriptionParameters()
        
        # 输出目录
        self.output_directory = None
        
        # 初始化参数
        self._init_parameters()
        
        # 订阅事件总线事件
        self._subscribe_to_events()
        
        # 记录环境状态
        logger.info(f"TranscriptionService环境状态：Windows={self.environment_info.is_windows}, GPU={self.environment_info.has_gpu}")
        logger.info(f"  预编译应用可用: {self.environment_info.whisper_app_available}")
        
    def _subscribe_to_events(self):
        """订阅事件总线事件"""
        # 订阅工作线程进度事件
        
        # 订阅新的工作线程结束事件
        event_bus.subscribe(EventTypes.WORKER_COMPLETED, self._handle_worker_completed)
        event_bus.subscribe(EventTypes.WORKER_FAILED, self._handle_worker_failed)
        event_bus.subscribe(EventTypes.WORKER_CANCELLED, self._handle_worker_cancelled)
        
        # 订阅请求开始处理事件
        event_bus.subscribe(EventTypes.REQUEST_START_PROCESSING, self._handle_request_start_processing)
        
        # 订阅请求取消处理事件
        event_bus.subscribe(EventTypes.REQUEST_CANCEL_PROCESSING, self._handle_request_cancel_processing)
        
        # 订阅任务分配事件
        event_bus.subscribe(EventTypes.TASK_ASSIGNED, self._handle_task_assigned)
        
        # 订阅CUDA环境下载完成事件
        event_bus.subscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._handle_cuda_env_download_completed)
        
        # 订阅模型加载完成事件
        event_bus.subscribe(EventTypes.MODEL_LOADED, self._handle_model_loaded)

        # 订阅配置变更事件
        event_bus.subscribe(EventTypes.CONFIG_CHANGED, self._on_config_changed)
        
        # 订阅环境状态变更事件
        event_bus.subscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._handle_environment_status_changed)
    
    
    # --- 新的事件处理方法 ---
    def _handle_worker_completed(self, event: WorkerCompletedEvent):
        """处理工作线程成功完成事件"""
        task_id = event.task_id
        if task_id not in self.active_tasks:
            logger.warning(f"收到未跟踪任务的工作线程完成事件: {task_id}")
            return

        # 清理工作线程引用
        self.active_workers.pop(task_id, None)

        task_info = self.active_tasks.get(task_id, {})
        audio_file = task_info.get("audio_file", "<未知>")
        file_name = os.path.basename(audio_file) if audio_file != "<未知>" else "<未知>"
        logger.info(f"转录成功: 文件='{file_name}', 任务ID={task_id}")

        if 'results' in event.data and 'audio_file' in event.data:
            results = event.data.get('results', [])
            audio_file = event.data.get('audio_file', '')

            # 导出转录结果
            result_obj = dict_to_transcription_result({
                "results": results,
                "audio_file": audio_file
            })
            try:
                configured_format = self.config_service.get_default_format().lower()
                valid_formats = ["srt", "vtt", "txt", "json", "tsv"]
                if configured_format not in valid_formats:
                    logger.warning(f"配置的导出格式 '{configured_format}' 无效，将使用默认 'srt' 格式。")
                    configured_format = "srt"
            except Exception as e:
                logger.error(f"读取导出格式配置时出错: {e}，将使用默认 'srt' 格式。")
                configured_format = "srt"

            base, _ = os.path.splitext(audio_file)
            ext_map = { "srt": ".srt", "vtt": ".vtt", "txt": ".txt", "json": ".json", "tsv": ".tsv" }
            suffix = ext_map.get(configured_format, ".srt")
            expected_export_path = base + suffix

            export_success = export_transcription_util(result_obj, audio_file, format_type=configured_format)

            if export_success:
                if self.task_service:
                    try:
                        if self.task_service.complete_task(task_id, expected_export_path):
                             logger.info(f"已调用 TaskService.complete_task: 任务ID={task_id}, 输出路径={expected_export_path}")
                        else:
                             logger.error(f"调用 TaskService.complete_task 失败: 任务ID={task_id}")
                    except Exception as e:
                        logger.error(f"调用 TaskService.complete_task 时出错: {str(e)}")
            else:
                logger.error(f"导出转录结果失败: 文件={audio_file}")
                # 发布错误事件，让TaskService处理失败状态
                error_msg = "导出结果失败"
                event_data = TranscriptionErrorEvent(
                    task_id=task_id,
                    error=error_msg,
                    details={"source": "export", "audio_file": audio_file}
                )
                event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, event_data)

        else:
            error_msg = "工作线程完成但缺少必要数据"
            logger.error(f"转录失败: 文件='{file_name}', 任务ID={task_id}, 错误={error_msg}")
            if self.error_service:
                error_info = ErrorInfo(
                    message=f"文件 '{file_name}' 转录数据不完整",
                    category=ErrorCategory.AUDIO, priority=ErrorPriority.HIGH,
                    code="TRANSCRIPTION_DATA_INCOMPLETE",
                    details={"missing_data": True, "worker_data": event.data},
                    source="TranscriptionService._handle_worker_completed", user_visible=True
                )
                self.error_service.handle_error(error_info)
            event_data = TranscriptionErrorEvent(
                task_id=task_id, error=error_msg,
                details={"source": "worker", "missing_data": True}
            )
            event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, event_data)

        # 移除任务
        self.active_tasks.pop(task_id, None)
        self._check_and_unload_model() # Restore call

    def _handle_worker_failed(self, event: WorkerFailedEvent):
        """处理工作线程失败事件"""
        task_id = event.task_id
        if task_id not in self.active_tasks:
            logger.warning(f"收到未跟踪任务的工作线程失败事件: {task_id}")
            return

        # 清理工作线程引用
        self.active_workers.pop(task_id, None)

        task_info = self.active_tasks.get(task_id, {})
        audio_file = task_info.get("audio_file", "<未知>")
        model_name = task_info.get("model_name", "<未知>")
        file_name = os.path.basename(audio_file) if audio_file != "<未知>" else "<未知>"
        error_msg = event.error or "未知错误"

        logger.error(f"转录失败: 文件='{file_name}', 任务ID={task_id}, 错误={error_msg}")

        error_details = {
            "source": "worker",
            "audio_file": audio_file,
            "model_name": model_name
        }
        if event.details:
             error_details.update(event.details)

        if self.error_service:
            error_info = ErrorInfo(
                message=f"文件 '{file_name}' 转录失败: {error_msg}",
                category=ErrorCategory.AUDIO, priority=ErrorPriority.HIGH,
                code="TRANSCRIPTION_WORKER_FAILED", details=error_details,
                source="TranscriptionService._handle_worker_failed", user_visible=True
            )
            self.error_service.handle_error(error_info)

        event_data = TranscriptionErrorEvent(
            task_id=task_id, error=error_msg, details=error_details
        )
        event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, event_data)

        # 移除任务
        self.active_tasks.pop(task_id, None)
        self._check_and_unload_model() # Restore call

    def _handle_worker_cancelled(self, event: WorkerCancelledEvent):
        """处理工作线程取消事件"""
        task_id = event.task_id
        if task_id not in self.active_tasks:
            logger.warning(f"收到未跟踪任务的工作线程取消事件: {task_id}")
            return

        # 清理工作线程引用
        self.active_workers.pop(task_id, None)

        task_info = self.active_tasks.get(task_id, {})
        audio_file = task_info.get("audio_file", "<未知>")
        file_name = os.path.basename(audio_file) if audio_file != "<未知>" else "<未知>"

        logger.info(f"转录已取消: 文件='{file_name}', 任务ID={task_id}")

        # 调用TaskService将任务状态设置为CANCELLED
        if self.task_service:
            try:
                if self.task_service.cancel_task(task_id):
                    logger.info(f"已调用 TaskService.cancel_task: 任务ID={task_id}")
                else:
                    logger.error(f"调用 TaskService.cancel_task 失败: 任务ID={task_id}")
            except Exception as e:
                logger.error(f"调用 TaskService.cancel_task 时出错: {str(e)}")

        # 移除任务
        self.active_tasks.pop(task_id, None)
        self._check_and_unload_model() # Restore call

    def _check_and_unload_model(self):
        """检查是否所有任务完成，如果是，则请求卸载模型"""
        if not self.active_tasks:
            logger.info("所有活动任务已处理完成，请求卸载模型")
            # 调用 ModelManagementService 来卸载模型
            # ModelManagementService 内部会处理实际的卸载逻辑
            if self.model_service.unload_model():
                 logger.info("已成功请求模型卸载")
            else:
                 logger.warning("请求模型卸载失败或无需卸载")

            # 广播全局转录完成事件 (可能需要审查其语义)
            try:
                # 假设导入在顶部
                from core.events.event_types import TranscriptionCompletedEvent
                completed_event = TranscriptionCompletedEvent() # Removed total_duration argument
                event_bus.publish(EventTypes.TRANSCRIPTION_COMPLETED, completed_event)
                logger.info("已广播全局转录完成事件 (TranscriptionCompletedEvent)")
            except Exception as e:
                logger.error(f"广播全局转录完成事件失败: {str(e)}")

    def _init_parameters(self):
        """初始化转录参数"""
        # 从配置服务加载参数
        if self.config_service:
            # 加载默认模型
            default_model = self.config_service.get_model_name()
            if default_model:
                self.transcription_parameters.model_name = default_model
            
            # 加载转录参数
            self.transcription_parameters.beam_size = self.config_service.get_beam_size()
            self.transcription_parameters.compute_type = self.config_service.get_compute_type()
            self.transcription_parameters.device = self.config_service.get_device()
            self.transcription_parameters.word_timestamps = self.config_service.get_word_timestamps()
            self.transcription_parameters.vad_filter = self.config_service.get_vad_filter()
            self.transcription_parameters.task = self.config_service.get_task()
            self.transcription_parameters.temperature = self.config_service.get_temperature()
            self.transcription_parameters.condition_on_previous_text = self.config_service.get_condition_on_previous_text()
            self.transcription_parameters.no_speech_threshold = self.config_service.get_no_speech_threshold()
            self.transcription_parameters.include_punctuation = self.config_service.get_punctuation()
            
            # 加载输出格式
            if hasattr(self.config_service, "get_default_format"):
                self.transcription_parameters.output_format = self.config_service.get_default_format()
            
            # 加载默认语言（仅当不是"auto"时才设置）
            if hasattr(self.config_service, "get_default_language"):
                default_language = self.config_service.get_default_language()
                if default_language and default_language != "auto":
                    self.transcription_parameters.language = default_language
                
            # 加载输出目录
            output_dir = self.config_service.get_output_directory()
            if output_dir and os.path.isdir(output_dir):
                self.output_directory = output_dir
            
            logger.info("已从配置加载转录参数")
    
    def _handle_transcription_completed(self, task_id: str, export_path: str):
        """处理转录完成
        
        Args:
            task_id: 任务ID
            export_path: 导出文件路径
        """
        # 更新任务状态为完成
        
        # 创建转录完成事件
        event_data = TranscriptionCompletedEvent(
            task_id=task_id,
            output_path=export_path,
            duration=self._get_task_duration(task_id),
            language=self.transcription_parameters.language
        )
        
        # 发布转录完成事件
        event_bus.publish(EventTypes.TRANSCRIPTION_COMPLETED, event_data)
        
        # 尝试处理下一个任务
        self._process_next_task()

    def _handle_model_error(self, task_id: str, error_msg: str):
        """处理模型相关错误
        
        Args:
            task_id: 任务ID
            error_msg: 错误信息
        """
        # 记录错误
        logger.error(f"模型错误：{error_msg}")
        
        # 创建转录错误事件
        error_event = TranscriptionErrorEvent(
            task_id=task_id,
            error=error_msg,
            details={"source": "model"}
        )
        
        # 发布转录错误事件
        event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, error_event)

    def _handle_audio_error(self, task_id: str, error_msg: str):
        """处理音频相关错误
        
        Args:
            task_id: 任务ID
            error_msg: 错误信息
        """
        # 记录错误
        logger.error(f"音频错误：{error_msg}")
        
        # 创建转录错误事件
        error_event = TranscriptionErrorEvent(
            task_id=task_id,
            error=error_msg,
            details={"source": "audio"}
        )
        
        # 发布转录错误事件
        event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, error_event)

    def _handle_transcription_error(self, task_id: str, error_msg: str):
        """处理转录过程中的错误
        
        Args:
            task_id: 任务ID
            error_msg: 错误信息
        """
        # 记录错误
        logger.error(f"转录错误：{error_msg}")
        
        # 创建转录错误事件
        error_event = TranscriptionErrorEvent(
            task_id=task_id,
            error=error_msg,
            details={"source": "transcription"}
        )
        
        # 发布转录错误事件
        event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, error_event)

    def transcribe_task(self, task_id: str, audio_file: str) -> bool:
        """转录任务
        
        Args:
            task_id: 任务ID
            audio_file: 音频文件路径
            
        Returns:
            bool: 是否成功启动转录
        """
        # 检查任务是否已存在
        if task_id in self.active_tasks:
            logger.warning(f"任务已存在: {task_id}")
            return False
        
        # 获取模型路径 - 使用model_service获取
        model_name = self.transcription_parameters.model_name
        model_path = None
        
        try:
            # 获取模型数据
            model_data = self.model_service.get_model_data(model_name)
            if model_data and model_data.is_exists:
                model_path = model_data.model_path
                # 不再设置模型信息到WhisperManager
                logger.info(f"使用模型路径: {model_path}")
            
            if not model_path:
                error_msg = f"无法获取模型路径: {model_name}"
                logger.error(error_msg)
                
                # 创建转录错误事件
                event_data = TranscriptionErrorEvent(
                    task_id=task_id,
                    error=error_msg
                )
                event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, event_data)
                return False
        except Exception as e:
            error_msg = f"获取模型路径失败: {str(e)}"
            logger.error(error_msg)
            
            # 创建转录错误事件
            event_data = TranscriptionErrorEvent(
                task_id=task_id,
                error=error_msg
            )
            event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, event_data)
            return False
        
        # 创建任务信息
        self.active_tasks[task_id] = {
            "audio_file": audio_file,
            "model_name": model_name,
            "status": "preparing",
            "start_time": time.time()
        }
        
        # 发布单个任务处理开始事件
        task_started_event = TaskStartedEvent(task_id=task_id, file_path=audio_file)
        event_bus.publish(EventTypes.TASK_STARTED, task_started_event)
        
        try:
            # 在任务开始前刷新环境状态，确保使用最新状态
            self.refresh_environment()
            
            final_device = self.transcription_parameters.device
            use_precompiled = False # 默认使用 Python 策略

            if final_device == 'cpu':
                logger.info(f"任务 {task_id}: 检测到最终设备为 CPU，强制使用 Python 库策略")
                use_precompiled = False
            else: # 设备是 'cuda' 或 'auto'
                logger.info(f"任务 {task_id}: 检测到最终设备为 {final_device}，尝试选择最佳策略")
                # 优先尝试预编译应用进行 GPU 加速
                if self.environment_info.can_use_gpu_acceleration():
                    use_precompiled = True
                    logger.info(f"任务 {task_id}: 使用预编译应用执行转录 (GPU 加速)")
                # 如果 GPU 可用但环境未就绪，尝试下载环境，本次任务回退到 Python
                elif self.environment_info.should_download_cuda_env():
                    logger.info(f"任务 {task_id}: 检测到 GPU 但预编译应用/环境不可用，尝试下载")
                    self._download_cuda_environment()
                    use_precompiled = False # 本次任务回退到 Python
                    logger.info(f"任务 {task_id}: 回退到 Python 库 (已启动预编译应用/环境下载)")
                # 其他情况（如非 Windows、预编译应用不可用等）也使用 Python 库
                else:
                    use_precompiled = False
                    strategy_reason = "非 Windows 平台或预编译应用/环境不可用"
                    logger.info(f"任务 {task_id}: 使用 Python 库执行转录 ({strategy_reason})")

            # 设置预编译标志到转录参数 (此行保留)
            self.transcription_parameters.use_precompiled = use_precompiled
            
            # 获取音频信息
            audio_duration = 0.0
            try:
                audio_info = self.audio_service.get_audio_info(audio_file)
                audio_duration = audio_info.get("duration", 0.0) if audio_info else 0.0
                logger.info(f"获取到音频时长: {audio_duration}秒，传递给WhisperManager")
            except Exception as e:
                logger.warning(f"获取音频时长失败: {str(e)}")
            
            # 使用Whisper管理器创建转录工作线程 - 直接传递参数对象
            worker = self.whisper_manager.create_transcription_worker(
                audio_file=audio_file,
                model_path=model_path,  # 传入模型路径
                audio_duration=audio_duration,  # 传递音频时长
                parameters=self.transcription_parameters,  # 直接传递参数对象
                task_id=task_id,
                worker_id=f"worker_{task_id}"
            )
            
            # 保存工作线程引用
            self.active_workers[task_id] = worker
            
            # 启动工作线程
            worker.start()
            logger.info(f"开始转录任务: {task_id}, 模型: {model_name}, 模型路径: {model_path}, 使用预编译: {use_precompiled}")
            return True
        
        except Exception as e:
            logger.error(f"启动转录任务失败: {task_id}, 错误: {str(e)}")
            
            # 记录错误
            if self.error_service:
                error_info = ErrorInfo(
                    message=f"启动转录任务失败: {str(e)}",
                    category=ErrorCategory.AUDIO,
                    priority=ErrorPriority.HIGH,
                    code="TRANSCRIPTION_START_FAILED",
                    details={"task_id": task_id, "audio_file": audio_file},
                    source="TranscriptionService.transcribe_task",
                    user_visible=True
                )
                self.error_service.handle_error(error_info)
            
            # 从活动任务和工作线程中移除
            self.active_tasks.pop(task_id, None)
            self.active_workers.pop(task_id, None)
            
            # 发布错误事件
            event_data = TranscriptionErrorEvent(
                task_id=task_id,
                error=f"启动转录任务失败: {str(e)}"
            )
            event_bus.publish(EventTypes.TRANSCRIPTION_ERROR, event_data)
            
            return False

    def cancel_process(self, task_id: str):
        """取消转录处理
        
        Args:
            task_id: 任务ID
        """
        logger.info(f"取消转录任务: {task_id}")
        
        # 取消工作线程
        if task_id in self.active_workers:
            worker = self.active_workers[task_id]
            # 调用工作线程的cancel方法
            try:
                worker.cancel()
                logger.info(f"已取消工作线程: {task_id}")
            except Exception as e:
                logger.error(f"取消工作线程失败: {task_id}, 错误: {str(e)}")
        else:
            logger.warning(f"未找到工作线程: {task_id}")
        
        # 创建转录取消事件
        cancel_event = TranscriptionProgressEvent(
            task_id=task_id,
            text="正在取消..."
        )
        
        # 发布转录取消事件
        event_bus.publish(EventTypes.TRANSCRIPTION_CANCELLED, cancel_event)
    
    def _cleanup_task(self, task_id: str):
        """清理任务资源
        
        Args:
            task_id: 任务ID
        """
        # 清理工作线程引用
        self.active_workers.pop(task_id, None)
        
        if task_id in self.active_tasks:
            task_context = self.active_tasks[task_id]
            temp_audio_file = task_context.get("temp_audio_file")
            
            # 清理临时音频文件
            if temp_audio_file and os.path.exists(temp_audio_file):
                try:
                    os.remove(temp_audio_file)
                    logger.info(f"[{task_id}] 已删除临时音频文件: {temp_audio_file}")
                except Exception as e:
                    logger.warning(f"[{task_id}] 删除临时音频文件失败: {str(e)}")
            
            # 从活动任务中移除
            del self.active_tasks[task_id]
            logger.info(f"[{task_id}] 已清理任务资源")
    
    def _process_next_task(self):
        """处理下一个任务 - 通过发布事件请求开始处理下一个任务"""
        # 发布请求开始处理事件
        model_name = self.transcription_parameters.model_name
        event_data = RequestStartProcessingEvent(model_name=model_name)
        event_bus.publish(EventTypes.REQUEST_START_PROCESSING, event_data)
        logger.info("请求处理下一个任务")

    def _handle_request_start_processing(self, event: RequestStartProcessingEvent):
        """处理请求开始处理事件
        
        Args:
            event: 请求开始处理事件
        """
        logger.info("接收到开始处理请求")
        
        # 如果指定了模型名称，更新转录参数
        if event.model_name and self.transcription_parameters:
            self.transcription_parameters.model_name = event.model_name
            logger.info(f"更新要使用的模型: {event.model_name}")
        
        # 注意：不再主动获取待处理任务
        # TranscriptionService现在等待TaskAssignedEvent事件来处理特定任务
    
    def _handle_request_cancel_processing(self, event: RequestCancelProcessingEvent):
        """处理请求取消处理事件
        
        Args:
            event: 请求取消处理事件
        """
        logger.info("接收到取消处理请求")
        
        # 取消所有当前活动的任务
        for task_id in list(self.active_tasks.keys()):
            # 发送取消请求状态 - 发布任务状态变更事件
            task_state_event = TaskStateChangedEvent(
                task_id=task_id,
                status=ProcessStatus.CANCELLING
            )
            event_bus.publish(EventTypes.TASK_STATE_CHANGED, task_state_event)
            
            # 执行取消处理
            self.cancel_process(task_id)
        
        if self.active_tasks:
            logger.info("正在取消所有处理任务...")
        else:
            logger.info("没有活动任务需要取消")

    def _handle_task_assigned(self, event: TaskAssignedEvent):
        """处理任务分配事件
        
        Args:
            event: 任务分配事件
        """
        # 处理分配给此服务的任务
        logger.info(f"收到任务分配事件: {event.task_id}, 文件: {event.file_path}")
        self.transcribe_task(event.task_id, event.file_path)

    def _handle_cuda_env_download_completed(self, event):
        """处理CUDA环境下载完成事件
        
        Args:
            event: CUDA环境下载完成事件
        """
        # 刷新环境状态
        self.refresh_environment()
        
        # 获取当前环境状态
        env_info = self.environment_service.get_environment_info()
        
        # 记录环境变化
        if env_info.whisper_app_available:
            logger.info("CUDA环境下载成功，已启用GPU加速")
        else:
            logger.warning("CUDA环境下载完成，但无法使用GPU加速")

    def _download_cuda_environment(self) -> bool:
        """下载CUDA环境
        
        Returns:
            bool: 是否成功启动下载
        """
        logger.info("触发CUDA环境下载")
        # 调用ModelManagementService下载CUDA环境
        if hasattr(self.model_service, 'download_cuda_environment'):
            return self.model_service.download_cuda_environment()
        return False

    def _handle_model_loaded(self, event_data):
        """处理模型加载完成事件
        
        Args:
            event_data: 模型加载事件数据
        """
        if not event_data.success:
            return
        
        # 获取模型信息
        model_name = event_data.model_name
        
        # 从模型服务获取模型数据
        model_data = self.model_service.get_model_data(model_name)
        if model_data and model_data.is_exists:
            # 更新本地模型信息
            # 如果是当前选中的模型，记录日志
            if model_name == self.transcription_parameters.model_name:
                # 不再更新WhisperManager中的模型信息
                logger.info(f"模型已加载: {model_name}, 路径: {model_data.model_path}")
            else:
                logger.info(f"模型已加载但不是当前选中模型: {model_name}, 路径: {model_data.model_path}")
        else:
            logger.warning(f"模型加载事件通知但模型数据不可用: {model_name}")

    def _on_config_changed(self, event):
        """处理配置变更事件
        
        Args:
            event: 配置变更事件
        """
        key = event.key
        value = event.value
        
        # 根据配置键名更新转录参数
        if key == "device" and hasattr(self.transcription_parameters, "device"):
            self.transcription_parameters.device = value
            logger.info(f"更新转录参数 - 设备: {value}")
        if key == "model_name" and hasattr(self.transcription_parameters, "model_name"):
            self.transcription_parameters.model_name = value
            logger.info(f"更新转录参数 - 模型: {value}")
            
        elif key == "beam_size" and hasattr(self.transcription_parameters, "beam_size"):
            self.transcription_parameters.beam_size = value
            logger.info(f"更新转录参数 - 波束大小: {value}")
            
        elif key == "compute_type" and hasattr(self.transcription_parameters, "compute_type"):
            self.transcription_parameters.compute_type = value
            logger.info(f"更新转录参数 - 计算精度: {value}")
            
        elif key == "device" and hasattr(self.transcription_parameters, "device"):
            self.transcription_parameters.device = value
            logger.info(f"更新转录参数 - 设备: {value}")
            
        elif key == "word_timestamps" and hasattr(self.transcription_parameters, "word_timestamps"):
            self.transcription_parameters.word_timestamps = value
            logger.info(f"更新转录参数 - 单词时间戳: {value}")
            
        elif key == "vad_filter" and hasattr(self.transcription_parameters, "vad_filter"):
            self.transcription_parameters.vad_filter = value
            logger.info(f"更新转录参数 - VAD过滤: {value}")
            
        elif key == "task" and hasattr(self.transcription_parameters, "task"):
            self.transcription_parameters.task = value
            logger.info(f"更新转录参数 - 任务类型: {value}")
            
        elif key == "temperature" and hasattr(self.transcription_parameters, "temperature"):
            value = round(value, 2)
            self.transcription_parameters.temperature = value
            logger.info(f"更新转录参数 - 温度: {value}")
            
        elif key == "condition_on_previous_text" and hasattr(self.transcription_parameters, "condition_on_previous_text"):
            self.transcription_parameters.condition_on_previous_text = value
            logger.info(f"更新转录参数 - 基于前文预测: {value}")
            
        elif key == "no_speech_threshold" and hasattr(self.transcription_parameters, "no_speech_threshold"):
            value = round(value, 2)
            self.transcription_parameters.no_speech_threshold = value
            logger.info(f"更新转录参数 - 无语音阈值: {value}")
            
        elif key == "punctuation" and hasattr(self.transcription_parameters, "include_punctuation"):
            # 特殊处理：配置中的punctuation对应TranscriptionParameters中的include_punctuation
            self.transcription_parameters.include_punctuation = value
            logger.info(f"更新转录参数 - 添加标点: {value}")
            
        elif key == "default_format" and hasattr(self.transcription_parameters, "output_format"):
            # 特殊处理：配置中的default_format对应TranscriptionParameters中的output_format
            self.transcription_parameters.output_format = value
            logger.info(f"更新转录参数 - 输出格式: {value}")
            
        elif key == "default_language" and hasattr(self.transcription_parameters, "language"):
            # 特殊处理：配置中的default_language对应TranscriptionParameters中的language
            # 只有在不是"auto"时才设置语言
            if value and value != "auto":
                self.transcription_parameters.language = value
                logger.info(f"更新转录参数 - 语言: {value}")
            else:
                # 如果是"auto"，则设置为None（自动检测）
                self.transcription_parameters.language = None
                logger.info("更新转录参数 - 语言: 自动检测")
            
        elif key == "output_directory":
            # 特殊处理：输出目录
            if value and os.path.isdir(value):
                self.output_directory = value
                logger.info(f"更新输出目录: {value}")
            elif not value:
                self.output_directory = None
                logger.info("重置输出目录为默认值")

    def _handle_environment_status_changed(self, event: EnvironmentStatusEvent):
        """处理环境状态变更事件
        
        当环境状态发生变化时，此方法会被调用，更新本地环境信息引用。
        转录服务会根据环境变化调整转录策略，如使用预编译应用或Python库。
        
        Args:
            event: 环境状态变更事件
        """
        # 获取新的环境信息
        new_info = event.environment_info
        
        # 如果环境信息没有变化，不需要处理
        if self.environment_info == new_info:
            return
        
        # 检查关键变化
        gpu_changed = self.environment_info.has_gpu != new_info.has_gpu
        precompiled_changed = self.environment_info.whisper_app_available != new_info.whisper_app_available
        
        # 更新本地环境信息引用
        self.environment_info = new_info
        
        # 记录关键变化
        if gpu_changed or precompiled_changed:
            logger.info(f"TranscriptionService: 环境状态已更新 - GPU可用: {new_info.has_gpu}, 预编译应用可用: {new_info.whisper_app_available}")
            if new_info.can_use_gpu_acceleration():
                logger.info("TranscriptionService: 将使用GPU加速转录")
            elif new_info.should_download_cuda_env():
                logger.info("TranscriptionService: 检测到GPU但预编译应用不可用，可下载CUDA环境以加速转录")
            else:
                logger.info("TranscriptionService: 将使用CPU模式转录")

    def __del__(self):
        """对象销毁时取消事件订阅"""
        try:
            # 取消订阅所有事件
            event_bus.unsubscribe(EventTypes.WORKER_COMPLETED, self.handle_worker_completed)
            event_bus.unsubscribe(EventTypes.REQUEST_START_PROCESSING, self._handle_request_start_processing)
            event_bus.unsubscribe(EventTypes.REQUEST_CANCEL_PROCESSING, self._handle_request_cancel_processing)
            event_bus.unsubscribe(EventTypes.TASK_ASSIGNED, self._handle_task_assigned)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._handle_cuda_env_download_completed)
            event_bus.unsubscribe(EventTypes.MODEL_LOADED, self._handle_model_loaded)
            event_bus.unsubscribe(EventTypes.CONFIG_CHANGED, self._on_config_changed)
            event_bus.unsubscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._handle_environment_status_changed)
        except Exception as e:
            # 忽略可能的异常
            logger.debug(f"取消事件订阅时发生异常: {str(e)}")

    def refresh_environment(self):
        """刷新环境状态，使用环境服务重新检测环境"""
        # 使用环境服务刷新环境状态，获取变化信息
        has_changes, changes = self.environment_service.refresh()
        
        # 如果没有变化，无需更新
        if not has_changes:
            return
        
        # 环境服务的refresh方法已经更新了环境信息对象并发布了事件
        # 通过事件处理器_handle_environment_status_changed更新本地引用
        logger.info(f"环境状态已刷新，有变化: {changes}")

