# 混合架构Whisper集成方案

## 背景

目前系统使用独立Python虚拟环境解决方案进行转录，具体包括以下步骤：
1. 安装Python 3.12嵌入版
2. 创建虚拟环境
3. 安装PyTorch
4. 安装faster-whisper

这种方案存在以下问题：
- 配置复杂，过程容易出错
- 下载和安装依赖耗时长
- 环境配置不稳定，受网络和系统状态影响
- 项目复杂度增加，维护成本高

## 解决方案

采用混合架构设计，根据用户环境智能选择最佳实现方式：

1. **默认情况**：直接使用主程序Python环境
   - 直接在主程序中导入faster-whisper库
   - 无需独立Python环境和虚拟环境
   - 适用于所有平台（Windows/Mac/Linux）
   - 程序启动即可使用，无需额外配置

2. **Windows+GPU环境**（优化路径）：使用ModelScope提供的预编译whisper-cpp应用
   - 在模型下载时自动检测环境并集成下载
   - 通过ModelScope API下载并提供进度反馈
   - 针对CUDA优化，提供最佳性能
   - 下载完成后自动切换使用预编译版本

这一混合方案将大幅简化系统架构，同时为GPU用户提供更好的性能体验。

## 架构设计

### 新增组件

**`whisper_manager.py`**
- 智能检测系统环境，选择最佳实现方式
- 使用ModelScope API下载预编译应用
- 提供统一的转录服务接口
- 实现平滑降级策略

### 组件关系图

```
                  ┌───────────────────┐
                  │  ModelScope API   │
                  └────────┬──────────┘
                           │   
                           │   [GPU优化路径]
                           ▼
┌───────────────────────────────────────────────────────┐
│                   whisper_manager.py                  │
├───────────────────────────────────────────────────────┤
│                                                       │
│  ┌─────────────────────┐      ┌────────────────────┐  │
│  │  预编译应用实现     │      │  Python库实现      │  │
│  │  (Windows+GPU)      │      │  (默认路径)        │  │
│  └─────────────────────┘      └────────────────────┘  │
│                                                       │
│  - 统一接口层                                         │
│  - 环境检测与选择                                     │
│  - 实现自动切换                                       │
└─────────────────────────┬─────────────────────────────┘
                          │
                          ▼
┌───────────────────────────────────────────────────────┐
│               transcription_service.py                │
├───────────────────────────────────────────────────────┤
│ - 转录流程控制                                        │
│ - 结果处理                                            │
└───────────────────────────────────────────────────────┘
```

### 用户界面逻辑

```
应用启动
  │
  ├── 初始化默认Python库实现
  │     - 加载基本依赖
  │     - 准备转录环境
  │     - 允许立即开始转录
  │
  └── 用户触发模型下载
        │
        ├── 环境检测
        │     │
        │     ├── Windows+CUDA可用+无whisper app
        │     │     │
        │     │     └── 执行完整下载流程
        │     │          - 触发绑定下载事件
        │     │          - 下载模型(显示0-100%进度)
        │     │          - 下载CUDA环境(显示0-100%进度)
        │     │          - 解压安装CUDA环境
        │     │          - 环境检测
        │     │          - 模型加载
        │     │
        │     ├── Windows+CUDA可用+已有whisper app
        │     │     │
        │     │     └── 执行简化下载流程
        │     │          - 触发绑定下载事件
        │     │          - 下载模型(显示0-100%进度)
        │     │
        │     └── 其他平台或CUDA不可用
        │           │
        │           └── 执行基础下载流程
        │                - 直接触发模型下载事件
        │                - 下载模型(显示0-100%进度)
        │
        └── 下载完成
              - 通知用户"模型准备就绪"
              - 自动使用最佳可用实现
```

### 实现选择逻辑

```
检测系统环境
  │
  ├── 主程序启动时默认使用Python库实现
  │
  ├── 用户触发模型下载
  │     │
  │     └── 环境检测决策
  │          │
  │          ├── 是Windows+CUDA兼容GPU吗？
  │          │     │
  │          │     ├── 是 ──► 检查预编译应用是否已下载
  │          │     │          │
  │          │     │          ├── 已下载 ──► 触发绑定下载事件，下载模型
  │          │     │          │
  │          │     │          └── 未下载 ──► 触发绑定下载事件，下载模型和CUDA环境
  │          │     │
  │          │     └── 否 ──► 直接触发模型下载事件，仅下载模型
  │          │
  │          └── 下载完成后自动选择最佳实现
  │
  └── 降级处理逻辑
        - 如果预编译应用执行失败，自动切换回Python库实现
        - 记录错误并通知用户
```

## 事件设计

为满足新的捆绑下载流程需求，我们将采用条件事件触发策略，根据不同环境选择不同的事件：

### 1. 模型下载事件（已存在）
适用于所有情况，在非CUDA优化场景下作为主要事件使用。

**事件类型：**
- `MODEL_DOWNLOAD_STARTED` (已存在)
- `MODEL_DOWNLOAD_PROGRESS` (已存在)
- `MODEL_DOWNLOAD_COMPLETED` (已存在)
- `MODEL_DOWNLOAD_ERROR` (已存在)

### 2. CUDA环境下载事件
仅用于Windows+CUDA环境下，用于下载预编译whisper-cpp应用。

**事件类型：**
- `CUDA_ENV_DOWNLOAD_STARTED` (新增)
- `CUDA_ENV_DOWNLOAD_PROGRESS` (新增)
- `CUDA_ENV_DOWNLOAD_COMPLETED` (新增)
- `CUDA_ENV_DOWNLOAD_ERROR` (新增)

### 3. CUDA环境安装事件
仅用于Windows+CUDA环境下，用于跟踪预编译应用的解压和安装过程。

**事件类型：**
- `CUDA_ENV_INSTALL_STARTED` (新增)
- `CUDA_ENV_INSTALL_PROGRESS` (新增)
- `CUDA_ENV_INSTALL_COMPLETED` (新增)
- `CUDA_ENV_INSTALL_ERROR` (新增)

### 4. 绑定下载事件
仅用于Windows+CUDA环境下，作为整体流程的元事件。

**事件类型：**
- `BUNDLED_DOWNLOAD_STARTED` (新增)
- `BUNDLED_DOWNLOAD_PROGRESS` (新增)
- `BUNDLED_DOWNLOAD_COMPLETED` (新增)
- `BUNDLED_DOWNLOAD_ERROR` (新增)

### 事件数据结构示例

```python
# CUDA环境下载事件
@dataclass
class CudaEnvDownloadStartedEvent(BaseEvent):
    app_name: str  # 应用名称，如"whisper-cpp"
    version: str  # 版本号
    
@dataclass
class CudaEnvDownloadProgressEvent(BaseEvent):
    app_name: str
    progress: float  # 0.0-1.0
    message: str  # 进度消息

# 绑定下载事件
@dataclass
class BundledDownloadStartedEvent(BaseEvent):
    bundle_id: str  # 绑定ID
    stages: List[str]  # 将执行的阶段列表
    is_cuda_optimization: bool  # 是否包含CUDA优化
    model_name: str  # 模型名称
```

### 条件事件触发策略

根据环境情况选择使用的事件类型：

```python
def download_model(model_name, callback=None):
    """下载模型并根据环境决定是否下载CUDA环境"""
    
    # 检测环境
    is_windows_with_cuda = self._is_windows_with_compatible_gpu()
    cuda_env_needed = is_windows_with_cuda and not self._check_cuda_env_exists()
    
    if is_windows_with_cuda:
        # Windows+CUDA环境：使用绑定事件
        bundle_id = f"whisper_setup_{int(time.time())}"
        
        # 确定要执行的阶段
        stages = ["MODEL_DOWNLOAD"]
        if cuda_env_needed:
            stages.extend(["CUDA_ENV_DOWNLOAD", "CUDA_ENV_INSTALL"])
        
        # 触发绑定开始事件
        event_bus.emit(EventTypes.BUNDLED_DOWNLOAD_STARTED, BundledDownloadStartedEvent(
            bundle_id=bundle_id,
            stages=stages,
            is_cuda_optimization=True,
            model_name=model_name
        ))
        
        # 执行下载流程...
    else:
        # 非CUDA环境：直接使用模型下载事件
        event_bus.emit(EventTypes.MODEL_DOWNLOAD_STARTED, ModelDownloadStartedEvent(
            model_name=model_name
        ))
        
        # 执行下载流程...
```

### 事件流程

根据环境不同，有两种不同的事件流程：

**Windows+CUDA环境流程：**
1. 用户触发模型下载
2. 系统检测环境，触发`BUNDLED_DOWNLOAD_STARTED`事件
3. 开始模型下载，触发`MODEL_DOWNLOAD_STARTED`及其后续事件
4. 如需下载CUDA环境，触发`CUDA_ENV_DOWNLOAD_STARTED`及其后续事件
5. 如需安装CUDA环境，触发`CUDA_ENV_INSTALL_STARTED`及其后续事件
6. 整体流程完成，触发`BUNDLED_DOWNLOAD_COMPLETED`事件

**非CUDA环境流程：**
1. 用户触发模型下载
2. 系统检测环境，直接触发`MODEL_DOWNLOAD_STARTED`事件
3. 模型下载进行中，触发`MODEL_DOWNLOAD_PROGRESS`事件
4. 模型下载完成，触发`MODEL_DOWNLOAD_COMPLETED`事件

### UI响应策略

UI组件需要监听两种不同的事件流程：

```python
# 监听标准模型下载事件（非CUDA环境）
event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_STARTED, self.on_model_download_started)
event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_PROGRESS, self.on_model_download_progress)
event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_COMPLETED, self.on_model_download_completed)
event_bus.subscribe(EventTypes.MODEL_DOWNLOAD_ERROR, self.on_model_download_error)

# 监听绑定下载事件（CUDA环境）
event_bus.subscribe(EventTypes.BUNDLED_DOWNLOAD_STARTED, self.on_bundled_download_started)
event_bus.subscribe(EventTypes.BUNDLED_DOWNLOAD_PROGRESS, self.on_bundled_download_progress)
event_bus.subscribe(EventTypes.BUNDLED_DOWNLOAD_COMPLETED, self.on_bundled_download_completed)
event_bus.subscribe(EventTypes.BUNDLED_DOWNLOAD_ERROR, self.on_bundled_download_error)
```

## 技术细节

### 系统要求

- **通用要求**：
  - Python 3.8+（应用程序主环境）
  - 8GB+ 内存
  - faster-whisper库及其依赖

- **预编译版本要求**（GPU优化路径）：
  - Windows 10/11 64位
  - CUDA兼容显卡，8GB+显存
  - CUDA 11.7或更高版本驱动

### ModelScope下载集成

集成ModelScope API进行模型和预编译应用下载：

1. **模型下载处理**:
   - 使用ModelScope API下载模型文件
   - 直接传递原始进度回调(0-100%)
   - 下载完成后通知用户

2. **CUDA环境下载处理(仅Windows+GPU环境)**:
   - 在模型下载完成后，开始下载预编译应用
   - 同样使用原始进度回调(新的0-100%)
   - 下载完成后执行解压操作
   - 验证安装并设置环境

3. **进度通知**:
   - 每个下载项独立显示进度(0-100%)
   - 清晰标识当前下载内容(模型/CUDA环境)
   - 保持与现有项目下载逻辑一致，使用原生ModelScope进度回调

### 文件组织

```
/LocalAppData/Faster-Vox/
  └── whisper-app/
      ├── faster-whisper.exe
      └── libs/    # CUDA相关库

# 主程序目录
/app/
  ├── requirements.txt # 包含faster-whisper依赖
  └── core/
      └── whisper_manager.py  # 新增的混合管理器
```

### 内部结构

`WhisperManager`类内部组织结构：

```
WhisperManager
├── 环境检测
│   ├── is_windows
│   ├── has_compatible_gpu
│   ├── _detect_compatible_gpu()
│   └── _get_cuda_version()
│
├── 实现选择
│   ├── use_precompiled
│   ├── precompiled_available
│   ├── _select_implementation()
│   └── _ensure_dependencies()
│
├── 预编译应用管理
│   ├── _download_precompiled_app()
│   ├── _extract_app_archive()
│   ├── _verify_app_installation()
│   └── _execute_with_app()
│
├── Python库封装
│   ├── _check_python_dependencies()
│   └── _execute_with_python()
│
├── 统一接口
│   ├── check_environment()
│   ├── setup_environment()
│   ├── execute_transcription()
│   └── is_gpu_optimization_available()
│
└── 错误处理与降级
    ├── _fallback_to_python()
    └── _log_and_notify_error()
```

### 关键接口

1. **环境检测与设置**
   - `check_environment()` - 检查当前环境是否可用
   - `setup_environment()` - 设置需要的环境（保持接口兼容性）
   - `is_gpu_optimization_available()` - 检查是否有GPU优化可用

2. **下载与安装**
   - `download_model(model_name, callback)` - 下载模型并按需下载预编译应用，提供进度反馈
   - `cancel_download()` - 取消正在进行的下载

3. **转录执行**
   - `create_transcription_worker(audio_file, model_path, options)` - 创建转录工作线程
   - `execute_transcription(audio_file, model_path, output_path, options, progress_callback)` - 执行转录


## 实现计划

### 阶段1：基础架构

1. 创建`whisper_manager.py`：
   - 实现环境检测逻辑
   - 集成ModelScope下载功能
   - 构建统一接口

2. 移除嵌入式Python和虚拟环境代码：
   - 删除或标记废弃`env_manager.py`
   - 更新依赖，添加faster-whisper到requirements.txt

### 阶段2：实现与集成

1. 完成两种具体实现：
   - 预编译应用调用实现（Windows+GPU）
   - Python库直接调用实现（默认路径）

2. 修改下载流程：
   - 将模型下载与CUDA环境下载逻辑整合
   - 根据环境智能选择下载内容和事件类型
   - 实现顺序下载流程，保持原生进度反馈

3. 修改`containers.py`：
   - 注册WhisperManager
   - 更新依赖注入关系

4. 适配`transcription_service.py`：
   - 确保兼容新的WhisperManager接口
   - 更新转录参数传递方式

5. 更新事件系统：
   - 在`event_types.py`中添加新的事件类型
   - 实现条件事件触发策略
   - 添加相应的事件处理逻辑

### 阶段3：测试与优化

1. 单元测试和集成测试：
   - 在不同环境测试自动选择
   - 验证条件事件触发策略
   - 测试降级和错误处理

2. 性能优化：
   - 比较两种实现的性能差异
   - 优化模型加载时间

3. 用户体验改进：
   - 添加设置选项允许手动选择实现
   - 提供详细的性能对比信息

## 优势与风险

### 优势

1. **极大简化架构**
   - 移除了复杂的独立Python环境
   - 减少了近80%的环境设置代码
   - 降低了安装和配置出错几率

2. **无缝用户体验**
   - 程序启动即可使用（默认Python实现）
   - 模型下载过程中自动获取CUDA优化组件
   - 无需用户额外操作，自动适应最佳环境

3. **集成下载流程**
   - 将模型和CUDA环境下载整合为一体
   - 消除了单独通知和用户决策步骤
   - 保持简单直观的进度显示

4. **事件系统优化**
   - 针对不同环境使用最合适的事件集合
   - 避免在简单场景中过度使用复杂事件
   - UI可以获得特定于环境的详细反馈

### 风险

1. **预编译版本限制**
   - 仅Windows平台有GPU优化版本
   - 依赖第三方预编译版本更新

2. **主程序依赖管理**
   - 需要确保主程序环境正确安装依赖
   - 可能与其他依赖产生冲突

3. **用户期望管理**
   - 需要清晰传达性能差异
   - 避免在非兼容环境引起困惑

4. **事件处理复杂性**
   - UI需要处理两种不同的事件流程
   - 需要确保所有环境下的用户体验一致

## 依赖管理

1. **主程序依赖**
   - 更新`requirements.txt`添加：
     ```
     faster-whisper>=0.9.0
     modelscope>=1.9.5
     ```
   - 确保PyTorch版本兼容性

2. **预编译版本**
   - 使用ModelScope API获取最新版本
   - 自动处理文件下载和解压
   - 提供版本检查和更新机制

## 总结

混合架构Whisper集成方案通过智能环境检测和集成下载流程，为用户提供了无缝的体验。新设计根据用户环境选择最合适的下载内容和事件类型：

1. 对于Windows+CUDA可用+无whisper app的用户：
   - 触发绑定下载事件系统
   - 自动完成模型下载、CUDA环境下载、解压、环境检测和模型加载
   - UI收到详细的阶段和进度信息

2. 对于Windows+CUDA可用+已有whisper app的用户：
   - 触发绑定下载事件系统
   - 只下载模型，然后使用已有的whisper app
   - UI收到简化但仍然完整的阶段信息

3. 对于其他平台或CUDA不可用的用户：
   - 直接触发模型下载事件
   - 只下载模型，使用CPU转录
   - UI收到标准的模型下载进度信息

这种条件事件触发策略既保持了代码的简洁性，又为不同环境的用户提供了最合适的反馈。进度回调机制简单直观，每个下载项显示独立的0-100%进度。通过避免在简单场景中使用复杂的事件系统，同时在复杂场景提供详细反馈，新设计实现了最佳的用户体验和系统效率平衡。 