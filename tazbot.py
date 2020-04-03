#Small telegram bot that gets most popular articles from taz.de and sends them in a telegram channel
from bs4 import BeautifulSoup
import requests
import schedule
import telegram
import time
import os
import datetime
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import traceback
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
        
def addArticle(link, title, name, tmpCollection):
    website = requests.get(link)
    soup = BeautifulSoup(website.content, features="html.parser")

    subtitle = soup.find_all("p", "intro")
    messageText = f"<b>{title}</b>\n{subtitle[0].text} \n{link}"
    tmpCollection[name] = {"text":messageText, "title":title}

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

    tmpCollection = {}
    session = Session()
    for a in articles:
        
        try:
            name = a.text
            title = a.h4.text
            # Skip article if it was in yesterday's articles
            if session.query(dbArticle).filter(dbArticle.key==name).first():
                continue
            
            # Make sure the currently most read articles are the last ones in the collection
            elif name in COLLECTION:
                COLLECTION[name] = COLLECTION.pop(name)
                continue
            
            else:
                urlArticle = str(a.get('href'))
                link = urlTaz+urlArticle
                # Add article
                addArticle(link, title, name, tmpCollection)

        except Exception:
            e = traceback.format_exc()
            print()
            print(f"ERROR: {e}")

            message = f"Error. Couldn't scrape taz.de\n\n{e}"
            messageAdmin(message)
            session.close()

    for i in range(-1,(len(tmpCollection)+1)*-1,-1):
        key = list(tmpCollection.keys())[i]
        COLLECTION[key] = tmpCollection[key]  
    
    print(f"Number of articles for today: {len(COLLECTION)}")
    
    articleList = []
    for key, value in COLLECTION.items():
        articleList.append(value["title"])
    print("Today's articles: ", articleList)

    if len(COLLECTION) == 0 or len(articles) == 0:
        message = f"Possible problem with scraping of taz.de. COLLECTION = {COLLECTION}"
        messageAdmin(message)
    
    session.close()

def send(attempt=0):
    print("Sending...")

    global COLLECTION
    count = 1
    message = ""

    if len(COLLECTION) == 0:
        print("Empty COLLECTION. Could not send anything.")
        print(f"Number of articles for today: {len(COLLECTION)}")
        return False

    sentArticles = []
    for i in range(-1,-9,-1):
        try:
            key = list(COLLECTION.keys())[i]
            message += COLLECTION[key]["text"]+"\n\n"
            sentArticles.append(key)
        except Exception:
            print("Less than 8 Articles in COLLECTION")
            session = Session()
            saved = session.query(dbArticle).all()
            session.close()
            print("Saved Article-titles: ", len(saved))
            break

    try:
        session = Session()
        if message == "":
            raise Exception("Empty message")
        bot.send_message(channelName, message, parse_mode=telegram.ParseMode.HTML)

        for eachkey in COLLECTION:
            session.add(dbArticle(key=eachkey))
        session.commit()
        eightdays = datetime.datetime.now()-datetime.timedelta(days=8)
        old = session.query(dbArticle).filter(dbArticle.created<=eightdays).delete()
        session.commit()
        COLLECTION = {}

        saved = session.query(dbArticle).all()
        print("Saved Article-titles: ", len(saved))
        print()
        print("Sending successful!")
    except Exception:
        if attempt <= 1:
            print(f"Message: \n{message}")
            e = traceback.format_exc()
            print(e)
            messageAdmin(f"Couln't send message:\n{message}\n\n. Will try to send again in 10 minutes...\nError:\n\n{e}")
        if attempt <= 20:
            print("Couln't send articles. Will try to send again in 13 minutes...")
            time.sleep(780)
            scrape()
            send(attempt+1)
    finally:
        print(f"Number of articles for today: {len(COLLECTION)}")
        session.close()

if __name__ == "__main__":
    print("Telegram Bot Infos: ", bot.get_me())

    schedule.every().day.at("00:10").do(scrape)
    schedule.every().day.at("11:00").do(scrape)
    schedule.every().day.at("13:45").do(scrape)
    schedule.every().day.at("15:45").do(scrape)
    schedule.every().day.at("17:00").do(scrape)
    schedule.every().day.at("17:30").do(scrape)
    schedule.every().day.at("18:05").do(scrape)
    schedule.every().day.at("18:06").do(send)

    scrape()
    send()
    while True:
        try:
            schedule.run_pending()
            time.sleep(600)
        except Exception as e:
            print(e)
