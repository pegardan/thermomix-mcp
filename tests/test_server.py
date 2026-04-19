"""Tests for MCP server tools via in-process FastMCP Client."""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Client

import server
from server import mcp


def _get_text(result) -> str:
    """Extract text from a CallToolResult."""
    return result.content[0].text


# ---------------------------------------------------------------------------
# generate_recipe_structure
# ---------------------------------------------------------------------------


async def test_generate_recipe_newline_ingredients():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "Pasta",
                "ingredients": "200g pasta\n100ml sauce\n1 onion",
                "steps": "Boil water\nCook pasta",
            },
        )
    text = _get_text(result)
    assert "validated successfully" in text
    data = json.loads(text.split("validated successfully!\n\n")[1].split("\n\nYou")[0])
    assert len(data["ingredients"]) == 3
    assert data["ingredients"][0] == "200g pasta"


async def test_generate_recipe_comma_ingredients():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "Salad",
                "ingredients": "lettuce,tomato,olive oil",
                "steps": "Mix everything",
            },
        )
    text = _get_text(result)
    assert "validated successfully" in text
    data = json.loads(text.split("validated successfully!\n\n")[1].split("\n\nYou")[0])
    assert len(data["ingredients"]) == 3
    assert "lettuce" in data["ingredients"]


async def test_generate_recipe_numbered_steps_stripped():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "Cake",
                "ingredients": "flour,eggs",
                "steps": "1. Mix ingredients\n2. Bake at 180°C\n3. Let cool",
            },
        )
    text = _get_text(result)
    assert "validated successfully" in text
    data = json.loads(text.split("validated successfully!\n\n")[1].split("\n\nYou")[0])
    assert data["steps"][0] == "Mix ingredients"
    assert data["steps"][1] == "Bake at 180°C"
    assert data["steps"][2] == "Let cool"


async def test_generate_recipe_hints_parsed():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "Cookies",
                "ingredients": "flour,butter",
                "steps": "Mix\nBake",
                "hints": "Don't overmix\nLet cool before eating",
            },
        )
    text = _get_text(result)
    assert "validated successfully" in text
    data = json.loads(text.split("validated successfully!\n\n")[1].split("\n\nYou")[0])
    assert data["hints"] is not None
    assert len(data["hints"]) == 2


async def test_generate_recipe_servings_out_of_range_returns_error():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "Party Food",
                "ingredients": "1 egg",
                "steps": "Cook",
                "servings": 25,
            },
        )
    text = _get_text(result)
    assert "Validation failed" in text


async def test_generate_recipe_empty_name_returns_error():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "",
                "ingredients": "1 egg",
                "steps": "Cook",
            },
        )
    text = _get_text(result)
    assert "Validation failed" in text


# ---------------------------------------------------------------------------
# upload_custom_recipe
# ---------------------------------------------------------------------------


async def test_upload_recipe_not_connected_returns_message(monkeypatch):
    monkeypatch.setattr(server, "_cookidoo_service", None)
    monkeypatch.setattr(server, "_cookidoo_api", None)

    async with Client(mcp) as client:
        result = await client.call_tool(
            "upload_custom_recipe",
            {"recipe_json": '{"name": "Test", "ingredients": ["egg"], "steps": ["cook"]}'},
        )
    text = _get_text(result)
    assert "Not connected" in text


async def test_upload_recipe_invalid_json_returns_message(monkeypatch):
    monkeypatch.setattr(server, "_cookidoo_service", MagicMock())
    monkeypatch.setattr(server, "_cookidoo_api", MagicMock())

    async with Client(mcp) as client:
        result = await client.call_tool(
            "upload_custom_recipe",
            {"recipe_json": "not valid json at all"},
        )
    text = _get_text(result)
    assert "Invalid JSON" in text


async def test_upload_recipe_success_returns_id_and_url(monkeypatch):
    mock_created = MagicMock()
    mock_created.name = "Cookies"
    mock_created.id = "abc123"
    mock_created.url = "https://cookidoo.es/recipes/abc123"

    mock_service = MagicMock()
    mock_service.create_custom_recipe = AsyncMock(return_value=mock_created)

    monkeypatch.setattr(server, "_cookidoo_service", mock_service)
    monkeypatch.setattr(server, "_cookidoo_api", MagicMock())

    recipe_json = json.dumps(
        {
            "name": "Cookies",
            "ingredients": ["200g flour", "100g butter"],
            "steps": ["Mix", "Bake"],
        }
    )
    async with Client(mcp) as client:
        result = await client.call_tool(
            "upload_custom_recipe",
            {"recipe_json": recipe_json},
        )
    text = _get_text(result)
    assert "abc123" in text
    assert "Cookies" in text
    assert "https://cookidoo.es/recipes/abc123" in text


async def test_upload_recipe_invalid_recipe_data_returns_message(monkeypatch):
    monkeypatch.setattr(server, "_cookidoo_service", MagicMock())
    monkeypatch.setattr(server, "_cookidoo_api", MagicMock())

    # Valid JSON but missing required fields
    async with Client(mcp) as client:
        result = await client.call_tool(
            "upload_custom_recipe",
            {"recipe_json": '{"name": "test"}'},
        )
    text = _get_text(result)
    assert "Invalid recipe data" in text


# ---------------------------------------------------------------------------
# connect_to_cookidoo
# ---------------------------------------------------------------------------


@patch("cookidoo_service.load_dotenv")
async def test_connect_missing_credentials_returns_error(mock_dotenv, monkeypatch):
    monkeypatch.delenv("COOKIDOO_EMAIL", raising=False)
    monkeypatch.delenv("COOKIDOO_PASSWORD", raising=False)

    async with Client(mcp) as client:
        result = await client.call_tool("connect_to_cookidoo", {})
    text = _get_text(result)
    assert "Configuration Error" in text


@patch("cookidoo_service.load_dotenv")
@patch("server.CookidooService")
async def test_connect_passes_country_language_device(MockService, mock_dotenv, monkeypatch):
    monkeypatch.setenv("COOKIDOO_EMAIL", "user@test.com")
    monkeypatch.setenv("COOKIDOO_PASSWORD", "pass")
    monkeypatch.setenv("COOKIDOO_COUNTRY", "fr")
    monkeypatch.setenv("COOKIDOO_LANGUAGE", "fr-FR")
    monkeypatch.setenv("COOKIDOO_DEVICE", "TM5")

    mock_instance = AsyncMock()
    mock_instance.login = AsyncMock(return_value=MagicMock())
    MockService.return_value = mock_instance

    async with Client(mcp) as client:
        await client.call_tool("connect_to_cookidoo", {})
    MockService.assert_called_once_with(
        "user@test.com", "pass", "fr", "fr-FR", "TM5"
    )


@patch("cookidoo_service.load_dotenv")
@patch("server.CookidooService")
async def test_connect_success_returns_message(MockService, mock_dotenv, monkeypatch):
    monkeypatch.setenv("COOKIDOO_EMAIL", "user@test.com")
    monkeypatch.setenv("COOKIDOO_PASSWORD", "pass")
    monkeypatch.setenv("COOKIDOO_COUNTRY", "es")
    monkeypatch.setenv("COOKIDOO_LANGUAGE", "es-ES")
    monkeypatch.setenv("COOKIDOO_DEVICE", "TM6")

    mock_instance = AsyncMock()
    mock_instance.login = AsyncMock(return_value=MagicMock())
    MockService.return_value = mock_instance

    async with Client(mcp) as client:
        result = await client.call_tool("connect_to_cookidoo", {})
    text = _get_text(result)
    assert "Successfully connected" in text
    assert "user@test.com" in text


# ---------------------------------------------------------------------------
# receta() prompt
# ---------------------------------------------------------------------------


from server import receta as receta_prompt  # noqa: E402


def _msg_text(msg) -> str:
    """Extract text from a fastmcp Message."""
    return msg.content.text


def test_receta_returns_two_messages(monkeypatch):
    monkeypatch.delenv("COOKIDOO_DEVICE", raising=False)
    result = receta_prompt()
    assert len(result) == 2
    assert result[0].role == "user"
    assert result[1].role == "assistant"


def test_receta_default_device_is_tm6(monkeypatch):
    monkeypatch.delenv("COOKIDOO_DEVICE", raising=False)
    result = receta_prompt()
    text = _msg_text(result[0])
    assert "TM6" in text
    assert "160" in text


@pytest.mark.parametrize("device,expected_temp", [
    ("TM31", "100"),
    ("TM5", "120"),
    ("TM6", "160"),
    ("TM7", "180"),
])
def test_receta_temp_limits_per_device(device, expected_temp, monkeypatch):
    monkeypatch.setenv("COOKIDOO_DEVICE", device)
    result = receta_prompt()
    text = _msg_text(result[0])
    assert device in text
    assert expected_temp in text


def test_receta_unknown_device_defaults_to_160(monkeypatch):
    monkeypatch.setenv("COOKIDOO_DEVICE", "TM99")
    result = receta_prompt()
    text = _msg_text(result[0])
    assert "160" in text


# ---------------------------------------------------------------------------
# connect_to_cookidoo — exception path
# ---------------------------------------------------------------------------


@patch("cookidoo_service.load_dotenv")
@patch("server.CookidooService")
async def test_connect_non_value_error_returns_connection_failed(MockService, mock_dotenv, monkeypatch):
    monkeypatch.setenv("COOKIDOO_EMAIL", "user@test.com")
    monkeypatch.setenv("COOKIDOO_PASSWORD", "pass")
    monkeypatch.setenv("COOKIDOO_COUNTRY", "es")
    monkeypatch.setenv("COOKIDOO_LANGUAGE", "es-ES")
    monkeypatch.setenv("COOKIDOO_DEVICE", "TM6")

    mock_instance = AsyncMock()
    mock_instance.login.side_effect = RuntimeError("network error")
    MockService.return_value = mock_instance

    async with Client(mcp) as client:
        result = await client.call_tool("connect_to_cookidoo", {})
    text = _get_text(result)
    assert "Connection Failed" in text


# ---------------------------------------------------------------------------
# get_recipe_details
# ---------------------------------------------------------------------------


async def test_get_recipe_details_not_connected(monkeypatch):
    monkeypatch.setattr(server, "_cookidoo_api", None)

    async with Client(mcp) as client:
        result = await client.call_tool("get_recipe_details", {"recipe_id": "r123"})
    text = _get_text(result)
    assert "Not connected" in text


async def test_get_recipe_details_happy_path(monkeypatch):
    mock_recipe = MagicMock()
    mock_recipe.name = "Tortilla española"
    mock_recipe.id = "r99999"
    mock_recipe.serving_size = 4
    mock_recipe.total_time = 30
    mock_recipe.difficulty = "easy"
    mock_ingredient = MagicMock()
    mock_ingredient.name = "6 eggs"
    mock_ingredient.quantity = None
    mock_recipe.ingredients = [mock_ingredient]
    mock_step = MagicMock()
    mock_step.description = "Beat eggs"
    mock_recipe.steps = [mock_step]
    mock_recipe.url = "https://cookidoo.es/recipes/r99999"

    mock_api = AsyncMock()
    mock_api.get_recipe_details.return_value = mock_recipe
    monkeypatch.setattr(server, "_cookidoo_api", mock_api)

    async with Client(mcp) as client:
        result = await client.call_tool("get_recipe_details", {"recipe_id": "r99999"})
    text = _get_text(result)
    assert "Tortilla española" in text
    assert "r99999" in text
    assert "6 eggs" in text
    assert "Beat eggs" in text
    assert "https://cookidoo.es/recipes/r99999" in text


async def test_get_recipe_details_missing_optional_attrs(monkeypatch):
    mock_recipe = MagicMock(spec=["name", "id"])
    mock_recipe.name = "Simple Dish"
    mock_recipe.id = "r00001"

    mock_api = AsyncMock()
    mock_api.get_recipe_details.return_value = mock_recipe
    monkeypatch.setattr(server, "_cookidoo_api", mock_api)

    async with Client(mcp) as client:
        result = await client.call_tool("get_recipe_details", {"recipe_id": "r00001"})
    text = _get_text(result)
    assert "Simple Dish" in text
    assert "r00001" in text


async def test_get_recipe_details_exception(monkeypatch):
    mock_api = AsyncMock()
    mock_api.get_recipe_details.side_effect = RuntimeError("not found")
    monkeypatch.setattr(server, "_cookidoo_api", mock_api)

    async with Client(mcp) as client:
        result = await client.call_tool("get_recipe_details", {"recipe_id": "r_bad"})
    text = _get_text(result)
    assert "Failed to get recipe details" in text


# ---------------------------------------------------------------------------
# generate_recipe_structure — edge cases
# ---------------------------------------------------------------------------


async def test_generate_recipe_empty_hints_results_in_no_hints():
    async with Client(mcp) as client:
        result = await client.call_tool(
            "generate_recipe_structure",
            {
                "name": "Salad",
                "ingredients": "lettuce,tomato",
                "steps": "Mix everything",
                "hints": "",
            },
        )
    text = _get_text(result)
    assert "validated successfully" in text
    data = json.loads(text.split("validated successfully!\n\n")[1].split("\n\nYou")[0])
    assert data["hints"] is None


# ---------------------------------------------------------------------------
# upload_custom_recipe — edge cases
# ---------------------------------------------------------------------------


async def test_upload_recipe_url_none_shows_na(monkeypatch):
    mock_created = MagicMock()
    mock_created.name = "No-URL Recipe"
    mock_created.id = "xyz789"
    mock_created.url = None

    mock_service = MagicMock()
    mock_service.create_custom_recipe = AsyncMock(return_value=mock_created)

    monkeypatch.setattr(server, "_cookidoo_service", mock_service)
    monkeypatch.setattr(server, "_cookidoo_api", MagicMock())

    recipe_json = json.dumps(
        {"name": "No-URL Recipe", "ingredients": ["1 egg"], "steps": ["Cook"]}
    )
    async with Client(mcp) as client:
        result = await client.call_tool("upload_custom_recipe", {"recipe_json": recipe_json})
    text = _get_text(result)
    assert "N/A" in text
    assert "xyz789" in text


async def test_upload_recipe_create_raises_returns_error(monkeypatch):
    mock_service = MagicMock()
    mock_service.create_custom_recipe = AsyncMock(side_effect=RuntimeError("API error"))

    monkeypatch.setattr(server, "_cookidoo_service", mock_service)
    monkeypatch.setattr(server, "_cookidoo_api", MagicMock())

    recipe_json = json.dumps(
        {"name": "Fail Recipe", "ingredients": ["1 egg"], "steps": ["Cook"]}
    )
    async with Client(mcp) as client:
        result = await client.call_tool("upload_custom_recipe", {"recipe_json": recipe_json})
    text = _get_text(result)
    assert "Upload failed" in text
