from urllib.error import HTTPError
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options  
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, UnexpectedAlertPresentException, ElementNotVisibleException
import time, datetime, re, os, logging
import pandas as pd
import wget
from PyPDF2 import PdfFileReader

now = datetime.datetime.now()
output_dir = "scrape-results/{}-{}-{}-{}-{}-{}".format(now.year,now.month,now.day,now.hour,now.minute,now.second)

pubslist_output = 'pubslist.csv'
serieslist_output = 'serieslist.csv'

os.mkdir(output_dir)
os.chdir(output_dir)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
fh = logging.FileHandler('afi-scraper.log')
fh.setLevel(logging.DEBUG)
sh = logging.StreamHandler()
sh.setLevel(logging.DEBUG)
logger.addHandler(fh)
logger.addHandler(sh)

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
catlist = []
for category in BeautifulSoup(categories,'lxml').find_all('a'):
    cat = {}
    cat['CategoryOnClick'] = category.attrs['onclick'][0:-14]
    cat['Category'] = category.text
    catlist.append(cat)
logger.info('Found %s categories',len(catlist))

# build subcategory list
subcatlist = []
browser.get(url)
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
        subcat['Subcategory'] = subcategory.text
        subcat['SubcategoryOnClick'] = subcategory.attrs['onclick'][0:-14]
        subcatlist.append(subcat)
logger.info("Found %s Subcategories",len(subcatlist))

serieslist = []
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
                serieslist.append(series)
            logger.debug("%s - %s - Found on Attempt %s - added %s items",subcatlist.index(item),item["Subcategory"],str(attempt),len(rows))
            time.sleep(0.5) #website didnt like pace, had to slow down 

        except (StaleElementReferenceException, TimeoutException) as e:
            continue
        except (NoSuchElementException) as e:
            logger.warning("%s - %s",type(e).__name__,subcatlist.index(item))
            break
        else:
            break
    else:
        logger.warning("%s - %s - Tried %s attempts",subcatlist.index(item),item["Subcategory"],str(attempt+1))
logger.info("Found %s Series",len(serieslist))
df = pd.DataFrame(serieslist)
df.to_csv(serieslist_output,index=False,encoding='utf-8')

# build complete pubslist
pubslist = []
alerts = 0
excepts = 0

for row in serieslist:
    index = serieslist.index(row)
    logger.debug("Beginning series %s - %s - %s",index,row["Subcategory"],row["Series"])
    
    for attempt in range(3):
        browser.get(url)
        browser.execute_script(row["SeriesOnClick"])

        try:
            dropdown = WebDriverWait(browser, 1).until(
                EC.presence_of_element_located((By.NAME,'data_length'))
            )
            Select(dropdown).select_by_value('100')
            logger.debug('Clicked on Dropdown')
        except UnexpectedAlertPresentException:
            alertObj = browser.switch_to.alert
            logger.warning("1a: (Alert) %s",alertObj.text)
            alertObj.accept()
            alerts += 1
            continue
        except (NoSuchElementException, StaleElementReferenceException, AttributeError, TypeError, TimeoutException) as e:
            logger.warning("1a: No dropdown for %s - %s",type(e).__name__,index)
            excepts += 1
            break
        else:
            break
    else:
        logger.warning('Didnt find any regs')
        
    pages_remain = True
    tabs = 0
    while pages_remain:
        try:
            regstable = browser.find_element_by_css_selector('#data tbody').get_attribute("outerHTML")
            regs = BeautifulSoup(regstable,'lxml').find_all('tr')
            logger.debug("Found %s regs",len(regs))
            for reg in regs:
                reg_index = regs.index(reg)
                regdict = {}
                
                products = reg.find_all('td')
                # annoying Series-but-empty-table condition 
                if products[0].has_attr('class') and products[0]['class'][0] == "dataTables_empty": 
                    logger.warning(" 3a: %s Datatable is empty",reg)
                    pages_remain = False
                else:           
                    prodnum = products[0].find('a').text
                    prodlink = products[0].find('a').get('href')
                    prodtitle = products[1].find('a').text
                    logger.debug('Found %s - %s',prodnum,prodtitle)

                    # click on link to get summary table #
                    for link_attempt in range(3):
                        try:
                            link = browser.find_element_by_partial_link_text(prodtitle)
                            logger.debug("Found product link - now clicking")
                            browser.execute_script("arguments[0].click();", link)
                            logger.debug('Clicked product link for %s',prodtitle)
                            time.sleep(1)
                        except (NoSuchElementException, TimeoutException) as e:
                            logger.warning("Clicking %s on Attempt %s didnt work",prodtitle,str(link_attempt))
                            continue
                        else:
                            break
                    else:
                        logger.warning('Something went super wrong with clicking summary table link')

                    # now scrape details table #
                    for summary_attempt in range(3):
                        detailtable = ""
                        try:
                            element = WebDriverWait(browser, 3).until(
                                EC.presence_of_element_located((By.CSS_SELECTOR,'.table-condensed.epubs-table > tbody'))
                            )
                            detailtable = element.get_attribute("outerHTML")
                            details = BeautifulSoup(detailtable,'lxml').find_all('tr')
                            if not details:
                                logger.warning('details table was empty')
                                break
                            else:
                                logger.debug('details table has %s rows',len(details))
                                for detail in details:                          
                                    variable = detail.find('th').text
                                    value = detail.find('td').text
                                    regdict[variable] = value
                                regdict['Prodlink'] = prodlink
                                regdict['Category'] = row["Category"]
                                regdict['Subcategory'] = row["Subcategory"]
                                regdict['Series'] = row["Series"]
                                pubslist.append(regdict)
                                logger.debug('scraped %s details for %s',str(len(details)),prodnum)

                        except (StaleElementReferenceException, NoSuchElementException, AttributeError, TimeoutException) as e:
                            logger.warning('3b: %s! - %s',type(e).__name__,prodnum)
                            excepts+=1
                            continue
                        except UnexpectedAlertPresentException:
                            alertObj = browser.switch_to.alert
                            logger.warning('3b: Alert - %s - %s',alertObj.text,prodnum)
                            alertObj.accept()
                            alerts+=1
                            continue
                        else:
                            break
                    else:
                        logger.warn('Something went real wrong with summary table open/scraping/close')
                        

                    # Now close details table #
                    
                    close_btn = browser.find_element_by_xpath('//button[text()="Close"]')
                    browser.execute_script("arguments[0].click();", close_btn)
                    logger.debug('Clicked close button')
                    time.sleep(1)

                    element = WebDriverWait(browser, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR,'#data tbody'))
                        )
                    logger.debug('Closed %s',prodnum)

                    # resume scraping after details table closed #                  
                    #progress.value = int(index)
                    #progress.description = str(len(pubslist)) + " (" + str(int(index)/len(serieslist))[0:8] + "%)"
                    
        except (StaleElementReferenceException, NoSuchElementException, AttributeError, TypeError) as e:
            browser.get_screenshot_as_file("Except"+row["Series"]+".png")
            logger.warning("2a:%s! - %s",type(e).__name__,reg_index)
            excepts += 1
        except UnexpectedAlertPresentException:
            alertObj = browser.switch_to.alert
            logger.warning("2a: %s",alertObj.text)
            browser.get_screenshot_as_file("Alert"+row["Series"]+".png")
            alertObj.accept()
            time.sleep(1)
            browser.get(url)
            browser.execute_script(row["SeriesOnClick"])
            alerts += 1

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
            logger.warning("2b: %s! - %s",type(e).__name__,index)
            excepts += 1

        except UnexpectedAlertPresentException:
            alertObj = browser.switch_to.alert
            logger.warning("2b: %s",alertObj.text)
            time.sleep(1)
            alertObj.accept()
            alerts += 1
    df = pd.DataFrame(pubslist)
    df.to_csv(pubslist_output,index=False,encoding='utf-8') 

logger.debug("Scraped %s pubs: %s Alerts, %s Exceptions",str(len(pubslist)),alerts, excepts)
