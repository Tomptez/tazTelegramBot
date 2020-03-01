#Small telegram bot that gets most popular articles from taz.de and sends them in a telegram channel
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import os
import datetime
from dotenv import load_dotenv
load_dotenv()

token = os.environ["telegramToken"]
adminUsername = os.environ["adminTelegramChatID"]
channelName = os.environ["publicChannelName"]
bot = telegram.Bot(token=token)
COLLECTION = {}
COLLECTION_YESTERDAY = {}

def messageAdmin(message):
    try:
        bot.send_message(adminUsername, message)
    except:
        pass

def scrape():
    print("Scraping...")
    global COLLECTION

    urlTaz = "https://taz.de"

    website = requests.get(urlTaz)
    soup = BeautifulSoup(website.content, features="html.parser")

    meistgelesenDiv = soup.find("div", "sect_shop")
    meistgelesenUl = meistgelesenDiv.find("ul")
    articles = meistgelesenUl.find_all("a")

    for a in articles:
        try:
            title = a.h4.text
            # Skip article if it's already in the collection
            if title in COLLECTION or title in COLLECTION_YESTERDAY:
                continue

            urlArticle = str(a.get('href'))
            link = urlTaz+urlArticle
            website = requests.get(link)
            soup = BeautifulSoup(website.content, features="html.parser")

            subtitle = soup.find_all("p", "intro")
            messageText = f"*{title}*\n{subtitle[0].text} \n{link}\n\n"
            COLLECTION[title] = messageText

        except Exception as e:
            print()
            print(f"ERROR: {e}")

            message = f"Error. Couldn't scrape taz.de\n\n{e}"
            messageAdmin(message)
    
    print(f"Current size of Article Collection: {len(COLLECTION)}, Yesterday: {len(COLLECTION_YESTERDAY)}")
    print("Today's articles: ",list(COLLECTION.keys()))

    if len(COLLECTION) == 0:
        message = f"Problem with scraping of taz.de. Couldn't retrieve any articles from 'meistgelesen'. COLLECTION == 0"
        messageAdmin(message)

def send():
    print("Sending...")

    global COLLECTION
    global COLLECTION_YESTERDAY
    count = 1
    message = ""

    for article, text in reversed(COLLECTION.items()):

        message += text

        # Makes sure it sends at most 8 messages
        if count >= 8:
            break
        else:
            count += 1

    try:
        bot.send_message(channelName, message, parse_mode=telegram.ParseMode.MARKDOWN)
    except Exception as e:
        messageAdmin(e)
    COLLECTION_YESTERDAY = COLLECTION
    COLLECTION = {}

print("Current Date and Time: ", datetime.datetime.now())
print("Telegram Bot Infos: ", bot.get_me())
messageAdmin(f"Started tazBot {datetime.datetime.now()}")

schedule.every().day.at("00:10").do(scrape)
schedule.every().day.at("10:30").do(scrape)
schedule.every().day.at("12:45").do(scrape)
schedule.every().day.at("15:15").do(scrape)
schedule.every().day.at("17:30").do(scrape)
schedule.every().day.at("17:35").do(send)

scrape()
send()
while True:
    schedule.run_pending()
    time.sleep(600)
