"""OpenAI 兼容 API 支持的单元测试。"""

import os
import sys
import argparse
from unittest.mock import patch, MagicMock

import pytest
import requests_mock

# 在导入 OpenAIRunner 之前设置环境变量，避免类级别 OpenAI 客户端初始化失败
os.environ.setdefault("OPENAI_KEY", "test-placeholder-key")

from lcb_runner.lm_styles import LMStyle, LanguageModel, LanguageModelStore
from lcb_runner.runner.runner_utils import build_runner
from lcb_runner.runner.main import validate_model_on_remote, resolve_model


# ============================================================
# 辅助函数：构造 mock args 对象
# ============================================================

def make_args(**overrides):
    """创建一个模拟的 args 对象，包含所有必要的默认值。"""
    defaults = {
        "model": "test-model",
        "base_url": None,
        "api_key": None,
        "local_model_path": None,
        "trust_remote_code": False,
        "temperature": 0.2,
        "max_tokens": 2000,
        "top_p": 0.95,
        "n": 10,
        "openai_timeout": 90,
        "stop": ["###"],
        "use_cache": False,
        "multiprocess": 0,
        "debug": False,
    }
    defaults.update(overrides)
    return argparse.Namespace(**defaults)


# ============================================================
# 测试 1：LMStyle.OpenAICompatible 枚举值存在性
# ============================================================

class TestLMStyleEnum:
    def test_openai_compatible_enum_exists(self):
        """验证 LMStyle 枚举中包含 OpenAICompatible 值。"""
        assert hasattr(LMStyle, "OpenAICompatible")
        assert LMStyle.OpenAICompatible.value == "OpenAICompatible"


# ============================================================
# 测试 2：命令行参数解析
# ============================================================

class TestParserArgs:
    def test_base_url_default_none(self):
        """验证 --base-url 参数默认为 None。"""
        args = make_args()
        assert args.base_url is None

    def test_api_key_default_none(self):
        """验证 --api-key 参数默认为 None。"""
        args = make_args()
        assert args.api_key is None

    def test_base_url_parsed(self):
        """验证 --base-url 参数可以正确设置。"""
        args = make_args(base_url="http://localhost:11434/v1")
        assert args.base_url == "http://localhost:11434/v1"

    def test_api_key_parsed(self):
        """验证 --api-key 参数可以正确设置。"""
        args = make_args(api_key="test-key-123")
        assert args.api_key == "test-key-123"


# ============================================================
# 测试 3：resolve_model 函数
# ============================================================

class TestResolveModel:
    def test_with_base_url_returns_openai_compatible(self):
        """提供 --base-url 时，返回 OpenAICompatible 风格的模型。"""
        args = make_args(
            model="my-custom-model",
            base_url="http://localhost:11434/v1",
        )
        with requests_mock.Mocker() as m:
            m.get(
                "http://localhost:11434/v1/models",
                json={"data": [{"id": "my-custom-model"}]},
            )
            model = resolve_model(args)

        assert model.model_style == LMStyle.OpenAICompatible
        assert model.model_name == "my-custom-model"
        assert model.model_repr == "my-custom-model"
        assert model.release_date is None

    def test_registered_model_without_base_url(self):
        """未提供 --base-url 时，从 LanguageModelStore 查找已注册模型。"""
        # 从 LanguageModelStore 中取一个已注册的模型名称
        registered_name = next(iter(LanguageModelStore.keys()))
        args = make_args(model=registered_name)
        model = resolve_model(args)
        assert model is LanguageModelStore[registered_name]

    def test_unregistered_model_without_base_url_exits(self):
        """未提供 --base-url 且模型未注册时，应报错退出。"""
        args = make_args(model="nonexistent-model-xyz")
        with pytest.raises(SystemExit) as exc_info:
            resolve_model(args)
        assert exc_info.value.code == 1

    def test_registered_model_with_base_url_overrides(self):
        """已注册模型 + --base-url 时，应覆盖为 OpenAICompatible 模式。"""
        registered_name = next(iter(LanguageModelStore.keys()))
        args = make_args(
            model=registered_name,
            base_url="http://localhost:1234/v1",
        )
        model = resolve_model(args)
        assert model.model_style == LMStyle.OpenAICompatible


# ============================================================
# 测试 4：validate_model_on_remote 函数
# ============================================================

class TestValidateModelOnRemote:
    def test_model_exists_on_remote(self):
        """远程服务确认模型存在时，验证通过（不抛异常）。"""
        with requests_mock.Mocker() as m:
            m.get(
                "http://localhost:11434/v1/models",
                json={"data": [{"id": "llama3"}, {"id": "qwen2:7b"}]},
            )
            # 不应抛出异常
            validate_model_on_remote(
                "llama3", "http://localhost:11434/v1", None
            )

    def test_model_not_exists_on_remote_exits(self):
        """远程服务确认模型不存在时，应报错退出。"""
        with requests_mock.Mocker() as m:
            m.get(
                "http://localhost:11434/v1/models",
                json={"data": [{"id": "llama3"}]},
            )
            with pytest.raises(SystemExit) as exc_info:
                validate_model_on_remote(
                    "nonexistent-model",
                    "http://localhost:11434/v1",
                    None,
                )
            assert exc_info.value.code == 1

    def test_connection_error_exits(self):
        """连接失败时，应报错退出。"""
        import requests

        with requests_mock.Mocker() as m:
            m.get(
                "http://localhost:99999/v1/models",
                exc=requests.ConnectionError("Connection refused"),
            )
            with pytest.raises(SystemExit) as exc_info:
                validate_model_on_remote(
                    "test-model",
                    "http://localhost:99999/v1",
                    None,
                )
            assert exc_info.value.code == 1

    def test_api_key_from_arg(self):
        """验证 --api-key 参数优先于环境变量。"""
        with requests_mock.Mocker() as m:
            adapter = m.get(
                "http://localhost:11434/v1/models",
                json={"data": [{"id": "test-model"}]},
            )
            validate_model_on_remote(
                "test-model",
                "http://localhost:11434/v1",
                "my-custom-key",
            )
            # 验证请求头中使用了自定义 key
            assert adapter.last_request.headers["Authorization"] == "Bearer my-custom-key"

    def test_api_key_from_env(self):
        """验证未提供 --api-key 时使用 OPENAI_API_KEY 环境变量。"""
        with requests_mock.Mocker() as m:
            adapter = m.get(
                "http://localhost:11434/v1/models",
                json={"data": [{"id": "test-model"}]},
            )
            with patch.dict(os.environ, {"OPENAI_API_KEY": "env-key-456"}):
                validate_model_on_remote(
                    "test-model",
                    "http://localhost:11434/v1",
                    None,
                )
            assert adapter.last_request.headers["Authorization"] == "Bearer env-key-456"

    def test_api_key_fallback_no_key(self):
        """验证无 --api-key 且无环境变量时使用占位符。"""
        with requests_mock.Mocker() as m:
            adapter = m.get(
                "http://localhost:11434/v1/models",
                json={"data": [{"id": "test-model"}]},
            )
            with patch.dict(os.environ, {}, clear=True):
                # 确保 OPENAI_API_KEY 不存在
                os.environ.pop("OPENAI_API_KEY", None)
                validate_model_on_remote(
                    "test-model",
                    "http://localhost:11434/v1",
                    None,
                )
            assert adapter.last_request.headers["Authorization"] == "Bearer no-key-provided"


# ============================================================
# 测试 5：build_runner 路由
# ============================================================

class TestBuildRunner:
    def test_openai_compatible_routes_to_openai_runner(self):
        """OpenAICompatible 风格应路由到 OpenAIRunner。"""
        from lcb_runner.runner.oai_runner import OpenAIRunner

        model = LanguageModel(
            model_name="test-model",
            model_repr="test-model",
            model_style=LMStyle.OpenAICompatible,
            release_date=None,
        )
        args = make_args(
            model="test-model",
            base_url="http://localhost:11434/v1",
            api_key="test-key",
        )
        runner = build_runner(args, model)
        assert isinstance(runner, OpenAIRunner)


# ============================================================
# 测试 6：OpenAIRunner 在 OpenAICompatible 模式下的行为
# ============================================================

class TestOpenAIRunnerCompatible:
    def test_instance_client_created(self):
        """OpenAICompatible 模式下应创建 instance_client。"""
        from lcb_runner.runner.oai_runner import OpenAIRunner

        model = LanguageModel(
            model_name="test-model",
            model_repr="test-model",
            model_style=LMStyle.OpenAICompatible,
            release_date=None,
        )
        args = make_args(
            model="test-model",
            base_url="http://localhost:11434/v1",
            api_key="test-key",
        )
        runner = OpenAIRunner(args, model)
        assert hasattr(runner, "instance_client")
        assert str(runner.instance_client.base_url).rstrip("/") == "http://localhost:11434/v1"

    def test_instance_client_uses_custom_api_key(self):
        """OpenAICompatible 模式下 instance_client 应使用自定义 API 密钥。"""
        from lcb_runner.runner.oai_runner import OpenAIRunner

        model = LanguageModel(
            model_name="test-model",
            model_repr="test-model",
            model_style=LMStyle.OpenAICompatible,
            release_date=None,
        )
        args = make_args(
            model="test-model",
            base_url="http://localhost:11434/v1",
            api_key="my-secret-key",
        )
        runner = OpenAIRunner(args, model)
        assert runner.instance_client.api_key == "my-secret-key"

    def test_client_kwargs_contains_sampling_params(self):
        """OpenAICompatible 模式下 client_kwargs 应包含采样参数。"""
        from lcb_runner.runner.oai_runner import OpenAIRunner

        model = LanguageModel(
            model_name="test-model",
            model_repr="test-model",
            model_style=LMStyle.OpenAICompatible,
            release_date=None,
        )
        args = make_args(
            model="test-model",
            base_url="http://localhost:11434/v1",
            api_key="key",
            temperature=0.5,
            max_tokens=1000,
            top_p=0.9,
            n=5,
        )
        runner = OpenAIRunner(args, model)
        assert runner.client_kwargs["model"] == "test-model"
        assert runner.client_kwargs["temperature"] == 0.5
        assert runner.client_kwargs["max_tokens"] == 1000
        assert runner.client_kwargs["top_p"] == 0.9
        assert runner.client_kwargs["n"] == 5

    def test_normal_openai_chat_no_instance_client(self):
        """非 OpenAICompatible 模式下不应创建 instance_client。"""
        from lcb_runner.runner.oai_runner import OpenAIRunner

        model = LanguageModel(
            model_name="gpt-4",
            model_repr="GPT-4",
            model_style=LMStyle.OpenAIChat,
            release_date=None,
        )
        args = make_args(model="gpt-4")
        runner = OpenAIRunner(args, model)
        assert not hasattr(runner, "instance_client")
