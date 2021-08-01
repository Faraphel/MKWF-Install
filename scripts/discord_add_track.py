import discord
import subprocess
import shutil
import os
import io

from source.CT_Config import CT_Config
from source.Track import Track
from source.wszst import szs
from scripts.minimap import obj_to_png

bot = discord.Client()
SERVER_ID = 842865613918699590
TRACK_CHANNEL_ID = 871100630251499530
DATA_CHANNEL_ID = 871469647617216652

warning_level_message = [
    "No special glitch",
    "minor glitch",
    "major glitch"
]

EMOTE_1STAR = 843109869107413012
EMOTE_2STAR = 843109881385058325
EMOTE_3STAR = 843109892330881107

placeholder_image_url = "https://media.discordapp.net/attachments/871469647617216652/871487829023289404/Placeholder.png"
download_icon_url = "https://media.discordapp.net/attachments/842865834090037310/871467284009480202/img_68704.png"


def get_track_minimap(track: Track):
    if os.path.exists("./scripts/tmp/"): shutil.rmtree("./scripts/tmp/")
    if not os.path.exists("./scripts/tmp/"): os.makedirs("./scripts/tmp/")

    szs.extract(track.file_szs, "./scripts/tmp/track.szs")
    subprocess.run(["abmatt", "convert", "./scripts/tmp/track.szs.d/map_model.brres",
                    "to", "./scripts/tmp/map_model.obj"])
    image = obj_to_png.render_top_view(obj_file="./scripts/tmp/map_model.obj")

    return image


@bot.event
async def on_ready():
    guild: discord.Guild = bot.get_guild(id=SERVER_ID)
    track_channel: discord.TextChannel = guild.get_channel(channel_id=TRACK_CHANNEL_ID)
    data_channel: discord.TextChannel = guild.get_channel(channel_id=DATA_CHANNEL_ID)

    message_from_sha1 = {}
    old_sha1 = set()

    message: discord.Message
    async for message in track_channel.history(limit=-1):
        if message.author.id == bot.user.id:
            for field in message.embeds[0].fields:
                if "sha1" in field.name:
                    message_from_sha1[field.value] = message
                    old_sha1.add(field.value)

    ct_config = CT_Config()
    ct_config.load_ctconfig_file("./ct_config.json")

    for track in ct_config.all_tracks:
        embed = discord.Embed(title=f"**{track.get_track_name()}**",
                              description="", url=f"https://ct.wiimm.de/i/{track.sha1}")

        author_link = ""
        if "," not in track.author: author_link = "http://wiki.tockdom.com/wiki/" + track.author
        embed.set_author(name=track.author, url=author_link)

        with io.BytesIO() as image_binary:
            image = get_track_minimap(track)
            image.save(image_binary, "PNG")
            image_binary.seek(0)

            message_minimap = await data_channel.send(file=discord.File(fp=image_binary, filename="minimap.png"))
        embed.set_thumbnail(url=message_minimap.attachments[0].url)

        if hasattr(track, "score"):
            embed.add_field(name="Track Score", value=track.score)  # TODO
        if hasattr(track, "warning"):
            embed.add_field(name="Warning level", value=warning_level_message[track.warning])
        if hasattr(track, "since_version"):
            embed.add_field(name="Here since version", value=track.since_version)  # TODO

        embed.add_field(name="Lap count", value="3")  # TODO
        embed.add_field(name="Speed multiplier", value="x1.0")  # TODO

        embed.set_image(url=placeholder_image_url)  # TODO

        if hasattr(track, "sha1"):
            embed.add_field(name="sha1", value=track.sha1)

        if track.sha1 not in old_sha1:
            message = await track_channel.send(embed=embed)
            await message.add_reaction(bot.get_emoji(EMOTE_1STAR))
            await message.add_reaction(bot.get_emoji(EMOTE_2STAR))
            await message.add_reaction(bot.get_emoji(EMOTE_3STAR))
            await message.add_reaction("❌")
        else:
            if hasattr(track, "sha1"):
                await message_from_sha1[track.sha1].edit(embed=embed)

bot.run(os.environ['DISCORD_GR_TOKEN'])
