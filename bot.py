import discord
from discord.ext import commands, tasks
from github import Github
import os
import json
from datetime import datetime

# Your Discord Bot Token
DISCORD_TOKEN = 'YOUR_DISCORD_BOT_TOKEN'

# GitHub Token and Repository
GITHUB_TOKEN = 'YOUR_GITHUB_TOKEN'
GITHUB_REPO = 'yourusername/yourrepository'

# Global variables
client = commands.Bot(command_prefix='!')
github_client = Github(GITHUB_TOKEN)
repo = github_client.get_repo(GITHUB_REPO)
channel_id = None
user_consent = {}  # To store user consent for collecting messages
state_file = "state.json"

# Load saved state from the file
if os.path.exists(state_file):
    with open(state_file, 'r') as f:
        saved_state = json.load(f)
else:
    saved_state = {"users": {}, "messages": []}  # Default state if no file exists

user_consent = saved_state['users']
collected_messages = saved_state['messages']

# Save state to the file
def save_state():
    with open(state_file, 'w') as f:
        json.dump({"users": user_consent, "messages": collected_messages}, f, indent=4)

# Run every hour to make a pull request
@tasks.loop(hours=1)
async def hourly_pull_request():
    """Make a pull request to GitHub every hour."""
    await send_to_github(None)  # Trigger the GitHub send function

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    hourly_pull_request.start()  # Start the hourly pull request task

@client.command()
async def privacy(ctx):
    """Command to set the channel where the consent message will be sent."""
    global channel_id
    channel_id = ctx.message.channel.id
    await ctx.send("The consent channel has been set.")

@client.event
async def on_message(message):
    """Check user consent and collect messages."""
    global user_consent, collected_messages
    
    # Ignore messages from the bot itself
    if message.author == client.user:
        return

    # Check if the user gave consent
    if message.author.id in user_consent and user_consent[message.author.id]:
        server_name = message.guild.name
        folder_name = server_name.replace(' ', '_')

        # Create a folder in the repo if it doesn't exist
        if not os.path.exists(folder_name):
            os.mkdir(folder_name)

        # Create a text file for the messages
        messages_count = len(collected_messages)
        file_name = f"{folder_name}/{server_name}_{(messages_count // 1000) + 1}.txt"

        with open(file_name, 'a') as file:
            file.write(f"{message.content}\n")
        
        # Save the message in the collected list
        collected_messages.append(message.content)
        save_state()  # Save the state every time a message is collected
        
        print(f"Collected message from {message.author.name}: {message.content}")
    
    await client.process_commands(message)

@client.event
async def on_reaction_add(reaction, user):
    """Handles the addition of a reaction, granting consent to collect messages."""
    global user_consent

    if reaction.message.channel.id == channel_id:
        if reaction.emoji == '👍':  # User consents to collect messages
            user_consent[user.id] = True
            await reaction.message.channel.send(f"{user.name} has given consent to collect messages.")
            await collect_old_messages(reaction.message.channel, user)  # Collect old messages
        
@client.event
async def on_reaction_remove(reaction, user):
    """Handles the removal of a reaction, revoking consent to collect messages."""
    global user_consent

    if reaction.message.channel.id == channel_id:
        if reaction.emoji == '👍':  # User revokes consent
            user_consent[user.id] = False
            await reaction.message.channel.send(f"{user.name} has revoked consent to collect messages.")

@client.command()
async def send_to_github(ctx):
    """Command to send collected messages to GitHub."""
    global user_consent, collected_messages
    server_name = ctx.guild.name
    folder_name = server_name.replace(' ', '_')
    
    # Use GitHub API to add new files in the repository
    for filename in os.listdir(folder_name):
        with open(f"{folder_name}/{filename}", 'r') as file:
            content = file.read()
        
        # Create a commit on GitHub
        repo.create_file(f"server_data/{server_name}/{filename}", "Collecting messages", content)
    
    await ctx.send("Messages have been sent to GitHub.")

async def collect_old_messages(channel, user):
    """Function to collect old messages from the channel."""
    global user_consent, collected_messages
    
    print(f"Collecting old messages from channel: {channel.name}")
    async for message in channel.history(limit=1000):  # Fetch the last 1000 messages
        if message.author.id == user.id:
            # Check if the user has consented to collect messages
            if user_consent.get(user.id, False):
                server_name = message.guild.name
                folder_name = server_name.replace(' ', '_')

                # Create the folder in the repo if it doesn't exist
                if not os.path.exists(folder_name):
                    os.mkdir(folder_name)

                # Create a text file for the messages
                messages_count = len(collected_messages)
                file_name = f"{folder_name}/{server_name}_{(messages_count // 1000) + 1}.txt"
                
                with open(file_name, 'a') as file:
                    file.write(f"{message.content}\n")
                
                # Save the message in the collected list
                collected_messages.append(message.content)
                save_state()  # Save the state every time a message is collected

                print(f"Collected old message from {message.author.name}: {message.content}")

# Run the bot
client.run(DISCORD_TOKEN)
