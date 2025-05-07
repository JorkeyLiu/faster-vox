# 独立环境转录架构重构计划

## 1. 背景与目标

### 1.1 背景

Faster-Vox 应用程序当前同时支持两种转录模式：
1. **内置转录**：直接在主应用程序进程中加载 PyTorch 和 Whisper 模型执行转录
2. **独立环境转录**：通过独立的 Python 环境运行 Whisper 模型执行转录

内置转录模式存在以下问题：
- 需要将 PyTorch 和 Whisper 打包进主应用程序，导致安装包体积过大
- 与用户机器上的 GPU 驱动兼容性问题复杂
- 故障排查和版本管理困难

根据 PyTorch CUDA 集成计划的实施，独立环境转录功能已经完善并稳定运行。现在需要完全移除内置转录相关代码，专注于独立环境转录架构。

### 1.2 重构目标

1. **架构简化**：移除所有与内置转录相关的代码，简化系统架构
2. **职责明确**：重新定义各个服务组件的职责边界，确保清晰的关注点分离
3. **可维护性提升**：减少冗余代码，降低系统的复杂性和技术债务
4. **错误修复**：解决当前架构中存在的依赖问题，如 `'ModelService' object has no attribute 'whisper_model_service'` 错误

## 2. 系统当前状态分析

### 2.1 核心服务组件

当前系统包含以下核心服务组件：

1. **EnvService**：负责管理独立 Python 环境，提供环境初始化、验证和执行转录任务的功能
2. **WhisperModelService**：负责模型的加载和使用，可以直接加载内置模型或通过 EnvService 验证独立环境中的模型
3. **ModelService**：负责模型的下载、状态管理和高级操作，持有 WhisperModelService 的引用
4. **TranscriptionService**：负责转录任务的处理，根据 use_env 标志决定使用内置转录或独立环境转录
5. **TranscriptionProcessService**：为内置转录提供核心处理逻辑
6. **~~EnvTranscriptionProcessService~~**：曾作为独立环境转录的中间层，现已移除

### 2.2 存在的问题

1. **代码冗余**：系统同时维护两套转录路径，导致代码冗余和复杂性增加
2. **依赖混乱**：服务之间的依赖关系不清晰，如 `TranscriptionService` 试图访问 `model_service.whisper_model_service`
3. **职责重叠**：多个服务之间存在功能重叠，如音频提取逻辑同时存在于多个服务中
4. **架构不一致**：架构设计在向独立环境转录演进过程中产生了不一致

## 3. 重构方案

### 3.1 服务组件重构

#### 3.1.1 移除 TranscriptionThread 类

`TranscriptionThread` 类是为内置转录设计的，应完全移除：

```python
# 在 core/services/transcription_service.py 中删除
class TranscriptionThread(QThread):
    # 整个类定义将被移除
    pass
```

#### 3.1.2 简化 TranscriptionService 类

清理 `TranscriptionService` 类中与内置转录相关的代码：

```python
class TranscriptionService(QObject):
    # 信号定义保持不变
    
    def __init__(self, config_service, model_service, audio_service, env_service=None):
        super().__init__()
        
        # 保留基本依赖注入
        self.config_service = config_service
        self.model_service = model_service
        self.audio_service = audio_service
        self.env_service = env_service
        
        # 移除 self.active_threads 字典
        # self.active_threads: Dict[str, TranscriptionThread] = {}
        
        # 保留独立环境相关的属性
        self.active_env_tasks = {}  # 存储独立环境任务上下文
        self._signal_handlers = {}  # 存储信号处理器
        
        # 转录参数相关代码保持不变
        self.transcription_parameters = TranscriptionParameters()
        self._load_default_parameters()
        self._set_model_name()
        
        # 独立环境标志始终为 True
        self.use_env = True
        
        # 环境服务检查
        if self.env_service is None:
            logger.error("环境服务未初始化，应用可能无法正常工作")
        elif not self.env_service.check_environment():
            logger.info("独立Python环境尚未设置，开始自动设置...")
            self._setup_environment()
        
        # 连接内部信号
        self._env_transcription_completed.connect(self._handle_env_transcription_completed_slot)
    
    def process_audio(self, task_id, file_path, language=None, output_format="srt"):
        """处理音频文件转录，只使用独立环境"""
        try:
            # 文件检查代码保持不变
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 发送状态
            self.process_status.emit(task_id, ProcessStatus.STARTED, 0.0)
            logger.info(f"[{task_id}] 开始处理文件: {file_path}")
            
            # 检查环境是否可用
            if not self.env_service:
                error_message = "环境服务未初始化"
                logger.error(f"[{task_id}] {error_message}")
                self.process_error.emit(task_id, error_message)
                self.process_status.emit(task_id, ProcessStatus.FAILED, 0.0)
                return
                
            if not self.env_service.check_environment():
                error_message = "独立Python环境未设置，请先设置环境"
                logger.error(f"[{task_id}] {error_message}")
                self.process_error.emit(task_id, error_message)
                self.process_status.emit(task_id, ProcessStatus.FAILED, 0.0)
                if not self.env_service.setup_worker or not self.env_service.setup_worker.isRunning():
                    logger.info(f"[{task_id}] 尝试自动设置环境...")
                    self.env_service.setup_environment()
                return
            
            # 独立环境转录流程代码保持不变
            # 提取音频、准备参数、连接信号、调用EnvService.transcribe等
            
            # 移除 else 分支代码 (内置转录相关)
            
        except Exception as e:
            # 错误处理代码保持不变
            pass
    
    # 删除不再需要的方法:
    # _handle_thread_result
    # _handle_thread_cancelled
    # _check_thread_finished
    # 所有其他只被内置转录逻辑使用的私有方法
```

#### 3.1.3 优化 ModelService 类

修改 `ModelService` 类，确保它正确暴露 `WhisperModelService` 实例：

```python
class ModelService(QObject):
    # 基本代码保持不变
    
    def _set_model_name(self):
        """从配置服务获取模型名称设置到转录参数中"""
        # 使用 get_model_service() 获取 WhisperModelService 实例
        whisper_model_service = self.get_model_service()
        if whisper_model_service:
            if hasattr(whisper_model_service, 'get_model_name'):
                model_name = whisper_model_service.get_model_name()
                if model_name:
                    self.transcription_parameters.model_name = model_name
                    return
        
        # 如果配置服务存在，从配置中获取model_name
        if hasattr(self.config_service, 'get_model_name'):
            self.transcription_parameters.model_name = self.config_service.get_model_name()
    
    def get_model_service(self):
        """获取WhisperModelService实例
        
        Returns:
            WhisperModelService: 模型服务实例
        """
        return self._model_service
```

#### 3.1.4 更新 WhisperModelService 处理方式

确保 `WhisperModelService` 在使用独立环境时正确工作：

```python
class WhisperModelService(QObject):
    # 基本代码保持不变
    
    def load_model(self, name=None):
        """加载/验证模型
        
        注意：当使用独立环境时，此方法主要验证模型是否存在并可用
        """
        try:
            # 获取模型名称
            if name:
                model_name = name
            else:
                model_name = self.config_service.get_model_name() if self.config_service else "medium"
            
            logger.debug(f"请求加载模型: {model_name}")
            self.model_name = model_name
            self.model_loading.emit(model_name)
            
            # 获取模型目录
            model_dir = self._get_model_directory(model_name)
            if not model_dir:
                self.model_loaded.emit(model_name, False)
                return False
            
            # 如果存在环境服务且环境可用，使用环境服务验证模型
            if self.env_service and self.env_service.is_environment_available():
                logger.info(f"使用环境服务验证模型: {model_name}")
                # 简单地验证模型目录存在即可，实际验证在转录时进行
                is_valid = os.path.exists(model_dir)
                self.model_loaded.emit(model_name, is_valid)
                return is_valid
            
            # 环境服务不可用，发送失败信号
            logger.error("环境服务不可用，无法加载模型")
            self.model_loaded.emit(model_name, False)
            return False
            
        except Exception as e:
            logger.error(f"加载模型过程中发生错误: {str(e)}")
            self.model_loaded.emit(self.model_name if self.model_name else name, False)
            return False
    
    # 保留 transcribe 方法但添加警告，因为实际转录应该通过 EnvService 进行
    def transcribe(self, *args, **kwargs):
        """此方法已废弃，请使用 EnvService.transcribe"""
        logger.warning("直接使用 WhisperModelService.transcribe 已废弃，请使用 EnvService.transcribe")
        raise NotImplementedError("直接使用 WhisperModelService.transcribe 已废弃")
```

### 3.2 依赖注入配置更新

评估 `TranscriptionProcessService` 的必要性，更新依赖注入配置：

```python
# core/containers.py

class AppContainer(containers.DeclarativeContainer):
    # 大部分配置保持不变
    
    # 更新 WhisperModelService 的依赖项，确保 env_service 被正确注入
    whisper_model_service = providers.Singleton(
        WhisperModelService,
        config_service=config_service,
        notification_service=notification_service,
        env_service=env_service
    )
    
    # 如果决定保留 TranscriptionProcessService 作为历史兼容
    # 可以保留此配置，但应在文档中明确标记为已废弃
    transcription_process_service = providers.Singleton(
        TranscriptionProcessService,
        whisper_model_service=whisper_model_service,
        config_service=config_service,
        audio_service=audio_service
    )
    
    # 更新 TranscriptionService 的依赖项
    transcription_service = providers.Singleton(
        TranscriptionService,
        config_service=config_service,
        model_service=model_service,
        audio_service=audio_service,
        env_service=env_service
    )
```

### 3.3 信号处理机制优化

确保信号连接和处理机制正确可靠：

```python
# 在 TranscriptionService 类中
def _emit_env_transcription_completed(self, task_id, success, error, data):
    """通过内部信号转发 EnvService 的完成信号"""
    # 使用内部信号确保处理函数在正确的线程中执行
    self._env_transcription_completed.emit(task_id, success, error, data)

@Slot(str, bool, str, object)
def _handle_env_transcription_completed_slot(self, task_id, success, error, data):
    """处理 EnvService 的完成信号"""
    logger.info(f"[{task_id}] 收到EnvService完成信号: success={success}, error='{error}'")
    
    # 验证任务上下文是否存在
    if task_id not in self.active_env_tasks:
        logger.warning(f"[{task_id}] 收到完成信号，但任务不在活动列表中")
        return
    
    # 断开信号连接
    if task_id in self._signal_handlers:
        try:
            # 使用存储的处理函数断开连接
            self.env_service.transcription_progress.disconnect(self._signal_handlers[task_id]['progress'])
            self.env_service.transcription_completed.disconnect(self._signal_handlers[task_id]['completed'])
            # 删除处理函数
            del self._signal_handlers[task_id]
            logger.info(f"[{task_id}] 已断开EnvService信号")
        except Exception as e:
            logger.warning(f"[{task_id}] 断开EnvService信号时出错: {e}")
    
    # 处理结果
    # 剩余代码保持不变
```

## 4. 实施步骤

为了安全地完成架构重构，建议按照以下步骤进行：

### 4.1 修复当前错误

首先修复 `'ModelService' object has no attribute 'whisper_model_service'` 错误：

1. 确认 `ModelService` 类中的 `get_model_service()` 方法存在并正确实现
2. 在 `TranscriptionService` 类中修改对 `model_service.whisper_model_service` 的引用，改为使用 `model_service.get_model_service()`

### 4.2 移除内置转录代码

1. 删除 `TranscriptionThread` 类
2. 简化 `TranscriptionService.process_audio` 方法，移除内置转录相关的代码分支
3. 删除仅被内置转录逻辑使用的私有方法

### 4.3 更新服务职责

1. 确保 `WhisperModelService` 正确处理独立环境下的模型验证
2. 更新 `ModelService` 类，确保它不再直接处理转录逻辑
3. 评估和更新 `TranscriptionProcessService` 的职责

### 4.4 更新依赖注入配置

检查并更新 `AppContainer` 中的依赖注入配置，确保所有服务之间的依赖关系正确。

### 4.5 优化信号处理

改进信号连接和断开连接的逻辑，确保可靠性和内存安全性。

### 4.6 更新文档

更新类和方法的文档注释，反映新的架构设计和职责划分。

## 5. 风险评估与缓解策略

### 5.1 潜在风险

1. **功能回归**：重构过程可能引入回归问题
2. **信号连接中断**：修改信号处理逻辑可能导致连接丢失
3. **错误处理不完整**：移除代码时可能意外删除错误处理逻辑

### 5.2 缓解策略

1. **增量式修改**：按照步骤逐步进行修改，每次修改后进行测试
2. **全面测试**：在每个主要修改点进行单元测试和集成测试
3. **代码审查**：引入同行审查确保重构质量
4. **回滚计划**：保留完整的历史版本，确保在问题出现时可以回滚

## 6. 测试计划

### 6.1 单元测试

1. **WhisperModelService 测试**
   - 测试模型加载和验证功能
   - 测试与环境服务的集成

2. **TranscriptionService 测试**
   - 测试音频处理和转录功能
   - 测试信号处理机制

3. **ModelService 测试**
   - 测试模型状态管理
   - 测试模型下载功能

### 6.2 集成测试

1. **完整转录流程测试**
   - 测试从文件选择到结果导出的完整流程
   - 验证不同文件格式和语言的支持

2. **取消操作测试**
   - 测试在不同阶段取消转录的行为

3. **错误处理测试**
   - 测试各种错误情况的处理

## 7. 结论

通过此次重构，Faster-Vox 应用将完全转向使用独立环境进行转录，这将使架构更加清晰、代码更加简洁，并降低维护成本。重构完成后，系统将只有一条清晰的转录路径，所有服务组件都有明确定义的职责，用户体验也将更加一致。

## 8. 附录

### 8.1 相关文件列表

- `core/services/transcription_service.py`
- `core/services/model_service.py`
- `core/services/whisper_model_service.py`
- `core/services/env_service.py`
- `core/services/transcription_process_service.py`
- `core/containers.py`

### 8.2 参考

- [PyTorch CUDA 集成计划](pytorch_cuda_integration_plan.md)
- [依赖注入文档](DEPENDENCY_INJECTION.md) 