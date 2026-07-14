from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Trend(str, Enum):
    RISING_FAST = "rising_fast"
    RISING = "rising"
    STEADY = "steady"
    FALLING = "falling"
    FALLING_FAST = "falling_fast"


@dataclass
class GlucoseReading:
    value_mmol_l: float
    trend: Trend
    timestamp: datetime


@dataclass
class NutritionInfo:
    food_name: str
    carbs_g: float
    glycemic_index: str  # "low" | "medium" | "high"
    notes: str = ""
