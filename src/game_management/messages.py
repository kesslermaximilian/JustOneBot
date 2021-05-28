import asyncio
from typing import List, Union

import discord
import discord.ext

import game_management.output as output
from environment import CHECK_EMOJI, SKIP_EMOJI, DEFAULT_TIMEOUT
from game_management.tools import Key, Group
from log_setup import logger


def message_handler_prefix():
    return '[Message Handler] '


class MessageHandler:  # Basic message handler for messages that one wants to send and later delete or fetch
    """
    Internal class for indexing messages a game has sent. Kind of like a small database
    """
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel):
        self.guild: discord.Guild = guild
        self.default_channel: discord.TextChannel = default_channel
        self.special_messages = {}  # Stores some special messages with keywords
        self.group_messages = {}  # Stores groups of messages by their group names
        logger.debug(f'{message_handler_prefix()}New message handler at guild {guild.id} with default channel '
                     f'{default_channel.id}')
        # Useful if we don't need to differentiate between a set of messages

    def add_message_to_group(self, message: discord.Message, group: Group = Group.default):
        """
        Indexes a message with a channel.

        @param message: The message to be indexed
        @param group: The group to be indexed in
        @return: nothing
        """
        logger.debug(f'{message_handler_prefix()}Adding message with id {message.id} to '
                     f'Group {group}')
        try:
            self.group_messages[group].append((message.channel.id, message.id))
        except KeyError:
            self.group_messages[group] = [(message.channel.id, message.id)]

    def add_special_message(self, message: discord.Message, key: Key):
        """
        Indexes a message with a special Key.

        @param message: The message to be indexed
        @param key: The key to be indexet with
        @return: nothing
        """
        logger.debug(f'{message_handler_prefix()}Trying to add message with id {message.id} into key '
                     f'{key}')
        if key in self.special_messages:
            logger.error(f'{message_handler_prefix()}Tried to add a message with key {key}, but key is already used')
        else:
            self.special_messages[key] = (message.channel.id, message.id)
            logger.debug(f'{message_handler_prefix()}Successfully added message with id {message.id} into key {key}')

    async def delete_group(self, group: Group = Group.default):
        """
        Deletes all messages indexed withing a group

        @param group: The group whose messages are to be cleared
        @return: nothing
        """
        logger.debug(f'{message_handler_prefix()}Trying to delete group {group}')
        if group not in self.group_messages:
            logger.debug(f'{message_handler_prefix()}Group {group} not registered as a key, nothing to delete here.')
            return
        to_delete = self.group_messages[group].copy()
        self.group_messages[group] = []
        if to_delete is None:
            logger.debug(f'{message_handler_prefix()}Group {group} is empty list, nothing to delete here.')
            return
        logger.debug(f'{message_handler_prefix()}Deleting non-empty group {group}')
        for (channel_id, message_id) in to_delete:
            message = await self._fetch_message_from_channel(channel_id=channel_id, message_id=message_id)
            if message:
                await message.delete()

    async def _fetch_message_from_channel(self, channel_id, message_id) -> Union[discord.Message, None]:
        """
        Fetches a message from a channel

        @param channel_id: The channel id to get the message from
        @param message_id: The id of the message to be fetched
        @return: The message (if exists), None otherwise
        """
        logger.debug(f'{message_handler_prefix()}Trying to fetch message from channel id {channel_id}'
                     f' with id {message_id}')
        channel: discord.TextChannel = self.guild.get_channel(channel_id=channel_id)
        if channel is None:
            logger.warn(f'{message_handler_prefix()}Channel with id {channel_id} does not exist anymore.')
            return None
        try:
            message = await channel.fetch_message(message_id)  # Getting message. Throws error, if not existing
            logger.debug(f'Returning message in channel {channel.name} with id {message_id}')
            return message
        except discord.NotFound:
            logger.warn(f'{message_handler_prefix()}Message with id {message_id} not found in channel {channel_id}')
            return None

    async def get_special_message(self, key: Key) -> Union[discord.Message, None]:
        """
        Fetch a message that was previously indexed by a key

        @param key: Key the message has been indexed before
        @return: The message (if exists), None otherwise
        """
        logger.debug(f'{message_handler_prefix()}Trying to get special message with key {key}')
        try:
            entry = self.special_messages[key]
        except KeyError:
            logger.error(f'{message_handler_prefix()}Special message with key {key} has never been indexed.')
            return None
        if entry is None:
            logger.error(f'{message_handler_prefix()}No entry for key {key} in the database, nothing to fetch.')
            return None
        (channel_id, message_id) = entry
        message = await self._fetch_message_from_channel(channel_id, message_id)  # Proper error handling is done here
        return message  # Could be None if message did not exist

    async def delete_special_message(self, key: Key, pop=True):
        """
        Delete a message using the key it has been indexed before.

        @param key: key under which the message has been indexed
        @param pop: Whether to pop the the entry of the message from the dictionary that stores it
        @return: nothing
        """
        logger.debug(f'{message_handler_prefix()}Trying to delete special message wih key {key}')
        message: discord.Message = await self.get_special_message(key)
        if message is None:
            logger.warn(f'{message_handler_prefix()}Message with key {key} not found, nothing to delete here.')
            return
        else:
            await message.delete()
            logger.debug(f'{message_handler_prefix()}Deleting message with id {message.id}')
        if pop:
            self.special_messages.pop(key)
            logger.debug(f'{message_handler_prefix()}Successfully popped key {key} from special message dictionary')

    async def clear_messages(self, preserve_keys: List[Key] = [], preserve_groups: List[Group] = []):
        """
        Clears the messages that have been indexed before

        @param preserve_keys: List of keys of the message one does NOT want to delete
        @param preserve_groups: List of groups of messages one does NOT want to delete
        @return:
        """
        logger.debug(f'{preserve_keys}Clearing messages except keys {preserve_keys} and groups {preserve_groups}')

        special_message_keys = [special_message_key for special_message_key in self.special_messages.keys()]
        for special_message_key in special_message_keys:
            logger.debug(f"{message_handler_prefix()}Checking key {special_message_key} within preserving list"
                         f" {preserve_keys}")
            if special_message_key not in preserve_keys:
                await self.delete_special_message(special_message_key, pop=True)

        for group_key in self.group_messages.keys():
            logger.debug(f'{message_handler_prefix()}Checking group {group_key} within preserving list'
                         f' {preserve_groups}')
            if group_key not in preserve_groups:
                await self.delete_group(group_key)


class MessageSender:
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel):
        self.guild = guild
        self.default_channel = default_channel
        self.message_handler = MessageHandler(guild=guild, default_channel=default_channel)

    def message_sender_prefix(self):
        return f'[Message Sender] '

    async def send_message(self, embed: Union[None, discord.Embed], normal_text="", reaction=True,
                           emoji: Union[Union[discord.Emoji, discord.Reaction, discord.PartialEmoji, str],
                                        List[Union[
                                            discord.Emoji, discord.Reaction, discord.PartialEmoji, str]]] = CHECK_EMOJI,
                           channel: Union[discord.TextChannel, None] = None,
                           key: Key = Key.invalid, group: Group = Group.default) -> discord.Message:
        """
        Sends a message in a channel and stores it in its message_handler and reacts to it with a given
        (optional: list of) emoji if told to do so
        :param embed: The embedding of the message to send (can be empty)
        :param normal_text: The normal text of the message to send (can be empty)
        :param reaction: If a reaction is to be added
        :param emoji: The emoji used for the reaction OR a list of emojis to react with
        :param channel: The channel to send the message in. Uses the own default_channel if not given
        :param key: The key to store the message. Used if this is a special message.
                    If nonempty, turns off group storing
        :param group: The group to store the message in. Only used if no key is given.
        :return: The message that was just sent
        """
        if channel:
            message = await channel.send(normal_text, embed=embed)
        else:
            message = await self.default_channel.send(normal_text, embed=embed)
        if reaction:  # Only add reaction if prompted to do so
            if type(emoji) is list:
                for e in emoji:
                    await message.add_reaction(e)
            else:
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
        if message is None:
            return
        if embed is None:
            if normal_text != "":
                await message.edit(normal_text=normal_text)
            else:
                print('Nothing to be edited')
        else:
            if normal_text != "":
                await message.edit(normal_text=normal_text, embed=embed)
            else:
                await message.edit(embed=embed)

    async def clear_reactions(self, key: Key):
        """
        Clears reactions from a message

        @param key: Key of the message to clear reactions from
        """
        message = await self.message_handler.get_special_message(key)
        try:
            await message.clear_reactions()
        except AttributeError:
            print('Failed to clear reactions')

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
            logger.debug(f'{self.message_sender_prefix()}Found a reaction, checking if valid...')
            if member:
                # print(f'User that reacted has id {user}, reacted with {str(reaction.emoji)} to message with id' f'{
                # reaction.message.id}, while i wait for a reaction of {member.id} with {str(emoji)} to message with
                # id' f' {message.id}')
                if type(member) != list:
                    return user.id == member.id and str(reaction.emoji) == emoji and reaction.message == message
                else:
                    return user.id in [person.id for person in member] and str(
                        reaction.emoji) == emoji and reaction.message == message
            else:
                return (not user.bot or react_to_bot) and str(reaction.emoji) == emoji and reaction.message == message

        logger.debug(f'{self.message_sender_prefix()}'
                     f'Waiting for reaction to message with key {message_key}{f" by {member.name}" if member else ""}')
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=warning_time, check=check)
            logger.debug(f'{self.message_sender_prefix()}...reaction valid, returning True')
            return True  # Notify that reaction was found
        except asyncio.TimeoutError:
            logger.debug(f'{self.message_sender_prefix()}Got no reaction to message {message.id}.')
            if timeout == 0:
                return False
            logger.debug(f'{self.message_sender_prefix()}Sending a warning to user')
            try:
                await self.send_message(normal_text=f"Hey, {member.mention if member else ''}",
                                        embed=warning, reaction=False, channel=message.channel, group=Group.warn)
            except discord.NotFound:  # In case the channel does not exist anymore
                logger.error(f'{self.message_sender_prefix()}The channel of the message I am waiting for a reaction '
                             f'does not exist anymore.')
                return False
            # Try a second time
            logger.debug(f'{self.message_sender_prefix()}Trying to wait a second time')
            try:
                reaction, user = await bot.wait_for('reaction_add', timeout=timeout, check=check)
                logger.debug(f'{self.message_sender_prefix()}Found reaction (on second try), returning True')
                return True  # Notify that reaction was found
            except asyncio.TimeoutError:
                logger.debug(f'{self.message_sender_prefix()}Failed to get a reaction, returning False')
                return False  # Notify that timeout has happened
