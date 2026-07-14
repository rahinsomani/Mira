"""Scripted fallback responses, required by AI1 for when the LLM is unavailable
or its output fails the safety check. These are the only responses that should
ever be used in that situation — do not attempt to patch/sanitize LLM output
and use it anyway."""

GLUCOSE_UNAVAILABLE = (
    "I can't reach my language model right now, but your last glucose reading "
    "was {value} mmol/L, trend {trend}. Please check with your care provider if "
    "you have concerns."
)

MEAL_UNAVAILABLE = (
    "I can't give meal guidance right now. Please check with your care provider "
    "or a nutrition label before eating."
)

SAFETY_BLOCKED = (
    "I'm not able to answer that one safely. Please contact your care provider "
    "for guidance."
)
