from jarvis.tools import tool


@tool(name="cancel_timers", description="Annuleert alle lopende timers. / Cancels all running timers.")
def cancel_timers(ctx, **_):
    n = ctx.timers.cancel_all()
    if n == 0:
        return ctx.say("Er loopt geen timer.", "There's no timer running.")
    return ctx.say(f"{n} timer geannuleerd." if n == 1 else f"{n} timers geannuleerd.",
                   f"{n} timer cancelled." if n == 1 else f"{n} timers cancelled.")
