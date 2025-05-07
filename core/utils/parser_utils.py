import re
from typing import Optional, Dict, Any

class TranscriptParser:
    """
    Whisper输出行解析工具
    解析格式: [hh:mm:ss.xxx --> hh:mm:ss.xxx] 文本 或 [mm:ss.xxx --> mm:ss.xxx] 文本
    """

    TIMESTAMP_PATTERN = re.compile(
        r"\[\s*(.*?)\s*-->\s*(.*?)\s*\]\s*(.*)" # 宽松匹配，允许空格
    )

    @staticmethod
    def time_str_to_seconds(time_str: str) -> float:
        """将时间字符串 (hh:mm:ss.xxx 或 mm:ss.xxx) 转换为秒"""
        time_str = time_str.strip() # 去除首尾空格

        parts = time_str.split(':')
        hours = 0
        minutes = 0
        seconds_part = ""

        if len(parts) == 3: # hh:mm:ss.xxx
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds_part = parts[2]
        elif len(parts) == 2: # mm:ss.xxx
            minutes = int(parts[0])
            seconds_part = parts[1]
        else:
            raise ValueError(f"无法解析的时间格式: {time_str}")

        # 解析秒和毫秒
        sec_millisec = seconds_part.split('.')
        if len(sec_millisec) != 2:
             raise ValueError(f"无法解析秒和毫秒部分: {seconds_part}")
        sec = int(sec_millisec[0])
        # Ensure millisec is padded to 3 digits if necessary, although whisper usually outputs 3 digits.
        millisec_str = sec_millisec[1]
        if len(millisec_str) > 3:
             millisec_str = millisec_str[:3] # Truncate if longer
        elif len(millisec_str) < 3:
             millisec_str = millisec_str.ljust(3, '0') # Pad if shorter
        millisec = int(millisec_str)


        total_seconds = (
            hours * 3600 + minutes * 60 + sec + millisec / 1000.0
        )
        return total_seconds

    @classmethod
    def parse_line(cls, line: str) -> Optional[Dict[str, Any]]:
        """
        解析一行Whisper输出
        返回 {'start': float, 'end': float, 'text': str} 或 None
        """
        match = cls.TIMESTAMP_PATTERN.search(line) # 使用search匹配任意位置
        if not match:
            return None

        start_str, end_str, text = match.groups()

        try:
            # 清洗捕获的字符串，去除可能的方括号和空格
            start_str_cleaned = start_str.strip().lstrip('[').rstrip(']')
            end_str_cleaned = end_str.strip().lstrip('[').rstrip(']')

            start_sec = cls.time_str_to_seconds(start_str_cleaned)
            end_sec = cls.time_str_to_seconds(end_str_cleaned)
        except ValueError as e: # 捕获特定异常并记录
            # 可以添加日志记录错误信息
            # from loguru import logger
            # logger.error(f"解析时间字符串失败: {e}, start='{start_str}', end='{end_str}'")
            return None
        except Exception as e: # 捕获其他可能的异常
             # from loguru import logger
             # logger.error(f"解析时间戳时发生未知错误: {e}")
             return None

        return {"start": start_sec, "end": end_sec, "text": text.strip()}


class ProgressCalculator:
    """
    根据end_time和音频总时长计算进度百分比
    """

    @staticmethod
    def calculate(end_time: float, audio_duration: float) -> float:
        if not audio_duration or audio_duration <= 0:
            return 0.0
        progress = end_time / audio_duration
        return min(max(progress, 0.0), 1.0)