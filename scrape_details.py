import pandas as pd
import numpy as np
import concurrent.futures
# !pip install requests
# !pip install bs4 
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

   

if __name__ == '__main__':

    tconst = 'tt5687612'
    page = 'companycredits'
    t1 = datetime.now()
    scrape_detail_page(tconst, page)
    t2 = datetime.now()
    duration = t2 - t1
    print(f'The {page} scraping for {tconst} took {round(duration.total_seconds(), 2)} seconds\n') 