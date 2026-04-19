"""
Cookidoo MCP Server

Main server file containing MCP tool definitions for interacting with Cookidoo.
"""

import os
import re
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.prompts import Message
from cookidoo_service import CookidooService, load_cookidoo_credentials
from schemas import CustomRecipe
import json

load_dotenv()

# Temperature limits (°C) per Thermomix model
DEVICE_MAX_TEMP: dict[str, int] = {
    "TM31": 100,
    "TM5": 120,
    "TM6": 160,
    "TM7": 180,
}

# Initialize FastMCP server
mcp = FastMCP("cookidoo-mcp-server")

# Module-level state to store the authenticated session
_cookidoo_service: CookidooService | None = None
_cookidoo_api = None


@mcp.tool()
async def connect_to_cookidoo() -> str:
    """
    Authenticate with Cookidoo and store the session.
    
    This tool must be called before using other Cookidoo tools. It will:
    1. Load your Cookidoo credentials from the .env file
    2. Authenticate with the Cookidoo platform
    3. Store the authenticated session for use by other tools
        
    Returns:
        str: Success message confirming connection
        
    Raises:
        ValueError: If credentials are missing from .env file
        Exception: If authentication fails
    """
    global _cookidoo_service, _cookidoo_api

    try:
        if _cookidoo_service:
            await _cookidoo_service.close()
        _cookidoo_service = None
        _cookidoo_api = None

        # Load credentials and configuration from .env file
        email, password, country, language, device = load_cookidoo_credentials()

        # Create Cookidoo service instance
        _cookidoo_service = CookidooService(email, password, country, language, device)

        # Authenticate and get API client
        _cookidoo_api = await _cookidoo_service.login()

        return f"Successfully connected to Cookidoo as {email}"

    except ValueError as e:
        _cookidoo_service = None
        _cookidoo_api = None
        return f"Configuration Error: {str(e)}\n\nPlease ensure your .env file contains COOKIDOO_EMAIL and COOKIDOO_PASSWORD"

    except Exception as e:
        _cookidoo_service = None
        _cookidoo_api = None
        return f"Connection Failed: {str(e)}\n\nPlease check your credentials and try again."


@mcp.tool()
async def get_recipe_details(recipe_id: str) -> str:
    """
    Get detailed information about a specific recipe by its ID.
    
    Use this tool to get full details about a recipe for inspiration before creating
    your own custom recipe. You must be connected first using connect_to_cookidoo.
    
    Args:
        recipe_id: The Cookidoo recipe ID (e.g., "r59322", "r907015")
        
    Returns:
        str: Detailed recipe information including ingredients, steps, cooking time, etc.
        
    Raises:
        Exception: If not connected or if the recipe is not found
    """
    global _cookidoo_api
    
    try:
        # Check if connected
        if not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        
        # Get recipe details
        recipe = await _cookidoo_api.get_recipe_details(recipe_id)
        
        # Format the results
        result = "Recipe Details:\n\n"
        result += f"Name: {recipe.name}\n"
        result += f"ID: {recipe.id}\n\n"
        
        if hasattr(recipe, 'serving_size'):
            result += f"Servings: {recipe.serving_size}\n"
        
        if hasattr(recipe, 'total_time'):
            result += f"Total Time: {recipe.total_time} minutes\n"
        
        if hasattr(recipe, 'difficulty'):
            result += f"Difficulty: {recipe.difficulty}\n"
        
        result += "\n"
        
        # Ingredients
        if hasattr(recipe, 'ingredients') and recipe.ingredients:
            result += "Ingredients:\n"
            for ingredient in recipe.ingredients:
                if hasattr(ingredient, 'name'):
                    result += f"  • {ingredient.name}"
                    if hasattr(ingredient, 'quantity') and ingredient.quantity:
                        result += f" - {ingredient.quantity}"
                    result += "\n"
            result += "\n"
        
        # Steps
        if hasattr(recipe, 'steps') and recipe.steps:
            result += "Steps:\n"
            for i, step in enumerate(recipe.steps, 1):
                if hasattr(step, 'description'):
                    result += f"{i}. {step.description}\n"
            result += "\n"
        
        # URL if available
        if hasattr(recipe, 'url') and recipe.url:
            result += f"URL: {recipe.url}\n"
        
        return result
        
    except Exception as e:
        return f"Failed to get recipe details: {str(e)}"


def _parse_text_list(text: str) -> list[str]:
    """Split a text block into a list, by newlines if present, else by commas."""
    return [item.strip() for item in (text.split('\n') if '\n' in text else text.split(',')) if item.strip()]


@mcp.tool()
async def generate_recipe_structure(
    name: str,
    ingredients: str,
    steps: str,
    servings: int = 4,
    prep_time: int = 30,
    total_time: int = 60,
    hints: str = "",
) -> str:
    """
    Generate and validate a recipe structure ready for upload to Cookidoo.
    
    This tool helps you structure your recipe data properly before uploading.
    It validates all fields and returns a JSON structure that can be used with
    the upload_custom_recipe tool.
    
    Args:
        name: Recipe name (required)
        ingredients: Ingredients list, one per line or comma-separated
        steps: Cooking steps, one per line or numbered
        servings: Number of servings (default: 4, range: 1-20)
        prep_time: Preparation time in minutes (default: 30)
        total_time: Total cooking time in minutes (default: 60)
        hints: Optional cooking tips, one per line or comma-separated
        
    Returns:
        str: Validated recipe structure in JSON format, ready for upload
    """
    try:
        # Parse ingredients (split by newlines or commas)
        ingredients_list = _parse_text_list(ingredients)

        # Parse steps (split by newlines or numbered steps)
        steps_list = [
            re.sub(r'^\s*\d+\s*[.)]\s*', '', step).strip()
            for step in steps.split('\n')
            if step.strip()
        ]

        # Parse hints if provided
        hints_list = _parse_text_list(hints) if hints else None
        
        # Create and validate the recipe using Pydantic
        recipe = CustomRecipe(
            name=name,
            ingredients=ingredients_list,
            steps=steps_list,
            servings=servings,
            prep_time=prep_time,
            total_time=total_time,
            hints=hints_list
        )
        
        # Return formatted JSON
        recipe_json = recipe.model_dump_json(indent=2)
        
        return f"Recipe structure validated successfully!\n\n{recipe_json}\n\nYou can now use this with 'upload_custom_recipe'."
        
    except Exception as e:
        return f"Validation failed: {str(e)}\n\nPlease check your recipe data and try again."


@mcp.tool()
async def upload_custom_recipe(recipe_json: str) -> str:
    """
    Upload a custom recipe to your Cookidoo account.
    
    This tool creates a brand new recipe from scratch on your Cookidoo account.
    Use 'generate_recipe_structure' first to validate your recipe data, then
    pass the resulting JSON to this tool.
    
    Args:
        recipe_json: The validated recipe JSON from generate_recipe_structure
        
    Returns:
        str: Success message with the created recipe ID
    """
    global _cookidoo_service, _cookidoo_api
    
    try:
        # Check if connected
        if not _cookidoo_service or not _cookidoo_api:
            return "Not connected. Please run 'connect_to_cookidoo' first."
        
        # Parse and validate the recipe JSON
        try:
            recipe_data = json.loads(recipe_json)
            recipe = CustomRecipe(**recipe_data)
        except json.JSONDecodeError as e:
            return f"Invalid JSON: {str(e)}"
        except Exception as e:
            return f"Invalid recipe data: {str(e)}"
        
        # Create the recipe using the cookidoo-api client
        created = await _cookidoo_service.create_custom_recipe(
            name=recipe.name,
            ingredients=recipe.ingredients,
            steps=recipe.steps,
            servings=recipe.servings,
            prep_time=recipe.prep_time,
            total_time=recipe.total_time,
            hints=recipe.hints
        )

        recipe_url = getattr(created, "url", None) or "N/A"
        return f"Recipe '{created.name}' created successfully!\n\nRecipe ID: {created.id}\nURL: {recipe_url}\n\nYour recipe is now saved in your Cookidoo account!"
        
    except Exception as e:
        return f"Upload failed: {str(e)}"


@mcp.prompt()
def receta() -> list[Message]:
    """Convierte una receta al formato Thermomix y la sube a Cookidoo"""
    device = os.getenv("COOKIDOO_DEVICE", "TM6")
    max_temp = DEVICE_MAX_TEMP.get(device, 160)

    instructions = f"""Eres un asistente culinario experto en Thermomix. Tu misión es convertir cualquier receta \
(desde una URL, texto pegado o foto) al formato Thermomix y subirla a Cookidoo.

El dispositivo configurado es **{device}** (temperatura máxima: {max_temp}°C). \
Si la receta original requiere temperaturas superiores, adapta el paso indicando usar el horno.

---

## REGLAS DE CONVERSIÓN (obligatorias)

### Regla 1 — Separar ingredientes de acciones de máquina

Cada paso que añade ingredientes y cada acción de máquina deben ser pasos separados.

MAL (un solo paso):
> "Añade 200 g de harina de trigo y 3 g de sal. Mezcla 5 seg/vel 4."

BIEN (dos pasos):
> Paso N: "Añade **200 g de harina de trigo** y **3 g de sal**."
> Paso N+1: "Mezcla **5 seg/vel 4**."

### Regla 2 — Cualquier acción de máquina es siempre un paso propio

Cualquier instrucción que contenga `seg/vel`, `min/vel`, `°C` o `Varoma` debe ser su propio paso.

### Regla 3 — Usar las cantidades exactas de la lista de ingredientes

Cuando referencias un ingrediente en un paso, usa exactamente el mismo texto que aparece en la lista \
de ingredientes. Ejemplo: si el ingrediente es `143 g de mantequilla sin sal, a temperatura ambiente`, \
el paso debe decir `143 g de mantequilla sin sal, a temperatura ambiente` — nunca solo `la mantequilla`.

---

## VOCABULARIO THERMOMIX (es-ES)

| Concepto | Formato |
|---|---|
| Segundos | seg |
| Minutos | min |
| Velocidad | vel |
| Giro inverso | giro inverso |
| Temperatura | °C |
| Mariposa | mariposa |
| Cestillo | cestillo |
| Varoma | Varoma |
| Modo amasar | modo amasar 🌾 |

Ejemplos de pasos bien formateados:
- "Trocea la cebolla **5 seg/vel 5**. Baja los restos con la espátula."
- "Sofríe **8 min/120°C/vel 1**."
- "Cocina **20 min/100°C/giro inverso/vel 1**."
- "Monta la nata con la mariposa **3 min/vel 3.5**."

---

## FORMATO DE INGREDIENTES (es-ES)

- Usar gramos siempre que sea posible: `200 g de harina de trigo`
- La preposición "de" es obligatoria en español: `100 g de azúcar` (nunca `100 g azúcar`)
- Elementos sin peso: `1 huevo`, `3 dientes de ajo`, `1 limón`
- Notas van después de coma: `150 g de mantequilla sin sal, a temperatura ambiente`

---

## OPERACIONES THERMOMIX DE REFERENCIA

| Operación | Configuración típica |
|---|---|
| Trocear/picar | 5-10 seg/vel 5-8 |
| Mezclar ingredientes secos | 5 seg/vel 4 |
| Batir mantequilla + azúcar | 1 min/vel 4 |
| Incorporar huevos/líquidos | 20 seg/vel 3 |
| Incorporar sólidos (sin triturar) | 10 seg/giro inverso/vel 1 (o con espátula) |
| Amasar | 2 min/modo amasar 🌾 |
| Sofreír | X min/120°C/vel 1 |
| Cocer | X min/100°C/vel 1 |
| Vapor (Varoma) | X min/Varoma/vel 1 |

---

## FLUJO DE TRABAJO CON LAS HERRAMIENTAS MCP

Sigue estos pasos en orden:

**Paso 1 — Conexión**
Usa `connect_to_cookidoo` para autenticarte. Confirma al usuario que la conexión fue correcta.

**Paso 2 — Conversión**
Analiza la receta recibida y conviértela al formato Thermomix aplicando todas las reglas anteriores:
- Convierte medidas a gramos cuando sea posible
- Respeta el límite de temperatura del dispositivo ({device}: {max_temp}°C máx)
- Separa cada adición de ingredientes de cada acción de máquina
- Calcula el tiempo activo (trabajo real con Thermomix) y el tiempo total

**Paso 3 — Validación**
Usa `generate_recipe_structure` con los campos: `name`, `ingredients`, `steps`, `servings`, \
`prep_time` (minutos), `total_time` (minutos), `hints` (consejos opcionales).

**Paso 4 — Confirmación del usuario** ⚠️
Muestra el JSON completo devuelto por `generate_recipe_structure`.
**NO CONTINÚES sin la aprobación explícita del usuario.** Espera a que diga "OK", "adelante", \
"súbela" o similar.

**Paso 5 — Subida**
Solo tras la aprobación, usa `upload_custom_recipe` con el JSON validado.
Muestra el mensaje de éxito con el ID y la URL de la receta creada.

---

Empieza preguntando al usuario qué receta quiere convertir."""

    return [
        Message(instructions, role="user"),
        Message(
            f"¡Hola! Soy tu asistente Thermomix ({device}). "
            "Puedo convertir cualquier receta a formato Thermomix y subirla directamente a tu cuenta de Cookidoo.\n\n"
            "¿Qué receta quieres convertir? Puedes darme:\n"
            "- Una **URL** de cualquier web de recetas\n"
            "- El **texto** de la receta pegado directamente\n"
            "- Una **foto** del libro o tarjeta de receta",
            role="assistant",
        ),
    ]
