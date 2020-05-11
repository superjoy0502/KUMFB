# -*- coding:utf-8 -*-

import logging

from discord.ext.commands import Bot, Context

from resources.token import getToken

bot = Bot(command_prefix="//")

logger = logging.getLogger('discord')
logger.setLevel(logging.DEBUG)
handler = logging.FileHandler(filename='resources/discord.log', encoding='utf-8', mode='w')
handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)


async def on_ready(self):
    logger.info(f"Logged in as {self.user}")


async def on_error(self, event, *args, **kwargs):
    logger.exception("")


@bot.command()
async def echo(ctx, *, arg):
    if arg:
        await ctx.send(arg)
    else:
        await ctx.send("Incorrect Usage!\nUsage: //echo <string>")


@bot.command(name="클리어")
async def clear(ctx: Context, arg: int):
    mgs = []
    number = int(arg)
    async for x in ctx.message.channel.history(limit=number + 1):
        mgs.append(x)
    await ctx.message.channel.delete_messages(mgs)


bot.load_extension("cogs.reaction_role")
bot.load_extension("cogs.mcserver_status")
tk = getToken()

bot.run(tk)
