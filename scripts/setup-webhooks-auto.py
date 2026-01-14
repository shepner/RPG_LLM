#!/usr/bin/env python3
"""
Create Mattermost outgoing webhooks for service bots (@gaia, @thoth, @maat).

Env:
  - MATTERMOST_URL (default: http://localhost:8065)
  - MATTERMOST_BOT_TOKEN (required; should have permissions to manage webhooks)
  - MATTERMOST_WEBHOOK_URL (default: http://mattermost_bot:8008/webhook)
"""

import os
import sys

import httpx


def die(msg: str) -> None:
    print(f"❌ {msg}", file=sys.stderr)
    raise SystemExit(1)


def main() -> None:
    mm_url = os.getenv("MATTERMOST_URL", "http://localhost:8065").rstrip("/")
    token = os.getenv("MATTERMOST_BOT_TOKEN")
    callback = os.getenv("MATTERMOST_WEBHOOK_URL", "http://mattermost_bot:8008/webhook")

    if not token:
        die("MATTERMOST_BOT_TOKEN is required")

    api = f"{mm_url}/api/v4"
    headers = {"Authorization": f"Bearer {token}"}

    triggers = [
        ("gaia", "@gaia", "Gaia Bot Webhook"),
        ("thoth", "@thoth", "Thoth Bot Webhook"),
        ("maat", "@maat", "Ma'at Bot Webhook"),
    ]

    with httpx.Client(timeout=15.0, verify=False) as client:
        me = client.get(f"{api}/users/me", headers=headers)
        if me.status_code != 200:
            die(f"Auth failed: {me.status_code} {me.text[:200]}")

        teams = client.get(f"{api}/teams", headers=headers)
        if teams.status_code != 200:
            die(f"Failed to list teams: {teams.status_code} {teams.text[:200]}")

        team_id = None
        for t in teams.json():
            if isinstance(t, dict) and t.get("delete_at", 1) == 0:
                team_id = t.get("id")
                break
        if not team_id:
            die("Could not determine an active team_id")

        hooks = client.get(
            f"{api}/hooks/outgoing",
            headers=headers,
            params={"team_id": team_id, "page": 0, "per_page": 200},
        )
        if hooks.status_code != 200:
            die(f"Failed to list outgoing hooks: {hooks.status_code} {hooks.text[:200]}")

        existing = hooks.json()

        def exists(trigger_word: str) -> str | None:
            for h in existing:
                if trigger_word in (h.get("trigger_words") or []):
                    return h.get("id")
            return None

        ok = 0
        for _username, trigger, display_name in triggers:
            ex_id = exists(trigger)
            if ex_id:
                print(f"⚠️  Webhook for {trigger} already exists (ID: {ex_id})")
                ok += 1
                continue

            payload = {
                "team_id": team_id,
                "display_name": display_name,
                "description": f"Webhook for {_username} bot interactions",
                "trigger_words": [trigger],
                "trigger_when": 1,
                "callback_urls": [callback],
                "content_type": "application/json",
            }
            created = client.post(f"{api}/hooks/outgoing", headers=headers, json=payload)
            if created.status_code not in (200, 201):
                die(f"Failed to create webhook for {trigger}: {created.status_code} {created.text[:200]}")

            hook_id = created.json().get("id")
            print(f"✅ Created webhook for {trigger} (ID: {hook_id})")
            ok += 1

        if ok != len(triggers):
            die(f"Configured {ok}/{len(triggers)} webhooks")

        print("✅ All webhooks configured successfully")


if __name__ == "__main__":
    main()

