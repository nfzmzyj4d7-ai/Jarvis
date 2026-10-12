import pytest

from jarvis.router import IntentRouter

router = IntentRouter()


@pytest.mark.parametrize("text,intent,lang", [
    ("Hoe laat is het?", "time", "nl"),
    ("Hey Jarvis, hoe laat is het?", "time", "nl"),
    ("Hoeveel uur is het?", "time", "nl"),
    ("Wat is het uur?", "time", "nl"),
    ("Kan je me zeggen hoe laat het is?", "time", "nl"),
    ("Jarvis, hoe laat is het nu?", "time", "nl"),
    ("What time is it?", "time", "en"),
    ("What's the time, Jarvis?", "time", "en"),
    ("Can you tell me what time it is?", "time", "en"),
    ("Welke datum is het vandaag?", "date", "nl"),
    ("De hoeveelste zijn we?", "date", "nl"),
    ("Welke dag is het?", "date", "nl"),
    ("What's the date today?", "date", "en"),
    ("What day is it?", "date", "en"),
    ("Zet een timer van 5 minuten.", "timer", "nl"),
    ("Zet een timer op tien minuten", "timer", "nl"),
    ("Timer van een kwartier", "timer", "nl"),
    ("Set a timer for 2 minutes and 30 seconds", "timer", "en"),
    ("Set a five minute timer", "timer", "en"),
    ("Annuleer de timer", "cancel_timer", "nl"),
    ("Cancel all timers", "cancel_timer", "en"),
    ("Stil!", "stop", "nl"),
    ("Hou op.", "stop", "nl"),
    ("Be quiet", "stop", "en"),
    ("Stop", "stop", None),
])
def test_commands(text, intent, lang):
    m = router.match(text)
    assert m is not None, text
    assert (m.name, m.lang) == (intent, lang)


@pytest.mark.parametrize("text,seconds", [
    ("Zet een timer van 5 minuten", 300),
    ("Zet een timer van vijf minuten en dertig seconden", 330),
    ("timer op een half uur", 1800),
    ("Set a timer for half an hour", 1800),
    ("Set a timer for 90 seconds", 90),
    ("Set a twenty five minute timer", 1500),
    ("Zet een timer van vijfentwintig minuten", 1500),
])
def test_timer_durations(text, seconds):
    assert router.match(text).args == {"seconds": seconds}


@pytest.mark.parametrize("text", [
    "Hoe laat gaat de bakker open?",            # bevat 'hoe laat', maar is geen klokvraag
    "What time does the shop close?",
    "Wat is de hoofdstad van Frankrijk?",
    "Onthoud dat mijn auto een Suzuki Vitara is",
    "Welke auto heb ik?",
    "Zet een timer",                            # geen duur -> laat het taalmodel doorvragen
    "Stop met roken, is dat gezond?",
    "Vertel me een mop",
    "",
])
def test_not_a_simple_command(text):
    assert router.match(text) is None
