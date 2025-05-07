"""
进度信息处理工具函数
用于解析包含进度信息的文本并发布相应事件
"""

import re
import sys
from typing import Optional, Tuple, Callable, Any


def parse_progress(text: str) -> Tuple[Optional[int], Optional[str]]:
    """
    从文本中解析进度信息
    
    Args:
        text: 包含进度信息的文本
    
    Returns:
        tuple: (percentage, filename) 如果解析成功，否则返回 (None, None)
    """
    if '%|' not in text:
        return None, None
    
    try:
        # 提取百分比
        match = re.search(r'(\d+)%', text)
        if not match:
            return None, None
        
        percentage = int(match.group(1))
        
        # 提取文件名
        file_match = re.search(r'\[(.*?)\]:', text)
        filename = file_match.group(1) if file_match else None
        
        return percentage, filename
    except Exception:
        return None, None


# Function calculate_transcription_progress removed as it's no longer used.

def create_progress_writer(progress_callback: Callable[[int, Optional[str]], Any], 
                         original_stdout: Any = None) -> 'ProgressWriter':
    """
    创建一个进度写入器
    
    Args:
        progress_callback: 进度回调函数，接收(percentage, filename)作为参数
        original_stdout: 原始的stdout对象，默认为sys.stdout
    
    Returns:
        ProgressWriter: 进度写入器对象
    """
    return ProgressWriter(progress_callback, original_stdout or sys.stdout)


class ProgressWriter:
    """进度写入器，用于捕获并处理进度信息"""
    
    def __init__(self, progress_callback: Callable[[int, Optional[str]], Any], 
                original_stdout: Any):
        """
        初始化进度写入器
        
        Args:
            progress_callback: 进度回调函数，接收(percentage, filename)作为参数
            original_stdout: 原始的stdout对象
        """
        self._original_stdout = original_stdout
        self._progress_callback = progress_callback
    
    def write(self, text: str) -> None:
        """
        写入并处理文本
        
        Args:
            text: 要写入的文本
        """
        percentage, filename = parse_progress(text)
        if percentage is not None:
            self._progress_callback(percentage, filename)
        
        # 写入原始stdout
        if self._original_stdout:
            self._original_stdout.write(text)
            self._original_stdout.flush()
    
    def flush(self) -> None:
        """刷新输出流"""
        if self._original_stdout:
            self._original_stdout.flush() 