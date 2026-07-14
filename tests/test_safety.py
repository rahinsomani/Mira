from mira.llm.safety import check


def test_blocks_medication_change_suggestion():
    result = check("You should take an extra dose of insulin tonight.")
    assert not result.passed


def test_blocks_diagnosis():
    result = check("You have diabetes based on this reading.")
    assert not result.passed


def test_allows_general_guidance():
    result = check("Your glucose is a bit high and trending up. Keep an eye on it.")
    assert result.passed
