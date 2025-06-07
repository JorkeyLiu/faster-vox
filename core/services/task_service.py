#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
任务服务 - 负责管理任务的添加、删除、状态更新和状态通知等
整合了原TaskStateService和TaskService的功能，作为任务状态的唯一真实来源
使用事件总线进行通信，同时支持向后兼容的信号机制
"""

import os
import time
from typing import Dict, List, Optional, Tuple, Any, Set
from loguru import logger
from PySide6.QtCore import QObject, Signal, QTimer
from pathlib import Path

from core.models.error_model import ErrorCategory, ErrorInfo, ErrorPriority
from core.models.task_model import Task, ProcessStatus
from core.events import (
    event_bus, EventTypes, 
    TaskStateChangedEvent, TaskAddedEvent, TaskRemovedEvent,
    RequestAddTasksEvent, RequestRemoveTaskEvent, RequestClearTasksEvent,
    RequestStartProcessingEvent, RequestCancelProcessingEvent,
    TranscriptionProgressEvent, TranscriptionCompletedEvent, TranscriptionErrorEvent,
    TaskTimerUpdatedEvent, TaskAssignedEvent
)
from core.services.audio_service import AudioService
from core.utils import file_utils # 导入整个file_utils模块
from core.utils.file_utils import is_supported_media_file, FileSystemUtils, get_files_from_folder # 保持原有导入，但现在可以直接使用file_utils.get_file_extension
from core.services.config_service import ConfigService

class TaskService(QObject):
    """任务服务 - 管理任务状态和生命周期
    
    整合了原TaskStateService和TaskService的功能
    """
    
    def __init__(self,
                 config_service: Optional[ConfigService] = None,
                 audio_service = None,
                 error_service = None):
        """初始化任务服务
        
        Args:
            config_service: 配置服务
            audio_service: 音频服务
            error_service: 错误处理服务
        """
        super().__init__()
        
        # 任务字典和计数器
        self.tasks: Dict[str, Task] = {}
        self.task_counter = 1  # 任务计数器
        
        # 使用依赖注入
        self.config_service = config_service
        self.audio_service = audio_service
        self.error_service = error_service
        
        # 活跃任务计时器
        self.active_task_timer = QTimer(self)
        self.active_task_timer.setInterval(1000)  # 1000毫秒 = 1秒
        self.active_task_timer.timeout.connect(self._update_active_task_timer)
        # 初始不启动，只在任务开始时启动
        
        # 当前活跃任务ID
        self.active_task_id = None
        
        # 订阅事件总线事件
        self._subscribe_to_events()
    
    
    
    def _subscribe_to_events(self):
        """订阅事件总线事件"""
        # 订阅请求添加任务事件
        event_bus.subscribe(EventTypes.REQUEST_ADD_TASKS, self._handle_request_add_tasks)
        
        # 订阅请求移除任务事件
        event_bus.subscribe(EventTypes.REQUEST_REMOVE_TASK, self._handle_request_remove_task)
        
        # 订阅请求清空任务事件
        event_bus.subscribe(EventTypes.REQUEST_CLEAR_TASKS, self._handle_request_clear_tasks)
        
        # 订阅请求开始处理事件
        event_bus.subscribe(EventTypes.REQUEST_START_PROCESSING, self._handle_request_start_processing)
        
        # 订阅请求取消处理事件
        event_bus.subscribe(EventTypes.REQUEST_CANCEL_PROCESSING, self._handle_request_cancel_processing)
        
        # 订阅转录状态事件
        event_bus.subscribe(EventTypes.TRANSCRIPTION_PROGRESS, self._handle_transcription_progress)
        # 移除 TASK_STATE_CHANGED 订阅
        event_bus.subscribe(EventTypes.TRANSCRIPTION_ERROR, self._handle_transcription_error)
        # 移除 TRANSCRIPTION_COMPLETED 订阅 (已在之前步骤移除)
    
    def _handle_request_add_tasks(self, event: RequestAddTasksEvent):
        """处理请求添加任务事件
        
        Args:
            event: 请求添加任务事件
        """
        logger.info(f"处理请求添加任务事件: {len(event.file_paths)} 个文件")
        # 调用内部方法添加任务
        self.add_tasks(event.file_paths)
    
    def _handle_request_remove_task(self, event: RequestRemoveTaskEvent):
        """处理请求移除任务事件
        
        Args:
            event: 请求移除任务事件
        """
        logger.info(f"处理请求移除任务事件: {event.task_id}")
        # 调用内部方法移除任务
        self.remove_task(event.task_id)
    
    def _handle_request_clear_tasks(self, event: RequestClearTasksEvent):
        """处理请求清空任务事件
        
        Args:
            event: 请求清空任务事件
        """
        logger.info("处理请求清空任务事件")
        # 调用内部方法清空任务
        self.clear_all_tasks()
    
    def _handle_request_start_processing(self, event: RequestStartProcessingEvent):
        """处理请求开始处理事件
        
        Args:
            event: 请求开始处理事件
        """
        logger.info("处理请求开始处理事件")
        # 获取所有待处理的任务
        pending_tasks = self.get_pending_tasks()
        
        # 如果没有待处理的任务，记录日志并返回
        if not pending_tasks:
            logger.debug("没有待处理的任务")
            return
            
        # 设置模型名称（如果有）
        # 注意：现在由TranscriptionService自己处理模型名称设置
        
        # 初始化所有任务状态
        for task_id, _ in pending_tasks:
            self.mark_task_as_waiting(task_id)
            
        # 只处理第一个任务，其他任务等待处理
        if pending_tasks:
            first_task_id, first_file_path = pending_tasks[0]
            # 更新任务状态为"开始处理"
            self.start_task(first_task_id)
            
            # 发布任务分配事件，通知转录服务处理任务
            task_assigned_event = TaskAssignedEvent(
                task_id=first_task_id,
                file_path=first_file_path
            )
            event_bus.publish(EventTypes.TASK_ASSIGNED, task_assigned_event)
            
            # 记录日志
            file_name = Path(first_file_path).name
            logger.info(f"分配任务: {file_name} 给转录服务处理")
    
    def _handle_request_cancel_processing(self, event: RequestCancelProcessingEvent):
        """处理请求取消处理事件
        
        Args:
            event: 请求取消处理事件
        """
        logger.info("处理请求取消处理事件")
        # 找到所有正在处理的任务并取消
        active_tasks = self.get_active_tasks()
        if active_tasks:
            for task_id in active_tasks:
                # 更新任务状态为"取消中"
                self.request_cancel_task(task_id)
                # 发布取消处理事件，由TranscriptionService自行处理
                cancel_event = RequestCancelProcessingEvent()
                    
            logger.info("正在取消所有处理任务...")
    
    def _handle_transcription_progress(self, event: TranscriptionProgressEvent):
        """处理转录进度事件
        
        Args:
            event: 转录进度事件
        """
        # 更新任务进度
        self.set_task_progress(event.task_id, event.progress)
    
    def _handle_transcription_error(self, event: TranscriptionErrorEvent):
        """处理转录错误事件
        
        Args:
            event: 转录错误事件
        """
        # 详细记录错误
        logger.error(f"收到转录错误事件: 任务ID={event.task_id}, 错误={event.error}")
        
        # 检查任务是否存在
        if event.task_id in self.tasks:
            # 设置错误信息
            self.tasks[event.task_id].error = event.error
            
            # 记录详细的任务信息
            task = self.tasks[event.task_id]
            file_name = os.path.basename(task.file_path)
            logger.error(f"转录失败: 文件={file_name}, 任务ID={event.task_id}, 错误={event.error}")
            
            # 使用错误处理服务
            if self.error_service:
                error_info = ErrorInfo(
                    message=f"文件 '{file_name}' 转录失败: {event.error}",
                    category=ErrorCategory.AUDIO,
                    priority=ErrorPriority.HIGH,
                    code="TRANSCRIPTION_ERROR",
                    details={"task_id": event.task_id, "file_path": task.file_path},
                    source="TaskService._handle_transcription_error",
                    user_visible=True  # 确保错误对用户可见
                )
                self.error_service.handle_error(error_info)
        else:
            logger.warning(f"收到未知任务的转录错误事件: {event.task_id}")
        
        # 更新任务状态为失败
        self.mark_task_as_failed(event.task_id, error_message=event.error)
    
    def add_task(self, file_path: str) -> str:
        """添加任务
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 任务ID
        """
        # 创建任务ID
        task_id = f"task_{int(time.time())}_{len(self.tasks) + 1}"
        
        # 创建任务对象
        task = Task(task_id, file_path)
        
        # 添加到任务列表
        self.tasks[task_id] = task
        
        # 发布任务添加事件
        file_name = Path(file_path).name
        event_data = TaskAddedEvent(
            task_id=task_id,
            file_path=file_path,
            file_name=file_name
        )
        event_bus.publish(EventTypes.TASK_ADDED, event_data)
        
        # 返回任务ID
        return task_id
    
    def remove_task(self, task_id: str) -> bool:
        """移除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功移除
        """
        if task_id in self.tasks:
            # 删除之前的任务状态
            self.tasks.pop(task_id)
            
            # 发布任务移除事件
            event_data = TaskRemovedEvent(task_id=task_id)
            event_bus.publish(EventTypes.TASK_REMOVED, event_data)
            
            return True
        return False
    
    def update_task_state(self, task_id: str, status: ProcessStatus, progress: float = None, 
                          error: str = None, output_path: str = None):
        """更新任务状态
        
        Args:
            task_id: 任务ID
            status: 任务状态
            progress: 任务进度（可选）
            error: 错误信息（可选）
            output_path: 输出文件路径（可选）
            
        Returns:
            bool: 是否成功更新
        """
        # 检查任务是否存在
        if task_id not in self.tasks:
            return False
        
        # 获取任务对象
        task = self.tasks[task_id]
        
        # 更新状态
        previous_status = task.status
        task.status = status
        
        # 更新进度
        if progress is not None:
            task.progress = float(progress)
        
        # 更新错误信息
        if error is not None:
            task.error = error
        
        # 更新输出文件
        if output_path is not None:
            task.output_path = output_path
        
        # 更新开始时间（如果从待处理状态变为开始或进行中）
        if previous_status == ProcessStatus.WAITING and status in [ProcessStatus.STARTED, ProcessStatus.IN_PROGRESS]:
            task.start_time = time.time()
        
        # 更新结束时间（如果进入完成、失败或取消状态）
        if status in [ProcessStatus.COMPLETED, ProcessStatus.FAILED, ProcessStatus.CANCELLED]:
            if task.start_time > 0:
                task.end_time = time.time()
                task.duration = task.end_time - task.start_time
        
        
        # 发布任务状态变化事件
        event_data = TaskStateChangedEvent(
            task_id=task_id,
            status=status,
            progress=task.progress,
            error=error or task.error,
            output_path=output_path or task.output_path
        )
        event_bus.publish(EventTypes.TASK_STATE_CHANGED, event_data)
        
        return True
    
    def get_task_state(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
        
        Returns:
            Optional[Dict[str, Any]]: 任务状态，如果不存在则返回None
        """
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        return {
            "task_id": task.id,
            "status": task.status,
            "progress": task.progress,
            "error": task.error,
            "output_path": task.output_path
        }
        
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取指定ID的任务对象
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[Task]: 任务对象，如果未找到则返回None
        """
        return self.tasks.get(task_id)
    
    def get_active_tasks(self) -> List[str]:
        """获取所有活动任务的ID
        
        Returns:
            List[str]: 活动任务ID列表
        """
        active_tasks = []
        
        for task_id, task in self.tasks.items():
            if task.status in Task.ACTIVE_STATUSES:
                active_tasks.append(task_id)
        
        return active_tasks
    
    def get_pending_tasks(self) -> List[Tuple[str, str]]:
        """获取所有待处理的任务
        
        Returns:
            List[Tuple[str, str]]: 待处理任务的元组列表，每个元组包含任务ID和文件路径
        """
        pending_tasks = []
        for task_id, task in self.tasks.items():
            if task.status == ProcessStatus.WAITING:
                pending_tasks.append((task_id, task.file_path))
        return pending_tasks
    
    def get_completed_tasks(self) -> List[str]:
        """获取所有已完成的任务
        
        Returns:
            List[str]: 已完成任务ID列表
        """
        completed_tasks = []
        
        for task_id, task in self.tasks.items():
            if task.status == ProcessStatus.COMPLETED:
                completed_tasks.append(task_id)
        
        return completed_tasks
    
    def get_failed_tasks(self) -> List[str]:
        """获取所有失败的任务
        
        Returns:
            List[str]: 失败任务ID列表
        """
        failed_tasks = []
        failed_statuses = [
            ProcessStatus.FAILED,
            ProcessStatus.CANCELLED
        ]
        
        for task_id, task in self.tasks.items():
            if task.status in failed_statuses:
                failed_tasks.append(task_id)
        
        return failed_tasks

    def clear_all_tasks(self):
        """清空所有任务"""
        # 获取所有任务ID
        task_ids = list(self.tasks.keys())
        
        # 移除每个任务并发送相应信号
        for task_id in task_ids:
            # 使用remove_task处理每个任务的移除通知
            self.remove_task(task_id)
        
        logger.info("已清空所有任务")
    
    # TaskStateService兼容方法
    def clear_all_tasks_for_observer(self):
        """清空所有任务（为观察者定义的方法，保持向后兼容）"""
        self.clear_all_tasks()
    
    def get_active_tasks(self) -> List[str]:
        """获取所有活动任务的ID
        
        Returns:
            List[str]: 活动任务ID列表
        """
        active_tasks = []
        
        for task_id, task in self.tasks.items():
            if task.status in Task.ACTIVE_STATUSES:
                active_tasks.append(task_id)
        
        return active_tasks

    def _add_task(self, file_path: str) -> str:
        """添加单个任务（私有方法）
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 任务ID，如果添加失败则返回空字符串
        """
        # 验证文件路径
        if not os.path.exists(file_path):
            logger.warning(f"文件不存在: {file_path}")
            return ""
        
        # 验证文件类型
        if not is_supported_media_file(file_path):
            logger.warning(f"不支持的文件类型: {file_path}")
            return ""
        
        # 生成任务ID
        task_id = f"task_{self.task_counter}"
        self.task_counter += 1
        
        # 将文件路径转换为绝对路径
        absolute_file_path = os.path.abspath(file_path)

        # 创建任务对象（只传递必需的参数）
        task = Task(task_id, absolute_file_path)

        # 保存任务
        self.tasks[task_id] = task
        
        # 获取文件名用于日志和事件
        file_name = FileSystemUtils.get_file_name(file_path)
        
        # 发布任务添加事件
        event_data = TaskAddedEvent(
            task_id=task_id,
            file_path=absolute_file_path, # 使用绝对路径
            file_name=file_name
        )
        event_bus.publish(EventTypes.TASK_ADDED, event_data)
        
        logger.info(f"添加任务: {file_name}")
        return task_id
    
    def add_tasks(self, file_paths: List[str]) -> List[str]:
        """批量添加任务
        
        Args:
            file_paths: 文件路径列表
            
        Returns:
            List[str]: 成功添加的任务ID列表
        """
        # 使用辅助方法收集所有的有效文件
        valid_files = self._collect_valid_files(file_paths)
        
        # 直接添加所有有效文件
        added_task_ids = []
        for file_path in valid_files:
            task_id = self._add_task(file_path)
            if task_id:
                added_task_ids.append(task_id)
        
        return added_task_ids
    
    def _collect_valid_files(self, paths: List[str]) -> List[str]:
        """收集所有有效的文件路径
        
        Args:
            paths: 文件或文件夹路径列表
            
        Returns:
            List[str]: 有效的文件路径列表
        """
        valid_files = []
        
        # 获取支持的文件格式
        supported_extensions = self.audio_service.get_supported_formats()
        
        # 使用队列进行迭代，避免递归
        from collections import deque
        queue = deque(paths)
        
        while queue:
            path = queue.popleft()
            
            # 跳过不存在的路径
            if not os.path.exists(path):
                logger.debug(f"路径不存在，已忽略: {path}")
                continue
            
            # 如果是文件夹，获取其中的所有文件和子文件夹
            if os.path.isdir(path):
                logger.debug(f"检测到文件夹: {path}")
                try:
                    # 直接获取文件夹中支持的文件
                    folder_files = get_files_from_folder(path, supported_extensions)
                    valid_files.extend(folder_files)
                    logger.debug(f"从文件夹添加了 {len(folder_files)} 个文件: {path}")
                except Exception as e:
                    error_msg = f"处理文件夹失败: {str(e)}"
                    logger.error(error_msg)
                    if self.error_service:
                        self.error_service.handle_exception(
                            e,
                            ErrorCategory.FILE_IO,
                            ErrorPriority.MEDIUM,
                            "TaskService._collect_valid_files",
                            user_visible=False  # 这是内部错误，不需要显示给用户
                        )
            # 如果是文件，检查是否支持
            elif os.path.isfile(path):
                ext = file_utils.get_file_extension(path) # 使用file_utils中的方法获取不带点的扩展名
                if ext in supported_extensions:
                    valid_files.append(path)
                    logger.debug(f"添加有效文件: {path}")
                else:
                    logger.debug(f"不支持的文件格式，已忽略: {path}")
        
        return valid_files
    
    def start_task(self, task_id: str) -> bool:
        """开始处理任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        result = self._update_task_status(task_id, ProcessStatus.STARTED)
        
        if result:
            # 获取任务对象
            task = self.tasks.get(task_id)
            if task:
                 # 显式启动任务内部计时器
                 task._start_timer()
            else:
                 # 如果任务不存在（理论上不应发生，因为_update_task_status已成功）
                 logger.error(f"无法启动计时器：任务 {task_id} 不存在。")
                 return False # 或者根据需要处理错误

            # 设置为当前活跃任务
            self.active_task_id = task_id
            
            # 启动全局计时器 (用于更新UI)
            if not self.active_task_timer.isActive():
                self.active_task_timer.start()
                
        return result
    
    def mark_task_as_waiting(self, task_id: str) -> bool:
        """将任务标记为等待处理
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        return self._update_task_status(task_id, ProcessStatus.WAITING)
    
    def request_cancel_task(self, task_id: str) -> bool:
        """请求取消任务，将任务标记为取消中
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        return self._update_task_status(task_id, ProcessStatus.CANCELLING)
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务，将任务标记为已取消
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        # 如果是当前活跃任务，停止计时器
        if task_id == self.active_task_id:
            if self.active_task_timer.isActive():
                self.active_task_timer.stop()
            self.active_task_id = None
            
        return self._update_task_status(task_id, ProcessStatus.CANCELLED)
    
    def complete_task(self, task_id: str, output_path: str) -> bool:
        """完成任务
        
        Args:
            task_id: 任务ID
            output_path: 输出文件路径
            
        Returns:
            bool: 是否成功
        """
        # 如果是当前活跃任务，停止计时器
        if task_id == self.active_task_id:
            if self.active_task_timer.isActive():
                self.active_task_timer.stop()
            self.active_task_id = None
            
        return self._update_task_status(task_id, ProcessStatus.COMPLETED, output_path)
    
    def mark_task_as_failed(self, task_id: str, error_message: str = None) -> bool:
        """将任务标记为失败
        
        Args:
            task_id: 任务ID
            error_message: 错误信息
            
        Returns:
            bool: 是否成功
        """
        # 检查任务是否存在
        if task_id not in self.tasks:
            logger.warning(f"尝试将不存在的任务标记为失败: {task_id}")
            return False
        
        # 记录详细的错误信息
        task = self.tasks[task_id]
        file_name = os.path.basename(task.file_path)
        
        # 记录错误信息
        if error_message:
            task.error = error_message
            logger.error(f"任务失败: 文件='{file_name}', 任务ID={task_id}, 错误={error_message}")
        else:
            logger.error(f"任务失败: 文件='{file_name}', 任务ID={task_id}, 无具体错误信息")
        
        # 如果是当前活跃任务，停止计时器
        if task_id == self.active_task_id:
            if self.active_task_timer.isActive():
                self.active_task_timer.stop()
            self.active_task_id = None
            
        return self._update_task_status(task_id, ProcessStatus.FAILED)
    
    def prepare_task(self, task_id: str) -> bool:
        """将任务标记为准备处理状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        return self._update_task_status(task_id, ProcessStatus.PREPARING)
    
    def set_task_exporting(self, task_id: str) -> bool:
        """将任务标记为导出中状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        return self._update_task_status(task_id, ProcessStatus.EXPORTING)
    
    def set_task_progress(self, task_id: str, progress: float) -> bool:
        """设置任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度值 (0.0-1.0)
            
        Returns:
            bool: 是否成功
        """
        return self._update_task_progress(task_id, progress)
    
    def _update_task_progress(self, task_id: str, progress: float) -> bool:
        """更新任务进度
        
        Args:
            task_id: 任务ID
            progress: 进度值 (0.0-1.0)
            
        Returns:
            bool: 是否成功更新
        """
        if task_id not in self.tasks:
            return False
            
        task = self.tasks[task_id]
        
        # 只有在进度有变化时才更新
        if task.progress == progress:
            return True
            
        task.progress = progress
        
        return True
    
    def get_task_count(self) -> int:
        """获取任务数量
        
        Returns:
            int: 任务数量
        """
        return len(self.tasks)
    
    def start_task_timer(self, task_id: str) -> bool:
        """启动任务计时器
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        if task_id not in self.tasks:
            return False
            
        task = self.tasks[task_id]
        task._start_timer()
        
        return True
    
    def stop_task_timer(self, task_id: str) -> bool:
        """停止任务计时器
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否成功
        """
        if task_id not in self.tasks:
            return False
            
        task = self.tasks[task_id]
        task._stop_timer()
        
        return True
    
    def _update_active_task_timer(self):
        """更新当前活跃任务的计时器"""
        if self.active_task_id and self.active_task_id in self.tasks:
            task = self.tasks[self.active_task_id]
            if task.update_timer():  # 只有当时间变化时才发送事件
                event_data = TaskTimerUpdatedEvent(
                    task_id=self.active_task_id,
                    duration=task.duration
                )
                event_bus.publish(EventTypes.TASK_TIMER_UPDATED, event_data)
        else:
            # 如果没有活跃任务但计时器在运行，停止计时器
            if self.active_task_timer.isActive():
                self.active_task_timer.stop()
                self.active_task_id = None
    
    def get_task_duration(self, task_id: str) -> str:
        """获取任务时长
        
        Args:
            task_id: 任务ID
            
        Returns:
            str: 任务时长字符串，格式为"分:秒"
        """
        if task_id not in self.tasks:
            return "00:00"
            
        return self.tasks[task_id].duration
    
    def get_task_progress(self, task_id: str) -> float:
        """获取任务进度
        
        Args:
            task_id: 任务ID
            
        Returns:
            float: 进度值 (0.0-1.0)
        """
        if task_id not in self.tasks:
            return 0.0
        
        return self.tasks[task_id].progress
    
    def get_task_status(self, task_id: str) -> Optional[ProcessStatus]:
        """获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[ProcessStatus]: 任务状态枚举，如果任务不存在则返回None
        """
        if task_id not in self.tasks:
            return None
        
        return self.tasks[task_id].status
    
    def is_task_active(self, task_id: str) -> bool:
        """检查任务是否处于活动状态（正在处理）
        
        Args:
            task_id: 任务ID
            
        Returns:
            bool: 是否处于活动状态
        """
        if task_id not in self.tasks:
            return False
        return self.tasks[task_id].is_active()
    
    def get_task_ids(self) -> List[str]:
        """获取所有任务ID列表
        
        Returns:
            List[str]: 所有任务的ID列表
        """
        return list(self.tasks.keys())
    
    def get_task_file_path(self, task_id: str) -> Optional[str]:
        """获取任务文件路径
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[str]: 文件路径，如果任务不存在则返回None
        """
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id].file_path
    
    def get_task_file_name(self, task_id: str) -> Optional[str]:
        """获取任务文件名
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[str]: 文件名，如果任务不存在则返回None
        """
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id].file_name
    
    def get_task_output_path(self, task_id: str) -> Optional[str]:
        """获取任务输出路径
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[str]: 输出文件路径，如果任务不存在或未设置则返回None
        """
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id].output_path
    
    def get_task_status_display(self, task_id: str) -> str:
        """获取任务状态显示文本
        
        Args:
            task_id: 任务ID
            
        Returns:
            str: 状态显示文本，如果任务不存在则返回空字符串
        """
        if task_id not in self.tasks:
            return ""
        return ProcessStatus.get_display_text(self.tasks[task_id].status)
    
    def get_task_error(self, task_id: str) -> Optional[str]:
        """获取任务错误信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            Optional[str]: 错误信息，如果任务不存在或没有错误则返回None
        """
        if task_id not in self.tasks:
            return None
        return self.tasks[task_id].error
    
    def remove_task_state(self, task_id: str):
        """移除任务状态
        
        Args:
            task_id: 任务ID
        """
        if task_id in self.tasks:
            # 通过事件总线发布任务计时器更新事件
            event_data = TaskTimerUpdatedEvent(
                task_id=task_id,
                duration="00:00"
            )
            event_bus.publish(EventTypes.TASK_TIMER_UPDATED, event_data)
            
            # 移除任务
            self.remove_task(task_id)
    
    def _update_task_status(self, task_id: str, status: ProcessStatus, output_path: str = None) -> bool:
        """更新任务状态（私有方法）
        
        Args:
            task_id: 任务ID
            status: 新状态
            output_path: 输出路径，仅在完成状态下使用
            
        Returns:
            bool: 是否成功更新
        """
        # 检查任务是否存在
        if task_id not in self.tasks:
            logger.error(f"任务不存在: {task_id}")
            return False
        
        # 获取任务对象
        task = self.tasks[task_id]
        
        # 记录状态变化
        previous_status = task.status
        log_level = "info"
        if status == ProcessStatus.FAILED:
            log_level = "error"
            logger.error(f"任务状态变更: {task_id} - {previous_status.name} -> {status.name}, 错误: {task.error or '未知错误'}")
        else:
            logger.info(f"任务状态变更: {task_id} - {previous_status.name} -> {status.name}")
        
        # 更新状态
        task.status = status
        
        # 更新输出路径（如果提供）
        if output_path:
            task.output_path = output_path
        
        # 发布任务状态变更事件
        event_data = TaskStateChangedEvent(
            task_id=task_id,
            status=status,
            progress=task.progress,
            error=task.error or "",
            output_path=task.output_path or ""
        )
        event_bus.publish(EventTypes.TASK_STATE_CHANGED, event_data)
        
        return True
    
    def get_all_tasks(self) -> Dict[str, Task]:
        """获取所有任务
        
        Returns:
            Dict[str, Task]: 所有任务的字典，键为任务ID，值为任务对象
        """
        return self.tasks
    