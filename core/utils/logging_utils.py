#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
日志工具 - 提供日志记录功能和统一日志格式
"""

import os
import sys
from pathlib import Path
from typing import Optional, Union, Dict, Any

from loguru import logger

# 从配置中获取日志目录
try:
    from core.models.config import APP_LOGS_DIR
except ImportError:
    # 如果配置模块不可用，使用默认路径
    APP_LOGS_DIR = Path.home() / "AppData" / "Local" / "Faster-Vox" / "logs"


def setup_logger(
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    log_dir: Optional[Union[str, Path]] = None,
    log_filename: str = "app.log",
    rotation: str = "1 day",
    retention: str = "7 days",
    compression: str = "zip"
) -> None:
    """配置日志系统
    
    Args:
        console_level: 控制台日志级别
        file_level: 文件日志级别
        log_dir: 日志目录，如果为None则使用默认目录
        log_filename: 日志文件名
        rotation: 日志轮转策略，如"1 day"、"10 MB"等
        retention: 日志保留策略，如"7 days"、"10 files"等
        compression: 日志压缩格式，如"zip"、"gz"等
    """
    # 移除默认的处理器
    logger.remove()
    
    # 获取日志目录
    if log_dir is None:
        log_dir = APP_LOGS_DIR
    else:
        log_dir = Path(log_dir)
    
    # 确保日志目录存在
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 日志文件路径
    log_file = log_dir / log_filename
    
    # 添加控制台处理器
    logger.add(
        sys.stderr,
        level=console_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # 添加文件处理器
    logger.add(
        log_file,
        level=file_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{line} - {message}",
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8"
    )
    
    logger.info("日志系统初始化完成")


def get_logger(name: str = None) -> logger:
    """获取日志记录器
    
    Args:
        name: 日志记录器名称，通常为模块名
        
    Returns:
        logger: 日志记录器实例
    """
    return logger.bind(name=name)


def log_exception(e: Exception, context: Optional[Dict[str, Any]] = None) -> None:
    """记录异常信息
    
    Args:
        e: 异常对象
        context: 上下文信息，可选
    """
    if context:
        logger.exception(f"异常: {str(e)}, 上下文: {context}")
    else:
        logger.exception(f"异常: {str(e)}")


def log_function_call(func_name: str, args: tuple = None, kwargs: dict = None) -> None:
    """记录函数调用信息
    
    Args:
        func_name: 函数名称
        args: 位置参数
        kwargs: 关键字参数
    """
    args_str = str(args) if args else "()"
    kwargs_str = str(kwargs) if kwargs else "{}"
    logger.debug(f"调用函数: {func_name}, 参数: {args_str}, 关键字参数: {kwargs_str}")


def log_performance(operation: str, elapsed_time: float) -> None:
    """记录性能信息
    
    Args:
        operation: 操作名称
        elapsed_time: 耗时（秒）
    """
    logger.debug(f"性能: {operation} 耗时 {elapsed_time:.4f} 秒")


# 默认导出的日志记录器
default_logger = logger

# 为了方便导入，直接导出 logger
__all__ = ['setup_logger', 'get_logger', 'log_exception', 'log_function_call', 'log_performance', 'logger', 'default_logger']
