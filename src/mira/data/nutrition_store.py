"""Nutrition lookup for meal guidance (F2: >=20 common foods). Replace the seed
data below with a real nutrition database as it becomes available."""

from __future__ import annotations

from mira.data.models import NutritionInfo

_SEED_FOODS: list[NutritionInfo] = [
    NutritionInfo("white bread", 14, "high"),
    NutritionInfo("whole wheat bread", 12, "medium"),
    NutritionInfo("oatmeal", 27, "low"),
    NutritionInfo("banana", 27, "medium"),
    NutritionInfo("apple", 25, "low"),
    NutritionInfo("orange", 15, "low"),
    NutritionInfo("white rice", 45, "high"),
    NutritionInfo("brown rice", 45, "medium"),
    NutritionInfo("pasta", 43, "medium"),
    NutritionInfo("potato, baked", 37, "high"),
    NutritionInfo("sweet potato", 27, "medium"),
    NutritionInfo("eggs", 1, "low"),
    NutritionInfo("chicken breast", 0, "low"),
    NutritionInfo("salmon", 0, "low"),
    NutritionInfo("broccoli", 6, "low"),
    NutritionInfo("carrots", 10, "medium"),
    NutritionInfo("milk, 2%", 12, "low"),
    NutritionInfo("yogurt, plain", 11, "low"),
    NutritionInfo("orange juice", 26, "high"),
    NutritionInfo("cereal, bran flakes", 24, "medium"),
    NutritionInfo("cookies", 22, "high"),
    NutritionInfo("almonds", 6, "low"),
]


class NutritionStore:
    def __init__(self) -> None:
        self._by_name = {f.food_name.lower(): f for f in _SEED_FOODS}

    def lookup(self, food_name: str) -> NutritionInfo | None:
        return self._by_name.get(food_name.lower())

    def all_foods(self) -> list[NutritionInfo]:
        return list(self._by_name.values())
