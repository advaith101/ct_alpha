from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
import os
import re
import requests
import psycopg2
import tweet_extractoor
import web3
import json
import datetime

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

TOTO_API_KEY = os.getenv("TOTO_API_KEY")

#postgres db info
DB_HOST = os.getenv("DB_HOST")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_NAME = os.getenv("DB_NAME")
DB_PORT = os.getenv("DB_PORT")
DB_URI = os.getenv("DB_URI")

# #connect to web3
# w3 = web3.Web3(web3.Web3.HTTPProvider(f"https://mainnet.infura.io/v3/{os.getenv('INFURA_API_KEY')}"))

#load uniswap abis
with open("abis/uniswapV2pair.json") as f:
    uniswapV2pair_abi = json.load(f)
with open("abis/uniswapV2factory.json") as f:
    uniswapV2factory_abi = json.load(f)
with open("abis/uniswapV2router.json") as f:
    uniswapV2router_abi = json.load(f)
with open("abis/uniswapV3factory.json") as f:
    uniswapV3factory_abi = json.load(f)
with open("abis/uniswapV3pool.json") as f:
    uniswapV3pool_abi = json.load(f)
with open("abis/uniswapV3router.json") as f:
    uniswapV3router_abi = json.load(f)

#load contracts
def load_contracts(pair_address: str, chain_id: str = 'ethereum'):
    contracts = {}
    w3 = None
    if chain_id == 'ethereum':
        w3 = web3.Web3(web3.Web3.HTTPProvider(os.getenv('ALCHEMY_MAINNET_URI')))
        contracts['uniswapV2factory'] = w3.eth.contract(address="0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f", abi=uniswapV2factory_abi)
        contracts['uniswapV2pair'] = w3.eth.contract(address=pair_address, abi=uniswapV2pair_abi)
        contracts['uniswapV3factory'] = w3.eth.contract(address="0x1F98431c8aD98523631AE4a59f267346ea31F984", abi=uniswapV3factory_abi)
        contracts['uniswapV3pool'] = w3.eth.contract(address=pair_address, abi=uniswapV3pool_abi)
    elif chain_id == 'base':
        w3 = web3.Web3(web3.Web3.HTTPProvider(os.getenv('ALCHEMY_BASE_URI')))
        contracts['uniswapV2factory'] = w3.eth.contract(address="0x8909Dc15e40173Ff4699343b6eB8132c65e18eC6", abi=uniswapV2factory_abi)
        contracts['uniswapV2pair'] = w3.eth.contract(address=pair_address, abi=uniswapV2pair_abi)
        contracts['uniswapV3factory'] = w3.eth.contract(address="0x33128a8fC17869897dcE68Ed026d694621f6FDfD", abi=uniswapV3factory_abi)
        contracts['uniswapV3pool'] = w3.eth.contract(address=pair_address, abi=uniswapV3pool_abi)
    return {'w3': w3, 'contracts': contracts}

#connect to postgres db
conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    port=DB_PORT
)

# conn = psycopg2.connect(DB_URI, sslmode='require')


def setup_db():
    #create table
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS calls
                (ID SERIAL PRIMARY KEY NOT NULL,
                call_ticker VARCHAR(8) NOT NULL,
                tweet_userid BIGINT NOT NULL,
                tweet_id BIGINT NOT NULL,
                price_at_call FLOAT,
                daily_return FLOAT,
                weekly_return FLOAT,
                monthly_return FLOAT,
                yearly_return FLOAT,
                current_return FLOAT,
                dex_id VARCHAR(32) NOT NULL,
                chain_id VARCHAR(32) NOT NULL,
                call_timestamp INT NOT NULL,
                last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
    # cur.execute('''CREATE TABLE IF NOT EXISTS tweets
    #             (ID SERIAL PRIMARY KEY NOT NULL,
    #             tweet_statusid BIGINT UNIQUE NOT NULL,
    #             tweet TEXT NOT NULL,
    #             tweet_time INT NOT NULL,
    #             tweet_userid BIGINT NOT NULL,
    #             tweet_link VARCHAR(100),
    #             tweet_likes INT,
    #             tweet_retweets INT,
    #             tweet_quotes INT,
    #             tweet_replies INT);''')
    # cur.execute('''CREATE TABLE IF NOT EXISTS ct_accounts
    #             (ID SERIAL PRIMARY KEY NOT NULL,
    #             twitter_userid BIGINT NOT NULL,
    #             twitter_username TEXT NOT NULL,
    #             alpha_score FLOAT,
    #             last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
    # cur.execute('''CREATE TABLE IF NOT EXISTS tickers
    #             (ID SERIAL PRIMARY KEY NOT NULL,
    #             ticker VARCHAR(8) NOT NULL,
    #             contract_address VARCHAR(44) NOT NULL,
    #             project_name VARCHAR(32),
    #             project_website VARCHAR(64),
    #             project_twitter VARCHAR(15));''')
    conn.commit()
    cur.close()
    print("Tables created successfully")


#function to execute db write operation
def db_write(queries):
    cur = conn.cursor()
    for query in queries:
        cur.execute(query)
    conn.commit()
    cur.close()

#function to execute db read operation
def db_read(query):
    cur = conn.cursor()
    cur.execute(query)
    result = cur.fetchall()
    cur.close()
    return result

#function to get call tickers from tweet
def get_call_tickers(tweet, influencer):
    convo = []
    system_cmd = "You are a crypto social analyst for the top crypto research firm. "
    system_cmd += "You are tasked with analyzing sentiment on twitter, namely tweets from crypto influencers."
    # system_cmd += "You are tasked with extracting the ticker main crypto project that a crypto influencer is promoting in a given tweet, based on the following criteria:\n\n"
    # system_cmd += "1. The ticker has 1 to 8 characters, preceeded by a '$'.\n"
    # system_cmd += "2. The tweet should clearly indicate that the influencer has bought the ticker.\n"
    # system_cmd += "3. The ticker must be already launched - no presales, upcoming launches, etc.\n"
    # system_cmd += "4. The ticker cannot be a mainstream crypto like BTC, ETH, SOL etc.\n\n"
    # system_cmd += "If the tweet doesn't contain any tickers that match the criteria, respond 'n/a'. "
    # system_cmd += "Otherwise, respond with only the ticker"

    user_cmd = f"What crypto project(s) is the influencer '@{influencer}' is supporting in the following tweet?\n\n"
    user_cmd += f"{tweet}\n\n"
    user_cmd += "There should be a clear indication that the influencer has bought the project or is promoting it positively. "
    user_cmd += "Respond with a JSON array, where each object has the fields 'ticker', 'contract_address' for each project that fits the criteria. " 
    user_cmd += "The tweet should mention either the ticker or contract address for a project, or both. "
    user_cmd += "If the tweet doesn't mention the contract address for a project, that field should be null. "
    user_cmd += "If the tweet doesn't mention the ticker for a project, that field should be null. "
    user_cmd += "If the tweet doesn't contain any projects that match the criteria, respond with an empty array."

    convo.append({"role": "system", "content": system_cmd})
    convo.append({"role": "user", "content": user_cmd})
    completion = client.chat.completions.create(
        model='gpt-4o',
        messages=convo
    )
    tickers = completion.choices[0].message.content
    #parse into json
    tickers = json.loads(tickers)
    tickers.map(lambda x: x["ticker"].replace('$', '').upper())
    print("\nTickers: ", tickers)
    return tickers


#function go get price of uniswap v2 pair at a time
def get_price_at_time(univ2pair, univ3pool, token_address, timestamp, chain_id):
    #get blcok number at time
    if chain_id == 'ethereum':
        request_url = f"https://api.etherscan.io/api?module=block&action=getblocknobytime&timestamp={timestamp}&closest=before&apikey={os.getenv('ETHERSCAN_API_KEY')}"
    elif chain_id == 'base':
        request_url = f"https://api.basescan.org/api?module=block&action=getblocknobytime&timestamp={timestamp}&closest=before&apikey={os.getenv('BASESCAN_API_KEY')}"
    else:
        print("Chain not supported")
        return None, None
    response = requests.get(request_url)
    block_number = int(response.json()["result"])

    #check if pair is uniswap v2 or v3
    price = None
    dex_id = None
    try:
        #get price at block number
        reserves = univ2pair.functions.getReserves().call(block_identifier=block_number)
        if univ2pair.functions.token0().call() == token_address:
            price = int(reserves[1]) / int(reserves[0])
        else:
            price = int(reserves[0]) / int(reserves[1])
        dex_id = "uniswapV2"
    except Exception as e:
        print(repr(e))
        print("Not a uniswap v2 pair")
        try:
            #get price at block number
            reserves = univ3pool.functions.slot0().call(block_identifier=block_number)
            sqrtPriceX96 = int(reserves[0])
            price = (sqrtPriceX96 ** 2) / (2**96)
            dex_id = "uniswapV3"
        except Exception as e:
            print(repr(e))
            print("Not a uniswap v3 pool")

    return price, dex_id

#function to get ticker stats
def get_ticker_stats(ticker, tweet, ca=None):
    try:
        print("\nGetting stats for ticker: ", ticker)
        url = f"https://api.dexscreener.com/latest/dex/search/?q={ticker if ca == None else ca}"
        response = requests.get(url)
        data = response.json()
        pairs = data["pairs"]
        if len(pairs) == 0:
            print("No pairs found on dexscreener")
            return None
        top_likelihood_pair = None
        for pair in pairs:
            if pair["baseToken"]["symbol"].upper() == ticker:
                top_likelihood_pair = pair
                break
        if top_likelihood_pair == None:
            print("No matching ticker found on dexscreener")
            return None
        dex_id = top_likelihood_pair["dexId"]
        chain_id = top_likelihood_pair["chainId"]
        token_address = top_likelihood_pair["baseToken"]["address"]
        if chain_id not in ['ethereum', 'base']:
            print("Chain not supported")
            return None
        
        contracts = load_contracts(top_likelihood_pair["pairAddress"], chain_id)['contracts']
        uniswapV2pair = contracts['uniswapV2pair']
        uniswapV3pool = contracts['uniswapV3pool']

        #parse datetime string in ISO 8601/RFC 3339 format and convert it to time in seconds since epoch
        call_time = int(tweet["timestamp"])
        print("CALL TIME")
        print(call_time)
        # pair_creation_time = int(top_likelihood_pair["pairCreatedAt"])
        # print("PAIR CREATION TIME")
        # print(pair_creation_time)

        #get price at call
        current_time = int(datetime.datetime.now().timestamp())
        price_at_call, dex_id = get_price_at_time(uniswapV2pair, uniswapV3pool, token_address, call_time, chain_id)
        if (price_at_call == None):
            print("Unable to get pricing info")
            return None
        print("PRICE AT CALL")
        print(price_at_call)

        #get performance
        one_day_performance = None
        one_week_performance = None
        one_month_performance = None
        one_year_performance = None
        current_performance = get_price_at_time(uniswapV2pair, uniswapV3pool, token_address, current_time, chain_id)[0] / price_at_call - 1
        if call_time + 86400 <= current_time:
            one_day_performance = get_price_at_time(uniswapV2pair, uniswapV3pool, token_address, call_time + 86400, chain_id)[0] / price_at_call - 1
        if call_time + 604800 <= current_time:
            one_week_performance = get_price_at_time(uniswapV2pair, uniswapV3pool, token_address, call_time + 604800, chain_id)[0] / price_at_call - 1
        if call_time + 2592000 <= current_time:
            one_month_performance = get_price_at_time(uniswapV2pair, uniswapV3pool, token_address, call_time + 2592000, chain_id)[0] / price_at_call - 1
        if call_time + 31536000 <= current_time:
            one_year_performance = get_price_at_time(uniswapV2pair, uniswapV3pool, token_address, call_time + 31536000, chain_id)[0] / price_at_call - 1

        #trim to 5 decimal places
        return {
            "price_at_call": round(price_at_call, 5),
            "daily_return": round(one_day_performance, 5) if one_day_performance != None else None,
            "weekly_return": round(one_week_performance, 5) if one_week_performance != None else None,
            "monthly_return": round(one_month_performance, 5) if one_month_performance != None else None,
            "yearly_return": round(one_year_performance, 5) if one_year_performance != None else None,
            "current_return": round(current_performance, 5) if current_performance != None else None,
            "dex_id": dex_id,
            "chain_id": chain_id
        }
    except Exception as e:
        print(repr(e))
        return None



def manual_write():
    #drop all tables
    query = '''DROP TABLE IF EXISTS calls;'''
    cur = conn.cursor()
    cur.execute(query)
    conn.commit()
    cur.close()
    print("Operation successful")


#upload tweets to database
def upload_tweets(username: str, start_time: datetime.datetime = None, end_time: datetime.datetime = None):
    tweets, user_id = tweet_extractoor.get_tweets(username, start_time, end_time)
    #insert into ct_accounts
    queries = [f'''INSERT INTO ct_accounts
                (twitter_userid, twitter_username)
                VALUES
                ({user_id}, '{username}');''']
    for tweet in tweets:
        tweet_text = tweet["tweet"]
        #remove leading and trailing whitespace
        tweet_text = tweet_text.strip()
        #if tweet is empty, skip
        if tweet_text == "" or tweet_text == " ":
            continue
        #make sure tweet contains a ticker
        tickers = re.findall(r'[$][A-Za-z][\S]*', tweet_text)
        if len(tickers) == 0:
            continue
        #replace &amp; with &
        tweet_text = tweet_text.replace("&amp;", "&")
        #replace &gt; with >
        tweet_text = tweet_text.replace("&gt;", ">")
        #replace &lt; with <
        tweet_text = tweet_text.replace("&lt;", "<")
        #replace ' with ''
        tweet_text = tweet_text.replace("'", "''")
        print(tweet_text)
        queries.append(f'''INSERT INTO tweets 
                 (tweet_statusid, tweet, tweet_time, tweet_userid, tweet_link, tweet_likes, tweet_retweets, tweet_quotes, tweet_replies) 
                 VALUES 
                 ({tweet['tweet_id']},'{tweet_text}', {int(tweet['timestamp'].timestamp())}, 
                 {tweet['user_id']}, '{tweet['link']}', {tweet['public_metrics']['like_count']}, 
                 {tweet['public_metrics']['retweet_count']}, {tweet['public_metrics']['quote_count']}, 
                 {tweet['public_metrics']['reply_count']});''')
    # print(queries)
    input("Press Enter to continue...")
    db_write(queries)
    print("Operation successful")
    return user_id

#iterate through tweet files in /chosen_tweets, get embedding, and add to pinecone index
calls = []
already_called_tickers = {}
def extract_calls(twitter_username: str):
    twitter_userid = tweet_extractoor.get_user_id(twitter_username)
    #get tweets from db ordered oldest to newest
    tweets = db_read(f'''SELECT * FROM tweets WHERE tweet_userid = {twitter_userid} ORDER BY tweet_time ASC;''')
    for tweet in tweets:
        tweet_formatted = {
            "tweet_id": tweet[1],
            "tweet": tweet[2],
            "timestamp": tweet[3],
            "user_id": tweet[4],
            "link": tweet[5],
            "likes": tweet[6],
            "retweets": tweet[7],
            "quotes": tweet[8],
            "replies": tweet[9]
        }
        tweet_text = tweet_formatted['tweet']
        print('\n')
        print(tweet_text)
        
        #get call tickers
        tickers = get_call_tickers(tweet_text, twitter_username)
        for ticker in tickers:
            ca = ticker["contract_address"]
            ticker = ticker["ticker"]

            # for ticker in call_tickers.replace(' ', '').replace('$', '').upper().split(","):
            if already_called_tickers.get(ticker, False):
                continue
            already_called_tickers[ticker] = True
            stats = get_ticker_stats(ticker, tweet_formatted, ca)
            if stats == None:
                print("Ticker not found or pricing info unavailable")
                continue
            print(stats)
            # input("Press Enter to continue...")

            # db_write([f'''INSERT INTO calls
            #             (call_ticker, tweet_userid, tweet_id, price_at_call, daily_return, weekly_return, monthly_return, yearly_return, current_return, dex_id, chain_id, call_timestamp)
            #             VALUES
            #             ('{ticker}', {tweet_formatted['user_id']}, {tweet_formatted['tweet_id']}, 
            #             {stats['price_at_call'] if stats['price_at_call'] != None else 'NULL'}, 
            #             {stats['daily_return'] if stats['daily_return'] != None else 'NULL'}, 
            #             {stats['weekly_return'] if stats['weekly_return'] != None else 'NULL'}, 
            #             {stats['monthly_return'] if stats['monthly_return'] != None else 'NULL'}, 
            #             {stats['yearly_return'] if stats['yearly_return'] != None else 'NULL'},
            #             {stats['current_return'] if stats['current_return'] != None else 'NULL'},
            #             '{stats['dex_id']}', '{stats['chain_id']}', {tweet_formatted["timestamp"]});'''])
            # print("Call successfully inserted")
        input("Press Enter to continue...")


# get calls and average performance for ct account
def get_ct_performance(username: str):
    twitter_userid = tweet_extractoor.get_user_id(username)
    calls = db_read(f'''SELECT * FROM calls WHERE tweet_userid = {twitter_userid};''')
    total_daily_return_calls = 0
    total_daily_return = 0
    total_weekly_return_calls = 0
    total_weekly_return = 0
    total_monthly_return_calls = 0
    total_monthly_return = 0
    total_yearly_return_calls = 0
    total_yearly_return = 0
    total_current_return_calls = 0
    total_current_return = 0
    calls_formatted = []
    for call in calls:
        total_daily_return_calls += 1 if call[5] != None else 0
        total_daily_return += call[5] if call[5] != None else 0
        total_weekly_return_calls += 1 if call[6] != None else 0
        total_weekly_return += call[6] if call[6] != None else 0
        total_monthly_return_calls += 1 if call[7] != None else 0
        total_monthly_return += call[7] if call[7] != None else 0
        total_yearly_return_calls += 1 if call[8] != None else 0
        total_yearly_return += call[8] if call[8] != None else 0
        total_current_return_calls += 1 if call[9] != None else 0
        total_current_return += call[9] if call[9] != None else 0
        calls_formatted.append({
            "call_ticker": call[1],
            "tweet_id": call[3],
            "price_at_call": call[4],
            "daily_return": call[5],
            "weekly_return": call[6],
            "monthly_return": call[7],
            "yearly_return": call[8],
            "current_return": call[9],
            "dex_id": call[10],
            "chain_id": call[11],
            "call_timestamp": call[12]
        })
    average_performance = {
        "daily_return": total_daily_return / total_daily_return_calls if total_daily_return_calls != 0 else None,
        "weekly_return": total_weekly_return / total_weekly_return_calls if total_weekly_return_calls != 0 else None,
        "monthly_return": total_monthly_return / total_monthly_return_calls if total_monthly_return_calls != 0 else None,
        "yearly_return": total_yearly_return / total_yearly_return_calls if total_yearly_return_calls != 0 else None,
        "current_return": total_current_return / total_current_return_calls if total_current_return_calls != 0 else None
    }
    return {
        "twitter_username": username,
        "calls": calls_formatted,
        "average_performance": average_performance
    }

if __name__ == "__main__":
    # manual_write()
    # setup_db()
    # extract_calls("chirocrypto")
    upload_tweets("gandalfcryptto")
    # extract_calls(1173075303742132225)
    # user_id = upload_tweets("0xSenzu")
    # user_id = tweet_extractoor.get_user_id("0xSenzu")
    # user_id = upload_tweets("UniswapVillain")
    # extract_calls(user_id)

    # extract_calls("ztrader369")

    # use sys args to get username
    # import sys
    # username = sys.argv[1]
    # performance = get_ct_performance("0xSenzu")
    # #format json pretty
    # print(json.dumps(performance, indent=4))
