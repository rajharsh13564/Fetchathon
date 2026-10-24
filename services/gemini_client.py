"""Gemini API client with error handling and retries."""
import asyncio
import json
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold

from config.settings import get_settings
from config.logging_config import get_logger
from shared.errors import GeminiAPIError, RateLimitError, ConfigurationError

logger = get_logger(__name__)


@dataclass
class GeminiResponse:
    """Structured response from Gemini."""
    text: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    raw_response: Any = None


class GeminiClient:
    """Async wrapper for Gemini API with retries and error handling."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        self.settings = get_settings()
        self.api_key = api_key or self.settings.gemini_api_key
        self.model_name = model or self.settings.gemini_model
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

        self._model = None
        self._configured = False

    def _configure(self) -> None:
        """Configure Gemini client."""
        if self._configured:
            return

        if not self.api_key or self.api_key == "your_gemini_api_key_here":
            raise ConfigurationError(
                "Gemini API key not configured. Set GEMINI_API_KEY in .env file."
            )

        genai.configure(api_key=self.api_key)
        self._model = genai.GenerativeModel(self.model_name)
        self._configured = True
        logger.info(f"Gemini client configured with model: {self.model_name}")

    def _get_safety_settings(self) -> Dict[HarmCategory, HarmBlockThreshold]:
        """Get safety settings for financial content."""
        return {
            HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
            HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_MEDIUM_AND_ABOVE,
        }

    async def _generate_with_retry(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
        response_schema: Optional[Dict] = None,
    ) -> GeminiResponse:
        """Generate content with exponential backoff retry."""
        self._configure()

        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [system_prompt]})
            contents.append({"role": "model", "parts": ["Understood. I'll follow those instructions."]})
        contents.append({"role": "user", "parts": [prompt]})

        generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if response_schema else "text/plain",
        )

        if response_schema:
            generation_config.response_schema = response_schema

        last_exception = None
        delay = self.base_delay

        for attempt in range(self.max_retries):
            try:
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: self._model.generate_content(
                        contents=contents,
                        generation_config=generation_config,
                        safety_settings=self._get_safety_settings(),
                    )
                )

                if response.text:
                    usage = None
                    if hasattr(response, 'usage_metadata') and response.usage_metadata:
                        usage = {
                            "prompt_tokens": response.usage_metadata.prompt_token_count,
                            "candidates_tokens": response.usage_metadata.candidates_token_count,
                            "total_tokens": response.usage_metadata.total_token_count,
                        }

                    return GeminiResponse(
                        text=response.text,
                        model=self.model_name,
                        usage=usage,
                        finish_reason=getattr(response, 'finish_reason', None),
                        raw_response=response,
                    )
                else:
                    raise GeminiAPIError("Empty response from Gemini")

            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()

                if "rate limit" in error_msg or "quota" in error_msg or "429" in error_msg:
                    if attempt < self.max_retries - 1:
                        logger.warning(f"Rate limited, retrying in {delay}s (attempt {attempt + 1}/{self.max_retries})")
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, self.max_delay)
                        continue
                    raise RateLimitError(f"Gemini rate limit exceeded: {str(e)}")

                if "api key" in error_msg or "authentication" in error_msg or "401" in error_msg:
                    raise GeminiAPIError(f"Authentication failed: {str(e)}")

                if attempt < self.max_retries - 1:
                    logger.warning(f"Gemini error, retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, self.max_delay)
                    continue

                raise GeminiAPIError(f"Gemini API error after {self.max_retries} attempts: {str(e)}")

        raise GeminiAPIError(f"Max retries exceeded: {str(last_exception)}")

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """Generate plain text response."""
        response = await self._generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response.text

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        schema: Optional[Dict] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """Generate JSON response with optional schema validation."""
        response = await self._generate_with_retry(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            response_schema=schema,
        )

        try:
            return json.loads(response.text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {response.text[:200]}")
            raise GeminiAPIError(f"Invalid JSON response: {str(e)}")

    async def generate_structured(
        self,
        prompt: str,
        response_model: type,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 4096,
    ) -> Any:
        """Generate structured response using Pydantic model."""
        # Convert Pydantic model to JSON schema
        schema = response_model.model_json_schema()
        result = await self.generate_json(
            prompt=prompt,
            system_prompt=system_prompt,
            schema=schema,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        return response_model.model_validate(result)


# Global client instance
_gemini_client: Optional[GeminiClient] = None


def get_gemini_client() -> Optional[GeminiClient]:
    """Get global Gemini client if configured."""
    global _gemini_client
    settings = get_settings()
    if settings.validate_gemini_key():
        if _gemini_client is None:
            _gemini_client = GeminiClient()
        return _gemini_client
    return None


def reset_gemini_client() -> None:
    """Reset global client (useful for testing)."""
    global _gemini_client
    _gemini_client = None