# Changelog

All notable changes to this project will be documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

---

## [0.2.0.0] — 2026-04-19

### Added

- **`COOKIDOO_VERIFY_SSL` env var** — TLS verification now configurable (default `true`); disabling it no longer requires code changes
- **30-second HTTP timeout** on `aiohttp.ClientSession` — prevents indefinite hangs on flaky networks
- **82-test suite** (up from 54): full coverage of `login()` happy path, `close()`, `get_recipe_details` all branches, `_parse_text_list`, `check_times` validator, reconnect session cleanup, and more
- **`prep_time ≤ total_time` validator** in `CustomRecipe` Pydantic model — rejects recipes where active time exceeds total time
- **Planning feature spec** at `docs/designs/2026-04-18-planificacion-semanal-discovery.md` — full discovery for Phase 5 weekly meal planner (6 new MCP tools + `/semana` prompt + SQLite local DB)
- **`docs/adr/`** with ADRs 0001–0004 committed

### Changed

- `connect_to_cookidoo` closes the previous `aiohttp.ClientSession` before creating a new one (session leak fix)
- `connect_to_cookidoo` resets `_cookidoo_service` and `_cookidoo_api` to `None` in all error paths — stale session references no longer survive a failed reconnect
- `generate_recipe_structure` step parsing now uses `re.sub(r'^\s*\d+\s*[.)]\s*', '', step)` instead of `lstrip('0123456789.)-• ')` — steps like "180°C for 12 min" no longer have their leading digits stripped
- `CookidooService.password` set to `None` after `login()` (replaces `del self.password` — safe for re-authentication on the same instance)
- Repo references updated to `pegardan/thermomix-mcp`

### Fixed

- `_cookidoo_api` no longer holds a closed session reference after a failed reconnect
- Step parsing no longer corrupts steps that start with a digit or temperature value

---

## [0.1.0.0] — 2026-04-18

First tracked release. Built on top of `alexandrepa/mcp-cookidoo` (v0.1.0 upstream).

### Added

- **Phase 1 — Fork setup:** switched dependency from `miaucl/cookidoo-api` to `Mariosd23/cookidoo-api` fork (adds `create_custom_recipe` + `edit_custom_recipe` not yet in upstream v0.17.0)
- **Phase 2 — `cookidoo_service.py` refactor:** replaced ~50 lines of manual HTTP calls (POST + sleep + PATCH) with `CookidooCreateCustomRecipe` from the fork (~5 lines); added `edit_custom_recipe` wrapper
- **Phase 3 — Flexible configuration:** `COOKIDOO_COUNTRY`, `COOKIDOO_LANGUAGE`, `COOKIDOO_DEVICE` now read from `.env`; defaults to `es`, `es-ES`, `TM6`
- **Phase 4 — `/receta` MCP Prompt:** `@mcp.prompt()` in `server.py` exposes the Thermomix recipe conversion workflow in Claude Desktop and Claude Code simultaneously
- **`DEVICE_MAX_TEMP` constant** in `server.py` mapping TM31/TM5/TM6/TM7 to their maximum temperatures (100/120/160/180 °C)
- **`_parse_text_list()` helper** in `server.py` — DRY ingredient/hint parsing (newlines or commas)
- **Test suite:** 54 unit tests across `test_cookidoo_service.py`, `test_schemas.py`, `test_server.py` (pytest + pytest-asyncio)
- **`setup.sh`** — one-command installation script (uv sync + gstack + .env setup)
- **Spec-driven development** with `docs/designs/` and `docs/adr/` structure
- **ADRs 0001–0004:** fork rationale, local SQLite (future), fastmcp ≥3.0, spec-driven dev

### Changed

- `load_cookidoo_credentials()` now returns 5-tuple `(email, password, country, language, device)` (was 2-tuple)
- `CookidooService.__init__` accepts `country`, `language`, `device` with sane defaults
- `create_custom_recipe` return type is now `CookidooCustomRecipe` (was `str`)
- `generate_recipe_structure` uses `_parse_text_list()` for both ingredients and hints
- `upload_custom_recipe` uses `getattr(created, "url", None)` for safe URL access
- `load_dotenv()` moved to module level in `server.py` (was inside `receta()` closure)
- `.env.example` updated with all new variables (`COOKIDOO_COUNTRY`, `COOKIDOO_LANGUAGE`, `COOKIDOO_DEVICE`)
- README rewritten with installation, setup, and configuration instructions

### Fixed

- Removed `time.sleep(5)` in async context — was blocking the entire event loop
- Removed access to `self._api_client._session` (private attribute, fragile across library updates)
- Hardcoded `fr-FR` locale replaced by configurable `COOKIDOO_LANGUAGE`
- Hardcoded `TM6` device replaced by configurable `COOKIDOO_DEVICE`

---

## [0.0.1] — upstream base (`alexandrepa/mcp-cookidoo`)

- Tool `connect_to_cookidoo` — auth with email/password
- Tool `get_recipe_details` — recipe detail by ID
- Tool `generate_recipe_structure` — Pydantic validation
- Tool `upload_custom_recipe` — upload to Cookidoo
