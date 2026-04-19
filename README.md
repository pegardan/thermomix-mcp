# thermomix-mcp

MCP server local para Claude Desktop y Claude Code que convierte cualquier receta (URL, texto o foto) al formato Thermomix y la sube automáticamente a Cookidoo.

> **Aviso:** Proyecto no oficial. No tiene relación con Cookidoo, Vorwerk ni Thermomix.

---

## Qué hace

- Escribe `/receta` en Claude Desktop o Claude Code
- Claude te pregunta qué receta quieres convertir
- Le das una URL, texto pegado o una foto
- Claude convierte al formato Thermomix (pasos, velocidades, temperaturas, ingredientes en gramos)
- Valida la estructura y te la muestra para que la apruebes
- Con tu OK, la sube directamente a tu cuenta de Cookidoo

Compatible con **TM5, TM6, TM7 y TM31**. Soporta `es-ES` por defecto, configurable a pt-PT, fr-FR, de-DE, en-US y más.

---

## Cómo funciona por dentro

El proyecto combina tres piezas:

**1. Servidor MCP** — basado en [`alexandrepa/mcp-cookidoo`](https://github.com/alexandrepa/mcp-cookidoo), con los siguientes fixes y mejoras:
- Auth limpia con email/password desde `.env` (sin cookies manuales)
- Sin `time.sleep` en contexto async
- Tipo de retorno correcto (`CookidooCustomRecipe` en vez de `str`)
- Locale y dispositivo configurables

**2. API de Cookidoo** — usa el fork [`Mariosd23/cookidoo-api`](https://github.com/Mariosd23/cookidoo-api) (PR #179 pendiente contra el oficial), que añade `create_custom_recipe` y `edit_custom_recipe` que el paquete oficial no tiene.

**3. Skill de conversión** — prompt embebido como MCP Prompt (`@mcp.prompt()`), basado en las reglas de [`guimatheus92/cookidoo-recipe-creator`](https://github.com/guimatheus92/cookidoo-recipe-creator):
- Separación estricta: paso de añadir ingredientes ≠ paso de acción de máquina
- Vocabulario correcto por idioma (vel/speed/Stufe/vitesse)
- Límites de temperatura por modelo (TM5 max 120°C, TM6 max 160°C, TM7 max 180°C)
- Formato de ingredientes: `200 g de harina de trigo`, `3 dientes de ajo`

Al declarar el skill como MCP Prompt queda disponible como `/receta` tanto en Claude Desktop como en Claude Code sin configuración adicional.

---

## Instalación

### 1. Clonar y ejecutar setup

```bash
git clone https://github.com/pegardan/thermomix-mcp
cd thermomix-mcp
bash setup.sh
```

El script hace todo de una vez:
- Instala dependencias Python (`uv sync`)
- Clona e instala [gstack](https://github.com/garrytan/gstack) en `~/.claude/skills/gstack` (skills para Claude Code: `/browse`, `/review`, `/ship` y más)
- Instala `bun` si no está disponible (requerido por gstack)
- Crea el `.env` con valores por defecto si no existe

### 2. Editar `.env` con tus credenciales

```env
COOKIDOO_EMAIL=tu@email.com
COOKIDOO_PASSWORD=tupassword
COOKIDOO_COUNTRY=es
COOKIDOO_LANGUAGE=es-ES
COOKIDOO_DEVICE=TM6        # TM5, TM6, TM7 o TM31
COOKIDOO_VERIFY_SSL=true   # false si usas proxy MITM o red corporativa
```

### 3. Registrar en Claude Desktop

Edita `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "thermomix": {
      "command": "/ruta/al/proyecto/thermomix-mcp/.venv/bin/python",
      "args": ["/ruta/al/proyecto/thermomix-mcp/server.py"]
    }
  }
}
```

Reinicia Claude Desktop. El comando `/receta` aparecerá automáticamente.

### 4. Registrar en Claude Code (opcional)

```bash
# En ~/.claude/settings.json añadir el mismo bloque mcpServers
```

O ejecutar en modo desarrollo para probar:

```bash
.venv/bin/python -m fastmcp dev server.py
```

---

## Uso

```
/receta
```

Claude pregunta por la receta. Puedes dar:
- Una URL (`https://www.directoalpaladar.com/...`)
- Texto con ingredientes y pasos pegado directamente
- Una foto del libro de recetas

Claude convierte, valida y espera tu confirmación antes de subir.

---

## Tools MCP disponibles

Además del prompt `/receta`, el server expone estos tools que Claude usa internamente:

| Tool | Descripción |
|---|---|
| `connect_to_cookidoo` | Autentica con tu cuenta (lee credenciales del `.env`) |
| `get_recipe_details` | Obtiene detalles de una receta existente por ID |
| `generate_recipe_structure` | Valida y formatea la receta con Pydantic antes de subir |
| `upload_custom_recipe` | Sube la receta validada a Cookidoo |

---

## Tests

```bash
.venv/bin/python -m pytest tests/ -v
```

82 tests, 0 fallos. Cubren validación Pydantic, lógica del service (con mocks) y los MCP tools vía cliente in-process.

---

## Estado

| Componente | Estado |
|---|---|
| Auth email/password | ✅ |
| create/edit custom recipe | ✅ |
| Skill `/receta` (MCP Prompt) | ✅ |
| Anotaciones INGREDIENT + TTS | ⏳ Fase B |
| Soporte `Mariosd23` PR mergeado | ⏳ pendiente upstream |

---

## Créditos

- [`alexandrepa/mcp-cookidoo`](https://github.com/alexandrepa/mcp-cookidoo) — base del servidor MCP
- [`Mariosd23/cookidoo-api`](https://github.com/Mariosd23/cookidoo-api) — fork con create/edit recipes
- [`miaucl/cookidoo-api`](https://github.com/miaucl/cookidoo-api) — librería Python oficial
- [`guimatheus92/cookidoo-recipe-creator`](https://github.com/guimatheus92/cookidoo-recipe-creator) — reglas de conversión al formato Thermomix

## Licencia

MIT
