## New feature need: refunds are not handled when the cross months. For example, if I got avis
## rental car in July and United refunds me for it in August, the dashboard will average out in 
## a multi-month summary but not for that month to erase that transaction as if it never occurred at all.
## a manual mapping table could be created where I manually say what an expense was, and then what the
## refund description was that came along to remedy it. If it finds the join it filters out that result.

from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
# import mysql
# from mysql.connector import Error
from sqlalchemy import text
from sqlalchemy import sql
from pprint import pprint
import df2gspread as d2g
import pandasql as ps
import pandas as pd
import gspread
import time
import json
import sys
import os

def chaseDf():
    paths_to_chase_files = []
    chase_dfs = []
    for file in os.listdir():
        if 'chase' in file or 'Chase' in file:
            paths_to_chase_files.append(file)
    for path in paths_to_chase_files:
        df = pd.read_csv(path)
        
        if 'Details' in df.columns:
            df = df.drop(columns=['Details', 'Type', 'Balance', 'Check or Slip #'])
            df.rename(columns={'Posting Date':'Date'})
        else:    
            df = df.drop(columns=['Post Date', 'Type', 'Memo'])
            df = df.rename(columns={'Transaction Date' : 'Date', 'Category':'bank_category'})
        chase_dfs.append(df)
    df = pd.concat(chase_dfs)
    return df
    
def bofaDf():
    paths_to_bofa_files = []
    bofa_dfs = []
    for file in os.listdir():
        if 'stmt' in file:
            paths_to_bofa_files.append(file)
    for path in paths_to_bofa_files:
        df = pd.read_csv(path, skiprows = 6, on_bad_lines='skip')
        df = df.drop(columns=['Running Bal.'])
        bofa_dfs.append(df)  
    df = pd.concat(bofa_dfs)
    df.insert(loc = 2,column = 'bank_category',value = 'None')
    return df

def amexDf():
    paths_to_amex_files = []
    amex_dfs = []
    for file in os.listdir():
        if 'activity' in file and '.csv' in file:
            paths_to_amex_files.append(file)
    for path in paths_to_amex_files:
        df = pd.read_csv(path, on_bad_lines='skip')
        amex_dfs.append(df)  
    df = pd.concat(amex_dfs)
    df.insert(loc = 2,column = 'bank_category',value = 'None')
    return df

def banksDf(): 
    # Read statements and drop/rename columns to prepare for DataFrame union.
    # Also insert 'dwh_insert_date' at position 0 for ETL purposes.
    # Finally, deduplicate and remove nulls.
    chase_df = chaseDf()
    bofa_df = bofaDf()
    amex_df = amexDf()
    dfs = [chase_df, bofa_df, amex_df]
    df = pd.concat(dfs)
    df = df.rename(columns={'Date':'date', 'Description':'description', 'Category':'bank_category', 'Amount':'amount'})
    df.insert(loc = 0,column = 'dwh_insert_date',value = str(datetime.now()))
    df = df.drop_duplicates()
    df = df.dropna()
    df['amount'] = df['amount'].astype('str').str.replace(',','').astype('float')
    return df


    


def dfToSheets(df, sheet_name):
    # Hard coding the values for now.
    os.chdir('/Users/Noah.Hazan/Downloads/')
    scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/spreadsheets',"https://www.googleapis.com/auth/drive.file","https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    gc = gspread.authorize(creds)
    worksheet = gc.open('MINT_2.0').worksheet(f'{sheet_name}')
    if sheet_name == 'Sheet1':
        df['dwh_insert_date']=df['dwh_insert_date'].astype(str)
    worksheet.clear()
    worksheet.update('A1',[df.columns.values.tolist()] + df.values.tolist())


    

transform_query = """
with precise_categories as (
    SELECT
        '2023-07-31' as dwh_insert_date,
        '2023-07-31' as date,
        'MANUAL INCOME' as description,
        6528.11 as amount,
        'INCOME' as category
    UNION ALL 
    SELECT
        dwh_insert_date as dwh_insert_date,
        cast(date as char(100)) as date,
        description,
        
        CASE WHEN DESCRIPTION = 'Amazon.com*505LS9B83' THEN cast(amount as float)+600 else 
        cast(amount as float) END as amount,
       case
       
            WHEN bank_category = 'Groceries' THEN 'GROCERIES'
            WHEN lower(description) like '%walmart%' THEN 'GROCERIES'
            WHEN lower(DESCRIPTION) LIKE '%construction%' then 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%Zelle payment to Avior Hazan%' THEN 'CHARITY'
            WHEN DESCRIPTION = 'Online Banking transfer from BRK 8183 Confirmation# XXXXX51288' THEN 'INCOME'
            WHEN DESCRIPTION LIKE '%Online Banking transfer from BRK 8183 Confirmation# XXXXX65530%' THEN 'INCOME'
            WHEN DESCRIPTION = 'Zelle Transfer Conf# bbwv51mbz; RalphGroupLLC' THEN 'WANTS'
            WHEN DESCRIPTION = 'VENMO DES:PAYMENT ID:XXXXX74724994 INDN:SARAH HAZAN CO ID:XXXXX81992 WEB' THEN 'CHARITY'
            WHEN DESCRIPTION = 'VENMO DES:PAYMENT ID:XXXXX43894846 INDN:NOAH HAZAN CO ID:XXXXX81992 WEB' THEN 'CHARITY'
            WHEN DESCRIPTION = 'FACTS TUITION AND FEES' THEN 'DAYCARE/BABY'
            WHEN DESCRIPTION = 'Zelle payment to Danny Palgon for Thank you for being a Tzadik! See you tomorrow"; Conf# zz1gqnt3a"' THEN 'CHARITY'
            WHEN DESCRIPTION = 'Zelle payment from JEFFREY SCHWARTZ Conf# zzxws2v23' THEN 'CHARITY'
            WHEN DESCRIPTION = 'PAYPAL *KHALCHASSID' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%Rabbi Pesach Raymon%' THEN 'DAYCARE/BABY'
            WHEN DESCRIPTION LIKE '%CHARIDY%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%Amazing Escape%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%GRANDMA%' THEN 'RESTAURANT/COFFEE'
            WHEN lower(description) like '%zelle%' then 'MISC'
            WHEN DESCRIPTION LIKE '%JEFF%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%TICKPICK%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%HPCT-CAE%' THEN 'DAYCARE/BABY'
            WHEN lower(description) LIKE '%costco%' THEN 'GROCERIES'
            WHEN lower(description) LIKE '%doordash%' THEN 'WANTS'
            WHEN lower(description) lIKE '%tyrwhi%' THEN 'WANTS'
            WHEN lower(description) LIKE '%aquarium%' THEN 'WANTS' 
            WHEN lower(description) LIKE '%mattress%' THEN 'WANTS'
            WHEN lower(description) LIKE '%appliance metuch%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%CHARITY%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%BREWED%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%LABCORP%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%SBUFEESDEPOSIT%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%STUDENT LN%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%MEDIACOM%' THEN 'INCOME'
            WHEN DESCRIPTION LIKE '%SOHO NAILS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%RAINBOW CLEANERS%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%COFFEE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%RITE AID%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%CHINA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%GOLDMAN SACHS%' THEN 'TRANSFER'
            WHEN DESCRIPTION LIKE '%Adjustment/Correction%' THEN 'BILL PAYMENT'
            WHEN DESCRIPTION LIKE '%BKOFAMERICA ATM 07/03 #XXXXX3883 DEPOSIT HIGHLAND PARK HIGHLAND PARK NJ%' THEN 'BILL PAYMENT'
            WHEN DESCRIPTION LIKE '%PAYMENT%' AND DESCRIPTION NOT LIKE '%VENMO%' THEN 'BILL PAYMENT'
            WHEN DESCRIPTION LIKE '%VENTURE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%STUDIOS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BANANARE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%HONDA%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%YAD ELIEZER%' THEN 'CHARITY'
            WHEN LOWER(DESCRIPTION) LIKE '%maaser%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%LOIS E. SHULM%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%TARGET%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%TOMCHEI%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%LUKOIL%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%SUNOCO%' THEN 'CAR'
            WHEN lower(description) LIKE '%maaser%' or lower(description) LIKE '%matanot%' or lower(description) like '%chesed%' then 'CHARITY'
            WHEN DESCRIPTION LIKE '%DUNKIN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%STARBUCKS%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SHEETZ%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%STOP & SHOP%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%INSTACART%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%SUNOCO%' THEN 'GAS'
            WHEN DESCRIPTION LIKE '%PSEG%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%PIZZA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SUSHI%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%VERIZON%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%OPTIMUM%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%DEPT EDUCATION%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%ONLINE PMT%' THEN 'BILL PAYMENT'
            WHEN DESCRIPTION LIKE '%Amazon%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%CHASE CREDIT%' THEN 'BILL PAYMENT'
            WHEN DESCRIPTION LIKE '%Trnsfr%' THEN 'TRANSFER'
            WHEN DESCRIPTION LIKE '%BAHAMAR%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%ANNUAL MEMBERSHIP FEE%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%ACME%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%WOODBRIDGE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BAHA BAY%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%CIBO%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%BERMAN BOOKS%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%HOME DEPOT%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%PEDIATRIC%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%MARKET%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%FIT2RUN%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%H&%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%FUEL%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%BABY%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%NORDRACK%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BASKETEERS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BP%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%SHELL OIL%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%GROCERY%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%MILKY WAY%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%MALL%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%CONCESSIONS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BREWERY%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%WIFI%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%HUDSON ST%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%CANONICA%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%OXYFRESH%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%FLORA%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%Bill Pay%' THEN 'BILL PAYMENT'
            WHEN DESCRIPTION LIKE '%Check%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%transfer%' THEN 'TRANSFER'
            WHEN DESCRIPTION LIKE '%BLUESTONE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%RWJ NEW%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%SPOTIFY%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%APPLE%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%ATM%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%Marcus Invest%' THEN 'TRANSFER'
            WHEN DESCRIPTION LIKE '%MTA%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%WELLS FARGO%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%AMZN%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%BAKERY%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%WHOLEFDS%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%TRANSACTION FEE%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%MINI GOLF%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%NINTENDO%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%BRIDGE TURKISH%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%LYFT%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%UBER%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%BED BATH%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%CAFE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%RACEWAY%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%CVS%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%DERECHETZCH%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%STAUF%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%UNITED%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%CAR%' AND DESCRIPTION NOT LIKE '%CARE%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%FEDEX%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%DERECH%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%KOLLEL%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%WITHDRWL%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%NJT%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%DOLLAR-A-DAY%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CITRON%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%GREAT CLIPS%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%PENSTOCK%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%HOTEL%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%RESTAURANT%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PAYPAL%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%WALGREENS%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%NAILS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%GIVING%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%AIRBNB%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%STOP &%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%BUDGET.COM%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%SPIRIT%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%CLEANERS%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%DUANE READE%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%GET AIR%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%VENDING%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%CONG.%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%7-ELEVEN%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%GLATT 27%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%BEXLEY MKT%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%TRADER JOE%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%HEADWAY%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%EXXON%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%CHAI%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%BUY BUY%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%HYATT%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%KOSHER%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%HAVA JAVA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%KOHL%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%SHOPRITE%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%OLD NAVY%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%AMC%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%SPEEDWAY%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%COFF%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PHARMA%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%CABOKI%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%RITA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ROASTERY%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%KROGER%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%FINES AND COSTS%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%MUSIC%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%KITTIE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%CHASDEI%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%BESTBUY%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%CHICKIES%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SPA%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%PRIME%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%ROCKNROLL%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PINOT%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%WALMART%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%BOUTIQUE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%ZAGE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SKI%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%QUICK CHEK%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%THEATRE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%DONATI%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%FIRESIDE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PARKING%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%YOLANDA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%TJMA%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%KISSENA%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%PARTY%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%STAPLES%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%YERUSHALAYIM%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%LAWRENCE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%LOFT%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%ANTHRO%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%GIVING%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%Travel%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%VICTORIA%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%PARKING%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%TAXI%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%TAVLIN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%GIVING%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SCHNITZ%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PARK P%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%DELI KAS%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%MICHAELS%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%CIRCLE K%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%HUMBLE TOAST%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ANN TAYLOR%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BEDBATH%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%SAMMY%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ZAGAFEN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%COLOR ME%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BETH JACOB%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%PARK DELI%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%RESTAU%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%NCSY%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%ZENNI%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%RWJ%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%Duane%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%MUNICI%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%MEOROT%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%BBQ%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%BAKERIST%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%EXPEDIA%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%656 OCEAN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%HILTON%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%ROBINHOOD%' THEN 'TRANSFER'
            WHEN DESCRIPTION LIKE '%VENMO%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%NATIONWIDE%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%GRAETERS%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%WAL-MART%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%EDEN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PARK DENTAL%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%PARKCOLUMBUS%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%CRIMSON%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%BARNES%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%Theater of%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%CLOTHING%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%JUDAICA%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%ROAD RUNNER%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%KITCHEN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%PIZZ%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%WEGMAN%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%AIRPORT%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%BLOOMINGDAL%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%FEE%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%NJMVC%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%FUNDRA%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CULVV%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%WOMENS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%GRILL%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%MACY%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%YU.EDU' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%BRAVO%' THEN 'GROCERIES'
            WHEN DESCRIPTION LIKE '%BRACHA' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SURGERY%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%VEORIDE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%PILOT%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%NORDSTROM%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%KEEPS%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%MEDICAL%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%SAM ASH%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%SCARF%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%STUDIOS' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%JJS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BANANARE' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BAGEL%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%BRUCE SPRINGSTEEN%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%MENUCHA%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%KOSH%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%TOPGOLF%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BARBER SHOP%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%VANGUARD%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%DOLLAR CITY%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%IPA MAN%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%CAFFE YAHUDA HALEVI%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%GIFTS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%AROMA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ZOL GADOL%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%TMOL%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%GAN SIPOR SAKER%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%BEGAL CAFE REHAVIA%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%COFFE%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%KAFE RIMON%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SUPER PHARM%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%SHORASHIM%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%GRAFUS BEAM%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%AMI%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%L LEVY NADLAN%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%HOTEL%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%INFUSED JLM%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%HEADWAY%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%FACEBK%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%PURCHASE NEW BRUNSWICK NJ%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ZARA USA%' THEN 'GENERAL NEEDS (TARGET, AMAZON, RITE AID, ETC)'
            WHEN DESCRIPTION LIKE '%TOP GOLF%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%AMERICAN FRIENDS OF%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CHAILI%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%TORAHT%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%GIVING%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%MR. C%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%AIRPOR%' THEN 'TRAVEL'
            WHEN (DESCRIPTION LIKE '%ATM%' AND DESCRIPTION LIKE '%DEPOSIT%') THEN 'INCOME'
            WHEN description LIKE '%ZALES%' THEN 'WANTS'
            WHEN description LIKE '%USPS%' THEN 'MISC'
            WHEN description LIKE '%Salt%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN description LIKE '%SEASONS%' THEN 'GROCERIES'
            WHEN description LIKE '%TIRES%' THEN 'CAR'
            WHEN description LIKE '%SAINT PETERS%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN description LIKE '%Milk N%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN description LIKE '%TZEDAKA%' THEN 'CHARITY'
            WHEN description LIKE '%InstaMed%' THEN 'MEDICAL AND GYM'
            WHEN description LIKE '%HURRICANE SIMULATOR%' THEN 'WANTS'
            WHEN description LIKE '%HIGHLANDPARK CONG%' THEN 'DAYCARE/BABY'
            WHEN description LIKE '%TCBY%' AND DESCRIPTION NOT LIKE '%DISNEY%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%JEFF%' THEN 'CAR'
            WHEN DESCRIPTION = 'Zelle payment to Ohr Torah for RDF"; Conf# qhpxvtaio' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%TM TICKETMASTER%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BONEI OLAM ORG%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%GoFundMe Aviva and Mo Ber%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%BONEI OLAM ORG 1%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%PPA Tow Lot 1%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%ZEEL NETWORKS  INC.%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BONEI OLAM ORG 1%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SESAME PLACE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%Indeed Jobs%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%PHILADELPHIA PAR DES:PHILADELPH ID: INDN:Noah Hazan CO ID:XXXXX55714 WEB%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%MAPLEWOOD TOTAL SONO LLC%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%LS LOCAL BICYCLE SHOPQ%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%GOFNDME *ETZ AHAIM PUR%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%ETOLL AVIS U614420483%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%VIEW A MIRACLE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%GAP OUTLET US 1106%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%BONEI OLAM ORG 1%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SPOONS BOROUGH PARK%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ACADEMY CDR ACEND PAC%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%BONEI OLAM ORG 1%' THEN 'CHARITY'

            WHEN DESCRIPTION LIKE '%PP*CHERISHEDME%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%TST* Grandmas Cheese - L%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%AHAVAS CHESED%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CASHSTAR SEPHORA EGIFT%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%CONG TOV LKOL%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%ZTL*CHERISHED MEMORIES UL%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%MED*IMM CARE EDISON%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%SQ *KOSOCO%' THEN 'RESTAURANT/COFFEE'
            
            WHEN DESCRIPTION LIKE '%WAWA 8365%' THEN 'CAR'
            
            WHEN DESCRIPTION LIKE '%METLIFE STADIUM%' THEN 'WANTS'
            
            WHEN DESCRIPTION LIKE '%TURKEY HILL #0239%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%ESSEX COUNTY ATTRACTIONS%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%ALLIANZ EVENT INS%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%DURHAM WOMAN CNTR 166B%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%SABA COLUMBUS LLC%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%LECHEM VCHOLOV%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SP URBANPOPS%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%WDW AFRICA ICECREAM%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SQ *CENTRAL PARK BOAT REN%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%TST* 16 HANDLES - RUTGERS%' THEN 'RESTAURANT/COFFEE'
            WHEN lower(description) like '%ohr%t%' then 'CHARITY'
            WHEN DESCRIPTION LIKE '%PLAYA BOWLS - S BRUNSW%' THEN 'RESTAURANT/COFFEE'
        
            WHEN DESCRIPTION LIKE '%RED MANGO%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%URBAN AIR CRYSTAL RUN%' THEN 'WANTS'
 
            WHEN DESCRIPTION LIKE '%AMK LIBERTY SCIENCE CENTE%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%Hulu 877-8244858 CA%' THEN 'WANTS'
    
            WHEN DESCRIPTION LIKE '%KEYMELOCKSMITHS.COM%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%TST* 16 HANDLES - RUTGERS%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%FANDANGO%' THEN 'WANTS'
      
            WHEN DESCRIPTION LIKE '%CHESED VEAMUNA%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SQ *CHIZUK HATORAH INC%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CHESEDFUND-HOLLYWOOD H%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%PP*Yeshiva Ateres Mordeca%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CONG OHR YECHESKEL%' THEN 'CHARITY'
        
            WHEN DESCRIPTION LIKE '%COLUMBUS ZOO GUEST SERVI%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%61585 - LIBERTY SCIENCE C%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%Zelle payment to Ohr Torah for RDF"; Conf# qhpxvtaio%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%Urban Air Milltown%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%PPA ON STREET KIOSKS%' THEN 'WANTS'
    
            WHEN DESCRIPTION LIKE '%HAAGEN DAZS #909%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SP URBANPOPS%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%SSA COLUMBUS ZOO &amp; AQUARI%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%SQ *MAZUMDER ENTERTAINMEN%' THEN 'WANTS'
      
            WHEN DESCRIPTION LIKE '%JUS BY JULIE NJ%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%LEV LEYELED INC.%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%SQ *FUN KIDS TRAIN%' THEN 'WANTS'
        
            WHEN DESCRIPTION LIKE '%ETOLL AVIS U614420483%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%TST* 16 HANDLES - RUTGERS%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%GLACIER ICE CREAM%' THEN 'RESTAURANT/COFFEE'
            WHEN DESCRIPTION LIKE '%ETOLL AVIS U614420483%' THEN 'TRAVEL'
            WHEN DESCRIPTION LIKE '%GOOGLE *Google Storage%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%LECHEIRIS ORGANIZATION%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%PROVIDENT%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%RAYMOUR%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%Belnick%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%MARSHALLS%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%CHESSED%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%UPS STORE%' THEN 'MISC'
            WHEN DESCRIPTION LIKE '%LOWES%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%IKEA%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%JEWLR%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%RUGS%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%HOMEDEPOT%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%RUGS%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%PUMPABLES%' THEN 'MEDICAL AND GYM'
            WHEN DESCRIPTION LIKE '%TASKRABBIT%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%EDISON WATER%' THEN 'HOUSE BILLS'
            WHEN DESCRIPTION LIKE '%FACTS TUITION%' THEN 'DAYCARE/BABY'
            WHEN DESCRIPTION LIKE '%IRS%' THEN 'TAXES'
            WHEN DESCRIPTION LIKE '%NEW JERSEY TGI%' THEN 'TAXES'
            WHEN DESCRIPTION LIKE '%WDW%' THEN 'WANTS'
            WHEN DESCRIPTION LIKE '%ANSHEI%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%CONGREGATION%' THEN 'CHARITY'
            WHEN DESCRIPTION LIKE '%AVARE%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%DETAILING%' THEN 'CAR'
            WHEN DESCRIPTION LIKE '%BREAST%' THEN 'DAYCARE/BABY'
            WHEN DESCRIPTION LIKE '%GoFund%' THEN 'CHARITY'
            
            
            
            WHEN amount > 0
            AND (
                DESCRIPTION NOT LIKE '%GOLDMAN SACHS%'
                and DESCRIPTION NOT LIKE '%PAYMENT%'
                and DESCRIPTION NOT LIKE '%TRANSFER%'
            ) THEN 'INCOME'
            ELSE 'UNCLASSIFIED'
        END AS category
    FROM
        df
)
select
    *
FROM
    precise_categories
"""

df = banksDf()
data = ps.sqldf(transform_query, locals())
dfToSheets(data, 'Sheet1')
print('done')
