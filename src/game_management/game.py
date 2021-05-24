import random
import time

import discord
from discord.ext import commands
from enum import Enum
from typing import NewType, List, Union
import utils as ut
from environment import PREFIX, CHECK_EMOJI, DISMISS_EMOJI, DEFAULT_TIMEOUT, ROLE_NAME, ROLE_COLOR
from game_management.tools import Hint, Phase, compute_proper_nickname, evaluate
from game_management.word_pools import getword, WordPoolDistribution
import asyncio
import database.db_access as dba

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

        # The admin mode is for the case that the user is a admin. He will be reminded to move to another channel,
        # and messages with tips will get cleared before guessing. If no argument is given, we just check whether
        # the guesser has admin privileges and choose the mode smart, but mode can be overwritten with a bool
        self.admin_mode = admin_mode
        self.admin_channel: discord.TextChannel= None

        self.id = random.getrandbits(64)
        self.aborted = False
        self.role_given = False
        self.role: discord.Role = None
        self.sent_messages = []
        self.summary_message: discord.Message = None
        self.phase = Phase.initialised
        self.won = None
        self.bot = bot
        self.clearing = True
        print(f'Game started in channel {self.channel} by user {self.guesser}')

    async def play(self):  # Main method to control the flow of a game
        # TODO: would be nice to have this as a task - to make it stoppable
        permissions = self.guesser.permissions_in(self.channel)  # Get permissions of the user in the channel
        # print(permissions)
        await self.remove_guesser_from_channel()
        # We now have to activate the admin_mode if it is a) explicitly enabled or b) not specified, but the
        # guesser can still read messages in the channel
        self.guesser = await self.guesser.guild.fetch_member(self.guesser.id)
        permissions = self.guesser.permissions_in(self.channel)  # Get permissions of the user in the channel
        # print(permissions)
        if (self.admin_mode is None and permissions and permissions.read_messages) or self.admin_mode is True:
            if not await self.make_channel_for_admin():
                return

        #  Now, we can safely start the round

        self.word = getword(self.wordpool)  # generate a word
        last_message = await self.show_word()  # Show the word

        self.phase = Phase.get_hints  # Now waiting for hints
        if not await self.wait_for_reaction_to_message(last_message):  # Wait for end of hint phase
            print('Did not get tips within time, fast-forwarding')
            return

        self.phase = Phase.filter_hints  # Now showing answers and filtering hints
        last_message = await self.show_answers()

        if not await self.wait_for_reaction_to_message(last_message):
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
            await self.clear_messages()
            await self.send_message(channel=self.admin_channel,
                                    embed=ut.make_embed(
                                        title=f"Du bist dran mit Raten!",
                                        value=f"Komm wieder in {self.channel.mention}, um das Wort zu erraten!",
                                        footer="Dieser Kanal wird automatisch wieder gelöscht."
                                    )
                                    )

        # Add guesser back to channel
        await self.add_guesser_to_channel()

        print('Added user back to channel')
        await self.show_hints()

        guess = await self.wait_for_reaction_from_user(self.guesser)

        if guess is None:
            print('No guess found, aborting')
            return
        self.sent_messages.append(guess)

        self.guess = guess.content
        self.phase = Phase.evaluation  # Start evaluation phase
        self.won = evaluate(guess.content, self.word)  # TODO: have better comparing function

        await self.show_summary()
        self.phase = Phase.finished
        await self.clear_messages()

        # time.sleep(60.0)  # Go to sleep one minute, in which the result of the round can be manually corrected

        await asyncio.sleep(30.0)

        await self.stop()

    async def show_word(self) -> discord.Message:
        return await self.send_message(
            embed=ut.make_embed(
                name='Neue Runde JustOne',
                value=f"Das neue Wort lautet `{self.word}`.",
                color=ut.green,
                footer=f'Gebt Tipps ab, um {compute_proper_nickname(self.guesser)} zu helfen, das Wort zu erraten und klickt auf den Haken, wenn ihr fertig seid!'),
            )

    async def show_answers(self):
        # Inform users that hint phase has ended
        await self.send_message(
            embed=ut.make_embed(
                title='Tippphase beendet',
                name='Wählt evtl. doppelte Tipps aus!',
                color=ut.yellow
            ),
            reaction=False
        )

        # Show all hints with possible reactions
        for hint in self.hints:
            hint_message = await self.send_message(
                embed=ut.make_embed(
                    name=hint.hint_message,
                    value=compute_proper_nickname(hint.author)
                ),
                emoji=DISMISS_EMOJI
            )
            hint.message_id = hint_message.id  # Store the message id in the corresponding hint

        # Show message to confirm that invalid tips have been removed
        return await self.send_message(
             embed=ut.make_embed(
                  title='Alle doppelten Tipps markiert?',
                  name='Dann bestätigt hier!'
             )
        )

    async def show_hints(self):
        embed = discord.Embed(
            title=f'Es ist Zeit, zu raten!',
            description=f'Die folgenden Tipps wurden für dich abgegeben:',
        )

        for hint in self.hints:
            if hint.is_valid():
                embed.add_field(name=hint.hint_message, value=f'_{compute_proper_nickname(hint.author)}_')

        await self.send_message(embed, reaction=False, normal_text=f"Hey {self.guesser.mention}")

    async def show_summary(self, corrected=False):  # Todo implement version with corrected = True
        s_color = ut.green if self.won else ut.red
        embed = discord.Embed(
            title = 'Gewonnen!' if self.won else "Verloren",
            description = f"Das Wort war: `{self.word}`\n _{compute_proper_nickname(self.guesser)}_ hat `{self.guess}` geraten.",
            color = s_color,
        )

        for hint in self.hints:
            if hint.is_valid():
                embed.add_field(name=f'`{hint.hint_message}`', value=f'_{compute_proper_nickname(hint.author)}_')
            else:
                embed.add_field(name=f"~~`{hint.hint_message}`~~", value=f'_{compute_proper_nickname(hint.author)}_')

        if not self.won:
            embed.set_footer(text=f"Nutzt {PREFIX}correct, falls die Antwort dennoch richtig ist")

        if corrected:
            embed.set_footer(text=f"Danke für's Korrigieren! Entschudigung, dass ich misstrauisch war.")

        self.summary_message = await self.channel.send(embed=embed)

    async def abort(self, reason: str, member: discord.Member=None):  # Aborting the current round. Can be either called explicitly or by timeout
        if self.aborted:  # Clearing or aborting of the game already in progress
            return
        self.aborted = True  # First, mark this game as finished to avoid doubling aborts or stops
        value = f' von {member.mention}' if member else ""
        await self.channel.send(
            embed=ut.make_embed(
                title="Runde abgebrochen",
                value=f"Die Runde wurde{value} vorzeitig beendet:\n {reason}\n_{compute_proper_nickname(self.guesser)}_ hätte `{self.word}` erraten müssen",
                color=ut.red
            )
        )
        if self.role_given:
            await self.add_guesser_to_channel()
        await self.stop()

    async def clear_messages(self):  # Used to clear chat associated with this game
        print(f'Clearing {len(self.sent_messages)} messages')
        to_delete = self.sent_messages.copy()  # We make a local copy of the messages we want to clear
        self.sent_messages = []  # so that we can have multiple clearing functions at a time

        for message in to_delete:
            try:  # Safety feature, usually should not trigger
                await message.delete()
            except discord.NotFound:
                print(f' The message with content {message.content} could not be deleted')

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
        await self.clear_messages()
        global games
        try:
            games.remove(self)
        except ValueError:  # Safety feature if stop() is called multiple times (e.g. by abort() and by play())
            return

    # Helper methods to manage communication via messages and their reactions
    async def send_message(self, embed, reaction=True, emoji=CHECK_EMOJI, normal_text="",
                           channel: Union[discord.TextChannel, None] = None) -> discord.Message:
        if channel:
            message = await channel.send(normal_text, embed=embed)
        else:
            message = await self.channel.send(normal_text, embed=embed)
        if reaction:  # Only add reaction if prompted to do so
            await message.add_reaction(emoji)
        self.sent_messages.append(message)
        return message

    async def wait_for_reaction_to_message(self, message: discord.Message, emoji=CHECK_EMOJI,
                                           timeout=DEFAULT_TIMEOUT, member: Union[discord.Member, None] = None) -> bool:
        def check(reaction, user):
            #  Only respond to reactions from non-bots with the correct emoji
            #  Optionally check if the user is the given member
            if member:
                return user.id == member.id and str(reaction.emoji) == emoji and reaction.message == message
            else:
                return not user.bot and str(reaction.emoji) == emoji and reaction.message == message

        print(f'waiting for reaction to message {message.content}')
        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=timeout, check=check)
            print('found reaction')
        except asyncio.exceptions.TimeoutError:
            print('timeout error in wait for reaction')
            await self.abort('TimeOut error: Keine Reaktion auf letzte Nachricht')
            return False
        return True

    async def wait_for_reaction_from_user(self, member):
        def check(message):
            return message.author == self.guesser and message.channel == self.channel
        try:
            message = await self.bot.wait_for('message', timeout=DEFAULT_TIMEOUT, check=check)
        except asyncio.exceptions.TimeoutError:
            await self.abort('TimeOut error: Nicht geraten')
            return None
        return message

    # Helper methods to manage user access to channel
    async def remove_guesser_from_channel(self):
        # TODO: create a proper role for this channel and store it in self.role
        self.role = await self.channel.guild.create_role(name=ROLE_NAME + f": #{self.channel.name}")
        await self.role.edit(color=ROLE_COLOR)
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
            self.admin_channel = await self.channel.category.create_text_channel(f"{self.channel.name}-Warteraum",
                                                                                 reason="Create waiting channel")
        else:
            self.admin_channel = await self.channel.guild.create_text_channel(f"{self.channel.name}-Warteraum",
                                                                              reason="Create waiting channel")
        # Add channel to created resources so we can delete it even after restart
        dba.add_resource(self.channel.guild.id, self.admin_channel.id, resource_type="text_channel")
        # Give read access to the bot in the channel
        await self.admin_channel.set_permissions(self.channel.guild.me,
                                                 reason="Bots need to have write access in the channel",
                                                 read_messages=True)
        # Hide channel to other users
        await self.admin_channel.set_permissions(self.channel.guild.default_role,
                                                 reason="Make admin channel only visible to admin himself",
                                                 read_messages=False)

        # Show messages so that Admin can quickly jump to the channel
        await self.send_message(reaction=False,
                                embed=ut.make_embed(title="Einen Moment noch...",
                                                    value=f"Hey, {compute_proper_nickname(self.guesser)}, verlasse bitte selbst-"
                                                          f"ständig diesen Kanal, damit ich die Runde starten kann."
                                                          f" Bestätige in {self.admin_channel.mention} kurz, "
                                                          f"dass ich die Runde starten kann!")

                                )
        last_message = await self.send_message(ut.make_embed(
            title="Angekommen!",
            value=f"Hey, {self.guesser}! Du kannst in diesem Kanal warten, während dein Team Tipps für dich "
                  f"erstellt. Bitte reagiere mit {CHECK_EMOJI}, damit ich weiß, dass ich die Runde sicher "
                  f"starten kann. Hol dir Popcorn!"
        ),
            channel=self.admin_channel,
            normal_text=self.guesser.mention
        )
        if not await self.wait_for_reaction_to_message(last_message, member=self.guesser):
            print('Admin did not leave the channel')
            return False
        return True

    # External methods called by listeners
    def add_hint(self, message):
        self.hints.append(Hint(message))

# End of Class Game


def find_game(channel: discord.TextChannel) -> Union[Game,None]:
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