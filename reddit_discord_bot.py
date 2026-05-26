"""
Reddit → Discord Bot (No API keys needed)
Posts new video posts from subreddits to a Discord channel at regular intervals.
"""

import discord
from discord.ext import tasks
import requests
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID", "0"))

SUBREDDITS = ["long_porn", "PublicFreakout", "funny"]

INTERVAL_MINUTES = 1
POSTS_PER_RUN = 2
SEEN_FILE = "seen_posts.json"

VIDEO_DOMAINS = [
    "v.redd.it", "youtube.com", "youtu.be",
    "streamable.com", "gfycat.com", "redgifs.com",
    "clips.twitch.tv", "medal.tv"
]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def is_video(post: dict) -> bool:
    if post.get("is_video"):
        return True
    url = post.get("url", "")
    return any(domain in url for domain in VIDEO_DOMAINS)

def fetch_posts(seen: set) -> list:
    results = []
    headers = {"User-Agent": "RedditDiscordBot/1.0"}
    for sub in SUBREDDITS:
        try:
            url = f"https://www.reddit.com/r/{sub}/new.json?limit=25"
            res = requests.get(url, headers=headers, timeout=10)
            res.raise_for_status()
            posts = res.json()["data"]["children"]
            count = 0
            for item in posts:
                post = item["data"]
                if post["id"] not in seen and is_video(post):
                    results.append(post)
                    count += 1
                    if count >= POSTS_PER_RUN:
                        break
        except Exception as e:
            print(f"[ERROR] Failed to fetch r/{sub}: {e}")
    return results

def build_embed(post: dict) -> discord.Embed:
    embed = discord.Embed(
        title=post["title"][:256],
        url=f"https://reddit.com{post['permalink']}",
        color=discord.Color.orange(),
        timestamp=datetime.utcfromtimestamp(post["created_utc"]),
    )
    embed.set_author(name=f"r/{post['subreddit']}")
    embed.set_footer(text=f"👍 {post['score']}  💬 {post['num_comments']} comments  u/{post['author']}")
    if post.get("is_video"):
        embed.add_field(name="🎬 Video", value=f"https://reddit.com{post['permalink']}", inline=False)
    elif post.get("url"):
        embed.add_field(name="🎬 Video", value=post["url"][:1024], inline=False)
    return embed

intents = discord.Intents.default()
client = discord.Client(intents=intents)
seen_posts = load_seen()

@tasks.loop(minutes=INTERVAL_MINUTES)
async def post_reddit():
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print(f"[ERROR] Channel {CHANNEL_ID} not found.")
        return
    posts = fetch_posts(seen_posts)
    if not posts:
        print(f"[{datetime.now().strftime('%H:%M')}] No new video posts found.")
        return
    for post in posts:
        embed = build_embed(post)
        await channel.send(embed=embed)
        seen_posts.add(post["id"])
        print(f"[Posted] r/{post['subreddit']} — {post['title'][:60]}")
    save_seen(seen_posts)

@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    print(f"📡 Watching: r/{' | r/'.join(SUBREDDITS)}")
    print(f"⏱  Posting every {INTERVAL_MINUTES} min → channel {CHANNEL_ID}\n")
    post_reddit.start()

client.run(DISCORD_TOKEN)
