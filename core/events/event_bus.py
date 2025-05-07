#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
事件总线 - 应用程序中央事件处理系统
提供事件发布-订阅模式，统一管理应用程序内的通信
"""

import time
from typing import Dict, List, Callable, Any, Optional, Type, TypeVar
from loguru import logger
from PySide6.QtCore import QObject, Signal, Slot

# 事件数据类型
T = TypeVar('T')

class EventBus(QObject):
    """应用程序事件总线，实现单例模式"""
    
    # 定义信号，传递事件名称和事件数据对象
    event_occurred = Signal(str, object)
    
    _instance = None
    
    def __new__(cls):
        """确保事件总线是单例"""
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        """初始化事件总线"""
        # 避免重复初始化
        if hasattr(self, '_initialized'):
            return
            
        super().__init__()
        # 存储事件订阅者
        self._subscribers: Dict[str, List[Callable]] = {}
        # 存储事件历史（调试用）
        self._event_history: List[Dict] = []
        # 历史记录大小限制
        self._max_history_size = 100
        # 调试模式
        self._debug = False
        
        # 连接信号到分发方法
        self.event_occurred.connect(self._dispatch_event)
        
        # 标记为已初始化
        self._initialized = True
        
        logger.info("事件总线初始化完成")
    
    def set_debug(self, debug: bool):
        """设置调试模式
        
        Args:
            debug: 是否启用调试模式
        """
        self._debug = debug
    
    def publish(self, event_name: str, event_data: Any = None):
        """发布事件
        
        Args:
            event_name: 事件名称，用于标识事件类型
            event_data: 事件数据，可以是任何类型
        """
        # 处理None值
        if event_data is None:
            event_data = {}
            
        # 记录事件历史
        if self._debug:
            self._record_event(event_name, event_data)
            
        # 发出事件信号
        self.event_occurred.emit(event_name, event_data)
        
        if self._debug:
            logger.debug(f"发布事件: {event_name}, 数据: {event_data}")
    
    def subscribe(self, event_name: str, handler: Callable) -> Callable:
        """订阅事件
        
        Args:
            event_name: 要订阅的事件名称
            handler: 事件处理函数，接受事件数据作为参数
            
        Returns:
            handler: 返回处理函数，便于后续取消订阅
        """
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
            
        if handler not in self._subscribers[event_name]:
            self._subscribers[event_name].append(handler)
            
        if self._debug:
            logger.debug(f"订阅事件: {event_name}")
            
        return handler
    
    def unsubscribe(self, event_name: str, handler: Callable) -> bool:
        """取消事件订阅
        
        Args:
            event_name: 事件名称
            handler: 之前订阅的处理函数
            
        Returns:
            bool: 是否成功取消订阅
        """
        if event_name in self._subscribers and handler in self._subscribers[event_name]:
            self._subscribers[event_name].remove(handler)
            
            if self._debug:
                logger.debug(f"取消订阅事件: {event_name}")
                
            return True
        return False
    
    def get_event_history(self) -> List[Dict]:
        """获取事件历史记录
        
        Returns:
            List[Dict]: 事件历史记录列表
        """
        return self._event_history.copy()
    
    def clear_event_history(self):
        """清除事件历史记录"""
        self._event_history.clear()
    
    @Slot(str, object)
    def _dispatch_event(self, event_name: str, event_data: Any):
        """分发事件到订阅者
        
        Args:
            event_name: 事件名称
            event_data: 事件数据
        """
        if event_name in self._subscribers:
            for handler in self._subscribers[event_name]:
                try:
                    handler(event_data)
                except Exception as e:
                    logger.error(f"事件处理错误: {event_name}, 错误: {str(e)}")
                    if self._debug:
                        # 在调试模式下打印更详细的错误信息
                        import traceback
                        logger.error(f"详细错误: {traceback.format_exc()}")
    
    def _record_event(self, event_name: str, event_data: Any):
        """记录事件到历史记录
        
        Args:
            event_name: 事件名称
            event_data: 事件数据
        """
        event_record = {
            "timestamp": time.time(),
            "name": event_name,
            "data": event_data
        }
        
        self._event_history.append(event_record)
        
        # 限制历史记录大小
        if len(self._event_history) > self._max_history_size:
            self._event_history.pop(0) 