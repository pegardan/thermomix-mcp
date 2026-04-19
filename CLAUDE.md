# thermomix-mcp — Contexto del proyecto

## Metodología: Spec-Driven Development

Este proyecto usa **spec-driven development** con gstack. Toda feature de cierta envergadura tiene un spec aprobado antes de implementarse.

### Estructura de documentación

```
docs/
  designs/    # Specs aprobados (output de /office-hours)
  adr/        # Architecture Decision Records (decisiones permanentes)
```

### Reglas para Claude / gstack en cada iteración

1. **Antes de implementar cualquier feature:** verificar si existe un spec en `docs/designs/`. Si no existe, sugerir `/office-hours` primero.
2. **Al aprobar un design doc en `/office-hours`:** copiar el archivo desde `~/.gstack/projects/` a `docs/designs/YYYY-MM-DD-nombre.md` y commitear.
3. **Al tomar una decisión arquitectónica importante** (cambio de dependencia, nueva tecnología, cambio de patrón): crear un ADR en `docs/adr/` con el siguiente número disponible. Leer `docs/adr/` para ver el último número.
4. **Al iniciar una sesión:** leer los specs en `docs/designs/` que sean relevantes al trabajo actual.
5. **`/plan-eng-review`** debe leer `docs/designs/` además de `~/.gstack/projects/` para encontrar el spec del feature a implementar.
6. **`/document-release`** debe actualizar el spec en `docs/designs/` si el feature implementado difiere del spec original.

### Workflow por feature

```
Problema → /office-hours → design doc aprobado → docs/designs/ → commit
                                                        ↓
                                               /plan-eng-review
                                                        ↓
                                               implementación
                                                        ↓
                                               /document-release
```

### ADRs existentes

| # | Título | Status |
|---|--------|--------|
| 0001 | Fork Mariosd23 vs PyPI oficial | Accepted |
| 0002 | SQLite local + Cookidoo source of truth | Accepted |
| 0003 | fastmcp >=3.0.0 | Accepted |
| 0004 | Spec-driven development con gstack | Accepted |

---

## gstack

Use the `/browse` skill from gstack for all web browsing. Never use `mcp__claude-in-chrome__*` tools directly.

Available gstack skills:
`/office-hours`, `/plan-ceo-review`, `/plan-eng-review`, `/plan-design-review`, `/design-consultation`, `/design-shotgun`, `/design-html`, `/review`, `/ship`, `/land-and-deploy`, `/canary`, `/benchmark`, `/browse`, `/connect-chrome`, `/qa`, `/qa-only`, `/design-review`, `/setup-browser-cookies`, `/setup-deploy`, `/retro`, `/investigate`, `/document-release`, `/codex`, `/cso`, `/autoplan`, `/plan-devex-review`, `/devex-review`, `/careful`, `/freeze`, `/guard`, `/unfreeze`, `/gstack-upgrade`, `/learn`

MCP server local para Claude Desktop y Claude Code. Convierte recetas (URL / texto / foto) al formato Thermomix, las sube a Cookidoo y planifica la semana familiar con las recetas aprobadas.

## Objetivo

1. Dar una URL/texto/foto → Claude convierte al formato Thermomix → se sube a Cookidoo
2. Autenticación limpia con email/password en `.env` (sin cookies manuales)
3. Soporte para `es-ES` / cookidoo.es
4. Compatible con TM5, TM6, TM7, TM31
5. Skill `/receta` disponible en Claude Desktop y Claude Code vía MCP Prompt

---

## El ecosistema: 4 repos que interactúan

### 1. `miaucl/cookidoo-api` — librería Python unofficial (v0.17.0 actual)

Maneja auth, recetas, listas de la compra, planificador.

**Lo que SÍ tiene para custom recipes:**
- `get_custom_recipes()` — listado
- `get_custom_recipe(id)` — detalle
- `add_custom_recipe_from(recipeId, servingSize)` — copia una receta existente
- `remove_custom_recipe(id)` — borrar

**Lo que NO tiene:** `create_custom_recipe` ni `edit_custom_recipe` (v0.17.0 salió el 1 abril 2026 sin incluir PR #179).

### 2. `Mariosd23/cookidoo-api` — fork con PR #179 pendiente contra miaucl

**Añade exactamente lo que necesitamos:**

`create_custom_recipe(recipe: CookidooCreateCustomRecipe) → CookidooCustomRecipe`
- POST `created-recipes/{language}` con `{"recipeName": name}` → obtiene `recipe_id`
- PATCH con payload completo (ingredientes, instrucciones, tiempos, herramientas, yield, workStatus)
- GET final devuelve objeto tipado

`edit_custom_recipe(custom_recipe_id, recipe: CookidooEditCustomRecipe) → CookidooCustomRecipe`
- Fetch-merge-patch: obtiene estado actual → aplica campos no-None → PATCH

**Tipos nuevos:** `CookidooCreateCustomRecipe`, `CookidooEditCustomRecipe`, `CookidooInstruction`, `CookidooStepSettings` (tiempo, temperatura, velocidad por paso).

**Estrategia de dependencia:**
```
# Mientras PR #179 esté pendiente (última actividad: 17 abril 2026):
cookidoo-api @ git+https://github.com/Mariosd23/cookidoo-api.git@main

# Cuando PR #179 sea mergeado en miaucl/cookidoo-api Y salga una versión nueva que lo incluya:
cookidoo-api>=0.18.0  # o la versión que corresponda — verificar que incluye create_custom_recipe
```

**Nota:** v0.17.0 ya está en PyPI pero PR #179 NO estaba incluido. No cambiar la dependencia basándose en el número de versión solo — verificar que `Cookidoo` tenga `create_custom_recipe` antes de migrar.

### 3. `alexandrepa/mcp-cookidoo` — base original (crédito)

4 tools MCP originales que sirvieron de punto de partida: `connect_to_cookidoo`, `get_recipe_details`, `generate_recipe_structure`, `upload_custom_recipe`. El proyecto ha evolucionado sustancialmente desde esa base.

**Bugs conocidos en el original que corregimos:**
- `time.sleep(5)` bloqueante en contexto `async` — congela el event loop
- Accede a `self._api_client._session` (atributo privado, frágil)
- Hardcodea `"tools": ["TM6"]`
- Devuelve solo `str` (recipe_id) en vez de objeto tipado
- Localización hardcodeada en `fr-FR`

### 4. `guimatheus92/cookidoo-recipe-creator` — base del skill de conversión

Define las reglas de conversión de recetas al formato Thermomix:
- Separación obligatoria: paso de ingredientes vs. paso de acción de máquina
- Vocabulario por idioma (vel/speed/Stufe/vitesse)
- Límites de temperatura por modelo (TM5 max 120°C, TM6 max 160°C, TM7 max 180°C)
- Formato de ingredientes por idioma ("de" en es/pt/fr, "di" en it, sin preposición en en/de)
- Sistema de anotaciones INGREDIENT + TTS (offset/length) para rendering enriquecido en Cookidoo

**Cómo se integra:** el contenido de `cookidoo-recipe.md` se embebe como MCP Prompt (`@mcp.prompt()`) en `server.py`. Esto lo expone como slash command `/receta` en Claude Desktop y Claude Code sin ninguna configuración adicional.

---

## Arquitectura del skill

### Por qué MCP Prompts y no un fichero de comando

| Mecanismo | Claude Code | Claude Desktop |
|---|---|---|
| `~/.claude/commands/receta.md` | ✅ slash command | ❌ no disponible |
| `@mcp.prompt()` en server.py | ✅ slash command | ✅ slash command |

Al declarar el prompt dentro del MCP server, queda disponible en ambos clientes automáticamente. El usuario escribe `/receta` y Claude pregunta por la receta a convertir.

### Flujo completo

```
Usuario: /receta
Claude pregunta: ¿Qué receta quieres convertir? (URL, texto o foto)
Usuario: https://... o texto pegado
    ↓
Claude aplica reglas de guimatheus92:
  - Separa pasos ingredientes / pasos acción
  - Adapta vocabulario a es-ES
  - Respeta límites del modelo (COOKIDOO_DEVICE)
  - Formatea ingredientes con "de": "200 g de harina de trigo"
    ↓
connect_to_cookidoo (auth email/password desde .env)
    ↓
generate_recipe_structure (valida con Pydantic)
    ↓
Muestra JSON al usuario para confirmación
    ↓  (usuario aprueba)
upload_custom_recipe → URL en cookidoo.es
```

---

## Decisiones de arquitectura

### Qué reemplazamos vs qué mantenemos

| Componente | Decisión |
|---|---|
| `cookidoo_service.py` → `create_custom_recipe` | **Reemplazado** (~50 líneas manuales → ~5 líneas delegando al fork) |
| `cookidoo_service.py` → `edit_custom_recipe` | **Añadido** (gratis con el fork) |
| `server.py` — 4 tools MCP | **Mantenidos** + `@mcp.prompt()` receta |
| `schemas.py` — validación Pydantic | **Mantenido** |
| Lectura de credenciales desde `.env` | **Mantenido** |
| Localización `fr-FR` hardcodeada | **Cambiado** a configurable via `.env` (default `es-ES`) |
| Dispositivo `TM6` hardcodeado | **Cambiado** a configurable via `.env` (default `TM6`) |
| Skill de conversión | **Nuevo** — MCP Prompt basado en guimatheus92 |

### Anotaciones INGREDIENT + TTS: estado actual

El skill de guimatheus92 usa un sistema de anotaciones con offsets de caracteres para que ingredientes y acciones aparezcan en negrita/enlazados en Cookidoo. Nuestro `create_custom_recipe` actual pasa instrucciones como strings planos — funcional pero sin rendering enriquecido.

Pendiente evaluar si `CookidooInstruction` / `CookidooStepSettings` del fork Mariosd23 soporta el formato completo de anotaciones para implementarlo en Fase B.

---

## Plan de implementación

### Fase 1 — Setup del fork ✅
- [x] Base inicial: `alexandrepa/mcp-cookidoo` (proyecto ahora independiente en `pegardan/thermomix-mcp`)
- [x] Cambiar dependencia a `Mariosd23/cookidoo-api`
- [x] Tests unitarios (43 tests, 0 fallos)

### Fase 2 — Refactor de cookidoo_service.py ✅
- [x] Reemplazar bloque manual de `create_custom_recipe`
- [x] Añadir `edit_custom_recipe` wrapper
- [x] Eliminar `time.sleep(5)` y acceso a `_session`
- [x] Tipo de retorno `CookidooCustomRecipe`

### Fase 3 — Configuración flexible ✅
- [x] `COOKIDOO_COUNTRY`, `COOKIDOO_LANGUAGE`, `COOKIDOO_DEVICE` en `.env`
- [x] `CookidooService` lee esas variables

### Fase 4 — MCP Prompt `/receta` ✅
- [x] Añadir `@mcp.prompt()` en `server.py` sin argumentos
- [x] Claude pregunta por la receta al invocar `/receta`
- [x] Embed de reglas guimatheus92: paso-ingrediente / paso-acción, vocabulario es-ES, límites por modelo
- [ ] Registrar MCP server en `claude_desktop_config.json`
- [ ] Verificar slash command en Claude Desktop y Claude Code

### Fase 5 — Anotaciones INGREDIENT + TTS (opcional, Fase B)
- [ ] Evaluar soporte en `CookidooInstruction` del fork Mariosd23
- [ ] Extender `create_custom_recipe` para pasar anotaciones
- [ ] Actualizar prompt para que Claude calcule offsets

---

## Variables de entorno (.env)

```env
COOKIDOO_EMAIL=tu@email.com
COOKIDOO_PASSWORD=tupassword
COOKIDOO_COUNTRY=es               # default: es
COOKIDOO_LANGUAGE=es-ES           # default: es-ES
COOKIDOO_DEVICE=TM6               # opciones: TM5, TM6, TM7, TM31
```

---

## Comandos de desarrollo

```bash
# Instalar dependencias (usando uv)
uv sync

# Ejecutar el servidor MCP en modo desarrollo
.venv/bin/python -m fastmcp dev server.py

# Ejecutar tests
.venv/bin/python -m pytest tests/ -v

# Inspeccionar el servidor con MCP inspector
.venv/bin/python -m fastmcp dev server.py --with-editable .
```

---

## Estado de dependencias externas

| Dependencia | Estado | Acción pendiente |
|---|---|---|
| `Mariosd23/cookidoo-api` PR #179 | Pendiente de merge contra `miaucl/cookidoo-api` | Cuando se apruebe, cambiar a PyPI `cookidoo-api>=0.17.0` |

---

## Referencias

- Repo: https://github.com/pegardan/thermomix-mcp
- Origen (crédito): https://github.com/alexandrepa/mcp-cookidoo
- cookidoo-api oficial: https://github.com/miaucl/cookidoo-api
- Fork con create/edit: https://github.com/Mariosd23/cookidoo-api
- PR #179 (pendiente): https://github.com/miaucl/cookidoo-api/pull/179
- Skill de conversión base: https://github.com/guimatheus92/cookidoo-recipe-creator

## Skill routing

When the user's request matches an available skill, ALWAYS invoke it using the Skill
tool as your FIRST action. Do NOT answer directly, do NOT use other tools first.
The skill has specialized workflows that produce better results than ad-hoc answers.

Key routing rules:
- Product ideas, "is this worth building", brainstorming → invoke office-hours
- Bugs, errors, "why is this broken", 500 errors → invoke investigate
- Ship, deploy, push, create PR → invoke ship
- QA, test the site, find bugs → invoke qa
- Code review, check my diff → invoke review
- Update docs after shipping → invoke document-release
- Weekly retro → invoke retro
- Design system, brand → invoke design-consultation
- Visual audit, design polish → invoke design-review
- Architecture review → invoke plan-eng-review
- Save progress, checkpoint, resume → invoke checkpoint
- Code quality, health check → invoke health
