import pandas as pd
import numpy as np
import concurrent.futures
import re
from datetime import date, datetime, timedelta
import os
import time
# !pip install selenium
import selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.proxy import Proxy, ProxyType
from selenium.common.exceptions import NoSuchElementException, TimeoutException, StaleElementReferenceException, WebDriverException
from selenium.webdriver.firefox.service import Service
# !pip install random_user_agent 
from random_user_agent.user_agent import UserAgent
from random_user_agent.params import SoftwareName, OperatingSystem



### Function to capture webpage errors ###
def check_h1_for_error(driver, substring, id_strings):

    '''Checks whether the page contains the error message, or has some attributes indicating the server/page was not found.
    
    Params:
    -------
    driver: WebDriver.
      The selenium driver used to locate the tag 'h1'. 
      
    substring: str.
      The string that indicates there is an error on the page, by checking the text under 'h1'.
      
    id_strings: str or list.
      The attribute(s) of a tag indicating the server or the page was not found.
      For the main page, the 'data-testid' should exist and for other pages, 'class' should exist under 'h1' tag.
      
    Returns:
    ---------
      True if there is an error, False if not. '''
    
    normal_error = False
    connection_error= False

    try: 
        # Locate the h1 tag (can be located without clicking the preference setting button)
        h1_element = WebDriverWait(driver, 50).until(EC.presence_of_element_located((By.TAG_NAME, 'h1')))
        # driver.find_element(By.TAG_NAME, 'h1')
        h1_text = h1_element.text
        if h1_element.get_attribute('data-testid') in id_strings or h1_element.get_attribute('class') in id_strings and h1_element.get_attribute('data-l10n-id') is None: # 'hero__pageTitle':
            return normal_error, connection_error
        # Check if the h1 text contains the specified substring
        # Some title contains 'error'
        if substring == h1_text: # 503 error
            print(f"'{substring}' was found.", flush=True)
            normal_error = True
            return normal_error, connection_error
        if h1_text == 'The connection has timed out': # substring != h1_text and h1_element.get_attribute('data-l10n-id') is not None: # connection error
            print(f"Connection Error '{h1_element.get_attribute('data-l10n-id')}' was found.", flush=True)
            connection_error = True
            return normal_error, connection_error
        if substring in h1_text and h1_element.get_attribute('data-l10n-id') is None: # 404 error
            print(f"Error '{h1_text}' was found.", flush=True)
            return normal_error, connection_error
        
    except TimeoutException:
        print(f'Cannot load the page', flush=True)
        connection_error = True
        return normal_error, connection_error
    
    except StaleElementReferenceException as e:
        print({e}, flush=True)
        normal_error = True
        return normal_error, connection_error
    
    except WebDriverException as e:
        print({e}, flush=True)
        normal_error = True
        return normal_error, connection_error
    
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}", flush=True)
        normal_error = True
        
    return normal_error, connection_error
    


### Function to scrape the number of winners and/or nominees of one category ###
def scrape_award_crew(driver, text_list, href_list, xpath):
    
    '''Scrapes the winners and/or nominees of one category under one award, e.g., the best leading character under Oscar,
    by retrieving both texts and hrefs,
    and the number of winnings and/or nominations will be used in the following functions. 
    
    Params:
    -------
    driver: WebDriver.
      The selenium driver used to locate the item, usually a category under a block of an award.
    
    text_list: list.
      The list that the persons are appended to. 
    
    href_list: list.
      The list that the personal unique ids by IMDB are appended to.
    
    xpath: XPath.
      The xpath that locates the category.
    
    Returns:
    --------
    None.
    '''
    
    try:
        # Grab the block of detailed info regarding the winner/nominee of the award
        crew = driver.find_elements(By.XPATH, xpath)
        crew_num = len(crew)
        if crew_num == 0:
            text_list.append(None)
            href_list.append(None)
        else:
            for p in crew:
                text_list.append(p.text)
                href = p.get_attribute('href')
                # append a list to the list
                href_list.append(re.findall(r'\/(n{1}m{1}\d+)', href)[0])
    except NoSuchElementException:
        text_list.append(None)
        href_list.append(None)
        


### Function to scrape the category, e.g., the best leading character; ###
### and the nomnination & award alias, e.g., 2023 Nominee Oscar        ###
def scrape_award_detail(driver, list_to_append, xpath, crew_num):

    '''Scrapes the detailed info regarding the category, nomination, award alias and notes.
    Specifically, the category is the unit of the driver. Nomination is in the format of '2023 Nominee award alias'.
    Notes are for the cases when there are ties with other persons in other titles.
    
    Params:
    -------
    driver: WebDriver.
      The selenium driver used to locate the item, usually a category under a block of an award.
    
    lists_to_append: list.
      The list to which the scraped element is appended .
      
    xpath_list: XPath.
      The XPath of the element.

    crew_num: int.
      The number of crew that are nominated or won this category.
      
    Returns:
    ---------
    None.
    '''
    
    try:
        elm = driver.find_element(By.XPATH, xpath)
        text = elm.text
        
    except NoSuchElementException:
        text = None

    if crew_num != 0:
        list_to_append.extend([text] * crew_num)
    else:
        list_to_append.append(text)



### Function to scrape notes such as Tied with another person in another title ###
def scrape_award_note(driver, text_list, href_list, xpath, crew_num):
    
    '''Scrapes with thom (person id) in which title (tconst) the title under investigation has a tie,
    by retrieving both texts and hrefs. 
    
    Params:
    -------
    driver: WebDriver.
      The selenium driver used to locate the item, usually a category under a block of an award.
    
    text_list: list.
      The list that the notes are appended to. 
    
    href_list: list.
      The list that the personal unique ids by IMDB and/or tconsts are appended to.
    
    xpath: XPath.
      The xpath that locates the category.

    crew_num: int.
      The number of crew that are nominated or won this category.
    
    Returns:
    --------
    None.
    '''
    
    try:
        # Grab the block of detailed info regarding the tie of the award
        # find_elements will return a list and there is no attribute find_elements
        note = driver.find_element(By.XPATH, xpath)
        hrefs = []
        # some notes contain only texts (no a tags)
        a_tags = note.find_elements(By.TAG_NAME, 'a')
        if a_tags:
            for a in a_tags:
                href = a.get_attribute('href')
                if href:
                    hrefs.append(re.findall(r'\/([t|n]{1}[t|m]{1}\d+)', href)[0])
            # concatenate all ids as one string
            ids = ','.join(hrefs)
        else:
            ids = None
        
        if crew_num != 0:
            text_list.extend([note.text] * crew_num)
            href_list.extend([ids] * crew_num)
        else:
            text_list.append(note.text)
            href_list.append(ids)
       
    except NoSuchElementException:
        if crew_num != 0:
            text_list.extend([None] * crew_num)
            href_list.extend([None] * crew_num)
        else:
            text_list.append(None)
            href_list.append(None)        




### Function to scrape the award page ###
def scrape_award(tconst):

    '''Scrapes the award page of one title and extracts first, the full name of the award,
    the unique id of the award (event id) and the number of categories;
    second, the info including the nominated and/or won category, 
    the number and identities of crew, and which place and/or tied with whom and which title.
    The results are appended to corresponding lists.
    
    Params:
    -------
    tconst: str.
      The unique id for each title on IMDB.
      
    Returns:
    ---------
    None. Outputs are saved to csv files. '''


    # The version (4.4.3) has a different way of setting params
    # Instances of options and service as well as the binary locaion of firefox
    # and the path to the webdriver (geckodriver) are needed
    options = Options()
    options.set_preference('intl.accept_languages', 'en-US')
    options.binary_location = 'C:/Program Files/Mozilla Firefox/firefox.exe' 
    options.page_load_strategy = 'eager'

    # user agent
    software_names = [SoftwareName.FIREFOX.value, SoftwareName.CHROME.value]
    operating_sys = [OperatingSystem.WINDOWS.value, OperatingSystem.LINUX.value]
    user_agent_rotator = UserAgent(software_names=software_names, operating_systems = operating_sys, limit=100)
    user_agent = user_agent_rotator.get_random_user_agent()
    options.add_argument('--user-agent={}'.format(user_agent))

    PATH = 'C:/Users/zhang/Downloads/geckodriver-v0.36.0-win32/geckodriver.exe'
    service = Service(executable_path=PATH)
    driver = webdriver.Firefox(options=options, service=service)

    url = 'https://www.imdb.com/title/' + tconst + '/awards/'
    
    driver.get(url) 
    driver.implicitly_wait(5) # tell the webdriver to wait for 10 seconds for the page to load

    ############################################
    ### Check for error and refresh the page ###
    ############################################
    
    # Capture any error message such as 503 error or server not found error
    normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text']) 

    initial_sleep_n = 3 # initial seconds to sleep when there is a normal error (not webdriver exception)
    initial_sleep_s = 30 # for special errors
    refresh_attempts = 0
  
    while normal_error and refresh_attempts<=10:
        print(f'### Pause {initial_sleep_n}s for {tconst} award at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}###', flush=True)
        time.sleep(initial_sleep_n)
        initial_sleep_n *= 2
        refresh_attempts += 1
        driver.refresh()
        print(f'refreshing {tconst} award...', flush=True)
            
        time.sleep(1)
        normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
        
        if refresh_attempts==11:
            print(f'Still error. Closing and skipping award {tconst}. Please check later!', flush=True)
            driver.close()
            break

    while connection_error and refresh_attempts<=5:
        print(f'### Connection error. Pause {initial_sleep_s}s for {tconst} award at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}###')
        time.sleep(initial_sleep_s)
        initial_sleep_s *= 2
        refresh_attempts += 1
        driver.refresh()
        print(f'refreshing {tconst} award...', flush=True)
        time.sleep(1)
        normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
        if refresh_attempts==6:
            print(f'Still connection error. Closing and skipping award {tconst}. Please check later!', flush=True)
            driver.close()
            break


    #############################
    ### Scrape the award page ###
    #############################

    print(f'Award page {tconst} ready!', flush=True) 

    # output file save to a subfolder
    current_path = os.getcwd()
    # define the subfolder name with the same date that the scraping started
    subfolder = 'Award'
    # create the subfolder if it doesn't exist
    subfolder_path = os.path.join(current_path, subfolder)
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)

    def save_award_gen_output(subfolder_path):
        df_gen = pd.DataFrame({'award_name': awards, 'award_id': event_ids, 'num_category': num_of_cats})
        output_file_name_gen = tconst + '_gen_' + str(date.today()) + '.csv'
        output_file_path_gen = os.path.join(subfolder_path, output_file_name_gen)
        df_gen.to_csv(output_file_path_gen, index=False)

    def save_award_detail_output(subfolder_path):
        df_out = pd.DataFrame({'award': award_alias, 'nomination': nominations, 'category': categories, 
                            'person': persons, 'person_id': person_ids, 'note': notes, 'note_id': note_ids})
        output_file_name = tconst + '_' + str(date.today()) + '.csv'
        # specify the output file path
        output_file_path = os.path.join(subfolder_path, output_file_name)
        df_out.to_csv(output_file_path, index=False)

    # Set initial empty list for each element
    awards = [] # award name
    nominations = [] # whether the person is a nominee or a winner
    award_alias = []
    categories = [] # specific award such as best leading character
    persons = []
    person_ids = []
    event_ids = []
    notes = []
    num_of_cats = [] # number of categories
    note_ids = []

    # Decline the preferences
    decline_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='reject-button']")))
    driver.execute_script("arguments[0].click();", decline_button)
    
    
    try:
        # Some titles do not have awards
        # Define the text that will be shown when the title has no award
        search_text = "It looks like we don't have any awards for this title yet."

        # Check if the text is present on the page
        if search_text in driver.page_source:
            raise NoSuchElementException
        
        error_text = "404 Error"
        if error_text in driver.find_element(By.TAG_NAME, 'h1').text:
            raise Exception
        
        # When there is sponsered info that takes a lot of space, scroll down to the h1 tag
        h1_tag = driver.find_element(By.XPATH, f"//h1[contains(@class, 'ipc-title__text')]")
        driver.execute_script("arguments[0].scrollIntoView();", h1_tag)

        
        ###############################################
        ### Grab the block of each individual award ###
        ###############################################
        
        block_award_names = driver.find_elements(By.XPATH, "//h3[contains(@class, 'ipc-title__text')]") 

        # Here, the number is of awards (blocks) and the value of 'num' later is of categories (winning and nominations)!
        num_sec = len(driver.find_elements(By.XPATH, "//section[@class='ipc-page-section ipc-page-section--base']"))

        for i in range(0, int(num_sec)): # number of nodes of categories (there are more 'h3' than awards)
            try:
                # Extract award name and event id
                award = block_award_names[i].text
                event = block_award_names[i].find_element(By.XPATH, "./span").get_attribute('id')
                awards.append(award)
                event_ids.append(event)
            except:
                awards.append(None)
                event_ids.append(None)
            print(f'Collected No. {i+1} award at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
                
        # Click the 'load more' button if there is one and count how many items for this event.
        # In the html, it shows that "some nodes were hidden". But on the page all is present and can be scraped.
        for x in event_ids:
            testid = 'sub-section-' + x
            while True:
                try: 
                    # Check first if there is a button before waiting to click in order to be time efficient
                    # since many sections do not have such a button
                    button = driver.find_element(By.XPATH, f"//div[@data-testid='{testid}']/ul/div/span/button")

                    load_more_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                        (By.XPATH, f"//div[@data-testid='{testid}']/ul/div/span/button")))
                    driver.execute_script("arguments[0].scrollIntoView();", load_more_button)
                    driver.execute_script("arguments[0].click();", load_more_button)

                except NoSuchElementException:
                    print(f"There is no 'Load More' button for {x}")
                    break
                
                except TimeoutException:
                    # There is no more clickable button, i.e., already clicked once and no more
                    print(f'Loaded more for {x}')
                    break

                except StaleElementReferenceException:
                    # Handle the case when there element becomes stale
                    continue

            num_of_category = len(driver.find_elements(By.XPATH, f"//div[@data-testid='{testid}']/ul/li"))
            num_of_cats.append(num_of_category)
        
        
        
        ###################################################### 
        ### Scrape each block of categories under an award ###
        ######################################################
            
        # Regardless of which award, one unit is a nomination/win record
        # the Category, Winner/Nominee & Note blocks do not always exist!

        # Grab the block of detailed info regarding the category of the award
    
        blocks = driver.find_elements(By.XPATH, "//div[@class='ipc-metadata-list-summary-item__tc']") 
       
        # Find the total number of nominations & awards 
        num = sum(int(i) for i in re.findall(r'\d+', driver.find_element(By.XPATH, "//div[@data-testid='awards-signpost']").text))
    
        for i in range(0, int(num)): 
            # Collect the crew info and count the number of nominees or winners
            scrape_award_crew(blocks[i], persons, person_ids, "./ul/li/a[@class='ipc-metadata-list-summary-item__li ipc-metadata-list-summary-item__li--link']")
            crew_num = len(blocks[i].find_elements(By.XPATH, "./ul/li/a[@class='ipc-metadata-list-summary-item__li ipc-metadata-list-summary-item__li--link']"))

            # Get nomination (eg 2023 Nominee / 2023 Winner)
            scrape_award_detail(blocks[i], nominations, "./a[@class='ipc-metadata-list-summary-item__t']", crew_num)

            # Get award alias (eg Oscar for Academy Awards, USA)
            scrape_award_detail(blocks[i], award_alias, "./a/span[@class='ipc-metadata-list-summary-item__tst']", crew_num)
            
            # Get category (eg best leading character)
            scrape_award_detail(blocks[i], categories, "./ul/li/span[contains(@class,'ipc-metadata-list-summary-item__li awardCategoryName')]", crew_num)

            # Get notes and person and title ids when available (eg Tied with Sandra Hüller for Anatomy of a Fall (2023) in 2nd place)
            scrape_award_note(blocks[i], notes, note_ids, "./div/span/div/div/div[@class='ipc-html-content-inner-div']", crew_num)

    except NoSuchElementException:
        num_of_cats.append(0)
        awards.append(None)
        event_ids.append(None)
        # Only save the general file to keep track and show that there is no award
        # But have to make sure the arrays are of the same length (appended list has len of 1 while others 0)
        save_award_gen_output(subfolder_path)
        print(f'{tconst} no award', flush=True)

    except Exception:
        num_of_cats.append('404')
        awards.append(None)
        event_ids.append(None)
        # 404 escaped the check at the beginning and only captured by checking the text of h1 tag
        save_award_gen_output(subfolder_path)
        print(f'404 error: {tconst} award', flush=True)

    finally:
        # If an exception occurs before this, the page will remain open
        driver.close()

    ###########################################
    ### Save output dataframes to csv files ###
    ###########################################
    
    # only save detailed files if they are not all empty (i.e., the title has awards)
    if not all(not lst for lst in [award_alias, nominations, categories, persons, person_ids]):
        # There are 2 files, one has more general info including the full name of the award,
        # the number of categories of each award and the unique id of each award;
        # another has detailed info including nominees and/or winners, categories and notes.
        save_award_gen_output(subfolder_path)
        save_award_detail_output(subfolder_path)
        print(f'Award files for {tconst} are saved!', flush=True)
            



if __name__ == '__main__':

    # Here, I use the series Fleabag as an example
    tconst = 'tt5687612'
    t1 = datetime.now()
    scrape_award(tconst)
    t2 = datetime.now()
    duration = t2 - t1

    print(f'The award scraping for {tconst} took {round(duration.total_seconds(), 2)} seconds\n')
