# 实现计划：OpenAI 兼容 API 支持

## 概述

基于设计文档，按增量方式实现 OpenAI 兼容 API 支持。从底层枚举扩展开始，逐步向上构建命令行参数、动态模型解析、Runner 扩展和路由，最后集成测试。每一步都在前一步基础上构建，确保无孤立代码。

## 任务

- [ ] 1. 扩展 LMStyle 枚举和命令行参数
  - [ ] 1.1 在 `lcb_runner/lm_styles.py` 的 `LMStyle` 枚举中新增 `OpenAICompatible = "OpenAICompatible"` 值
    - 在现有枚举值列表末尾（`TogetherAI` 之后）添加
    - _需求：1.1_
  - [ ] 1.2 在 `lcb_runner/runner/parser.py` 中新增 `--base-url` 和 `--api-key` 命令行参数
    - `--base-url`：类型 `str`，默认 `None`，帮助文本说明用于指定 OpenAI 兼容 API 基础 URL
    - `--api-key`：类型 `str`，默认 `None`，帮助文本说明用于指定 API 密钥
    - 两个参数均为可选
    - _需求：2.1, 2.2_

- [ ] 2. 实现动态模型查找与创建逻辑
  - [ ] 2.1 在 `lcb_runner/runner/main.py` 中实现 `validate_model_on_remote` 函数
    - 使用 `requests.get` 调用 `{base_url}/models` 端点
    - 解析返回的 JSON，提取可用模型 ID 列表
    - 模型不存在时打印错误信息并 `sys.exit(1)`
    - 连接失败时打印包含 `base_url` 的错误信息并 `sys.exit(1)`
    - API 密钥优先级：`--api-key` > `OPENAI_API_KEY` 环境变量 > `"no-key-provided"`
    - _需求：3.1, 3.3, 6.2, 6.3_
  - [ ] 2.2 在 `lcb_runner/runner/main.py` 中实现 `resolve_model` 函数
    - 当提供 `--base-url` 时：若模型不在 `LanguageModelStore` 中则调用 `validate_model_on_remote` 验证；无论是否已注册，均动态创建 `LanguageModel` 对象（`model_style=LMStyle.OpenAICompatible`，`release_date=None`）
    - 当未提供 `--base-url` 时：从 `LanguageModelStore` 查找，找不到则打印错误信息（建议使用 `--base-url`）并 `sys.exit(1)`
    - _需求：2.3, 2.4, 3.2, 3.4, 5.4, 6.1_
  - [ ] 2.3 修改 `lcb_runner/runner/main.py` 的 `main()` 函数，将 `model = LanguageModelStore[args.model]` 替换为 `model = resolve_model(args)`
    - 确保后续逻辑（output_path、runner 构建等）使用返回的 model 对象
    - _需求：2.3, 2.4, 5.1_

- [ ] 3. 检查点 - 确保核心模型解析逻辑正确
  - 确保所有测试通过，如有疑问请询问用户。

- [ ] 4. 扩展 OpenAIRunner 支持自定义端点
  - [ ] 4.1 修改 `lcb_runner/runner/oai_runner.py` 的 `OpenAIRunner.__init__` 方法
    - 新增对 `LMStyle.OpenAICompatible` 的处理分支（放在现有分支之前）
    - 创建实例级别 `self.instance_client = OpenAI(api_key=..., base_url=args.base_url)`
    - API 密钥优先级：`args.api_key` > `os.environ.get("OPENAI_API_KEY")` > `"no-key-provided"`
    - 设置 `client_kwargs`：包含 `model`、`temperature`、`max_tokens`、`top_p`、`n`、`timeout`
    - _需求：4.1, 4.2, 4.3, 4.5_
  - [ ] 4.2 修改 `lcb_runner/runner/oai_runner.py` 的 `_run_single` 方法
    - 在方法开头通过 `getattr(self, "instance_client", OpenAIRunner.client)` 选择客户端
    - 使用选中的客户端替代硬编码的 `OpenAIRunner.client` 发送请求
    - 在异常处理中，若存在 `instance_client`，打印包含 `base_url` 的错误信息
    - _需求：4.4, 6.4_

- [ ] 5. 扩展 Runner 路由
  - [ ] 5.1 在 `lcb_runner/runner/runner_utils.py` 的 `build_runner` 函数中添加 `OpenAICompatible` 路由
    - 在函数最前面（现有 `OpenAIChat` 判断之前）添加对 `LMStyle.OpenAICompatible` 的判断
    - 路由到 `OpenAIRunner`
    - _需求：1.2, 5.2_

- [ ] 6. 检查点 - 确保端到端流程可用
  - 确保所有测试通过，如有疑问请询问用户。

- [ ] 7. 编写单元测试
  - [ ] 7.1 创建测试文件 `tests/test_openai_compatible.py`，编写核心单元测试
    - 测试 `LMStyle.OpenAICompatible` 枚举值存在性
    - 测试 `--base-url` 和 `--api-key` 参数解析
    - 测试 `resolve_model`：提供 `--base-url` 时返回 `OpenAICompatible` 模型
    - 测试 `resolve_model`：未提供 `--base-url` 时从 `LanguageModelStore` 查找已注册模型
    - 测试 `resolve_model`：未提供 `--base-url` 且模型未注册时报错退出
    - 测试 `build_runner`：`OpenAICompatible` 风格路由到 `OpenAIRunner`
    - 测试远程验证：mock `/v1/models` 端点返回模型存在
    - 测试远程验证：mock `/v1/models` 端点返回模型不存在时报错
    - 测试远程验证：mock 连接失败时报错
    - 测试 OpenAIRunner 在 `OpenAICompatible` 模式下使用 `instance_client`
    - _需求：1.1, 1.2, 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 4.1, 5.1, 5.2, 6.1, 6.2, 6.3_


  - [ ]* 7.2 编写属性测试：属性 1 - --base-url 触发 OpenAI 兼容模式
    - **属性 1：--base-url 触发 OpenAI 兼容模式**
    - 使用 hypothesis 生成随机模型名称和随机 URL
    - 验证 `resolve_model` 返回的对象 `model_style == LMStyle.OpenAICompatible`
    - **验证需求：2.3, 5.4**

  - [ ]* 7.3 编写属性测试：属性 2 - 无 --base-url 时保持现有行为
    - **属性 2：无 --base-url 时保持现有行为**
    - 使用 hypothesis 从 `LanguageModelStore` 随机选取已注册模型名称
    - 验证 `resolve_model` 返回的对象与 `LanguageModelStore[model_name]` 是同一引用
    - **验证需求：2.4, 5.1**

  - [ ]* 7.4 编写属性测试：属性 3 - 动态创建 LanguageModel 的正确性
    - **属性 3：动态创建 LanguageModel 的正确性**
    - 使用 hypothesis 生成随机非空字符串作为模型名称
    - 验证动态创建的对象满足：`model_name == args.model`，`model_repr == args.model`，`model_style == LMStyle.OpenAICompatible`，`release_date is None`
    - **验证需求：3.2, 3.4**

  - [ ]* 7.5 编写属性测试：属性 4 - Runner 使用用户指定的 base_url
    - **属性 4：Runner 使用用户指定的 base_url**
    - 使用 hypothesis 生成随机合法 URL 字符串
    - 验证 OpenAIRunner 的 `instance_client.base_url` 等于用户指定的值
    - **验证需求：4.1**

  - [ ]* 7.6 编写属性测试：属性 5 - API 密钥优先级解析
    - **属性 5：API 密钥优先级解析**
    - 使用 hypothesis 生成 `api_key` 参数值和 `OPENAI_API_KEY` 环境变量值的随机组合（包括 None）
    - 验证优先级：(1) `--api-key` > (2) `OPENAI_API_KEY` > (3) `"no-key-provided"`
    - **验证需求：4.2, 4.3**

  - [ ]* 7.7 编写属性测试：属性 6 - 采样参数正确传递
    - **属性 6：采样参数正确传递**
    - 使用 hypothesis 生成随机合法采样参数（temperature ∈ [0,2]，max_tokens > 0，top_p ∈ [0,1]，n > 0）
    - 验证 `client_kwargs` 包含这些参数且值一致
    - **验证需求：4.5**

  - [ ]* 7.8 编写属性测试：属性 7 - 已注册模型路由保持不变
    - **属性 7：已注册模型路由保持不变**
    - 使用 hypothesis 从 `LanguageModelStore` 随机选取模型
    - 验证 `build_runner` 返回的 Runner 类型与该模型 `model_style` 对应的原有 Runner 类型一致
    - **验证需求：5.2**

- [ ] 8. 最终检查点 - 确保所有测试通过
  - 确保所有测试通过，如有疑问请询问用户。

## 备注

- 标记 `*` 的任务为可选任务，可跳过以加速 MVP 交付
- 每个任务引用了对应的需求编号，确保可追溯性
- 检查点任务确保增量验证
- 属性测试使用 hypothesis 库验证通用正确性属性
- 单元测试验证具体示例和边界情况
