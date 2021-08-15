"""
This script allow you to update a discord channel with the ct_config.json
"""

import discord
import subprocess
import shutil
import os
import io

from PIL import Image

from source.CT_Config import CT_Config
from source.Track import Track
from source.wszst import szs
from scripts.minimap import obj_to_png

bot = discord.Client()
SERVER_ID = 842865613918699590
TRACK_CHANNEL_ID = 871100630251499530
OLD_TRACK_CHANNEL_ID = 842867283428507699  # previous channel used by the program to get score
DATA_CHANNEL_ID = 871469647617216652

warning_level_message = [
    "No special glitch",
    "minor glitch",
    "major glitch"
]

EMOTE_1STAR = 843109869107413012
EMOTE_2STAR = 843109881385058325
EMOTE_3STAR = 843109892330881107

placeholder_image_url = "https://media.discordapp.net/attachments/842865834090037310/875817942200238111/Placeholder.png"


get_norm_color_value = lambda x: int((x if x >= 0 else 0) if x <= 255 else 255)
get_R = lambda x: get_norm_color_value(-510 * x + 1021)
get_G = lambda x: get_norm_color_value(255 * x - 510)
get_B = lambda x: get_norm_color_value(254 * x - 127 if x < 1.5 else -254 * x + 890)
get_color_from_score = lambda x: (get_R(x), get_G(x), get_B(x))


def get_track_minimap(track: Track):
    tmp_dir = f"./scripts/tmp/{track.sha1}/"
    if not os.path.exists(tmp_dir): os.makedirs(tmp_dir)

    szs.extract(track.file_szs, tmp_dir + "track.szs")
    subprocess.run(["abmatt", "convert", tmp_dir + "track.szs.d/map_model.brres",
                    "to", tmp_dir + "map_model.obj"])
    image = obj_to_png.render_top_view(obj_file=tmp_dir + "map_model.obj")

    try: shutil.rmtree(tmp_dir)
    except: print(f"can't remove tmp directory for {track.name}")

    return image


@bot.event
async def on_ready():
    guild: discord.Guild = bot.get_guild(id=SERVER_ID)
    track_channel: discord.TextChannel = guild.get_channel(channel_id=TRACK_CHANNEL_ID)
    old_track_channel: discord.TextChannel = guild.get_channel(channel_id=OLD_TRACK_CHANNEL_ID)
    data_channel: discord.TextChannel = guild.get_channel(channel_id=DATA_CHANNEL_ID)

    message_from_sha1 = {}
    old_message_from_sha1 = {}

    message: discord.Message
    async for message in track_channel.history(limit=5000):
        if message.author.id == bot.user.id:
            for field in message.embeds[0].fields:
                if "sha1" in field.name:
                    message_from_sha1[field.value] = message

    async for message in old_track_channel.history(limit=5000):
        if message.author.id == bot.user.id:
            if "_" in message.content: continue
            sha1 = message.content.split("ct.wiimm.de/i/")[-1].replace("|", "").strip()
            old_message_from_sha1[sha1] = message

    ct_config = CT_Config()
    ct_config.load_ctconfig_file("./ct_config.json")

    for track in ct_config.all_tracks:
        try:
            if track.name == "_": continue

            if track.sha1 in message_from_sha1:
                embed = message_from_sha1[track.sha1].embeds[0]
            else:
                embed = discord.Embed(title=f"**{track.get_track_name()}**",
                                      description="", url=f"https://ct.wiimm.de/i/{track.sha1}")
                for _ in range(6): embed.add_field(name="empty", value="empty")

            author_link = ""
            if "," not in track.author:
                author_link = "http://wiki.tockdom.com/wiki/" + track.author.replace(" ", "_")
            try: embed.set_author(name=track.author, url=author_link)
            except: embed.set_author(name=track.author)

            track_technical_data = szs.analyze(track.file_szs)

            if hasattr(track, "score"):
                scores = [track.score]
                if track.sha1 in old_message_from_sha1:
                    for reaction in old_message_from_sha1[track.sha1].reactions:
                        if str(EMOTE_1STAR) in str(reaction.emoji): scores.extend([1] * (reaction.count - 1))
                        elif str(EMOTE_2STAR) in str(reaction.emoji): scores.extend([2] * (reaction.count - 1))
                        elif str(EMOTE_3STAR) in str(reaction.emoji): scores.extend([3] * (reaction.count - 1))

                if track.sha1 in message_from_sha1:
                    for reaction in message_from_sha1[track.sha1].reactions:
                        if str(EMOTE_1STAR) in str(reaction.emoji): scores.extend([1] * (reaction.count - 1))
                        elif str(EMOTE_2STAR) in str(reaction.emoji): scores.extend([2] * (reaction.count - 1))
                        elif str(EMOTE_3STAR) in str(reaction.emoji): scores.extend([3] * (reaction.count - 1))

                average_score = round(sum(scores) / len(scores), 2)
                embed.colour = discord.Color.from_rgb(*get_color_from_score(average_score))

                embed.set_field_at(index=0, name="Track Score", value=f"{average_score} (vote : {len(scores)})")
            if hasattr(track, "warning"):
                embed.set_field_at(index=1, name="Warning level", value=warning_level_message[track.warning])
            if hasattr(track, "since_version"):
                embed.set_field_at(index=2, name="Here since version", value=track.since_version)

            embed.set_field_at(index=3, name="Lap count", value=track_technical_data["lap_count"])
            embed.set_field_at(index=4, name="Speed multiplier", value=track_technical_data["speed_factor"])

            embed.set_field_at(index=5, name="sha1", value=track.sha1)

            if track.sha1 not in message_from_sha1:
                with io.BytesIO() as image_binary:
                    track_img_path = f"./scripts/map preview/image/{track.get_track_name()}.png"
                    if os.path.exists(track_img_path):
                        image = Image.open(track_img_path)
                        image.save(image_binary, "PNG")
                        image_binary.seek(0)
                        message_map_preview = await data_channel.send(
                            file=discord.File(fp=image_binary, filename=f"map preview {track.sha1}.png"))
                        url_map_preview = message_map_preview.attachments[0].url
                    else: url_map_preview = placeholder_image_url
                embed.set_image(url=url_map_preview)

                with io.BytesIO() as image_binary:
                    image = get_track_minimap(track)
                    image.save(image_binary, "PNG")
                    image_binary.seek(0)
                    message_minimap = await data_channel.send(
                        file=discord.File(fp=image_binary, filename=f"minimap {track.sha1}.png"))
                embed.set_thumbnail(url=message_minimap.attachments[0].url)

                message = await track_channel.send(embed=embed)
                await message.add_reaction(bot.get_emoji(EMOTE_1STAR))
                await message.add_reaction(bot.get_emoji(EMOTE_2STAR))
                await message.add_reaction(bot.get_emoji(EMOTE_3STAR))
                await message.add_reaction("❌")

            else:
                message = message_from_sha1[track.sha1]
                await message.edit(embed=embed)

        except Exception as e:
            print(f"error for track {track.name} : {str(e)}")

bot.run(os.environ['DISCORD_GR_TOKEN'])
