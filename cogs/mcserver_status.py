import discord
from discord.ext.commands import Cog, Bot, command, Context
from mcstatus import MinecraftServer


class MCServerStatus(Cog):
    def __init__(self, bot: Bot):
        self.bot = bot

    @command(name="상태")
    async def displayStatus(self, ctx: Context, server):
        async with ctx.channel.typing():
            strserver = server
            server = MinecraftServer.lookup(server)
            status = server.status()

            embed = discord.Embed(title=strserver + "의 상태", description="", color=0x42f569)
            embed.add_field(name=":satellite: **핑**", value=str(status.latency) + "ms", inline=False)
            embed.add_field(name=":pencil: **설명**", value=str(status.description), inline=False)
            embed.add_field(name=":desktop:  **버젼**", value=str(status.version.name), inline=False)
        await ctx.send(embed=embed)

    async def cog_command_error(self, ctx, error):
        eEmbed = discord.Embed(title="에러", description="", color=0xff0000)
        eEmbed.add_field(name=":no_entry_sign: **에러 내용**", value=str(error) + "ms", inline=False)
        await ctx.send(embed=eEmbed)


def setup(bot: Bot):
    bot.add_cog(MCServerStatus(bot))
