#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
环境数据模型 - 提供统一的环境状态和信息表示
集中管理系统环境状态，为其他服务提供环境相关信息
"""

from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class EnvironmentInfo:
    """环境信息数据模型，集中管理系统环境状态
    
    此类作为环境信息的权威来源，集中管理所有与环境相关的状态和决策逻辑。
    所有依赖环境状态的服务都应该使用此类的实例来查询环境信息，
    而不是直接调用环境服务的方法。
    
    Attributes:
        is_windows: 当前系统是否为Windows平台
        has_gpu: 是否检测到GPU硬件
        whisper_app_available: 预编译的whisper应用是否可用
        python_deps_available: 必要的Python依赖是否已安装
    """

    
    # 平台信息
    is_windows: bool = False
    
    # GPU信息
    has_gpu: bool = False
    gpu_name: str = ""
    
    # 应用状态
    whisper_app_available: bool = False
    python_deps_available: bool = False
    
    def can_use_gpu_acceleration(self) -> bool:
        """检查是否可以使用GPU加速
        
        当满足以下所有条件时，可以使用GPU加速：
        1. 当前系统是Windows
        2. 有GPU
        3. 预编译应用可用
        
        Returns:
            bool: 是否可以使用GPU加速
        """
        return self.is_windows and self.has_gpu and self.whisper_app_available
    
    def should_download_cuda_env(self) -> bool:
        """检查是否应该下载CUDA环境
        
        当满足以下所有条件时，应该下载CUDA环境：
        1. 当前系统是Windows
        2. 有GPU 
        3. 预编译应用不可用
        
        Returns:
            bool: 是否应该下载CUDA环境
        """
        return self.is_windows and self.has_gpu and not self.whisper_app_available
    
    def to_dict(self) -> Dict[str, Any]:
        """将环境信息转换为字典
        
        Returns:
            Dict[str, Any]: 环境信息字典
        """
        return {
            "is_windows": self.is_windows,
            "has_gpu": self.has_gpu,
            "whisper_app_available": self.whisper_app_available,
            "python_deps_available": self.python_deps_available
        }
    
    def __eq__(self, other) -> bool:
        """比较两个环境信息对象是否相同
        
        Args:
            other: 另一个环境信息对象
            
        Returns:
            bool: 两个对象是否相同
        """
        if not isinstance(other, EnvironmentInfo):
            return False
        
        return (
            self.is_windows == other.is_windows and
            self.has_gpu == other.has_gpu and
            self.whisper_app_available == other.whisper_app_available and
            self.python_deps_available == other.python_deps_available
        ) 