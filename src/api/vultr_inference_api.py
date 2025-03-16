"""
Vultr Inference API Client

This module provides a client for Vultr's Serverless Inference service,
allowing Origin to run machine learning models on Vultr's infrastructure.
This serves as a backup inference provider when Mikael's WSL environment
is unavailable.

Vultr's inference API is OpenAI-compatible, so we use the OpenAI Python SDK.
"""

import os
import json
import time
import logging
import requests
from typing import Dict, List, Any, Optional, Union
from datetime import datetime, timedelta

# Import OpenAI SDK
try:
    from openai import OpenAI, APIError, APIConnectionError, RateLimitError
    OPENAI_SDK_AVAILABLE = True
except ImportError:
    OPENAI_SDK_AVAILABLE = False
    APIError = Exception
    APIConnectionError = Exception
    RateLimitError = Exception

logger = logging.getLogger(__name__)

class VultrInferenceClient:
    """
    Client for Vultr Serverless Inference API using OpenAI SDK.
    """
    
    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initialize the Vultr Inference client
        
        Args:
            api_key: Vultr API key (defaults to VULTR_INFERENCE_API_KEY environment variable)
            base_url: Base URL for Vultr Inference API (defaults to VULTR_INFERENCE_URL environment variable)
        """
        self.api_key = api_key or os.environ.get('VULTR_INFERENCE_API_KEY')
        self.base_url = base_url or os.environ.get(
            'VULTR_INFERENCE_URL', 'https://api.vultrinference.com/v1'
        )
        
        if not self.api_key:
            logger.warning("No Vultr Inference API key provided")
        
        # Initialize OpenAI client if available
        if OPENAI_SDK_AVAILABLE:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info(f"Initialized OpenAI SDK client for Vultr Inference with base URL: {self.base_url}")
        else:
            self.client = None
            logger.warning("OpenAI SDK not available. Install with 'pip install openai'")
            
            # Create fallback requests session
            self.session = requests.Session()
            self.session.headers.update({
                'Authorization': f'Bearer {self.api_key}',
                'Content-Type': 'application/json',
                'Accept': 'application/json'
            })
            logger.info(f"Initialized fallback requests client for Vultr Inference with base URL: {self.base_url}")
        
        # Track request rate for client-side rate limiting
        self.recent_requests = []
        self.rate_limit_config = {
            'requests_per_minute': 100,
            'backoff_seconds': 1,
            'max_backoff_seconds': 60
        }
    
    def _rate_limit(self):
        """Implement client-side rate limiting"""
        now = time.time()
        
        # Remove timestamps older than 1 minute
        self.recent_requests = [ts for ts in self.recent_requests if now - ts < 60]
        
        # Check if we've hit the rate limit
        if len(self.recent_requests) >= self.rate_limit_config['requests_per_minute']:
            # Calculate time to wait
            oldest = min(self.recent_requests)
            wait_time = 60 - (now - oldest)
            if wait_time > 0:
                logger.warning(f"Rate limit reached, waiting {wait_time:.2f} seconds")
                time.sleep(wait_time)
        
        # Add current timestamp
        self.recent_requests.append(now)
    
    def list_models(self) -> List[Dict[str, Any]]:
        """
        List available models on Vultr Inference
        
        Returns:
            List of model information dictionaries
        """
        self._rate_limit()
        
        try:
            if OPENAI_SDK_AVAILABLE and self.client:
                models = self.client.models.list()
                return [model.model_dump() for model in models.data]
            else:
                # Fallback to direct API call
                response = self.session.get(f"{self.base_url}/models")
                response.raise_for_status()
                return response.json().get('data', [])
        except (APIError, requests.RequestException) as e:
            logger.error(f"Failed to list models: {e}")
            return []
    
    def chat_completion(self,
                        model: str,
                        messages: List[Dict[str, str]],
                        max_tokens: int = 256,
                        temperature: float = 0.7,
                        top_p: float = 1.0,
                        stop: Optional[List[str]] = None,
                        stream: bool = False,
                        **kwargs) -> Dict[str, Any]:
        """
        Generate chat completion using Vultr Inference
        
        Args:
            model: Model ID to use
            messages: List of message dictionaries with 'role' and 'content'
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter
            stop: Optional list of stop sequences
            stream: Whether to stream the response
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with completion data
        """
        self._rate_limit()
        
        try:
            if OPENAI_SDK_AVAILABLE and self.client:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop,
                    stream=stream,
                    **kwargs
                )
                
                # Handle streaming responses
                if stream:
                    return response  # Return the stream directly
                else:
                    # Convert to dictionary that matches raw API response
                    return {
                        "id": response.id,
                        "object": response.object,
                        "created": response.created,
                        "model": response.model,
                        "choices": [
                            {
                                "message": {
                                    "role": choice.message.role,
                                    "content": choice.message.content
                                },
                                "index": choice.index,
                                "finish_reason": choice.finish_reason
                            } for choice in response.choices
                        ],
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens
                        }
                    }
            else:
                # Fallback to direct API call
                payload = {
                    "model": model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "stream": stream,
                    **kwargs
                }
                
                if stop:
                    payload["stop"] = stop
                
                response = self.session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except (APIError, requests.RequestException) as e:
            logger.error(f"Chat completion failed: {e}")
            raise
    
    def text_completion(self, 
                       model: str,
                       prompt: str,
                       max_tokens: int = 256,
                       temperature: float = 0.7,
                       top_p: float = 1.0,
                       stop: Optional[List[str]] = None,
                       stream: bool = False,
                       **kwargs) -> Dict[str, Any]:
        """
        Generate text completion using Vultr Inference
        
        Args:
            model: Model ID to use
            prompt: Text prompt to generate completion for
            max_tokens: Maximum number of tokens to generate
            temperature: Sampling temperature (0-1)
            top_p: Nucleus sampling parameter
            stop: Optional list of stop sequences
            stream: Whether to stream the response
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with completion data
        """
        self._rate_limit()
        
        try:
            if OPENAI_SDK_AVAILABLE and self.client:
                response = self.client.completions.create(
                    model=model,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    top_p=top_p,
                    stop=stop,
                    stream=stream,
                    **kwargs
                )
                
                # Handle streaming responses
                if stream:
                    return response  # Return the stream directly
                else:
                    # Convert to dictionary that matches raw API response
                    return {
                        "id": response.id,
                        "object": response.object,
                        "created": response.created,
                        "model": response.model,
                        "choices": [
                            {
                                "text": choice.text,
                                "index": choice.index,
                                "finish_reason": choice.finish_reason
                            } for choice in response.choices
                        ],
                        "usage": {
                            "prompt_tokens": response.usage.prompt_tokens,
                            "completion_tokens": response.usage.completion_tokens,
                            "total_tokens": response.usage.total_tokens
                        }
                    }
            else:
                # Fallback to direct API call
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "top_p": top_p,
                    "stream": stream,
                    **kwargs
                }
                
                if stop:
                    payload["stop"] = stop
                
                response = self.session.post(
                    f"{self.base_url}/completions",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except (APIError, requests.RequestException) as e:
            logger.error(f"Text completion failed: {e}")
            raise
    
    def embeddings(self,
                  model: str,
                  input: Union[str, List[str]],
                  **kwargs) -> Dict[str, Any]:
        """
        Generate embeddings for text using Vultr Inference
        
        Args:
            model: Model ID to use
            input: Text or list of texts to generate embeddings for
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with embedding data
        """
        self._rate_limit()
        
        try:
            if OPENAI_SDK_AVAILABLE and self.client:
                response = self.client.embeddings.create(
                    model=model,
                    input=input,
                    **kwargs
                )
                
                # Convert to dictionary that matches raw API response
                return {
                    "object": response.object,
                    "data": [
                        {
                            "object": data.object,
                            "embedding": data.embedding,
                            "index": data.index
                        } for data in response.data
                    ],
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            else:
                # Fallback to direct API call
                payload = {
                    "model": model,
                    "input": input,
                    **kwargs
                }
                
                response = self.session.post(
                    f"{self.base_url}/embeddings",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except (APIError, requests.RequestException) as e:
            logger.error(f"Embeddings generation failed: {e}")
            raise
    
    def image_generation(self,
                        model: str,
                        prompt: str,
                        n: int = 1,
                        size: str = "1024x1024",
                        response_format: str = "url",
                        **kwargs) -> Dict[str, Any]:
        """
        Generate images using Vultr Inference
        
        Args:
            model: Model ID to use
            prompt: Text prompt to generate image from
            n: Number of images to generate
            size: Image size (e.g. "1024x1024")
            response_format: Output format ("url" or "b64_json")
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with image data
        """
        self._rate_limit()
        
        try:
            if OPENAI_SDK_AVAILABLE and self.client:
                response = self.client.images.generate(
                    model=model,
                    prompt=prompt,
                    n=n,
                    size=size,
                    response_format=response_format,
                    **kwargs
                )
                
                # Convert to dictionary that matches raw API response
                return {
                    "created": response.created,
                    "data": [
                        {
                            "url": image.url,
                            "b64_json": getattr(image, "b64_json", None),
                            "revised_prompt": getattr(image, "revised_prompt", None)
                        } for image in response.data
                    ]
                }
            else:
                # Fallback to direct API call
                payload = {
                    "model": model,
                    "prompt": prompt,
                    "n": n,
                    "size": size,
                    "response_format": response_format,
                    **kwargs
                }
                
                response = self.session.post(
                    f"{self.base_url}/images/generations",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        except (APIError, requests.RequestException) as e:
            logger.error(f"Image generation failed: {e}")
            raise


class InferenceManager:
    """
    Manager that handles failover between primary (Mikael's WSL) and backup (Vultr) inference.
    Uses OpenAI SDK for both primary and backup endpoints.
    """
    
    def __init__(self, primary_url: Optional[str] = None, primary_key: Optional[str] = None,
                 vultr_url: Optional[str] = None, vultr_key: Optional[str] = None):
        """
        Initialize the Inference Manager with primary and backup endpoints
        
        Args:
            primary_url: URL for primary inference API
            primary_key: API key for primary inference
            vultr_url: URL for Vultr Inference API
            vultr_key: API key for Vultr Inference
        """
        # Check if OpenAI SDK is available
        if not OPENAI_SDK_AVAILABLE:
            logger.warning("OpenAI SDK not available. Inference failover may not work properly.")
        
        # Get configuration for primary inference (Mikael's WSL)
        self.primary_url = primary_url or os.environ.get('PRIMARY_INFERENCE_URL')
        self.primary_key = primary_key or os.environ.get('PRIMARY_INFERENCE_KEY')
        
        # Get configuration for backup inference (Vultr)
        vultr_url = vultr_url or os.environ.get('VULTR_INFERENCE_URL', 'https://api.vultrinference.com/v1')
        vultr_key = vultr_key or os.environ.get('VULTR_INFERENCE_API_KEY')
        
        # Initialize clients
        self.primary_client = None
        if OPENAI_SDK_AVAILABLE and self.primary_url and self.primary_key:
            try:
                self.primary_client = OpenAI(
                    api_key=self.primary_key,
                    base_url=self.primary_url
                )
                logger.info(f"Initialized primary inference client with URL: {self.primary_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize primary inference client: {e}")
        
        # Initialize Vultr client
        self.vultr_client = VultrInferenceClient(vultr_key, vultr_url)
        
        # Failure tracking for primary
        self.primary_failures = 0
        self.primary_last_success = time.time()
        self.failure_threshold = 3
        self.recovery_interval = 300  # 5 minutes
        
        # Set active provider
        self.active_provider = "primary" if self.primary_client else "vultr"
        
        # Load model mappings from environment or use defaults
        self.model_mappings = self._load_model_mappings()
        
        logger.info(f"Inference Manager initialized with active provider: {self.active_provider}")
    
    def _load_model_mappings(self) -> Dict[str, str]:
        """
        Load model mappings from environment or configuration
        
        Returns:
            Dictionary mapping custom model names to provider-specific names
        """
        # Default model mappings
        default_mappings = {
            # Chat models
            "singularity-local": "gpt-3.5-turbo",
            "singularity-large": "gpt-4",
            "mikael-fine-tuned": "gpt-3.5-turbo-16k",
            
            # Embedding models
            "singularity-embeddings": "text-embedding-ada-002"
        }
        
        # Try to load from environment
        mappings_json = os.environ.get('INFERENCE_MODEL_MAPPINGS')
        if mappings_json:
            try:
                return json.loads(mappings_json)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse model mappings from environment: {mappings_json}")
        
        return default_mappings
    
    def _check_primary_health(self) -> bool:
        """
        Check if primary inference is healthy
        
        Returns:
            True if primary is healthy, False otherwise
        """
        if not self.primary_client:
            return False
        
        # Skip health check if we've recently succeeded
        if self.active_provider == "primary":
            return True
        
        # Check if enough time has passed to try primary again
        if time.time() - self.primary_last_success < self.recovery_interval:
            return False
        
        try:
            # Simple health check - list models
            self.primary_client.models.list()
            
            # Reset failure counter on success
            self.primary_failures = 0
            self.primary_last_success = time.time()
            
            logger.info("Primary inference is healthy, switching back")
            self.active_provider = "primary"
            return True
        except Exception as e:
            logger.warning(f"Primary inference health check failed: {e}")
            return False
    
    def _handle_primary_failure(self):
        """Handle failure of primary inference"""
        self.primary_failures += 1
        
        if self.primary_failures >= self.failure_threshold and self.active_provider == "primary":
            logger.warning(f"Primary inference failed {self.primary_failures} times, switching to Vultr")
            self.active_provider = "vultr"
    
    def _map_model_name(self, model: Optional[str], task_type: str = "chat") -> str:
        """
        Map a model name based on the active provider and task type
        
        Args:
            model: Original model name (or None)
            task_type: Type of task (chat, completion, embeddings)
            
        Returns:
            Appropriate model name for the active provider
        """
        if not model:
            # Use defaults by task type
            defaults = {
                "chat": "gpt-3.5-turbo",
                "completion": "text-davinci-003",
                "embeddings": "text-embedding-ada-002",
                "image": "dall-e-3"
            }
            return defaults.get(task_type, "gpt-3.5-turbo")
        
        # If model is in mappings, use the mapped name
        if model in self.model_mappings:
            return self.model_mappings[model]
        
        # If model name already looks like a standard model, use as is
        standard_prefixes = ["gpt-", "llama-", "mixtral-", "mistral-", "text-embedding-", "dall-e"]
        if any(model.startswith(prefix) for prefix in standard_prefixes):
            return model
        
        # Fall back to default for task type
        return self._map_model_name(None, task_type)
    
    def chat_completion(self, messages: List[Dict[str, str]], model: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generate chat completion with automatic failover
        
        Args:
            messages: List of message dictionaries with 'role' and 'content'
            model: Model ID to use (different models may be used for primary vs backup)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with completion data
        """
        # Try primary first if it's active and healthy
        if (self.active_provider == "primary" or self._check_primary_health()) and self.primary_client:
            try:
                # Map model name if needed
                primary_model = self._map_model_name(model, "chat")
                
                # Make request
                response = self.primary_client.chat.completions.create(
                    model=primary_model,
                    messages=messages,
                    **kwargs
                )
                
                # Update success tracking
                self.primary_last_success = time.time()
                self.primary_failures = 0
                self.active_provider = "primary"
                
                # Handle streaming responses
                if kwargs.get('stream', False):
                    return response
                
                # Convert to dictionary that matches the expected format
                return {
                    "id": response.id,
                    "object": response.object,
                    "created": response.created,
                    "model": response.model,
                    "choices": [
                        {
                            "message": {
                                "role": choice.message.role,
                                "content": choice.message.content
                            },
                            "index": choice.index,
                            "finish_reason": choice.finish_reason
                        } for choice in response.choices
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            except Exception as e:
                logger.warning(f"Primary inference request failed: {e}")
                self._handle_primary_failure()
        
        # Use Vultr as backup
        try:
            # Map to Vultr model if needed
            vultr_model = self._map_model_name(model, "chat")
            logger.info(f"Using Vultr inference with model: {vultr_model}")
            
            return self.vultr_client.chat_completion(
                model=vultr_model,
                messages=messages,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Both primary and backup inference failed: {e}")
            raise
    
    def text_completion(self, prompt: str, model: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generate text completion with automatic failover
        
        Args:
            prompt: Text prompt to generate completion for
            model: Model ID to use (different models may be used for primary vs backup)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with completion data
        """
        # Try primary first if it's active and healthy
        if (self.active_provider == "primary" or self._check_primary_health()) and self.primary_client:
            try:
                # Map model name if needed
                primary_model = self._map_model_name(model, "completion")
                
                # Make request
                response = self.primary_client.completions.create(
                    model=primary_model,
                    prompt=prompt,
                    **kwargs
                )
                
                # Update success tracking
                self.primary_last_success = time.time()
                self.primary_failures = 0
                self.active_provider = "primary"
                
                # Handle streaming responses
                if kwargs.get('stream', False):
                    return response
                
                # Convert to dictionary that matches the expected format
                return {
                    "id": response.id,
                    "object": response.object,
                    "created": response.created,
                    "model": response.model,
                    "choices": [
                        {
                            "text": choice.text,
                            "index": choice.index,
                            "finish_reason": choice.finish_reason
                        } for choice in response.choices
                    ],
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            except Exception as e:
                logger.warning(f"Primary inference request failed: {e}")
                self._handle_primary_failure()
        
        # Use Vultr as backup
        try:
            # Map to Vultr model if needed
            vultr_model = self._map_model_name(model, "completion")
            logger.info(f"Using Vultr inference with model: {vultr_model}")
            
            return self.vultr_client.text_completion(
                model=vultr_model,
                prompt=prompt,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Both primary and backup inference failed: {e}")
            raise
    
    def embeddings(self, input: Union[str, List[str]], model: str = None, **kwargs) -> Dict[str, Any]:
        """
        Generate embeddings with automatic failover
        
        Args:
            input: Text or list of texts to generate embeddings for
            model: Model ID to use (different models may be used for primary vs backup)
            **kwargs: Additional parameters to pass to the API
            
        Returns:
            API response with embedding data
        """
        # Try primary first if it's active and healthy
        if (self.active_provider == "primary" or self._check_primary_health()) and self.primary_client:
            try:
                # Map model name if needed
                primary_model = self._map_model_name(model, "embeddings")
                
                # Make request
                response = self.primary_client.embeddings.create(
                    model=primary_model,
                    input=input,
                    **kwargs
                )
                
                # Update success tracking
                self.primary_last_success = time.time()
                self.primary_failures = 0
                self.active_provider = "primary"
                
                # Convert to dictionary that matches the expected format
                return {
                    "object": response.object,
                    "data": [
                        {
                            "object": data.object,
                            "embedding": data.embedding,
                            "index": data.index
                        } for data in response.data
                    ],
                    "model": response.model,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "total_tokens": response.usage.total_tokens
                    }
                }
            except Exception as e:
                logger.warning(f"Primary inference request failed: {e}")
                self._handle_primary_failure()
        
        # Use Vultr as backup
        try:
            # Map to Vultr model if needed
            vultr_model = self._map_model_name(model, "embeddings")
            logger.info(f"Using Vultr inference with model: {vultr_model}")
            
            return self.vultr_client.embeddings(
                model=vultr_model,
                input=input,
                **kwargs
            )
        except Exception as e:
            logger.error(f"Both primary and backup inference failed: {e}")
            raise


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Create inference manager (will use environment variables for configuration)
    inference = InferenceManager()
    
    # Example chat completion
    try:
        result = inference.chat_completion(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "Hello! How does Vultr Cloud Inference work?"}
            ],
            max_tokens=100
        )
        
        print(f"Response: {result['choices'][0]['message']['content']}")
    except Exception as e:
        print(f"Error: {e}")