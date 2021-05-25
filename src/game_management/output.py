import discord
import utils as ut
from game_management.tools import compute_proper_nickname
from typing import List, Union
from game_management.tools import Hint, hints2name_list


def warning_head(reason: str) -> discord.Embed:
    return discord.Embed(title="Warnung!", color=ut.red, description=reason)


def time_warning() -> discord.Embed:
    return warning_head("Ich warte auf eine Reaktion von dir")


def inform_admin_to_reenter_channel(channel: discord.TextChannel) -> discord.Embed:
    return ut.make_embed(
        title=f"Du bist dran mit Raten!",
        value=f"Komm wieder in {channel.mention},"
              f" um das Wort zu erraten!",
        footer="Dieser Kanal wird automatisch wieder gelöscht."
    )


def announce_word(guesser: discord.Member, word: str) -> discord.Embed:
    return discord.Embed(
        title='Neue Runde JustOne',
        color=ut.green,
        description=f'Gebt Tipps ab, um {compute_proper_nickname(guesser)} '
                    f'zu helfen, das Wort zu erraten und klickt auf den Haken, wenn ihr fertig seid!\n'
                    f'Das neue Wort lautet `{word}`.')


def announce_word_updated(guesser: discord.Member, word: str, hint_list: List[Hint]) -> discord.Embed:
    embed = announce_word(guesser, word)
    embed.add_field(name="Mitspieler, die schon (mindestens) einen Tipp abgegeben haben:",
                    value=hints2name_list(hint_list))
    return embed


def hint_to_review(hint_message: str, author: discord.Member) -> discord.Embed:
    return ut.make_embed(name=hint_message, value=compute_proper_nickname(author))


def confirm_massage_all_hints_reviewed() -> discord.Embed:
    return ut.make_embed(title='Alle doppelten Tipps markiert?', name='Dann bestätigt hier!')


def hints(hint_list: List[Hint]) -> discord.Embed:
    embed = discord.Embed(
        title=f'Es ist Zeit, zu raten!',
        description=f'Die folgenden Tipps wurden für dich abgegeben:'
    )

    for hint in hint_list:
        if hint.is_valid():
            embed.add_field(name=hint.hint_message, value=f'_{compute_proper_nickname(hint.author)}_')

    return embed


def hints_top(guesser: discord.Member) -> str:
    return f"Hey {guesser.mention}"


def summary(won: bool, word: str, guess: str, guesser: discord.Member, prefix: str, hint_list: List[Hint],
            corrected: bool = False) -> discord.Embed:
    color = ut.green if won else ut.red
    embed = discord.Embed(
        title='Gewonnen!' if won else "Verloren",
        description=f"Das Wort war: `{word}`\n _{compute_proper_nickname(guesser)}_ hat `{guess}` geraten.",
        color=color
    )

    for hint in hint_list:
        if hint.is_valid():
            embed.add_field(name=f'`{hint.hint_message}`', value=f'_{compute_proper_nickname(hint.author)}_')
        else:
            embed.add_field(name=f"~~`{hint.hint_message}`~~", value=f'_{compute_proper_nickname(hint.author)}_')

    if not won:
        embed.set_footer(text=f"Nutzt {prefix}correct, falls die Antwort dennoch richtig ist")

    if corrected:
        embed.set_footer(text=f"Danke für's Korrigieren! Entschudigung, dass ich misstrauisch war.")

    return embed


def abort(reason: str, word: str, guesser: discord.Member,
          aborting_person: Union[discord.Member, None] = None) -> discord.Embed:
    return discord.Embed(
        title="Runde abgebrochen",
        description=f"Die Runde wurde{f' von {aborting_person.mention}' if aborting_person else ''} vorzeitig beendet.",
        footer=f":\n {reason}\n_{compute_proper_nickname(guesser)}_ hätte `{word}` erraten müssen",
        color=ut.red
    )


def admin_mode_wait(guesser: discord.Member, admin_channel: discord.TextChannel) -> discord.Embed:
    return ut.make_embed(
        title="Einen Moment noch...",
        value=f"Hey, {compute_proper_nickname(guesser)}, verlasse bitte selbstständig diesen Kanal, damit ich die "
              f"Runde starten kann, ohne dass du das Wort siehst. Bestätige in {admin_channel.mention} kurz,"
              f"dass ich die Runde starten kann"
    )


def admin_channel_name(channel: discord.TextChannel) -> str:
    return f"{channel.name}-Warteraum"


def admin_welcome(guesser: discord.Member, emoji) -> discord.Embed:
    return ut.make_embed(
        title="Angekommen!",
        value=f"Hey, {guesser}! Du kannst in diesem Kanal warten, während dein Team Tipps für dich "
              f"erstellt. Bitte reagiere mit {emoji}, damit ich weiß, dass ich die Runde sicher "
              f"starten kann. Hol dir Popcorn!"
    )


def announce_hint_phase_ended(dismiss_emoji) -> discord.Embed:
    return ut.make_embed(
        title="Tippphase beendet",
        color=ut.orange,
        name=f"Wählt eventuell doppelte Tipps aus, indem ihr auf das {dismiss_emoji} klickt."
    )