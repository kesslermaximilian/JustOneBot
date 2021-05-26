import random
import time

import discord
from discord.ext import tasks
from discord.ext import commands
from enum import Enum
from typing import NewType, List, Union
import utils as ut

from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI, SKIP_EMOJI, DEFAULT_TIMEOUT, ROLE_NAME
from environment import PLAY_AGAIN_CLOSED_EMOJI, PLAY_AGAIN_OPEN_EMOJI
from game_management.tools import Hint, Phase, evaluate, Key, Group, compute_proper_nickname

from game_management.word_pools import getword, WordPoolDistribution, compute_current_distribution
from game_management.messages import MessageSender, MessageHandler
import asyncio
import database.db_access as dba
import game_management.output as output
from log_setup import logger

games = []  # Global variable (what a shame!)


class Game:
    def __init__(self, channel: discord.TextChannel, guesser: discord.Member, bot,
                 word_pool_distribution: WordPoolDistribution, admin_mode: Union[None, bool] = None,
                 participants: List[discord.Member] = [], repeation=False,
                 quick_delete=True, expected_tips_per_person=0):
        self.channel = channel
        self.guesser = guesser
        self.guess = ""
        self.word = ""
        self.hints: List[Hint] = []
        self.wordpool: WordPoolDistribution = word_pool_distribution
        self.abort_reason = ""
        self.repeation=repeation
        self.quick_delete = quick_delete

        # Helper class that controls sending, indexing, editing and deletion of messages
        self.message_sender = MessageSender(self.channel.guild, channel)

        # Helper class to handle the phases
        self.phase_handler = PhaseHandler(self)

        # The admin mode is for the case that the user is a admin. He will be reminded to move to another channel,
        # and messages with tips will get cleared before guessing. If no argument is given, we just check whether
        # the guesser has admin privileges and choose the mode smart, but mode can be overwritten with a bool
        self.admin_mode = admin_mode
        self.admin_channel: discord.TextChannel = None

        # List of participants that play the game
        self.closed_game = bool(participants)  # Whether the participant list was given before start of the game
        self.participants: List[discord.Member] = participants
        if self.guesser in self.participants:
            self.participants.remove(self.guesser)  # Remove guesser from participants

        # Parse the expected_tips_person:
        if expected_tips_per_person != 0:
            self.expected_tips_per_person = expected_tips_per_person  # Argument was given
        else:
            # Argument was not given. According to member count, expect a certain number of tips:
            if len(participants) == 1:
                self.expected_tips_per_person = 3  # One player -> 3 Tips
            elif len(participants) == 2:
                self.expected_tips_per_person = 2  # 2 players -> 2 Tips
            else:
                self.expected_tips_per_person = 1  # Default value for tips

        print(f"Participants of this round: {self.participants}, game is in closed mode = {self.closed_game}")

        self.id = random.getrandbits(64)
        self.aborted = False
        self.role_given = False
        self.role: discord.Role = None
        self.summary_message: discord.Message = None
        self.phase = Phase.initialised
        self.won = None
        self.bot = bot
        self.clearing = True
        print(f'Game started in channel {self.channel} by user {self.guesser}')
        logger.info(f'Initialised game with id {self.id} in channel {self.channel.name}.')

    def game_prefix(self):
        return f'[Game {self.id}] '

    def logger_inform_phase(self):
        logger.info(f'{self.game_prefix()}Started phase {self.phase}')

    def play(self):
        self.phase_handler.advance_to_phase(Phase.preparation)

    @tasks.loop(count=1)
    async def preparation(self):
        self.logger_inform_phase()
        await self.message_sender.send_message(output.round_started(
            repeation=self.repeation, guesser=self.guesser, closed_game=self.closed_game
        ), reaction=False)
        await self.remove_guesser_from_channel()

        # We now have to activate the admin_mode if it is a) explicitly enabled or b) not specified, but the
        # guesser can still read messages in the channel
        self.guesser = await self.guesser.guild.fetch_member(self.guesser.id)
        permissions = self.guesser.permissions_in(self.channel)  # Get permissions of the user in the channel
        if (self.admin_mode is None and permissions and permissions.read_messages) or self.admin_mode is True:
            await self.make_channel_for_admin()  # Creating admin channel
            self.phase_handler.advance_to_phase(Phase.wait_for_admin)
        else:
            self.phase_handler.advance_to_phase(Phase.show_word)

    @tasks.loop(count=1)
    async def wait_for_admin(self):
        self.logger_inform_phase()
        if await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.admin_welcome,
                member=self.guesser):
            self.phase_handler.advance_to_phase(Phase.show_word)
        else:
            logger.warn(f'{self.game_prefix()}Admin did not confirm second channel, aborting.')
            self.phase_handler.advance_to_phase(Phase.aborting)
            # await self.abort("")  # TODO: add output message

    @tasks.loop(count=1)
    async def show_word(self):
        self.logger_inform_phase()
        self.word = getword(self.wordpool)  # generate a word
        # Show the word:
        await self.message_sender.send_message(
            embed=output.announce_word(self.guesser, self.word),
            key=Key.show_word
        )
        self.phase_handler.advance_to_phase(Phase.wait_collect_hints)

    @tasks.loop(count=1)
    async def wait_collect_hints(self):
        self.logger_inform_phase()
        if not await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.show_word
        ):
            logger.warn(f'{self.game_prefix()}Did not get confirmation that Phase {self.phase} is done, aborting.')
            self.abort_reason = output.collect_hints_phase_not_ended()
            self.phase_handler.advance_to_phase(Phase.aborting)
        self.phase_handler.advance_to_phase(Phase.show_all_hints_to_players)

    @tasks.loop(count=1)
    async def show_all_hints_to_players(self):
        self.logger_inform_phase()

        # Inform users that hint phase has ended
        await self.message_sender.send_message(
            embed=output.announce_hint_phase_ended(dismiss_emoji=DISMISS_EMOJI),
            reaction=False,
            group=Group.filter_hint
        )

        # Show all hints with possible reactions
        for hint in self.hints:
            hint_message = await self.message_sender.send_message(
                embed=output.hint_to_review(hint.hint_message, hint.author),
                emoji=DISMISS_EMOJI,
                group=Group.filter_hint
            )
            # TODO move keeping track of hint -> message to MessageHandler
            hint.message_id = hint_message.id  # Store the message id in the corresponding hint

        # Show message to confirm that invalid tips have been removed
        await self.message_sender.send_message(embed=output.confirm_massage_all_hints_reviewed(),
                                               key=Key.filter_hint_finished
                                               )
        self.phase_handler.advance_to_phase(Phase.wait_for_hints_reviewed)

    @tasks.loop(count=1)
    async def wait_for_hints_reviewed(self):
        self.logger_inform_phase()
        if not await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.filter_hint_finished):
            logger.warn(f'{self.game_prefix()}Did not get confirmation that invalid tips have been marked, aborting.')
            self.abort_reason = output.review_hints_phase_not_ended()
            self.phase_handler.advance_to_phase(Phase.aborting)
        self.phase_handler.advance_to_phase(Phase.compute_valid_hints)

    @tasks.loop(count=1)
    async def compute_valid_hints(self):
        self.logger_inform_phase()
        # Iterate over hints and check if they are valid
        for hint in self.hints:
            try:
                message = await self.channel.fetch_message(hint.message_id)
            except discord.NotFound:
                if self.aborted:
                    return  # Program has stopped already, nothing to do
                else:
                    print('Fetching hints failed, hint already deleted, aborting')
                    self.phase_handler.advance_to_phase(Phase.stopping)
                    return
            for reaction in message.reactions:
                if reaction.emoji == DISMISS_EMOJI and reaction.count > 1:
                    hint.valid = False
        if self.admin_mode:
            self.phase_handler.advance_to_phase(Phase.inform_admin_to_reenter)
        else:
            self.phase_handler.advance_to_phase(Phase.remove_role_from_guesser)

    @tasks.loop(count=1)
    async def inform_admin_to_reenter(self):
        self.logger_inform_phase()
        # Deleting all shown hints before admin can enter the channel
        await self.message_sender.message_handler.delete_group(Group.filter_hint)
        # Inform admin to enter the channel
        await self.message_sender.send_message(channel=self.admin_channel,
                                               embed=output.inform_admin_to_reenter_channel(channel=self.channel),
                                               reaction=False,
                                               key=Key.admin_inform_reenter
                                               )
        self.phase_handler.advance_to_phase(Phase.remove_role_from_guesser)

    @tasks.loop(count=1)
    async def remove_role_from_guesser(self):
        self.logger_inform_phase()
        await self.add_guesser_to_channel()
        self.phase_handler.advance_to_phase(Phase.show_valid_hints)

    @tasks.loop(count=1)
    async def show_valid_hints(self):
        self.logger_inform_phase()
        await self.message_sender.send_message(embed=output.hints(self.hints),
                                               reaction=False,
                                               normal_text=output.hints_top(self.guesser),
                                               key=Key.show_hints_to_guesser)
        self.phase_handler.advance_to_phase(Phase.wait_for_guess)

    @tasks.loop(count=1)
    async def wait_for_guess(self):
        self.logger_inform_phase()
        if self.quick_delete:
            self.phase_handler.start_task(
                Phase.clear_messages,
                preserve_groups=[Group.other_bot, Group.user_chat],
                preserve_keys=[Key.summary, Key.abort, Key.show_hints_to_guesser]
            )  # Clearing messages in background can already start
        guess = await self.wait_for_reaction_from_user(self.guesser)  # TODO make this better

        # Check if we got a guess
        if guess is None:
            print('No guess found, aborting')  # TODO better log here, also better function!
            return
        print(f'Guess is {guess}')
        self.message_sender.message_handler.add_special_message(message=guess, key=Key.guess)
        # future: don't delete guess immediately but make it edible ?
        self.guess = guess.content
        self.won = evaluate(guess.content, self.word)  # TODO: have better comparing function
        self.phase_handler.advance_to_phase(Phase.show_summary)

    @tasks.loop(count=1)
    async def show_summary(self):
        self.logger_inform_phase()
        await self.message_sender.send_message(
            embed=output.summary(self.won, self.word, self.guess, self.guesser, PREFIX, self.hints),
            key=Key.summary,
            emoji=[PLAY_AGAIN_CLOSED_EMOJI,PLAY_AGAIN_OPEN_EMOJI]
        )  # TODO add other emojis?

        self.phase_handler.start_task(Phase.wait_for_play_again_in_closed_mode)
        self.phase_handler.start_task(Phase.wait_for_stop_game_after_timeout)
        self.phase_handler.start_task(Phase.wait_for_play_again_in_open_mode)

    @tasks.loop(count=1)
    async def wait_for_stop_game_after_timeout(self):
        logger.info(f'{self.game_prefix()}Game is open for {DEFAULT_TIMEOUT} seconds, closing then')
        await asyncio.sleep(DEFAULT_TIMEOUT)
        self.phase_handler.advance_to_phase(Phase.stopping)

    @tasks.loop(count=1)
    async def wait_for_play_again_in_closed_mode(self):
        if await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.summary,
                emoji=PLAY_AGAIN_EMOJI,
                timeout=0,
        ):
            self.phase_handler.advance_to_phase(Phase.stopping)
            self.phase_handler.start_task(Phase.play_new_game)

    @tasks.loop(count=1)
    async def clear_messages(self, preserve_keys: List[Key], preserve_groups: List[Group]):
        await self.message_sender.message_handler.clear_messages(
            preserve_groups=preserve_groups,
            preserve_keys=preserve_keys
        )

    @tasks.loop(count=1)
    async def play_new_game(self):
        # Start a new game with the same people
        if len(self.participants) == 0:
            await self.message_sender.send_message(embed=output.warn_participant_list_empty(), reaction=False,
            group=Group.warn)
            return
        guesser = self.participants.pop(0)
        self.participants.append(self.guesser)
        game = Game(self.channel, guesser=guesser, bot=self.bot,
                    word_pool_distribution=self.wordpool,
                    participants=self.participants)
        games.append(game)
        game.play()

    @tasks.loop(count=1)
    async def aborting(self, reason: str, member: discord.Member = None):
        await self.message_sender.send_message(
            embed=output.abort(reason, self.word, self.guesser, member),
            reaction=False,
            key=Key.abort
        )
        if self.role_given:
            await self.add_guesser_to_channel()
        self.phase_handler.advance_to_phase(Phase.stopping)  # Stop the game now

    @tasks.loop(count=1)
    async def stopping(self):
        if self.admin_mode:
            try:
                await self.admin_channel.delete()
            except discord.NotFound:
                logger.warn(f'{self.game_prefix()}Admin channel was deleted manually. Please let me do this job!')
            # Delete admin channel from database
            dba.del_resource(self.channel.guild.id, value=self.admin_channel.id, resource_type="text_channel")
        await self.message_sender.message_handler.clear_messages(
            preserve_keys=[Key.summary, Key.abort],
            preserve_groups=[Group.other_bot, Group.user_chat]
        )  # Clearing (almost) everything the bot has sent
        # TODO: Remove reactions from summary message here
        self.phase = Phase.stopped
        global games
        try:
            games.remove(self)
        except ValueError:  # Safety feature if stop() is called multiple times (e.g. by abort() and by play())
            logger.warn(f'{self.game_prefix()}Game has already been removed from global variables')

    async def wait_for_reaction_from_user(self, member):
        def check(message):
            return message.author == self.guesser and message.channel == self.channel

        try:
            message = await self.bot.wait_for('message', timeout=DEFAULT_TIMEOUT, check=check)
        except asyncio.TimeoutError:
            self.abort_reason = output.not_guessed()
            self.phase_handler.advance_to_phase(Phase.aborting)
            return None
        return message

    # Helper methods to manage user access to channel
    async def remove_guesser_from_channel(self):
        # TODO: create a proper role for this channel and store it in self.role
        self.role = await self.channel.guild.create_role(name=ROLE_NAME + f": #{self.channel.name}")
        await self.role.edit(color=ut.orange)
        await self.channel.set_permissions(self.role, read_messages=False)
        await self.guesser.add_roles(self.role)
        dba.add_resource(self.channel.guild.id, self.role.id)
        self.role_given = True

    async def make_channel_for_admin(self):
        self.admin_mode = True  # Mark this game as having admin mode
        # Create channel for the admin in proper category
        if self.channel.category:
            self.admin_channel = await self.channel.category.create_text_channel(
                name=output.admin_channel_name(self.channel),
                reason="Create waiting channel"
            )
        else:
            self.admin_channel = await self.channel.guild.create_text_channel(
                name=output.admin_channel_name(self.channel.name),
                reason="Create waiting channel"
            )

        # Add channel to created resources so we can delete it even after restart
        dba.add_resource(self.channel.guild.id, self.admin_channel.id, resource_type="text_channel")
        # Give read access to the bot in the channel
        await self.admin_channel.set_permissions(self.channel.guild.me,
                                                 reason="Bot needs to have write access in the channel",
                                                 read_messages=True)
        # Hide channel to other users
        await self.admin_channel.set_permissions(self.channel.guild.default_role,
                                                 reason="Make admin channel only visible to admin himself",
                                                 read_messages=False)

        # Show message so that Admin can quickly jump to the channel
        await self.message_sender.send_message(reaction=False,
                                               embed=output.admin_mode_wait(self.guesser, self.admin_channel),
                                               key=Key.admin_wait)

        await self.message_sender.send_message(
            embed=output.admin_welcome(self.guesser, emoji=CHECK_EMOJI),
            channel=self.admin_channel,
            normal_text=self.guesser.mention,
            reaction=True,
            key=Key.admin_welcome
        )

    # External methods called by listeners
    async def add_hint(self, message):
        # We need to check if the author of the message is a participant of the game:
        if self.closed_game:
            if message.author not in self.participants:
                await self.message_sender.send_message(
                    embed=output.not_participant_warning(message.author),
                    reaction=False,
                    group=Group.warn
                )
                return
        else:
            if message.author not in self.participants:
                self.participants.append(message.author)
                print(f'Added {message.author} as a participant')
        # Now, add the hint properly
        self.hints.append(Hint(message))
        await self.message_sender.edit_message(
            key=Key.show_word,
            embed=output.announce_word_updated(self.guesser, self.word, self.hints)
        )  # Update the show_word message to display the person that gave the hint
        print(self.closed_game)
        # In a closed game, check whether everyone has already reacted
        if self.closed_game:
            gave_tip = [hint.author for hint in self.hints]
            print(f"These people gave a tip already: {[compute_proper_nickname(person) for person in gave_tip]}")
            print(f"These people participate: {[compute_proper_nickname(person) for person in self.participants]}")
            for participant in self.participants:
                if participant not in gave_tip and participant != self.guesser:
                    return
            # Skip hint phase as we got every tip already
            self.phase_handler.advance_to_phase(Phase.show_all_hints_to_players)

    async def add_guesser_to_channel(self):
        guild = await self.bot.fetch_guild(self.channel.guild.id)
        self.role = guild.get_role(self.role.id)
        print('Role deleted, user should be back in channel')
        await self.guesser.remove_roles(self.role)
        await self.role.delete()
        dba.del_resource(self.channel.guild.id, value=self.role.id)
        self.role_given = False
        print('Added user back to channel')


# End of Class Game


def find_game(channel: discord.TextChannel) -> Union[Game, None]:
    # Gives back the game running in the current channel, None else
    global games
    if games is None:
        return None
    for game in games:
        if game.channel.id == channel.id:
            return game


def print_games():
    for game in games:
        print(f'Found game in {game.channel} in Phase {game.phase}')


class PhaseHandler:
    def __init__(self, game: Game):
        self.game = game
        self.task_dictionary = {
            Phase.initialised: None,
            Phase.preparation: game.preparation,
            Phase.wait_for_admin: game.wait_for_admin,
            Phase.show_word: game.show_word,
            Phase.wait_collect_hints: game.wait_collect_hints,
            Phase.show_all_hints_to_players: game.show_all_hints_to_players,
            Phase.wait_for_hints_reviewed: game.wait_for_hints_reviewed,
            Phase.compute_valid_hints: game.compute_valid_hints,
            Phase.inform_admin_to_reenter: game.inform_admin_to_reenter,
            Phase.remove_role_from_guesser: game.remove_role_from_guesser,
            Phase.show_valid_hints: game.show_valid_hints,
            Phase.wait_for_guess: game.wait_for_guess,
            # future: Phase.show_guess
            Phase.show_summary: game.show_summary,
            Phase.stopping: game.stopping,
            Phase.stopped: None,  # There is no task in this phase

            Phase.wait_for_play_again_in_closed_mode: game.wait_for_play_again_in_closed_mode,
            # Phase.wait_for_play_again_in_open_mode: game.wait_for_play_again_in_open_mode # future
            Phase.wait_for_stop_game_after_timeout: game.wait_for_stop_game_after_timeout,
            Phase.clear_messages: game.clear_messages,
            Phase.play_new_game: game.play_new_game
        }

    def cancel_all(self, cancel_tasks=False):
        for phase in self.task_dictionary.keys():
            if (phase.value < 1000 or cancel_tasks) and self.task_dictionary[phase]:
                self.task_dictionary[phase].cancel()

    def advance_to_phase(self, phase: Phase):
        if phase.value >= 1000:
            logger.error(f'{self.game.game_prefix()}Tried to advance to Phase {phase}, but phase number is too high. '
                         f'Aborting phase advance')
            return
        if self.game.phase.value > phase.value:
            logger.error(f'{self.game.game_prefix()}Tried to advance to Phase {phase}, but game is already '
                         f'in phase {self.game.phase}, cannot go back in time. Aborting phase start.')
            return
        elif self.game.phase == phase:
            logger.warn(f'{self.game.game_prefix()}Tried to advance to Phase {phase}, but game is already in that phase.'
                        f'Canot start phase a second time.')
            return
        else:  # Start the new phase
            self.game.phase = phase
            self.cancel_all(phase == Phase.stopping)
            if self.task_dictionary[phase]:
                self.task_dictionary[phase].start()

    def start_task(self, phase: Phase, **kwargs):
        if self.task_dictionary[phase].is_running():
            logger.error(f'{self.game.game_prefix()}Task {phase} is already running, cannot start it twice. '
                         f'Aborting task start.')
            return
        else:
            self.task_dictionary[phase].start(**kwargs)
            logger.info(f'Started task {phase}')
