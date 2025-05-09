#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
任务数据模型 - 表示一个需要处理的任务，包含任务属性和状态管理
此文件定义了Task模型类，作为系统中任务的数据表示层
"""

import time
from enum import Enum, auto
from core.utils.file_utils import FileSystemUtils


class ProcessStatus(Enum):
    """处理状态枚举"""
    WAITING = auto()     # 等待处理
    PREPARING = auto()   # 准备中
    STARTED = auto()     # 已开始
    IN_PROGRESS = auto() # 处理中
    EXPORTING = auto()   # 导出中
    COMPLETED = auto()   # 已完成
    FAILED = auto()      # 失败
    CANCELLED = auto()   # 已取消
    CANCELLING = auto()  # 取消中
    
    @classmethod
    def get_display_text(cls, status):
        """获取状态的显示键 (用于国际化)
        
        Args:
            status: ProcessStatus枚举值
            
        Returns:
            str: 状态键 (小写枚举名称)
        """
        if not isinstance(status, cls):
            # 对于无效状态，可以返回一个默认键或引发错误
            # 这里返回 'waiting' 作为默认值
            return cls.WAITING.name.lower()
            
        # 直接返回枚举成员名称的小写形式作为键
        return status.name.lower()


class Task:
    """任务数据模型，表示一个需要处理的任务"""
    
    # 活动状态列表
    ACTIVE_STATUSES = [
        ProcessStatus.STARTED, 
        ProcessStatus.IN_PROGRESS,
        ProcessStatus.PREPARING,
        ProcessStatus.EXPORTING,
        ProcessStatus.CANCELLING
    ]
    
    def __init__(self, task_id: str, file_path: str):
        """初始化一个任务
        
        Args:
            task_id: 任务ID
            file_path: 文件路径
        """
        # 基本信息
        self.id = task_id
        self.file_path = file_path
        self.file_name = FileSystemUtils.get_file_name(file_path)
        
        # 状态相关
        self.status = ProcessStatus.WAITING
        self.progress = 0.0
        self.output_path = None
        self.error = None
        
        # 计时相关
        self.start_time = None  # 开始时间
        self.duration = "--:--"  # 持续时间显示
    
    def set_status(self, status: ProcessStatus) -> None:
        """设置任务状态
        
        Args:
            status: 新状态
        """
        self.status = status
        
        # 处理计时相关逻辑
        if status == ProcessStatus.STARTED:
            self._start_timer()
        elif status in [ProcessStatus.COMPLETED, ProcessStatus.FAILED, 
                        ProcessStatus.CANCELLED, ProcessStatus.WAITING]:
            self._stop_timer()
    
    def set_output_path(self, output_path: str) -> None:
        """设置输出路径
        
        Args:
            output_path: 输出文件路径
        """
        self.output_path = output_path
    
    def set_progress(self, progress: float) -> None:
        """设置任务进度
        
        Args:
            progress: 进度值 (0.0-1.0)
        """
        self.progress = min(max(0.0, progress), 1.0)
    
    def set_error(self, error_message: str) -> None:
        """设置错误信息
        
        Args:
            error_message: 错误描述
        """
        self.error = error_message
    
    def is_active(self) -> bool:
        """检查任务是否处于活动状态
        
        Returns:
            是否活动
        """
        return self.status in self.ACTIVE_STATUSES
    
    def update_timer(self) -> bool:
        """更新计时器，返回是否有变化
        
        Returns:
            布尔值，表示持续时间是否有变化
        """
        if self.start_time is None:
            return False
            
        prev_duration = self.duration
        
        elapsed_seconds = int(time.time() - self.start_time)
        minutes = elapsed_seconds // 60
        seconds = elapsed_seconds % 60
        self.duration = f"{minutes:02d}:{seconds:02d}"
        
        return prev_duration != self.duration
    
    def _start_timer(self) -> None:
        """启动计时器"""
        self.start_time = time.time()
        self.duration = "--:--"
    
    def _stop_timer(self) -> None:
        """停止计时器"""
        if self.start_time is not None:
            self.update_timer()  # 更新最终时长
            self.start_time = None 