# Small telegram bot that gets most popular articles from taz.de and sends them to a telegram channel
# -*- coding: utf-8 -*-
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import pickle
import os
import math
import sys
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import traceback
import feedparser
from collections import Counter
import logging
import logging.config
import asyncio

# Load logging config and create logger
logging.config.fileConfig('config_log.ini')
logger = logging.getLogger('root')

load_dotenv()

token = os.environ["TELEGRAM_TOKEN"]
adminUsername = os.environ["ADMIN_TELEGRAM_CHAT_ID"]
channelName = os.environ["PUBLIC_CHANNEL_NAME"]

engine = create_engine(os.environ["DATABASE_URL"])
Base = declarative_base()

class dbArticle(Base):
    __tablename__ = 'articles'
    id = Column(Integer, primary_key=True)
    key = Column(String)
    created = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.bind = engine      
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)

async def get_bot_info():
    bot = await telegram.Bot(token=token)
    bot_info = await bot.get_me()
    return bot_info

try:
    bot_info = asyncio.run(get_bot_info())
except:
    bot_info = {"name": None, "id": None}
    logger.warning("Connection to telegram timed out")

try:
    with open("tmp_articles.pkl", "rb") as fp:
        COLLECTION = pickle.load(fp)
except:
    COLLECTION = {}

def messageAdmin(message):
    try:
        bot.send_message(adminUsername, message)
    except Exception:
        logger.error("Could not send Error message to admin.")
        
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
        ressort = soup.find(attrs={"data-breadcrumb-level": "1"}).find("a").text
        #ressort = soup.find_all("div","sect_meta")[0].div.ul.li.a.span.text
    except Exception:
        ressort = "None"
        logger.warning(f"{title} has no ressort")
    subtitle = soup.find_all("p", class_=lambda value: value and "subline" in value)
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

    logger.info(f"Add {needed} Articles from RSS")

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
        message = f"Failed to get articles from RSS-Feed \n {e}"
        logger.error(message)
        messageAdmin(message)

def scrape():
    time_now = datetime.datetime.now().strftime("%H:%M")
    logger.info(f"[{time_now}] Scraping...")

    global COLLECTION

    urlTaz = "https://taz.de"

    try:
        website = requests.get(urlTaz)
        soup = BeautifulSoup(website.content, features="html.parser")
        meistgelesenDiv = soup.find_all("div", "type-mostread")
        articles = []
        for div in meistgelesenDiv:
            articles.append(div.find("a", "teaser-link"))
    except Exception as e:
        articles = []
        logger.error(f"Maybe taz.de is down? Or taz layout changed? \n {e}")
        messageAdmin(f"ERROR encountered. Maybe taz.de is down? \n {e}")

    tmpCollection = {}
    
    for a in articles:
        try:
            title = a.find("p", "headline").text
            urlArticle = str(a.get('href'))
            link = urlTaz+"/"+urlArticle.split("/")[-2]+"/"

            # Add article
            addArticle(link, title, tmpCollection)

        except Exception:
            e = traceback.format_exc()
            logger.error(f"Error while scraping {link}\nERROR Message: \n{e}")

            message = f"Error while scraping {link} \n\n{e}"
            messageAdmin(message)

    # Add items from tmpCollection to Collection in reversed order
    for key in reversed(tmpCollection.keys()):
        COLLECTION[key] = tmpCollection[key]  
    
    logger.info(f"Added {len(tmpCollection)} new articles. Total today: {len(COLLECTION)}")
    titles_ressorts = [(each["title"], each["ressort"]) for each in COLLECTION.values()]
    logger.debug(f"Today's articles: {titles_ressorts}")
    
    # Save current articles in pickle
    print(COLLECTION)
    with open("tmp_articles.pkl", "wb") as fp:
        pickle.dump(COLLECTION, fp)

def send(attempt=0):
    global COLLECTION
    articlesFromRSS()
    ressortList =  []

    logger.info(f"Start sending...")
    for key, value in COLLECTION.items():
        ressortList.append(value["ressort"])
    logger.debug("----- Ressorts: ",Counter(ressortList))
    
    time_now = datetime.datetime.now().strftime("%H:%M")
    finalMessage = ""

    if len(COLLECTION) == 0:
        logger.warning("Empty COLLECTION. Could not send anything.")
        session = Session()
        saved = session.query(dbArticle).all()
        session.close()
        logger.debug(f"Number of articles in db: {len(saved)}")
        return False

    sentArticles = []
    for i in range(-1,-9,-1):
        try:
            key = list(COLLECTION.keys())[i]
            finalMessage += COLLECTION[key]["text"]+"\n\n"
            sentArticles.append(key)
        except Exception:
            logger.warning("Less than 8 Articles in COLLECTION")
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
        
        # Clear tmp_articles.pkl
        COLLECTION = {}
        with open("tmp_articles.pkl", "wb") as fp:
            pickle.dump(COLLECTION, fp)
        
        logger.info("Sending successful!")
        
    except Exception:
        if attempt <= 1:
            logger.error(f"Message: \n{finalMessage} \n {e}")
            e = traceback.format_exc()
            messageAdmin(f"Couln't send message:\n{finalMessage}\n\n. Will try to send again in 10 minutes...\nError:\n\n{e}")
        if attempt <= 20:
            logger.warning("Couln't send articles. Will try to send again in 13 minutes...")
            time.sleep(780)
            scrape()
            send(attempt+1)
    finally:
        logger.debug("Start the finally bracket")
        try:
            saved = session.query(dbArticle).all()
            logger.debug("Article-titles in database ", len(saved))
            session.close()
        except:
            logger.debug("Encountered Problem")

def scrape_and_send():
    scrape()
    send()

if __name__ == "__main__":
    logger.info(f"--- Tazbot launched ---")
    logger.info(f"Logfile location: {logger.handlers[1].baseFilename}")
    logger.info(f'Telegram Bot name: {bot_info["name"]} ID: {bot_info["id"]} Target Channel: {channelName}')
    logger.info(f"Loaded {len(COLLECTION)} articles from last run")


    send_time = os.environ.get("DAILY_SEND_TIME", "18:15")
    schedule.every().day.at(send_time).do(scrape_and_send)

    scrape()
    schedule.every().hour.do(scrape)

    while True:
        try:
            schedule.run_pending()
            time.sleep(60)
        except Exception as e:
            logger.error
