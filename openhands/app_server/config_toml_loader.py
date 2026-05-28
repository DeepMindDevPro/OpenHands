"""Configuration loader from config.toml.

This module provides a centralized way to read LLM and other configuration
from the project's config.toml file instead of environment variables.

The config.toml path is fixed to: /Users/gechunfa1/Documents/ai-code/OpenHands/config.toml
"""

import logging
from functools import lru_cache
from pathlib import Path

import tomllib

_logger = logging.getLogger(__name__)

# Fixed path to config.toml
CONFIG_TOML_PATH = Path('/Users/gechunfa1/Documents/ai-code/OpenHands/config.toml')


@lru_cache(maxsize=1)
def _load_toml_config() -> dict:
    """Load and cache the config.toml file.

    Returns:
        dict: The parsed TOML configuration, or empty dict if file not found.
    """
    try:
        if CONFIG_TOML_PATH.exists():
            with open(CONFIG_TOML_PATH, 'rb') as f:
                config = tomllib.load(f)
            _logger.info(f'Loaded config from {CONFIG_TOML_PATH}')
            return config
        else:
            _logger.warning(f'config.toml not found at {CONFIG_TOML_PATH}')
            return {}
    except Exception as e:
        _logger.error(f'Error loading config.toml: {e}')
        return {}


def reload_config() -> None:
    """Force reload the config.toml file (clears the cache)."""
    _load_toml_config.cache_clear()


def get_llm_config() -> dict:
    """Get the [llm] section from config.toml.

    Returns:
        dict: The LLM configuration section, or empty dict if not found.
    """
    config = _load_toml_config()
    return config.get('llm', {})


def get_llm_model() -> str | None:
    """Get the LLM model name from config.toml.

    Returns:
        str | None: The model name, or None if not configured.
    """
    return get_llm_config().get('model')


def get_llm_api_key() -> str | None:
    """Get the LLM API key from config.toml.

    Returns:
        str | None: The API key, or None if not configured.
    """
    return get_llm_config().get('api_key')


def get_llm_base_url() -> str | None:
    """Get the LLM base URL from config.toml.

    Returns:
        str | None: The base URL, or None if not configured.
    """
    return get_llm_config().get('base_url')


def get_llm_stream() -> bool | None:
    """Get the LLM stream setting from config.toml.

    Returns:
        bool | None: The stream setting, or None if not configured.
    """
    return get_llm_config().get('stream')


def get_core_config() -> dict:
    """Get the [core] section from config.toml.

    Returns:
        dict: The core configuration section, or empty dict if not found.
    """
    config = _load_toml_config()
    return config.get('core', {})


def get_security_config() -> dict:
    """Get the [security] section from config.toml.

    Returns:
        dict: The security configuration section, or empty dict if not found.
    """
    config = _load_toml_config()
    return config.get('security', {})


def get_agent_server_env_from_toml() -> dict[str, str]:
    """Build LLM-related environment variables from config.toml.

    This replaces the auto-forwarding of LLM_* environment variables
    in sandbox_spec_service.py. Instead of reading from os.environ,
    we read from config.toml and construct the equivalent env vars.

    Returns:
        dict[str, str]: Dictionary of LLM environment variable names to values.
    """
    llm = get_llm_config()
    result: dict[str, str] = {}

    if llm.get('model'):
        result['LLM_MODEL'] = llm['model']
    if llm.get('api_key'):
        result['LLM_API_KEY'] = llm['api_key']
    if llm.get('base_url'):
        result['LLM_BASE_URL'] = llm['base_url']
    if llm.get('stream') is not None:
        result['LLM_STREAM'] = str(llm['stream']).lower()
    if llm.get('timeout'):
        result['LLM_TIMEOUT'] = str(llm['timeout'])
    if llm.get('num_retries'):
        result['LLM_NUM_RETRIES'] = str(llm['num_retries'])
    if llm.get('max_input_tokens'):
        result['LLM_MAX_INPUT_TOKENS'] = str(llm['max_input_tokens'])
    if llm.get('max_output_tokens'):
        result['LLM_MAX_OUTPUT_TOKENS'] = str(llm['max_output_tokens'])
    if llm.get('temperature') is not None:
        result['LLM_TEMPERATURE'] = str(llm['temperature'])
    if llm.get('top_p') is not None:
        result['LLM_TOP_P'] = str(llm['top_p'])
    if llm.get('custom_llm_provider'):
        result['LLM_CUSTOM_LLM_PROVIDER'] = llm['custom_llm_provider']

    return result
