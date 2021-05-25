import discord
from discord.ext import commands
import utils as ut
from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI
from game_management.game import Game, find_game, games
from game_management.tools import Phase, Group, Key
from game_management.word_pools import compute_current_distribution, getword
import game_management.output as output


class JustOne(commands.Cog):
    """
    Manager for the popular Game 'JustOne'
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='play', help='Starte eine neue Rund von *Just One* in deinem aktuellen Kanal')
    async def play(self, ctx: commands.Context, *args):
        compute_current_distribution(ctx=ctx)
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
            game = Game(text_channel, guesser, bot=self.bot,
                        word_pool_distribution=compute_current_distribution(ctx=ctx))

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
    async def correct(self, ctx: commands.Context):
        print('correction started')
        game = find_game(ctx.channel)
        if game is None or game.phase != Phase.finished:
            print('no game found or game not in finished phase')
            return
        else:
            game.won = True
            await game.message_sender.message_handler.delete_special_message(key=Key.summary)
            game.summary_message = await game.message_sender.send_message(
                embed=output.summary(game.won, game.word, game.guess,
                                     game.guesser, prefix=PREFIX, hint_list=game.hints, corrected=True)
            )

    @commands.command(name='draw', help='Ziehe ein Wort aus dem aktuellen Wortpool')
    async def draw_word(self, ctx):
        await ctx.send(embed=ut.make_embed(
            title="Ein Wort für dich!",
            value=f"Dein Wort lautet: `{getword(compute_current_distribution(ctx=ctx))}`. Viele Spaß damit!"
        )
        )

    @commands.Cog.listener()
    async def on_message(self, message):
        channel = message.channel
        game = find_game(channel)
        if game is None:
            return  # since no game is running in this channel, nothing has to be done

        if message.author.bot:
            if message.author.id == message.channel.guild.me.id:
                print('Found own bot message. Ignoring')
            else:
                print('Found other bot message.')
                game.message_sender.message_handler.add_message_to_group(message, Group.bot)  # Add to category bot

        if message.content.startswith(PREFIX):
            print('Found a own bot command, ignoring it')
            game.message_sender.message_handler.add_message_to_group(message, Group.command)

        if game.phase == Phase.get_hints:
            await message.delete()  # message has been properly processed as a hint
            await game.add_hint(message)
        elif game.phase == Phase.show_hints:
            if message.author != game.guesser:
                game.message_sender.message_handler.add_message_to_group(message, group=Group.chat)  # Regular chat
        else:  # game is not in a phase to process messages (should be in Phase.filter_hints)
            game.message_sender.message_handler.add_message_to_group(message, group=Group.chat)


async def help_message(channel: discord.TextChannel,
                       member: discord.Member) -> discord.Embed:  # Prints a proper help message for JustOne
    embed = discord.Embed(
        title=f'Was ist JustOne?',
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
        value=f'Startet das Spiel in einem beliebigen Textkanal auf dem Server mit `{PREFIX}play`. '
              f'Wer den Befehl eingibt, ist selbst mit Raten dran.',
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
        name='Zu Unrecht verloren?',
        value=f'Der Bot hat eure Antwort zu Unrecht nicht als korrekt eingestuft? Kein Problem, das könnt ihr mit'
              f' dem Befehl `{PREFIX}correct` beheben, den ihr bis zu 30 Sekunden nach der Zusammenfassung der Runde'
              f' verwenden könnt. Nicht schummeln!',
        inline=False
    )
    embed.add_field(
        name='Weiteres',
        value=f'Mehr Details erfahrt ihr, indem ihr `{PREFIX}help` verwendet',
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
