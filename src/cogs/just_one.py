import random
import time

import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List
import utils as ut
from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI, DEFAULT_TIMEOUT
from game import Game, find_game
from game import print_games
from tools import Hint, Phase, compute_proper_nickname, getword
import json
import asyncio

from game import games


class JustOne(commands.Cog):
    """
    Manager for the popular Game 'JustOne'
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='play', help='Starte eine neue Rund von *Just One* in deinem aktuellen Kanal')
    async def play(self, ctx: commands.Context):
        guesser = ctx.author
        text_channel = ctx.channel
        for game in games:
            if game.channel.id == text_channel.id:
                if not (game.phase == Phase.finished or game.phase == Phase.stopped):

                    print('There is already a game running in this channel, aborting...')
                    game.sent_messages.append(ctx.message)  # Delete the command at the end of the game
                    await game.send_message(  # Show an error message that a game is running
                        embed=ut.make_embed(
                            title="Oops!",
                            value="In diesem Kanal läuft bereits eine Runde JustOne, du kannst keine neue starten",
                            color=ut.red
                        ),
                        reaction=False
                    )
                    break  # We found a game that is already running, so break the loop
                elif game.phase == Phase.finished:  # If the game is finished but not stopped, stop it
                    await game.stop()
        else:  # Now - if the loop did not break - we are ready to start a new game
            game = Game(text_channel, guesser, bot=self.bot)
            games.append(game)
            await game.play()

    @commands.command(name='rules', help='Zeige die Regeln von *Just One* an und erkläre, wie dieser Bot funktioniert.')
    async def rules(self, ctx):
        await help_message(ctx.channel, ctx.message.author)

    @commands.command(name='abort', help='Bricht die aktuelle Runde im Kanal ab')
    async def abort(self, ctx: commands.Context):
        game = find_game(ctx.channel)
        if game is None:
            return
        else:
            await game.abort(f'Manueller Abbruch', member=ctx.author)

    @commands.command(name='correct', help='Ändere das Ergebnis der Runde auf _richtig_. Sollte dann verwendet'
                                           ' werden, wenn der Bot eine Antwort fälschlicherweise abgelehnt hat.'
                                           ' Wir vertrauen euch! :wink:')
    async def correct(self, ctx:commands.Context):
        print('correction started')
        game = find_game(ctx.channel)
        if game is None or game.phase != Phase.finished:
            print('no game found or game not in finished phase')
            return
        else:
            game.won = True
            await game.summary_message.delete()
            game.summary_message = await game.show_summary(True)



    @commands.command(name='print')
    async def print_games(self, ctx):
        print_games()

    """
    @commands.command()
    async def tips(self, ctx: commands.Context):
        global text_channel
        global valid_tips
        global tips
        await display_valid_tips(text_channel, tips)
    """

    @commands.Cog.listener()
    async def on_message(self, message):
        channel = message.channel
        game = find_game(channel)
        if game is None:
            return  # since no game is running in this channel, nothing has to be done

        if message.author.bot:
            print('Found a bot message. Ignoring')  # TODO: what if this was another bot?
            return

        if message.content.startswith(PREFIX):
            print('Found a own bot command, ignoring it')
            game.sent_messages.append(message)

        if game.phase == Phase.get_hints:
            game.add_hint(message)
            await message.delete()  # message has been properly processed as a hint
        elif game.phase == Phase.show_hints:
            if message.author != game.guesser:
                game.sent_messages.append(message)  # message was not relevant for game, but still deleting (for log)
        else:  # game is not in a phase to process messages (should be Phase.filter_hints)
            game.sent_messages.append(message)


async def help_message(channel: discord.TextChannel, member: discord.Member) -> discord.Embed:  # Prints a proper help message for JustOne
    embed = discord.Embed(
        title=f'Was is JustOne?',
        description=f'Hallo, {member.mention}. JustOne ist ein beliebtes Partyspiel von  *Ludovic Roudy* und *Bruno Sautter*\n'
                    f'Das Spiel ist kollaborativ, Ziel ist es, dass eine Person ein ihr unbekanntes Wort errät\n'
                    f'Dazu wird dieses Wort allen Mitspielenden genannt, die sich ohne Absprache je einen Tipp - *ein* Wort - ausdenken '
                    f'dürfen. Doch Vorsicht! Geben 2 oder mehr SpielerInnen den (semantisch) gleichen Tipp, so darf die '
                    f'ratende Person diesen nicht ansehen! Seid also geschickt, um ihr zu helfen, das '
                    f'Lösungswort zu erraten',
        color=ut.orange,
        footer='Dieser Bot ist noch unstabil. Bei Bugs, gebt uns auf [GitHub]'
               '(https://github.com/kesslermaximilian/JustOneBot) Bescheid!)'
    )
    embed.add_field(
        name='Spielstart',
        value='Startet das Spiel in einem beliebigen Textkanal auf dem Server mit `~play`. '
              'Wer den Befehl eingibt, ist selbst mit Raten dran.',
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
        value=f'Bestätigt nun dem Bot, dass ihr eure Tipps gegeben habt, indem ihr auf den {CHECK_EMOJI} klickt. '
              f'Der Bot zeigt euch nun die abgegebenen Antworten an: Markiert alle doppelten, indem ihr mit '
              f'{DISMISS_EMOJI} reagiert. Anschließend bestätigt ihr die Auswahl unter der letzten Nachricht mit einem'
              f' {CHECK_EMOJI}',
        inline=False
    )
    embed.add_field(
        name='Raten!',
        value='Die ratende Person kann nun den Channel automatisch wieder betreten und eine Antwort eingeben, der Bot'
              ' wertet diese automatisch aus und zeigt euch dann eine Zusammenfassung eurer Runde',
        inline=False
    )
    embed.add_field(
        name='Viel Spaß!',
        value='Worauf wartet ihr noch! Sucht euch einen Kanal und beginnt eure Erste Runde *JustOne*',
        inline=False
    )

    await channel.send(embed=embed)
    return embed

# Setup the bot if this extension is loaded


def setup(bot):
    bot.add_cog(JustOne(bot))



"""
Todo:
speichern / loggen von games
settings
"""
