from jarvis.textfmt import spoken_time
from jarvis.tools import tool


@tool(name="get_time", description="Geeft de huidige tijd. / Returns the current time.")
def get_time(ctx, **_):
    return spoken_time(ctx.now(), ctx.lang)
