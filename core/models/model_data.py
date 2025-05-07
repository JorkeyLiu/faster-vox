#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模型数据模型 - 表示一个AI模型的所有相关数据
"""

from typing import Optional, List
from enum import Enum


class ModelSize(Enum):
    """模型大小枚举"""
    
    TINY = "tiny"
    BASE = "base"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE_V3 = "large-v3"
    
    @staticmethod
    def get_all() -> List[str]:
        """获取所有模型名称
        
        Returns:
            List[str]: 所有模型名称
        """
        return [size.value for size in ModelSize]
    
    @staticmethod
    def get_display_name(name: str) -> str:
        """获取模型的显示名称
        
        Args:
            name: 模型名称
            
        Returns:
            str: 显示名称
        """
        name = name.lower()
        if name == ModelSize.TINY.value:
            return "Tiny"
        elif name == ModelSize.BASE.value:
            return "Base"
        elif name == ModelSize.SMALL.value:
            return "Small"
        elif name == ModelSize.MEDIUM.value:
            return "Medium"
        elif name == ModelSize.LARGE_V3.value:
            return "Large-V3"
        else:
            return name
    
    @staticmethod
    def get_from_value(value: str) -> 'ModelSize':
        """根据字符串值获取枚举成员
        
        Args:
            value: 字符串值
            
        Returns:
            ModelSize: 枚举成员
            
        Raises:
            ValueError: 如果值无效
        """
        value = value.lower()
        for size in ModelSize:
            if size.value == value:
                return size
        raise ValueError(f"无效的模型名称: {value}")
        
    @staticmethod
    def is_valid(value: str) -> bool:
        """检查值是否有效
        
        Args:
            value: 要检查的值
            
        Returns:
            bool: 是否有效
        """
        value = value.lower()
        return value in [size.value for size in ModelSize]


class ModelData:
    """
    模型数据类 - 表示一个AI模型的所有相关数据
    包含模型的元数据、存在状态、下载状态等
    """
    
    def __init__(self, name: str):
        """初始化模型数据
        
        Args:
            name: 模型名称
        """
        self.name = name.lower()              # 模型名称
        self.display_name = name              # 显示名称
        self.is_exists = False                # 模型是否存在
        self.is_downloading = False           # 是否正在下载
        self.download_progress = 0            # 下载进度 (0-100)
        self.is_loaded = False                # 是否已加载
        self.is_loading = False               # 是否正在加载
        self.model_path = ""                  # 模型路径
        self.model_id = ""                    # 模型ID
        self.error = None                     # 错误信息
        
    @property
    def status_text(self) -> str:
        """获取状态文本
        
        Returns:
            str: 状态文本
        """
        if self.is_loading:
            return "正在加载..."
        elif self.is_loaded:
            return "已加载"
        elif self.is_downloading:
            return f"下载中 {self.download_progress}%"
        elif self.is_exists:
            return "已下载"
        else:
            return "未下载"
    
    def set_exists(self, exists: bool, model_path: str = ""):
        """设置模型是否存在
        
        Args:
            exists: 是否存在
            model_path: 模型路径
        """
        self.is_exists = exists
        if model_path:
            self.model_path = model_path
        
    def set_downloading(self, downloading: bool):
        """设置模型是否正在下载
        
        Args:
            downloading: 是否正在下载
        """
        self.is_downloading = downloading
        # 如果不是下载中，则重置进度
        if not downloading:
            self.download_progress = 0
        
    def set_download_progress(self, progress: float):
        """设置下载进度
        
        Args:
            progress: 进度 (0-100)
        """
        self.download_progress = progress
        
    def set_loaded(self, loaded: bool):
        """设置模型是否已加载
        
        Args:
            loaded: 是否已加载
        """
        self.is_loaded = loaded
        # 如果已加载，则不再是加载中状态
        if loaded:
            self.is_loading = False
        
    def set_loading(self, loading: bool):
        """设置模型是否正在加载
        
        Args:
            loading: 是否正在加载
        """
        self.is_loading = loading
        # 如果不是加载中，则可能需要重置加载状态
        if not loading:
            self.is_loaded = False 