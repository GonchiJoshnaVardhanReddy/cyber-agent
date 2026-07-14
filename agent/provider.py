"""agent/provider.py — LLM provider abstraction.

Supports OpenAI-compatible (OpenAI, Ollama, OpenRouter, vLLM, etc.) and Anthropic
native. The agent loop only knows the LLMProvider interface, never the provider SDK.
"""
from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LLMResponse:
    """Normalized response from any LLM."""
    content: str  # visible text
    tool_calls: list[ToolCall] = field(default_factory=list)
    finish_reason: str = "stop"  # stop | tool_calls | length | content_filter
    usage: dict[str, int] = field(default_factory=dict)  # prompt_tokens, completion_tokens
    raw: Any = None  # original provider response


class LLMProvider(ABC):
    """Abstract LLM provider. The agent loop only knows this interface."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> LLMResponse:
        """Send messages + tools, get a normalized response."""
        ...


class OpenAICompatibleProvider(LLMProvider):
    """Works with OpenAI, Ollama, OpenRouter, vLLM, Together, Groq, etc."""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        # Lazy import so the dependency is only required if you use this provider
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    @property
    def name(self) -> str:
        return "openai-compatible"

    def chat(self, messages, tools, model, temperature=0.2, max_tokens=4096) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools

        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message

        tool_calls: list[ToolCall] = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments) if tc.function.arguments else {}
                except json.JSONDecodeError:
                    args = {"_raw": tc.function.arguments}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, arguments=args))

        finish = resp.choices[0].finish_reason or "stop"
        usage = {}
        if resp.usage:
            usage = {
                "prompt_tokens": resp.usage.prompt_tokens,
                "completion_tokens": resp.usage.completion_tokens,
            }

        return LLMResponse(
            content=msg.content or "",
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
            raw=resp,
        )


class AnthropicProvider(LLMProvider):
    """Native Anthropic Messages API."""

    def __init__(self, api_key: str):
        from anthropic import Anthropic
        self._client = Anthropic(api_key=api_key)

    @property
    def name(self) -> str:
        return "anthropic"

    def chat(self, messages, tools, model, temperature=0.2, max_tokens=4096) -> LLMResponse:
        # Split system from messages (Anthropic takes system separately)
        system_text = ""
        convo: list[dict[str, Any]] = []
        for m in messages:
            if m["role"] == "system":
                system_text += m["content"] + "\n"
            else:
                convo.append(m)

        # Convert OpenAI-style tool schema to Anthropic format
        anthropic_tools = []
        for t in tools:
            fn = t.get("function", t)
            anthropic_tools.append({
                "name": fn["name"],
                "description": fn.get("description", ""),
                "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
            })

        kwargs: dict[str, Any] = {
            "model": model,
            "system": system_text.strip(),
            "messages": convo,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if anthropic_tools:
            kwargs["tools"] = anthropic_tools

        resp = self._client.messages.create(**kwargs)

        content = ""
        tool_calls: list[ToolCall] = []
        for block in resp.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=block.input if isinstance(block.input, dict) else {"_raw": block.input},
                ))

        finish = "tool_calls" if tool_calls else resp.stop_reason or "stop"
        usage = {
            "prompt_tokens": resp.usage.input_tokens,
            "completion_tokens": resp.usage.output_tokens,
        }

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            finish_reason=finish,
            usage=usage,
            raw=resp,
        )


def make_provider_from_config(config_dict: dict) -> tuple[LLMProvider, str]:
    """Pick a provider from config + environment variables. Returns (provider, default_model).
    
    Supports: openai, anthropic, ollama, openrouter, groq, together, vllm, or any OpenAI-compatible endpoint.
    
    Config format:
        agent:
            provider: ollama  # or openai, anthropic, openrouter, groq, together, vllm
            model: llama3.1   # model name for the provider
            base_url: http://localhost:11434/v1  # optional, for OpenAI-compatible providers
    
    Environment variables (override config):
        CYBER_AGENT_PROVIDER: overrides agent.provider
        OPENAI_API_KEY, ANTHROPIC_API_KEY: API keys
        OPENAI_BASE_URL: base URL for OpenAI-compatible providers
        CYBER_AGENT_MODEL: default model name
    """
    agent_cfg = config_dict.get("agent", {})
    
    # Provider can be overridden by env var
    provider_name = os.getenv("CYBER_AGENT_PROVIDER", agent_cfg.get("provider", "openai")).lower()
    
    if provider_name == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        model = os.getenv("CYBER_AGENT_MODEL", agent_cfg.get("model", "claude-3-5-sonnet-20241022"))
        return AnthropicProvider(api_key=api_key), model
    
    # All other providers use OpenAI-compatible API
    # Determine base_url and api_key based on provider
    if provider_name == "ollama":
        base_url = os.getenv("OPENAI_BASE_URL", agent_cfg.get("base_url", "http://localhost:11434/v1"))
        api_key = os.getenv("OPENAI_API_KEY", "ollama")  # Ollama doesn't require a real key
        default_model = agent_cfg.get("model", "llama3.1")
    elif provider_name == "openrouter":
        base_url = os.getenv("OPENAI_BASE_URL", agent_cfg.get("base_url", "https://openrouter.ai/api/v1"))
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set (required for OpenRouter)")
        default_model = agent_cfg.get("model", "meta-llama/llama-3.1-70b-instruct")
    elif provider_name == "groq":
        base_url = os.getenv("OPENAI_BASE_URL", agent_cfg.get("base_url", "https://api.groq.com/openai/v1"))
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set (required for Groq)")
        default_model = agent_cfg.get("model", "llama3-70b-8192")
    elif provider_name == "together":
        base_url = os.getenv("OPENAI_BASE_URL", agent_cfg.get("base_url", "https://api.together.xyz/v1"))
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY not set (required for Together)")
        default_model = agent_cfg.get("model", "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo")
    elif provider_name == "vllm":
        base_url = os.getenv("OPENAI_BASE_URL", agent_cfg.get("base_url", "http://localhost:8000/v1"))
        api_key = os.getenv("OPENAI_API_KEY", "vllm")  # vLLM doesn't require a real key by default
        default_model = agent_cfg.get("model", "")
        if not default_model:
            raise RuntimeError("Model name required for vLLM (set agent.model in config)")
    else:
        # Default to OpenAI
        base_url = os.getenv("OPENAI_BASE_URL", agent_cfg.get("base_url", "https://api.openai.com/v1"))
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Set it in .env or use CYBER_AGENT_PROVIDER=ollama/anthropic/etc."
            )
        default_model = agent_cfg.get("model", "gpt-4o")
    
    model = os.getenv("CYBER_AGENT_MODEL", default_model)
    return OpenAICompatibleProvider(api_key=api_key, base_url=base_url), model


def make_provider_from_env() -> tuple[LLMProvider, str]:
    """Legacy function - kept for backward compatibility. Use make_provider_from_config instead."""
    return make_provider_from_config({})
