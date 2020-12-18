#Small telegram bot that gets most popular articles from taz.de and sends them in a telegram channel
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import os
import math
import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import traceback
import feedparser
from collections import Counter

load_dotenv()

token = os.environ["telegramToken"]
adminUsername = os.environ["adminTelegramChatID"]
channelName = os.environ["publicChannelName"]

engine = create_engine(os.environ["DATABASE_URL"])
Base = declarative_base()

class dbArticle(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    key = Column(String)
    created = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.bind = engine      
Base.metadata.create_all() 
Session = sessionmaker(bind=engine)


bot = telegram.Bot(token=token)
COLLECTION = {}

def messageAdmin(message):
    try:
        bot.send_message(adminUsername, message)
    except Exception:
        print(f"Error. Could not send Error message to admin.")
        
def addArticle(link, title, tmpCollection):
    global COLLECTION
    session = Session()

    articleID = link.split("!")[-1][:-1]

    # Skip article if it was in yesterday's articles
    if session.query(dbArticle).filter(dbArticle.key==articleID).first():
        return
    
    # Make sure the currently most read articles are the last ones in the collection
    elif articleID in COLLECTION:
        COLLECTION[articleID] = COLLECTION.pop(articleID)
        return
    website = requests.get(link)
    soup = BeautifulSoup(website.content, features="html.parser")

    url = "https://taz.de/!"+articleID
    try:
        ressort = soup.find_all("div","sect_meta")[0].div.ul.li.a.span.text
    except Exception:
        ressort = "None"
        print(title," has no ressort")
    subtitle = soup.find_all("p", "intro")
    messageText = f"<b>{title}</b>\n{subtitle[0].text} \n{url}"
    tmpCollection[articleID] = {"text":messageText, "title":title, "ressort":ressort}
    session.close()

def articlesFromRSS():
    global COLLECTION
    oldLen = len(COLLECTION)
    needed = 8-oldLen
    if needed < 2:
        needed, polNum, geselNum = 2, 1, 1
    else:
        polNum = math.floor((needed-1)/2)
        geselNum = math.ceil((needed-1)/2)+1

    print(f"Add {needed} Articles from RSS")

    try:
        tmpCollection = {}

        i = 0
        while len(tmpCollection) != polNum and i <= 12:
            gesellschaft = feedparser.parse('https://taz.de/!p4615;rss/')
            link = gesellschaft.entries[i].link
            title = gesellschaft.entries[i].title
            title = title.split(":")[0]
            addArticle(link, title, tmpCollection)
            i += 1

        i = 0
        while len(tmpCollection) != geselNum+polNum and i <= 12:
            politik = feedparser.parse('https://taz.de/!p4611;rss/')
            link = politik.entries[i].link
            title = politik.entries[i].title
            title = title.split(":")[0]
            addArticle(link, title, tmpCollection)
            i += 1

        COLLECTION = {**COLLECTION,**tmpCollection}

    except Exception as e:
        print("ERROR: Failed to get articles from RSS-Feed")
        message = f"Failed to get articles from RSS-Feed \n {e}"
        messageAdmin(message)

def scrape():
    time_now = datetime.datetime.now().strftime("%H:%M")
    print(f"[{time_now}] Scraping...")

    global COLLECTION

    urlTaz = "https://taz.de"

    try:
        website = requests.get(urlTaz)
        soup = BeautifulSoup(website.content, features="html.parser")
        meistgelesenDiv = soup.find("div", "clip_small")
        meistgelesenUl = meistgelesenDiv.find_all("ul")
        articleUl = meistgelesenUl[1]
        articles = articleUl.find_all("a")
    except Exception as e:
        articles = []
        print(f"ERROR encountered. Maybe taz.de is down? \n {e}")
        messageAdmin(f"ERROR encountered. Maybe taz.de is down? \n {e}")

    tmpCollection = {}
    
    for a in articles:
        
        try:
            title = a.contents[0].text
            urlArticle = str(a.get('href'))
            link = urlTaz+"/"+urlArticle.split("/")[-2]+"/"

            # Add article
            addArticle(link, title, tmpCollection)

        except Exception:
            e = traceback.format_exc()
            print()
            print(f"Error while scrpaing {link}\nERROR Message: \n{e}")

            message = f"Error while scraping {link} \n\n{e}"
            messageAdmin(message)

    # Add items from tmpCollection to Collection in reversed order
    for i in range(-1,(len(tmpCollection)+1)*-1,-1):
        key = list(tmpCollection.keys())[i]
        COLLECTION[key] = tmpCollection[key]  
    
    print(f"Number of articles for today: {len(COLLECTION)}")
    
    articleList = []
    for key, value in COLLECTION.items():
        articleList.append(value["title"])
    print("Today's articles: ", articleList)

def send(attempt=0):
    global COLLECTION
    print("----------")
    articlesFromRSS()
    ressortList =  []
    for key, value in COLLECTION.items():
        ressortList.append(value["ressort"])
    print("Ressorts: ",Counter(ressortList))
    
    
    time_now = datetime.datetime.now().strftime("%H:%M")
    print(f"[{time_now}] Sending...")

    finalMessage = ""

    if len(COLLECTION) == 0:
        print("Empty COLLECTION. Could not send anything.")
        session = Session()
        saved = session.query(dbArticle).all()
        session.close()
        print("Saved Article-titles: ", len(saved))
        return False

    sentArticles = []
    for i in range(-1,-9,-1):
        try:
            key = list(COLLECTION.keys())[i]
            finalMessage += COLLECTION[key]["text"]+"\n\n"
            sentArticles.append(key)
        except Exception:
            print("Less than 8 Articles in COLLECTION")
            break

    try:
        session = Session()
        if finalMessage == "":
            raise Exception("Empty message")
        bot.send_message(channelName, finalMessage, parse_mode=telegram.ParseMode.HTML)

        for eachkey in COLLECTION:
            session.add(dbArticle(key=eachkey))
        session.commit()
        eightdays = datetime.datetime.now()-datetime.timedelta(days=8)
        old = session.query(dbArticle).filter(dbArticle.created<=eightdays).delete()
        session.commit()
        COLLECTION = {}
        print("Sending successful!")
        
    except Exception:
        if attempt <= 1:
            print(f"Message: \n{finalMessage}")
            e = traceback.format_exc()
            print(e)
            messageAdmin(f"Couln't send message:\n{finalMessage}\n\n. Will try to send again in 10 minutes...\nError:\n\n{e}")
        if attempt <= 20:
            print("Couln't send articles. Will try to send again in 13 minutes...")
            time.sleep(780)
            scrape()
            send(attempt+1)
    finally:
        saved = session.query(dbArticle).all()
        print("Saved Article-titles: ", len(saved))
        session.close()

if __name__ == "__main__":
    print("Telegram Bot Infos: ", bot.get_me())

    schedule.every().day.at("21:00").do(scrape)
    schedule.every().day.at("00:10").do(scrape)
    schedule.every().day.at("11:00").do(scrape)
    schedule.every().day.at("13:45").do(scrape)
    schedule.every().day.at("15:45").do(scrape)
    schedule.every().day.at("17:00").do(scrape)
    schedule.every().day.at("17:30").do(scrape)
    schedule.every().day.at("17:55").do(scrape)
    schedule.every().day.at("18:12").do(scrape)
    schedule.every().day.at("18:15").do(send)

    scrape()

    while True:
        try:
            schedule.run_pending()
            time.sleep(300)
        except Exception as e:
            print(e)
