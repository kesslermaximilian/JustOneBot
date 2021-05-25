import random
import time

import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List, Union
import utils as ut

from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI, DEFAULT_TIMEOUT, ROLE_NAME, ROLE_COLOR
from game_management.tools import Hint, Phase, compute_proper_nickname, evaluate, hints2name_list, Key, Group

from game_management.word_pools import getword, WordPoolDistribution
from game_management.messages import MessageSender, MessageHandler
import asyncio
import database.db_access as dba
import game_management.output as output

games = []  # Global variable (what a shame!)


class Game:
    def __init__(self, channel: discord.TextChannel, guesser: discord.Member, bot
                 , word_pool_distribution: WordPoolDistribution, admin_mode: Union[None, bool] = None):
        self.channel = channel
        self.guesser = guesser
        self.guess = ""
        self.word = ""
        self.hints: List[Hint] = []
        self.wordpool: WordPoolDistribution = word_pool_distribution
        self.show_word_message = None

        self.message_sender = MessageSender(self.channel.guild, channel)

        # The admin mode is for the case that the user is a admin. He will be reminded to move to another channel,
        # and messages with tips will get cleared before guessing. If no argument is given, we just check whether
        # the guesser has admin privileges and choose the mode smart, but mode can be overwritten with a bool
        self.admin_mode = admin_mode
        self.admin_channel: discord.TextChannel = None

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

    async def play(self):  # Main method to control the flow of a game
        # TODO: would be nice to have this as a task - to make it stoppable
        await self.remove_guesser_from_channel()

        # We now have to activate the admin_mode if it is a) explicitly enabled or b) not specified, but the
        # guesser can still read messages in the channel
        self.guesser = await self.guesser.guild.fetch_member(self.guesser.id)
        permissions = self.guesser.permissions_in(self.channel)  # Get permissions of the user in the channel
        if (self.admin_mode is None and permissions and permissions.read_messages) or self.admin_mode is True:
            if not await self.make_channel_for_admin():
                return

        #  Now, we can safely start the round

        self.word = getword(self.wordpool)  # generate a word
        # Show the word
        await self.message_sender.send_message(embed=output.announce_word(self.guesser, self.word), key=Key.show_word)

        self.phase = Phase.get_hints  # Now waiting for hints
        if not await self.message_sender.message_handler.wait_for_reaction_to_message(bot=self.bot,
                                                                                      message_key=Key.show_word):  # Wait for end of hint phase
            print('Did not get tips within time, fast-forwarding')
            return

        self.phase = Phase.filter_hints  # Now showing answers and filtering hints
        await self.show_answers()

        if not await self.message_sender.message_handler.wait_for_reaction_to_message(
                bot=self.bot,
                message_key=Key.filter_hint_finished):
            print('Did not get confirmation of marked double tips within time, fast-forwarding')
            return

        # Iterate over hints and check if they are valid

        for hint in self.hints:
            try:
                message = await self.channel.fetch_message(hint.message_id)
            except discord.NotFound:
                if self.aborted:
                    return  # Program has stopped already, nothing to do
                else:
                    print('Fetching hints failed, hint already deleted, aborting')
                    await self.stop()
                    return
            for reaction in message.reactions:
                if reaction.emoji == DISMISS_EMOJI and reaction.count > 1:
                    hint.valid = False

        self.phase = Phase.show_hints
        if self.admin_mode:
            # Deleting all shown hints before admin can enter the channel
            await self.message_sender.message_handler.delete_group(Group.filter_hint)
            # Inform admin to enter the channel
            await self.message_sender.send_message(channel=self.admin_channel,
                                                   embed=output.inform_admin_to_reenter_channel(channel=self.channel),
                                                   reaction=False,
                                                   key=Key.admin_inform_reenter
                                                   )
        # Add guesser back to channel
        await self.add_guesser_to_channel()
        print('Added user back to channel')

        # Show hints to guesser
        await self.message_sender.send_message(embed=output.hints(self.hints),
                                               reaction=False,
                                               normal_text=output.hints_top(self.guesser),
                                               key=Key.show_hints_to_guesser)

        # Wait for guess
        guess = await self.wait_for_reaction_from_user(self.guesser)

        # Check if we got a guess
        if guess is None:
            print('No guess found, aborting')
            return

        # self.message_sender.message_handler.add_special_message(message=guess, key=Key.guess)  # For now useless.
        # future: don't delete guess immediately but make it edible TODO

        # Evaluate
        self.guess = guess.content
        self.phase = Phase.evaluation  # Start evaluation phase
        self.won = evaluate(guess.content, self.word)  # TODO: have better comparing function

        # Show summary
        await self.message_sender.send_message(
            embed=output.summary(self.won, self.word, self.guess, self.guesser, PREFIX, self.hints)
        )

        self.phase = Phase.finished
        #  Clear history
        await self.message_sender.message_handler.clear_all()  # TODO implement exceptions and options for clearing

        # Keep game open to make correct command possible
        await asyncio.sleep(30.0)

        # Stop the game
        await self.stop()

    async def show_answers(self):
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

    # Aborting the current round. Can be either called explicitly or by timeout
    async def abort(self, reason: str, member: discord.Member = None):
        if self.aborted:  # Clearing or aborting of the game already in progress
            return
        self.aborted = True  # First, mark this game as finished to avoid doubling aborts or stops
        await self.message_sender.send_message(
            embed=output.abort(reason, self.word, self.guesser, member),
            reaction=False,
            key=Key.abort
        )
        if self.role_given:
            await self.add_guesser_to_channel()
        await self.stop()

    async def stop(self):  # Used to stop a game (remove in from games variable)
        if self.phase == Phase.stopped:
            return
        print('stopping game')
        self.phase = Phase.stopped  # Start clearing, but new games can start yet
        if self.admin_mode:
            try:
                await self.admin_channel.delete()
            except discord.NotFound:
                print('Text Channel of admin has already been deleted')
            # Delete admin channel from database
            dba.del_resource(self.channel.guild.id, value=self.admin_channel.id, resource_type="text_channel")
        await self.message_sender.message_handler.clear_all()  # Clearing everything the bot has sent
        global games
        try:
            games.remove(self)
        except ValueError:  # Safety feature if stop() is called multiple times (e.g. by abort() and by play())
            return

    async def wait_for_reaction_from_user(self, member):
        def check(message):
            return message.author == self.guesser and message.channel == self.channel

        try:
            message = await self.bot.wait_for('message', timeout=DEFAULT_TIMEOUT, check=check)
        except asyncio.TimeoutError:
            await self.abort('TimeOut error: Nicht geraten')
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

    async def add_guesser_to_channel(self):
        guild = await self.bot.fetch_guild(self.channel.guild.id)
        self.role = guild.get_role(self.role.id)
        print('Role deleted, user should be back in channel')
        await self.guesser.remove_roles(self.role)
        print('bla')
        await self.role.delete()
        print('bla2')
        dba.del_resource(self.channel.guild.id, value=self.role.id)
        self.role_given = False

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
                name=output.admin_channel_name(),
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

        if not await self.message_sender.message_handler.wait_for_reaction_to_message(bot=self.bot,
                                                                                      message_key=Key.admin_welcome,
                                                                                      member=self.guesser):
            print('Admin did not leave the channel')
            return False
        return True

    # External methods called by listeners
    async def add_hint(self, message):
        self.hints.append(Hint(message))
        await self.message_sender.edit_message(
            key=Key.show_word,
            embed=output.announce_word_updated(self.guesser, self.word, self.hints)
        )


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
