#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
模型管理服务 - 负责模型的下载、加载、验证和管理
整合了原ModelService和WhisperModelService的功能
"""

import os
import re
import sys
import platform
import time
import subprocess
import threading
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from PySide6.QtCore import QObject, Slot, QThread
from loguru import logger

from core.models.model_data import ModelSize, ModelData
from core.models.error_model import ErrorInfo, ErrorCategory, ErrorPriority
from core.services.config_service import ConfigService
from core.services.notification_service import NotificationService
from core.events import event_bus, EventTypes
from core.events.event_types import (
    ModelDownloadErrorEvent, ModelEvent, WorkerCompletedEvent, WorkerProgressEvent, 
    EnvironmentStatusEvent, CudaEnvDownloadStartedEvent, CudaEnvDownloadProgressEvent, 
    CudaEnvDownloadCompletedEvent, CudaEnvInstallStartedEvent, CudaEnvInstallProgressEvent,
    CudaEnvInstallCompletedEvent, CudaEnvDownloadErrorEvent
)
from utils.progress_utils import create_progress_writer
from core.models.config import APP_ENV_DIR, WHISPER_EXE_PATH
from modelscope.hub.snapshot_download import snapshot_download

class ModelScopeDownloader(QThread):
    """ModelScope模型下载器"""
    
    def __init__(self, model_id: str, model_name: str, save_path: str):
        """初始化下载器
        
        Args:
            model_id: ModelScope模型ID
            model_name: 模型名称
            save_path: 保存路径
        """
        super().__init__()
        self.model_id = model_id
        self.model_name = model_name
        self.save_path = save_path
        self._original_stdout = None
        self._original_stderr = None
        self._is_canceled = False
    
    def _publish_model_download_progress(self, progress: int, status_message: str):
        """发布下载进度事件"""
        progress_event = ModelEvent(
            event_type=EventTypes.MODEL_DOWNLOAD_PROGRESS,
            model_name=self.model_name,
            progress=progress,
            status_message=status_message
        )
        event_bus.publish(EventTypes.MODEL_DOWNLOAD_PROGRESS, progress_event)

    def _publish_model_download_completed(self, success: bool, error: Optional[str] = None):
        """发布下载完成事件"""
        completed_event = ModelEvent(
            event_type=EventTypes.MODEL_DOWNLOAD_COMPLETED,
            model_name=self.model_name,
            success=success,
            error=error
        )
        event_bus.publish(EventTypes.MODEL_DOWNLOAD_COMPLETED, completed_event)
    
    def run(self):
        """运行下载线程"""
        try:
            # 发布下载进度事件（开始）
            self._publish_model_download_progress(0, "开始下载...")
            
            # 保存原始stdout
            self._original_stdout = sys.stdout
            self._original_stderr = sys.stderr
            
            # 创建进度回调函数
            def handle_progress(percentage, filename):
                if filename:
                    # 发布下载进度事件
                    self._publish_model_download_progress(percentage, f"正在下载 {filename}: {percentage}%")
            
            # 重定向输出
            sys.stdout = create_progress_writer(handle_progress, self._original_stdout)
            sys.stderr = create_progress_writer(handle_progress, self._original_stderr)
            
            try:
                # 下载模型
                snapshot_download(
                    self.model_id,
                    local_dir=self.save_path
                )
            finally:
                # 恢复原始输出
                sys.stdout = self._original_stdout
                sys.stderr = self._original_stderr
            
            # 检查是否被取消
            if self._is_canceled:
                # 发布下载完成事件（失败）
                self._publish_model_download_completed(False, "下载已取消")
                return
            
            # 发布下载进度事件（完成）
            self._publish_model_download_progress(100, "下载完成")
            
            # 发布下载完成事件（成功）
            self._publish_model_download_completed(True)
            
        except Exception as e:
            # 恢复原始输出
            if self._original_stdout:
                sys.stdout = self._original_stdout
            if self._original_stderr:
                sys.stderr = self._original_stderr
                
            # 记录错误
            logger.error(f"下载模型 {self.model_name} 失败: {str(e)}")
            
            # 发布下载完成事件（失败）
            self._publish_model_download_completed(False, str(e))
    
    def cancel(self):
        """取消下载"""
        self._is_canceled = True

class CudaEnvDownloader(QThread):
    """CUDA环境下载器线程"""
    
    def __init__(self, model_id: str, app_name: str, save_path: str, file_pattern: str = None):
        """初始化下载器
        
        Args:
            model_id: ModelScope模型ID
            app_name: 应用名称
            save_path: 保存路径
            file_pattern: 文件匹配模式，只下载匹配此模式的文件
        """
        super().__init__()
        self.model_id = model_id
        self.app_name = app_name
        self.save_path = save_path
        self.file_pattern = file_pattern
        self._is_canceled = False
        self._original_stdout = None
        self._original_stderr = None

    def _publish_cuda_env_download_started(self):
        """发布下载开始事件"""
        progress_event = CudaEnvDownloadStartedEvent(
            app_name=self.app_name
        )
        event_bus.publish(EventTypes.CUDA_ENV_DOWNLOAD_STARTED,progress_event)

    def _publish_cuda_env_download_progress(self, progress: int, message: str):
        """发布下载进度事件"""
        progress_event = CudaEnvDownloadProgressEvent(
            app_name=self.app_name,
            progress=progress, 
            message=message
        )
        event_bus.publish(EventTypes.CUDA_ENV_DOWNLOAD_PROGRESS, progress_event)

    def _publish_cuda_env_download_completed(self, success: bool, error: Optional[str] = None):
        """发布下载完成事件"""
        completed_event = CudaEnvDownloadCompletedEvent(
            app_name=self.app_name,
            success=success,
            error=error or "" # Ensure error is not None
        )
        event_bus.publish(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, completed_event)
    
    def run(self):
        """运行下载线程"""
        try:
            # 保存原始stdout/stderr
            self._original_stdout = sys.stdout
            self._original_stderr = sys.stderr
            
            # 创建进度回调函数
            def handle_progress(percentage, filename):
                if filename:
                    # 发布下载进度事件
                    self._publish_cuda_env_download_progress(percentage, f"正在下载 {filename}: {percentage}%")
            
            # 重定向输出
            sys.stdout = create_progress_writer(handle_progress, self._original_stdout)
            sys.stderr = create_progress_writer(handle_progress, self._original_stderr)
            
            try:
                # 发布下载开始事件
                self._publish_cuda_env_download_started()

                # 下载预编译应用
                if self.file_pattern:
                    snapshot_download(
                        self.model_id,
                        local_dir=self.save_path,
                        allow_patterns=[self.file_pattern]
                    )
                else:
                    snapshot_download(
                        self.model_id,
                        local_dir=self.save_path
                    )
            finally:
                # 恢复原始输出
                sys.stdout = self._original_stdout
                sys.stderr = self._original_stderr
            
            # 检查是否被取消
            if self._is_canceled:
                # 发布下载完成事件（失败）
                self._publish_cuda_env_download_completed(False, "下载已取消")
                return
            
            # 发布下载完成事件（成功）
            self._publish_cuda_env_download_completed(True)
            
        except Exception as e:
            # 恢复原始输出
            if self._original_stdout:
                sys.stdout = self._original_stdout
            if self._original_stderr:
                sys.stderr = self._original_stderr
                
            # 记录错误
            logger.error(f"下载CUDA环境 {self.app_name} 失败: {str(e)}")
            
            # 发布下载完成事件（失败）
            self._publish_cuda_env_download_completed(False, str(e))
    
    def cancel(self):
        """取消下载"""
        self._is_canceled = True

class CudaEnvInstaller(QThread):
    """CUDA环境安装器线程"""
    
    def __init__(self, temp_download_dir: Path, extract_target_dir: Path, app_name: str):
        """初始化安装器
        
        Args:
            temp_download_dir: 包含下载文件的临时目录
            extract_target_dir: 解压的目标根目录
            app_name: 应用名称
        """
        super().__init__()
        self.temp_download_dir = temp_download_dir
        self.extract_target_dir = extract_target_dir
        self.app_name = app_name
        self._is_canceled = False
        self._progress_re = re.compile(r'(\d+)%')
    
    def run(self):
        """运行安装线程"""
        try:
            # 发布安装开始事件
            from core.events.event_types import CudaEnvInstallStartedEvent
            start_event = CudaEnvInstallStartedEvent(
                app_name=self.app_name
            )
            event_bus.publish(EventTypes.CUDA_ENV_INSTALL_STARTED, start_event)
            
            # 解压文件
            self._extract_files()
            
            # 检查是否取消
            if self._is_canceled:
                logger.warning("解压过程被取消，安装中止")
                return
            
            # 验证安装
            validation_result, error_msg = self._validate_installation()
            if not validation_result:
                self._publish_install_completed(False, f"安装验证失败: {error_msg}")
                return
            
            # 发布安装完成事件（成功）
            self._publish_install_completed(True, "")
            
        except Exception as e:
            # 记录错误
            logger.error(f"安装CUDA环境 {self.app_name} 失败: {str(e)}")
            logger.exception(e)  # 记录详细的异常堆栈
            
            # 发布安装完成事件（失败）
            try:
                self._publish_install_completed(False, str(e))
            except Exception as notify_ex:
                # 确保即使通知失败也不会导致更多问题
                logger.error(f"发送安装失败通知时发生错误: {str(notify_ex)}")
    
    def _reader_thread(self, process: subprocess.Popen):
        """读取并解析7z输出流的线程函数"""
        last_reported_progress = -1
        try:
            # 使用 iter(process.stdout.readline, '') 因为 Popen 现在是文本模式
            for line in iter(process.stdout.readline, ''):
                if self._is_canceled:
                    logger.info("读取线程检测到取消请求，停止读取。")
                    break
                try:
                    # 直接使用 line，因为 Popen(text=True) 已经自动解码
                    decoded_line = line.strip()
                    if not decoded_line:
                        continue

                    # 尝试用正则提取进度
                    match = self._progress_re.search(decoded_line)
                    if match:
                        progress = int(match.group(1))
                        if progress > last_reported_progress:
                             self._publish_install_progress(progress, f"正在解压: {progress}%")
                             last_reported_progress = progress
                    else:
                         pass

                except Exception as e:
                    logger.warning(f"解析 7z 输出时出错: {e}")
                    # 继续尝试读取下一行

            logger.info("7z 输出读取线程结束。")

        except Exception as e:
            logger.error(f"7z 输出读取线程异常: {e}")

    def _extract_files(self):
        """使用捆绑的7-Zip解压文件，并实时报告进度"""
        try:
            # --- 确定应用程序基础路径 (根据打包方式可能需要调整) ---
            if getattr(sys, 'frozen', False):
                 # 如果在 PyInstaller 包中运行
                 app_base_path = Path(sys.executable).parent
            else:
                 # 如果作为普通脚本运行
                 # 假设此文件位于 core/services/ 目录下，需要向上两级到项目根目录
                 app_base_path = Path(__file__).resolve().parent.parent.parent

            # --- 构建捆绑 7-Zip 的完整路径 (指向命令行版本) ---
            bundled_7z_path = app_base_path / "resources" / "7-Zip-Zstandard64" / "7z.exe"

            # --- 检查捆绑的 7z 是否存在 ---
            if not bundled_7z_path.is_file():
                # 更新错误消息中的文件名和路径
                error_msg = f"捆绑的 7-Zip 命令行可执行文件未找到: {bundled_7z_path}。请确保 'resources/7-Zip-Zstandard64/' 目录下包含 '7z.exe'。"
                logger.error(error_msg)
                raise FileNotFoundError(error_msg)

            seven_zip_exe = str(bundled_7z_path)
            logger.info(f"找到捆绑的 7-Zip: {seven_zip_exe}")

            # --- 定位需要解压的文件 ---
            file_pattern = ModelManagementService.FILE_PATTERN
            downloaded_files = list(self.temp_download_dir.glob(file_pattern))

            if not downloaded_files:
                raise FileNotFoundError(f"在临时目录 {self.temp_download_dir} 未找到匹配 {file_pattern} 的待解压文件")

            # 选择最新的文件进行解压
            archive_file = max(downloaded_files, key=lambda f: f.stat().st_mtime)
            target_dir = str(self.extract_target_dir)

            self._publish_install_progress(0, f"准备从 {self.temp_download_dir} 使用捆绑的 7-Zip 解压 {archive_file.name} 到 {target_dir}")

            if self._is_canceled:
                logger.info("解压开始前检测到取消请求")
                return

            # --- 执行解压 (使用 Popen) ---
            # -bsp1: 将进度输出到stdout (需要验证7z版本是否支持以及格式)
            # -y:    假设所有查询都为 Yes (例如覆盖文件)
            cmd = [seven_zip_exe, 'x', str(archive_file), f'-o{target_dir}', '-bsp1', '-y']
            logger.info(f"执行 7-Zip 命令: {' '.join(cmd)}")

            process = None # Initialize process variable
            reader = None # Initialize reader thread variable

            try:
                # 确保目标目录存在
                os.makedirs(target_dir, exist_ok=True)

                # 执行解压命令，捕获 stdout 和 stderr
                process_flags = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
                process = subprocess.Popen(cmd,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT, # 合并stderr到stdout
                                           # 添加 text=True, encoding, errors 以启用文本模式和自动解码
                                           text=True,
                                           encoding='utf-8', # 使用utf-8并忽略错误，增加兼容性
                                           errors='ignore',
                                           creationflags=process_flags)

                # 启动读取输出的线程
                reader = threading.Thread(target=self._reader_thread, args=(process,))
                reader.daemon = True # 设置为守护线程，主线程退出时它也会退出
                reader.start()

                # --- 等待解压完成或取消 ---
                while process.poll() is None:
                    if self._is_canceled:
                        logger.info("主线程检测到取消请求，尝试终止 7z 进程。")
                        try:
                            process.terminate() # 尝试优雅地终止
                            # 短暂等待后强制终止（如果需要）
                            try:
                                process.wait(timeout=1)
                            except subprocess.TimeoutExpired:
                                logger.warning("7z 进程未能优雅终止，强制终止。")
                                process.kill()
                        except Exception as term_err:
                             logger.error(f"终止 7z 进程时出错: {term_err}")
                        break # 退出等待循环
                    # 短暂休眠避免CPU空转
                    time.sleep(0.1)

                # 确保读取线程结束 (即使进程被终止也尝试join)
                if reader and reader.is_alive():
                     logger.info("等待读取线程结束...")
                     reader.join(timeout=2) # 等待最多2秒
                     if reader.is_alive():
                          logger.warning("读取线程未能按时结束。")

                # 检查是否因为取消而退出
                if self._is_canceled:
                     logger.info("解压过程已被取消。")
                     # 清理可能残留的未完全解压的文件是困难且有风险的，暂时跳过
                     return # 直接返回，run()方法会处理后续

                # --- 检查最终结果 ---
                return_code = process.returncode
                if return_code == 0:
                    logger.info(f"捆绑的 7-Zip 解压成功: {archive_file.name}")
                    self._publish_install_progress(100, "解压完成") # 报告解压阶段完成
                    # --- 添加清理逻辑 ---
                    try:
                        logger.info(f"尝试删除临时压缩文件: {archive_file}")
                        archive_file.unlink(missing_ok=True)
                    except OSError as e:
                        logger.warning(f"删除临时压缩文件失败: {e}")
                    # --- 清理逻辑结束 ---
                else:
                    error_message = f"捆绑的 7-Zip 解压失败 (返回码: {return_code})。请检查日志获取详细信息。"
                    logger.error(error_message)
                    # 输出可能已在reader线程中记录
                    raise Exception(error_message)

            except FileNotFoundError:
                 logger.error(f"无法执行捆绑的 7-Zip 命令。请检查文件 '{seven_zip_exe}' 是否有效且具有执行权限。")
                 raise
            except Exception as e:
                 logger.error(f"执行捆绑的 7-Zip 解压时发生意外错误: {e}")
                 logger.exception(e)
                 # 如果进程仍在运行，尝试终止
                 if process and process.poll() is None:
                       try:
                            logger.warning("解压发生异常，尝试终止 7z 进程...")
                            process.kill()
                       except:
                            pass # Ignore errors during cleanup
                 raise
            finally:
                 # 确保读取线程已处理完毕
                 if reader and reader.is_alive():
                      logger.warning("解压 _extract_files 方法结束时，读取线程仍在活动状态。")

        except FileNotFoundError as e: # Catch specific FileNotFoundError for missing archive or 7z
             logger.error(f"文件查找失败: {e}")
             raise
        except Exception as e:
            # Catch all other exceptions during the process
            logger.error(f"解压CUDA环境文件时发生未预料的错误: {str(e)}")
            logger.exception(e) # Log stack trace
            raise # Re-throw to be handled by the run method
    
    def _validate_installation(self) -> Tuple[bool, str]:
        """验证安装
        
        Returns:
            Tuple[bool, str]: (是否验证成功, 错误消息)
        """
        whisper_exe = WHISPER_EXE_PATH

        if not whisper_exe.exists():
            return False, f"未找到Whisper APP文件: {whisper_exe}"
        
        return True, ""
    
    def _publish_install_progress(self, progress: int, message: str):
        """发布安装进度事件
        
        Args:
            progress: 进度百分比
            message: 进度消息
        """
        from core.events.event_types import CudaEnvInstallProgressEvent
        progress_event = CudaEnvInstallProgressEvent(
            app_name=self.app_name,
            progress=progress,
            message=message
        )
        event_bus.publish(EventTypes.CUDA_ENV_INSTALL_PROGRESS, progress_event)
        
        # 记录关键进度点，避免日志过多
        if progress % 10 == 0 or "完成" in message:
            logger.info(f"解压进度: {progress}% - {message}")
    
    def _publish_install_completed(self, success: bool, error: str):
        """发布安装完成事件
        
        Args:
            success: 是否成功
            error: 错误消息
        """
        from core.events.event_types import CudaEnvInstallCompletedEvent
        completed_event = CudaEnvInstallCompletedEvent(
            app_name=self.app_name,
            success=success,
            error=error
        )
        event_bus.publish(EventTypes.CUDA_ENV_INSTALL_COMPLETED, completed_event)
    
    def cancel(self):
        """取消安装"""
        logger.info(f"用户请求取消CUDA环境安装: {self.app_name}")
        self._is_canceled = True
        
        # 发布取消状态通知
        self._publish_install_progress(0, "正在取消安装...")
        
        # 发布最终的取消完成事件
        self._publish_install_completed(False, "安装已被用户取消")

class ModelManagementService(QObject):
    """模型管理服务，整合模型的下载、加载和验证功能"""
    
    # ModelScope模型ID映射
    MODEL_IDS = {
        ModelSize.TINY.value: "gpustack/faster-whisper-tiny",
        ModelSize.BASE.value: "gpustack/faster-whisper-base",
        ModelSize.SMALL.value: "gpustack/faster-whisper-small",
        ModelSize.MEDIUM.value: "gpustack/faster-whisper-medium",
        ModelSize.LARGE_V3.value: "gpustack/faster-whisper-large-v3"
    }
    
    # 预编译应用ModelScope模型ID
    WHISPER_APP_MODEL_ID = "bkfengg/whisper-cpp"
    FILE_PATTERN = "Faster-Whisper-XXL_r245.2_windows.7z"
    
    def __init__(self, config_service: ConfigService, 
                 environment_service,
                 notification_service: Optional[NotificationService] = None,
                 error_service = None):  # 错误处理服务
        """初始化模型管理服务
        
        Args:
            config_service: 配置服务
            environment_service: 环境服务
            notification_service: 通知服务
            error_service: 错误处理服务
        """
        super().__init__()
        
        # 保存依赖服务
        self.config_service = config_service
        self.notification_service = notification_service
        self.error_service = error_service
        self.environment_service = environment_service
        
        # 获取环境信息
        self.environment_info = self.environment_service.get_environment_info()
        
        # 模型文件目录
        self.models_dir = Path(self.config_service.get_model_directory())
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # 预编译应用目录
        self.base_dir = APP_ENV_DIR
        
        # 确保目录存在
        self.base_dir.mkdir(exist_ok=True, parents=True)
        
        # 模型数据字典 {模型名称: ModelData对象}
        self.model_data_dict = {}
        
        # 初始化模型数据
        self._init_model_data()
        
        # 活跃的下载器 {模型名称: 下载器}
        self.active_downloaders = {}
        
        # 当前选择的模型名称
        self.model_name = None
        
        # 当前加载的模型名称
        self.current_model_name = None
        
        # 配置选项
        self.auto_download_enabled = False  # 是否自动下载模型
        
        # 初始化通知服务
        if self.notification_service:
            self.notification_service.initialize()

        # 记录当前环境状态
        logger.info("ModelManagementService已初始化")
        logger.info(f"环境状态：Windows={self.environment_info.is_windows}, GPU={self.environment_info.has_gpu}")
        logger.info(f"预编译应用可用: {self.environment_info.whisper_app_available}")
        
        # 订阅环境状态变更事件
        event_bus.subscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._handle_environment_status_changed)
    
    def _init_model_data(self):
        """初始化模型数据"""
        # 这里不再自己检测环境
        
        # 添加内置模型数据
        for size_name, model_id in self.MODEL_IDS.items():
            # 构建默认路径
            model_path = os.path.join(str(self.models_dir), size_name)
            
            # 检查是否存在
            is_exists = self._check_model_path(model_path)
            
            # 创建ModelData对象
            model_data = ModelData(size_name)
            model_data.model_id = model_id
            model_data.set_exists(is_exists, model_path if is_exists else None)
            
            # 添加到字典
            self.model_data_dict[size_name] = model_data
        
        # 记录日志
        logger.info(f"模型数据初始化完成: {len(self.model_data_dict)} 个模型")
    
    def initialize(self):
        """初始化模型服务，包括扫描模型"""
        # 扫描模型
        self.scan_models()
        
        # 订阅事件 - 处理模型下载完成后触发CUDA环境下载
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self._on_model_download_completed)
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_ERROR, self._on_model_download_error)
        event_bus.subscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._on_cuda_env_download_completed)
        # 订阅模型下载请求事件
        event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_REQUESTED, self._on_model_download_requested)
    
    def _on_model_download_completed(self, event_data: ModelEvent): # 添加类型提示
        """模型下载完成事件处理 (仅处理成功情况)

        Args:
            event_data: 事件数据 (ModelEvent)
        """
        model_name = event_data.model_name
        if model_name in self.active_downloaders:
            del self.active_downloaders[model_name]

        # --- 处理成功逻辑 ---
        model_data = self.get_model_data(model_name)
        if model_data:
            model_data.is_downloading = False
            model_data.is_exists = True
            model_data.error = None
            logger.info(f"模型 {model_name} 下载成功，更新状态并发布事件。")
            self._publish_model_data_changed_event(model_name, model_data)

        # 重新扫描模型目录
        logger.info(f"模型 {model_name} 下载完成，（可选）重新扫描模型目录。")
        self.scan_models()

    def _on_model_download_error(self, model_name: str, error: str):
        """处理模型下载失败的逻辑"""
        model_data = self.get_model_data(model_name)
        if model_name in self.active_downloaders:
            del self.active_downloaders[model_name]
            
        if model_data:
            model_data.is_downloading = False
            # 下载失败时重新检查路径确定是否存在
            model_data.is_exists = self._check_model_path(model_data.path)
            model_data.error = error
            logger.warning(f"模型 {model_name} 下载失败: {error}。更新状态并发布事件。")
            # 失败时也发布事件，让UI知道下载结束但失败了
            self._publish_model_data_changed_event(model_name, model_data)
        else:
             logger.error(f"尝试处理模型 {model_name} 下载失败时未找到对应的 ModelData。")
    
    def _on_model_download_requested(self, event_data):
        """模型下载请求事件处理
        
        Args:
            event_data: 事件数据，包含model_name
        """
        model_name = event_data.model_name
        logger.info(f"接收到模型下载请求事件: {model_name}")
        
        # 调用下载模型方法
        self.download_model(model_name)
    
    
    def _on_cuda_env_download_completed(self, event_data):
        """CUDA环境下载完成事件处理
        
        Args:
            event_data: 事件数据
        """
        # 从活跃下载器中移除
        if "cuda_env" in self.active_downloaders:
            del self.active_downloaders["cuda_env"]

        # 检查下载是否成功
        if not event_data.success:
            logger.error(f"CUDA环境下载失败: {event_data.error}")
            # 发布错误事件，让其他部分知道下载失败
            self._publish_cuda_download_error_event(event_data.error)
            return

        # 下载成功，开始安装CUDA环境
        logger.info("CUDA环境下载完成，开始安装")

        # 定义临时目录和目标目录
        temp_dir = self.base_dir / "temp" # self.base_dir 就是 APP_ENV_DIR
        extract_target_dir = self.base_dir # 解压到 APP_ENV_DIR

        # 检查临时目录和压缩文件是否存在
        if not temp_dir.exists():
            logger.error(f"安装失败：临时下载目录 {temp_dir} 不存在")
            self._publish_install_completed(False, f"临时下载目录不存在: {temp_dir}")
            return

        # 查找下载好的压缩文件
        file_pattern = self.FILE_PATTERN
        downloaded_files = list(temp_dir.glob(file_pattern))
        if not downloaded_files:
            logger.error(f"安装失败：在临时目录 {temp_dir} 未找到匹配 {file_pattern} 的压缩文件")
            self._publish_install_completed(False, f"未在临时目录找到压缩文件: {file_pattern}")
            return

        # 创建并启动CUDA环境安装器
        installer = CudaEnvInstaller(temp_dir, extract_target_dir, "faster-whisper-app")

        # 存储安装器以便可以取消
        self.active_downloaders["cuda_env_installer"] = installer
        
        # 订阅安装完成事件
        def _on_install_completed(install_event):
            # 移除事件订阅
            event_bus.unsubscribe(EventTypes.CUDA_ENV_INSTALL_COMPLETED, _on_install_completed)
            
            # 从活跃安装器中移除
            if "cuda_env_installer" in self.active_downloaders:
                del self.active_downloaders["cuda_env_installer"]
            
            if install_event.success:
                # 安装成功
                logger.info("CUDA环境安装成功")
                
                # 更新环境状态 - 使用environment_service刷新环境信息
                has_changes, _ = self.environment_service.refresh()
                if has_changes:
                    logger.info("环境状态已更新")
                    # 强制更新本地环境信息，确保与刷新后一致
                    self.environment_info = self.environment_service.get_environment_info()
                    logger.info(f"已同步更新环境信息：预编译应用可用 = {self.environment_info.whisper_app_available}")
                else:
                    # 如果环境服务没有检测到变化，也手动更新一下本地状态以防万一
                    self.environment_info.whisper_app_available = self.environment_service.check_whisper_app_available()
                    logger.info(f"已手动更新环境信息：预编译应用可用 = {self.environment_info.whisper_app_available}")
            else:
                # 安装失败
                logger.error(f"CUDA环境安装失败: {install_event.error}")
        
        # 订阅安装完成事件
        event_bus.subscribe(EventTypes.CUDA_ENV_INSTALL_COMPLETED, _on_install_completed)
        
        # 启动安装
        installer.start()
    
    def get_model_data(self, model_name: str) -> Optional[ModelData]:
        """获取模型数据对象
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[ModelData]: 模型数据对象，如果不存在则返回None
        """
        return self.model_data_dict.get(model_name)
    
    def scan_models(self):
        """扫描可用模型
        
        Args:
            force: 是否强制扫描，即使模型状态字典不为空
        
        Returns:
            Dict[str, ModelData]: 模型名称到模型数据的映射
        """

        # 重置所有模型存在状态
        for model_name, model_data in self.model_data_dict.items():
            model_data.set_exists(None)
            model_data.model_path = None
        
        # 确保模型目录存在
        self.models_dir.mkdir(parents=True, exist_ok=True)
        
        # 记录日志
        logger.info(f"扫描模型目录: {self.models_dir}")
        
        # 扫描子目录
        for item in self.models_dir.iterdir():
            if item.is_dir():
                # 检查目录名是否匹配模型格式
                model_match = re.match(r'faster-whisper-(.+)', item.name)
                if model_match:
                    model_name = model_match.group(1)
                    # 检查是否有model.bin文件
                    model_bin_path = item / "model.bin"
                    exists = model_bin_path.exists() and model_bin_path.is_file() and model_bin_path.stat().st_size > 0
                    
                    # 更新模型数据
                    model_data = self.model_data_dict.get(model_name)
                    if model_data: 
                        model_data_changed = False
                        if model_data.is_exists is not None: # 已经初始化完成，用于更新模型数据
                            if exists and not model_data.is_exists:
                                # logger.info(f"找到模型: {model_name}, 文件大小: {model_bin_path.stat().st_size} 字节")
                                model_data.set_exists(True)
                                model_data.model_path = str(item)
                                model_data_changed = True
                            elif not exists and model_data.is_exists:
                                # logger.info(f"模型目录存在但缺少有效的model.bin文件: {model_name}")
                                model_data.set_exists(False)
                                model_data.model_path = None
                                model_data_changed = True
                        else: # 未初始化，用于初始化模型数据
                            if exists:
                                # logger.info(f"找到模型: {model_name}, 文件大小: {model_bin_path.stat().st_size} 字节")
                                model_data.set_exists(True)
                                model_data.model_path = str(item)
                            else:
                                model_data.set_exists(False)
                                model_data.model_path = None
                        
                        if model_data_changed:
                            # 发布数据变更事件
                            self._publish_model_data_changed_event(model_name, model_data)
        
        # 记录扫描结果，使用简洁易读的格式
        logger.info("模型扫描结果:")
        for model_name, model_data in self.model_data_dict.items():
            status = "已下载" if model_data.is_exists else "未下载"
            path = str(model_data.model_path) if model_data.model_path else "无"
            logger.info(f"  - {model_data.display_name}: {status}, 路径: {path}")
        
    @Slot(str)
    def download_model(self, model_name: str) -> bool:
        """下载模型
        
        Args:
            model_name: 模型名称
        
        Returns:
            bool: 是否成功启动下载
        """
        try:
            # 获取模型数据
            model_data = self.get_model_data(model_name)
            if not model_data:
                error_msg = f"未找到模型数据: {model_name}"
                logger.error(error_msg)
                
                # 使用错误处理服务
                self._handle_model_error(
                    error_msg, 
                    ErrorPriority.HIGH, 
                    "MODEL_DATA_NOT_FOUND", 
                    model_name, 
                    "download_model"
                )
                
                # 发布模型下载错误事件
                self._publish_model_download_error_event(model_name, error_msg)
                return False
            
            # 检查是否已经在下载
            if model_data.is_downloading or model_name in self.active_downloaders:
                logger.warning(f"模型 {model_name} 已经在下载中")
                return False
            
            # 获取模型ID
            model_id = model_data.model_id
            if not model_id:
                error_msg = f"模型 {model_name} 无有效的下载ID"
                logger.error(error_msg)
                
                # 使用错误处理服务
                self._handle_model_error(
                    error_msg, 
                    ErrorPriority.HIGH, 
                    "MODEL_ID_INVALID", 
                    model_name, 
                    "download_model"
                )
                
                # 发布模型下载错误事件
                self._publish_model_download_error_event(model_name, error_msg)
                return False
            
            # 设置下载状态
            model_data.set_downloading(True)
            
            # 发布数据变更事件
            self._publish_model_data_changed_event(model_name, model_data)
            
            # 构建保存路径
            save_path = self.models_dir / f"faster-whisper-{model_name}"
            
            # 检查环境 - 使用环境信息对象
            is_windows_with_cuda = self.environment_info.is_windows and self.environment_info.has_gpu
            cuda_env_needed = is_windows_with_cuda and not self.environment_info.whisper_app_available
            
            # 记录环境状态，用于日志
            if is_windows_with_cuda:
                if cuda_env_needed:
                    logger.info(f"Windows+CUDA环境，CUDA环境未安装，稍后将提示下载: {model_name}")
                    # 记录日志 # 新增提示
                    logger.info("若下载模型后未自动开始下载CUDA环境，请尝试重启应用或手动检查环境设置")
                else:
                    logger.info(f"Windows+CUDA环境，CUDA环境已安装: {model_name}")
            else:
                logger.info(f"非Windows+CUDA环境，使用标准下载流程: {model_name}")
            
            # 记录日志
            logger.info(f"开始下载模型 {model_name}，保存到 {save_path}")
            
            # 发布下载开始事件 - 使用辅助方法
            self._publish_model_download_started_event(model_name)
            
            # 创建下载线程并启动
            downloader = ModelScopeDownloader(model_id, model_name, str(save_path))
            
            # 保存活跃下载器
            self.active_downloaders[model_name] = downloader
            
            # 启动下载线程
            downloader.start()
            
            return True
            
        except Exception as e:
            # 下载失败
            error_msg = f"模型 {model_name} 下载启动失败: {str(e)}"
            logger.error(error_msg)
            
            # 重置下载状态
            if 'model_data' in locals() and model_data:
                model_data.set_downloading(False)
                self._publish_model_data_changed_event(model_name, model_data)
            
            # 使用错误处理服务
            self._handle_exception(e, model_name, "download_model")
            
            return False
    
    def download_cuda_environment(self, file_pattern: str = FILE_PATTERN) -> bool:
        """下载CUDA环境和预编译应用
        
        Args:
            file_pattern: 文件匹配模式，只下载匹配此模式的文件"
        
        Returns:
            bool: 是否成功启动下载
        """
        # 获取环境状态
        env_info = self.environment_service.get_environment_info()
        
        # 检查是否是Windows且有GPU
        if not env_info.is_windows or not env_info.has_gpu:
            # 记录错误
            self._publish_cuda_download_error_event("只有Windows平台上有GPU时才需要CUDA环境")
            return False
        
        # 检查是否已经有下载器活动
        if "cuda_env" in self.active_downloaders and self.active_downloaders["cuda_env"] is not None:
            # 如果下载器已经在运行，返回True
            logger.info("CUDA环境下载已经在进行中")
            return True
            
        if "cuda_env_installer" in self.active_downloaders and self.active_downloaders["cuda_env_installer"] is not None:
            # 如果安装器已经在运行，返回True
            logger.info("CUDA环境安装已经在进行中")
            return True
        
        try:
            # 确保环境目录存在
            # if not self.whisper_app_dir.exists():
            #     self.whisper_app_dir.mkdir(parents=True, exist_ok=True)
                
            # --- 创建临时下载目录 ---
            temp_dir = APP_ENV_DIR / "temp"
            temp_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"创建或确认临时下载目录: {temp_dir}")

            # 创建下载器
            downloader = CudaEnvDownloader(
                model_id=self.WHISPER_APP_MODEL_ID,
                app_name="whisper-app",
                save_path=str(temp_dir),
                file_pattern=file_pattern
            )
            
            # 启动下载器
            downloader.start()
            
            # 保存下载器引用
            self.active_downloaders["cuda_env"] = downloader
            
            # 记录日志
            logger.info(f"CUDA环境下载已启动，临时保存到: {temp_dir}，文件模式: {file_pattern}")
            
            return True
            
        except Exception as e:
            error_msg = f"启动CUDA环境下载失败: {str(e)}"
            logger.error(error_msg)
            
            # 发布错误事件
            self._publish_cuda_download_error_event(error_msg)
            
            # 使用错误处理服务记录
            if self.error_service:
                self.error_service.handle_exception(
                    e,
                    ErrorCategory.MODEL,
                    ErrorPriority.MEDIUM,
                    "ModelManagementService.download_cuda_environment"
                )
            
            return False
    
    def cancel_cuda_download(self) -> bool:
        """取消CUDA环境下载
        
        Returns:
            bool: 是否成功取消下载
        """
        if "cuda_env" in self.active_downloaders and self.active_downloaders["cuda_env"].isRunning():
            self.active_downloaders["cuda_env"].cancel()
            return True
        return False
    
    def cancel_cuda_install(self) -> bool:
        """取消CUDA环境安装
        
        Returns:
            bool: 是否成功取消安装
        """
        if "cuda_env_installer" in self.active_downloaders and self.active_downloaders["cuda_env_installer"].isRunning():
            self.active_downloaders["cuda_env_installer"].cancel()
            return True
        return False
    
    @Slot(str)
    def cancel_download(self, model_name: str) -> bool:
        """取消下载
        
        Args:
            model_name: 模型名称
        
        Returns:
            bool: 是否成功取消
        """
        # 获取模型数据
        model_data = self.get_model_data(model_name)
        if not model_data:
            return False
        
        # 检查是否在下载
        if not model_data.is_downloading or model_name not in self.active_downloaders:
            return False
        
        # 取消下载
        self.active_downloaders[model_name].cancel()
        
        # 从活跃下载器中移除
        del self.active_downloaders[model_name]
        
        # 更新模型状态
        model_data.set_downloading(False)
        
        # 发布数据变更事件
        self._publish_model_data_changed_event(model_name, model_data)
        
        return True
    
    def _check_model_path(self, path: str) -> bool:
        """内部方法：验证模型路径是否有效
        
        Args:
            path: 模型路径
            
        Returns:
            bool: 路径是否有效
        """
        if not path or not os.path.exists(path) or not os.path.isdir(path):
            return False
            
        # 检查model.bin文件是否存在
        model_bin_path = os.path.join(path, "model.bin")
        return os.path.exists(model_bin_path) and os.path.isfile(model_bin_path) and os.path.getsize(model_bin_path) > 0

    @Slot(str)
    def load_model(self, model_name: str) -> bool:
        """加载模型
        
        Args:
            model_name: 模型名称
            
        Returns:
            bool: 是否成功加载
        """
        logger.info(f"开始加载模型: {model_name}")
        
        # 检查模型是否存在
        model_data = self.get_model_data(model_name)
        if not model_data:
            logger.error(f"未知模型: {model_name}")
            self._publish_model_loaded_event(model_name, False, f"未知模型: {model_name}")
            return False
            
        # 检查模型是否已经加载
        if model_data.is_loaded:
            logger.info(f"模型已经加载: {model_name}")
            self._publish_model_loaded_event(model_name, True)
            return True
        
        # 检查模型是否已下载
        if not model_data.is_exists:
            logger.warning(f"模型未下载: {model_name}")
            
            # 如果启用了自动下载，尝试下载
            if self.auto_download_enabled:
                logger.info(f"尝试自动下载模型: {model_name}")
                self.download_model(model_name)
                
            # 不管如何，此时不能加载
            error_msg = f"模型未下载，无法加载: {model_name}"
            self._publish_model_loaded_event(model_name, False, error_msg)
            return False
            
        try:
            # 更新模型状态
            model_data.set_loading(True)
            
            # 发布状态变更事件
            self._publish_model_data_changed_event(model_name, model_data)
            
            # 发布模型加载事件
            self._publish_model_loading_event(model_name)
            
            # 验证模型
            is_valid, error_msg, validated_path = self._validate_model(model_name)
            
            if not is_valid:
                # 更新模型状态 - 重置loading状态
                model_data.set_loading(False)
                model_data.error = error_msg
                
                # 发布状态变更事件
                self._publish_model_data_changed_event(model_name, model_data)
                
                # 发布加载失败事件
                self._publish_model_loaded_event(model_name, False, error_msg)
                
                return False
                
            # 更新模型数据
            model_data.model_path = validated_path
            model_data.is_exists = True
            model_data.set_loaded(True)
            model_data.download_progress = 100
            model_data.error = None
            
            # 发布状态变更事件
            self._publish_model_data_changed_event(model_name, model_data)
            
            # 发布加载成功事件
            self._publish_model_loaded_event(model_name, True)
            
            # 记录当前模型
            self.current_model_name = model_name
            
            return True
            
        except Exception as e:
            logger.error(f"加载模型失败: {str(e)}")
            
            # 更新模型状态
            model_data.set_loading(False)
            model_data.error = str(e)
            
            # 发布状态变更事件
            self._publish_model_data_changed_event(model_name, model_data)
            
            # 发布加载失败事件
            self._publish_model_loaded_event(model_name, False, str(e))
            
            # 使用错误处理服务记录
            if self.error_service:
                self._handle_exception(e, model_name, "load_model")
            
            return False
    
    def get_model_name(self) -> Optional[str]:
        """获取当前设置的模型名称
        
        Returns:
            Optional[str]: 当前模型名称，如果未设置则返回None
        """
        return self.model_name
    
    def get_model_path(self, model_name: str) -> Optional[str]:
        """获取指定模型的路径
        
        Args:
            model_name: 模型名称
            
        Returns:
            Optional[str]: 模型路径，如果模型不存在则返回None
        """
        # 先检查模型是否存在
        model_data = self.get_model_data(model_name)
        if not model_data or not model_data.is_exists:
            logger.warning(f"模型不存在或未下载: {model_name}")
            return None
            
        # 返回模型路径
        return model_data.model_path
    
    def _validate_model(self, model_name: str) -> Tuple[bool, str, Optional[str]]:
        """验证模型是否有效
        
        Args:
            model_name: 模型名称
        
        Returns:
            Tuple[bool, str, Optional[str]]: (是否有效, 错误消息, 模型路径)
        """
        # 获取模型数据
        model_data = self.get_model_data(model_name)
        if not model_data:
            return False, f"未找到模型数据: {model_name}", None
            
        # 检查模型是否存在
        if not model_data.is_exists:
            return False, f"模型 {model_name} 不存在，请先下载", None
        
        # 获取模型路径
        model_path = model_data.model_path
        if not model_path:
            model_path = str(self.models_dir / f"faster-whisper-{model_name}")
        
        # 验证模型路径
        if not self._check_model_path(model_path):
            return False, f"模型 {model_name} 路径无效或不存在: {model_path}", None
        
        return True, "", model_path

    def _publish_model_data_changed_event(self, model_name: str, model_data: ModelData):
        """发布模型数据变更事件
        
        Args:
            model_name: 模型名称
            model_data: 模型数据
        """
        data_event = ModelEvent(
            event_type=EventTypes.MODEL_DATA_CHANGED,
            model_name=model_name,
            model_data=model_data
        )
        event_bus.publish(EventTypes.MODEL_DATA_CHANGED, data_event)

    def _publish_model_loading_event(self, model_name: str):
        """发布模型加载中事件
        
        Args:
            model_name: 模型名称
        """
        loading_event = ModelEvent(
            event_type=EventTypes.MODEL_LOADING,
            model_name=model_name
        )
        event_bus.publish(EventTypes.MODEL_LOADING, loading_event)

    def _publish_model_loaded_event(self, model_name: str, success: bool, error: str = ""):
        """发布模型加载完成事件
        
        Args:
            model_name: 模型名称
            success: 是否成功
            error: 错误信息
        """
        loaded_event = ModelEvent(
            event_type=EventTypes.MODEL_LOADED,
            model_name=model_name,
            success=success,
            error=error
        )
        event_bus.publish(EventTypes.MODEL_LOADED, loaded_event)

    def _publish_model_download_error_event(self, model_name: str, error_msg: str):
        """发布模型下载错误事件
        
        Args:
            model_name: 模型名称
            error_msg: 错误消息
        """
        event_data = ModelEvent(
            event_type=EventTypes.MODEL_DOWNLOAD_ERROR,
            model_name=model_name,
            error=error_msg
        )
        event_bus.publish(EventTypes.MODEL_DOWNLOAD_ERROR, event_data)

    def _publish_model_download_started_event(self, model_name: str):
        """发布模型下载开始事件
        
        Args:
            model_name: 模型名称
        """
        start_event = ModelEvent(
            event_type=EventTypes.MODEL_DOWNLOAD_STARTED,
            model_name=model_name
        )
        event_bus.publish(EventTypes.MODEL_DOWNLOAD_STARTED, start_event)

    def _handle_model_error(self, message: str, priority: ErrorPriority, code: str, 
                           model_name: str, source_suffix: str, user_visible: bool = True):
        """处理模型操作错误
        
        Args:
            message: 错误消息
            priority: 错误优先级
            code: 错误代码
            model_name: 模型名称
            source_suffix: 错误来源后缀
            user_visible: 是否对用户可见
        """
        if self.error_service:
            error_info = ErrorInfo(
                message=message,
                category=ErrorCategory.MODEL,
                priority=priority,
                code=code,
                details={"model_name": model_name},
                source=f"ModelManagementService.{source_suffix}",
                user_visible=user_visible
            )
            self.error_service.handle_error(error_info)

    def _handle_exception(self, exception: Exception, model_name: str, source_suffix: str):
        """处理异常，记录错误并发布事件
        
        Args:
            exception: 异常对象
            model_name: 模型名称
            source_suffix: 源码后缀
        """
        error_msg = f"处理模型 {model_name} 时发生异常: {str(exception)}"
        logger.error(error_msg)
        logger.exception(exception)
        
        # 使用错误处理服务记录
        if self.error_service:
            self.error_service.handle_exception(
                exception,
                ErrorCategory.MODEL,
                ErrorPriority.HIGH,
                f"ModelManagementService.{source_suffix}:{model_name}"
            )

    def is_gpu_optimization_available(self) -> bool:
        """检查是否有GPU优化可用
        
        Returns:
            bool: 是否有GPU优化可用
        """
        # 直接使用环境信息对象
        return self.environment_info.can_use_gpu_acceleration()

    def _handle_environment_status_changed(self, event: EnvironmentStatusEvent):
        """处理环境状态变更事件
        
        当环境状态发生变化时，此方法会被调用，更新本地环境信息引用
        并在必要时触发相应操作。
        
        Args:
            event: 环境状态变更事件
        """
        # 获取新的环境信息
        new_info = event.environment_info
        
        # 如果环境信息没有变化，不需要处理
        if self.environment_info == new_info:
            return
        
        # 检查关键变化
        cuda_changed = self.environment_info.has_gpu != new_info.has_gpu
        precompiled_changed = self.environment_info.whisper_app_available != new_info.whisper_app_available
        
        # 更新本地环境信息引用
        self.environment_info = new_info
        
        # 记录关键变化
        if cuda_changed or precompiled_changed:
            logger.info(f"ModelManagementService: 环境状态已更新 - GPU可用: {new_info.has_gpu}, 预编译应用可用: {new_info.whisper_app_available}")
            if new_info.can_use_gpu_acceleration():
                logger.info("ModelManagementService: 将使用GPU加速模型操作")
            elif new_info.should_download_cuda_env():
                logger.info("ModelManagementService: 检测到GPU但预编译应用不可用，可下载CUDA环境以加速模型操作")
            else:
                logger.info("ModelManagementService: 将使用CPU模式加载模型")

    def __del__(self):
        """对象销毁时的清理操作"""
        try:
            # 取消订阅环境变更事件
            event_bus.unsubscribe(EventTypes.ENVIRONMENT_STATUS_CHANGED, self._handle_environment_status_changed)
            # 取消订阅模型事件
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self._on_model_download_completed)
            event_bus.unsubscribe(EventTypes.CUDA_ENV_DOWNLOAD_COMPLETED, self._on_cuda_env_download_completed)
            event_bus.unsubscribe(EventTypes.MODEL_DOWNLOAD_REQUESTED, self._on_model_download_requested)
        except:
            # 忽略可能的异常
            pass
            
    def _publish_cuda_download_error_event(self, error_msg: str):
        """发布CUDA环境下载错误事件
        
        Args:
            error_msg: 错误消息
        """
        error_event = CudaEnvDownloadErrorEvent(
            app_name="faster-whisper-app",
            error=error_msg
        )
        event_bus.publish(EventTypes.CUDA_ENV_DOWNLOAD_ERROR, error_event)

    def unload_model(self) -> bool:
        """卸载当前加载的模型，释放资源
        
        Returns:
            bool: 卸载是否成功
        """
        logger.info("卸载模型")
        
        # 检查是否有模型已加载
        if not self.current_model_name:
            logger.info("没有模型需要卸载")
            return True
        
        try:
            # 获取当前模型数据
            model_data = self.get_model_data(self.current_model_name)
            if model_data:
                # 更新模型状态
                model_data.set_loaded(False)
                
                # 发布状态变更事件
                self._publish_model_data_changed_event(self.current_model_name, model_data)
            
            # 存储当前模型名称，用于事件发布
            unloaded_model_name = self.current_model_name
            
            # 清除当前模型引用
            self.current_model_name = None
            
            # 发布MODEL_UNLOADED事件
            unload_event = ModelEvent(
                event_type=EventTypes.MODEL_UNLOADED,
                model_name=unloaded_model_name
            )
            event_bus.publish(EventTypes.MODEL_UNLOADED, unload_event)
            
            logger.info(f"模型 {unloaded_model_name} 已成功卸载")
            return True
        except Exception as e:
            logger.error(f"卸载模型失败: {str(e)}")
            
            # 使用错误处理服务记录
            if self.error_service:
                self._handle_exception(e, self.current_model_name if self.current_model_name else "unknown", "unload_model")
            
            return False

    def is_model_loaded(self) -> bool:
        """检查是否已加载模型
        
        Returns:
            bool: 是否已加载模型
        """
        # 如果current_model_name存在且不为空，则认为模型已加载
        return bool(self.current_model_name)