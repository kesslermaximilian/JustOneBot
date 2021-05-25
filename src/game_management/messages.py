import discord
from typing import TypedDict, List


class MessageHandler:  # Basic message handler for messages that one wants to send and later delete or fetch
    def __init__(self, guild: discord.Guild, default_channel: discord.TextChannel):
        self.guild = guild,
        self.default_channel = default_channel
        self.special_messages: TypedDict[str, (int,int)] = {}  # Stores some special messages with keywords
        self.group_messages: TypedDict[str, List[(int,int)]] = {}  # Stores groups of messages by their group names
        # Useful if we don't need to differentiate between a set of messages

    def add_message_to_group(self, message: discord.Message, group: str = 'default'):
        if self.group_messages[group] is None:
            self.group_messages[group] = [(message.channel.id, message.id)]
        else:
            self.group_messages[group].append((message.channel.id,message.id))

    def add_special_message(self, message: discord.Message, key):
        if self.special_messages[key] is not None:
            print('Error')
            return
        self.special_messages[key] = (message.channel.id, message.id)

    def delete_group(self, group: str = 'default'):
        to_delete = self.group_messages[group].copy()
        self.group_messages[group] = []
        for (channel_id, message_id) in to_delete:
            self.guild.get_channel(channel_id)



    def _get_message(self, id: int):
        self.guild.

