#!/usr/bin/env python3
"""
LLM Provider abstraction for NL2SQL evaluation.

Supports multiple providers with a unified interface.
"""

import os
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file (look in project root)
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path, override=True)


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    sql: str
    raw_response: str
    model: str
    latency_ms: float
    error: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate_sql(self, schema: str, question: str) -> LLMResponse:
        """Generate SQL from a natural language question."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider/model name for reporting."""
        pass


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider."""

    def __init__(self, model: str = "claude-opus-4-5-20250101"):
        self.model = model
        self.api_key = os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not set")

        import anthropic
        self.client = anthropic.Anthropic(api_key=self.api_key)

    @property
    def name(self) -> str:
        return f"anthropic/{self.model}"

    def generate_sql(self, prompt_or_schema: str, question: str = "") -> LLMResponse:
        """Generate code from prompt. If question is empty, prompt_or_schema is the full prompt."""
        if question:
            prompt = self._build_prompt(prompt_or_schema, question)
        else:
            prompt = prompt_or_schema

        start = time.time()
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}]
            )
            latency_ms = (time.time() - start) * 1000

            raw = response.content[0].text
            sql = self._extract_code(raw)

            return LLMResponse(
                sql=sql,
                raw_response=raw,
                model=self.model,
                latency_ms=latency_ms
            )
        except Exception as e:
            return LLMResponse(
                sql="",
                raw_response="",
                model=self.model,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    def _build_prompt(self, schema: str, question: str) -> str:
        return f"""Given the following database schema:

{schema}

Write a SQL query to answer this question: {question}

Return only the SQL query, no explanation. Do not wrap in markdown code blocks."""

    def _extract_code(self, response: str) -> str:
        """Extract code from response, handling markdown code blocks."""
        text = response.strip()

        # Remove markdown code blocks if present
        if text.startswith("```malloy"):
            text = text[9:]
        elif text.startswith("```sql"):
            text = text[6:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        return text.strip()


class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider."""

    def __init__(self, model: str = "gpt-5.2"):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not set")

        import openai
        self.client = openai.OpenAI(api_key=self.api_key)

    @property
    def name(self) -> str:
        return f"openai/{self.model}"

    def generate_sql(self, prompt_or_schema: str, question: str = "") -> LLMResponse:
        """Generate code from prompt. If question is empty, prompt_or_schema is the full prompt."""
        if question:
            prompt = self._build_prompt(prompt_or_schema, question)
        else:
            prompt = prompt_or_schema

        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_completion_tokens=1024
            )
            latency_ms = (time.time() - start) * 1000

            raw = response.choices[0].message.content
            code = self._extract_code(raw)

            return LLMResponse(
                sql=code,
                raw_response=raw,
                model=self.model,
                latency_ms=latency_ms
            )
        except Exception as e:
            return LLMResponse(
                sql="",
                raw_response="",
                model=self.model,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    def _build_prompt(self, schema: str, question: str) -> str:
        return f"""Given the following database schema:

{schema}

Write a SQL query to answer this question: {question}

Return only the SQL query, no explanation. Do not wrap in markdown code blocks."""

    def _extract_code(self, response: str) -> str:
        text = response.strip()
        if text.startswith("```malloy"):
            text = text[9:]
        elif text.startswith("```sql"):
            text = text[6:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


class GoogleProvider(LLMProvider):
    """Google Gemini provider."""

    def __init__(self, model: str = "gemini-3-pro"):
        self.model = model
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not set")

        import google.generativeai as genai
        genai.configure(api_key=self.api_key)
        self.client = genai.GenerativeModel(self.model)

    @property
    def name(self) -> str:
        return f"google/{self.model}"

    def generate_sql(self, prompt_or_schema: str, question: str = "") -> LLMResponse:
        if question:
            prompt = self._build_prompt(prompt_or_schema, question)
        else:
            prompt = prompt_or_schema

        start = time.time()
        try:
            response = self.client.generate_content(prompt)
            latency_ms = (time.time() - start) * 1000

            raw = response.text
            code = self._extract_code(raw)

            return LLMResponse(
                sql=code,
                raw_response=raw,
                model=self.model,
                latency_ms=latency_ms
            )
        except Exception as e:
            return LLMResponse(
                sql="",
                raw_response="",
                model=self.model,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    def _build_prompt(self, schema: str, question: str) -> str:
        return f"""Given the following database schema:

{schema}

Write a SQL query to answer this question: {question}

Return only the SQL query, no explanation. Do not wrap in markdown code blocks."""

    def _extract_code(self, response: str) -> str:
        text = response.strip()
        if text.startswith("```malloy"):
            text = text[9:]
        elif text.startswith("```sql"):
            text = text[6:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


class DeepSeekProvider(LLMProvider):
    """DeepSeek provider (OpenAI-compatible API)."""

    def __init__(self, model: str = "deepseek-chat"):
        self.model = model
        self.api_key = os.getenv("DEEPSEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY not set")

        import openai
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

    @property
    def name(self) -> str:
        return f"deepseek/{self.model}"

    def generate_sql(self, prompt_or_schema: str, question: str = "") -> LLMResponse:
        if question:
            prompt = self._build_prompt(prompt_or_schema, question)
        else:
            prompt = prompt_or_schema

        start = time.time()
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024
            )
            latency_ms = (time.time() - start) * 1000

            raw = response.choices[0].message.content
            code = self._extract_code(raw)

            return LLMResponse(
                sql=code,
                raw_response=raw,
                model=self.model,
                latency_ms=latency_ms
            )
        except Exception as e:
            return LLMResponse(
                sql="",
                raw_response="",
                model=self.model,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    def _build_prompt(self, schema: str, question: str) -> str:
        return f"""Given the following database schema:

{schema}

Write a SQL query to answer this question: {question}

Return only the SQL query, no explanation. Do not wrap in markdown code blocks."""

    def _extract_code(self, response: str) -> str:
        text = response.strip()
        if text.startswith("```malloy"):
            text = text[9:]
        elif text.startswith("```sql"):
            text = text[6:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


class MinimaxProvider(LLMProvider):
    """Minimax provider."""

    def __init__(self, model: str = "minimax-2.1"):
        self.model = model
        self.api_key = os.getenv("MINIMAX_API_KEY")
        if not self.api_key:
            raise ValueError("MINIMAX_API_KEY not set")

        import requests
        self.requests = requests
        self.base_url = "https://api.minimax.chat/v1/text/chatcompletion_v2"

    @property
    def name(self) -> str:
        return f"minimax/{self.model}"

    def generate_sql(self, prompt_or_schema: str, question: str = "") -> LLMResponse:
        if question:
            prompt = self._build_prompt(prompt_or_schema, question)
        else:
            prompt = prompt_or_schema

        start = time.time()
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 1024
            }

            response = self.requests.post(
                self.base_url,
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()

            latency_ms = (time.time() - start) * 1000
            data = response.json()

            raw = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            code = self._extract_code(raw)

            return LLMResponse(
                sql=code,
                raw_response=raw,
                model=self.model,
                latency_ms=latency_ms
            )
        except Exception as e:
            return LLMResponse(
                sql="",
                raw_response="",
                model=self.model,
                latency_ms=(time.time() - start) * 1000,
                error=str(e)
            )

    def _build_prompt(self, schema: str, question: str) -> str:
        return f"""Given the following database schema:

{schema}

Write a SQL query to answer this question: {question}

Return only the SQL query, no explanation. Do not wrap in markdown code blocks."""

    def _extract_code(self, response: str) -> str:
        text = response.strip()
        if text.startswith("```malloy"):
            text = text[9:]
        elif text.startswith("```sql"):
            text = text[6:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        return text.strip()


# Registry of available providers
PROVIDERS = {
    "claude-opus-4.5": lambda: AnthropicProvider("claude-opus-4-5-20251101"),
    "gpt-5.2": lambda: OpenAIProvider("gpt-5.2"),
    "gemini-3-pro": lambda: GoogleProvider("gemini-3-pro-preview"),
    "deepseek-v3.2": lambda: DeepSeekProvider("deepseek-chat"),
    "minimax-m2": lambda: MinimaxProvider("MiniMax-Text-01"),
}


def get_provider(name: str) -> LLMProvider:
    """Get a provider by name."""
    if name not in PROVIDERS:
        available = ", ".join(PROVIDERS.keys())
        raise ValueError(f"Unknown provider: {name}. Available: {available}")
    return PROVIDERS[name]()


def list_providers() -> list:
    """List available provider names."""
    return list(PROVIDERS.keys())
