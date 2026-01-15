"""Main FastAPI application for Mattermost bot service."""

import logging
import hashlib
import time
import random
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict
from src.bot import MattermostBot
from src.config import Config

# Import bot registry for API endpoints
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "shared"))
    from bot_registry import BotRegistry
    BOT_REGISTRY_AVAILABLE = True
except ImportError:
    BOT_REGISTRY_AVAILABLE = False
    BotRegistry = None

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Mattermost Bot Service")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global bot instance
bot: Optional[MattermostBot] = None


# Track last processed post ID per channel per bot
_last_post_ids = {}  # Format: {bot_username: {channel_id: post_id}}
# Track messages processed by webhooks to avoid duplicate processing in polling
# Format: {(bot_username, channel_id, message_hash): timestamp}
# We use message_hash because webhooks don't always include post_id
_webhook_processed_messages = {}  # Dict to track when messages were processed


async def poll_channel_messages_for_collab(primary_token: str):
    """
    Poll public/private channels and let service bots optionally respond like humans.
    DMs are excluded here (DM behavior remains handled by per-bot DM polling).
    """
    import asyncio
    import httpx
    from urllib.parse import urlparse

    if not Config.CHANNEL_COLLAB_ENABLED:
        logger.info("Channel collaboration disabled (CHANNEL_COLLAB_ENABLED=false)")
        return

    parsed = urlparse(Config.MATTERMOST_URL)
    hostname = parsed.hostname or "mattermost"
    if hostname in ["localhost", "127.0.0.1"]:
        hostname = "mattermost"
    api_url = f"{parsed.scheme or 'http'}://{hostname}:{parsed.port or 8065}/api/v4"
    headers = {"Authorization": f"Bearer {primary_token}"}

    service_bots = ["gaia", "thoth", "maat"]
    known_bot_usernames = set(service_bots + [Config.MATTERMOST_BOT_USERNAME])

    last_since_ms: dict[str, int] = {}
    processed_posts: set[str] = set()
    last_bot_response_at: dict[tuple[str, str, str], float] = {}  # (bot, channel_id, root_id_or_post_id) -> ts
    user_cache: dict[str, tuple[str, float]] = {}  # user_id -> (username, ts)

    logger.info("Starting channel collaboration poller")
    await asyncio.sleep(2)

    # Tokens we can use to enumerate channels / read posts (private channels require membership)
    token_by_name = {
        "primary": primary_token,
        "gaia": Config.get_bot_token("gaia"),
        "thoth": Config.get_bot_token("thoth"),
        "maat": Config.get_bot_token("maat"),
    }
    token_by_name = {k: v for k, v in token_by_name.items() if v}

    async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
        # Resolve user IDs per token once
        user_id_by_name: dict[str, str] = {}
        for name, tok in token_by_name.items():
            r = await client.get(f"{api_url}/users/me", headers={"Authorization": f"Bearer {tok}"})
            if r.status_code == 200:
                user_id_by_name[name] = r.json().get("id")
            else:
                logger.warning(f"Channel collab: cannot auth token '{name}': {r.status_code} {r.text[:120]}")

        if "primary" not in user_id_by_name:
            logger.error("Channel collab: cannot start (no valid primary token)")
            return

        while True:
            # Runtime overrides (no restart needed)
            from src.runtime_settings import RuntimeSettings
            rs = RuntimeSettings().get()
            cc = rs.get("channel_collab", {}) if isinstance(rs, dict) else {}
            temps = rs.get("bot_temperatures", {}) if isinstance(rs, dict) else {}

            base_prob_override = cc.get("base_response_prob")
            bot_to_bot_prob_override = cc.get("bot_to_bot_prob")
            max_replies_override = cc.get("max_bot_replies_per_post")
            cooldown_override = cc.get("bot_cooldown_seconds")
            reply_in_thread_override = cc.get("reply_in_thread")
            allow_bot_to_bot_override = cc.get("allow_bot_to_bot")

            await asyncio.sleep(max(1.0, float(cc.get("poll_seconds", Config.CHANNEL_COLLAB_POLL_SECONDS))))

            # Union channels visible to any bot token (private channels require membership)
            channel_map: dict[str, dict] = {}  # channel_id -> channel dict
            channel_reader_token: dict[str, str] = {}  # channel_id -> token to read posts

            for name, uid in user_id_by_name.items():
                tok = token_by_name[name]
                chans = await client.get(
                    f"{api_url}/users/{uid}/channels",
                    headers={"Authorization": f"Bearer {tok}"},
                )
                if chans.status_code != 200:
                    continue
                for c in chans.json():
                    if c.get("type") not in ["O", "P"]:
                        continue
                    cid = c.get("id")
                    if not cid:
                        continue
                    channel_map[cid] = c
                    channel_reader_token.setdefault(cid, tok)

            channels = list(channel_map.values())
            now_ms = int(time.time() * 1000)

            for c in channels:
                channel_id = c.get("id")
                if not channel_id:
                    continue

                since = last_since_ms.get(channel_id)
                if since is None:
                    lookback_ms = max(5, Config.CHANNEL_COLLAB_INITIAL_LOOKBACK_SECONDS) * 1000
                    since = now_ms - lookback_ms

                read_token = channel_reader_token.get(channel_id, primary_token)
                posts_resp = await client.get(
                    f"{api_url}/channels/{channel_id}/posts",
                    headers={"Authorization": f"Bearer {read_token}"},
                    params={"since": since},
                )
                if posts_resp.status_code != 200:
                    continue

                payload = posts_resp.json()
                order = payload.get("order", [])
                posts = payload.get("posts", {})
                if not order:
                    last_since_ms[channel_id] = now_ms
                    continue

                # Oldest -> newest
                for post_id in reversed(order):
                    if post_id in processed_posts:
                        continue

                    post = posts.get(post_id, {})
                    msg = (post.get("message") or "").strip()
                    user_id = post.get("user_id")
                    if not msg or not user_id:
                        processed_posts.add(post_id)
                        continue

                    cached = user_cache.get(user_id)
                    if cached and time.time() - cached[1] < 300:
                        sender_username = cached[0]
                    else:
                        u = await client.get(f"{api_url}/users/{user_id}", headers={"Authorization": f"Bearer {read_token}"})
                        sender_username = (u.json().get("username") or "unknown").lower() if u.status_code == 200 else "unknown"
                        user_cache[user_id] = (sender_username, time.time())

                    sender_is_bot = sender_username in known_bot_usernames
                    allow_bot_to_bot = bool(allow_bot_to_bot_override) if allow_bot_to_bot_override is not None else Config.CHANNEL_COLLAB_ALLOW_BOT_TO_BOT
                    if sender_is_bot and not allow_bot_to_bot:
                        processed_posts.add(post_id)
                        continue

                    mentions = []
                    if bot and bot.message_router:
                        mentions = [m.lower() for m in bot.message_router.extract_mentions(msg)]
                    mentioned_bots = [b for b in service_bots if b in mentions]

                    responders: list[str] = []
                    if mentioned_bots:
                        responders = mentioned_bots
                    else:
                        # For non-mentioned channel messages, all bots *observe* the message, but we
                        # only *ask* a bot to consider responding with some probability to limit API calls.
                        base_prob_default = Config.CHANNEL_COLLAB_BOT_TO_BOT_PROB if sender_is_bot else Config.CHANNEL_COLLAB_BASE_RESPONSE_PROB
                        base_prob = bot_to_bot_prob_override if sender_is_bot and bot_to_bot_prob_override is not None else (
                            base_prob_override if (not sender_is_bot and base_prob_override is not None) else base_prob_default
                        )
                        responders = [b for b in service_bots if random.random() < base_prob]
                        # Ensure at least one bot occasionally considers responding
                        if not responders and random.random() < base_prob:
                            responders = [random.choice(service_bots)]

                    root_id = post.get("root_id") or post_id
                    final_responders: list[str] = []
                    for bname in responders:
                        if sender_username == bname:
                            continue
                        ck = (bname, channel_id, root_id)
                        cooldown = float(cooldown_override) if cooldown_override is not None else Config.CHANNEL_COLLAB_BOT_COOLDOWN_SECONDS
                        if time.time() - last_bot_response_at.get(ck, 0.0) < cooldown:
                            continue
                        final_responders.append(bname)

                    # Mentions can invite multiple bots; otherwise we cap replies per post.
                    max_replies = int(max_replies_override) if max_replies_override is not None else Config.CHANNEL_COLLAB_MAX_BOT_REPLIES_PER_POST
                    reply_limit = len(final_responders) if mentioned_bots else max_replies

                    for bname in final_responders[:reply_limit]:
                        try:
                            temp = temps.get(bname) if isinstance(temps, dict) else None
                            response_text = await bot.service_handler.handle_service_message(
                                bot_username=bname,
                                message=msg,
                                mattermost_user_id=user_id,
                                mattermost_username=sender_username,
                                context={
                                    "channel_observe": True,
                                    "addressed": bname in mentioned_bots,
                                    "llm_temperature": temp,
                                    "channel_id": channel_id,
                                    "channel_name": c.get("name"),
                                    "sender": sender_username,
                                },
                            )
                            if not response_text:
                                continue
                            # Threading is optional; no special-casing for quoted text.
                            reply_in_thread = bool(reply_in_thread_override) if reply_in_thread_override is not None else Config.CHANNEL_COLLAB_REPLY_IN_THREAD
                            reply_root_id = post_id if reply_in_thread else None

                            await bot.post_message(
                                channel_id=channel_id,
                                text=response_text,
                                bot_username=bname,
                                root_id=reply_root_id,
                            )
                            last_bot_response_at[(bname, channel_id, root_id)] = time.time()
                        except Exception as e:
                            logger.error(f"Channel collab: error responding as {bname}: {e}", exc_info=True)

                    processed_posts.add(post_id)

                last_since_ms[channel_id] = now_ms

async def poll_dm_messages_for_bot(bot_username: str, bot_token: str):
    """Poll for new DM messages and channel @mentions for a specific service bot."""
    import asyncio
    import httpx
    from urllib.parse import urlparse
    
    logger.info(f"Starting DM polling for {bot_username}")
    await asyncio.sleep(2)  # Initial delay
    
    # Use httpx directly instead of mattermostdriver (avoids websocket issues)
    parsed = urlparse(Config.MATTERMOST_URL)
    # If hostname is localhost, use 'mattermost' for Docker networking
    hostname = parsed.hostname or 'mattermost'
    if hostname in ['localhost', '127.0.0.1']:
        hostname = 'mattermost'
    api_url = f"{parsed.scheme or 'http'}://{hostname}:{parsed.port or 8065}/api/v4"
    headers = {"Authorization": f"Bearer {bot_token}"}
    
    while True:
        try:
            await asyncio.sleep(5)  # Poll every 5 seconds
            
            try:
                # Get this bot's user ID using httpx
                async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
                    try:
                        user_response = await client.get(f"{api_url}/users/me", headers=headers)
                        if user_response.status_code != 200:
                            logger.warning(f"{bot_username}: Could not get user info: {user_response.status_code} - {user_response.text[:100]}")
                            await asyncio.sleep(10)
                            continue
                        bot_user = user_response.json()
                        bot_user_id = bot_user["id"]
                        logger.debug(f"{bot_username}: Bot user ID: {bot_user_id}")
                    except Exception as e:
                        logger.error(f"{bot_username}: Error getting bot user: {e}", exc_info=True)
                        await asyncio.sleep(10)
                        continue
                    
                    # Get DM channels for this bot (DMs it receives)
                    try:
                        channels_response = await client.get(f"{api_url}/users/{bot_user_id}/channels", headers=headers)
                        if channels_response.status_code != 200:
                            logger.warning(f"{bot_username}: Could not get channels: {channels_response.status_code}")
                            dm_channels = []
                        else:
                            all_channels = channels_response.json()
                            logger.info(f"{bot_username}: Got {len(all_channels)} total channels")
                            # Filter for DM channels
                            dm_channels = [c for c in all_channels if c.get("type") == "D"]
                            # IMPORTANT: DM polling should not process channels.
                            # Channel behavior is handled by the channel collaboration poller.
                            group_channels = []
                            if len(dm_channels) > 0:
                                logger.info(f"{bot_username}: Found {len(dm_channels)} DM channels")
                                for dm in dm_channels:
                                    logger.debug(f"{bot_username}: DM channel ID: {dm.get('id')}")
                            else:
                                logger.debug(f"{bot_username}: Found {len(dm_channels)} DM channels (no DMs yet)")
                            # group_channels intentionally empty
                    except Exception as e:
                        logger.error(f"{bot_username}: Error getting channels: {e}", exc_info=True)
                        dm_channels = []
                        group_channels = []
                
                    # Process DM channels
                    for channel in dm_channels:
                        channel_id = channel.get("id")
                        
                        # Get channel members
                        try:
                            members_response = await client.get(f"{api_url}/channels/{channel_id}/members", headers=headers)
                            if members_response.status_code != 200:
                                logger.debug(f"{bot_username}: Could not get members for {channel_id}")
                                continue
                            members = members_response.json()
                            member_ids = [m.get("user_id") for m in members]
                            
                            # Get recent posts in this channel
                            try:
                                # Get posts since last check
                                last_post_ids = _last_post_ids.get(bot_username, {})
                                last_post_id = last_post_ids.get(channel_id, "")
                                
                                if last_post_id:
                                    posts_response = await client.get(
                                        f"{api_url}/channels/{channel_id}/posts",
                                        headers=headers,
                                        params={"since": last_post_id}
                                    )
                                    # If "since" parameter fails (400), the post_id is invalid/expired - clear it and use per_page
                                    if posts_response.status_code == 400:
                                        logger.warning(f"{bot_username}: 'since' parameter failed for {channel_id} with post_id {last_post_id[:20]}... (invalid/expired), clearing and using per_page")
                                        # Clear the invalid last_post_id
                                        if bot_username in _last_post_ids and channel_id in _last_post_ids[bot_username]:
                                            del _last_post_ids[bot_username][channel_id]
                                        last_post_id = ""  # Reset for this iteration
                                        posts_response = await client.get(
                                            f"{api_url}/channels/{channel_id}/posts",
                                            headers=headers,
                                            params={"per_page": 20}
                                        )
                                else:
                                    # First time checking - get last 20 posts
                                    posts_response = await client.get(
                                        f"{api_url}/channels/{channel_id}/posts",
                                        headers=headers,
                                        params={"per_page": 20}
                                    )
                                
                                if posts_response.status_code != 200:
                                    logger.warning(f"{bot_username}: Could not get posts for {channel_id}: {posts_response.status_code} - {posts_response.text[:100]}")
                                    continue
                                
                                posts = posts_response.json()
                                post_list = posts.get("posts", {})
                                order = posts.get("order", [])
                                
                                logger.debug(f"{bot_username}: Channel {channel_id[:20]}... has {len(order)} posts, last_post_id={last_post_id[:20] if last_post_id else 'None'}...")
                                
                                # Determine which posts to process
                                # Mattermost order array is sorted newest first
                                posts_to_process = []
                                if last_post_id and last_post_id in order:
                                    # Find the index of last_post_id in the order
                                    last_index = order.index(last_post_id)
                                    # Process all posts that come before last_post_id (newer posts)
                                    posts_to_process = order[:last_index]
                                    logger.info(f"{bot_username}: Found {len(posts_to_process)} new posts after last_post_id {last_post_id[:20]}...")
                                elif last_post_id:
                                    # last_post_id exists but not in current 20 posts
                                    # This means either:
                                    # 1. The post is older than the 20 posts we fetched (already processed)
                                    # 2. The post_id is invalid (should have been cleared)
                                    # In either case, don't process anything - we've already processed everything
                                    logger.info(f"{bot_username}: last_post_id {last_post_id[:20]}... not in current posts - skipping (already processed)")
                                    posts_to_process = []
                                else:
                                    # No last_post_id - process newest post only (first time checking this channel)
                                    if order:
                                        posts_to_process = [order[0]]  # Just the newest post
                                        logger.info(f"{bot_username}: No last_post_id, processing newest post only (first check)")
                                
                                # Process new posts (excluding bot's own posts)
                                # Process in reverse order (newest first) to handle the most recent message
                                for post_id in reversed(posts_to_process):
                                    # Skip if we've already processed this post (double-check)
                                    if post_id == last_post_id:
                                        logger.debug(f"{bot_username}: Skipping post {post_id[:20]}... (matches last_post_id)")
                                        continue
                                    
                                    post = post_list.get(post_id, {})
                                    post_user_id = post.get("user_id")
                                    message = post.get("message", "").strip()
                                    
                                    # Skip empty messages
                                    if not message:
                                        continue
                                    
                                    # Skip bot's own messages (check by user_id first, then by username)
                                    if post_user_id == bot_user_id:
                                        logger.debug(f"{bot_username}: Skipping own message {post_id} (user_id match)")
                                        # Update last_post_id to skip this message in future polls
                                        if bot_username not in _last_post_ids:
                                            _last_post_ids[bot_username] = {}
                                        current_latest = _last_post_ids[bot_username].get(channel_id, "")
                                        if not current_latest or post_id > current_latest:
                                            _last_post_ids[bot_username][channel_id] = post_id
                                        continue
                                    
                                    # Get the user who sent the message to check username
                                    sender_username = None
                                    try:
                                        user_response = await client.get(f"{api_url}/users/{post_user_id}", headers=headers)
                                        if user_response.status_code == 200:
                                            sender_user = user_response.json()
                                            sender_username = sender_user.get("username", "").lower()
                                            
                                            # Double-check: skip if sender is this bot or any service bot
                                            if sender_username == bot_username or (bot and bot.service_handler and bot.service_handler.is_service_bot(sender_username)):
                                                logger.debug(f"{bot_username}: Skipping message from bot {sender_username} (post_id {post_id})")
                                                # Update last_post_id to skip this message in future polls
                                                if bot_username not in _last_post_ids:
                                                    _last_post_ids[bot_username] = {}
                                                current_latest = _last_post_ids[bot_username].get(channel_id, "")
                                                if not current_latest or post_id > current_latest:
                                                    _last_post_ids[bot_username][channel_id] = post_id
                                                continue
                                    except Exception:
                                        sender_username = "unknown"
                                    
                                    # Skip rate limit warning messages (they start with ⚠️)
                                    if message.startswith("⚠️") or "Rate limit" in message or "rate limit" in message.lower():
                                        logger.debug(f"{bot_username}: Skipping rate limit message {post_id}")
                                        # Update last_post_id to skip this message in future polls
                                        if bot_username not in _last_post_ids:
                                            _last_post_ids[bot_username] = {}
                                        current_latest = _last_post_ids[bot_username].get(channel_id, "")
                                        if not current_latest or post_id > current_latest:
                                            _last_post_ids[bot_username][channel_id] = post_id
                                        continue
                                    
                                    # Process the message as this service bot
                                    logger.info(f"{bot_username}: Processing DM from {sender_username or 'unknown'}: {message[:50]}")
                                    
                                    # Route to service handler
                                    if not bot:
                                        logger.error(f"{bot_username}: Global bot variable is None - bot not initialized")
                                    elif not bot.service_handler:
                                        logger.error(f"{bot_username}: Bot service_handler is None")
                                    else:
                                        logger.info(f"{bot_username}: Routing to service handler")
                                        try:
                                            response_text = await bot.service_handler.handle_service_message(
                                                bot_username=bot_username,
                                                message=message,
                                                mattermost_user_id=post_user_id,
                                                mattermost_username=sender_username  # Pass username to avoid auth_bridge lookup
                                            )
                                            
                                            if response_text:
                                                logger.info(f"{bot_username}: Got response: {response_text[:100]}")
                                                # Post response as this bot using httpx
                                                response_post_id = await post_message_as_bot_httpx(
                                                    api_url=api_url,
                                                    bot_token=bot_token,
                                                    channel_id=channel_id,
                                                    text=response_text,
                                                    bot_username=bot_username
                                                )
                                                logger.info(f"{bot_username}: Posted DM response")
                                                
                                                # Update last_post_id to the response post_id (newest post) to prevent re-processing
                                                if response_post_id:
                                                    if bot_username not in _last_post_ids:
                                                        _last_post_ids[bot_username] = {}
                                                    _last_post_ids[bot_username][channel_id] = response_post_id
                                                    logger.debug(f"{bot_username}: Updated last_post_id to response post_id {response_post_id[:20]}...")
                                                else:
                                                    # Fallback: update to the user's post_id if we couldn't get response post_id
                                                    if bot_username not in _last_post_ids:
                                                        _last_post_ids[bot_username] = {}
                                                    _last_post_ids[bot_username][channel_id] = post_id
                                                    logger.debug(f"{bot_username}: Updated last_post_id to user post_id {post_id[:20]}...")
                                            else:
                                                logger.warning(f"{bot_username}: Service handler returned no response")
                                                # Still update last_post_id to prevent re-processing
                                                if bot_username not in _last_post_ids:
                                                    _last_post_ids[bot_username] = {}
                                                _last_post_ids[bot_username][channel_id] = post_id
                                                logger.debug(f"{bot_username}: Updated last_post_id to user post_id {post_id[:20]}... (no response)")
                                        except Exception as e:
                                            logger.error(f"{bot_username}: Error in service handler: {e}", exc_info=True)
                                            # Still update last_post_id to prevent infinite loops on errors
                                            if bot_username not in _last_post_ids:
                                                _last_post_ids[bot_username] = {}
                                            _last_post_ids[bot_username][channel_id] = post_id
                                            logger.debug(f"{bot_username}: Updated last_post_id to user post_id {post_id[:20]}... (error)")
                                    
                                    # After processing, update last_post_id to the newest post we've seen in this channel
                                    # This ensures we don't re-process messages even if response posting failed
                                    # Only update if we actually processed a post (not if we skipped everything)
                                    if posts_to_process and order and order[0]:  # order[0] is the newest post
                                        newest_post_id = order[0]
                                        if bot_username not in _last_post_ids:
                                            _last_post_ids[bot_username] = {}
                                        current_latest = _last_post_ids[bot_username].get(channel_id, "")
                                        if not current_latest or newest_post_id > current_latest:
                                            _last_post_ids[bot_username][channel_id] = newest_post_id
                                            logger.info(f"{bot_username}: Updated last_post_id to newest post in channel: {newest_post_id[:20]}...")
                                
                            except Exception as e:
                                logger.debug(f"Error processing posts in DM channel {channel_id} for {bot_username}: {e}")
                        except Exception as e:
                            logger.debug(f"Error checking DM channel {channel_id} for {bot_username}: {e}")
                    
                    # NOTE: channel handling intentionally removed here.
                    # Public/private channel behavior is handled by `poll_channel_messages_for_collab`.
                        
            except Exception as e:
                logger.debug(f"Error polling messages for {bot_username}: {e}")
                
        except Exception as e:
            logger.error(f"Error in DM polling loop for {bot_username}: {e}")
            await asyncio.sleep(10)  # Wait longer on error


async def post_message_as_bot_httpx(api_url: str, bot_token: str, channel_id: str, text: str, bot_username: str) -> Optional[str]:
    """Post a message as a specific bot using httpx.
    
    Returns:
        The post_id of the created post, or None if posting failed
    """
    try:
        import httpx
        
        post_data = {
            "channel_id": channel_id,
            "message": text
            # Note: override_username is not needed when using bot tokens - the message will appear as the bot user automatically
        }
        
        async with httpx.AsyncClient(timeout=10.0, verify=False) as client:
            response = await client.post(
                f"{api_url}/posts",
                json=post_data,
                headers={"Authorization": f"Bearer {bot_token}"}
            )
            
            if response.status_code == 201:
                response_data = response.json()
                post_id = response_data.get("id")
                logger.info(f"{bot_username}: Successfully posted message to channel {channel_id} (post_id: {post_id[:20] if post_id else 'unknown'}...)")
                return post_id
            else:
                logger.error(f"{bot_username}: Error posting message: {response.status_code} - {response.text[:200]}")
                return None
                # Try to extract error details
                try:
                    error_data = response.json()
                    error_msg = error_data.get("message", error_data.get("error", response.text[:200]))
                    logger.error(f"{bot_username}: Post error details: {error_msg}")
                except:
                    pass
        
    except Exception as e:
        logger.error(f"Error posting message as {bot_username}: {e}", exc_info=True)


@app.on_event("startup")
async def startup_event():
    """Initialize bot on startup."""
    global bot
    try:
        bot = MattermostBot()
        logger.info("Mattermost bot initialized")
        
        # Start DM polling for each service bot in background
        import asyncio
        
        # Load bot registry and start polling for each service bot
        if BOT_REGISTRY_AVAILABLE:
            try:
                registry = BotRegistry()
                service_bots = ["gaia", "thoth", "maat"]
                
                logger.info(f"Loading bot registry from: {registry.registry_path}")
                for bot_username in service_bots:
                    bot_info = registry.get_bot(bot_username)
                    if bot_info:
                        logger.info(f"Found {bot_username} in registry: active={bot_info.is_active}, has_token={bool(bot_info.token)}")
                        if bot_info.is_active and bot_info.token:
                            logger.info(f"Starting DM polling for {bot_username}")
                            asyncio.create_task(poll_dm_messages_for_bot(bot_username, bot_info.token))
                        else:
                            logger.warning(f"Service bot {bot_username} is inactive or missing token")
                    else:
                        logger.warning(f"Service bot {bot_username} not found in registry")
            except Exception as e:
                logger.error(f"Could not start service bot DM polling: {e}", exc_info=True)
        else:
            logger.warning("Bot registry not available - DM polling for service bots disabled")
        
        logger.info("Started DM message polling for service bots")

        # Start channel collaboration poller using the primary bot token
        try:
            primary_token = Config.get_bot_token()
            if primary_token:
                asyncio.create_task(poll_channel_messages_for_collab(primary_token))
                logger.info("Started channel collaboration poller")
            else:
                logger.warning("Channel collaboration poller not started: no primary bot token")
        except Exception as e:
            logger.error(f"Could not start channel collaboration poller: {e}", exc_info=True)
    except Exception as e:
        logger.warning(f"Bot initialization had issues: {e}")
        logger.warning("Bot service will start but may not function until Mattermost is configured")
        # Try to create bot anyway - it will handle errors gracefully
        try:
            bot = MattermostBot()
        except Exception:
            logger.error("Could not initialize bot at all")
            bot = None


class MattermostWebhook(BaseModel):
    """Mattermost webhook payload."""
    event: Optional[str] = None
    data: Optional[Dict] = None
    # Slash command format
    command: Optional[str] = None
    text: Optional[str] = None
    user_id: Optional[str] = None
    channel_id: Optional[str] = None
    team_id: Optional[str] = None
    # Outgoing webhook format
    token: Optional[str] = None
    trigger_word: Optional[str] = None


@app.post("/webhook")
async def handle_webhook(request: Request):
    """
    Handle incoming Mattermost webhook or slash command.
    
    Supports:
    - Slash commands
    - Outgoing webhooks
    - Incoming webhooks
    - Direct messages (via incoming webhook from Mattermost)
    """
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Try to parse as JSON first
        try:
            body = await request.json()
        except Exception:
            # Try form data
            form = await request.form()
            body = dict(form)
        
        # Check if this is an incoming webhook (has 'text' and 'username' but no 'trigger_word')
        # This handles DMs sent via incoming webhook
        if "text" in body and "username" in body and "trigger_word" not in body and "command" not in body:
            # This might be an incoming webhook for a DM
            logger.info(f"Received incoming webhook: username={body.get('username')}, text={body.get('text')[:50]}")
            
            # Check if it's a DM to a service bot
            channel_id = body.get("channel_id")
            user_id = body.get("user_id") or body.get("user_name")
            message = body.get("text", "").strip()
            
            if channel_id and message:
                # Try to determine if this is a DM with a service bot
                # We'll check by trying to route it
                event_data = {
                    "event": "posted",
                    "data": {
                        "post": {
                            "id": body.get("post_id", "incoming_webhook_post"),
                            "channel_id": channel_id,
                            "user_id": user_id,
                            "message": message
                        }
                    }
                }
                
                response = await bot.handle_post_event(event_data)
                
                if response:
                    channel_id = response.get("channel_id") or channel_id
                    response_text = response.get("text", "")
                    
                    if channel_id and response_text:
                        logger.info(f"Posting DM response to channel {channel_id}")
                        try:
                            # Get bot username from response if available (set by handle_post_event)
                            bot_username_for_posting = response.get("bot_username")
                            
                            # If not in response, try to detect from channel
                            if not bot_username_for_posting and bot.driver:
                                try:
                                    channel_info = bot.driver.channels.get_channel(channel_id)
                                    if channel_info.get("type") == "D":
                                        # Get other user in DM
                                        members = channel_info.get("members", [])
                                        if not members:
                                            try:
                                                channel_members = bot.driver.channels.get_channel_members(channel_id)
                                                members = [m.get("user_id") for m in channel_members]
                                            except Exception:
                                                pass
                                        
                                        for member_id in members:
                                            if member_id != user_id:
                                                try:
                                                    other_user = bot.driver.users.get_user(member_id)
                                                    other_username = other_user.get("username", "").lower()
                                                    if bot.service_handler.is_service_bot(other_username):
                                                        bot_username_for_posting = other_username
                                                        break
                                                except Exception:
                                                    pass
                                except Exception as e:
                                    logger.debug(f"Could not detect bot from channel: {e}")
                            
                            await bot.post_message(
                                channel_id=channel_id,
                                text=response_text,
                                attachments=response.get("attachments"),
                                bot_username=bot_username_for_posting
                            )
                            logger.info(f"DM response posted successfully as {bot_username_for_posting or 'rpg-bot'}")
                        except Exception as e:
                            logger.error(f"Error posting DM response: {e}", exc_info=True)
                
                return {"status": "ok"}
        
        # Validate slash command token if present
        if "command" in body and Config.MATTERMOST_SLASH_COMMAND_TOKEN:
            token = body.get("token")
            if token != Config.MATTERMOST_SLASH_COMMAND_TOKEN:
                logger.warning(f"Invalid slash command token received")
                raise HTTPException(status_code=401, detail="Invalid token")
        
        # Check if it's a slash command
        if "command" in body:
            command = body.get("command", "")
            text = body.get("text", "").strip()
            
            logger.info(f"Received slash command: command='{command}', text='{text}'")
            logger.info(f"DEBUG: Full body keys: {list(body.keys())}")
            logger.info(f"DEBUG: Body user_id: {body.get('user_id')}, user_name: {body.get('user_name')}, username: {body.get('username')}")
            
            # Handle both formats:
            # 1. /rpg-health (command="/rpg-health", text="")
            # 2. /rpg health (command="/rpg", text="health")
            if command == "/rpg" or command.startswith("/rpg-"):
                if command == "/rpg":
                    # Format: /rpg health -> command_name="health"
                    parts = text.split() if text else []
                    command_name = parts[0] if parts else ""
                    args = parts[1:] if len(parts) > 1 else []
                else:
                    # Format: /rpg-health -> command_name="health"
                    command_name = command[5:]  # Remove "/rpg-" prefix
                    args = text.split() if text else []
                
                logger.info(f"Parsed command: command_name='{command_name}', args={args}")
                logger.info(f"TEST: About to get user_id from body")
                
                user_id = body.get("user_id")
                channel_id = body.get("channel_id")
                logger.info(f"TEST: Got user_id={user_id}, channel_id={channel_id}")
                
                # Get Mattermost user info for authentication
                mattermost_username = None
                mattermost_email = None
                
                # First try to get from request body (slash commands include user_name)
                mattermost_username = body.get("user_name") or body.get("username")
                logger.info(f"Username from body: {mattermost_username}, user_id: {user_id}")
                
                # Try to get more info from Mattermost API if driver is available
                if bot and bot.driver and user_id:
                    try:
                        logger.info(f"Attempting to get Mattermost user info for user_id={user_id}")
                        user_info = bot.driver.users.get_user(user_id)
                        mattermost_username = mattermost_username or user_info.get("username")
                        mattermost_email = user_info.get("email")
                        logger.info(f"Got Mattermost user info: username={mattermost_username}, email={mattermost_email}")
                    except Exception as e:
                        logger.warning(f"Could not get Mattermost user info via API: {e}")
                        # Continue with username from body if available
                
                # If still no username, use user_id as fallback
                if not mattermost_username and user_id:
                    mattermost_username = f"mm_user_{user_id[:8]}"
                    logger.info(f"Using fallback username: {mattermost_username}")
                
                logger.info(f"Final auth info: username={mattermost_username}, email={mattermost_email}, user_id={user_id}")
                
                if command_name:
                    try:
                        logger.info(f"Calling handle_command with user_id={user_id}, username={mattermost_username}, email={mattermost_email}")
                        response = await bot.admin_handler.handle_command(
                            command_name, 
                            args, 
                            user_id,
                            mattermost_username=mattermost_username,
                            mattermost_email=mattermost_email
                        )
                        logger.info(f"Command response: {response}")
                    except Exception as e:
                        logger.error(f"Error handling command: {e}", exc_info=True)
                        response = {
                            "text": f"Error executing command: {str(e)}",
                            "response_type": "ephemeral"
                        }
                else:
                    # No subcommand provided - show help
                    response = {
                        "text": "**RPG LLM Commands**\n\nType `/rpg` followed by one of these commands:\n\n" +
                                "**Character Management:**\n" +
                                "• `health` - Check service status\n" +
                                "• `create-character [name]` - Create a new character\n" +
                                "• `list-characters` - List your characters\n" +
                                "• `delete-character <id>` - Delete a character\n\n" +
                                "**Game Sessions:**\n" +
                                "• `create-session [name]` - Create a game session\n" +
                                "• `join-session <id>` - Join a session\n\n" +
                                "**Gameplay:**\n" +
                                "• `roll <dice>` - Roll dice (e.g., `roll 1d20`)\n" +
                                "• `world-event <description>` - Record world event\n" +
                                "• `system-status` - Get system status (GM only)\n\n" +
                                "**Examples:**\n" +
                                "• `/rpg health`\n" +
                                "• `/rpg create-character Gandalf`\n" +
                                "• `/rpg roll 2d6+3`",
                        "response_type": "ephemeral"
                    }
                
                # Return response for Mattermost slash command
                result = {
                    "response_type": response.get("response_type", "ephemeral"),
                    "text": response.get("text", ""),
                }
                if "attachments" in response:
                    result["attachments"] = response.get("attachments", [])
                
                logger.info(f"Returning response: {result}")
                return result
        
        # If this is an outgoing webhook (trigger_word present), ignore it for message handling.
        # Channel behavior is handled by the channel collaboration poller to allow "human-like"
        # optional participation by multiple bots and to support non-directed messages.
        if "trigger_word" in body:
            return Response(status_code=200, content="")

        # Check if it's an outgoing webhook (has trigger_word) or a regular post event
        # Also handle regular post events that might come through webhooks
        is_outgoing_webhook = "trigger_word" in body
        is_post_event = "event" in body and body.get("event") == "posted"
        
        if is_outgoing_webhook or is_post_event or ("text" in body and "command" not in body and "trigger_word" not in body):
            # This could be an outgoing webhook from Mattermost or a post event
            logger.info(f"Received webhook/post event: trigger_word={body.get('trigger_word')}, event={body.get('event')}, channel_id={body.get('channel_id')}, text={body.get('text', body.get('data', {}).get('post', {}).get('message', ''))[:50]}")
            
            # Extract message and channel info - handle both webhook and post event formats
            if is_post_event:
                # Post event format
                post_data = body.get("data", {}).get("post", {})
                message = post_data.get("message", "").strip()
                channel_id = post_data.get("channel_id") or body.get("channel_id")
                user_id = post_data.get("user_id") or body.get("user_id")
            else:
                # Webhook format
                message = body.get("text", "").strip()
                channel_id = body.get("channel_id")
                user_id = body.get("user_id")
                # Also check for channel_id in nested data structures
                if not channel_id:
                    channel_id = body.get("data", {}).get("channel_id")
                if not channel_id:
                    channel_id = body.get("data", {}).get("post", {}).get("channel_id")
            
            # Log channel info for debugging
            logger.info(f"Webhook channel_id: {channel_id}, user_id: {user_id}, message: {message[:50]}, body keys: {list(body.keys())}")
            # Log full body for debugging (truncate long values)
            body_str = str({k: (v[:100] if isinstance(v, str) and len(v) > 100 else v) for k, v in body.items()})
            logger.info(f"Full webhook body: {body_str}")  # Changed to INFO level so we can see it
            
            trigger_word = body.get("trigger_word", "")
            
            # Determine which bot this is for based on trigger word or @mentions
            bot_username = None
            if trigger_word:
                # Remove @ symbol if present
                bot_username = trigger_word.lstrip("@").lower()
            
            # Check for @mentions in the message (for both webhooks and post events)
            if not bot_username and message:
                # Use the message router to extract mentions properly
                if bot and bot.message_router:
                    mentions = bot.message_router.extract_mentions(message)
                    for mentioned_username in mentions:
                        if bot.service_handler.is_service_bot(mentioned_username.lower()):
                            bot_username = mentioned_username.lower()
                            logger.info(f"Detected @mention of service bot: {bot_username}")
                            break
                
                # Fallback: simple word matching
                if not bot_username:
                    words = message.split()
                    for word in words:
                        word_lower = word.lower().lstrip("@")
                        if word_lower == "gaia" or word_lower.startswith("gaia"):
                            bot_username = "gaia"
                            break
                        elif word_lower == "thoth" or word_lower.startswith("thoth"):
                            bot_username = "thoth"
                            break
                        elif word_lower == "maat" or word_lower.startswith("ma'at") or word_lower.startswith("maat"):
                            bot_username = "maat"
                            break
            
            # Do NOT strip the trigger word (e.g. "@gaia") from the message.
            # We want consistent behavior across channels and full visibility of mentions
            # for downstream services.
            
            # If no bot_username from trigger_word, check for @mentions in the message
            if not bot_username and message:
                mentions = bot.message_router.extract_mentions(message) if bot.message_router else []
                for mentioned_username in mentions:
                    if bot.service_handler.is_service_bot(mentioned_username.lower()):
                        bot_username = mentioned_username.lower()
                        logger.info(f"Detected @mention of service bot in webhook: {bot_username}")
                        break
            
            if message and bot_username and bot.service_handler:
                # Mark this message as processed IMMEDIATELY to prevent race condition with polling
                # Do this BEFORE processing to ensure polling sees it as processed
                message_hash = hashlib.md5(f"{channel_id}:{message}".encode()).hexdigest()[:16]
                key = (bot_username.lower(), channel_id, message_hash)
                
                # Check if already processed (deduplicate webhooks)
                if key in _webhook_processed_messages:
                    processed_time = _webhook_processed_messages[key]
                    if time.time() - processed_time < 60:  # Within last minute
                        logger.info(f"=== WEBHOOK HANDLER: Skipping duplicate webhook (processed {int(time.time() - processed_time)}s ago) ===")
                        return {"status": "ok", "text": "Already processed"}
                
                # Mark as processing NOW (before calling service handler)
                _webhook_processed_messages[key] = time.time()
                logger.info(f"=== WEBHOOK HANDLER: Marked message as processing (hash: {message_hash}) IMMEDIATELY ===")
                
                # Also update last_post_id IMMEDIATELY if available
                post_id = body.get("post_id") or body.get("data", {}).get("post", {}).get("id")
                if post_id and bot_username:
                    if bot_username not in _last_post_ids:
                        _last_post_ids[bot_username] = {}
                    _last_post_ids[bot_username][channel_id] = post_id
                    logger.info(f"=== WEBHOOK HANDLER: Updated last_post_id to {post_id[:20]}... IMMEDIATELY ===")
                
                # Route directly to service handler for this bot
                logger.info(f"Routing webhook message to service bot: {bot_username}, channel_id: {channel_id}")
                try:
                    logger.info(f"=== WEBHOOK HANDLER: Calling service handler for {bot_username} with message: {message[:50]} ===")
                    response_text = await bot.service_handler.handle_service_message(
                        bot_username=bot_username,
                        message=message,
                        mattermost_user_id=user_id
                    )
                    logger.info(f"=== WEBHOOK HANDLER: Service handler returned response_text: {bool(response_text)}, length: {len(response_text) if response_text else 0} ===")
                    
                    if response_text:
                        logger.info(f"=== WEBHOOK HANDLER: Response text received: {response_text[:100]} ===")
                        logger.info(f"=== WEBHOOK HANDLER: channel_id before check: {channel_id} ===")
                        
                        # Post the response manually using the bot API
                        # Mattermost outgoing webhooks don't always auto-post responses
                        if not channel_id:
                            logger.error(f"Cannot post response - channel_id is missing from webhook. Full body: {body_str}")
                            # Try to get channel_id from the webhook's post data if available
                            if "post" in body:
                                channel_id = body.get("post", {}).get("channel_id")
                            if not channel_id and "data" in body:
                                channel_id = body.get("data", {}).get("channel_id") or body.get("data", {}).get("post", {}).get("channel_id")
                            if not channel_id:
                                logger.error(f"Still no channel_id after checking all locations")
                                return {"text": f"Error: Could not determine channel. Response: {response_text}"}
                            logger.info(f"Found channel_id in alternative location: {channel_id}")
                        
                        # Verify channel_id is correct - check if it's a DM or group channel
                        try:
                            if bot and bot.driver:
                                channel_info = bot.driver.channels.get_channel(channel_id)
                                channel_type = channel_info.get("type", "")
                                channel_name = channel_info.get("name", "")
                                logger.info(f"Posting to channel type: {channel_type}, name: {channel_name}, id: {channel_id}")
                        except Exception as e:
                            logger.warning(f"Could not verify channel info: {e}")
                        
                        logger.info(f"=== WEBHOOK HANDLER: Posting webhook response manually to channel {channel_id} (from webhook) ===")
                        try:
                            logger.info(f"=== WEBHOOK HANDLER: About to call bot.post_message with channel_id={channel_id}, bot_username={bot_username} ===")
                            post_success = await bot.post_message(
                                channel_id=channel_id,
                                text=response_text,
                                bot_username=bot_username
                            )
                            if post_success:
                                logger.info(f"=== WEBHOOK HANDLER: Webhook response posted successfully as {bot_username} to channel {channel_id} ===")
                                # Return early to prevent duplicate posting in the code below
                                # IMPORTANT: For outgoing webhooks, any non-empty response body can be auto-posted
                                # by Mattermost as the webhook creator (often rpg-bot). Return an empty body.
                                return Response(status_code=200, content="")
                            else:
                                logger.error(f"=== WEBHOOK HANDLER: Failed to post webhook response (post_message returned False) ===")
                                # Fallback: return response for Mattermost to post
                                return {
                                    "text": response_text,
                                    "username": bot_username
                                }
                        except Exception as e:
                            logger.error(f"=== WEBHOOK HANDLER: Error posting webhook response: {e} ===", exc_info=True)
                            # Fallback: return response for Mattermost to post
                            return {
                                "text": response_text,
                                "username": bot_username
                            }
                        # Safety: if we ever reach here after manual posting, do not return a body
                        return Response(status_code=200, content="")
                    else:
                        response = None
                except Exception as e:
                    logger.error(f"Error handling service message: {e}", exc_info=True)
                    return {
                        "text": f"Error processing message: {str(e)}",
                        "username": bot_username
                    }
            elif message:
                # Fallback to regular event handling
                event_data = {
                    "event": "posted",
                    "data": {
                        "post": {
                            "id": body.get("post_id", "webhook_post"),
                            "channel_id": channel_id,
                            "user_id": user_id,
                            "message": message
                        }
                    }
                }
                
                # Handle the event
                response = await bot.handle_post_event(event_data)
            else:
                response = None
        
        # Otherwise, treat as regular webhook event (if it has event field)
        elif "event" in body:
            event_data = {
                "event": body.get("event", "posted"),
                "data": body.get("data", body)
            }
            
            logger.info(f"Handling post event: event={event_data.get('event')}, channel_id={event_data.get('data', {}).get('post', {}).get('channel_id')}")
            # Handle the event
            response = await bot.handle_post_event(event_data)
        else:
            # Unknown webhook format - log it
            logger.warning(f"Received unknown webhook format: {list(body.keys())}")
            response = None
        
        # If response was already returned (for outgoing webhooks), don't post again
        if isinstance(response, dict) and "username" in response:
            # This is a webhook response that Mattermost will post automatically
            logger.info("Returning webhook response for Mattermost to post automatically")
            return response
        
        # Only post response here if it wasn't already posted by the webhook handler above.
        # IMPORTANT: For outgoing webhooks, return an empty body to prevent Mattermost auto-posting.
        is_outgoing_webhook = "trigger_word" in body
        if is_outgoing_webhook:
            logger.debug("Outgoing webhook handled; returning empty body to prevent auto-post")
            return Response(status_code=200, content="")
        
        if response:
            # Post response back to Mattermost (for other webhook types)
            channel_id = response.get("channel_id") or body.get("channel_id")
            response_text = response.get("text", "")
            
            if channel_id and response_text:
                logger.info(f"Posting response to channel {channel_id}: {response_text[:100]}")
                try:
                    # Use the bot token for the specific service bot if available
                    bot_username_for_posting = None
                    if "trigger_word" in body:
                        trigger_word = body.get("trigger_word", "")
                        bot_username_for_posting = trigger_word.lstrip("@").lower()
                    
                    await bot.post_message(
                        channel_id=channel_id,
                        text=response_text,
                        attachments=response.get("attachments"),
                        bot_username=bot_username_for_posting
                    )
                    logger.info("Response posted successfully")
                except Exception as e:
                    logger.error(f"Error posting response: {e}", exc_info=True)
            else:
                logger.warning(f"Cannot post response - channel_id={channel_id}, response_text={bool(response_text)}")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Error handling webhook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-character-channel")
async def create_character_channel(
    request: Request
):
    """
    Create a Mattermost channel for a character.
    
    This endpoint is called when a character is created.
    """
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Get parameters from query string or JSON body
        try:
            body = await request.json()
            being_id = body.get("being_id") or request.query_params.get("being_id")
            character_name = body.get("character_name") or request.query_params.get("character_name")
            owner_mattermost_id = body.get("owner_mattermost_id") or request.query_params.get("owner_mattermost_id")
        except:
            # Fallback to query params
            being_id = request.query_params.get("being_id")
            character_name = request.query_params.get("character_name")
            owner_mattermost_id = request.query_params.get("owner_mattermost_id", "")
        
        if not being_id:
            raise HTTPException(status_code=400, detail="being_id is required")
        
        channel_id = await bot.create_character_channel(
            being_id=being_id,
            character_name=character_name or f"Character {being_id[:8]}",
            owner_mattermost_id=owner_mattermost_id or ""
        )
        
        if channel_id:
            return {"channel_id": channel_id, "status": "created"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create channel")
            
    except Exception as e:
        logger.error(f"Error creating character channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/create-session-channel")
async def create_session_channel(
    request: Request
):
    """
    Create a Mattermost channel for a game session.
    
    This endpoint is called when a session is created.
    """
    if not bot:
        raise HTTPException(status_code=503, detail="Bot not initialized")
    
    try:
        # Get parameters from query string or JSON body
        try:
            body = await request.json()
            session_id = body.get("session_id") or request.query_params.get("session_id")
            session_name = body.get("session_name") or request.query_params.get("session_name")
            member_mattermost_ids = body.get("member_mattermost_ids", [])
        except:
            # Fallback to query params
            session_id = request.query_params.get("session_id")
            session_name = request.query_params.get("session_name")
            member_mattermost_ids = []
        
        if not session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        
        channel_id = await bot.create_session_channel(
            session_id=session_id,
            session_name=session_name or f"Session {session_id[:8]}",
            member_mattermost_ids=member_mattermost_ids
        )
        
        if channel_id:
            return {"channel_id": channel_id, "status": "created"}
        else:
            raise HTTPException(status_code=500, detail="Failed to create channel")
            
    except Exception as e:
        logger.error(f"Error creating session channel: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "bot_initialized": bot is not None
    }


# Bot Registry API endpoints
if BOT_REGISTRY_AVAILABLE:
    @app.get("/api/bots")
    async def list_bots(active_only: bool = True):
        """
        List all bots in the registry.
        
        Args:
            active_only: If True, only return active bots
        """
        try:
            registry = BotRegistry()
            bots = registry.list_bots(active_only=active_only)
            return {
                "bots": [bot.to_dict() for bot in bots],
                "count": len(bots)
            }
        except Exception as e:
            logger.error(f"Error listing bots: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/bots/{username}")
    async def get_bot(username: str):
        """Get a specific bot by username."""
        try:
            registry = BotRegistry()
            bot_info = registry.get_bot(username)
            if not bot_info:
                raise HTTPException(status_code=404, detail=f"Bot '{username}' not found")
            return bot_info.to_dict()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bot: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/bots/{username}/token")
    async def get_bot_token(username: str):
        """Get a bot's token by username (for internal use)."""
        try:
            registry = BotRegistry()
            token = registry.get_bot_token(username)
            if not token:
                raise HTTPException(status_code=404, detail=f"Bot '{username}' not found or inactive")
            return {"username": username, "token": token}
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting bot token: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/api/bots/tokens/all")
    async def get_all_bot_tokens(active_only: bool = True):
        """Get all bot tokens (for internal use)."""
        try:
            registry = BotRegistry()
            tokens = registry.get_all_tokens(active_only=active_only)
            return {"tokens": tokens, "count": len(tokens)}
        except Exception as e:
            logger.error(f"Error getting all bot tokens: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
