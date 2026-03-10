"""Twitter/X posting logic."""

import tweepy

from lib.config import SNAPSHOT_PATH, load_twitter_keys
from lib.camera import take_alert_snapshot


def post_tweet(text, mode):
    """Take a snapshot and post a tweet with the image."""
    try:
        take_alert_snapshot(mode)

        keys = load_twitter_keys()
        if not keys:
            print("No Twitter keys, skipping tweet", flush=True)
            return

        auth = tweepy.OAuth1UserHandler(
            keys["API_KEY"], keys["API_SECRET"],
            keys["ACCESS_TOKEN"], keys["ACCESS_SECRET"]
        )
        api = tweepy.API(auth)
        media = api.media_upload(SNAPSHOT_PATH)

        client = tweepy.Client(
            consumer_key=keys["API_KEY"], consumer_secret=keys["API_SECRET"],
            access_token=keys["ACCESS_TOKEN"], access_token_secret=keys["ACCESS_SECRET"]
        )
        client.create_tweet(text=text, media_ids=[media.media_id])
        print("Tweet posted: " + text, flush=True)

    except Exception as e:
        print("Tweet failed: " + str(e), flush=True)
