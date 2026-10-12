from jarvis.textfmt import spoken_duration
from jarvis.tools import tool


def _num(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


@tool(
    name="set_timer",
    description="Zet een afteltimer. Geef de duur in minutes en/of seconds. / Starts a countdown timer.",
    parameters={
        "type": "object",
        "properties": {
            "minutes": {"type": "number", "description": "Aantal minuten / number of minutes"},
            "seconds": {"type": "number", "description": "Aantal seconden / number of seconds"},
        },
    },
)
def set_timer(ctx, minutes=0, seconds=0, **_):
    total = int(round(_num(minutes) * 60 + _num(seconds)))
    if total <= 0:
        return ctx.say("Voor hoelang moet de timer lopen?", "How long should the timer run?")
    ctx.timers.start(total, ctx.lang)
    duration = spoken_duration(total, ctx.lang)
    return ctx.say(f"Timer gezet voor {duration}.", f"Timer set for {duration}.")
