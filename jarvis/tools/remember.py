from jarvis.tools import tool


@tool(
    name="remember",
    description=("Onthoud blijvend een feit dat de gebruiker je vraagt te onthouden. Schrijf het als korte zin in de "
                 "derde persoon, bv. 'De auto van Jules is een Suzuki Vitara'. / Permanently store a fact the user "
                 "asks you to remember, as a short third-person sentence."),
    parameters={
        "type": "object",
        "properties": {"fact": {"type": "string", "description": "Het feit, in de derde persoon / the fact"}},
        "required": ["fact"],
    },
)
def remember(ctx, fact: str = "", **_):
    if not fact.strip():
        return ctx.say("Wat moet ik onthouden?", "What should I remember?")
    new = ctx.memory.add_fact(fact)
    return ctx.say("Opgeslagen: " if new else "Dat wist ik al: ", "Saved: " if new else "Already known: ") + fact
