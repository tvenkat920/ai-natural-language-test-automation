"""OpenAI (and compatible) LLM provider implementation."""
import os
from typing import Optional

from planner.llm.providers.base import BaseLLMProvider


class OpenAILLMProvider(BaseLLMProvider):
    """Uses the OpenAI API (or compatible endpoint like Ollama/vLLM) to generate test plans."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4o-mini",
        base_url: Optional[str] = None,
    ):
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._model = model
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL")
        if not self._api_key and not self._base_url:
            raise ValueError(
                "OpenAI API key is required. Set OPENAI_API_KEY or configure a local base_url."
            )
        try:
            import openai as _openai_module
            # Detect openai v1 (new) vs v0 (old) SDK
            if hasattr(_openai_module, "OpenAI"):
                kwargs = {"api_key": self._api_key or "none"}
                if self._base_url:
                    kwargs["base_url"] = self._base_url
                self._client = _openai_module.OpenAI(**kwargs)
                self._use_v1 = True
            else:
                _openai_module.api_key = self._api_key
                if self._base_url:
                    _openai_module.api_base = self._base_url
                self._openai = _openai_module
                self._use_v1 = False
        except ImportError as e:
            raise ImportError("openai package not installed. Run: pip install openai") from e

    @property
    def provider_name(self) -> str:
        return f"openai/{self._model}"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Call the OpenAI Chat Completions API and return the content of the first choice."""
        if self._use_v1:
            response = self._client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )
            return response.choices[0].message.content or ""
        else:
            response = self._openai.ChatCompletion.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
            )
            return response["choices"][0]["message"]["content"]

