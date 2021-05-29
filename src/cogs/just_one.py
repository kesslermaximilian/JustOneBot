import asyncio

from discord.ext import commands, tasks

import game_management.output as output
import utils as ut
from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI
from game_management.game import Game, find_game, games
from game_management.tools import Phase, Group, Key
from game_management.word_pools import compute_current_distribution, getword
from log_setup import logger, channel_prefix


class JustOne(commands.Cog):
    """
    Contains commands to play the JustOne game
    """

    def __init__(self, bot):
        self.bot = bot

    @tasks.loop(count=1)
    async def clear_messages(self, game: Game):
        game.message_sender.message_handler.clear_messages()

    @commands.command(name='play', aliases=['start', 'game', 'jo', 'just-one', 'justone'],
                      help=f'Start a new round of *Just One* in your current channel, optionally with a set list of '
                           f'participants for this round. Note that per channel there can only be one game running.\n\n'
                           f'Usage: `{PREFIX}play [Optional: list of players] [Optional: number of hints per person]`\n'
                           f'Add players by mentioning them.\n'
                           f'*Default players* None, anyone can participate.\n'
                           f'*Default hints per players* 3,2 and 1 for 1,2 and at least 3 participants respectively')
    async def play(self, ctx: commands.Context, *args):
        logger.debug(f'{channel_prefix(ctx.channel)}Play command found.')
        compute_current_distribution(ctx=ctx)
        guesser = ctx.author
        text_channel = ctx.channel
        for game in games:
            if game.channel.id == text_channel.id:
                logger.debug(f'{channel_prefix(ctx.channel)}Found a game in the channel in phase {game.phase}...')
                if not (game.phase.value >= 130):  # Check if the game has a summary already
                    logger.debug(f'{channel_prefix(ctx.channel)}...game is still playing, aborting play command and '
                                 f'sending warning message')
                    await game.message_sender.send_message(
                        embed=output.already_running(),
                        reaction=False,
                        group=Group.warn
                    )
                    break  # We found a game that is already running, so break the loop
                elif game.phase == Phase.show_summary:  # If the game is finished but not stopped, stop it
                    logger.debug(f'{channel_prefix(ctx.channel)}...game can be stopped, stopping')
                    game.phase_handler.advance_to_phase(Phase.stopping)
        else:  # Now - if the loop did not break - we are ready to start a new game
            logger.debug(f'{channel_prefix(ctx.channel)}Initialising new game, as no game is running or old game has '
                         f'been stopped')
            game = Game(text_channel, guesser, bot=self.bot,
                        word_pool_distribution=compute_current_distribution(ctx=ctx),
                        participants=ut.get_members_from_args(ctx.guild, args),
                        expected_tips_per_person=ut.get_expected_number_of_tips_from_args(args)
                        )

            games.append(game)
            game.play()
            logger.debug(f'{channel_prefix(ctx.channel)}Started new game')

    @commands.command(name='rules', help='Show the rules of this game.')
    async def rules(self, ctx):
        await ctx.send(embed=output.rules(member=ctx.message.author, prefix=PREFIX, check_emoji=CHECK_EMOJI,
                                          dismiss_emoji=DISMISS_EMOJI))

    @commands.command(name='abort', help='Abort the round running in this channel (if any).\n'
                                         'If the round has a fixed participant list, command can only be issued by '
                                         'a participant\n'
                                         'Can also be sent privately to the bot to abort the round where one is '
                                         'currently guessing')
    async def abort(self, ctx: commands.Context):  # TODO: debug this
        logger.debug(f'{channel_prefix(ctx.channel)}Abort command issued, checking for existing game')
        game = find_game(channel=ctx.channel, user=ctx.author)
        if game is None:
            logger.debug(f'{channel_prefix(ctx.channel)}No game found in the current channel, sending warn message.')
            print('abort command initiated in channel with no game')
            await ctx.send(embed=output.warning_no_round_running())
            return
        else:
            logger.debug(f'{channel_prefix(ctx.channel)}Found an existing game in phase {game.phase}')
        if game.closed_game and ctx.author not in game.participants and ctx.author != game.guesser:
            logger.debug(f'{channel_prefix(ctx.channel)}Game is in closed mode and command author not on participant'
                         f' list or guesser. Ignoring the abort command.')
            return  # Ignore abort command by non-participating person. Warn message is sent otherwise
        elif game.phase.value < 130:  # 130 is the value of the summary phase
            logger.debug(f'{channel_prefix(ctx.channel)}Game has not finished yet, aborting it')
            game.abort_reason = output.manual_abort(ctx.author)
            game.phase_handler.advance_to_phase(Phase.aborting)
        else:
            logger.debug(f'{channel_prefix(ctx.channel)}Game is already showing summary, being aborted, stopped or has'
                         f' stopped already, no abort needed anymore. Sending warn message that this is the case.')
            await game.message_sender.send_message(embed=output.warn_no_abort_anymore(), reaction=False,
                                                   group=Group.warn)
        if ctx.guild is None:
            await asyncio.sleep(1)  # Wait a second so that mentioning the channel will properly work
            await ctx.send(embed=output.abortion_in_private_channel(channel=game.channel))

    @commands.command(name='correct', help='Tell the bot that your guess is correct. This can be used if the bot '
                                           'improperly rejects your guess.'
                                           ' We trust you not to abuse this! :wink:')
    async def correct(self, ctx: commands.Context):
        print('correction started')
        game = find_game(ctx.channel)
        if game is None or game.phase != Phase.show_summary:
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

    @commands.command(name='draw', help='Draw a word from the current wordpool.')
    async def draw_word(self, ctx):
        distribution = compute_current_distribution(ctx=ctx)
        await ctx.send(embed=ut.make_embed(
            title="Ein Wort für dich!",
            value=f"Dein Wort lautet: `{getword(distribution)}`. Viele Spaß damit!"
        )
        )
        logger.info(f'Drew a word from Distribution: {distribution}')

    @commands.Cog.listener()
    async def on_message(self, message):
        logger.debug(f'{on_message_prefix(message)}Got a message, trying to find game in channel '
                     f'{message.channel.id}...')
        channel = message.channel
        game = find_game(channel)
        if game is None:
            logger.debug(f'{on_message_prefix(message)}No game found in channel, nothing to do')
            return  # since no game is running in this channel, nothing has to be done

        logger.debug(f'{on_message_prefix(message)}Found game with id {game.id} in phase {game.phase} in the current'
                     f'channel. Further handling of the message is needed')
        if message.author.bot:
            if message.author.id == message.channel.guild.me.id:
                logger.debug(f'{on_message_prefix(message)}Message was written by myself, ignoring it.')
            else:
                game.message_sender.message_handler.add_message_to_group(message, Group.other_bot)
                logger.debug(f'{on_message_prefix(message)}Message was written by other bot, added it to group '
                             f'{Group.other_bot} of the running game {game.id}')

        elif message.content.startswith(PREFIX):
            game.message_sender.message_handler.add_message_to_group(message, Group.own_command_invocation)
            logger.debug(f'{on_message_prefix(message)}Message is a command for myself, added it to group '
                         f'{Group.own_command_invocation} of game {game.id}')
        #  We now know that 1) there is game running in the current channel and 2) the message was sent by a real user
        #  and 3) the message is not a command for our bot.
        elif game.phase == Phase.wait_collect_hints:  # Check if game collects hints
            # Check if we have to delete the message
            if not game.closed_game or message.author in game.participants:
                await message.delete()
                logger.debug(f'{on_message_prefix(message)}Message was deleted as it will be processed as a hint by '
                             f'the game')
            await game.add_hint(message)
        elif game.phase == Phase.wait_for_guess:  # Check if game is waiting for a guess
            #  Check if message is from the guesser, if not, it is regular chat
            if message.author == game.guesser:
                logger.debug(f'{on_message_prefix(message)}Message will be the guess of the game, nothing to do')
                return
        else:  # Message has to be regular chat
            game.message_sender.message_handler.add_message_to_group(message, group=Group.user_chat)
            logger.debug(f'{on_message_prefix(message)}Message was added to group {Group.user_chat} of the game, '
                         f'as it is not a hint or the guess for the game.')


def on_message_prefix(message):
    return f'[Message listener] [Message {message.id}] '


# Setup the bot if this extension is loaded
def setup(bot):
    bot.add_cog(JustOne(bot))
