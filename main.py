#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Faster-Vox 应用程序入口
"""

import sys
import os
import time

from PySide6.QtWidgets import QApplication

from core.utils.logging_utils import setup_logger, logger
from core.containers import AppContainer
from core.models.config import APP_NAME, APP_ORGANIZATION
from ui.main_window import MainWindow
from core.events import event_bus

def setup_environment():
    """设置应用环境"""
    try:
        # 尝试使用硬件加速
        os.environ["QT_OPENGL"] = "desktop"
        # 可以在这里添加一些测试代码验证OpenGL是否正常工作
    except Exception:
        # 如果出错，回退到软件渲染
        os.environ["QT_OPENGL"] = "software"
        logger.warning("硬件OpenGL初始化失败，切换到软件渲染模式")
    
def main():
    """应用程序主入口"""

    # 初始化容器
    container = AppContainer()

    # 配置日志系统
    setup_logger(console_level="DEBUG", file_level="DEBUG")
    
    # 记录启动时间
    start_time = time.time()
    
    # 设置应用环境
    setup_environment()
    
    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    
    # 配置事件总线，在开发环境中启用调试模式
    event_bus.set_debug(os.environ.get('DEBUG_EVENT_BUS', '').lower() == 'true')
    logger.info("事件总线已初始化")
    
    # 初始化核心服务 - 按依赖顺序初始化
    logger.info("开始初始化核心服务...")
    
    # 1. 首先初始化环境服务 - 其他服务依赖它提供的环境信息
    logger.info("初始化环境服务")
    environment_service = container.environment_service()
    
    # 检查环境状态
    logger.info("开始检测系统环境...")
    environment_service.refresh()
    
    # 2. 初始化错误处理服务
    logger.info("初始化错误处理服务")
    container.error_handling_service()
    
    # 3. 初始化任务服务
    logger.info("初始化任务服务")
    container.task_service()
    
    
    # 5. 初始化模型服务 - 依赖环境服务
    logger.info("初始化模型服务")
    model_service = container.model_service()
    model_service.initialize()
    
    # 6. 初始化转录服务 - 依赖环境服务、模型服务和Whisper管理器
    logger.info("初始化转录服务")
    container.transcription_service()
    
    # 创建并显示主窗口
    logger.info("创建主窗口")
    w = MainWindow()
    
    # 显示主窗口
    w.show()
    
    # 记录启动完成时间
    end_time = time.time()
    logger.info(f"应用程序启动耗时: {end_time - start_time:.2f} 秒")
    
    # 运行应用程序
    sys.exit(app.exec())


if __name__ == "__main__":
    # 运行应用程序
    main() 