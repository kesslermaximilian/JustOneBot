import discord
import utils as ut
from game_management.tools import compute_proper_nickname
from typing import List, Union
from game_management.tools import Hint, hints2name_list


def warning_head(reason: str) -> discord.Embed:
    return discord.Embed(title="Warnung!", color=ut.orange, description=reason)


def time_warning() -> discord.Embed:
    return warning_head("Ich warte auf eine Reaktion von dir")


def game_running_warning() -> discord.Embed:
    return warning_head("In diesem Kanal läuft bereits ein Spiel, ich ignoriere deswegen deinen Command, "
                        "weil er nicht relevant für das Spiel ist und dieses stören würde")


def not_participant_warning(member: discord.Member) -> discord.Embed:
    return warning_head(f"Hey {member.mention}, es scheint, als spielst du bei dieser Runde nicht mit. Warte bitte, "
                        f"bis die nächste Runde anfängt.")


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


def abort(reason: str, word: str, guesser: discord.Member) -> discord.Embed:
    return discord.Embed(
        title="Runde abgebrochen",
        description=f"Die Runde wurde vorzeitig beendet.\n"
                    f"{reason}",
        footer=f":\n {reason}\n_{compute_proper_nickname(guesser)}_ hätte `{word}` erraten müssen",
        color=ut.red
    )


def admin_mode_wait(guesser: discord.Member, admin_channel: discord.TextChannel) -> discord.Embed:
    return ut.make_embed(
        name="Einen Moment noch...",
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


def rules(member: discord.Member, prefix: str, check_emoji, dismiss_emoji) -> discord.Embed:  # Prints a proper help
    # message for JustOne
    embed = discord.Embed(
        title=f'Was ist JustOne?',
        description=f'Hallo, {member.mention}. JustOne ist ein beliebtes Partyspiel von  *Ludovic Roudy* und *Bruno '
                    f'Sautter*\n '
                    f'Das Spiel ist kollaborativ, Ziel ist es, dass eine Person ein ihr unbekanntes Wort errät\n'
                    f'Dazu wird dieses Wort allen Mitspielenden genannt, die sich ohne Absprache je einen Tipp - '
                    f'*ein* Wort - ausdenken '
                    f'dürfen. Doch Vorsicht! Geben 2 oder mehr SpielerInnen den (semantisch) gleichen Tipp, so darf die'
                    f' ratende Person diesen nicht ansehen! Seid also geschickt, um ihr zu helfen, das '
                    f'Lösungswort zu erraten',
        color=ut.orange,
    )
    embed.add_field(
        name='Spielstart',
        value=f'Startet das Spiel in einem beliebigen Textkanal auf dem Server mit `{prefix}play`. '
              f'Für Details hierzu siehe `{prefix}help JustOne`.',
        inline=False
    )
    embed.add_field(
        name='Tippphase',
        value='Die ratende Person kann nun die Nachrichten des Textkanals nicht mehr lesen, macht euch also um'
              ' Schummler keine Sorgen! Ihr könnt nun alle *einen* Tipp abgeben, indem ihr einfach eine Nachricht'
              ' in den Kanal schickt. Der Bot löscht diese automatisch, damit ihr sie nicht gegenseitig seht.'
              ' Doch keine Sorge, der Bot merkt sich natürlich eure Tipps!',
        inline=False
    )
    embed.add_field(
        name='Fertig? Dann Tipps vergleichen!',
        value=f'Bestätigt nun dem Bot, dass ihr eure Tipps gegeben habt, indem ihr auf den {check_emoji} klickt. '
              f'Der Bot zeigt euch nun die abgegebenen Antworten an: Markiert alle doppelten, indem ihr mit '
              f'{dismiss_emoji} reagiert. Anschließend bestätigt ihr die Auswahl unter der letzten Nachricht mit einem'
              f' {check_emoji}',
        inline=False
    )
    embed.add_field(
        name='Raten!',
        value='Die ratende Person kann nun den Channel automatisch wieder betreten und eine Antwort eingeben, der Bot'
              ' wertet diese automatisch aus und zeigt euch dann eine Zusammenfassung eurer Runde',
        inline=False
    )
    embed.add_field(
        name='Zu Unrecht verloren?',
        value=f'Der Bot hat eure Antwort zu Unrecht nicht als korrekt eingestuft? Kein Problem, das könnt ihr mit'
              f' dem Befehl `{prefix}correct` beheben, den ihr bis zu 30 Sekunden nach der Zusammenfassung der Runde'
              f' verwenden könnt. Nicht schummeln!',
        inline=False
    )
    embed.add_field(
        name='Weiteres',
        value=f'Mehr Details erfahrt ihr, indem ihr `{prefix}help` verwendet',
        inline=False
    )
    embed.add_field(
        name='Viel Spaß!',
        value='Worauf wartet ihr noch! Sucht euch einen Kanal und beginnt eure Erste Runde *JustOne*',
        inline=False
    )
    return embed


def already_running():
    return warning_head("In diesem Kanal läuft bereits ein Spiel, deswegen kannst du kein neues starten. "
                        "Warte auf das Ende der aktuellen Runde, dann kann ich ein neues beginnen")


def round_started(closed_game=False, repeation=False, guesser=None):
    if repeation:
        return ut.make_embed(name="Auf ein neues!",
                             value=f"Ich hab eine neue Runde mit den gleichen Teilnehmern und Einstellungen für euch "
                                   f"gestartet. Der ratende Mitspieler wurde rotiert und ist nun {guesser.mention}"
                                   f"\n Viel Spaß!",
                             color=ut.green)
    return ut.make_embed(name="Okay", value=f"Die Runde{'mit einer festen Teilnehmerliste' if closed_game else ''} "
                                            f"ist gestartet. {guesser.mention} ist der ratende Spieler. Wundere dich nicht,"
                                            f"wenn du den Kanal nicht mehr siehst, dann verläuft alles nach Plan.\n"
                                            f"Viel Spaß", color=ut.green)


def collect_hints_phase_not_ended():
    return 'Keine Betätigung, dass alle Tipps abgegeben wurden.'


def review_hints_phase_not_ended():
    return 'Keine Bestätigung, dass doppelte Tipps markiert wurden.'


def not_guessed():
    return 'TimeOut error: Nicht geraten'


def warn_participant_list_empty() -> discord.Embed:
    return warning_head("Ihr seid aber Trolle! Ich kann kein neues Spiel mit den gleichen Teilnehmern starten, weil dieses keine " \
           "(ratenden) Teilnehmer hat, und ich die ratende Person nicht rotieren kann!")


def manual_abort(author):
    return f'Manueller Abbruch durch {compute_proper_nickname(author)}'


def warn_no_abort_anymore():
    return warning_head('Die laufende Runde ist doch schon vorbei, es macht keinen Sinn, sie abzubrechen!')


def warning_no_round_running():
    return warning_head('In diesem Kanal läuft aktuell gar keine Runde, ich ignoriere daher deinen Command.')