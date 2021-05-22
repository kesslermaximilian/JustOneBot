import discord
from discord.ext import commands
from typing import NewType, List
import utils as ut

class Hint:
    def __init__(self, message: discord.Message):
        self.author = message.author
        self.hint_message = message.content
        self.valid = True

    def get_author(self):
        return self.author

    def get_message(self):
        return self.hint_message

    def strike(self):
        self.valid = False

    def is_valid(self):
        return self.valid


class Game:
    def __init__(self, channel: discord.TextChannel, guesser: discord.Member, wordtype='default'):
        self.channel = channel
        self.guesser = guesser
        self.word = None
        self.hints = []
        self.wordtype = wordtype
        self.role = None
        self.sent_messages = []
        self.phase = 'initialisation'
        print(f'Game started in channel {self.channel} by user {self.guesser}')

    async def remove_guesser_from_channel(self):
        # TODO: create a proper role for this channel and store it in self.role
        self.role = self.channel.guild.get_role(845740067481321473)
        await self.guesser.add_roles(self.role)

    async def start(self):
        self.phase = 'get_hints'
        await self.remove_guesser_from_channel()
        await self.show_word()

    def add_hint(self, message):
        self.hints.append(Hint(message))

    async def add_guesser_to_channel(self):
        await self.guesser.remove_roles(self.role)

    async def show_word(self):
        self.word = getword(self.wordtype)  # generate a word
        self.sent_messages.append(
            await self.channel.send(
                embed=ut.make_embed(
                    name='Neue Runde JustOne',
                    value=f'Das neue Wort lautet *{self.word}*.',
                    color=ut.green,
                    footer=f'Gebt Tipps ab, um {compute_proper_nickname(self.guesser)} zu helfen, das Wort zu erraten!'
                )
            )
        )

    async def show_answers(self):
        self.sent_messages.append(
            await self.channel.send(
                embed=ut.make_embed(
                    title='Tippphase beendet',
                    name='Wählt evtl. doppelte Tipps aus!',
                 color=ut.yellow
                )
            )
        )

        for hint in self.hints:
            self.sent_messages.append(
                await self.channel.send(
                    embed=ut.make_embed(
                        name=hint.hint_message,
                        value=compute_proper_nickname(hint.author)
                    )
                )
            )

        self.sent_messages.append(
            await self.channel.send(
                embed=ut.make_embed(
                    title='Keine doppelten Tipps?',
                    name='Dann klickt hier!'
                )
            )
        )


    async def show_hints(self):
        embedding = discord.Embed(
            title='Es ist Zeit, zu raten!',
            description='Die folgenden Tipps wurden abgegeben:'
        )

        for hint in self.hints:
            if hint.is_valid():
                embedding.add_field(name=hint.hint_message, value=f'({compute_proper_nickname(hint.author)})')

        await self.channel.send(embed=embedding)

    # def show_summary(self):

    def clear(self):
        for message in self.sent_messages:
            message.delete()


games = []


class JustOne(commands.Cog):
    """
    Manager for the popular Game 'JustOne'
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='one', help='Start a new round of just one in this text channel'
                                       'with the people of your voice channel')
    async def one(self, ctx: commands.Context):
        global games

        guesser = ctx.author
        text_channel = ctx.channel
        for game in games:
            if game.channel.id == text_channel.id:
                print('There is already a game running in this channel, aborting...')
                # TODO: maybe print a proper error message in the text channel as well?
                return

        game = Game(text_channel,guesser)
        games.append(game)
        await game.start()

    """
    @commands.command()
    async def tips(self, ctx: commands.Context):
        global text_channel
        global valid_tips
        global tips
        await display_valid_tips(text_channel, tips)
    """

    @commands.Cog.listener()
    async def on_message(self, message):
        # Todo: Make on_message ignore all bot commands
        channel = message.channel
        if message.author.bot:
            print('Found a bot message. Ignoring')
            return

        global games
        if games is None:
            return
        for game in games:
            if channel.id == game.channel.id:
                game.add_hint(message)
                await message.delete()


def compute_proper_nickname(member: discord.Member):
    if member.nick is None:
        return member.name
    else:
        return member.nick


def getword(wordtype):
    return 'Gandhi'


def setup(bot):
    bot.add_cog(JustOne(bot))