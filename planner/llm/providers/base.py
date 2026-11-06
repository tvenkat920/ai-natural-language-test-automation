"""Abstract base class for all LLM provider implementations."""
from abc import ABC, abstractmethod
from typing import Optional


class BaseLLMProvider(ABC):
    """Interface that every LLM backend must implement."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """
        Send a prompt to the LLM and return the raw string response.

        Args:
            system_prompt: Instruction for the model (role + JSON schema guidance).
            user_prompt: The user's natural language test case + context.

        Returns:
            Raw string response from the LLM (expected to be valid JSON).
        """
        ...

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the human-readable name of the provider."""
        ...

