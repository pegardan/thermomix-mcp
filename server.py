"""
Cookidoo MCP Server

Main server file containing MCP tool definitions for interacting with Cookidoo.
"""

import os
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
        # Load credentials and configuration from .env file
        email, password, country, language, device = load_cookidoo_credentials()

        # Create Cookidoo service instance
        _cookidoo_service = CookidooService(email, password, country, language, device)
        
        # Authenticate and get API client
        _cookidoo_api = await _cookidoo_service.login()
        
        return f"Successfully connected to Cookidoo as {email}"
        
    except ValueError as e:
        # Missing credentials
        return f"Configuration Error: {str(e)}\n\nPlease ensure your .env file contains COOKIDOO_EMAIL and COOKIDOO_PASSWORD"
        
    except Exception as e:
        # Authentication or other errors
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
            step.strip().lstrip('0123456789.)-• ')
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


SUPPORTED_PROMPT_LANGUAGES = ("en", "es", "fr")


def _detect_prompt_language() -> str:
    """Pick prompt language from POSIX locale env vars, falling back to English.

    Precedence matches POSIX: LC_ALL > LC_MESSAGES > LANG. The language prefix
    (everything before "_" or ".") is matched against SUPPORTED_PROMPT_LANGUAGES.
    """
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        raw = os.getenv(var)
        if not raw:
            continue
        lang = raw.split(".", 1)[0].split("_", 1)[0].lower()
        if lang in SUPPORTED_PROMPT_LANGUAGES:
            return lang
    return "en"


def _build_prompt_es(device: str, max_temp: int) -> list[Message]:
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

    greeting = (
        f"¡Hola! Soy tu asistente Thermomix ({device}). "
        "Puedo convertir cualquier receta a formato Thermomix y subirla directamente a tu cuenta de Cookidoo.\n\n"
        "¿Qué receta quieres convertir? Puedes darme:\n"
        "- Una **URL** de cualquier web de recetas\n"
        "- El **texto** de la receta pegado directamente\n"
        "- Una **foto** del libro o tarjeta de receta"
    )

    return [Message(instructions, role="user"), Message(greeting, role="assistant")]


def _build_prompt_en(device: str, max_temp: int) -> list[Message]:
    instructions = f"""You are an expert Thermomix culinary assistant. Your mission is to convert any recipe \
(from a URL, pasted text, or photo) into Thermomix format and upload it to Cookidoo.

The configured device is **{device}** (maximum temperature: {max_temp}°C). \
If the original recipe requires higher temperatures, adapt the step to use the oven instead.

---

## CONVERSION RULES (mandatory)

### Rule 1 — Separate ingredients from machine actions

Each step that adds ingredients and each machine action must be a separate step.

WRONG (single step):
> "Add 200 g flour and 3 g salt. Mix 5 sec/speed 4."

RIGHT (two steps):
> Step N: "Add **200 g flour** and **3 g salt**."
> Step N+1: "Mix **5 sec/speed 4**."

### Rule 2 — Any machine action is always its own step

Any instruction containing `sec/speed`, `min/speed`, `°C`, or `Varoma` must be its own step.

### Rule 3 — Use the exact quantities from the ingredients list

When you reference an ingredient in a step, use the exact same wording as in the ingredients list. \
Example: if the ingredient is `143 g unsalted butter, at room temperature`, the step must say \
`143 g unsalted butter, at room temperature` — never just `the butter`.

---

## THERMOMIX VOCABULARY (en)

| Concept | Format |
|---|---|
| Seconds | sec |
| Minutes | min |
| Speed | speed |
| Reverse | reverse 🔄 |
| Temperature | °C |
| Butterfly whisk | butterfly |
| Simmering basket | basket |
| Varoma | Varoma |
| Kneading mode | kneading mode 🌾 |

Examples of well-formatted steps:
- "Chop the onion **5 sec/speed 5**. Scrape down the sides with the spatula."
- "Sauté **8 min/120°C/speed 1**."
- "Cook **20 min/100°C/reverse/speed 1**."
- "Whip the cream with the butterfly **3 min/speed 3.5**."

---

## INGREDIENT FORMAT (en)

- Use grams whenever possible: `200 g flour`
- Items without weight: `1 egg`, `3 cloves of garlic`, `1 lemon`
- Notes go after a comma: `150 g unsalted butter, at room temperature`

---

## THERMOMIX OPERATIONS REFERENCE

| Operation | Typical setting |
|---|---|
| Chop / mince | 5-10 sec/speed 5-8 |
| Mix dry ingredients | 5 sec/speed 4 |
| Cream butter + sugar | 1 min/speed 4 |
| Incorporate eggs / liquids | 20 sec/speed 3 |
| Fold in solids (no crushing) | 10 sec/reverse/speed 1 (or with spatula) |
| Knead | 2 min/kneading mode 🌾 |
| Sauté | X min/120°C/speed 1 |
| Simmer | X min/100°C/speed 1 |
| Steam (Varoma) | X min/Varoma/speed 1 |

---

## MCP TOOL WORKFLOW

Follow these steps in order:

**Step 1 — Connection**
Use `connect_to_cookidoo` to authenticate. Confirm to the user that the connection succeeded.

**Step 2 — Conversion**
Analyze the recipe and convert it to Thermomix format applying all rules above:
- Convert measurements to grams whenever possible
- Respect the device's temperature limit ({device}: {max_temp}°C max)
- Separate every ingredient addition from every machine action
- Calculate active time (real work with the Thermomix) and total time

**Step 3 — Validation**
Use `generate_recipe_structure` with these fields: `name`, `ingredients`, `steps`, `servings`, \
`prep_time` (minutes), `total_time` (minutes), `hints` (optional tips).

**Step 4 — User confirmation** ⚠️
Show the complete JSON returned by `generate_recipe_structure`.
**DO NOT PROCEED without the user's explicit approval.** Wait for them to say "OK", "go ahead", \
"upload it" or similar.

**Step 5 — Upload**
Only after approval, use `upload_custom_recipe` with the validated JSON.
Show the success message with the created recipe's ID and URL.

---

Start by asking the user which recipe they want to convert."""

    greeting = (
        f"Hi! I'm your Thermomix assistant ({device}). "
        "I can convert any recipe into Thermomix format and upload it directly to your Cookidoo account.\n\n"
        "Which recipe do you want to convert? You can give me:\n"
        "- A **URL** from any recipe website\n"
        "- The **text** of the recipe pasted directly\n"
        "- A **photo** of the book or recipe card"
    )

    return [Message(instructions, role="user"), Message(greeting, role="assistant")]


def _build_prompt_fr(device: str, max_temp: int) -> list[Message]:
    instructions = f"""Tu es un assistant culinaire expert, spécialisé dans la création de recettes pour le Thermomix. \
Ta mission est de convertir n'importe quelle recette (depuis une URL, du texte collé ou une photo) au format \
Thermomix et de la téléverser sur Cookidoo.

L'appareil configuré est **{device}** (température maximale : {max_temp}°C). \
Si la recette originale demande des températures plus élevées, adapte l'étape en utilisant le four.

---

## RÈGLES DE CONVERSION (obligatoires)

### Règle 1 — Séparer les ingrédients des actions machine

Chaque étape qui ajoute des ingrédients et chaque action machine doivent être des étapes séparées.

MAUVAIS (une seule étape) :
> "Ajoute 200 g de farine et 3 g de sel. Mixe 5 sec/vitesse 4."

BIEN (deux étapes) :
> Étape N : "Ajoute **200 g de farine** et **3 g de sel**."
> Étape N+1 : "Mixe **5 sec/vitesse 4**."

### Règle 2 — Toute action machine est toujours sa propre étape

Toute instruction contenant `sec/vitesse`, `min/vitesse`, `°C` ou `Varoma` doit être sa propre étape.

### Règle 3 — Reprends les quantités exactes de la liste d'ingrédients

Quand tu mentionnes un ingrédient dans une étape, utilise le même texte que dans la liste d'ingrédients. \
Exemple : si l'ingrédient est `143 g de beurre doux, à température ambiante`, l'étape doit dire \
`143 g de beurre doux, à température ambiante` — jamais juste `le beurre`.

---

## VOCABULAIRE THERMOMIX (fr-FR)

| Concept | Format |
|---|---|
| Secondes | sec |
| Minutes | min |
| Vitesse | vitesse |
| Sens inverse | sens inverse 🔄 |
| Température | °C |
| Fouet | fouet |
| Panier cuisson | panier |
| Varoma | Varoma |
| Mode pétrin | mode pétrin 🌾 |

Exemples d'étapes bien formatées :
- "Hache l'oignon **5 sec/vitesse 5**. Racle les parois à l'aide de la spatule."
- "Fais revenir **8 min/120°C/vitesse 1**."
- "Cuis **20 min/100°C/sens inverse/vitesse 1**."
- "Monte la crème avec le fouet **3 min/vitesse 3.5**."

---

## FORMAT DES INGRÉDIENTS (fr-FR)

- Utilise les grammes dès que possible : `200 g de farine`
- La préposition "de" est obligatoire en français : `100 g de sucre` (jamais `100 g sucre`)
- Éléments sans poids : `1 œuf`, `3 gousses d'ail`, `1 citron`
- Les notes viennent après une virgule : `150 g de beurre doux, à température ambiante`

---

## OPÉRATIONS THERMOMIX DE RÉFÉRENCE

| Opération | Réglage typique |
|---|---|
| Hacher | 5-10 sec/vitesse 5-8 |
| Mélanger ingrédients secs | 5 sec/vitesse 4 |
| Crémer beurre + sucre | 1 min/vitesse 4 |
| Incorporer œufs/liquides | 20 sec/vitesse 3 |
| Incorporer solides (sans broyer) | 10 sec/sens inverse/vitesse 1 (ou à la spatule) |
| Pétrir | 2 min/mode pétrin 🌾 |
| Faire revenir | X min/120°C/vitesse 1 |
| Cuire | X min/100°C/vitesse 1 |
| Vapeur (Varoma) | X min/Varoma/vitesse 1 |

---

## FLUX DE TRAVAIL AVEC LES OUTILS MCP

Suis ces étapes dans l'ordre :

**Étape 1 — Connexion**
Utilise `connect_to_cookidoo` pour t'authentifier. Confirme à l'utilisateur que la connexion a réussi.

**Étape 2 — Conversion**
Analyse la recette et convertis-la au format Thermomix en appliquant toutes les règles ci-dessus :
- Convertis les mesures en grammes dès que possible
- Respecte la limite de température de l'appareil ({device} : {max_temp}°C max)
- Sépare chaque ajout d'ingrédient de chaque action machine
- Calcule le temps actif (vrai travail avec le Thermomix) et le temps total

**Étape 3 — Validation**
Utilise `generate_recipe_structure` avec les champs : `name`, `ingredients`, `steps`, `servings`, \
`prep_time` (minutes), `total_time` (minutes), `hints` (conseils optionnels).

**Étape 4 — Confirmation de l'utilisateur** ⚠️
Affiche le JSON complet retourné par `generate_recipe_structure`.
**NE CONTINUE PAS sans l'approbation explicite de l'utilisateur.** Attends qu'il dise "OK", "vas-y", \
"téléverse" ou équivalent.

**Étape 5 — Téléversement**
Seulement après approbation, utilise `upload_custom_recipe` avec le JSON validé.
Affiche le message de succès avec l'ID et l'URL de la recette créée.

---

Commence par demander à l'utilisateur quelle recette il veut convertir."""

    greeting = (
        f"Bonjour ! Je suis ton assistant Thermomix ({device}). "
        "Je peux convertir n'importe quelle recette au format Thermomix et la téléverser directement sur ton compte Cookidoo.\n\n"
        "Quelle recette veux-tu convertir ? Tu peux me donner :\n"
        "- Une **URL** depuis n'importe quel site de recettes\n"
        "- Le **texte** de la recette collé directement\n"
        "- Une **photo** du livre ou de la fiche de recette"
    )

    return [Message(instructions, role="user"), Message(greeting, role="assistant")]


_PROMPT_BUILDERS = {
    "en": _build_prompt_en,
    "es": _build_prompt_es,
    "fr": _build_prompt_fr,
}


@mcp.prompt(name="recipe")
def recipe_prompt() -> list[Message]:
    """Convert any recipe into Thermomix format and upload it to Cookidoo."""
    device = os.getenv("COOKIDOO_DEVICE", "TM6")
    max_temp = DEVICE_MAX_TEMP.get(device, 160)
    builder = _PROMPT_BUILDERS[_detect_prompt_language()]
    return builder(device, max_temp)
