[MODE: PLAN]

# 实施计划：合并ModelService和WhisperModelService

下面是将ModelService和WhisperModelService合并为统一的ModelManagementService的详细实施计划。

## 阶段一：准备工作

1. **创建新的ModelManagementService类**
   - 新建文件 `core/services/model_management_service.py`
   - 整合两个服务的所有功能
   - 确保保留所有现有信号

2. **创建临时兼容层**
   - 添加兼容方法确保向后兼容
   - 添加日志记录以便跟踪旧API的使用

3. **添加单元测试**
   - 为新服务创建测试文件
   - 确保覆盖所有关键功能

## 阶段二：实现ModelManagementService

1. **实现基础结构**
   ```python
   class ModelManagementService(QObject):
       # 合并两个服务的所有信号
       model_downloading = Signal(str)
       model_download_progress = Signal(str, int)
       model_download_completed = Signal(str, bool)
       model_loading = Signal(str)
       model_loaded = Signal(str, bool)
       model_data_changed = Signal(str, object)
       download_error = Signal(str)
   
       def __init__(self, config_service, env_service, notification_service):
           super().__init__()
           self.config_service = config_service
           self.env_service = env_service
           self.notification_service = notification_service
           
           # 模型数据和路径
           self.model_name = None
           self.models_dir = Path(self.config_service.get_model_directory())
           self.models_dir.mkdir(parents=True, exist_ok=True)
           self.model_data_dict = {}
           self.active_downloaders = {}
           
           # 初始化模型数据
           self._init_model_data()
   ```

2. **迁移ModelService核心功能**
   ```python
   def _init_model_data(self):
       """初始化模型数据"""
       # 从ModelService迁移代码
   
   def scan_models(self, force=False):
       """扫描可用模型"""
       # 从ModelService迁移代码
   
   def download_model(self, model_name: str) -> bool:
       """下载模型"""
       # 从ModelService迁移代码
   
   def cancel_download(self, model_name: str) -> bool:
       """取消下载"""
       # 从ModelService迁移代码
   ```

3. **迁移WhisperModelService核心功能**
   ```python
   def _validate_model_path(self, model_name: str) -> Optional[str]:
       """验证模型路径是否有效"""
       # 从WhisperModelService中提取验证逻辑
   
   def load_model(self, name: Optional[str] = None) -> bool:
       """验证并设置Whisper模型"""
       # 整合WhisperModelService.load_model逻辑
   
   def get_model_name(self) -> Optional[str]:
       """获取当前设置的模型名称"""
       return self.model_name
   ```

4. **实现新的统一方法**
   ```python
   def initialize(self):
       """初始化模型服务"""
       # 整合初始化逻辑
   
   def verify_and_download_model(self, model_name: str, status_callback=None) -> bool:
       """验证模型是否存在，如果不存在则自动下载"""
       # 整合验证和下载逻辑
   ```

5. **实现兼容性方法**
   ```python
   def get_model_service(self):
       """兼容性方法，返回self"""
       logger.debug("调用了兼容性方法get_model_service()")
       return self
   ```

## 阶段三：更新依赖注入容器

1. **修改containers.py**
   ```python
   # 从imports中移除WhisperModelService
   from core.services.model_management_service import ModelManagementService
   
   # 注册ModelManagementService
   model_management_service = providers.Singleton(
       ModelManagementService,
       config_service=config_service,
       env_service=env_service,
       notification_service=notification_service
   )
   
   # 更新依赖注入
   transcription_service = providers.Singleton(
       TranscriptionService,
       config_service=config_service,
       model_service=model_management_service,
       audio_service=audio_service,
       env_service=env_service
   )
   
   # 其他依赖于model_service的服务也需要更新
   ```

## 阶段四：更新引用点

1. **修改UI组件中的引用**
   - 识别所有使用ModelService或WhisperModelService的UI组件
   - 确保所有注入点使用新的ModelManagementService

2. **更新TranscriptionService**
   - 确保TranscriptionService中对ModelService的引用正确
   - 验证get_model_service()的兼容性处理

3. **更新依赖注入配置**
   - 检查所有依赖注入配置点
   - 确保wiring_config配置正确

## 阶段五：测试与验证

1. **单元测试**
   - 运行针对ModelManagementService的单元测试
   - 确保所有功能按预期工作

2. **集成测试**
   - 测试UI组件与新服务的交互
   - 测试模型下载和加载流程
   - 验证通知功能

3. **功能测试**
   - 测试模型扫描功能
   - 测试模型下载功能
   - 测试模型加载和验证功能

## 阶段六：清理和文档更新

1. **移除旧服务**
   - 确认所有功能正常后，移除WhisperModelService.py文件
   - 确认所有功能正常后，移除ModelService.py文件

2. **更新文档**
   - 更新架构文档
   - 更新API文档
   - 添加迁移指南

3. **代码清理**
   - 移除所有不必要的兼容性代码
   - 优化实现

## 实施清单：

1. 创建新的ModelManagementService类
   - 创建文件结构
   - 定义所有必要的信号
   - 实现基本构造函数

2. 实现ModelService功能
   - 移植模型扫描功能
   - 移植模型下载功能
   - 移植模型状态管理

3. 实现WhisperModelService功能
   - 移植模型验证逻辑
   - 移植模型加载逻辑
   - 移植与EnvService交互的功能

4. 更新依赖注入配置
   - 修改containers.py
   - 更新所有引用点

5. 添加兼容性层
   - 实现get_model_service()方法
   - 确保传递所有信号

6. 运行测试
   - 验证模型扫描
   - 验证模型下载
   - 验证模型加载
   - 验证UI交互

7. 移除旧服务
   - 移除WhisperModelService.py
   - 移除ModelService.py

8. 更新文档
   - 更新架构图
   - 更新API文档

9. 最终代码清理
   - 优化实现
   - 移除不必要的兼容代码

## 注意事项与风险管理

1. **向后兼容性**
   - 确保保留所有现有信号
   - 添加适当的兼容层处理旧API调用
   - 在开发过程中逐步移除兼容层

2. **错误处理**
   - 确保所有错误处理逻辑保持一致
   - 确保所有异常都被适当捕获和记录

3. **性能考虑**
   - 确保合并后的服务性能不降低
   - 避免不必要的对象创建

4. **测试策略**
   - 先测试基本功能
   - 再测试边缘情况
   - 最后测试UI交互

5. **回滚计划**
   - 保留原始代码备份
   - 准备回滚脚本
   - 设置检查点允许部分回滚

通过这个详细的实施计划，我们可以系统地将ModelService和WhisperModelService合并为统一的ModelManagementService，简化代码结构，提高可维护性，同时确保应用功能不受影响。
