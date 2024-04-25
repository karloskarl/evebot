import os
from interactions import Client, Intents, slash_command, slash_option, SlashContext, listen, OptionType, Member
from interactions.api.events import MemberAdd, MemberRemove
from dotenv import load_dotenv
from rcon.source import rcon

load_dotenv()
#loads environment variables from .env file
TOKEN: str = os.getenv('DISCORD_TOKEN')
GUILD: str = os.getenv('DISCORD_GUILD')
RCON_HOST: str = os.getenv('RCON_HOST')
RCON_PORT : int = int(os.getenv('RCON_PORT'))
RCON_PASSWORD: str = os.getenv('RCON_PASSWORD')
COUNTER_VOICE_CHANNEL_ID: str = os.getenv('COUNTER_VOICE_CHANNEL_ID')
PLAYER_ROLE_ID: str = os.getenv('PLAYER_ROLE_ID')
ADMIN_ROLE_ID: str = os.getenv('ADMIN_ROLE_ID')
STATUS_MESSAGE_CHANNEL: str = os.getenv('STATUS_MESSAGE_CHANNEL')
STATUS_MESSAGE_ID: str = os.getenv('STATUS_MESSAGE_ID')

bot = Client(intents=Intents.GUILDS | Intents.MESSAGES)

@slash_command(name="echo", description="Responds with the content of the argument", scopes=[GUILD])
@slash_option(
    name="argument",
    description="Argument that gets echoed",
    required=True,
    opt_type=OptionType.STRING
)
async def echo(ctx: SlashContext, argument: str = ""):
    await ctx.send(argument)

async def rcon_call(command: str, username: str = ""):
    command_list = command.strip().split(' ')
    if username == "":
        response = await rcon(*command_list, host=RCON_HOST, port=RCON_PORT, passwd=RCON_PASSWORD)
    else:
        response = await rcon(*command_list, username, host=RCON_HOST, port=RCON_PORT, passwd=RCON_PASSWORD)
    return str(response)

#whitelist list command
@slash_command(name="whitelist", description="View or manage the whitelist of the minecraft server", sub_cmd_name="list", sub_cmd_description="Lists all whitelisted members", scopes=[GUILD])
async def whitelist_list_function(ctx: SlashContext):
    response = await rcon_call("whitelist list")
    await ctx.send(response)

#whitelist add command
@slash_command(name="whitelist", description="View or manage the whitelist of the minecraft server", sub_cmd_name="add", sub_cmd_description="Adds a player to the whitelist", scopes=[GUILD])
@slash_option(
    name="submitted_username",
    description="Minecraft Username",
    required=True,
    opt_type=OptionType.STRING)
@slash_option(
    name="discord_user",
    description="The discord user who is being added",
    required=True,
    opt_type=OptionType.USER)
async def whitelist_add_function(ctx: SlashContext, submitted_username: str, discord_user: Member):
    response = await rcon_call("whitelist add", submitted_username)
    response_words = response.split(' ')
    match response_words[0]:
        # from "That player does not exist"
        case "That":
            await ctx.send(response)
            return
        # from "Player is already whitelisted"
        case "Player":
            await ctx.send(response)
            return
        # from "Added username to the whitelist"
        case "Added":
            minecraft_username = response_words[1]
            already_whitelisted = False
            with open("whitelist.txt","r") as f:
                lines = f.readlines()
            for line in lines:
                if(line[0] == "#"):
                    continue
                if line.split('@')[1].strip() == discord_user.global_name.strip():
                    already_whitelisted = True
            with open("whitelist.txt","a") as f:
                f.write(minecraft_username + " - @" + discord_user.global_name + "\n")
            # creates mention in correct formatting
            mention = f"<@{discord_user.id}>"
            # Adds the players role to them
            guild = ctx.guild
            role = guild.get_role(PLAYER_ROLE_ID)
            if role:
                await discord_user.add_role(role)
            if already_whitelisted:
                await ctx.send(response + f", another account owned by {mention}." )
            else:
                await ctx.send(response)
            return
            
        case _:
            await ctx.send("Unexpected RCON response")

#whitelist remove command
@slash_command(name="whitelist", description="View or manage the whitelist of the minecraft server", sub_cmd_name="remove", sub_cmd_description="Removes a player from the whitelist", scopes=[GUILD])
@slash_option(
    name="submitted_username",
    description="Minecraft Username",
    required=True,
    opt_type=OptionType.STRING)
async def whitelist_remove_function(ctx: SlashContext, submitted_username: str):
    response = await rcon_call("whitelist remove", submitted_username)
    response_words = response.split(' ')
    match response_words[0]:
        # from "That player does not exist"
        case "That":
            await ctx.send(response)
            return
        # from "Player is not whitelisted"
        case "Player":
            await ctx.send(response)
            return
        # from "Removed username from the whitelist"
        case "Removed":
            with open("whitelist.txt","r") as f:
                lines = f.readlines()
            with open("whitelist.txt","w") as f:
                for line in lines:
                    minecraft_username = response_words[1]
                    if line.strip("\n").split(' ')[0] != minecraft_username:
                        f.write(line)
                        if line[0] != '#':
                            discord_username = line.strip().split('@')
            await ctx.send(response)
        case _:
            await ctx.send("Unexpected RCON response")

#account whitelist remove command
@slash_command(name="whitelist", description="View or manage the whitelist of the minecraft server", sub_cmd_name="account_remove", sub_cmd_description="Removes all accounts from a single discord account from the whitelist", scopes=[GUILD])
@slash_option(
    name="discord_user",
    description="The discord user who is being removed from the whitelist",
    required=True,
    opt_type=OptionType.USER)
async def whitelist_account_remove_function(ctx: SlashContext, discord_user: Member):
    with open("whitelist.txt","r") as f:
        lines = f.readlines()
    nRemoved = 0
    with open("whitelist.txt","w") as f: 
        for line in lines:
            if line[0] == "#" or line.split('@')[1].strip() != discord_user.global_name.strip():
                f.write(line)
            else:
                await rcon_call("whitelist remove", line.split(' ')[0])
                nRemoved += 1
    if nRemoved == 0:
        await ctx.send("This discord user has no accounts connected to them.")
    else:
        guild = ctx.guild
        role = guild.get_role(PLAYER_ROLE_ID)
        if role:
            discord_user.remove_role(role, "You were removed from the whitelist.")
        await ctx.send(f"Removed {nRemoved} users from the whitelist.")
     
@listen(MemberAdd)
async def on_member_join(member: MemberAdd):
    await update_channel_name()

@listen(MemberRemove)
async def on_member_remove(member: MemberRemove):
    await update_channel_name()

# Updates the counter tracker
async def update_channel_name():
    try:
        guild = bot.get_guild(GUILD)
        if guild is None:
            print("Guild not found.")
            return
        
        voice_channel = guild.get_channel(COUNTER_VOICE_CHANNEL_ID)
        if voice_channel is None:
            print("Voice channel not found.")
            return
        
        member_count = guild.member_count
        await voice_channel.edit(name=f"Total Members: {member_count}")
        print("Member count updated!")
    
    except Exception as e:
        print(f"An error occurred: {e}")

async def remove_slash_command(id):
    try:
        await bot.delete_command(id)
        print(f"Command with id {id} deleted.")
    except Exception as e:
        print(f"Error deleting command: {e}")

@listen
async def on_ready():
    print("Ready")

async def update_status_message():
    try:
        guild = bot.get_guild(GUILD)
        channel = guild.get_channel(STATUS_MESSAGE_CHANNEL)
        if STATUS_MESSAGE_ID == "":
            message = await channel.send("Server Offline!")
            STATUS_MESSAGE_ID = message.id
        else:
            message = await channel.fetch(STATUS_MESSAGE_ID)
            try:
                playercount = get_active_playercount()
                playerlist = get_active_playerlist()
                tps = "not yet"
                await message.edit(content=f"server: online ({tps}) | players online: {playercount} {playerlist}")
            except:
                await message.edit(content="Server Offline!")
        print("Status message updated!")

    except Exception as e:
        print(f"An error occured while updating status: {e}")

async def get_active_playerlist():
    response = await rcon_call("list")
    playercount = await get_active_playercount()
    if(int(playercount[0]) > 0):
        player_list = response.split(' ')[5:]
        return player_list
    else:
        return []


async def get_active_playercount():
    response = await rcon_call("list")
    return response.split(' ')[2]

bot.start(TOKEN)