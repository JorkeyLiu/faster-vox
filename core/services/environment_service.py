#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
环境服务 - 提供系统环境检测和状态查询功能
统一管理GPU硬件检测和预编译应用可用性检测
"""

import os
import platform
import subprocess
import time
from loguru import logger
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PySide6.QtCore import QObject

from core.models.config import WHISPER_EXE_PATH
from core.events import event_bus, EventTypes
from core.services.config_service import ConfigService
from core.events.event_types import EnvironmentStatusEvent
from core.models.environment_model import EnvironmentInfo


class EnvironmentService(QObject):
    """环境服务 - 提供系统环境检测和状态查询功能
    
    此服务负责检测系统环境状态，包括操作系统、GPU硬件、预编译应用可用性等，
    并将这些信息集中管理在一个EnvironmentInfo对象中。其他服务可以通过
    get_environment_info()方法获取环境信息，并通过事件总线接收环境变更通知。
    """

    def __init__(self, config_service: ConfigService):
        """初始化环境服务
        
        Args:
            config_service: 配置服务，用于获取应用目录等配置
        """
        super().__init__()
        
        # 保存依赖
        self.config_service = config_service
        
        # 创建环境信息对象
        self.environment_info = EnvironmentInfo(
            is_windows=platform.system() == "Windows"
        )
        
        # 初始环境检测
        self._detect_environment()
        
        # 记录环境状态
        logger.info(f"EnvironmentService初始化完成: Windows={self.environment_info.is_windows}, GPU={self.environment_info.has_gpu}")
        logger.info(f"预编译应用可用: {self.environment_info.whisper_app_available}, Python依赖可用: {self.environment_info.python_deps_available}")
    
    def _detect_environment(self):
        """检测环境，包括 GPU 硬件和预编译应用可用性"""
        # 检测GPU硬件
        self._detect_gpu()
        
        # 检查预编译应用可用性
        self.environment_info.whisper_app_available = self.check_whisper_app_available()
        
        # 发布环境状态事件
        self._publish_environment_status_changed()
    
    def _detect_gpu(self):
        """检测系统是否有GPU硬件"""
        # 仅在Windows平台上进行检测
        if not self.environment_info.is_windows:
            self.environment_info.has_gpu = False
            return
        
        try:
            # 使用NVML检测GPU
            self.environment_info.has_gpu = self._detect_gpu_hardware()
            if self.environment_info.has_gpu:
                logger.info("检测到GPU硬件")
            else:
                logger.info("未检测到GPU硬件")
            
        except Exception as e:
            logger.error(f"GPU检测过程中发生错误: {str(e)}")
            self.environment_info.has_gpu = False

    def _detect_gpu_hardware(self) -> bool:
        """使用NVML检测GPU硬件
        
        Returns:
            bool: 是否检测到GPU硬件
        """
        try:
            # 导入py3nvml库
            import py3nvml.nvidia_smi as smi
            try:
                # 初始化NVML库
                smi.nvmlInit()
                
                try:
                    # 获取GPU数量
                    result = smi.nvmlDeviceGetCount()
                    
                    if result > 0:
                        try:
                            # 获取第一个GPU的名称用于记录
                            gpu_info = smi.nvmlDeviceGetHandleByIndex(0)
                            self.environment_info.gpu_name = smi.nvmlDeviceGetName(gpu_info)
                            logger.info(f"检测到NVIDIA GPU: {self.environment_info.gpu_name}")
                            return True
                        except Exception as device_err:
                            logger.error(f"获取GPU设备信息失败: {str(device_err)}")
                            # 虽然获取详情失败，但我们知道有GPU，所以返回True
                            return True
                    else:
                        logger.info("未检测到NVIDIA GPU设备")
                        return False
                finally:
                    # 确保在所有操作完成后关闭NVML
                    smi.nvmlShutdown()
            except Exception as nvml_err:
                logger.error(f"NVML操作失败: {str(nvml_err)}")
                return False
        except ImportError as imp_err:
            logger.error(f"导入py3nvml模块失败: {str(imp_err)}")
            return False
        except Exception as e:
            logger.error(f"GPU检测过程中发生未预期错误: {str(e)}")
            return False

    def check_whisper_app_available(self) -> bool:
        """检查预编译的 Whisper 应用是否可用
        
        Returns:
            bool: 应用是否可用
        """
        # 检查应用主文件是否存在
        whisper_exe = WHISPER_EXE_PATH # 新代码
        if not whisper_exe.exists() or not whisper_exe.is_file():
            logger.debug(f"文件未找到: {whisper_exe}")
            return False
        
        return True
    
    def _publish_environment_status_changed(self):
        """发布环境状态变更事件"""
        try:
            # 创建环境状态事件
            event = EnvironmentStatusEvent(
                environment_info=self.environment_info
            )
            
            # 发布环境状态事件
            event_bus.publish(EventTypes.ENVIRONMENT_STATUS_CHANGED, event)
            
        except Exception as e:
            logger.error(f"发布环境状态事件失败: {str(e)}")
    
    def refresh(self, force: bool = False) -> Tuple[bool, Dict[str, Any]]:
        """刷新环境状态，重新检测环境并发布状态事件
        
        此方法会重新检测环境状态，并在状态发生变化时发布环境状态事件。
        同时返回是否有关键状态发生变化，以及变化的详情。
        
        Args:
            force: 是否强制刷新，忽略缓存时间
        """
        
        # 保存旧状态用于比较
        old_info = EnvironmentInfo(
            is_windows=self.environment_info.is_windows,
            has_gpu=self.environment_info.has_gpu,
            whisper_app_available=self.environment_info.whisper_app_available,
            python_deps_available=self.environment_info.python_deps_available
        )
        
        # 重新检测环境
        self._detect_environment()
        
        # 检查关键变化
        has_changes = False
        changes = {}
        
        # 检查GPU硬件变化
        if old_info.has_gpu != self.environment_info.has_gpu:
            has_changes = True
            changes["gpu_hardware"] = {
                "old": old_info.has_gpu,
                "new": self.environment_info.has_gpu
            }
            if self.environment_info.has_gpu:
                logger.info("检测到GPU硬件，可以使用GPU加速")
            else:
                logger.warning("未检测到GPU硬件，使用CPU模式")
        
        # 检查预编译应用可用性变化
        if old_info.whisper_app_available != self.environment_info.whisper_app_available:
            has_changes = True
            changes["precompiled_availability"] = {
                "old": old_info.whisper_app_available,
                "new": self.environment_info.whisper_app_available
            }
            if self.environment_info.whisper_app_available:
                logger.info("预编译应用现在可用，已启用GPU加速")
            else:
                logger.warning("预编译应用不再可用，回退到Python库")
        
        # 检查Python依赖变化
        if old_info.python_deps_available != self.environment_info.python_deps_available:
            has_changes = True
            changes["python_deps"] = {
                "old": old_info.python_deps_available,
                "new": self.environment_info.python_deps_available
            }
            if self.environment_info.python_deps_available:
                logger.info("Python依赖现在可用")
            else:
                logger.warning("Python依赖不再可用")
        
        # 如果有变化，记录日志
        if has_changes:
            logger.info(f"环境状态已更新: {changes}")
        
        return has_changes, changes
    
    def get_environment_info(self) -> EnvironmentInfo:
        """获取环境信息对象
        
        此方法返回当前环境信息对象的引用，可以通过这个对象
        查询环境状态和使用环境相关功能。
        
        Returns:
            EnvironmentInfo: 环境信息对象
        """
        return self.environment_info 