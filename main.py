# -*- coding: utf-8 -*-
"""getAmazonNewReleaseRanking.ipynb

Automatically generated by Colaboratory.

Original file is located at
    https://colab.research.google.com/drive/1x3no05xLIY1DttkIGRz4HwHOwAvEFdHt
"""
"""
!pip install beautifulsoup4
!pip install requests
!pip3 install lxml
!pip install retry
!pip install gspread
!pip install --upgrade google-api-python-client
"""
# coding: utf-8
import requests
from bs4 import BeautifulSoup
import urllib
from retry import retry
import re
import pandas as pd
import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

#url = "https://www.amazon.co.jp/gp/bestsellers/books/4915091051" の情報を取得する
uri = 'https://www.amazon.co.jp/'
category = 'books/4915091051'

def pages():
    pages =[1,2,3,4,5] #取得するRankingの順位を増やしたいときはここを増やす
    urls = []
    for page in pages:
        url = uri + 'gp/bestsellers/' + category + '?pg=' + str(page)    
        urls.append(url)
    return urls

#urlsリストのページ情報を取得
@retry(urllib.error.HTTPError, tries=12, delay=1, backoff=2)
def soup_url(urls):
    soups = []
    for url in urls:
        htmltext = requests.get(url).text
        soup = BeautifulSoup(htmltext, "lxml")
        soups.append(soup)
    return soups

# JAN13のチェックデジットを作成する
def checkdigit(code):
    s = str(code)[:12]
    a = 0
    b = 0

    for i in range(0, len(s), 2):
        a += int(s[i])

    for i in range(1, len(s), 2):
        b += int(s[i])

    d = (a + (b * 3)) % 10
    d = 10 - d 
    if d == 10:
        d = 0
    return d

#取得したページの情報から、必要なデータを抜き出す
@retry(urllib.error.HTTPError, tries=7, delay=1)
def get_ISBN(soups):
    df = pd.DataFrame(index=[],columns=["date","ranking", "title", "author", "jan", "price", "releaseDate"])
    for soup in soups:
        for el in soup.find_all("div", class_="zg_itemRow"):
            rank  = el.find("span", class_="zg_rankNumber").string.strip()
            rank = rank.replace(".","")
            
            title  = el.find_all("div", class_="p13n-sc-truncate")[0].string.strip()

            author = el.find("a", class_="a-size-small")
            if author:
                author = author.string.strip()
            else:
                author = el.find("span", class_="a-size-small").string.strip()

            if author.isdigit():
                author = el.find("span", class_="a-size-small").string.strip()
                
            price = el.find("span", class_="p13n-sc-price")
            if price:
                price = price.string.strip()
            else:
                price = "not defined"

            asin_tag = el.find("a", class_="a-link-normal").get("href")
            asin_list =re.findall('[0-9]{9}.' , str(asin_tag))
            asin = ",".join(asin_list)
            
            jan12 = "978" + asin
            checkd = checkdigit(jan12)
            jan13 = jan12[:-1] + str(checkd)
            
            date = datetime.date.today().strftime('%y%m%d')
            
            re_date = el.find("div", class_="zg_releaseDate").string.strip()
            re_date = re_date.replace("発売日: ", "")
            re_date = re_date.replace("出版日: ", "")
            
#            print("{} {} {} {} {} {} {}".format(date, rank, price, title, author, jan13, re_date))

            series = pd.Series([date, rank, title, author, str(jan13), price, re_date], index = df.columns)
            df = df.append(series, ignore_index = True)

    return df

# テーブルに保管していく
# Heroku用の認証（変数を環境変数仕様にする必要あり後述）
scope = ['https://spreadsheets.google.com/feeds',
         'https://www.googleapis.com/auth/drive']

# 辞書オブジェクト。認証に必要な情報をHerokuの環境変数から呼び出している
credential = {
                "type": "service_account",
                "project_id": os.environ['SHEET_PROJECT_ID'],
                "private_key_id": os.environ['SHEET_PRIVATE_KEY_ID'],
                "private_key": os.environ['SHEET_PRIVATE_KEY'],
                "client_email": os.environ['SHEET_CLIENT_EMAIL'],
                "client_id": os.environ['SHEET_CLIENT_ID'],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
                "client_x509_cert_url":  os.environ['SHEET_CLIENT_X509_CERT_URL']
             }

credentials = ServiceAccountCredentials.from_json_keyfile_dict(credential, scope)

gc = gspread.authorize(credentials)

wks = gc.open_by_key('1KRNyGqmFRvoAFGGdPrpCXvFBZB71euRZp7O_BL_FDgk').sheet1

# append処理の為のリスト化
# https://note.nkmk.me/python-pandas-list/
def append_sheet(append_list):
    for row in append_list:
        if row[0] == "index":
            continue
        else:
            wks.append_row(row, value_input_option='RAW')

#一連の実行関数
def main():
    urls = pages()
    soups = soup_url(urls)
    ranking_df = get_ISBN(soups)
#    print(ranking_df)        
    append_list = ranking_df.values.tolist()
    append_sheet(append_list)
    
if __name__ == '__main__':
    main()
    
