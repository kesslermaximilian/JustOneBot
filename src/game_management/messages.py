import asyncio

import discord
import discord.ext
from typing import TypedDict, List, Union
from environment import CHECK_EMOJI, DISMISS_EMOJI, SKIP_EMOJI, DEFAULT_TIMEOUT
from game_management.tools import Key, Group
import game_management.output as output


class MessageHandler:  # Basic message handler for messages that one wants to send and later delete or fetch
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel, message_sender):
        self.guild: discord.Guild = guild
        self.default_channel: discord.TextChannel = default_channel
        self.message_sender: MessageSender = message_sender
        self.special_messages: TypedDict[Key, (int, int)] = {}  # Stores some special messages with keywords
        self.group_messages: TypedDict[Group, List[(int, int)]] = {}  # Stores groups of messages by their group names
        # Useful if we don't need to differentiate between a set of messages

    def add_message_to_group(self, message: discord.Message, group: Group = Group.default):
        try:
            self.group_messages[group].append((message.channel.id, message.id))
        except KeyError:
            self.group_messages[group] = [(message.channel.id, message.id)]

    def add_special_message(self, message: discord.Message, key: Key):
        try:  # Check if key is already used
            print(f'I already stored a message in the key {key} with message id {self.special_messages[key][1]}')
        except KeyError:
            self.special_messages[key] = (message.channel.id, message.id)

    async def delete_group(self, group: Group = Group.default):
        try:
            to_delete = self.group_messages[group].copy()
        except KeyError:
            print('No messages in group found')
            return
        self.group_messages[group] = []
        if to_delete is None:
            print('Group is already empty, nothing to delete here.')
            return
        for (channel_id, message_id) in to_delete:
            message = await self._fetch_message_from_channel(channel_id=channel_id, message_id=message_id)
            if message:
                await message.delete()

    async def _fetch_message_from_channel(self, channel_id, message_id):
        channel: discord.TextChannel = self.guild.get_channel(channel_id=channel_id)
        if channel is None:
            print('Channel not found while trying to fetch a message from channel. Ignoring')
            return None
        try:
            print(f'Returning message in channel {channel.name} with id {message_id}')
            message = await channel.fetch_message(message_id)
            return message
        except discord.NotFound:
            print('Tried to fetch message from channel that does not exist anymore')
            return None

    async def get_special_message(self, key: Key) -> Union[discord.Message, None]:
        print(f'Getting special message with key {key}')
        try:
            entry = self.special_messages[key]
        except KeyError:
            return None
        if entry is None:
            print(f'No entry for {key} in the database')
            return None
        (channel_id, message_id) = entry
        message = await self._fetch_message_from_channel(channel_id, message_id)
        return message

    async def delete_special_message(self, key: Key, pop=True):
        message: discord.Message = await self.get_special_message(key)
        if message is None:
            print(f'Failed to delete message with special key {key}')
            return
        else:
            await message.delete()
        if pop:
            self.special_messages.pop(key)

    async def clear_messages(self, preserve_keys: List[Key] = [], preserve_groups: List[Group] = []):
        print(self.group_messages)
        for group_key in self.group_messages.keys():
            if group_key not in preserve_groups:
                await self.delete_group(group_key)

        print(f"Special messages (dict): {self.special_messages}\n")
        special_message_keys = [special_message_key for special_message_key in self.special_messages.keys()]
        for special_message_key in special_message_keys:
            print(f"Checking key {special_message_key} within list {preserve_keys}")
            if special_message_key not in preserve_keys:
                await self.delete_special_message(special_message_key, pop=True)


class MessageSender:
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel):
        self.guild = guild
        self.default_channel = default_channel
        self.message_handler = MessageHandler(guild=guild, default_channel=default_channel, message_sender=self)

    async def send_message(self, embed: Union[None, discord.Embed], normal_text="", reaction=True, emoji=CHECK_EMOJI,
                           channel: Union[discord.TextChannel, None] = None,
                           key: Key = Key.invalid, group: Group = Group.default) -> discord.Message:
        """
        Sends a message in a channel and stores it in its message_handler and reacts to it with a given emoji if told
        to do so
        :param embed: The embedding of the message to send (can be empty)
        :param normal_text: The normal text of the message to send (can be empty)
        :param reaction: If a reaction is to be added
        :param emoji: The emoji used for the reaction
        :param channel: The channel to send the message in. Uses the own default_channel if not given
        :param key: The key to store the message. Used if this is a special message. If nonempty, turns off group storing
        :param group: The group to store the message in. Only used if no key is given.
        :return: The message that was just sent
        """
        if channel:
            message = await channel.send(normal_text, embed=embed)
        else:
            message = await self.default_channel.send(normal_text, embed=embed)
        if reaction:  # Only add reaction if prompted to do so
            await message.add_reaction(emoji)
        if key != Key.invalid:
            self.message_handler.add_special_message(message, key=key)
        else:
            self.message_handler.add_message_to_group(message=message, group=group)
        return message

    async def edit_message(self, key: Key, embed: Union[None, discord.Embed], normal_text=""):
        """
        Edits a message.

        :param key: key of the message to be edited
        :param embed: [Optional] new embed for the message. If not provided, the embedding stays the same
        :param normal_text: [Option] new text for the message. If not provided, the normal text stays the same
        :return:
        """
        message = await self.message_handler.get_special_message(key)
        if embed is None:
            if normal_text != "":
                await message.edit(normal_text=normal_text)
            else:
                print('Nothing to be edited')
        else:
            if normal_text != "":
                await message.edit(normal_text=normal_text,embed=embed)
            else:
                await message.edit(embed=embed)

    async def wait_for_reaction_to_message(self,
                                           bot: discord.ext.commands.Bot,
                                           message_key: Key,
                                           emoji=CHECK_EMOJI,
                                           member: Union[discord.Member, List[discord.Member], None] = None,
                                           warning_time=DEFAULT_TIMEOUT,
                                           timeout=60.0,
                                           react_to_bot=False,
                                           warning: discord.Embed = output.time_warning()) -> bool:
        """
        Method that waits for a reaction to a message while informing the user with proper warnings

        :param bot: The bot that waits for the reaction
        :param message_key: Key of the message that one wants to observe
        :param emoji: The reaction emoji one wants to wait for
        :param member: [Optional] the member or members of whom one wants to wait for a reaction
        :param warning_time: Time after warnings are sent
        :param timeout: Interval between warning and timeout
        :param react_to_bot: whether to react to bots as well. Disabled by default
        :param warning: The warning message to send
        :return:
        """

        message = await self.message_handler.get_special_message(key=message_key)

        def check(reaction, user):
            #  Only respond to reactions from non-bots with the correct emoji
            #  Optionally check if the user is the given member
            print('Checking reaction')
            if user.id == reaction.message.channel.guild.me.id and str(reaction.emoji) == SKIP_EMOJI:
                return True
            if member:
                # print(f'User that reacted has id {user}, reacted with {str(reaction.emoji)} to message with id' f'{
                # reaction.message.id}, while i wait for a reaction of {member.id} with {str(emoji)} to message with
                # id' f' {message.id}')
                if type(member) != list:
                    return user.id == member.id and str(reaction.emoji) == emoji and reaction.message == message
                else:
                    return user.id in [person.id for person in member] and str(reaction.emoji) == emoji and reaction.message == message
            else:
                return (not user.bot or react_to_bot) and str(reaction.emoji) == emoji and reaction.message == message

        print(f'waiting for reaction with key {message_key}{f" by {member.name}" if member else ""}')
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=warning_time, check=check)
            print('found reaction')
            return True  # Notify that reaction was found
        except asyncio.TimeoutError:
            if timeout == 0:
                return False
            print('No reaction, send warning')
            # TODO check if warning is appropiate, i.e. if the original message still exists. Else, abort this
            try:
                await self.send_message(normal_text=f"Hey, {member.mention if member else ''}",
                                                   embed=warning, reaction=False, channel=message.channel, group=Group.warn)
            except discord.NotFound:  # In case the channel does not exist anymore
                return False
            # Try a second time
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=timeout, check=check)
                return True  # Notify that recation was found
            except asyncio.TimeoutError:
                return False  # Notify that timeout has happened