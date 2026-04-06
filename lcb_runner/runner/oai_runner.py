import os
from time import sleep

try:
    import openai
    from openai import OpenAI
except ImportError as e:
    pass

from lcb_runner.lm_styles import LMStyle
from lcb_runner.runner.base_runner import BaseRunner


class OpenAIRunner(BaseRunner):
    _client = None

    @classmethod
    def _get_default_client(cls):
        """延迟初始化默认 OpenAI 客户端，避免在模块导入时因缺少 API key 而报错。"""
        if cls._client is None:
            cls._client = OpenAI(
                api_key=os.getenv("OPENAI_KEY"),
            )
        return cls._client

    def __init__(self, args, model):
        super().__init__(args, model)
        if model.model_style == LMStyle.OpenAICompatible:
            # OpenAI 兼容模式：使用实例级别客户端，支持自定义 base_url
            api_key = args.api_key or os.environ.get("OPENAI_API_KEY", "no-key-provided")
            self.instance_client = OpenAI(
                api_key=api_key,
                base_url=args.base_url,
            )
            self.client_kwargs: dict[str | str] = {
                "model": args.model,
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "top_p": args.top_p,
                "n": args.n,
                "timeout": args.openai_timeout,
            }
        elif model.model_style == LMStyle.OpenAIReasonPreview:
            self.client_kwargs: dict[str | str] = {
                "model": args.model,
                "max_completion_tokens": 25000,
            }
        elif model.model_style == LMStyle.OpenAIReason:
            assert (
                "__" in args.model
            ), f"Model {args.model} is not a valid OpenAI Reasoning model as we require reasoning effort in model name."
            model, reasoning_effort = args.model.split("__")
            self.client_kwargs: dict[str | str] = {
                "model": model,
                "reasoning_effort": reasoning_effort,
            }
        else:
            self.client_kwargs: dict[str | str] = {
                "model": args.model,
                "temperature": args.temperature,
                "max_tokens": args.max_tokens,
                "top_p": args.top_p,
                "frequency_penalty": 0,
                "presence_penalty": 0,
                "n": args.n,
                "timeout": args.openai_timeout,
                # "stop": args.stop, --> stop is only used for base models currently
            }

    def _run_single(self, prompt: list[dict[str, str]], n: int = 10) -> list[str]:
        assert isinstance(prompt, list)

        if n == 0:
            print("Max retries reached. Returning empty response.")
            return [""] * self.args.n

        # 根据是否存在 instance_client 选择客户端
        client = getattr(self, "instance_client", None) or OpenAIRunner._get_default_client()

        try:
            response = client.chat.completions.create(
                messages=prompt,
                **self.client_kwargs,
            )
        except (
            openai.APIError,
            openai.RateLimitError,
            openai.InternalServerError,
            openai.OpenAIError,
            openai.APIStatusError,
            openai.APITimeoutError,
            openai.InternalServerError,
            openai.APIConnectionError,
        ) as e:
            print("Exception: ", repr(e))
            if hasattr(self, "instance_client"):
                print(f"连接端点：{self.instance_client.base_url}")
            print("Sleeping for 30 seconds...")
            print("Consider reducing the number of parallel processes.")
            sleep(30)
            return self._run_single(prompt, n=n - 1)
        except Exception as e:
            print(f"Failed to run the model for {prompt}!")
            print("Exception: ", repr(e))
            if hasattr(self, "instance_client"):
                print(f"连接端点：{self.instance_client.base_url}")
            raise e
        return [c.message.content for c in response.choices]
