#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
文件工具类 - 提供文件操作相关的工具函数
"""

import os
import platform
import sys # Added for PyInstaller _MEIPASS check
import subprocess
from typing import List, Set, Optional
from loguru import logger
from pathlib import Path

from core.models.config import SUPPORTED_AUDIO_FORMATS, SUPPORTED_VIDEO_FORMATS, SUPPORTED_EXPORT_FORMATS

def get_resource_path(relative_path: str) -> str:
    """获取资源的绝对路径，兼容开发环境和打包后的环境。"""
    try:
        # PyInstaller 创建的临时文件夹 _MEIPASS
        # 对于 --onedir 模式, sys._MEIPASS 是 dist/appname 目录
        # 对于 --onefile 模式, sys._MEIPASS 是解压的临时目录
        base_path = sys._MEIPASS
    except AttributeError:
        # 不在 PyInstaller 打包环境中（例如开发环境）
        # 此工具函数位于 core/utils/file_utils.py
        # 则项目根目录是其上两级
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    return os.path.join(base_path, relative_path)

def get_file_extension(file_path: str) -> str:
    """获取文件扩展名（不带点）
    
    Args:
        file_path: 文件路径
    
    Returns:
        str: 文件扩展名（小写，不带点）
    """
    return Path(file_path).suffix.lower().lstrip('.')


def is_supported_media_file(file_path: str) -> bool:
    """判断是否为支持的媒体文件（音频或视频）
    
    Args:
        file_path: 文件路径
    
    Returns:
        bool: 是否支持
    """
    return is_supported_audio_file(file_path) or is_supported_video_file(file_path)


def is_supported_video_file(file_path: str) -> bool:
    """判断是否为支持的视频文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        bool: 是否支持
    """
    return get_file_extension(file_path) in SUPPORTED_VIDEO_FORMATS


def is_supported_audio_file(file_path: str) -> bool:
    """判断是否为支持的音频文件
    
    Args:
        file_path: 文件路径
    
    Returns:
        bool: 是否支持
    """
    return get_file_extension(file_path) in SUPPORTED_AUDIO_FORMATS

def is_supported_export_file(file_path: str) -> bool:
    """检查文件是否是支持的导出格式
    
    Args:
        file_path: 文件路径

    Returns:
        bool: 是否是支持的导出格式
    """
    ext = get_file_extension(file_path)
    if ext.startswith("."):
        ext = ext[1:]
    return ext in SUPPORTED_EXPORT_FORMATS


def get_supported_media_extensions() -> List[str]:
    """获取支持的媒体文件扩展名列表
    
    Returns:
        List[str]: 支持的媒体文件扩展名列表
    """
    return SUPPORTED_AUDIO_FORMATS + SUPPORTED_VIDEO_FORMATS

def get_supported_audio_extensions() -> List[str]:
    """获取支持的音频文件扩展名列表
    
    Returns:
        List[str]: 支持的音频文件扩展名列表
    """
    return SUPPORTED_AUDIO_FORMATS

def get_supported_video_extensions() -> List[str]:
    """获取支持的视频文件扩展名列表
    
    Returns:
        List[str]: 支持的视频文件扩展名列表
    """ 
    return SUPPORTED_VIDEO_FORMATS

def get_supported_export_extensions() -> List[str]:
    """获取支持的导出文件扩展名列表
    
    Returns:
        List[str]: 支持的导出文件扩展名列表
    """
    return SUPPORTED_EXPORT_FORMATS

def get_files_from_folder(folder_path: str, extensions: List[str] = None) -> List[str]:
    """获取文件夹中的所有文件
    
    Args:
        folder_path: 文件夹路径
        extensions: 文件扩展名列表，如果为None则获取所有文件
        
    Returns:
        List[str]: 文件路径列表
    """
    files = []
    
    # 检查文件夹是否存在
    if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
        return files
    
    # 遍历文件夹
    for root, _, filenames in os.walk(folder_path):
        for filename in filenames:
            file_path = os.path.join(root, filename)
            
            # 如果指定了扩展名，则只获取指定扩展名的文件
            if extensions:
                file_ext = os.path.splitext(filename)[1].lower()
                if file_ext in extensions:
                    files.append(file_path)
            else:
                files.append(file_path)
    
    return files


def ensure_dir_exists(dir_path: str) -> bool:
    """确保目录存在，如果不存在则创建
    
    Args:
        dir_path: 目录路径
        
    Returns:
        bool: 是否成功（目录已存在或创建成功）
    """
    try:
        os.makedirs(dir_path, exist_ok=True)
        return True
    except Exception:
        return False


def get_unique_filename(file_path: str) -> str:
    """获取唯一的文件名，避免覆盖已有文件
    
    Args:
        file_path: 原始文件路径
        
    Returns:
        str: 唯一的文件路径
    """
    if not os.path.exists(file_path):
        return file_path
        
    directory, filename = os.path.split(file_path)
    name, ext = os.path.splitext(filename)
    
    counter = 1
    while True:
        new_filename = f"{name}_{counter}{ext}"
        new_filepath = os.path.join(directory, new_filename)
        
        if not os.path.exists(new_filepath):
            return new_filepath
            
        counter += 1


def get_file_size_mb(file_path: str) -> float:
    """获取文件大小（MB）
    
    Args:
        file_path: 文件路径
        
    Returns:
        float: 文件大小（MB）
    """
    if not os.path.exists(file_path) or not os.path.isfile(file_path):
        return 0.0
        
    size_bytes = os.path.getsize(file_path)
    return size_bytes / (1024 * 1024)


class FileSystemUtils:
    """文件系统工具类，提供文件和目录操作的静态方法"""
    
    @staticmethod
    def open_file(file_path: str) -> bool:
        """打开文件
        
        Args:
            file_path: 文件路径
            
        Returns:
            bool: 是否成功打开
        """
        try:
            if not os.path.exists(file_path) or not os.path.isfile(file_path):
                logger.error(f"文件不存在: {file_path}")
                return False
                
            if platform.system() == "Windows":
                os.startfile(file_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["open", file_path])
            else:  # Linux
                subprocess.call(["xdg-open", file_path])
                
            logger.info(f"打开文件: {file_path}")
            return True
        except Exception as e:
            logger.error(f"打开文件失败: {str(e)}")
            return False
    
    @staticmethod
    def open_directory(dir_path: str) -> bool:
        """打开目录
        
        Args:
            dir_path: 目录路径
            
        Returns:
            bool: 是否成功打开
        """
        try:
            if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
                logger.error(f"目录不存在: {dir_path}")
                return False
                
            if platform.system() == "Windows":
                os.startfile(dir_path)
            elif platform.system() == "Darwin":  # macOS
                subprocess.call(["open", dir_path])
            else:  # Linux
                subprocess.call(["xdg-open", dir_path])
                
            logger.info(f"打开目录: {dir_path}")
            return True
        except Exception as e:
            logger.error(f"打开目录失败: {str(e)}")
            return False
    
    @staticmethod
    def get_file_name(file_path: str) -> str:
        """获取文件名（带扩展名）
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件名
        """
        return os.path.basename(file_path)
    
    @staticmethod
    def get_file_dir(file_path: str) -> str:
        """获取文件所在目录
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件所在目录
        """
        return os.path.dirname(file_path)
    
    @staticmethod
    def get_file_extension(file_path: str) -> str:
        """获取文件扩展名
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 文件扩展名（带点，如.mp3）
        """
        return os.path.splitext(file_path)[1].lower()
    
    @staticmethod
    def get_file_name_without_extension(file_path: str) -> str:
        """获取不带扩展名的文件名
        
        Args:
            file_path: 文件路径
            
        Returns:
            str: 不带扩展名的文件名
        """
        return os.path.splitext(os.path.basename(file_path))[0]
        
    @staticmethod
    def create_file_dialog(parent, title="选择音频/视频文件", last_directory="", extensions=None):
        """创建文件选择对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            last_directory: 上次打开的目录
            extensions: 支持的文件扩展名列表，如果为None则使用所有支持的媒体格式
            
        Returns:
            tuple: (选择的文件列表, 选择的过滤器)
        """
        from PySide6.QtWidgets import QFileDialog
        
        # 如果没有指定扩展名，则使用所有支持的媒体格式
        if extensions is None:
            extensions = get_supported_media_extensions()
        
        # 构建支持的文件格式过滤器
        format_list = []
        for fmt in extensions:
            format_list.append(f"*{fmt}")
        
        filter_str = f"音频/视频文件 ({' '.join(format_list)});;所有文件 (*)"
        
        # 打开文件对话框
        return QFileDialog.getOpenFileNames(
            parent,
            title,
            last_directory,
            filter_str
        )
        
    @staticmethod
    def create_folder_dialog(parent, title="选择文件夹", last_directory=""):
        """创建文件夹选择对话框
        
        Args:
            parent: 父窗口
            title: 对话框标题
            last_directory: 上次打开的目录
            
        Returns:
            str: 选择的文件夹路径，如果用户取消则返回空字符串
        """
        from PySide6.QtWidgets import QFileDialog
        
        # 打开文件夹对话框
        return QFileDialog.getExistingDirectory(
            parent,
            title,
            last_directory
        )

def files_filter(paths: List[str]) -> List[str]:
    """过滤文件和目录，返回所有符合条件的文件列表
    
    Args:
        paths: 文件和目录路径列表
        
    Returns:
        List[str]: 符合条件的文件路径列表
    """
    logger.debug(f"files_filter被调用，路径数量: {len(paths)}")
    
    # 获取支持的扩展名
    supported_extensions = get_supported_media_extensions()
    
    # 结果文件列表
    valid_files = []
    
    # 定义辅助函数处理单个路径
    def process_path(path):
        # 检查路径是否存在
        if not os.path.exists(path):
            logger.debug(f"路径不存在: {path}")
            return []
            
        # 如果是文件，直接检查扩展名
        if os.path.isfile(path):
            ext = get_file_extension(path)
            if ext in supported_extensions:
                logger.debug(f"有效文件: {path}")
                return [path]
            else:
                logger.debug(f"不支持的文件: {path}")
                return []
        # 如果是目录，递归获取目录中所有符合条件的文件
        elif os.path.isdir(path):
            logger.debug(f"处理文件夹: {path}")
            folder_files = get_files_from_folder(path, supported_extensions)
            logger.debug(f"从文件夹 {path} 获取到 {len(folder_files)} 个有效文件")
            return folder_files
        else:
            logger.debug(f"不支持的路径类型: {path}")
            return []
    
    # 处理每个路径并将结果汇总
    for path in paths:
        if path:  # 跳过空路径
            valid_files.extend(process_path(path))
    
    # 返回所有符合条件的文件列表
    logger.debug(f"files_filter处理完成，共 {len(valid_files)} 个有效文件")
    return valid_files

def get_temp_file_path(directory: str, prefix: str = "temp", suffix: str = ".wav") -> str:
    """获取临时文件路径
    
    Args:
        directory: 目录路径
        prefix: 文件名前缀
        suffix: 文件名后缀
    
    Returns:
        str: 临时文件路径
    """
    import uuid
    import tempfile
    
    # 确保目录存在
    os.makedirs(directory, exist_ok=True)
    
    # 生成唯一文件名
    unique_id = str(uuid.uuid4())
    filename = f"{prefix}_{unique_id}{suffix}"
    
    # 返回完整路径
    return os.path.join(directory, filename)

def ensure_directory_exists(directory_path: str) -> bool:
    """确保目录存在，如果不存在则创建
    
    Args:
        directory_path: 目录路径
    
    Returns:
        bool: 操作是否成功
    """
    try:
        os.makedirs(directory_path, exist_ok=True)
        return True
    except Exception:
        return False
