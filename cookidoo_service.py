"""
Cookidoo Service

Module to encapsulate all cookidoo-api logic for interacting with the Cookidoo platform.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from aiohttp import ClientSession
from cookidoo_api import Cookidoo, CookidooConfig, CookidooCreateCustomRecipe, CookidooEditCustomRecipe
from cookidoo_api.types import CookidooCustomRecipe
from cookidoo_api.helpers import get_localization_options
import aiohttp


def load_cookidoo_credentials() -> tuple[str, str, str, str, str]:
    """
    Load Cookidoo credentials and configuration from .env file.

    Returns:
        tuple[str, str, str, str, str]: email, password, country, language, device

    Raises:
        ValueError: If credentials are not found in environment variables
    """
    load_dotenv()

    email = os.getenv("COOKIDOO_EMAIL")
    password = os.getenv("COOKIDOO_PASSWORD")

    if not email or not password:
        raise ValueError(
            "Missing Cookidoo credentials. Please set COOKIDOO_EMAIL and "
            "COOKIDOO_PASSWORD in your .env file"
        )

    country = os.getenv("COOKIDOO_COUNTRY", "es")
    language = os.getenv("COOKIDOO_LANGUAGE", "es-ES")
    device = os.getenv("COOKIDOO_DEVICE", "TM6")

    return email, password, country, language, device


class CookidooService:
    """Service class for managing Cookidoo API interactions."""

    def __init__(self, email: str, password: str, country: str = "es", language: str = "es-ES", device: str = "TM6"):
        """
        Args:
            email: Cookidoo account email.
            password: Cookidoo account password.
            country: Country code for localization (default: "es").
            language: Language code for localization (default: "es-ES").
            device: Thermomix model identifier (default: "TM6").
        """
        self.email = email
        self.password = password
        self.country = country
        self.language = language
        self.device = device
        self._api_client: Optional[Cookidoo] = None
        self._session: Optional[ClientSession] = None

    async def login(self) -> Cookidoo:
        """
        Authenticate with Cookidoo and return the API client.

        Raises:
            Exception: If authentication fails
        """
        try:
            verify_ssl = os.getenv("COOKIDOO_VERIFY_SSL", "true").lower() != "false"
            timeout = aiohttp.ClientTimeout(total=30)
            self._session = ClientSession(
                connector=aiohttp.TCPConnector(verify_ssl=verify_ssl),
                timeout=timeout,
            )

            localizations = await get_localization_options(country=self.country, language=self.language)
            if not localizations:
                raise ValueError(f"No localization found for country='{self.country}', language='{self.language}'")

            config = CookidooConfig(
                email=self.email,
                password=self.password,
                localization=localizations[0],
            )
            del self.password

            self._api_client = Cookidoo(session=self._session, cfg=config)
            await self._api_client.login()

            return self._api_client

        except Exception as e:
            if self._session:
                await self._session.close()
            raise Exception(f"Failed to authenticate with Cookidoo: {str(e)}") from e

    async def close(self) -> None:
        """Close the aiohttp session."""
        if self._session:
            await self._session.close()

    async def create_custom_recipe(
        self,
        name: str,
        ingredients: list[str],
        steps: list[str],
        servings: int = 4,
        prep_time: int = 30,
        total_time: int = 60,
        hints: Optional[list[str]] = None,
    ) -> CookidooCustomRecipe:
        """
        Create a new custom recipe from scratch.

        Args:
            name: Recipe name
            ingredients: List of ingredient descriptions
            steps: List of cooking step descriptions
            servings: Number of servings (default: 4)
            prep_time: Preparation time in minutes (default: 30)
            total_time: Total cooking time in minutes (default: 60)
            hints: Optional list of tips appended as additional instructions

        Returns:
            CookidooCustomRecipe: The created recipe object

        Raises:
            Exception: If not authenticated or if recipe creation fails
        """
        if not self._api_client:
            raise Exception("Not authenticated. Please call login() first.")

        # Append hints as additional instructions if provided
        all_steps = steps + hints if hints else steps

        recipe = CookidooCreateCustomRecipe(
            name=name,
            ingredients=ingredients,
            instructions=all_steps,
            serving_size=servings,
            active_time=prep_time * 60,   # minutes → seconds
            total_time=total_time * 60,   # minutes → seconds
            tools=[self.device],
        )

        return await self._api_client.create_custom_recipe(recipe)

    async def edit_custom_recipe(
        self,
        custom_recipe_id: str,
        name: Optional[str] = None,
        ingredients: Optional[list[str]] = None,
        steps: Optional[list[str]] = None,
        servings: Optional[int] = None,
        prep_time: Optional[int] = None,
        total_time: Optional[int] = None,
    ) -> CookidooCustomRecipe:
        """
        Edit an existing custom recipe (partial update — only provided fields change).

        Args:
            custom_recipe_id: ID of the recipe to edit
            name: New recipe name (optional)
            ingredients: New ingredients list (optional)
            steps: New instructions list (optional)
            servings: New serving size (optional)
            prep_time: New preparation time in minutes (optional)
            total_time: New total time in minutes (optional)

        Returns:
            CookidooCustomRecipe: The updated recipe object
        """
        if not self._api_client:
            raise Exception("Not authenticated. Please call login() first.")

        recipe = CookidooEditCustomRecipe(
            name=name,
            ingredients=ingredients,
            instructions=steps,
            serving_size=servings,
            active_time=prep_time * 60 if prep_time is not None else None,
            total_time=total_time * 60 if total_time is not None else None,
        )

        return await self._api_client.edit_custom_recipe(custom_recipe_id, recipe)

    @property
    def api_client(self) -> Optional[Cookidoo]:
        """Get the current API client instance."""
        return self._api_client
