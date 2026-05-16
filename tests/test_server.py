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
# recipe_prompt() prompt
# ---------------------------------------------------------------------------


from server import recipe_prompt, _detect_prompt_language  # noqa: E402


def _msg_text(msg) -> str:
    """Extract text from a fastmcp Message."""
    return msg.content.text


@pytest.fixture(autouse=True)
def _force_english_prompt(monkeypatch):
    """Pin language detection to English so device/temp assertions work regardless of shell locale."""
    monkeypatch.setenv("LANG", "en_US.UTF-8")
    monkeypatch.delenv("LC_ALL", raising=False)
    monkeypatch.delenv("LC_MESSAGES", raising=False)


def test_recipe_prompt_returns_two_messages(monkeypatch):
    monkeypatch.delenv("COOKIDOO_DEVICE", raising=False)
    result = recipe_prompt()
    assert len(result) == 2
    assert result[0].role == "user"
    assert result[1].role == "assistant"


def test_recipe_prompt_default_device_is_tm6(monkeypatch):
    monkeypatch.delenv("COOKIDOO_DEVICE", raising=False)
    result = recipe_prompt()
    text = _msg_text(result[0])
    assert "TM6" in text
    assert "160" in text


@pytest.mark.parametrize("device,expected_temp", [
    ("TM31", "100"),
    ("TM5", "120"),
    ("TM6", "160"),
    ("TM7", "180"),
])
def test_recipe_prompt_temp_limits_per_device(device, expected_temp, monkeypatch):
    monkeypatch.setenv("COOKIDOO_DEVICE", device)
    result = recipe_prompt()
    text = _msg_text(result[0])
    assert device in text
    assert expected_temp in text


def test_recipe_prompt_unknown_device_defaults_to_160(monkeypatch):
    monkeypatch.setenv("COOKIDOO_DEVICE", "TM99")
    result = recipe_prompt()
    text = _msg_text(result[0])
    assert "160" in text


# ---------------------------------------------------------------------------
# Prompt language detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("env_var,env_value,expected", [
    ("LANG", "en_US.UTF-8", "en"),
    ("LANG", "es_ES.UTF-8", "es"),
    ("LANG", "fr_FR.UTF-8", "fr"),
    ("LANG", "no_NO.UTF-8", "en"),
    ("LANG", "C", "en"),
    ("LC_MESSAGES", "es_ES.UTF-8", "es"),
    ("LC_ALL", "fr_FR.UTF-8", "fr"),
])
def test_detect_prompt_language(env_var, env_value, expected, monkeypatch):
    for k in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv(env_var, env_value)
    assert _detect_prompt_language() == expected


def test_detect_prompt_language_no_env_defaults_to_english(monkeypatch):
    for k in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(k, raising=False)
    assert _detect_prompt_language() == "en"


def test_detect_prompt_language_precedence(monkeypatch):
    monkeypatch.setenv("LANG", "fr_FR.UTF-8")
    monkeypatch.setenv("LC_MESSAGES", "es_ES.UTF-8")
    monkeypatch.setenv("LC_ALL", "en_US.UTF-8")
    assert _detect_prompt_language() == "en"
    monkeypatch.delenv("LC_ALL")
    assert _detect_prompt_language() == "es"
    monkeypatch.delenv("LC_MESSAGES")
    assert _detect_prompt_language() == "fr"


@pytest.mark.parametrize("lang_env,expected_marker", [
    ("en_US.UTF-8", "Hi! I'm your Thermomix"),
    ("es_ES.UTF-8", "¡Hola! Soy tu asistente Thermomix"),
    ("fr_FR.UTF-8", "Bonjour ! Je suis ton assistant Thermomix"),
])
def test_recipe_prompt_dispatches_by_language(lang_env, expected_marker, monkeypatch):
    for k in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LANG", lang_env)
    monkeypatch.delenv("COOKIDOO_DEVICE", raising=False)
    result = recipe_prompt()
    assistant_text = _msg_text(result[1])
    assert expected_marker in assistant_text
