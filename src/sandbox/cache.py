"""Caching for sandbox - LangGraph testing environment.

Custom SQLite cache implementation for LLM responses with LiteLLM sanitization.
"""

from collections.abc import Sequence

from langchain_community.cache import SQLiteCache
from langchain_core.outputs import ChatGeneration, Generation


class LiteLLMCache(SQLiteCache):
    """A custom SQLiteCache that sanitizes LangChain generations before storing them.

    This is necessary because ChatLiteLLM returns objects (like litellm.Usage)
    that are not serializable by LangChain's default serializer.
    """

    def update(
        self, prompt: str, llm_string: str, return_val: Sequence[Generation]
    ) -> None:
        """Update the cache with the given prompt and return value.

        Args:
            prompt: The prompt string.
            llm_string: The LLM configuration string.
            return_val: The list of generations to cache.
        """
        for gen in return_val:
            # Sanitize response_metadata
            if isinstance(gen, ChatGeneration) and hasattr(
                gen.message, "response_metadata"
            ):
                meta = gen.message.response_metadata
                for key, value in list(meta.items()):
                    if hasattr(
                        value, "__class__"
                    ) and value.__class__.__module__.startswith("litellm"):
                        try:
                            if hasattr(value, "model_dump"):
                                meta[key] = value.model_dump()
                            elif hasattr(value, "dict"):
                                meta[key] = value.dict()
                            elif hasattr(value, "__dict__"):
                                meta[key] = value.__dict__
                            else:
                                meta[key] = str(value)
                        except Exception:
                            meta[key] = str(value)

            # Sanitize additional_kwargs
            if isinstance(gen, ChatGeneration) and hasattr(
                gen.message, "additional_kwargs"
            ):
                kwargs = gen.message.additional_kwargs
                # litellm puts raw ChatCompletionMessageToolCall objects in tool_calls
                # which breaks serialization. We can sanitize them or remove them.
                # Since standard 'tool_calls' attribute exists, we can try to sanitize.
                if "tool_calls" in kwargs:
                    tool_calls = kwargs["tool_calls"]
                    if isinstance(tool_calls, list):
                        new_tool_calls = []
                        for tc in tool_calls:
                            if hasattr(
                                tc, "__class__"
                            ) and tc.__class__.__module__.startswith("litellm"):
                                try:
                                    if hasattr(tc, "model_dump"):
                                        new_tool_calls.append(tc.model_dump())
                                    elif hasattr(tc, "dict"):
                                        new_tool_calls.append(tc.dict())
                                    elif hasattr(tc, "__dict__"):
                                        new_tool_calls.append(tc.__dict__)
                                    else:
                                        # If we can't serialize, removing might be safer
                                        # if the standard tool_calls field is present
                                        new_tool_calls.append(str(tc))
                                except Exception:
                                    new_tool_calls.append(str(tc))
                            else:
                                new_tool_calls.append(tc)
                        kwargs["tool_calls"] = new_tool_calls

        super().update(prompt, llm_string, return_val)
