# 需求文档

## 简介

LiveCodeBench 是一个大模型代码能力评测项目，目前仅支持硬编码的模型列表和固定的 API 端点。本功能旨在添加通用的 OpenAI 兼容 API 支持，使用户无需修改源代码即可使用 Ollama、LM Studio、vLLM 远程部署等任意 OpenAI 兼容服务进行模型评测。

## 术语表

- **LiveCodeBench**：大模型代码能力评测基准框架
- **OpenAI_Compatible_API**：遵循 OpenAI Chat Completions API 协议的第三方服务接口（如 Ollama、LM Studio、vLLM 等提供的接口）
- **LanguageModelStore**：`lm_styles.py` 中以 model_name 为键存储所有已注册 LanguageModel 对象的字典
- **LMStyle**：`lm_styles.py` 中定义模型交互风格的枚举类
- **Runner**：负责向模型 API 发送请求并获取响应的执行器类
- **base_url**：OpenAI 兼容 API 服务的基础 URL 地址（例如 Ollama 默认为 `http://localhost:11434/v1`，LM Studio 默认为 `http://localhost:1234/v1`）
- **Parser**：`parser.py` 中负责解析命令行参数的模块
- **/v1/models 端点**：OpenAI 兼容 API 提供的模型列表查询接口，返回该服务中可用的模型列表，用于验证指定模型是否存在于远程服务中

## 需求

### 需求 1：新增 OpenAI 兼容 LMStyle 枚举值

**用户故事：** 作为评测开发者，我希望有一个专用的 LMStyle 枚举值来标识 OpenAI 兼容模型，以便系统能正确路由到对应的 Runner。

#### 验收标准

1. THE LMStyle 枚举 SHALL 包含一个名为 `OpenAICompatible` 的枚举值
2. WHEN Runner 选择逻辑处理 `OpenAICompatible` 风格时，THE build_runner 函数 SHALL 返回支持自定义 base_url 的 Runner 实例

### 需求 2：支持命令行动态注册自定义模型

**用户故事：** 作为评测用户，我希望通过命令行参数指定自定义模型，而无需修改 `lm_styles.py` 源代码。

#### 验收标准

1. THE Parser SHALL 支持 `--base-url` 参数，用于指定 OpenAI 兼容 API 的基础 URL 地址
2. THE Parser SHALL 支持 `--api-key` 参数，用于指定 API 密钥（覆盖默认环境变量）
3. WHEN 用户提供 `--base-url` 参数时，THE 系统 SHALL 自动将该模型视为 OpenAI 兼容模型，无需该模型预先注册在 LanguageModelStore 中
4. WHEN 用户未提供 `--base-url` 参数时，THE 系统 SHALL 保持现有行为，从 LanguageModelStore 中查找模型

### 需求 3：动态创建 LanguageModel 对象

**用户故事：** 作为评测用户，我希望系统能根据命令行参数动态创建模型对象，以便在不修改源代码的情况下评测任意 OpenAI 兼容模型。

#### 验收标准

1. WHEN 用户提供 `--base-url` 参数且 `--model` 指定的模型名称不在 LanguageModelStore 中时，THE 系统 SHALL 调用 `--base-url` 指定的 OpenAI 兼容 API 的 `/v1/models` 端点，验证该模型是否存在于远程服务中
2. WHEN 远程服务的 `/v1/models` 端点确认模型存在时，THE 系统 SHALL 动态创建一个 LanguageModel 对象，其 model_name 和 model_repr 均使用 `--model` 参数的值，model_style 设置为 `OpenAICompatible`，release_date 设为 None
3. WHEN 远程服务的 `/v1/models` 端点确认模型不存在时，THE 系统 SHALL 输出错误信息，提示用户该模型在远程服务中不可用
4. WHEN 动态创建的模型用于评测时，THE 系统 SHALL 使用该模型的 model_repr（即 `--model` 参数的值）作为输出目录名称

### 需求 4：OpenAI 兼容 Runner 支持自定义端点

**用户故事：** 作为评测用户，我希望 Runner 能连接到任意 OpenAI 兼容 API 端点，以便使用 Ollama、LM Studio 等本地模型服务。

#### 验收标准

1. WHEN 模型风格为 `OpenAICompatible` 时，THE Runner SHALL 使用用户指定的 base_url 初始化 OpenAI 客户端
2. WHEN 用户通过 `--api-key` 提供 API 密钥时，THE Runner SHALL 使用该密钥进行认证
3. WHEN 用户未通过 `--api-key` 提供 API 密钥时，THE Runner SHALL 使用环境变量 `OPENAI_API_KEY` 的值，若该环境变量也未设置则使用占位符字符串 `no-key-provided`
4. THE OpenAI 兼容 Runner SHALL 复用现有 OpenAIRunner 的请求逻辑（消息格式、重试机制、错误处理）
5. THE OpenAI 兼容 Runner SHALL 支持与 OpenAIRunner 相同的采样参数（temperature、max_tokens、top_p、n）

### 需求 5：现有功能向后兼容

**用户故事：** 作为现有用户，我希望新功能不会破坏现有的模型评测流程。

#### 验收标准

1. WHEN 用户未提供 `--base-url` 参数时，THE 系统 SHALL 保持与当前版本完全一致的行为
2. THE 现有 LanguageModelStore 中的所有模型 SHALL 继续正常工作，无需任何修改
3. THE 现有 OpenAIRunner 的类级别客户端初始化方式 SHALL 保持不变，仅在 OpenAI 兼容模式下使用实例级别客户端
4. WHEN 用户使用已注册模型名称且同时提供 `--base-url` 时，THE 系统 SHALL 优先使用 `--base-url` 指定的端点（即命令行参数覆盖预注册配置）

### 需求 6：提供清晰的错误提示

**用户故事：** 作为评测用户，我希望在配置错误时获得清晰的错误信息，以便快速定位和解决问题。

#### 验收标准

1. IF 用户提供的 `--model` 名称不在 LanguageModelStore 中且未提供 `--base-url` 参数，THEN THE 系统 SHALL 输出错误信息，提示用户该模型未注册，并建议使用 `--base-url` 参数指定自定义端点
2. IF 用户提供的 `--model` 名称不在 LanguageModelStore 中且提供了 `--base-url` 参数，但远程服务的 `/v1/models` 端点确认该模型不存在，THEN THE 系统 SHALL 输出错误信息，提示用户该模型既未在本地注册也未在远程服务中找到
3. IF 调用远程服务的 `/v1/models` 端点时连接失败，THEN THE 系统 SHALL 输出包含 base_url 地址的错误信息，帮助用户排查连接问题
4. IF OpenAI 兼容 API 端点在评测过程中连接失败，THEN THE Runner SHALL 输出包含 base_url 地址的错误信息，帮助用户排查连接问题
