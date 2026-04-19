"""Tests for CustomRecipe Pydantic schema validation."""

import pytest
from pydantic import ValidationError
from schemas import CustomRecipe


def test_valid_recipe_all_fields():
    recipe = CustomRecipe(
        name="Chocolate Chip Cookies",
        ingredients=["200g flour", "100g butter", "1 egg"],
        steps=["Mix butter and sugar", "Add egg", "Bake at 180°C"],
        servings=12,
        prep_time=15,
        total_time=30,
        hints=["Don't overmix", "Cookies firm up as they cool"],
    )
    assert recipe.name == "Chocolate Chip Cookies"
    assert len(recipe.ingredients) == 3
    assert len(recipe.steps) == 3
    assert recipe.servings == 12
    assert recipe.prep_time == 15
    assert recipe.total_time == 30
    assert recipe.hints == ["Don't overmix", "Cookies firm up as they cool"]


def test_defaults():
    recipe = CustomRecipe(
        name="Simple Recipe",
        ingredients=["1 egg"],
        steps=["Cook the egg"],
    )
    assert recipe.servings == 4
    assert recipe.prep_time == 30
    assert recipe.total_time == 60
    assert recipe.hints is None


def test_name_empty_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="", ingredients=["1 egg"], steps=["Cook"])


def test_name_too_long_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="x" * 201, ingredients=["1 egg"], steps=["Cook"])


def test_name_max_length_valid():
    recipe = CustomRecipe(name="x" * 200, ingredients=["1 egg"], steps=["Cook"])
    assert len(recipe.name) == 200


def test_ingredients_empty_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=[], steps=["Cook"])


def test_steps_empty_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=[])


def test_servings_zero_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=["Cook"], servings=0)


def test_servings_twenty_one_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=["Cook"], servings=21)


def test_servings_boundary_valid():
    r1 = CustomRecipe(name="R", ingredients=["x"], steps=["s"], servings=1)
    r2 = CustomRecipe(name="R", ingredients=["x"], steps=["s"], servings=20)
    assert r1.servings == 1
    assert r2.servings == 20


def test_prep_time_zero_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=["Cook"], prep_time=0)


def test_prep_time_over_max_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=["Cook"], prep_time=1441)


def test_total_time_zero_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=["Cook"], total_time=0)


def test_total_time_over_max_raises():
    with pytest.raises(ValidationError):
        CustomRecipe(name="Recipe", ingredients=["1 egg"], steps=["Cook"], total_time=1441)


def test_time_boundary_valid():
    recipe = CustomRecipe(
        name="R", ingredients=["x"], steps=["s"], prep_time=1, total_time=1440
    )
    assert recipe.prep_time == 1
    assert recipe.total_time == 1440


def test_json_roundtrip():
    recipe = CustomRecipe(
        name="Cookies",
        ingredients=["200g flour", "100g butter"],
        steps=["Mix", "Bake"],
        servings=12,
        prep_time=15,
        total_time=45,
        hints=["Don't overbake"],
    )
    json_str = recipe.model_dump_json()
    restored = CustomRecipe.model_validate_json(json_str)
    assert recipe == restored


def test_json_roundtrip_no_hints():
    recipe = CustomRecipe(
        name="Simple",
        ingredients=["1 egg"],
        steps=["Cook"],
    )
    json_str = recipe.model_dump_json()
    restored = CustomRecipe.model_validate_json(json_str)
    assert restored.hints is None
    assert recipe == restored


# ---------------------------------------------------------------------------
# check_times model_validator (new in this branch)
# ---------------------------------------------------------------------------


def test_prep_time_exceeds_total_time_raises():
    """prep_time > total_time must be rejected by the model validator."""
    with pytest.raises(ValidationError, match="prep_time.*cannot exceed total_time"):
        CustomRecipe(
            name="Bad Times",
            ingredients=["1 egg"],
            steps=["Cook"],
            prep_time=60,
            total_time=30,
        )


def test_prep_time_equal_total_time_valid():
    """prep_time == total_time is allowed (edge boundary)."""
    recipe = CustomRecipe(
        name="Equal Times",
        ingredients=["1 egg"],
        steps=["Cook"],
        prep_time=45,
        total_time=45,
    )
    assert recipe.prep_time == recipe.total_time
