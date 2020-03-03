#Small telegram bot that gets most popular articles from taz.de and sends them in a telegram channel
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import os
import datetime
from dotenv import load_dotenv
import traceback
load_dotenv()

token = os.environ["telegramToken"]
adminUsername = os.environ["adminTelegramChatID"]
channelName = os.environ["publicChannelName"]
bot = telegram.Bot(token=token)
COLLECTION = {}
OLDARTICLES = []
ARTICLESET = set()

def messageAdmin(message):
    try:
        bot.send_message(adminUsername, message)
    except Exception:
        print(f"Error. Could not send Error message to admin.")

def scrape():
    print("Scraping...")
    global COLLECTION

    urlTaz = "https://taz.de"

    try:
        website = requests.get(urlTaz)
        soup = BeautifulSoup(website.content, features="html.parser")
        meistgelesenDiv = soup.find("div", "sect_shop")
        meistgelesenUl = meistgelesenDiv.find("ul")
        articles = meistgelesenUl.find_all("a")
    except Exception:
        articles = []
        print("ERROR encountered. Maybe taz.de is down?")
        messageAdmin("ERROR encountered. Maybe taz.de is down?")

    for a in articles:
        try:
            title = a.h4.text
            # Skip article if it was in yesterday's articles
            if title in ARTICLESET:
                continue
            
            # Make sure the currently most read articles are the last ones in the collection
            elif title in COLLECTION:
                COLLECTION[title] = COLLECTION.pop(title)
                continue
            
            else:
                urlArticle = str(a.get('href'))
                link = urlTaz+urlArticle
                website = requests.get(link)
                soup = BeautifulSoup(website.content, features="html.parser")

                subtitle = soup.find_all("p", "intro")
                messageText = f"*{title}*\n{subtitle[0].text} \n{link}\n\n"
                COLLECTION[title] = {"text":messageText}

        except Exception:
            e = traceback.format_exc()
            print()
            print(f"ERROR: {e}")

            message = f"Error. Couldn't scrape taz.de\n\n{e}"
            messageAdmin(message)
    
    print(f"Number of articles for today: {len(COLLECTION)}, Old saved ones: {len(OLDARTICLES)}")
    print("Today's articles: ",list(COLLECTION.keys()))

    if len(COLLECTION) == 0 or len(articles) == 0:
        message = f"Possible problem with scraping of taz.de. COLLECTION = {COLLECTION}"
        messageAdmin(message)

def send(attempt=0):
    print("Sending...")

    global COLLECTION
    global OLDARTICLES
    global ARTICLESET
    count = 1
    message = ""

    if len(COLLECTION) == 0:
        print("Empty COLLECTION. Could not send anything.")
        print(f"Number of articles for today: {len(COLLECTION)}, Old saved ones: {len(OLDARTICLES)}")
        return False

    sendedArticles = []
    for article, list in reversed(COLLECTION.items()):

        message += list["text"]
        sendedArticles.append(article)

        # Makes sure it sends at most 8 messages
        if count >= 8:
            break
        else:
            count += 1

    try:
        if message == "":
            raise Exception("Empty message")
        bot.send_message(channelName, message, parse_mode=telegram.ParseMode.MARKDOWN)

        OLDARTICLES += sendedArticles
        OLDARTICLES = OLDARTICLES[-300:]
        ARTICLESET = set(OLDARTICLES)
        COLLECTION = {}
        with open('file.txt', 'w') as f:
            for listitem in OLDARTICLES:
                f.write(f'{listitem}\n')

        print("Saved Article-titles: ", OLDARTICLES)
        print("Successfully sent!")
    except Exception:
        e = traceback.format_exc()
        print(e)
        if attempt <= 1:
            messageAdmin(f"Couln't send articles. Will try to send again in 10 minutes...\n\n{e}")
        if attempt <= 30:
            print("Will try to send again in 10 minutes...")
            time.sleep(600)
            send(attempt+1)
    finally:
        print(f"Number of articles for today: {len(COLLECTION)}, Old saved ones: {len(OLDARTICLES)}")

if __name__ == "__main__":
    print("Telegram Bot Infos: ", bot.get_me())

    schedule.every().day.at("00:10").do(scrape)
    schedule.every().day.at("10:30").do(scrape)
    schedule.every().day.at("13:45").do(scrape)
    schedule.every().day.at("15:45").do(scrape)
    schedule.every().day.at("17:30").do(scrape)
    schedule.every().day.at("17:35").do(send)

    try:
        with open('file.txt', 'r') as f:
            for line in f:
                # remove linebreak which is the last character of the string
                currentPlace = line[:-1]

                # add item to the list
                OLDARTICLES.append(currentPlace)
        ARTICLESET = set(OLDARTICLES)
    except:
        print("Couldn't load old Article titles. There is no such file as file.txt")

    scrape()
    while True:
        try:
            schedule.run_pending()
            time.sleep(600)
        except Exception as e:
            print(e)