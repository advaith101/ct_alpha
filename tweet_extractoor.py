import datetime
import tweepy
from dotenv import load_dotenv
load_dotenv(override=True)
import os

# Sign up for the Twitter API and generate a Bearer Token here:
# https://developer.twitter.com/en/docs/twitter-api

TWITTER_BEARER_TOKEN = os.getenv("TWITTER_BEARER_TOKEN")

def get_user_id(username: str):
    client = tweepy.Client(TWITTER_BEARER_TOKEN)
    user_id = client.get_user(username=username).data.id
    return user_id


def get_tweets(username: str, start_time: datetime.datetime = None, end_time: datetime.datetime = None):
    """
    Pulls last 50 most recent tweets for specified username and saves to tweets_<username>.csv
    """

    client = tweepy.Client(TWITTER_BEARER_TOKEN)
    user_id = client.get_user(username=username).data.id
    responses = tweepy.Paginator(client.get_users_tweets, user_id, max_results=100, exclude=["retweets", "replies"], tweet_fields=["created_at", "public_metrics"], start_time=start_time, end_time=end_time)

    tweets_list = []
    #iterate through tweets and append to list
    counter=0
    for tweets in responses:
        counter += 1
        if counter == 3:
            break
        print(f"==> processing {counter * 100} to {(counter + 1) * 100} of {username}'s tweets")
        for tweet in tweets.data:
            try:
                tweets_list.append({
                    "link": f"https://twitter.com/{username}/status/{tweet.id}",
                    "username": username,
                    "user_id": user_id,
                    "tweet": tweet.text,
                    "tweet_id": tweet.id,
                    "timestamp": tweet.created_at,
                    "public_metrics": tweet.public_metrics
                })
            except Exception as e:
                print(repr(e))
        # print(tweets_list)
    print("Done!")

    return tweets_list, user_id


if __name__ == "__main__":
    # os.chdir(os.path.dirname(os.path.abspath(__file__)))
    get_tweets("ztrader369")