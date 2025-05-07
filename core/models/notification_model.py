#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
通知相关枚举定义
"""

from enum import Enum

class NotificationContent(Enum):
    """通知内容模板枚举"""

    # 模型加载
    MODEL_LOADING = "正在加载 {model_name} 模型，请稍候..."
    MODEL_LOADED = "模型 {model_name} 已成功加载"
    MODEL_LOADING_FAILED = "模型 {model_name} 加载失败，请检查模型文件或重新下载"

    # 模型下载
    MODEL_DOWNLOADING = "正在下载 {model_name} 模型，请稍候..."
    MODEL_DOWNLOADED = "模型 {model_name} 已成功下载"
    MODEL_DOWNLOADING_FAILED = "模型 {model_name} 下载失败，请检查网络连接或重新下载"
    MODEL_DOWNLOAD_STARTED = "模型 {model_name} 开始下载，请耐心等待下载完成"
    MODEL_DOWNLOAD_COMPLETED = "模型 {model_name} 已下载完成"
    MODEL_DOWNLOAD_NOT_FOUND = "未找到模型 {model_name} 的下载信息"

    # 系统错误
    SYSTEM_ERROR = "内部错误"
    
    # 文件操作
    FILE_ADD_FAILED = "添加文件失败: {error_message}"
    FILE_OPEN_FAILED = "打开文件失败: {file_path}"
    FILE_NOT_EXIST = "输出文件不存在"
    DIRECTORY_OPEN_FAILED = "打开目录失败: {directory_path}"
    
    # 设置相关
    SETTINGS_SAVED = "{setting_name}已更新"
    SETTINGS_RESET = "已将所有设置恢复为默认值"
    OUTPUT_DIR_RESET = "已恢复为默认输出目录设置"
    
    # 任务处理
    TASK_STARTED = "开始处理文件: {file_name}"
    TASK_COMPLETED = "任务完成: {file_name} -> {output_name}"
    TASK_CANCELLED = "用户取消了所有处理任务"
    ALL_TASKS_COMPLETED = "所有任务处理完成"
    
    # 环境管理
    ENV_SETUP_STARTED = "开始设置独立Python环境..."
    ENV_SETUP_COMPLETED = "独立Python环境设置完成"
    ENV_SETUP_FAILED = "独立Python环境设置失败: {error_message}"
    ENV_ALREADY_SETUP = "独立Python环境已经设置完成"
    ENV_NOT_READY = "独立Python环境未准备好，请先设置环境"


class NotificationTitle(Enum):
    """通知标题枚举"""

    # 空标题
    NONE_TITLE = "" 