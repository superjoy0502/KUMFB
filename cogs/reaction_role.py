import asyncio
import json
import traceback
from os.path import exists
from typing import Dict, Union, Optional

from discord import Reaction, PartialEmoji
from discord import TextChannel, Guild
from discord import User, Member, Message, Permissions, Embed, Role
from discord.ext.commands import AutoShardedBot as Bot
from discord.ext.commands import CheckFailure, BadArgument
from discord.ext.commands import Cog, Context, command
from discord.ext.commands import has_guild_permissions
from discord.ext.tasks import loop


class ReactionRole(Cog):
    file_name = "reaction_roles.json"

    def __init__(self, bot: Bot):
        self.bot = bot

        # target_messages[(guild_id, channel_id)] = Dict[message_id, Dict[reaction_id, role_id]]
        self._target_messages: Dict[str, Dict[int, Dict[int, int]]] = {}

    @property
    def target_messages(self):
        return self._target_messages

    @target_messages.setter
    def target_messages(self, arg):
        self._target_messages = arg
        self.save_messages()

    def save_messages(self):
        print("Saving targets")
        open(self.file_name, "w").write(json.dumps(self._target_messages))

    @Cog.listener()
    async def on_ready(self):
        self.reload_cache_task.start()
        return await self.reload_caches()

    @loop(minutes=10)
    async def reload_cache_task(self, *args, **kwargs):
        print("Reloading caches")
        await self.reload_caches()

    async def reload_caches(self):
        if exists(self.file_name):
            self.target_messages = json.load(open(self.file_name))

        for g_c, v in self.target_messages.copy().items():
            for msg_id, reaction_id in v.copy().items():
                del self.target_messages[g_c][msg_id]
                self.target_messages[g_c][int(msg_id)] = reaction_id

        print(self.target_messages)
        for g_c, v in self.target_messages.items():
            guild_id, channel_id = map(int, g_c.split(", "))
            try:
                # guild: Guild = await self.bot.fetch_guild(guild_id)
                channel: TextChannel = await self.bot.fetch_channel(channel_id)

                for msg_id in v.keys():
                    try:
                        msg = await channel.fetch_message(msg_id)
                        if msg_id not in [x.id for x in self.bot._connection._messages]:
                            self.bot._connection._messages.append(msg)
                            print("Added message cache:", msg_id)
                    except:
                        pass
            except:
                pass

    async def is_target_reaction(self, reaction, user):
        guild_id: int = user.guild.id if user.guild else 0  # DM 채널 -> 0
        channel_id: int = reaction.message.channel.id
        msg: Message = reaction.message
        guild: Optional[Guild] = msg.guild

        if f"{guild_id}, {channel_id}" not in self.target_messages:  # 타깃 목록에 없는 경우
            return False, "Not in target guild-channel", None

        targets = self.target_messages[f"{guild_id}, {channel_id}"]

        # 타깃 메시지가 아닌 경우
        if not targets:
            return False, "Target messages not found", None

        if msg.id not in targets:
            return False, "Not in target messages", None

        if reaction.emoji.id not in targets[msg.id]:
            return False, "Not in target emojis", None

        role_id = targets[msg.id][reaction.emoji.id]
        role = guild.get_role(role_id)

        if role:
            return True, "", role
        return False, "Role not found", None

    @Cog.listener()
    async def on_reaction_add(self, reaction: Reaction, user: Union[Member, User]):
        # print(user, reaction.message.guild, reaction.message.channel, reaction)
        result, feedback, role = await self.is_target_reaction(reaction, user)

        if result:
            await user.add_roles(role)
        else:
            print(feedback)

    @Cog.listener()
    async def on_reaction_remove(self, reaction: Reaction, user: Union[Member, User]):
        result, feedback, role = await self.is_target_reaction(reaction, user)

        if result:
            await user.remove_roles(role)
        else:
            print(feedback)

    @command(name="추가")
    @has_guild_permissions(administrator=True)
    async def c_add(self, ctx: Context, channel: TextChannel, *, content: str):
        perm_target: Permissions = channel.permissions_for(ctx.me)
        perm_this: Permissions = ctx.channel.permissions_for(ctx.me)
        if not perm_target.send_messages:
            return ctx.send(f"{ctx.author.mention} 채널 {channel.mention} 에 메시지를 보낼 수 없습니다. "
                            f"권한을 확인해주세요.")
        if not perm_this.add_reactions:
            return ctx.send(f"{ctx.author.mention} 이 채널에 이모지를 달 수 없습니다. 권한을 확인해주세요.")
        if not perm_this.manage_messages:
            return ctx.send(f"{ctx.author.mention} 이 채널에서 메시지를 지울 수 없습니다. 권한을 확인해주세요.")

        embed_data = Embed(title="이모지 -> 역할: 새로운 메시지", description=f"제목: {content}").to_dict()
        embed_data["fields"] = [
            {
                "name": "등록된 이모지 목록",
                "value": "<없음>",
                "inline": False,
            },
            {
                "name": "이모지 추가",
                "value": "반응할 이모지를 이 메시지에 달아주세요.\n"
                         "끝내려면 ✅ 이모지를 눌러주세요.",
                "inline": False,
            }
        ]
        print(embed_data)
        msg = await ctx.send(embed=Embed.from_dict(embed_data))
        await msg.add_reaction("✅")

        def check_same_context(r: Reaction, u: Union[User, Member]):
            print(r, u)
            return u.id == ctx.author.id and r.message.id == msg.id

        def check_same_user(m: Message):
            print(m)
            return m.author.id == ctx.author.id

        first = True
        reactions: Dict[Reaction, Role] = {}
        while True:
            try:
                if not first and reactions:
                    embed_data["fields"][0]["value"] = "\n".join(f"{k} {v}" for k, v in reactions.items())
                else:
                    embed_data["fields"][0]["value"] = "<없음>"

                embed_data["fields"][1] = {
                    "name": "이모지 추가",
                    "value": "반응할 이모지를 이 메시지에 달아주세요.\n"
                             "끝내려면 ✅ 이모지를 눌러주세요.",
                    "inline": False,
                }
                await msg.edit(embed=Embed.from_dict(embed_data))

                reaction, user = await self.bot.wait_for("reaction_add", check=check_same_context)

                if reaction.emoji == "✅":
                    break

                if isinstance(reaction.emoji, PartialEmoji) or not reaction.emoji.available:
                    await ctx.send("봇이 이용할 수 없는 이모지입니다. 이모지 등록으로 돌아갑니다.", delete_after=5)
                    continue

                embed_data["fields"][1]["name"] = f"{reaction}의 역할 설정"
                embed_data["fields"][1]["value"] = "해당 이모지에 지급할 역할을 멘션해주세요."
                await msg.edit(embed=Embed.from_dict(embed_data))

                try:
                    role_message: Message = await self.bot.wait_for("message", check=check_same_user,
                                                                    timeout=60 * 10)  # 10분
                    if not role_message.role_mentions:
                        await ctx.send("올바른 역할을 멘션하지 않았습니다. 이모지 등록으로 돌아갑니다.", delete_after=5)
                        continue

                    target_role = role_message.role_mentions[0]
                    reactions[reaction] = target_role
                    first = False
                    continue
                except asyncio.TimeoutError:
                    await ctx.send("시간 초과로 등록을 취소했습니다. 이모지 등록으로 돌아갑니다.", delete_after=5)
                    continue
            except asyncio.TimeoutError:
                embed_data["fields"][1] = {
                    "name": "이모지 추가",
                    "value": "반응할 이모지를 이 메시지에 달아주세요.\n"
                             "끝내려면 ✅ 이모지를 눌러주세요.",
                    "inline": False,
                }
                await msg.edit(embed=Embed.from_dict(embed_data))
            except:
                await ctx.send("오류로 인해 등록을 취소했습니다.")
                return await ctx.send(traceback.format_exc())

        await msg.clear_reactions()
        del embed_data["fields"][1]
        embed_data["title"] = content
        embed_data["description"] = ""
        embed_data["fields"][0]["name"] = "・"

        target_msg = await channel.send(embed=Embed.from_dict(embed_data))
        for k in reactions:
            await target_msg.add_reaction(k.emoji)

        if (ctx.guild.id, ctx.channel.id) not in self.target_messages:
            self.target_messages[f"{ctx.guild.id}, {ctx.channel.id}"] = {}

        self.target_messages[f"{ctx.guild.id}, {ctx.channel.id}"][target_msg.id] = \
            dict((k.emoji.id, v.id) for k, v in reactions.items())
        self.save_messages()
        await ctx.send(f"{ctx.author.mention} 등록이 완료되었습니다.")

    @command(name="삭제")
    @has_guild_permissions(administrator=True)
    async def c_remove(self, ctx: Context, msg_id: int):
        target_msg: Optional[Message] = None

        for g_c, v in self.target_messages.items():
            guild_id, channel_id = map(int, g_c.split(", "))
            if msg_id in v.keys():
                channel: TextChannel = self.bot.get_channel(channel_id)
                target_msg = await channel.fetch_message(msg_id)

                await target_msg.delete()
                return await ctx.send(f"{ctx.author.mention} 성공적으로 삭제했습니다.")

        if not target_msg:
            return await ctx.send(f"{ctx.author.mention} 타깃 메시지를 찾을 수 없습니다.")

    @command(name="r")
    async def c_r(self, ctx: Context):
        try:
            await self.reload_caches()
            return await ctx.send(f"{ctx.author.mention} 갱신 성공")
        except:
            return await ctx.send(traceback.format_exc())

    @c_add.error
    async def c_add_error(self, ctx: Context, error):
        if isinstance(error, CheckFailure):
            return await ctx.send(f"{ctx.author.mention} 이 명령어를 이용하려면 서버의 관리자이어야 합니다.")
        elif isinstance(error, BadArgument):
            return await ctx.send(f"{ctx.author.mention} 적절한 사용법\n"
                                  f"> {self.bot.command_prefix} 추가 <채널 멘션> [...보낼 메시지]")
        else:
            return await ctx.send(traceback.format_exc())

    @c_remove.error
    async def c_remove_error(self, ctx: Context, error):
        if isinstance(error, CheckFailure):
            return await ctx.send(f"{ctx.author.mention} 이 명령어를 이용하려면 서버의 관리자이어야 합니다.")
        elif isinstance(error, BadArgument):
            return await ctx.send(f"{ctx.author.mention} 적절한 사용법\n"
                                  f"> {self.bot.command_prefix} 삭제 <메시지id>\n\n"
                                  f"* 메시지 id를 얻는 방법은 아래 링크를 확인해보세요.\n"
                                  f"<https://support.discordapp.com/hc/ko/articles/"
                                  f"206346498-%EC%9C%A0%EC%A0%80-%EC%84%9C%EB%B2%84-"
                                  f"%EB%A9%94%EC%8B%9C%EC%A7%80-ID%EB%8A%94-%EC%96%B4%EB%94%94%EC%84%9C-"
                                  f"%EC%B0%BE%EB%82%98%EC%9A%94->")
        else:
            return await ctx.send(traceback.format_exc())

    @command(name="b")
    async def c_b(self, ctx: Context):
        await ctx.send(f"```py\n{self.bot.cached_messages}\n```")
        await ctx.send(f"```py\n{[x.id for x in self.bot._connection._messages]}\n```")


def setup(bot: Bot):
    bot.add_cog(ReactionRole(bot))
