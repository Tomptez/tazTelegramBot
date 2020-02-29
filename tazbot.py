#Small script that gets most popular articles from taz.de and sends them in a telegram channel
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import os
import datetime

def tazArticles():
    url = "https://taz.de"

    website = requests.get(url)
    soup = BeautifulSoup(website.content, features="html.parser")

    divs = soup.find_all("div", "sect_shop")
    articles = divs[0].find_all("a")

    messageText = ""
    for a in articles:
        urll = str(a.get('href'))
        if urll != "None":
            link = url+urll

            website = requests.get(link)
            soup = BeautifulSoup(website.content, features="html.parser")

            subtitle = soup.find_all("p", "intro")
            messageText += f"{subtitle[0].text} \n{link} \n\n"
    return messageText

token = os.environ["telegramToken"]
bot = telegram.Bot(token=token)
print(bot.get_me())
print(datetime.datetime.now())

def send():
    print("Send message")
    bot.send_message("@taztopstories", tazArticles())

# schedule.every(10).minutes.do(send)
schedule.every().day.at("17:30").do(send)

while True:
    schedule.run_pending()
    time.sleep(600)
