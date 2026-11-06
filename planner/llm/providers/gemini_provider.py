"""Google Gemini LLM provider implementation."""
import os
from typing import Optional

from planner.llm.providers.base import BaseLLMProvider


class GeminiLLMProvider(BaseLLMProvider):
    """Uses the Google Gemini API (google-genai SDK) to generate test plans."""

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.5-flash"):
        self._api_key = api_key or os.environ.get("GEMINI_API_KEY", "")
        self._model = model
        if not self._api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY environment variable or pass api_key parameter."
            )
        try:
            from google import genai
            self._client = genai.Client(api_key=self._api_key)
        except ImportError as e:
            raise ImportError("google-genai package not installed. Run: pip install google-genai") from e

    @property
    def provider_name(self) -> str:
        return f"gemini/{self._model}"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Call the Gemini API and return the response text."""
        full_prompt = f"{system_prompt}\n\n---\n\n{user_prompt}"
        response = self._client.models.generate_content(
            model=self._model,
            contents=full_prompt,
        )
        return response.text

