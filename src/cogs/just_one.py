import discord
from discord.ext import commands, tasks
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

    @tasks.loop(count=1)
    async def clear_messages(self, game: Game):
        game.message_sender.message_handler.clear_messages()

    @commands.command(name='play', help='Starte eine neue Rund von *Just One* in deinem aktuellen Kanal')
    async def play(self, ctx: commands.Context, *args):
        compute_current_distribution(ctx=ctx)
        guesser = ctx.author
        text_channel = ctx.channel
        for game in games:
            if game.channel.id == text_channel.id:
                if not (game.phase.value >= 130):  # Check if the game has a summary already

                    print('There is already a game running in this channel, aborting...')
                    await game.message_sender.send_message(
                        embed=output.already_running(),
                        reaction=False,
                        group=Group.warn
                    )
                    break  # We found a game that is already running, so break the loop
                elif game.phase == Phase.show_summary:  # If the game is finished but not stopped, stop it
                    game.phase_handler.advance_to_phase(Phase.stopping)
        else:  # Now - if the loop did not break - we are ready to start a new game
            game = Game(text_channel, guesser, bot=self.bot,
                        word_pool_distribution=compute_current_distribution(ctx=ctx),
                        participants=ut.get_members_from_args(ctx.guild, args)
                        )

            games.append(game)
            game.play()

    @commands.command(name='rules', help='Zeige die Regeln von *Just One* an und erkläre, wie dieser Bot funktioniert.')
    async def rules(self, ctx):
        await ctx.send(embed=output.rules(member=ctx.message.author, prefix=PREFIX, check_emoji=CHECK_EMOJI,
                                          dismiss_emoji=DISMISS_EMOJI))

    @commands.command(name='abort', help='Bricht die aktuelle Runde im Kanal ab')
    async def abort(self, ctx: commands.Context):
        game = find_game(ctx.channel)
        if game is None:
            return
        elif game.phase.value < 120:
            game.abort_reason = output.manual_abort(ctx.author)
            game.phase_handler.advance_to_phase(Phase.aborting)
        else:
            await game.message_sender.send_message(embed=output.warn_no_abort_anymore(), reaction=False, group=Group.warn)

    @commands.command(name='correct', help='Ändere das Ergebnis der Runde auf _richtig_. Sollte dann verwendet'
                                           ' werden, wenn der Bot eine Antwort fälschlicherweise abgelehnt hat.'
                                           ' Wir vertrauen euch! :wink:')
    async def correct(self, ctx: commands.Context):
        print('correction started')
        game = find_game(ctx.channel)
        if game is None or game.phase == Phase.show_summary:
            print('no game found or game not in finished phase')
            return
        else:
            game.won = True
            await game.message_sender.edit_message(key=Key.summary,
                                                   embed=output.summary(game.won, game.word, game.guess,
                                                                        game.guesser, prefix=PREFIX,
                                                                        hint_list=game.hints, corrected=True)
                                                   )
            # await game.message_sender.message_handler.delete_special_message(key=Key.summary)
            # game.summary_message = await game.message_sender.send_message(
            #     embed=output.summary(game.won, game.word, game.guess,
            #                          game.guesser, prefix=PREFIX, hint_list=game.hints, corrected=True)
            # )

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
                print('Found own bot message. Ignoring')  # TODO: what if other command from same bot is executed?
            else:
                print('Found other bot message.')
                # Add to category bot
                # game.message_sender.message_handler.add_message_to_group(message, Group.other_bot_messages)
        elif message.content.startswith(PREFIX):
            print('Found a own bot command, ignoring it')
            game.message_sender.message_handler.add_message_to_group(message, Group.own_command_invocation)
        #  We now know that the message is neither from a bot, nor a command invocation for our bot
        elif game.phase == Phase.wait_collect_hints:  # The game currently collects hints, so delete the message and add hint
            await message.delete()
            await game.add_hint(message)
        elif game.phase == Phase.wait_for_guess:  # The game is waiting for a guess
            #  Check if message is from the guesser, if not, it is regular chat
            if message.author != game.guesser:
                game.message_sender.message_handler.add_message_to_group(message, group=Group.user_chat)  # Regular chat
        else:  # regular chat
            game.message_sender.message_handler.add_message_to_group(message, group=Group.user_chat)


# Setup the bot if this extension is loaded
def setup(bot):
    bot.add_cog(JustOne(bot))
