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



###########################################################
### Functions to check for error and get proxies ready ###
###########################################################

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
    

######################################################
### Functions to scrape the awards and nominations ###
######################################################

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
            print('Scraped crew!')

            # Get nomination (eg 2023 Nominee / 2023 Winner)
            scrape_award_detail(blocks[i], nominations, "./a[@class='ipc-metadata-list-summary-item__t']", crew_num)
            print('Scraped nominations!')

            # Get award alias (eg Oscar for Academy Awards, USA)
            scrape_award_detail(blocks[i], award_alias, "./a/span[@class='ipc-metadata-list-summary-item__tst']", crew_num)
            print('Scraped award alias!')
            
            # Get category (eg best leading character)
            scrape_award_detail(blocks[i], categories, "./ul/li/span[contains(@class,'ipc-metadata-list-summary-item__li awardCategoryName')]", crew_num)
            print('Scraped categories!')

            # Get notes and person and title ids when available (eg Tied with Sandra Hüller for Anatomy of a Fall (2023) in 2nd place)
            scrape_award_note(blocks[i], notes, note_ids, "./div/span/div/div/div[@class='ipc-html-content-inner-div']", crew_num)
            print('Scraped notes!')

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
            




#########################################################################
### Functions to scrape the detailed company credits and release info ###
#########################################################################
    
### Function to use regex to extract different parts of a string ###
def regex_extract(s):

    '''
    Extracts different parts of a string when there is no more than one pair of parentheses in each line. 
    There are 3 types of strings. 
    For the release dates, "Italy\nSeptember 1, 2023(Venice Film Festival)". 
    For the producer, "Warner Bros.\n(presents)" or "Warner Bros. (WB)\n(presents)". 
    For special effects & other companies, "BGI Supplies\n(BGI, ornithopters)".
    For sales representatives/ISA, "StudioCanal\n(World-wide, 1994)". 
    Note that content in parentheses is extracted by the date pattern.
    
    Params:
    -------
    s: str.
      The string that is being extracted.
      
    Returns:
    ---------
    Three parts separated by the new line and in the parentheses.'''

    # Extract the producer/special effects company, or the release country
    firm_pattern = r'(^(.*?))\s*\n' # everything before the new line and possibly space
    multi_line = re.search(r'\n', s)
    firm = re.search(firm_pattern, s).group(1) if multi_line else s
    
    # Match all characters before the first closing parenthesis (there could be numbers and dots)
    # to extract notes for producer or other companies, or the release place (e.g., film festival)
    # The content in the parentheses for producers are not needed (e.g, 'presents')
    parentheses_pattern = r'\(([^)]+)\)' 
    parentheses_match = re.search(parentheses_pattern, s, re.DOTALL)
    parentheses_content = parentheses_match.group(1) if parentheses_match else None
    
    # Match the date of release (only not None for releases, others such as ISA will be dropped)
    date_pattern = r'([A-Za-z]+\s*\d*,\s\d{4})'
    date_match = re.search(date_pattern, s)
    date = re.search(date_pattern, s).group(1) if date_match else None

    return firm, parentheses_content, date


def split_parentheses(s):

    '''
    Splits the string by the new line and parentheses.
    For the distributor, e.g., "Cinemundo\n(Portugal, 2024)(theatrical)". 
    '''
    
    try:
        lines = s.split('\n') # store the split result to make it more efficient
        firm = lines[0] if lines[0] else None
        
        second_line = lines[1] if len(lines) > 1 else None
        date = None
        parentheses_content = None
        
        if second_line:
            if ')(' in second_line:
                parts = second_line.split(')(')
                date = parts[0].strip('(') if parts[0] else None
                parentheses_content = parts[1].strip(')') if len(parts) > 1 else None
            else: # when there is only (country, year)
                date = second_line.strip('()')
        
    except:
        firm = 'Error'
        date = None
        parentheses_content = None

    return firm, parentheses_content, date



### Function to scrape producers, distributors, special effect and other companies & release info ###
def scrape_sub_section(driver, section):

    '''
    Scrapes the texts of all elements under one subsection on a page and 
    appends to different lists after splitting by funcs above. 
    The section could be about production, distribution, special effect companies or releases.
    
    Params:
    -------
    driver: : WebDriver.
      The selenium driver used to locate the item, usually a category under a block of an award.
    
    section: str.
      The section that is being scraped.
      
    Returns:
    ---------
    firms: list.
      The firms that are given credits or the country where the title is released.
    
    firm_ids: list.
      The unique id for each firm that is given credits. 
      Note that subsidiaries under a parent company has different firm ids.
    
    dates: list.
      The date that the title is released or the country and year when the title is distributed.
      Only available for some parameters (page='releaseinfo' or section='distribution').

    notes: list.
      The location that the title was released such as a film festival, or distributed such as in theater,
      or what the firm did specifically such as visual effects. '''

    # Set initial empty lists for each element
    firms = []
    firm_ids = []
    notes = []
    dates= []

    ##################################
    ### Click the load more button ###
    ##################################

    # Sometimes there are more than one buttons to load more, for such case clicking 'load all' returns incomplete list
    # So always click the load more button until there is none
    while True:
        try:
            load_more_button = WebDriverWait(driver, 2).until(EC.element_to_be_clickable(
                (By.XPATH, f"//div[@data-testid='sub-section-{section}']/ul/div/span[contains(@class, 'single-page-see-more')]/button")))
            driver.execute_script("arguments[0].click();", load_more_button)
            print('loaded more')
           
        except TimeoutException:
            print("No more 'Load More' button.")
            break

    ##############################
    ### Scrape the sub section ###
    ##############################
    
    app_firm = firms.append
    app_note = notes.append
    app_date = dates.append

    try:
        # Since all 'load more' buttons are already pressed, it should be quick to locate all elements
        # Otherwise, when there is no such block (distributor or production companies etc), it takes very long to collect info which is actually little
        blocks = driver.find_elements(By.XPATH, f"//div[@data-testid='sub-section-{section}']/ul/li")

        # WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.XPATH, f"//div[@data-testid='sub-section-{section}']/ul/li")))
        # Not all pages have special effect section
        # if blocks:
        print(f'Starting to collect info of {section}')
        for x in blocks:
            s = x.text
            # ID includes company id when the page is for company credits and release order otherwise (will be dropped)
            co_id = x.get_attribute('id')
            firm_ids.append(co_id)

            if section == 'distribution':
                firm, parentheses_content, date = split_parentheses(s)
            else:
                firm, parentheses_content, date = regex_extract(s)
            app_firm(firm)
            app_note(parentheses_content)
            app_date(date) 
            # print(f'Finish collecting info of {section}')
    except NoSuchElementException:
        print(f'No {section} on the page found!')
        pass
    # else:
    #     
    
    return firms, firm_ids, dates, notes



### Function to scrape a certain page ###
def scrape_detail_page(tconst, page):

    '''
    Scrapes the texts of all elements under all desired subsections on one page and 
    appends to different DataFrames afterwards. 
    The page could be about release info or about companies credits.
    
    Params:
    -------
    tconst: str.
      The unique id by IMDB of a title.

    page: str.
      The page that contains the relevant info, such as company credits or release info.

    Returns:
    ---------
    A DataFrame containing relevant info regarding release info or company credits.
    '''

    
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
    url = 'https://www.imdb.com/title/' + tconst + '/' + page + '/' 
    
    driver.get(url) 
    driver.implicitly_wait(10)

    # Capture any error message such as 503 error or server not found error
    initial_sleep = 3
    initial_sleep_s = 30
    refresh_attempts = 0
    normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
    while normal_error and refresh_attempts<=10:
        print(f'### Pause {initial_sleep}s for {tconst} {page} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}###', flush=True)
        time.sleep(initial_sleep)
        initial_sleep *= 2
        refresh_attempts += 1
        driver.refresh()
        print(f'refreshing {tconst} {page}...', flush=True)
        time.sleep(1)
        normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
    
        if refresh_attempts==11: 
            print(f'Still error. Closing {tconst} page {page}', flush=True)
            driver.close()
            break

    while connection_error and refresh_attempts<=5:
        print(f'### Connection error. Pause {initial_sleep_s}s for {tconst} {page} at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}###',
               flush=True)
        time.sleep(initial_sleep_s)
        initial_sleep_s *= 2
        refresh_attempts += 1
        driver.refresh()
        print(f'refreshing {tconst} {page}...', flush=True)
        time.sleep(1)
        normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
        if refresh_attempts==6:
            print(f'Still connection error. Closing {tconst} {page}', flush=True)
            driver.close()
            break
        
    print(f'Page {page} for {tconst} ready!', flush=True) 
    


    # Decline the preferences
    decline_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='reject-button']")))
    driver.execute_script("arguments[0].click();", decline_button)
    

    ### Function to build output path ###
    def build_output_path(subfolder, filestr, tconst):

        '''
        Builds the corresponding file path by joining the folder and string in the file name.
        
        Params:
        --------
        subfolder: str.
          The subfolder that the file is saved in.
          
        filestr: str.
          The string that is used to construct the file name, indicating which info it conains.

        tconst: str.
          The title id.

        Returns:
        ---------
        output_path: Path.
          The path that the output file will be saved in.
        '''


        # output file save to a subfolder
        current_path = os.getcwd()

        # create the subfolder if it doesn't exist
        subfolder_path = os.path.join(current_path, subfolder)
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)

        output_file_name = tconst + filestr + str(date.today()) + '.csv'

        # specify the output file path
        output_file_path = os.path.join(subfolder_path, output_file_name)
       
        return output_file_path


    # For the company credits, it does not make sense to load the page multiple times to extract different sections
    # Instead, when the driver is on the page, loop over sub sections

    # As the scrape_sub_section func already handles the NoSuchElementException,
    # here, I could directly use if-else to run the func.
    # But to keep track, I still use try-except to save the files without the info

    if page == 'releaseinfo':
        output_file_path_re = build_output_path('Release', '_release_', tconst)
        try:
            search_text = "It looks like we don't have any release date for this title yet."
            # Check if the text is present on the page
            if search_text in driver.page_source:
                print(f'No release info for {tconst}')
                raise NoSuchElementException
                
            error_text = "404 Error"
            if error_text in driver.find_element(By.TAG_NAME, 'h1').text:
                raise Exception

            # when there is sponsered info that takes a lot of space, scroll down to the h1 tag
            h1_tag = driver.find_element(By.XPATH, f"//h1[contains(@class, 'ipc-title__text')]")
            driver.execute_script("arguments[0].scrollIntoView();", h1_tag)

            firms, firm_ids, dates, notes = scrape_sub_section(driver, 'releases')

            df = pd.DataFrame({'country': firms, 'rel_id': firm_ids, 'date': dates, 'location': notes})            
            df.to_csv(output_file_path_re, index=False)
            print(f'Release file for {tconst} saved', flush=True)

        except NoSuchElementException:
            df = pd.DataFrame({'country': [None], 'rel_id': [None], 'date': [None], 'location': ['NoInfo']})
            df.to_csv(output_file_path_re, index=False)
            print(f'Release file for {tconst} saved. No release info.', flush=True)

        except Exception:
            df = pd.DataFrame({'country': ['404'], 'rel_id': ['404'], 'date': ['404'], 'location': ['404']})
            df.to_csv(output_file_path_re, index=False)
            print(f'404 error: Release file for {tconst}', flush=True)

        finally:
            driver.close()


    if page == 'companycredits':
        output_file_path_dis = build_output_path('Company Credit', '_distribution_', tconst)
        output_file_path_pro = build_output_path('Company Credit', '_pro_', tconst)
        
        sections = ['production', 'distribution', 'specialEffects', 'miscellaneous', 'sales']
        dfs = []
        try:
            search_text = "It looks like we don't have any company credits for this title yet."
            # Check if the text is present on the page
            if search_text in driver.page_source: # no need to handle the case when len(dfs)==0
                print(f'No company credits for {tconst}')
                raise NoSuchElementException
            
            error_text = "404 Error"
            if error_text in driver.find_element(By.TAG_NAME, 'h1').text:
                raise Exception

            # when there is sponsered info that takes a lot of space, scroll down to the h1 tag
            h1_tag = driver.find_element(By.XPATH, f"//h1[contains(@class, 'ipc-title__text')]")
            driver.execute_script("arguments[0].scrollIntoView();", h1_tag)

            for sec in sections:
                try:
                    firms, firm_ids, dates, notes = scrape_sub_section(driver, sec)
                    df = pd.DataFrame({'firm': firms, 'firm_id': firm_ids, 'country, yr': dates, 'note': notes})
                    dfs.append(df)
                    if sec == 'distribution':
                        dis = True
                except NoSuchElementException:
                    # not every sub section exists on the page
                    pass

            if len(dfs) == 1:
                if dis:
                    dfs[0].to_csv(output_file_path_dis, index=False)
                    print(f'Distribution file for {tconst} saved', flush=True)
                else:
                    dfs[0].to_csv(output_file_path_pro, index=False)
                    print(f'Production file for {tconst} saved', flush=True)
            if len(dfs)>1:
                # Append distribution to one df and all others to another concatenated df
                dfs[1].to_csv(output_file_path_dis, index=False)
                print(f'Distribution file for {tconst} saved')
                
                pd.concat([df for i, df in enumerate(dfs) if i != 1]).to_csv(output_file_path_pro, index=False)
                print(f'Production file for {tconst} saved', flush=True)

        except NoSuchElementException:
            df = pd.DataFrame({'firm': [None], 'firm_id': [None], 'country, yr': [None], 'note': ['NoInfo']})
            df.to_csv(output_file_path_pro, index=False)
            print(f'Company creds for {tconst} saved. No info.', flush=True)

        except Exception:
            df = pd.DataFrame({'firm': ['404'], 'firm_id': ['404'], 'country, yr': ['404'], 'note': ['404']})
            df.to_csv(output_file_path_re, index=False)
            print(f'404 error: Company creds for {tconst}', flush=True)
        
        finally:        
            driver.close()

            



#######################################################
### Functions to scrape the blocks on the main page ###
#######################################################
    
### Function to append to lists based on strings ###
def append_to_temp_list(s1, s2, lists_to_append, lists_to_check):

    '''
    Checks the string input 1 and append the string output 2 to the corresponding list.
    
    Params:
    -------
    s1: str.
      The input string that is checked.
      
    s2: str or NoneType. 
      The output string that is appended to the corresponding list. 
      
    lists_to_append: list.
      A list of lists that the output strings are appended to.
      
    lists_to_check: list.
      A list of strings that the input strings are compared to. 
      
    Returns:
    ---------
    None. 
    '''
    
    for (txt, li) in zip(lists_to_check, lists_to_append):
        # loop over the texts to append corresponding streaming, rent/buy or theatrical info to lists
        if s1 == txt:
            li.append(s2)


### Function to scrape the text of a subsection in a section on the main page ###
def scrape_main_subsec(driver, section, sub_sec, list_to_append):

    ''' Collects and appends the text of the sub section under the section on the main page to the list_to_append. '''
    
    try:
        block = driver.find_element(By.XPATH, f"//div[@data-testid='title-{section}-section']")
        if not block:
            raise NoSuchElementException
        
        if section == 'boxoffice': # only available for movies
            elm_loc = '/div/ul/li'
        else:
            elm_loc = '/div/ul/li/a'
        
        # elements under details block and techspecs block are under './li/a' but box office under './li/span'
        elements = block.find_elements(By.XPATH, f"./ul/li[@data-testid='title-{section}-{sub_sec}']{elm_loc}")
        if not elements:
            raise Exception
        temp_list = []
        if len(elements)>1:
            for elm in elements:
                temp_list.append(elm.text)
            list_to_append.append('; '.join(temp_list))
        else:
            for elm in elements:
                list_to_append.append(elm.text)

    except NoSuchElementException:
        list_to_append.append(None)
        print(f'No {sub_sec} info.')

    except Exception:
        block = driver.find_element(By.XPATH, f"//div[@data-testid='title-{section}-section']")
        # the data-testid becomes 'techspec' instead of 'techspecs' followed by an underscore
        if sub_sec == 'aspectratio':
            elements = block.find_elements(By.XPATH, f"./ul/li[@data-testid='title-{section[:-1]}_{sub_sec}']/div/ul/li/span")
        else:
            elements = block.find_elements(By.XPATH, f"./ul/li[@data-testid='title-{section[:-1]}_{sub_sec}']/div/ul/li/a")
        temp_list = []
        if len(elements)>1:
            for elm in elements:
                temp_list.append(elm.text)
            list_to_append.append('; '.join(temp_list))
        else:
            for elm in elements:
                list_to_append.append(elm.text)
        
    


### Functions to scrape the blocks on the main page ###
def scrape_watchlist(driver, tconst, list_watchlist):
    try:
        watchlist = driver.find_element(By.XPATH, "//div[@data-testid='tm-box-wl-count']") 
        list_watchlist.append(re.search(r'(\d+.*\d+[K|M]*)', watchlist.text).group(1))
        print(f'Watchlist for {tconst} scraped')
    except NoSuchElementException:
        list_watchlist.append(None)
        print(f'No one added {tconst} to Watchlists')


def scrape_score(driver, tconst, list_review, list_critic, list_meta):

    try:
        reviews = driver.find_elements(By.XPATH, "//span[@class='score']")

        if len(reviews) == 3:
            for r in reviews:
                if r.find_element(By.XPATH, "./following-sibling::span").text == 'User reviews':
                    list_review.append(r.text)
                elif r.find_element(By.XPATH, "./following-sibling::span").text == 'Critic reviews':
                    list_critic.append(r.text)
                elif r.find_element(By.XPATH, "./following-sibling::span").text == 'Metascore':
                    list_meta.append(r.text)
                    
        elif len(reviews) == 2:
            for r in reviews:
                if r.find_element(By.XPATH, "./following-sibling::span").text == 'User reviews':
                    list_review.append(r.text)
                elif r.find_element(By.XPATH, "./following-sibling::span").text == 'Critic reviews':
                    list_critic.append(r.text)
            list_meta.append(None)

        elif len(reviews) == 1:
            for r in reviews:
                if r.find_element(By.XPATH, "./following-sibling::span").text == 'User reviews':
                    list_review.append(r.text)
                elif r.find_element(By.XPATH, "./following-sibling::span").text == 'Critic reviews':
                    list_critic.append(r.text)
            for li in [list_review, list_critic]:
                if not li:
                    li.append(None)
            list_meta.append(None)
                    
        elif len(reviews) == 0:
            list_review.append(None)
            list_critic.append(None)
            list_meta.append(None)
        
        print('Reviews scraped')

    except NoSuchElementException:
        list_review.append(None)
        list_critic.append(None)
        list_meta.append(None)
        print(f'No Reviews for {tconst}')


def scrape_visual(driver, list_photo, list_video):
    try:
        list_video.append(driver.find_element(By.XPATH, "//a[@data-testid='hero__video-link']").get_attribute('aria-label').split(' ')[0])
        list_photo.append(driver.find_element(By.XPATH, "//a[@data-testid='hero__photo-link']").get_attribute('aria-label').split(' ')[0])

    except NoSuchElementException:
        list_photo.append(None)
        list_video.append(None)



def scrape_star(driver, star_list):
    try:
        temp_list = []
        # find the block for Stars (directors and writes have the same path except for the end, they have 'span' not 'a')
        block = driver.find_element(By.XPATH, "//li[@data-testid='title-pc-principal-credit']/a[contains(text(), 'Stars')]")
        
        stars = block.find_elements(By.XPATH, "../div/ul/li") # the 'div' tag is at the same level as the 'a' tag
        for s in stars:
            temp_list.append(s.text)
        star_list.append('; '.join(temp_list))
    except NoSuchElementException:
        star_list.append(None)


def scrape_air_date(driver, date_list):
    try:
        # find the block for Stars (directors and writes have the same path except for the end, they have 'span' not 'a')
        block = driver.find_element(By.XPATH, 
                                "//ul[@class='ipc-inline-list ipc-inline-list--show-dividers sc-d8941411-2 cdJsTz baseAlt']/li[contains(text(), 'Episode aired')]")
        date_list.append(block.text)
    except NoSuchElementException:
        date_list.append(None)


### Function to scrape the main page using the funcs above ###
def scrape_view(tconst):

    ''' 
    Scrapes the main page of the title and collects the streaming options,
    user and critic reviews and metascore if available as well as the number of
    graphical material including photos and videos. Also scrapes the info in the 
    Details and the Technical Specs blocks including languages, filming locations,
    aspect ratio, etc.
    
    Params:
    -------
    tconst: str.
    
    Returns:
    ---------
    data_dict: dict.
      The dictionary with all the info on the main page. '''
            
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
    user_agent_rotator = UserAgent(software_names=software_names, operating_systems=operating_sys, limit=100)
    user_agent = user_agent_rotator.get_random_user_agent()
    options.add_argument('--user-agent={}'.format(user_agent))
   
    PATH = 'C:/Users/zhang/Downloads/geckodriver-v0.36.0-win32/geckodriver.exe'
    service = Service(executable_path=PATH)
    driver = webdriver.Firefox(options=options, service=service)
    url = 'https://www.imdb.com/title/' + tconst + '/'

    # Set initial empty list for each element
    tconsts = []
    tconsts.append(tconst)
    theaters = [] # if theater, yes 
    prices = [] # if rent/buy, how much
    seasons = [] # if streaming, which season available
    streaming_providers = [] # arial label
    rent_providers = [] # arial label
    theater_providers = [] # arial label
    

    num_watchlists = [] # how many people added to their watch lists
    num_reviews = [] # number of user reviews
    num_critics = [] # number of critic reviews
    metascores = [] # if available

    num_photos = []
    num_videos = []

    origin_countries = [] # countries of origin 
    languages = [] # languages
    filming_locs = [] # fimling locations

    # Box office section on the main page
    budgets = [] # Budget
    open_americas = [] # Opening weekend US & Canada
    gross_americas = [] # Gross US & Canada
    gross_intls = [] # gross worldwide

    # Technical specs section on the main page
    colors = [] 
    soundmix = [] 
    aspect_ratios = [] # Aspect ratio

    stars = [] # main actors and actresses
    air_dates = [] # the date episodes were aired


    data_dict = {'tconst': tconsts, 'theater': theaters, 'price': prices, 'season': seasons, 
                'streaming_provider': streaming_providers, 'rent_provider': rent_providers, 'num_watchlist': num_watchlists, 
                'num_review': num_reviews, 'num_critic': num_critics, 'metascore': metascores,
                'num_photo': num_photos, 'num_video': num_videos, 'origin': origin_countries, 'language': languages,
                'filming_loc': filming_locs, 'budget':budgets, 'open_boxoffice_america': open_americas,
                'gross_boxoffice_america': gross_americas, 'gross_boxoffice_world':gross_intls, 'color':colors,
                'soundmix': soundmix, 'aspect_ratio':aspect_ratios, 'star':stars, 'air_date': air_dates }

    
    driver.get(url) 
    driver.implicitly_wait(10) 
    
    # Capture any error message such as 503 error or server not found error
    normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
    initial_sleep = 3 
    initial_sleep_s = 30
    refresh_attempts = 0
    while normal_error and refresh_attempts<=10:
        print(f'### Pause {initial_sleep}s for {tconst} main page at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}###', flush=True)
        time.sleep(initial_sleep)
        initial_sleep *= 2
        refresh_attempts += 1
        driver.refresh()
        print(f'refreshing {tconst} main page...', flush=True)
        time.sleep(1)
        normal_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
   
        if refresh_attempts==11: 
            driver.close()
            print(f'Main page {tconst} still error. Closing and skipping. Please check later!', flush=True)
            break
    
    while connection_error and refresh_attempts<=5:
        print(f'### Connection error. Pause {initial_sleep_s}s for {tconst} main page at {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}###',
               flush=True)
        time.sleep(initial_sleep_s)
        initial_sleep_s *= 2
        refresh_attempts += 1
        driver.refresh()
        print(f'refreshing {tconst} main page...', flush=True)
        time.sleep(1)
        normal_error, connection_error = check_h1_for_error(driver, 'Error', ['hero__pageTitle', 'ipc-title__text'])
        if refresh_attempts==6:
            print(f'Still connection error. Closing {tconst} main page. Please check later!', flush=True)
            driver.close()
            break
    
    print(f'Main page {tconst} ready!', flush=True)


    # Decline the preferences
    decline_button = WebDriverWait(driver, 30).until(EC.element_to_be_clickable((By.XPATH, "//button[@data-testid='reject-button']")))
    driver.execute_script("arguments[0].click();", decline_button)

    try:
        # when there is sponsered info that takes a lot of space, scroll down to the h1 tag
        h1_tag = driver.find_element(By.XPATH, f"//h1[@data-testid='hero__pageTitle']")
        driver.execute_script("arguments[0].scrollIntoView();", h1_tag)
        
        ##############################################
        ### The block containing all watch options ###
        ##############################################

        lists_dict = {'RENT/BUY': rent_providers, 'STREAMING': streaming_providers, 'IN THEATERS': theater_providers}
        check_list = ['IN THEATERS', 'STREAMING', 'RENT/BUY']
        # temp list to append all texts under the first block about watching options
        temp_list = []
        # the parent div of streaming options has a sibling, which contains the watch lists info
        stream_options = WebDriverWait(driver, 60).until(EC.presence_of_all_elements_located(
            (By.XPATH, "//div[@data-testid='tm-box-wb-overflow']/div/div")))

        for opt in stream_options:
            temp_list.append(opt.text)
            for key, lst in lists_dict.items():
                if key == opt.text:
                    print(f'Investigating key {key}...')
                    # the 'div' where the text is e.g. 'streaming' has no tag 'a', but rather its next sibling 'div'
                    # But when there is no text under the icon, NoSuchElementException will be raised
                    # So i go back to parent tag and then look for the final a tag
                    lst.append(opt.find_element(By.XPATH, "../div/div/a").get_attribute('aria-label'))

                    
        for key in check_list:
            # if the list is empty (for a round), append None
            if not lists_dict[key]:
                lists_dict[key].append(None)
                
        for i in range(0, int(len(temp_list)/2)): # to avoid the type error: float cannot be interpreted as int
            # Check the 1st, 3rd and 5th string and append the 2nd, 4th and 6th accordingly
            append_to_temp_list(temp_list[i*2], temp_list[i*2+1], [theaters, seasons, prices], check_list)
        for x in list(set(check_list) - set(temp_list[0::2])):
            # If there are only 4 results, then one watching option is not available
            # e.g., if there are streaming and rent/buy options, then append None to theater list
            append_to_temp_list(x, None, [theaters, seasons, prices], check_list)

        print(f'Streaming options for {tconst} scraped')


        #######################################################################
        ### The block containing how many people added to their watch lists ###
        #######################################################################
        scrape_watchlist(driver, tconst, num_watchlists)

        #######################################################################
        ### The block containing how many people made reviews and metascore ###
        #######################################################################
        scrape_score(driver, tconst, num_reviews, num_critics, metascores)
        
        ######################################################################
        ### The block containing the number of videos and photos available ###
        ######################################################################

        scrape_visual(driver, num_photos, num_videos)

        #######################################################
        ### The details block and the technical specs block ###
        #######################################################
        
        scrape_main_subsec(driver, 'details', 'origin', origin_countries)
        scrape_main_subsec(driver, 'details', 'languages', languages)
        scrape_main_subsec(driver, 'details', 'filminglocations', filming_locs)
        scrape_main_subsec(driver, 'boxoffice', 'budget', budgets)
        scrape_main_subsec(driver, 'boxoffice', 'openingweekenddomestic', open_americas)
        scrape_main_subsec(driver, 'boxoffice', 'grossdomestic', gross_americas)
        scrape_main_subsec(driver, 'boxoffice', 'cumulativeworldwidegross', gross_intls)
        scrape_main_subsec(driver, 'techspecs', 'color', colors)
        scrape_main_subsec(driver, 'techspecs', 'soundmix', soundmix)
        scrape_main_subsec(driver, 'techspecs', 'aspectratio', aspect_ratios)

        #######################
        ### The stars block ###
        #######################
        scrape_star(driver, stars)

        ##########################
        ### The air date block ###
        ##########################
        scrape_air_date(driver, air_dates)

        
    except TimeoutException: 
        print(f'No streaming option for {tconst}')
        for li in [theaters, prices, seasons, streaming_providers, rent_providers]:
            li.append(None)

    except NoSuchElementException: 
        print(f'No watching option for {tconst}')
        for li in [theaters, prices, seasons, streaming_providers, rent_providers]:
            li.append('404')

    finally:
        driver.close()

    for key in data_dict:
        if not data_dict[key]:  # Check if the value corresponding to the key is an empty list
            data_dict[key].append(None)
    return data_dict





############################################################################
### Functions to save the files and to be used in the threading executor ###
############################################################################

### Function to check whether there is a file obtained less than 2 weeks ###
def check_recent_file(t, folder, directory):

    '''
    Checks wehther there exists a recent file regarding a title's awards, release and company credit info. 
    
    Params:
    -------
    t: str.
      The tconst of the title.
      
    folder: str.
      The string in each file name, but not the exact subfolder name. 
      E.g., the subfolder is 'Release' while the file name contains 'release'.
      
    directory: path.
      The path to the subfolder. 
      
    Returns:
    --------
    True if there is a recent file and False otherwise. '''
    
    today = date.today()
    two_week_ago = today - timedelta(weeks=2)
    # Escape special characters in t
    escaped_t = re.escape(t)
    
    if folder == None:
        # Compile the RE pattern to a RE object to match files in the format 'tconst_YYYY-MM-DD.csv'
        pattern = re.compile(rf'{t}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv')
    
    else:
        pattern = re.compile(rf'{escaped_t}_{folder}_(\d{{4}}-\d{{2}}-\d{{2}})\.csv')
    
    # List all files in the specified directory
    for file_name in os.listdir(directory):
        match = pattern.match(file_name)
        if match:
            file_date_str = match.group(1)
            file_date = datetime.strptime(file_date_str, '%Y-%m-%d').date()
            if two_week_ago <= file_date <= today:
                return True  # Recent file found
    return False  # No recent file found



def check_recent_batch(i, folder, directory):

    '''
    Checks wehther there exists a recent file regarding a title's info on the main page. 
    
    Params:
    -------
    i: int.
      The index of the batch.
      
    folder: str.
      The string in each file name, but not the exact subfolder name. 
      E.g., the subfolder is 'Release' while the file name contains 'release'.
      
    directory: path.
      The path to the subfolder. 

    Returns:
    --------
    True if there is a recent file and False otherwise. '''
    
    today = date.today()
    two_week_ago = today - timedelta(weeks=2)
    
    pattern = re.compile(rf'{folder}_\({i+1}\)_(\d{{4}}-\d{{2}}-\d{{2}})\.csv')
    
    # List all files in the specified directory
    for file_name in os.listdir(directory):
        match = pattern.match(file_name)
        if match:
            file_date_str = match.group(1)
            file_date = datetime.strptime(file_date_str, '%Y-%m-%d').date()
            if two_week_ago <= file_date <= today:
                return True  
    return False  


### Function to check whether the output file for award exists and if not, scrape and save ###
def save_award_file(t):
    # output file save to a subfolder
    current_path = os.getcwd()
    # define the subfolder name with the same date that the scraping started
    subfolder = 'Award'
    # create the subfolder if it doesn't exist
    subfolder_path = os.path.join(current_path, subfolder)
    if check_recent_file(t, 'gen', subfolder_path):
        # for no award titles, there is only gen file
        print(f'A recent {t} file exists.', flush=True)
        return

    scrape_award(t)
    

### Function to check whether the output file for detailed info exists and if not, scrape and save ###
def save_detail_file(t):
    current_path = os.getcwd()
    for txt in ['releaseinfo', 'companycredits']:
        subfolder_release = 'Release'
        subfolder_credit = 'Company credit'

        # create the subfolder if it doesn't exist
        subfolder_path_release = os.path.join(current_path, subfolder_release)
        subfolder_path_credit = os.path.join(current_path, subfolder_credit)
        if check_recent_file(t, 'release', subfolder_path_release) and check_recent_file(t, 'pro', subfolder_path_credit):
            # use 'and' to check whether the collected info is complete (with production, unnecessary to include others such as distribution)
            print(f'A recent {t} file for details exists.', flush=True)
            return
        
        scrape_detail_page(t, txt)


### Function to check whether the file for the i-th batch of main pages exists and if not, scrape and save ###
def save_main_file(i, tconsts, dicts, result_dict):

    '''
    First, checks whether the recent file for the i-th batch of the main pages exists. 
    If not, use the thread pool executor to scrape and append the result dictionaries to a list.

    Params:
    -------
    i: int.
      The index of the batch.

    tconsts: list.
      A list of tconsts of the titles.

    dicts: list.
      A list of dictionaries obtained from the func scrape_view.

    result_dict: dict.
      A dictionary containing the data to generate the saved main page file.

    Returns:
    --------
    empty_ids: list.
      A list of title IDs (tconsts) without watching options.

    '''

    subfolder = 'Main'
    subfolder_path = os.path.join(os.getcwd(), subfolder)
    if not os.path.exists(subfolder_path):
        os.makedirs(subfolder_path)
    output_file_name = 'main_' +'(' + str(i+1) + ')_' + str(date.today()) + '.csv'
    # specify the output file path
    output_file_path = os.path.join(subfolder_path, output_file_name)
    if check_recent_batch(i, 'main', subfolder_path):
        print(f'Main page file for {i+1}th batch exists!', flush=True)
        return

    def run_and_append(t):
        dicts.append(scrape_view(t))

    def update_dict(dicts, result_dict):
        for d in dicts:
            for key, value in d.items():
                if key not in result_dict:
                    result_dict[key] = value  # Instead of [value]
                else:
                    result_dict[key].extend(value)  # Instead of append.()

    with concurrent.futures.ThreadPoolExecutor() as executor:
        executor.map(run_and_append, tconsts)

    update_dict(dicts, result_dict)
    pd.DataFrame(result_dict).to_csv(output_file_path, index=False)
    print(f'Main file for {i+1} saved.', flush=True)

    empty_ids = [tconst for tconst, streaming_provider, rent_provider 
                 in zip(result_dict['tconst'], result_dict['streaming_provider'], result_dict['rent_provider']) 
                 if streaming_provider is None and rent_provider is None]
    return empty_ids





if __name__ == '__main__':
    
    for i, chunk in enumerate(pd.read_csv('imdb_merged.csv', usecols=['tconst', 'title_yr'], chunksize=20)):
        # First make sure the col yr is integer and Nan for invalid parsing
        if (chunk['title_yr'].dtype != np.float64 or chunk['title_yr'].dtype != np.int64):
            chunk['title_yr'] = pd.to_numeric(chunk['title_yr'], errors='coerce', downcast='integer') 

        # If derised, we could limit the titles to only the recent ones, e.g., those after 2024
        title_ids = chunk[chunk['title_yr']>=2024]['tconst'].unique()
        if len(title_ids) == 0:
            print(f'There is no title in No.{i+1}th batch later than 2024')
            continue
        else:
            print(f'No.{i+1}th batch has {len(title_ids)} titles')

            t1 = datetime.now()
            print(f'Scraping the {i+1}th batch at {t1.strftime("%Y-%m-%d %H:%M:%S")}...')
            dicts = []
            result_dict = {}
            try:
                no_stream_tconsts = save_main_file(i, title_ids, dicts, result_dict)
                if no_stream_tconsts is None:
                    no_stream_tconsts = [] 
            except: 
                print(f'No.{i+1}th batch main page error!')
                no_stream_tconsts = [] # skip the main file and scrape all details for this batch

            # To save time, do not scrape the title if there is no streaming option
            title_ids_detail = list(set(title_ids) - set(no_stream_tconsts))
            # print(title_ids_detail) if title_ids_detail else print('No title has streaming option')


            if title_ids_detail:
                print(title_ids_detail)

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    executor.map(save_award_file, title_ids_detail)
                    executor.map(save_detail_file, title_ids_detail)

                t2 = datetime.now()
                duration = t2 - t1
                print(f'The {i+1}th batch took {round(duration.total_seconds(), 2)} seconds\n') 
                break # to continue running for other chunks, comment this out 
            else:
                print('No title has streaming option')
                

            

           

        

            
    

    

