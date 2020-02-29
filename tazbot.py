#Small script that gets most popular articles from taz.de and sends them in a telegram channel
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import os
import datetime

print(datetime.datetime.now())

token = os.environ["telegramToken"]
bot = telegram.Bot(token=token)
print(bot.get_me())

COLLECTION = {}

def scrape():
    print("Scraping...")
    global COLLECTION

    url = "https://taz.de"

    website = requests.get(url)
    soup = BeautifulSoup(website.content, features="html.parser")

    divs = soup.find_all("div", "sect_shop")
    articles = divs[0].find_all("a")

    for a in articles:
        try:
            messageText = ""
            urll = str(a.get('href'))
            
            if urll != "None":
                title = a.h4.text
                link = url+urll

                website = requests.get(link)
                soup = BeautifulSoup(website.content, features="html.parser")

                subtitle = soup.find_all("p", "intro")
                messageText += f"**{title}**\n{subtitle[0].text} \n{link}\n"
                if title not in articles:
                    COLLECTION[title] = messageText
        except Exception as e:
            print()
            print(f"ERROR: {e}")

def send():
    print("Sending...")

    global COLLECTION
    count = 1
    message = ""

    for article, text in reversed(COLLECTION.items()):

        message += text

        # Makes sure it sends at most 8 messages
        if count >= 8:
            break
        else:
            count += 1

    bot.send_message("@taztopstories", message)
    COLLECTION = {}

schedule.every(1).hour.do(scrape)
schedule.every().day.at("17:40").do(send)

scrape()
while True:
    schedule.run_pending()
    time.sleep(600)
