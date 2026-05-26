"""
Reddit → Discord Bot
Posts top new Reddit posts to a Discord channel at regular intervals.

Requirements:
    pip install discord.py praw python-dotenv

Setup:
    1. Create a .env file (see .env.example)
    2. Configure SUBREDDITS and CHANNEL_ID below
    3. Run: python reddit_discord_bot.py
"""

import discord
from discord.ext import tasks
import praw
import os
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# CONFIG — edit these
# ─────────────────────────────────────────────

DISCORD_TOKEN   = os.getenv("DISCORD_TOKEN")
REDDIT_CLIENT_ID     = os.getenv("REDDIT_CLIENT_ID")
REDDIT_CLIENT_SECRET = os.getenv("REDDIT_CLIENT_SECRET")
REDDIT_USER_AGENT    = "RedditDiscordBot/1.0"

# List of subreddits to pull from
SUBREDDITS = ["worldnews", "technology", "funny"]

# Discord channel ID to post in (right-click channel → Copy ID)
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))

# How often to post (in minutes)
INTERVAL_MINUTES = 30

# How many posts to send per interval, per subreddit
POSTS_PER_RUN = 1

# File to track already-posted IDs (avoids duplicates)
SEEN_FILE = "seen_posts.json"

# ─────────────────────────────────────────────


def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)


def get_reddit():
    return praw.Reddit(
        client_id=REDDIT_CLIENT_ID,
        client_secret=REDDIT_CLIENT_SECRET,
        user_agent=REDDIT_USER_AGENT,
    )


def fetch_new_posts(reddit, seen: set):
    """Fetch unseen posts from configured subreddits."""
    new_posts = []
    for sub_name in SUBREDDITS:
        subreddit = reddit.subreddit(sub_name)
        for post in subreddit.new(limit=10):
            if post.id not in seen:
                new_posts.append(post)
                if len(new_posts) >= POSTS_PER_RUN * len(SUBREDDITS):
                    return new_posts
    return new_posts


def build_embed(post) -> discord.Embed:
    """Turn a Reddit post into a Discord embed."""
    embed = discord.Embed(
        title=post.title[:256],
        url=f"https://reddit.com{post.permalink}",
        color=discord.Color.orange(),
        timestamp=datetime.utcfromtimestamp(post.created_utc),
    )
    embed.set_author(name=f"r/{post.subreddit.display_name}")
    embed.set_footer(text=f"👍 {post.score}  💬 {post.num_comments} comments  u/{post.author}")

    # Attach image if the post has one
    if post.url and any(post.url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
        embed.set_image(url=post.url)
    elif not post.is_self and post.url:
        embed.add_field(name="Link", value=post.url[:1024], inline=False)

    # Show text preview for text posts
    if post.is_self and post.selftext:
        preview = post.selftext[:300]
        if len(post.selftext) > 300:
            preview += "..."
        embed.description = preview

    return embed


# ─────────────────────────────────────────────
# Bot setup
# ─────────────────────────────────────────────

intents = discord.Intents.default()
client = discord.Client(intents=intents)
seen_posts = load_seen()


@tasks.loop(minutes=INTERVAL_MINUTES)
async def post_reddit():
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        print(f"[ERROR] Channel {CHANNEL_ID} not found. Check CHANNEL_ID.")
        return

    reddit = get_reddit()
    posts = fetch_new_posts(reddit, seen_posts)

    if not posts:
        print(f"[{datetime.now().strftime('%H:%M')}] No new posts found.")
        return

    for post in posts:
        embed = build_embed(post)
        await channel.send(embed=embed)
        seen_posts.add(post.id)
        print(f"[Posted] r/{post.subreddit} — {post.title[:60]}")

    save_seen(seen_posts)


@client.event
async def on_ready():
    print(f"✅ Logged in as {client.user}")
    print(f"📡 Watching: r/{' | r/'.join(SUBREDDITS)}")
    print(f"⏱  Posting every {INTERVAL_MINUTES} minutes to channel {CHANNEL_ID}\n")
    post_reddit.start()


client.run(DISCORD_TOKEN)
  
