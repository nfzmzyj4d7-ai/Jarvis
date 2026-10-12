from jarvis.textfmt import spoken_date
from jarvis.tools import tool


@tool(name="get_date", description="Geeft de datum en weekdag van vandaag. / Returns today's date and weekday.")
def get_date(ctx, **_):
    return spoken_date(ctx.now(), ctx.lang)
