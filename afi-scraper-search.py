from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options  
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, UnexpectedAlertPresentException, ElementNotVisibleException
import time, datetime, re, os, logging, sys
import pandas as pd
import numpy as np
from progress.bar import Bar
from getPDF import getPubFile

if sys.argv:
    nslice = sys.argv[1]
    this_slice = sys.argv[2]
else:
    nslice = 1
    this_slice = 1

now = datetime.datetime.now()
output_dir = "search-results/{}-{}-{}-{}-{}-{}".format(now.year,now.month,now.day,now.hour,now.minute,now.second)

pubslist_output = this_slice + 'pubslist.csv'
serieslist_output = this_slice + 'serieslist.csv'
detaillist_output = this_slice + 'detaillist.csv'

os.mkdir(output_dir)
os.chdir(output_dir)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler(this_slice+'-afi-scraper-search.log')
fh.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.WARNING)
logger.addHandler(fh)
logger.addHandler(sh)

def handleAlert(level='main'):
    browser.get_screenshot_as_file("Alert"+time.time()+".png")
    alertObj = browser.switch_to.alert
    logger.debug("Alert: (%s) - %s",level,alertObj.text)
    alertObj.accept()
    time.sleep(1)

# setup selenium driver in chrome
path_to_chromedriver = '/Users/Capizzi/Google Drive/Code projects/chromedriver'
chrome_options = webdriver.ChromeOptions()

prefs = {'download.default_directory': '/Users/Capizzi/Google Drive/Code projects/afi-scraper/'}

chrome_options.add_experimental_option('prefs', prefs)
chrome_options.add_argument("--log-level=3")
chrome_options.add_argument("--incognito")
chrome_options.add_argument('headless')

browser = webdriver.Chrome(executable_path = path_to_chromedriver, options = chrome_options)
browser.implicitly_wait(0.25)
url = 'http://www.e-publishing.af.mil/Product-Index/'

# build category list
browser.get(url)
categories = browser.find_element_by_css_selector('.main-nav > .col-md-6 > ul').get_attribute("outerHTML")
category_list = BeautifulSoup(categories,'lxml').find_all('a')
category_progress = Bar('Categories', max=len(category_list))
catlist = []
for category in category_list :
    cat = {}
    cat['CategoryOnClick'] = category.attrs['onclick'][0:-14]
    cat['Category'] = category.text.strip('\"')
    catlist.append(cat)
    category_progress.next()
category_progress.finish()
logger.info('Found %s categories',len(catlist))

# build subcategory list
subcatlist = []
browser.get(url)
subcategory_progress = Bar('Subcategories', max=len(catlist))
for item in catlist:
    catid = "#cat-{} div ul" .format(re.findall(r"\d+",item["CategoryOnClick"])[0])
    browser.execute_script(item["CategoryOnClick"])
    element = WebDriverWait(browser, 5).until(
        EC.presence_of_element_located((By.CSS_SELECTOR,catid))
    )
    subcategories = element.get_attribute("outerHTML")
    for subcategory in BeautifulSoup(subcategories,'lxml').find_all('a'):
        subcat = {}
        subcat['Category'] = item["Category"]
        subcat['CategoryOnClick'] = item["CategoryOnClick"]
        subcat['Subcategory'] = subcategory.text.strip('\"')
        subcat['SubcategoryOnClick'] = subcategory.attrs['onclick'][0:-14]
        subcatlist.append(subcat)
    subcategory_progress.next()
subcategory_progress.finish()
logger.info("Found %s Subcategories",len(subcatlist))

# build series list

# parallel process begins
subcatlist = list(np.array_split(subcatlist,int(nslice))[int(this_slice)-1])
serieslist = []
series_progress = Bar('Series', max=len(subcatlist))
for item in subcatlist: 
    for attempt in range(2):
        try:
            seriestable = ""
            rows = []
            browser.get(url)
            browser.execute_script(item["SubcategoryOnClick"])
            element = WebDriverWait(browser, 0.5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR,'#org-list .col-md-12 ul'))
                    )
            seriestable = element.get_attribute("outerHTML")
            rows = BeautifulSoup(seriestable,'lxml').find_all('a')[1:]
            for row in rows:
                series = {}
                series['Category'] = item["Category"]
                series['Subcategory'] = item["Subcategory"]
                series['Series'] = row.text.strip().split()[0]
                series['SeriesOnClick'] = row.attrs['onclick'][0:-14]
                if series:
                    serieslist.append(series)
            logger.debug("%s - %s - Found on Attempt %s - added %s items",subcatlist.index(item),item["Subcategory"],str(attempt),len(rows))
            time.sleep(0.4) #website didnt like pace, had to slow down
            series_progress.next()

        except (StaleElementReferenceException, TimeoutException) as e:
            continue
        except (NoSuchElementException) as e:
            logger.debug("%s - %s",type(e).__name__,subcatlist.index(item))
            series_progress.next()
            break
        else:
            break
    else:
        logger.debug("%s - %s - Tried %s attempts",subcatlist.index(item),item["Subcategory"],str(attempt+1))
        series_progress.next()
series_progress.finish()
logger.info("Found %s Series",len(serieslist))
serieslist = list(filter(None,serieslist))
df = pd.DataFrame(serieslist)
df.dropna(axis=0,how='all',inplace=True)
df.to_csv(serieslist_output,index=False,encoding='utf-8')

# build shallow pubslist
pubslist = []
pubs_progress = Bar('Pubs', max=len(serieslist))

for row in serieslist:
    index = serieslist.index(row)
    logger.debug("Beginning series %s | %s | %s",index,row["Subcategory"],row["Series"])
    
    for attempt in range(3):
        browser.get(url)
        browser.execute_script(row["SeriesOnClick"])

        try:
            dropdown = WebDriverWait(browser, 1).until(
                EC.presence_of_element_located((By.NAME,'data_length'))
            )
            Select(dropdown).select_by_value('100')
            tablength = int(Select(dropdown).first_selected_option.text)
            logger.debug('Clicked on Dropdown - Value %s',tablength)
        except UnexpectedAlertPresentException:
            handleAlert("dropdown")
            continue
        except (NoSuchElementException, StaleElementReferenceException, AttributeError, TypeError, TimeoutException) as e:
            logger.debug("No entries dropdown for %s - %s",type(e).__name__,index)
            break
        else:
            break
    else:
        logger.debug('Didnt find any regs')
        
    pages_remain = True
    tabs = 0
    while pages_remain:
        
        #scrape the Page
        try:
            regstable = browser.find_element_by_css_selector('#data tbody').get_attribute("outerHTML")
            regs = BeautifulSoup(regstable,'lxml').find_all('tr')
            logger.debug("Found %s regs",len(regs))
            for reg in regs:
                reg_index = regs.index(reg)
                products = reg.find_all('td')
                # annoying Series-but-empty-table condition 
                if products[0].has_attr('class') and products[0]['class'][0] == "dataTables_empty": 
                    logger.debug("%s - Datatable is empty",reg)
                    pages_remain = False
                else:
                    regdict = {}           
                    prodnum = products[0].find('a').text.strip('\"')
                    regdict['prodnum'] = prodnum
                    prodtitle = products[1].find('a').text.replace('"','')
                    regdict['prodtitle'] = prodtitle
                    regdict['Category'] = row["Category"]
                    regdict['Subcategory'] = row["Subcategory"]
                    regdict['Series'] = row["Series"]
                    logger.debug('Found %s - %s',prodnum,prodtitle)
                    if regdict:
                        pubslist.append(regdict)
        except (StaleElementReferenceException, NoSuchElementException, AttributeError, TypeError) as e:
            browser.get_screenshot_as_file("Summarytable-"+row["Series"]+"-"+str(time.time())+".png")
            logger.debug("2a:%s! - %s",type(e).__name__,reg_index)
        except UnexpectedAlertPresentException:
            handleAlert('regs')

        # hit the Next Page tab until done
        try:
            next_page = browser.find_element_by_xpath("//a[@class='paginate_button current']/following::a[1]")
            if next_page.get_attribute("innerHTML") == "Next": #then we've scraped the last tab
                logger.debug(" %s - %s regs scraped",index,tabs*100 + len(regs)) 
                pages_remain = False
            else:
                logger.debug("Clicking tab %s",next_page.get_attribute("text"))
                browser.execute_script("arguments[0].click();", next_page) #click to next tab in table
                tabs += 1
        except (NoSuchElementException, StaleElementReferenceException, AttributeError, TypeError) as e:
            logger.debug("2b: %s! - %s",type(e).__name__,index)
        except UnexpectedAlertPresentException:
            handleAlert('nexttab')
    pubs_progress.next()
    pubslist = list(filter(None,pubslist))
    df = pd.DataFrame(pubslist)
    df.dropna(axis=0,how='all',inplace=True)
    df.to_csv(pubslist_output,index=False,encoding='utf-8')
pubs_progress.finish()
logger.debug("Scraped %s pubs",str(len(pubslist)))

def search_scrape_details(prodnum,prodtitle,category="Default Category",subcategory="Default Subcategory",series=00):
    search_url = "https://www.e-publishing.af.mil/Product-Index/#/?view=search&keyword=" + prodnum + "&isObsolete=false&modID=449&tabID=131"
        
    for search_attempt in range(3):
        try:
            browser.get(search_url)
            regdict = {}
            prodlink = browser.find_element_by_xpath('//*[@id="data"]/tbody/tr/td[1]/a').get_attribute('href')
            summary = browser.find_element_by_xpath('//*[@id="data"]/tbody/tr/td[2]/a')
            browser.execute_script("arguments[0].click();", summary)
            logger.debug('Clicked product link for %s - %s',prodnum,prodtitle)
            time.sleep(1)
        except (NoSuchElementException, TimeoutException, StaleElementReferenceException) as e:
            logger.debug("Clicking %s - %s on Attempt %s didnt work",prodnum,prodtitle,str(search_attempt))
            continue
        else:
            break
    else:
        logger.debug('Something went wrong with the summary table for %s - %s',prodnum,prodtitle)

    # now scrape details table #
    for i in range(3):
        detailtable = ""
        try:
            element = WebDriverWait(browser, 3).until(
                EC.presence_of_element_located((By.CSS_SELECTOR,'.table-condensed.epubs-table > tbody'))
            )
            detailtable = element.get_attribute("outerHTML")
            details = BeautifulSoup(detailtable,'lxml').find_all('tr')
            if not details:
                logger.debug('details table was empty')
                break

        except (StaleElementReferenceException, NoSuchElementException, AttributeError, TimeoutException) as e:
            logger.debug('Detail table: %s! - %s attempt %s',type(e).__name__,prodnum,i)
            continue
        except UnexpectedAlertPresentException:
            handleAlert('details')
            continue
        else:
            for detail in details:                          
                variable = detail.find('th').text.strip()
                value = detail.find('td').text.replace('"','')
                regdict[variable] = value
            regdict['Category'] = category
            regdict['Subcategory'] = subcategory
            regdict['Series'] = series
            regdict['Prodlink'] = prodlink
            logger.debug('scraped %s details for %s',str(len(details)),prodnum)
            break
    else:
        logger.debug('The details table opened but something went wrong with scraping')
    
    # Now close details table #
    close_btn = browser.find_element_by_xpath('//button[text()="Close"]')
    browser.execute_script("arguments[0].click();", close_btn)
    logger.debug('Clicked close button')
    time.sleep(0.2)
    if regdict:
        return regdict


details_progress = Bar('Details',max=len(pubslist))
detaillist = []
for i, pub in enumerate(pubslist):
    logger.debug(i)
    logger.debug(pub)
    detail = search_scrape_details(pub['prodnum'],pub['prodtitle'],pub['Category'],pub['Subcategory'],pub['Series'])
    #detail['content'] = getPubFile(detail['Prodlink'])
    detaillist.append(detail)
    details_progress.next()
    if i % 20 == 0:
        detaillist = list(filter(None,detaillist))
        df = pd.DataFrame(detaillist)
        df.dropna(axis=0,how='all',inplace=True)
        df.to_csv(detaillist_output,index=False,encoding='utf-8')

details_progress.finish()
detaillist = list(filter(None,detaillist))
df = pd.DataFrame(detaillist)
df.dropna(axis=0,how='all',inplace=True)
df.to_csv(detaillist_output,index=False,encoding='utf-8')

browser.quit() 