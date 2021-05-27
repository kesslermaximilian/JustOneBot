import asyncio
import random
from typing import List, Union

import discord
from discord.ext import tasks

import database.db_access as dba
import game_management.output as output
import utils as ut
from environment import PLAY_AGAIN_CLOSED_EMOJI, PLAY_AGAIN_OPEN_EMOJI, PREFIX, CHECK_EMOJI, DISMISS_EMOJI, \
    DEFAULT_TIMEOUT, ROLE_NAME
from game_management.messages import MessageSender
from game_management.tools import Hint, Phase, evaluate, Key, Group
from game_management.word_pools import getword, WordPoolDistribution
from log_setup import logger

games = []  # Global variable (what a shame!) -> Where can i better put this and e.g. use a dictionary for channels?


class Game:
    def __init__(self, channel: discord.TextChannel, guesser: discord.Member, bot,
                 word_pool_distribution: WordPoolDistribution, admin_mode: Union[None, bool] = None,
                 participants: List[discord.Member] = [], repeation=False,
                 quick_delete=True, expected_tips_per_person=0):
        """

        @param channel: The channel to run the game in
        @param guesser: The person who has to guess a word
        @param bot: The bot instantiating this game. Needed for the wait_for method
        @param word_pool_distribution: The distribution of the word pools to be drawn of
        @param admin_mode: Whether to create an extra channel for the admin. Setting to True or False will enable /
                disable the mode, setting to None will check for permissions of the guesser in the channel and
                choose the mode 'smartly'
        @param participants: a List of members to participate in this round.
                If given, only these participants can give hints or abort the game, and the game automatically checks
                if each participant has given their hint(s) to proceed with the next phase after collecting hints
                If left empty, everyone can participate and interact with the round arbitrarily.
        @param repeation: Whether this game has been called as a repeating game by a previous one. This changes the
                info message sent at the beginning of the game to explain why the game has started
        @param quick_delete: whether to delete messages the game has sent already while waiting for a guess. This
                speeds up the bot as we can spread the API calls over a larger amount of time, but potentially
                one prefers to have the chat cleared at the end of the game for a cleaner game experience while
                the game is active. For now, this parameter is always set to True.
        @param expected_tips_per_person: The number of tips the game expects each player to give in the hint phase
                Only applies to games that have a list of participants.
                If so, the game advances to the next phase after collecting hints automatically once each participant
                has given (at least) the number of expected hints.
                If set to a nonzero value, this parameter is used. If set to zero, the game chooses the number of tips
                according on the number of players playing in the game as three, two and one hints for one, two and
                at least three players, respectively
        """
        self.channel = channel
        self.guesser = guesser
        self.guess = ""
        self.word = ""
        self.hints: List[Hint] = []
        self.wordpool: WordPoolDistribution = word_pool_distribution
        self.abort_reason = ""
        self.repeation = repeation
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
        logger.info(f'{self.game_prefix()}Initialised game with {len(self.participants)} participants. '
                    f'Wordpool distribution: {self.wordpool}, admin mode: {self.admin_mode}, '
                    f'expected hints per participant: {self.expected_tips_per_person}, '
                    f'repeation: {self.repeation}, '
                    f'quick delete mode: {self.quick_delete}'
                    )

    def game_prefix(self):
        """

        @return: The prefix of the game containing the game id used for the logger
        """
        return f'[Game {self.id}] '

    def logger_inform_phase(self):
        """
        logs the phase of the current game
        """
        logger.info(f'{self.game_prefix()}Started phase {self.phase}')

    def play(self):
        """
        used to start the game after it has been instantiated
        """
        self.phase_handler.advance_to_phase(Phase.preparation)

    @tasks.loop(count=1)
    async def preparation(self):
        """
        Preparation phase of the game. Includes giving a role to the guesser, setting up permissions for the channel
        and finding out whether to play this game in admin_mode if needed.
        Starts Phase.wait_for_admin or Phase.show_word after finishing
        """
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
        """
        Phase whilst waiting for confirmation of the admin that he has left the channel.
        Waits for a reaction of the guesser to the sent message in the admin channel
        Starts Phase.show_word or aborts the game due to timeout
        """
        self.logger_inform_phase()
        if await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.admin_welcome,
                member=self.guesser):
            self.phase_handler.advance_to_phase(Phase.show_word)
        else:
            logger.warn(f'{self.game_prefix}Admin did not confirm second channel, aborting.')
            self.phase_handler.advance_to_phase(Phase.aborting)
            # await self.abort("")  # TODO: add output message

    @tasks.loop(count=1)
    async def show_word(self):
        """
        Phase to show the word in the corresponding channel.
        Starts Phase.wait_collect_hints
        """
        self.logger_inform_phase()
        self.word = getword(self.wordpool)  # generate a word
        # Show the word:
        await self.message_sender.send_message(
            embed=output.announce_word(self.guesser, self.word, closed_game=self.closed_game,
                                       expected_number_of_tips=self.expected_tips_per_person),
            key=Key.show_word
        )
        self.phase_handler.advance_to_phase(Phase.wait_collect_hints)

    @tasks.loop(count=1)
    async def wait_collect_hints(self):
        """
        Phase for collecting hints. This method itself only waits for a reaction of the participants via emoji
        and then starts Phase.show_all_hints_to_players.
        Note that the processing of the hints is done in listener on_message
        """
        self.logger_inform_phase()
        if not await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.show_word
        ):
            logger.warn(f'{self.game_prefix}Did not get confirmation that Phase {self.phase} is done, aborting.')
            self.abort_reason = output.collect_hints_phase_not_ended()
            self.phase_handler.advance_to_phase(Phase.aborting)
        self.phase_handler.advance_to_phase(Phase.show_all_hints_to_players)

    @tasks.loop(count=1)
    async def show_all_hints_to_players(self):
        """
        Phase for showing the given hints to the players (but not the guesser) to have them review the tips.
        Prints info message that collecting hints has ended, then prints all given hints, and prints info message
        asking people to confirm their choices if ready
        Starts Phase.wait_for_hints_reviewed
        """
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
        """
        Waits for confirmation that hints have been reviewed.
        Starts Phase.compute_valid_hints
        """
        self.logger_inform_phase()
        if not await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.filter_hint_finished):
            logger.warn(f'{self.game_prefix}Did not get confirmation that invalid tips have been marked, aborting.')
            self.abort_reason = output.review_hints_phase_not_ended()
            self.phase_handler.advance_to_phase(Phase.aborting)
        self.phase_handler.advance_to_phase(Phase.compute_valid_hints)

    @tasks.loop(count=1)
    async def compute_valid_hints(self):
        """
        Fetches reactions to all printed hints and updates the hints correspondingly, if they have been flagged
        Starts Phase.inform_admin_to_reenter if in admin mode, else Phase.remove_role_from_guesser
        @return: nothing, only used to stop execution
        """
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
        """
        Deletes all shown hints in the main channel
        Prints a message in the admin channel that informs the admin to reenter the main channel of the game, as the
        game is ready for guessing.
        Starts Phase.remove_role_from_guesser
        """
        self.logger_inform_phase()
        # Deleting all shown hints before admin can enter the channel
        await self.message_sender.message_handler.delete_group(Group.filter_hint)
        await self.message_sender.message_handler.delete_special_message(Key.show_word)
        # Inform admin to enter the channel
        await self.message_sender.send_message(channel=self.admin_channel,
                                               embed=output.inform_admin_to_reenter_channel(channel=self.channel),
                                               reaction=False,
                                               key=Key.admin_inform_reenter
                                               )
        self.phase_handler.advance_to_phase(Phase.remove_role_from_guesser)

    @tasks.loop(count=1)
    async def remove_role_from_guesser(self):
        """
        Removes the role from the guesser.
        Starts Phase.show_valid_hints
        """
        self.logger_inform_phase()
        await self.add_guesser_to_channel()
        self.phase_handler.advance_to_phase(Phase.show_valid_hints)

    @tasks.loop(count=1)
    async def show_valid_hints(self):
        """
        Prints a message showing the valid hints in the main channel
        starts Phase.wait_for_guess
        """
        self.logger_inform_phase()
        await self.message_sender.send_message(embed=output.hints(self.hints),
                                               reaction=False,
                                               normal_text=output.hints_top(self.guesser),
                                               key=Key.show_hints_to_guesser)
        self.phase_handler.advance_to_phase(Phase.wait_for_guess)

    @tasks.loop(count=1)
    async def wait_for_guess(self):
        """
        Waits for the guesser to give a guess. Computes whether game has been won or not
        Starts Phase.show_summary

        @return: The guess (as a Discord.Message) of the guesser
        """
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
        """
        Prints a pleasing summary of the round containing the word, guess, guesser and all hints (invalid hints are
        crossed out but shown) in the main channel for information
        Starts the tasks
            wait_for_play_again_in_closed_mode
            wait_for_play_again_in_open_mode
            wait_for_stop_game_after_timeout
        (in parallel)
        """
        self.logger_inform_phase()
        await self.message_sender.send_message(
            embed=output.summary(self.won, self.word, self.guess, self.guesser, PREFIX, self.hints),
            key=Key.summary,
            emoji=[PLAY_AGAIN_CLOSED_EMOJI, PLAY_AGAIN_OPEN_EMOJI]
        )  # TODO add other emojis?

        self.phase_handler.start_task(Phase.wait_for_play_again_in_closed_mode)
        self.phase_handler.start_task(Phase.wait_for_stop_game_after_timeout)
        self.phase_handler.start_task(Phase.wait_for_play_again_in_open_mode)

    @tasks.loop(count=1)
    async def wait_for_stop_game_after_timeout(self):
        """
        Takes a timer and stops the game after DEFAULT_TIMEOUT seconds if not cancelled before.
        This is to avoid users being locked away from channels if games are not being aborted.
        """
        logger.info(f'{self.game_prefix}Game is open for {DEFAULT_TIMEOUT} seconds, closing then')
        await asyncio.sleep(DEFAULT_TIMEOUT)
        self.phase_handler.advance_to_phase(Phase.stopping)

    @tasks.loop(count=1)
    async def wait_for_play_again_in_closed_mode(self):
        """
        Waits for a reaction to the summary message. If found (with emoji PLAY_AGAIN_CLOSED_EMOJI), starts a new
        game with the same participant list as the current one, rotating the guesser by one.
        Stops the current game
        Calls task play_new_game to start the new game
        """
        if await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.summary,
                emoji=PLAY_AGAIN_CLOSED_EMOJI,
                timeout=0,
        ):
            self.phase_handler.advance_to_phase(Phase.stopping)
            self.phase_handler.start_task(Phase.play_new_game)

    # TODO adjust this function
    @tasks.loop(count=1)
    async def wait_for_play_again_in_open_mode(self):
        """
        Waits for a reaction to the summary message. If found (with emoji PLAY_AGAIN_OPEN_EMOJI), starts a new
        game with empty participant list, i.e. everyone can participate in the new game.
        Stops the current game
        Calls task play_new_game to start the new game
        """
        if await self.message_sender.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.summary,
                emoji=PLAY_AGAIN_OPEN_EMOJI,
                timeout=0,
        ):
            self.phase_handler.advance_to_phase(Phase.stopping)
            self.phase_handler.start_task(Phase.play_new_game, closed_mode=False)

    @tasks.loop(count=1)
    async def clear_messages(self, preserve_keys: List[Key], preserve_groups: List[Group]):
        """
        Background task that clears the messages the current game has sent

        @param preserve_keys: List of Keys of the messages to exclude from clearing
        @param preserve_groups: List of Groups of the messages to exclude from clearing
        """
        await self.message_sender.message_handler.clear_messages(
            preserve_groups=preserve_groups,
            preserve_keys=preserve_keys
        )

    @tasks.loop(count=1)
    async def play_new_game(self, closed_mode=True):
        """
        Starts a new game with the same settings as the current one

        @param closed_mode: Whether to run the next game with a participant list (in closed_mode) or not
        @return: nothing, only used to end execution
        """
        # self.phase_handler.advance_to_phase(Phase.stopping)  # Stop the current game since we start a new one
        # Start a new game with the same people
        if len(self.participants) == 0:
            await self.message_sender.send_message(embed=output.warn_participant_list_empty(), reaction=False,
                                                   group=Group.warn)
            return
        guesser = self.participants.pop(0)
        self.participants.append(self.guesser)
        game = Game(self.channel, guesser=guesser, bot=self.bot,
                    word_pool_distribution=self.wordpool,
                    participants=self.participants if closed_mode else [],
                    repeation=closed_mode,
                    quick_delete=self.quick_delete, expected_tips_per_person=self.expected_tips_per_person,
                    )
        games.append(game)
        game.play()

    @tasks.loop(count=1)
    async def aborting(self):
        """
        Aborts the current game. This includes adding the guesser back to the channel
        prints an appropriate message why the game has been aborted using attribute self.abort_reason
        """
        await self.message_sender.send_message(
            embed=output.abort(self.abort_reason, self.word, self.guesser),
            reaction=False,
            key=Key.abort
        )
        if self.role_given:
            await self.add_guesser_to_channel()
        self.phase_handler.advance_to_phase(Phase.stopping)  # Stop the game now

    @tasks.loop(count=1)
    async def stopping(self):
        """
        Stops the current game. This includes deleting all resources, i.e. the admin channel (if exists), the created
        role. Clears all sent messages (except a known List of exceptions)
        """
        if self.admin_mode:
            try:
                if self.admin_channel:  # Admin channel could have been not created yet
                    await self.admin_channel.delete()
            except discord.NotFound:
                logger.warn(f'{self.game_prefix}Admin channel was deleted manually. Please let me do this job!')
            # Delete admin channel from database
            dba.del_resource(self.channel.guild.id, value=self.admin_channel.id, resource_type="text_channel")
            logger.info(f'{self.game_prefix()}Removed admin channel from database')
        await self.message_sender.message_handler.clear_messages(
            preserve_keys=[Key.summary, Key.abort],
            preserve_groups=[Group.other_bot, Group.user_chat]
        )  # Clearing (almost) everything the bot has sent
        # TODO: check if summary message was sent
        await self.message_sender.clear_reactions(key=Key.summary)
        await self.message_sender.edit_message(key=Key.summary, embed=output.summary(
            self.won, self.word, self.guess, self.guesser, PREFIX, self.hints,
            evaluate(self.word, self.guess) != self.won,
            show_explanation=False
        )
                                               )
        self.phase = Phase.stopped
        global games
        try:
            games.remove(self)
        except ValueError:  # Safety feature if stop() is called multiple times (e.g. by abort() and by play())
            logger.warn(f'{self.game_prefix}Game has already been removed from global variables')

    async def wait_for_reaction_from_user(self, member):
        """
        Waits for a reaction from a user. If timeout, aborts the current game.
        @param member: The member of whom one wants to look for a message
        @return: The message the user has sent.
        """
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
        """
        Removes the guesser from the current channel by assigning him a role. Manages the permissions of the role and
        the channel
        """
        # TODO: create a proper role for this channel and store it in self.role
        self.role = await self.channel.guild.create_role(name=ROLE_NAME + f": #{self.channel.name}")
        await self.role.edit(color=ut.orange)
        await self.channel.set_permissions(self.role, read_messages=False)
        await self.guesser.add_roles(self.role)
        dba.add_resource(self.channel.guild.id, self.role.id)
        logger.info(f'{self.game_prefix()}Added role to database.')
        self.role_given = True

    async def make_channel_for_admin(self):
        """
        Creates a new channel in the same Category as the main channel to have the admin wait there. Configures
        channel properly.
        """
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
        logger.info(f'{self.game_prefix()}Added admin channel to database')
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
        """
        Adds a hint to the current game. Is called externally by the listener on_message.
        If in closed_game mode, checks if all participants have given at least the required amount of hints. If yes,
        starts the next phase.
        @param message: The message to be interpreted as the hint
        @return:
        """
        # We need to check if the author of the message is a participant of the game:
        if self.closed_game:
            if message.author not in self.participants:
                await self.message_sender.send_message(
                    embed=output.not_participant_warning(message.author),
                    reaction=False,
                    group=Group.warn
                )
                logger.info(f'{self.game_prefix()}Ignored possible hint by non-participant')
                return
        else:
            if message.author not in self.participants:
                self.participants.append(message.author)
        # Now, add the hint properly
        self.hints.append(Hint(message))
        logger.info(f'{self.game_prefix()}Received a hint')
        await self.message_sender.edit_message(
            key=Key.show_word,
            embed=output.announce_word_updated(self.guesser, self.word, self.hints,
                                               closed_game=self.closed_game,
                                               expected_number_of_tips=self.expected_tips_per_person)
        )  # Update the show_word message to display the person that gave the hint
        print(self.closed_game)
        # In a closed game, check whether everyone has already reacted
        if self.closed_game:
            hints_per_person = {}
            for participant in self.participants:
                hints_per_person[participant] = 0
            for hint in self.hints:
                hints_per_person[hint.author] += 1
            for participant in self.participants:
                print(hints_per_person[participant])
                print(self.expected_tips_per_person)
                if hints_per_person[participant] < self.expected_tips_per_person:
                    return
            else:
                # Skip hint phase as we got every tip already
                logger.info(f'{self.game_prefix()}Skipping collecting hints as all participants gave enough hints.')
                self.phase_handler.advance_to_phase(Phase.show_all_hints_to_players)

    async def add_guesser_to_channel(self):
        """
        Adds the guesser back to the main channel
        """
        guild = await self.bot.fetch_guild(self.channel.guild.id)
        self.role = guild.get_role(self.role.id)
        print('Role deleted, user should be back in channel')
        await self.guesser.remove_roles(self.role)
        await self.role.delete()
        dba.del_resource(self.channel.guild.id, value=self.role.id)
        logger.info('f{self.game_prefix()}Removed role from database')
        self.role_given = False
        print('Added user back to channel')


# End of Class Game


def find_game(channel: discord.TextChannel) -> Union[Game, None]:
    """
    Finds a game in the global variable of all games running in the channel
    @param channel: The channel to be searched in
    @return: The game running in the channel (if any). None otherwise.
    """
    # Gives back the game running in the current channel, None else
    global games
    if games is None:
        return None
    for game in games:
        if game.channel.id == channel.id:
            return game


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
            Phase.aborting: game.aborting,
            Phase.stopping: game.stopping,
            Phase.stopped: None,  # There is no task in this phase

            Phase.wait_for_play_again_in_closed_mode: game.wait_for_play_again_in_closed_mode,
            Phase.wait_for_play_again_in_open_mode: game.wait_for_play_again_in_open_mode,
            Phase.wait_for_stop_game_after_timeout: game.wait_for_stop_game_after_timeout,
            Phase.clear_messages: game.clear_messages,
            Phase.play_new_game: game.play_new_game
        }

    def cancel_all(self, cancel_tasks=False):
        """
        Cancels all running phases of the game ond optionally tasks as well
        @param cancel_tasks: Whether to cancel the tasks as well
        """
        print(f'Cancelling all phases{" and tasks" if cancel_tasks else ""}')
        for phase in self.task_dictionary.keys():
            if (phase.value < 1000 or cancel_tasks) and self.task_dictionary[phase]:
                self.task_dictionary[phase].cancel()
        print('Clearing done')

    def advance_to_phase(self, phase: Phase):
        """
        Advances the game to the given phase while cancelling execution of other phases. Checks that phases only are
        applied in chronological order. If advancing to Phase.stopping, also all tasks are canceled.

        @param phase: The phase to advance the game to
        @return: nothing, only used for stopping execution
        """
        if phase.value >= 1000:
            logger.error(f'{self.game.game_prefix}Tried to advance to Phase {phase}, but phase number is too high. '
                         f'Aborting phase advance')
            return
        if self.game.phase.value > phase.value:
            logger.error(f'{self.game.game_prefix}Tried to advance to Phase {phase}, but game is already '
                         f'in phase {self.game.phase}, cannot go back in time. Aborting phase start.')
            return
        elif self.game.phase == phase:
            logger.warn(
                f'{self.game.game_prefix}Tried to advance to Phase {phase}, but game is already in that phase.'
                f'Cannot start phase a second time.')
            return
        else:  # Start the new phase
            self.game.phase = phase
            self.cancel_all(phase == Phase.stopping)
            if self.task_dictionary[phase]:
                self.task_dictionary[phase].start()

    def start_task(self, phase: Phase, **kwargs):
        """
        Starts a given task with some keyword arguments while checking that tasks don't run twice.

        @param phase: The phase of the task to start
        @param kwargs: Arbitrary list of keyword arguments. This will directly be passed to the called task
        @return: nothing, only used for stopping execution
        """
        if self.task_dictionary[phase].is_running():
            logger.error(f'{self.game.game_prefix}Task {phase} is already running, cannot start it twice. '
                         f'Aborting task start.')
            return
        else:
            self.task_dictionary[phase].start(**kwargs)
            logger.info(f'Started task {phase}')
