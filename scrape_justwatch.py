import pandas as pd
import re
from datetime import date, timedelta, datetime
import os
import time
import random
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.firefox.service import Service




def check_recent_file(t, folder, directory):

    '''Checks whether there exists a recent file. 
    
    Params:
    -------
    t: str.
      The item to be checked. E.g., a platform.
      
    folder: str.
      The folder where the files are saved. E.g., New Content folder.
      
    directory: path.
      The complete path to the folder. 
      
    Returns:
    ---------
    True if there is a recent file and False otherwise. '''
    
    today = date.today()
    two_day_ago = today - timedelta(days=2) # adjust by need
    # Escape special characters in t
    escaped_t = re.escape(t)
    
    if folder == None:
        # Regular expression pattern to match files in the format "t_YYYY-MM-DD.csv"
        pattern = re.compile(rf'{t}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv')
    
    else:
        pattern = re.compile(rf'{escaped_t}_{folder}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv')
    
    # List all files in the specified directory
    for file_name in os.listdir(directory):
        match = pattern.match(file_name)
        if match:
            file_date_str = match.group(1)
            file_date = datetime.strptime(file_date_str, '%Y-%m-%d').date()
            if two_day_ago <= file_date <= today:
                return True  
    return False  


def scrape_justwatch_href_selenium(replace_str='new', platform='netflix'):

    '''
    This function scrapes Justwatch website to get hrefs of all available streaming platforms.
    
    Params:
    -------
    replace_str: str.
      'new' to collect what is new to the streaming platforms.

    platform: str.
      Default is 'netflix'. Can be changed to other platforms. This platform's href needs to be appended manually.
        
    
    Returns:
    --------
    None.
      A csv file is saved for each platform with the corresponding hrefs.
    '''

    current_path = os.getcwd()
    # define the subfolder name
    subfolder = replace_str[0].upper() + replace_str[1:] + '_Content'
    # create the subfolder if it doesn't exist
    subfolder_path = os.path.join(current_path, subfolder)

    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)

    if check_recent_file('justwatch_href', None, subfolder_path):
       print('URLs already retrieved!')
       return
    
    options = Options()
    options.set_preference('intl.accept_languages', 'en-US')
    options.binary_location = 'C:/Program Files/Mozilla Firefox/firefox.exe' # Replace with the path of Firebox!

    # user agent
    software_names = [SoftwareName.FIREFOX.value, SoftwareName.CHROME.value]
    operating_sys = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
    user_agent_rotator = UserAgent(software_names=software_names, operating_systems = operating_sys, limit=100)
    user_agent = user_agent_rotator.get_random_user_agent()
    options.add_argument('--user-agent={}'.format(user_agent))

    PATH = 'C:/Users/zhang/Downloads/geckodriver-v0.36.0-win32/geckodriver.exe' # Replace with the path of geckodriver!
    service = Service(executable_path=PATH)
    driver = webdriver.Firefox(options=options, service=service)
    driver.maximize_window()

    base_url = 'https://www.justwatch.com'
    url = base_url + '/us/provider/' + platform + '/' + replace_str
    driver.get(url)
    driver.implicitly_wait(20)    

    #########################################
    ### Get all the hrefs and save to csv ###
    #########################################
    hrefs = []
    providers = driver.find_elements(By.XPATH, "//div[@class='filter-bar-seo__provider-icon filter-bar-seo__provider-icon--provider']")
    for p in providers:
        hrefs.append(p.find_element(By.TAG_NAME, 'a').get_attribute('href'))

    hrefs.append(f'https://www.justwatch.com/us/provider/{platform}/new')
    df = pd.DataFrame({'href_justwatch':hrefs})

    output_file_name = 'justwatch_href_' + str(date.today()) + '.csv'
    output_file_path = os.path.join(subfolder_path, output_file_name)
    df.to_csv(output_file_path, index=False) 

    print('All platforms on Justwatch are saved.')
    driver.close()



def scrape_justwatch_content_change(replace_str, url):

    '''
    This function scrapes Justwatch website to get contents new to the streaming platforms.
    
    Params:
    -------
    replace_str: str.
      'new' to collect what is new to the streaming platforms.

    url: str.
      The url for each platform retrieved and saved by the scrape_justwatch_href_selenium func.
        
    
    Returns:
    --------
    None.
      A csv file 'platform_new_collect-date.csv' is saved for each platform with the hrefs and update dates for new contents.
    '''

    # Retrieve the platform from the url
    platform = re.search(r'\/provider\/(.*)\/new', url).group(1)

    # First check whether a recent file exists
    current_path = os.getcwd()
    # define the subfolder name
    subfolder = replace_str[0].upper() + replace_str[1:] + '_Content'
    # create the subfolder if it doesn't exist
    subfolder_path = os.path.join(current_path, subfolder)

    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)

    if check_recent_file(platform, replace_str, subfolder_path):
       print(f'recent Justwatch {replace_str} file for {platform} exists')
       return
    
    options = Options()
    options.set_preference('intl.accept_languages', 'en-US')
    options.binary_location = 'C:/Program Files/Mozilla Firefox/firefox.exe' # Replace with the path of Firefox!

    # user agent
    software_names = [SoftwareName.FIREFOX.value, SoftwareName.CHROME.value]
    operating_sys = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
    user_agent_rotator = UserAgent(software_names=software_names, operating_systems = operating_sys, limit=100)
    user_agent = user_agent_rotator.get_random_user_agent()
    options.add_argument('--user-agent={}'.format(user_agent))

    PATH = 'C:/Users/zhang/Downloads/geckodriver-v0.36.0-win32/geckodriver.exe' # Replace with the path of geckodriver!
    service = Service(executable_path=PATH)
    driver = webdriver.Firefox(options=options, service=service)
    driver.maximize_window()

    driver.get(url) 
    driver.implicitly_wait(30)    

    ##########################################################
    ### Scroll the page and wait for it to load dynamiclly ###
    ##########################################################
    scroll_count = 15 # Scroll how many times
     
    for _ in range(scroll_count):
        driver.execute_script("window.scrollBy(0, arguments[0]);", 1600)
        time.sleep(3)    
        try:
            end_of_page_tag = driver.find_element(By.TAG_NAME, 'h3').text
            if "You've reached the end of the list!" in end_of_page_tag or "Sorry, nothing to see here!" in end_of_page_tag:
                print('Reached the end of the list!')
                break
        except:
            pass    

    dates= []
    title_hrefs = [] 

    ############################
    ### Scrape with selenium ###
    ############################

    try:
        blocks = WebDriverWait(driver, 60).until(EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'timeline__timeframe timeline__timeframe')]")))
        # each block is a date
        for x in blocks:
            # the update date separated by '--'
            change_day = x.get_attribute('class').split('--')[1]

            # scroll the date block into view
            driver.execute_script("arguments[0].scrollIntoView(true);", x)

            # For each day, retrieve all the (hidden) contents
            # find the scrollable container
            container = x.find_element(By.CSS_SELECTOR, 'div.hidden-horizontal-scrollbar__items')

            while True:
                # scroll right
                driver.execute_script("arguments[0].scrollLeft += 500;", container)
                time.sleep(1)

                # check if the 'end' nav element is still visible
                # First there is only the 'end'. Once start strolling, 'start' will appear. Once all is loaded, 'end' disappears.
                try:
                    end_marker = x.find_element(By.CSS_SELECTOR, 'span.hidden-horizontal-scrollbar__nav.hidden-horizontal-scrollbar__nav--end')
                    if end_marker:
                        # still visible, keep scrolling
                        continue
                except NoSuchElementException:
                    # print(f'All updates on {change_day} loaded')
                    break
                    
            items = container.find_elements(By.XPATH, "./div[@class='horizontal-title-list__item']/a")
            dates.extend([change_day]*len(items))
            print(f'Updated {len(items)} titles on {change_day}')
            for item in items:
                title_hrefs.append(item.get_attribute("href"))

        df = pd.DataFrame({'date': dates, 'href': title_hrefs})
        output_file_name = platform + '_' + replace_str + '_' + str(date.today()) + '.csv'
        output_file_path = os.path.join(subfolder_path, output_file_name)
        df.to_csv(output_file_path, index=False) 
        print(f'{replace_str} titles for {platform} saved at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}\n')
    
    except Exception as e:
        print(e)

    finally:
        driver.close()




if __name__ == '__main__':

    ####################################################################
    ### Justwatch: Retrieve all URLs and illustrate with 2 platforms ###
    ####################################################################

    # Check whether a recent file with all hrefs already exists 
    scrape_justwatch_href_selenium()

    current_path = os.getcwd()
    subfolder = 'New_Content'
    folder = os.path.join(current_path, subfolder)
    prefix = 'justwatch_href'

    # Find the latest file that contains all the hrefs of platforms on Justwatch
    latest_file = max(
        (f for f in os.listdir(folder) if f.startswith(prefix) and f.endswith('.csv') and os.path.isfile(os.path.join(folder, f))),
        key=lambda f: os.path.getmtime(os.path.join(folder, f)),
        default=None)

    latest_path = os.path.join(folder, latest_file)
    print('Latest file:', latest_file)
    df = pd.read_csv(latest_path)

    # To illustrate, we can pick 2 platforms that do not have many new contents
    # To collect the full info, we would run:
    # urls = df['href_justwatch']
    urls = df['href_justwatch'][38:40]
    for i, url in enumerate(urls):
        print(f'Navigating to {url}...')
        if (i+1) %50 == 0: # If desired, could be commented out
            time.sleep(300)
        scrape_justwatch_content_change('new', url)


    
