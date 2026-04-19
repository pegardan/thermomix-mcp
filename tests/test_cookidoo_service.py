"""Tests for CookidooService and load_cookidoo_credentials."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from cookidoo_service import CookidooService, load_cookidoo_credentials


# ---------------------------------------------------------------------------
# load_cookidoo_credentials
# ---------------------------------------------------------------------------


@patch("cookidoo_service.load_dotenv")
def test_load_credentials_valid(mock_dotenv, monkeypatch):
    monkeypatch.setenv("COOKIDOO_EMAIL", "test@example.com")
    monkeypatch.setenv("COOKIDOO_PASSWORD", "secret")
    monkeypatch.delenv("COOKIDOO_COUNTRY", raising=False)
    monkeypatch.delenv("COOKIDOO_LANGUAGE", raising=False)
    monkeypatch.delenv("COOKIDOO_DEVICE", raising=False)

    email, password, country, language, device = load_cookidoo_credentials()

    assert email == "test@example.com"
    assert password == "secret"
    assert country == "es"
    assert language == "es-ES"
    assert device == "TM6"


@patch("cookidoo_service.load_dotenv")
def test_load_credentials_missing_email_raises(mock_dotenv, monkeypatch):
    monkeypatch.delenv("COOKIDOO_EMAIL", raising=False)
    monkeypatch.setenv("COOKIDOO_PASSWORD", "secret")

    with pytest.raises(ValueError, match="Missing Cookidoo credentials"):
        load_cookidoo_credentials()


@patch("cookidoo_service.load_dotenv")
def test_load_credentials_missing_password_raises(mock_dotenv, monkeypatch):
    monkeypatch.setenv("COOKIDOO_EMAIL", "test@example.com")
    monkeypatch.delenv("COOKIDOO_PASSWORD", raising=False)

    with pytest.raises(ValueError, match="Missing Cookidoo credentials"):
        load_cookidoo_credentials()


@patch("cookidoo_service.load_dotenv")
def test_load_credentials_override_from_env(mock_dotenv, monkeypatch):
    monkeypatch.setenv("COOKIDOO_EMAIL", "user@test.com")
    monkeypatch.setenv("COOKIDOO_PASSWORD", "pass123")
    monkeypatch.setenv("COOKIDOO_COUNTRY", "fr")
    monkeypatch.setenv("COOKIDOO_LANGUAGE", "fr-FR")
    monkeypatch.setenv("COOKIDOO_DEVICE", "TM7")

    email, password, country, language, device = load_cookidoo_credentials()

    assert country == "fr"
    assert language == "fr-FR"
    assert device == "TM7"


# ---------------------------------------------------------------------------
# CookidooService.create_custom_recipe
# ---------------------------------------------------------------------------


async def test_create_recipe_not_authenticated_raises():
    service = CookidooService("email@test.com", "password")
    with pytest.raises(Exception, match="Not authenticated"):
        await service.create_custom_recipe(
            name="Test",
            ingredients=["1 egg"],
            steps=["Cook egg"],
        )


async def test_create_recipe_converts_minutes_to_seconds():
    service = CookidooService("email@test.com", "password", device="TM6")
    mock_api = AsyncMock()
    mock_api.create_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.create_custom_recipe(
        name="Test Recipe",
        ingredients=["100g flour"],
        steps=["Mix flour"],
        prep_time=15,
        total_time=30,
    )

    call_args = mock_api.create_custom_recipe.call_args.args[0]
    assert call_args.active_time == 15 * 60  # 900 seconds
    assert call_args.total_time == 30 * 60  # 1800 seconds


async def test_create_recipe_uses_device_in_tools():
    service = CookidooService("email@test.com", "password", device="TM7")
    mock_api = AsyncMock()
    mock_api.create_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.create_custom_recipe(
        name="Test",
        ingredients=["1 egg"],
        steps=["Cook"],
    )

    call_args = mock_api.create_custom_recipe.call_args.args[0]
    assert call_args.tools == ["TM7"]


async def test_create_recipe_hints_appended_to_instructions():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.create_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    steps = ["Step 1", "Step 2"]
    hints = ["Tip A", "Tip B"]

    await service.create_custom_recipe(
        name="Test",
        ingredients=["1 egg"],
        steps=steps,
        hints=hints,
    )

    call_args = mock_api.create_custom_recipe.call_args.args[0]
    assert call_args.instructions == ["Step 1", "Step 2", "Tip A", "Tip B"]


async def test_create_recipe_no_hints_keeps_steps_only():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.create_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    steps = ["Step 1", "Step 2"]

    await service.create_custom_recipe(
        name="Test",
        ingredients=["1 egg"],
        steps=steps,
        hints=None,
    )

    call_args = mock_api.create_custom_recipe.call_args.args[0]
    assert call_args.instructions == ["Step 1", "Step 2"]


async def test_create_recipe_passes_serving_size():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.create_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.create_custom_recipe(
        name="Test",
        ingredients=["1 egg"],
        steps=["Cook"],
        servings=6,
    )

    call_args = mock_api.create_custom_recipe.call_args.args[0]
    assert call_args.serving_size == 6


# ---------------------------------------------------------------------------
# CookidooService.edit_custom_recipe
# ---------------------------------------------------------------------------


async def test_edit_recipe_not_authenticated_raises():
    service = CookidooService("email@test.com", "password")
    with pytest.raises(Exception, match="Not authenticated"):
        await service.edit_custom_recipe("recipe-123", name="New Name")


async def test_edit_recipe_converts_times_to_seconds():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.edit_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.edit_custom_recipe(
        "recipe-123",
        prep_time=20,
        total_time=40,
    )

    call_args = mock_api.edit_custom_recipe.call_args.args[1]
    assert call_args.active_time == 20 * 60
    assert call_args.total_time == 40 * 60


async def test_edit_recipe_none_times_stay_none():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.edit_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.edit_custom_recipe("recipe-123", name="New Name")

    call_args = mock_api.edit_custom_recipe.call_args.args[1]
    assert call_args.name == "New Name"
    assert call_args.active_time is None
    assert call_args.total_time is None


async def test_edit_recipe_passes_recipe_id():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.edit_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.edit_custom_recipe("my-recipe-id", name="Updated")

    assert mock_api.edit_custom_recipe.call_args.args[0] == "my-recipe-id"


async def test_edit_recipe_passes_optional_fields():
    service = CookidooService("email@test.com", "password")
    mock_api = AsyncMock()
    mock_api.edit_custom_recipe.return_value = MagicMock()
    service._api_client = mock_api

    await service.edit_custom_recipe(
        "recipe-123",
        ingredients=["100g flour", "2 eggs"],
        steps=["Mix", "Bake"],
        servings=8,
    )

    call_args = mock_api.edit_custom_recipe.call_args.args[1]
    assert call_args.ingredients == ["100g flour", "2 eggs"]
    assert call_args.instructions == ["Mix", "Bake"]
    assert call_args.serving_size == 8


# ---------------------------------------------------------------------------
# CookidooService.login — error paths
# ---------------------------------------------------------------------------


@patch("cookidoo_service.aiohttp.TCPConnector")
@patch("cookidoo_service.ClientSession")
@patch("cookidoo_service.get_localization_options", new_callable=AsyncMock)
async def test_login_empty_localizations_raises(mock_get_loc, MockSession, MockConnector):
    mock_get_loc.return_value = []
    mock_session = MagicMock()
    mock_session.close = AsyncMock()
    MockSession.return_value = mock_session

    service = CookidooService("test@test.com", "pass")
    with pytest.raises(Exception, match="Failed to authenticate"):
        await service.login()


@patch("cookidoo_service.aiohttp.TCPConnector")
@patch("cookidoo_service.ClientSession")
@patch("cookidoo_service.get_localization_options", new_callable=AsyncMock)
async def test_login_closes_session_on_exception(mock_get_loc, MockSession, MockConnector):
    mock_get_loc.return_value = []  # triggers ValueError → except → close()
    mock_session = MagicMock()
    mock_session.close = AsyncMock()
    MockSession.return_value = mock_session

    service = CookidooService("test@test.com", "pass")
    with pytest.raises(Exception):
        await service.login()

    mock_session.close.assert_awaited_once()


@patch("cookidoo_service.aiohttp.TCPConnector")
@patch("cookidoo_service.ClientSession")
@patch("cookidoo_service.get_localization_options", new_callable=AsyncMock)
@patch("cookidoo_service.Cookidoo")
async def test_login_happy_path_returns_api(MockCookidoo, mock_get_loc, MockSession, MockConnector):
    mock_localization = MagicMock()
    mock_get_loc.return_value = [mock_localization]
    mock_session = MagicMock()
    MockSession.return_value = mock_session
    mock_api = AsyncMock()
    MockCookidoo.return_value = mock_api

    service = CookidooService("test@test.com", "pass", country="es", language="es-ES")
    result = await service.login()

    mock_api.login.assert_awaited_once()
    assert result is mock_api
    assert service._api_client is mock_api


async def test_close_with_session():
    service = CookidooService("test@test.com", "pass")
    mock_session = MagicMock()
    mock_session.close = AsyncMock()
    service._session = mock_session

    await service.close()

    mock_session.close.assert_awaited_once()


async def test_close_without_session():
    service = CookidooService("test@test.com", "pass")
    service._session = None
    await service.close()  # should not raise


async def test_create_recipe_api_error_propagates():
    service = CookidooService("test@test.com", "pass")
    mock_api = AsyncMock()
    mock_api.create_custom_recipe.side_effect = RuntimeError("API unavailable")
    service._api_client = mock_api

    with pytest.raises(Exception):
        await service.create_custom_recipe(
            name="Test",
            ingredients=["1 egg"],
            steps=["Cook"],
        )


async def test_edit_recipe_api_error_propagates():
    service = CookidooService("test@test.com", "pass")
    mock_api = AsyncMock()
    mock_api.edit_custom_recipe.side_effect = RuntimeError("API unavailable")
    service._api_client = mock_api

    with pytest.raises(Exception):
        await service.edit_custom_recipe("recipe-123", name="New Name")
