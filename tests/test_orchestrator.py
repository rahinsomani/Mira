import pytest

from mira.orchestrator import Orchestrator


def test_requires_confirmed_request():
    orchestrator = Orchestrator()
    with pytest.raises(PermissionError):
        orchestrator.handle_voice_turn(audio_bytes=b"", requester_confirmed=False)


def test_handles_glucose_query():
    orchestrator = Orchestrator()
    response = orchestrator.handle_voice_turn(audio_bytes=b"", requester_confirmed=True)
    assert isinstance(response, str)
    assert response
