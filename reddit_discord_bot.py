import discord
from discord.ext import tasks
import requests
import os
import json
import subprocess
import tempfile
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID    = int(os.getenv("CHANNEL_ID", "0"))

SUBREDDITS = ["long_porn", "Porn", "boobs"]
INTERVAL_MINUTES = 1
POSTS_PER_RUN = 2
SEEN_FILE = "seen_posts.json"
MAX_FILE_SIZE_MB = 24

VIDEO_DOMAINS = ["v.redd.it", "youtube.com", "youtu.be", "streamable.com", "gfycat.com", "redgifs.com", "clips.twitch.tv", "medal.tv"]

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(seen), f)

def is_video(post):
    if post.get("is_video"):
        return True
    return any(d in post.get("url", "") for d in VIDEO_DOMAINS)

def fetch_posts(seen):
    results = []
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"}
    for sub in SUBREDDITS:
        try:
            res = requests.get(f"https://www.reddit.com/r/{sub}/new.json?limit=25", headers=headers, timeout=10)
            res.raise_for_status()
            count = 0
            for item in res.json()["data"]["children"]:
                post = item["data"]
                if post["id"] not in seen and is_video(post):
                    results.append(post)
                    count += 1
                    if count >= POSTS_PER_RUN:
                        break
        except Exception as e:
            print(f"[ERROR] r/{sub}: {e}")
    return results

def download_video(url, output_path):
    try:
        cmd = ["yt-dlp", url, "-o", output_path, "--merge-output-format", "mp4", "-f", "bestvideo[height<=480]+bestaudio/best[height<=480]/best", "--max-filesize", f"{MAX_FILE_SIZE_MB}m", "--no-playlist", "--quiet"]
        result = subprocess.run(cmd, timeout=60)
        if result.returncode == 0 and os.path.exists(output_path):
            if os.path.getsize(output_path) / (1024*1024) <= MAX_FILE_SIZE_MB:
                return True
        return False
    except:
        return False

intents = discord.Intents.default()
client = discord.Client(intents=intents)
seen_posts = load_seen()

@tasks.loop(minutes=INTERVAL_MINUTES)
async def post_reddit():
    channel = client.get_channel(CHANNEL_ID)
    if not channel:
        return
    for post in fetch_posts(seen_posts):
        video_url = f"https://reddit.com{post['permalink']}" if post.get("is_video") else post.get("url", "")
        caption = f"**{post['title'][:200]}**\nr/{post['subreddit']} • 👍 {post['score']} • 💬 {post['num_comments']} • u/{post['author']}"
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "video.mp4")
            if download_video(video_url, output_path):
                await channel.send(content=caption, file=discord.File(output_path, filename="video.mp4"))
            else:
                await channel.send(content=f"{caption}\n{video_url}")
        seen_posts.add(post["id"])
    save_seen(seen_posts)

@client.event
async def on_ready():
    print(f"✅ {client.user} online")
    post_reddit.start()

client.run(DISCORD_TOKEN)
