import asyncio
import os
from abc import ABC, abstractmethod

from openhands.agent_server import env_parser
from openhands.app_server.errors import SandboxError
from openhands.app_server.sandbox.sandbox_spec_models import (
    SandboxSpecInfo,
    SandboxSpecInfoPage,
)
from openhands.app_server.services.injector import Injector
from openhands.sdk.utils.models import DiscriminatedUnionMixin

# The version of the agent server to use for deployments.
# Typically this will be the same as the values from the pyproject.toml
AGENT_SERVER_IMAGE = 'ghcr.io/openhands/agent-server:1.21.1-python'


class SandboxSpecService(ABC):
    """Service for managing Sandbox specs.

    At present this is read only. The plan is that later this class will allow building
    and deleting sandbox specs and limiting access by user and group. It would also be
    nice to be able to set the desired number of warm sandboxes for a spec and scale
    this up and down.
    """

    @abstractmethod
    async def search_sandbox_specs(
        self, page_id: str | None = None, limit: int = 100
    ) -> SandboxSpecInfoPage:
        """Search for sandbox specs."""

    @abstractmethod
    async def get_sandbox_spec(self, sandbox_spec_id: str) -> SandboxSpecInfo | None:
        """Get a single sandbox spec, returning None if not found."""

    async def get_default_sandbox_spec(self) -> SandboxSpecInfo:
        """Get the default sandbox spec."""
        page = await self.search_sandbox_specs()
        if not page.items:
            raise SandboxError('No sandbox specs available!')
        return page.items[0]

    async def batch_get_sandbox_specs(
        self, sandbox_spec_ids: list[str]
    ) -> list[SandboxSpecInfo | None]:
        """Get a batch of sandbox specs, returning None for any not found."""
        results = await asyncio.gather(
            *[
                self.get_sandbox_spec(sandbox_spec_id)
                for sandbox_spec_id in sandbox_spec_ids
            ]
        )
        return results


class SandboxSpecServiceInjector(
    DiscriminatedUnionMixin, Injector[SandboxSpecService], ABC
):
    pass


def get_agent_server_image() -> str:
    agent_server_image_repository = os.getenv('AGENT_SERVER_IMAGE_REPOSITORY')
    agent_server_image_tag = os.getenv('AGENT_SERVER_IMAGE_TAG')
    if agent_server_image_repository and agent_server_image_tag:
        return f'{agent_server_image_repository}:{agent_server_image_tag}'
    return AGENT_SERVER_IMAGE


# Prefixes for environment variables that should be auto-forwarded to agent-server
# LLM_* prefix is no longer auto-forwarded; LLM config comes from config.toml
AUTO_FORWARD_PREFIXES = ('LMNR_',)


def get_agent_server_env() -> dict[str, str]:
    """Get environment variables to be injected into agent server sandbox environments.

    This function combines three sources of environment variables:

    1. **LLM config from config.toml**: LLM configuration (model, api_key,
       base_url, etc.) is read from config.toml instead of environment variables.
       This is the primary and preferred source for LLM settings.

    2. **Auto-forwarded variables**: Environment variables with the LMNR_ prefix
       are automatically forwarded to the agent-server container.
       LLM_* prefix forwarding is disabled since LLM config now comes from
       config.toml (source 1 above).

    3. **Explicit overrides via OH_AGENT_SERVER_ENV**: A JSON string that allows
       setting arbitrary environment variables in the agent-server container.
       Values set here take precedence over config.toml and auto-forwarded variables.

    Config sources (in priority order):
        - config.toml [llm] section → LLM_MODEL, LLM_API_KEY, LLM_BASE_URL, etc.
        - LMNR_* env vars → auto-forwarded for Laminar monitoring/analytics
        - OH_AGENT_SERVER_ENV JSON → explicit overrides (highest priority)

    Usage:
        # LLM config is now read from config.toml automatically:
        # [llm]
        # model = "openai/gpt-4"
        # api_key = "sk-xxx"
        # base_url = "https://api.openai.com/v1"

        # Auto-forwarding for Laminar (still from env vars):
        export LMNR_PROJECT_API_KEY=your-api-key
        export LMNR_BASE_URL=https://app.lmnr.ai

        # Explicit override via JSON (takes precedence over all):
        OH_AGENT_SERVER_ENV='{"DEBUG": "true", "CUSTOM_VAR": "value"}'

    Returns:
        dict[str, str]: Dictionary of environment variable names to values.
                       Returns empty dict if no variables are found.

    Raises:
        JSONDecodeError: If OH_AGENT_SERVER_ENV contains invalid JSON.
    """
    result: dict[str, str] = {}

    # Step 1: Load LLM configuration from config.toml (primary source)
    from openhands.app_server.config_toml_loader import get_agent_server_env_from_toml

    toml_llm_env = get_agent_server_env_from_toml()
    result.update(toml_llm_env)

    # Step 2: Auto-forward environment variables with LMNR_ prefix only
    # LLM_* prefix forwarding is replaced by config.toml (Step 1)
    for key, value in os.environ.items():
        if key.startswith('LMNR_'):
            result[key] = value

    # Step 3: Apply explicit overrides from OH_AGENT_SERVER_ENV
    # These take precedence over config.toml and auto-forwarded variables
    explicit_env = env_parser.from_env(dict[str, str], 'OH_AGENT_SERVER_ENV')
    result.update(explicit_env)

    return result
