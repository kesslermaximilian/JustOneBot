import discord
from typing import TypedDict, List, Union
from environment import CHECK_EMOJI, DISMISS_EMOJI


class MessageHandler:  # Basic message handler for messages that one wants to send and later delete or fetch
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel):
        self.guild: discord.Guild = guild
        self.default_channel: discord.TextChannel = default_channel
        self.special_messages: TypedDict[str, (int, int)] = {}  # Stores some special messages with keywords
        self.group_messages: TypedDict[str, List[(int, int)]] = {}  # Stores groups of messages by their group names
        # Useful if we don't need to differentiate between a set of messages

    def add_message_to_group(self, message: discord.Message, group: str = 'default'):
        try:
            self.group_messages[group].append((message.channel.id, message.id))
        except KeyError:
            self.group_messages[group] = [(message.channel.id, message.id)]

    def add_special_message(self, message: discord.Message, key):
        try:
            print(f'I already stored the message with content {self.special_messages[key].content} in the key {key}')
        except KeyError:
            self.special_messages[key] = (message.channel.id, message.id)

    async def delete_group(self, group: str = 'default'):
        to_delete = self.group_messages[group].copy()
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

    async def get_special_message(self, key: str) -> Union[discord.Message, None]:
        print(f'Getting special message with key {key}')
        entry = self.special_messages[key]
        if entry is None:
            print(f'No entry for {key} in the database')
            return None
        (channel_id, message_id) = entry
        message = await self._fetch_message_from_channel(channel_id, message_id)
        return message

    async def delete_special_message(self, key: str, pop=True):
        message: discord.Message = await self.get_special_message(key)
        if message is None:
            print(f'Failed to delete message with special key {key}')
            return
        else:
            await message.delete()
        if pop:
            self.special_messages.pop(key)

    async def clear_all(self):
        for group_key in self.group_messages.keys():
            await self.delete_group(group_key)
        for special_message_key in self.special_messages.keys():
            await self.delete_special_message(special_message_key, pop=False)
        self.special_messages = {}


class MessageSender:
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel):
        self.guild = guild
        self.default_channel = default_channel
        self.message_handler = MessageHandler(guild=guild, default_channel=default_channel)

    async def send_message(self, embed, normal_text="", reaction=True, emoji=CHECK_EMOJI,
                           channel: Union[discord.TextChannel, None] = None, key="", group="default") -> discord.Message:
        """
        Sends a message in a channel and stores it in its message_handler and reacts to it with a given emoji if told
        to do so
        :param embed: The embedding of the message to send (can be empty)
        :param normal_text: The normal text of the message to send (can be empty)
        :param reaction: If a reaction is to be added
        :param emoji: The emoji used for the reaction
        :param channel: The channel to send the message in. Uses the own default_channel if not given
        :param key: The key to store the message. Used if this is a special message. If nonempty, turns of group storing
        :param group: The group to store the message in. Only used if no key is given.
        :return: The message that was just sent
        """
        if channel:
            message = await channel.send(normal_text, embed=embed)
        else:
            message = await self.default_channel.send(normal_text, embed=embed)
        if reaction:  # Only add reaction if prompted to do so
            await message.add_reaction(emoji)
        if key != "":
            self.message_handler.add_special_message(message, key=key)
        else:
            self.message_handler.add_message_to_group(message=message, group=group)
        return message
