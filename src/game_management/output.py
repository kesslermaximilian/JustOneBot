import discord
import utils as ut

def warning(reason: str) -> discord.Embed:
    return discord.Embed(title="Warnung!", color=ut.red, description=reason)

def time_warning() -> discord.Embed:
    return warning("Ich warte auf eine Reaktion von dir")