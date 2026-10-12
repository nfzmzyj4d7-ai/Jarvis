from jarvis.tools import tool


@tool(
    name="recall",
    description=("Zoek in de opgeslagen feiten over de gebruiker (bv. 'wat weet je over mijn auto'). "
                 "/ Search the stored facts about the user."),
    parameters={
        "type": "object",
        "properties": {"topic": {"type": "string", "description": "Onderwerp / topic, bv. 'auto'"}},
        "required": ["topic"],
    },
)
def recall(ctx, topic: str = "", **_):
    facts = ctx.memory.search_facts(topic)
    if not facts:
        return ctx.say(f"Niets opgeslagen over '{topic}'.", f"Nothing stored about '{topic}'.")
    return "\n".join(f"- {f}" for f in facts)
