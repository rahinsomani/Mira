from mira.data.nutrition_store import NutritionStore


def test_covers_at_least_20_foods():
    store = NutritionStore()
    assert len(store.all_foods()) >= 20


def test_lookup_is_case_insensitive():
    store = NutritionStore()
    assert store.lookup("BANANA") is not None
