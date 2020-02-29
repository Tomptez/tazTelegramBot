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
myusername = os.environ["myTelegramChatID"]
bot = telegram.Bot(token=token)
COLLECTION = {}
OLDCOLLECTION = {}

def messageAdmin(message):
    try:
        bot.send_message(myusername, message)
    except:
        pass

def scrape():
    print("Scraping...")
    global COLLECTION

    urlTaz = "https://taz.de"

    website = requests.get(urlTaz)
    soup = BeautifulSoup(website.content, features="html.parser")

    divs = soup.find_all("div", "sect_shop")
    articles = divs[0].find_all("a")

    for a in articles:
        try:
            messageText = ""
            urlArticle = str(a.get('href'))
            
            if urlArticle != "None":
                title = a.h4.text
                link = urlTaz+urlArticle

                website = requests.get(link)
                soup = BeautifulSoup(website.content, features="html.parser")

                subtitle = soup.find_all("p", "intro")
                messageText += f"*{title}*\n{subtitle[0].text} \n{link}\n\n"
                if title not in COLLECTION and title not in OLDCOLLECTION:
                    COLLECTION[title] = messageText
        except Exception as e:
            print()
            print(f"ERROR: {e}")

            message = f"Error. Couldn't scrape taz.de\n\n{e}"
            messageAdmin(message)
    
    print("Current size of Article Collection: ", len(COLLECTION))
    print("Artikel: ",list(COLLECTION.keys()))

    if len(COLLECTION) == 0:
        message = f"Problem with scraping of taz.de. Couldn't retrieve any articles from 'meistgelesen'"
        messageAdmin(message)

def send():
    print("Sending...")

    global COLLECTION
    global OLDCOLLECTION
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
        bot.send_message("@taztopstories", message, parse_mode=telegram.ParseMode.MARKDOWN)
    except Exception as e:
        messageAdmin(e)
    OLDCOLLECTION = COLLECTION
    COLLECTION = {}

print("Current Date and Time: ", datetime.datetime.now())
print("Telegram Bot Infos: ", bot.get_me())
bot.send_message(myusername, f"Started tazBot")

schedule.every().day.at("00:10").do(scrape)
schedule.every().day.at("10:30").do(scrape)
schedule.every().day.at("12:45").do(scrape)
schedule.every().day.at("15:15").do(scrape)
schedule.every().day.at("17:25").do(scrape)
schedule.every().day.at("17:30").do(send)

scrape()
while True:
    schedule.run_pending()
    time.sleep(1200)
