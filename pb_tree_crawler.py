import os
import time
import json
import csv
from urllib.parse import urljoin
from dotenv import load_dotenv
import glob

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException
from selenium.webdriver.chrome.options import Options

# ANSI escape codes for colors
COLOR_BLUE = "\033[96m" # Main profile, important headers
COLOR_GREEN = "\033[92m" # Data points
COLOR_YELLOW = "\033[93m" # Links
COLOR_ORANGE = "\033[33m" # Warnings, empty data
COLOR_RED = "\033[91m"   # Errors
COLOR_RESET = "\033[0m"

load_dotenv()

class WebScraper:
    
    def __init__(self, headless=False):
        """Initialize the web scraper with Chrome driver"""
        self.options = Options()

        if headless:
            self.options.add_argument('--headless')
        #ignores ssl errors lol
        self.options.add_argument('--ignore-certificate-errors')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu') # Keep this as it often helps with stability
        self.options.add_argument('--window-size=1920,1080')
        
        # Add logging preferences to capture browser logs
        self.options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
        
        # --- REVISED: Very Explicit and Simple Profile Path ---
        self.scraper_profile_dir = r"C:\temp\chrome_scraper_data" # Using raw string for backslashes

        # Ensure the directory exists
        if not os.path.exists(self.scraper_profile_dir):
            try:
                os.makedirs(self.scraper_profile_dir, exist_ok=True)
                print(f"{COLOR_BLUE}Created new scraper profile directory: {self.scraper_profile_dir}{COLOR_RESET}")
            except Exception as e:
                print(f"{COLOR_RED}ERROR: Could not create scraper profile directory {self.scraper_profile_dir}. Check permissions. Error: {e}{COLOR_RESET}")
                raise # Re-raise to stop if directory cannot be created

        self.options.add_argument(f"--user-data-dir={self.scraper_profile_dir}")
        # --------------------------------------------------------------------------

        chromedriver_path = "C:/Users/QLindse25/Downloads/chromedriver-win64/chromedriver-win64/chromedriver.exe"
        service = Service(chromedriver_path)

        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.wait = WebDriverWait(self.driver, 5) # Default main wait time set to 5 seconds
        self.long_wait = WebDriverWait(self.driver, 10) # Longer wait for specific elements
        self.logged_in = False
        self.base_url = None
        
        # New attributes for recursive scraping
        self.visited_urls = set()
    
    def login(self, login_url, username, password, 
              username_selector="input[name='email']", 
              password_selector="input[name='password']",
              login_button_selector="input[type='submit']",
              success_indicator=None):
        """
        Login to a website
        
        Args:
            login_url: URL of the login page
            username: Username/email
            password: Password
            username_selector: CSS selector for username field
            password_selector: CSS selector for password field
            login_button_selector: CSS selector for login button
            success_indicator: CSS selector to confirm successful login
        """
        try:
            print(f"{COLOR_BLUE}Navigating to login page: {login_url}{COLOR_RESET}")
            self.driver.get(login_url)
            self.base_url = login_url # Capture base URL during login
            
            # Wait for login form to load (using main wait)
            username_field = self.wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, username_selector))
            )
            password_field = self.driver.find_element(By.CSS_SELECTOR, password_selector)
            
            # Clear fields and enter credentials
            username_field.clear()
            username_field.send_keys(username)
            
            password_field.clear()
            password_field.send_keys(password)
            
            # Submit the form
            try:
                login_button = self.driver.find_element(By.CSS_SELECTOR, login_button_selector)
                login_button.click()
            except NoSuchElementException:
                # Try submitting with Enter key if button not found
                password_field.send_keys(Keys.RETURN)
            
            # Wait for page to load after login
            print(f"{COLOR_BLUE}Waiting for post-login redirect...{COLOR_RESET}")
            time.sleep(10) # Give extra time for redirects and JS to load
            
            # Check for successful login (using main wait)
            if success_indicator:
                try:
                    self.wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, success_indicator))
                    )
                    print(f"{COLOR_BLUE}Login successful! Success indicator found.{COLOR_RESET}")
                    self.logged_in = True
                    return True
                except TimeoutException:
                    print(f"{COLOR_ORANGE}Login may have failed - success indicator not found after full login.{COLOR_RESET}")
                    return False
            else:
                # Fallback: Check if we're redirected away from login page
                current_url = self.driver.current_url
                if current_url != login_url and "login" not in current_url: # Added check for "login" in URL
                    print(f"{COLOR_BLUE}Login appears successful (redirected from login page).{COLOR_RESET}")
                    self.logged_in = True
                    return True
                else:
                    print(f"{COLOR_ORANGE}Login may have failed - still on login page or redirected back to login.{COLOR_RESET}")
                    return False
                    
        except TimeoutException:
            print(f"{COLOR_RED}Timeout waiting for login form to load.{COLOR_RESET}")
            return False
        except Exception as e:
            print(f"{COLOR_RED}Error during login: {e}{COLOR_RESET}")
            return False
    
    def check_login_status(self, logged_in_indicator=None):
        """Check if still logged in by looking for a specific element."""
        if logged_in_indicator:
            print(f"{COLOR_BLUE}Checking login status using indicator: {logged_in_indicator}{COLOR_RESET}")
            try:
                # Use a short wait to quickly check for the indicator's presence
                WebDriverWait(self.driver, 5).until( # Shorter wait for just a check
                    EC.presence_of_element_located((By.CSS_SELECTOR, logged_in_indicator))
                )
                print(f"{COLOR_BLUE}Login indicator '{logged_in_indicator}' found. User appears logged in.{COLOR_RESET}")
                self.logged_in = True
                return True
            except TimeoutException:
                print(f"{COLOR_ORANGE}Login indicator '{logged_in_indicator}' NOT found. User does NOT appear logged in.{COLOR_RESET}")
                self.logged_in = False
                return False
        # If no specific indicator is provided, we can't definitively check, assume not logged in.
        print(f"{COLOR_ORANGE}No specific logged-in indicator provided for status check. Assuming not logged in.{COLOR_RESET}")
        self.logged_in = False
        return False
    
    def logout(self, logout_url=None, logout_selector=None):
        """Logout from the website"""
        try:
            if logout_url:
                self.driver.get(logout_url)
            elif logout_selector:
                logout_element = self.driver.find_element(By.CSS_SELECTOR, logout_selector)
                logout_element.click()
            
            self.logged_in = False
            print(f"{COLOR_BLUE}Logged out successfully{COLOR_RESET}")
            return True
            
        except Exception as e:
            print(f"{COLOR_RED}Error during logout: {e}{COLOR_RESET}")
            return False
    
    def scrape_protected_content(self, url, content_selector=".content", logged_in_indicator=None):
        """Scrape content that requires login"""
        print(f"{COLOR_BLUE}Navigating to protected URL: {url}{COLOR_RESET}")
        self.driver.get(url)
        time.sleep(.4) # Give page time to load after navigation

        # Crucial check: Verify login status *after* navigating to the protected page
        if logged_in_indicator:
            if not self.check_login_status(logged_in_indicator):
                print(f"{COLOR_ORANGE}Session expired or invalid after navigating to protected content. Cannot scrape.{COLOR_RESET}")
                self.logged_in = False # Reset login status if check fails
                return []
        elif not self.logged_in: # Fallback if no specific indicator, but internal state is false
            print(f"{COLOR_ORANGE}Not logged in (internal state). Please login first to scrape protected content.{COLOR_RESET}")
            return []
        
        try:
            print(f"{COLOR_BLUE}Waiting for content element with selector: {content_selector}{COLOR_RESET}")
            # Use presence_of_element_located to get the main container element
            main_content_element = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, content_selector))
                )
            
            content_data = []
            content_data.append({
                'text': main_content_element.text, # This will get all visible text within the section
                'html': main_content_element.get_attribute('outerHTML'), # This gets the full HTML of the section
                'url': url
            })
            
            print(f"{COLOR_BLUE}Scraped content from '{content_selector}'.{COLOR_RESET}")
            return content_data
            
        except TimeoutException:
            print(f"{COLOR_ORANGE}Timeout waiting for element with selector '{content_selector}' on {url}.{COLOR_RESET}")
            return []
        except Exception as e:
            print(f"{COLOR_RED}Error during protected content scraping: {e}{COLOR_RESET}")
            return []
            
    def scrape_quotes(self, url="https://my.pitchbook.com/profile/97149-88/investor/profile"):
        quotes_data = []
        
        try:
            self.driver.get(url)
            page_num = 1
            
            print(f"{COLOR_BLUE}Scraping page {page_num}...{COLOR_RESET}")
            
            quotes = self.wait.until(
                EC.presence_of_all_elements_located((By.CLASS_NAME, "quote"))
            )
            
            for quote in quotes:
                try:
                    text = quote.find_element(By.CLASS_NAME, "text").text
                    author = quote.find_element(By.CLASS_NAME, "author").text
                    tags = [tag.text for tag in quote.find_elements(By.CLASS_NAME, "tag")] 
                    
                    quotes_data.append({
                        'text': text,
                        'author': author,
                        'tags': tags,
                        'page': page_num
                    })
                except NoSuchElementException as e:
                    print(f"{COLOR_ORANGE}Error extracting quote details (text/author/tags): {e}{COLOR_RESET}")
                    continue
        except TimeoutException:
            print(f"{COLOR_ORANGE}Timeout waiting for page to load or quotes to appear.{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error during scraping quotes: {e}{COLOR_RESET}")
        
        return quotes_data
    
    def _extract_cell_content(self, cell_element, col_header):
        """
        Helper to extract text, link, and check for 'x' footnote from a table cell.
        """
        cell_data = {
            col_header: cell_element.text.strip(), # Default to full cell text
            f"{col_header}_link": ""
        }
        
        # Check for a company name link specifically
        name_link_element = None
        try:
            # Try to find the <a> tag that is likely the primary link for the company
            # This handles cases like <td><div><span><a>Company</a></span></div></td>
            name_link_element = cell_element.find_element(By.CSS_SELECTOR, "span.entity-hover a")
        except NoSuchElementException:
            try:
                # Fallback: if not entity-hover, maybe a direct link
                name_link_element = cell_element.find_element(By.TAG_NAME, "a")
            except NoSuchElementException:
                pass # No link found in this cell

        if name_link_element:
            cell_data[col_header] = name_link_element.text.strip()
            cell_data[f"{col_header}_link"] = urljoin(self.driver.current_url, name_link_element.get_attribute("href"))
        
        # Check for 'x' footnote within the cell for relevant columns
        cell_data['_is_exited_deal'] = False
        if col_header in ["Name", "Company Name"]: # Apply this check only to name columns
            try:
                # Look for the specific 'x' footnote span
                foot_note_elements = cell_element.find_elements(By.CSS_SELECTOR, "span.foot-note")
                for fn_element in foot_note_elements:
                    if fn_element.text.strip().lower() == 'x':
                        cell_data['_is_exited_deal'] = True
                        break
            except NoSuchElementException:
                pass # No footnote found

        return cell_data

    def _prepare_related_companies_for_recursion(self, raw_data, name_link_header, source_type_name, required_deal_type=None):

        prepared_list = []
        if raw_data:
            print(f"{COLOR_BLUE}Processing {len(raw_data)} {source_type_name} rows.{COLOR_RESET}")
            for row in raw_data:
                processed_row = row.copy()
                
                if name_link_header != 'Name' and name_link_header in processed_row:
                    processed_row['Name'] = processed_row.pop(name_link_header)
                    if f'{name_link_header}_link' in processed_row:
                        processed_row['Name_link'] = processed_row.pop(f'{name_link_header}_link')
       
                if source_type_name == "Investment (Buy-Side)":
        
                    if required_deal_type:
                        deal_type = processed_row.get("Deal Type") 
                        if deal_type != required_deal_type:
                            print(f"{COLOR_YELLOW}Skipping investment '{processed_row.get('Name', 'N/A')}' because Deal Type is '{deal_type}', not '{required_deal_type}'.{COLOR_RESET}")
                            continue # Skip this row

         
                    if processed_row.get('_is_exited_deal', False):
                        print(f"{COLOR_YELLOW}Skipping investment '{processed_row.get('Name')}' due to 'x' footnote (exited deal).{COLOR_RESET}")
                        continue
                
                processed_row['Source_Type'] = source_type_name
                
                processed_row["nested_related_companies"] = []

                processed_row.pop('_is_exited_deal', None) 

                prepared_list.append(processed_row)
        return prepared_list

    def _scrape_affiliate_table_old_logic(self, main_section_selector, table_selector, tab_selector_a_tag=None, initial_section_wait=10):

        page_scraped_rows_data = []
        headers = [] 
        
        active_page_selector = f'{main_section_selector} nav[aria-label="Pagination"] button[aria-current="page"] span.button__caption'
        next_arrow_button_selector = f'{main_section_selector} nav[aria-label="Pagination"] button.pagination__navigation-button[aria-label="Go to next page"]'
        prev_button_selector = f'{main_section_selector} nav[aria-label="Pagination"] button.pagination__navigation-button[aria-label="Go to previous page"]'

        try:
            print(f"{COLOR_BLUE}Waiting for main section ({main_section_selector}) to be visible (up to {initial_section_wait}s)...{COLOR_RESET}")
            WebDriverWait(self.driver, initial_section_wait).until(EC.visibility_of_element_located((By.CSS_SELECTOR, main_section_selector)))
            print(f"{COLOR_BLUE}Main section ({main_section_selector}) found and visible.{COLOR_RESET}")

            # 2. If a specific tab is required, find and activate it
            if tab_selector_a_tag:
                print(f"{COLOR_BLUE}Checking tab status ({tab_selector_a_tag}) (up to 10s for visibility)...{COLOR_RESET}")
                target_tab_element = WebDriverWait(self.driver, 3).until(EC.visibility_of_element_located((By.CSS_SELECTOR, tab_selector_a_tag)))
                print(f"{COLOR_BLUE}Tab ({tab_selector_a_tag}) found and visible.{COLOR_RESET}")

                if target_tab_element.get_attribute("aria-selected") != "true":
                    print(f"{COLOR_BLUE}Tab ({tab_selector_a_tag}) is not active. Clicking to activate...{COLOR_RESET}")
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_tab_element)
                    time.sleep(0.5)
                    self.driver.execute_script("arguments[0].click();", target_tab_element)
                    
                    WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.CSS_SELECTOR, tab_selector_a_tag + '[aria-selected="true"]')))
                    print(f"{COLOR_BLUE}Tab ({tab_selector_a_tag}) activated.{COLOR_RESET}")
                else:
                    print(f"{COLOR_BLUE}Tab ({tab_selector_a_tag}) is already active.{COLOR_RESET}")
                time.sleep(0.5)

            # 3. Wait for the table and its content to be ready
            print(f"{COLOR_BLUE}Waiting for table '{table_selector}' to be visible (up to 10s)...{COLOR_RESET}")
            table = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, table_selector))
            )
            print(f"{COLOR_BLUE}Table is visible.{COLOR_RESET}")

            # Wait for any potential loading overlay to disappear within the section
            loading_box_selector = f'{main_section_selector} div.box-loading'
            try:
                print(f"{COLOR_BLUE}Waiting for loading box '{loading_box_selector}' to disappear (up to 5s)...{COLOR_RESET}")
                WebDriverWait(self.driver, 5).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, loading_box_selector))
                )
                print(f"{COLOR_BLUE}Loading box disappeared (or was not present).{COLOR_RESET}")
            except TimeoutException:
                print(f"{COLOR_ORANGE}Warning: Loading box '{loading_box_selector}' did not disappear within 5s. Proceeding anyway.{COLOR_RESET}")

            # Now, wait for the table body to be present
            print(f"{COLOR_BLUE}Waiting for table body ('{table_selector} tbody') to be present (up to 10s)...{COLOR_RESET}")
            table_body_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody"))
            )
            print(f"{COLOR_BLUE}Table body is present.{COLOR_RESET}")

            # NEW: Wait for at least one row (tr) to be present within the table body
            print(f"{COLOR_BLUE}Waiting for at least one row ('{table_selector} tbody tr') to be present (up to 10s)...{COLOR_RESET}")
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody tr"))
            )
            print(f"{COLOR_BLUE}At least one row is present in table body. Content loaded.{COLOR_RESET}")

        except TimeoutException as e:
            screenshot_name = f"error_table_load_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"{COLOR_ORANGE}Warning: Timeout waiting for main section, tab, or table structure within {main_section_selector}. This might mean the table is empty or failed to load within the given time. Error: {type(e).__name__}: {e}. Proceeding but returning potentially empty data.{COLOR_RESET}")
            return []
        except Exception as e:
            screenshot_name = f"error_table_scrape_unexpected_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"{COLOR_RED}An unexpected error occurred during table setup for {main_section_selector}. Screenshot saved to {screenshot_name}. Error: {type(e).__name__}: {e}{COLOR_RESET}")
            return []


        current_page_num = 1
        try:
            initial_active_page_text = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, active_page_selector))).text
            current_page_num = int(initial_active_page_text)
        except (TimeoutException, ValueError):
            print(f"{COLOR_ORANGE}Could not determine initial active page number, assuming 1.{COLOR_RESET}")
            current_page_num = 1

  
        if current_page_num != 1:
            print(f"{COLOR_ORANGE}Table not on page 1 ({current_page_num}). Attempting to navigate back to page 1 using 'Prev' button.{COLOR_RESET}")
            
            while current_page_num > 1:
                try:
                    prev_button = WebDriverWait(self.driver, 5).until( # Shorter wait for prev button
                        EC.element_to_be_clickable((By.CSS_SELECTOR, prev_button_selector))
                    )
                    
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", prev_button)
                    time.sleep(0.2) 

                    print(f"{COLOR_BLUE}Clicking 'Prev' button to go from page {current_page_num}...{COLOR_RESET}")
                    self.driver.execute_script("arguments[0].click();", prev_button)
                    
                    old_page_num_for_wait = current_page_num
                    print(f"{COLOR_BLUE}Waiting for page to change from {old_page_num_for_wait}...{COLOR_RESET}")
                    WebDriverWait(self.driver, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, active_page_selector).text != str(old_page_num_for_wait))
                    
                    new_active_page_text = self.driver.find_element(By.CSS_SELECTOR, active_page_selector).text
                    try:
                        new_page_number = int(new_active_page_text)
                        print(f"{COLOR_BLUE}Successfully moved back to page {new_page_number}.{COLOR_RESET}")
                        current_page_num = new_page_number
                        time.sleep(.2) 
                    except ValueError:
                        print(f"{COLOR_ORANGE}Warning: Could not parse new active page number '{new_active_page_text}'. Ending 'Prev' navigation.{COLOR_RESET}")
                        break 
                    
                except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                    print(f"{COLOR_ORANGE}Error navigating back using 'Prev' button. Error: {type(e).__name__}: {e}.{COLOR_RESET}")
                    print(f"{COLOR_ORANGE}Skipping scraping for this table as initial state cannot be guaranteed.{COLOR_RESET}")
                    return [] 
            
            if current_page_num != 1:
                print(f"{COLOR_ORANGE}Failed to reach page 1. Currently on page {current_page_num}. Exiting table scraping.{COLOR_RESET}")
                return [] 

        print(f"{COLOR_BLUE}Successfully positioned on page 1 of the table.{COLOR_RESET}")

        while True:
            print(f"{COLOR_BLUE}--- Scraping data from page {current_page_num} of {main_section_selector} ---{COLOR_RESET}")
            
            try:
                # Re-find table to avoid stale elements
                table_body = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody")))
                
                # Scrape headers only once
                if not headers: 
                    header_elements = table_body.find_elements(By.XPATH, "./preceding-sibling::thead/tr/th") # Adjusted to find headers relative to tbody
                    headers = [header_el.text for header_el in header_elements]
                    if not headers:
                        print(f"{COLOR_RED}Error: No table headers found for {table_selector}. Cannot proceed.{COLOR_RESET}")
                        break 
                    print(f"{COLOR_BLUE}Headers found: {headers}{COLOR_RESET}")
                
                row_elements = table_body.find_elements(By.TAG_NAME, "tr")
                if not row_elements: 
                    print(f"{COLOR_BLUE}No more rows found. Ending scraping for this table.{COLOR_RESET}")
                    break 

                print(f"{COLOR_BLUE}Found {len(row_elements)} rows on page {current_page_num}.{COLOR_RESET}")
                for row in row_elements:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            col_header = headers[i]
                            # Use the new helper to extract cell content, including the exited deal flag
                            extracted_data = self._extract_cell_content(cell, col_header)
                            row_data.update(extracted_data)
                                
                    page_scraped_rows_data.append(row_data) 
                
                # Pagination Logic
                next_button_to_click = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_arrow_button_selector)))
                if next_button_to_click.get_attribute("aria-disabled") == "true":
                    print(f"{COLOR_BLUE}Next button is disabled (last page). Ending pagination.{COLOR_RESET}")
                    break

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button_to_click) 
                time.sleep(0.2) 
                self.driver.execute_script("arguments[0].click();", next_button_to_click)

                old_page_num_for_wait = current_page_num
                print(f"{COLOR_BLUE}Waiting for page to change from {old_page_num_for_wait}...{COLOR_RESET}")
                WebDriverWait(self.driver, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, active_page_selector).text != str(old_page_num_for_wait))
                
                new_active_page_text = self.driver.find_element(By.CSS_SELECTOR, active_page_selector).text
                current_page_num = int(new_active_page_text)
                print(f"{COLOR_BLUE}Successfully moved to page {current_page_num}.{COLOR_RESET}")
                time.sleep(0.2)

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                print(f"{COLOR_ORANGE}No more 'Next' button found or content did not update as expected. Ending pagination for {main_section_selector}. Error: {type(e).__name__}: {e}{COLOR_RESET}")
                break 
            except Exception as e: 
                print(f"{COLOR_RED}An unexpected error occurred during table scraping and pagination: {type(e).__name__}: {e}{COLOR_RESET}")
                break
        
        return page_scraped_rows_data

    def _scrape_investments_table(self, main_section_selector, table_selector, tab_text_to_find=None, initial_section_wait=10):
        """
        Generic function to scrape table data from a specific tab within a main section,
        including links from cells, and paginate through multiple pages.
        This version is intended for investments or other tables where tab is optional.
        """
        page_scraped_rows_data = []
        headers = []
        
        active_page_selector = f'{main_section_selector} nav[aria-label="Pagination"] button[aria-current="page"] span.button__caption'
        next_arrow_button_selector = f'{main_section_selector} nav[aria-label="Pagination"] button.pagination__navigation-button[aria-label="Go to next page"]'
        prev_button_selector = f'{main_section_selector} nav[aria-label="Pagination"] button.pagination__navigation-button[aria-label="Go to previous page"]'

        xpath_main_section_base = main_section_selector.replace('#', '[@id=\'') + "\']"
        if xpath_main_section_base.startswith('section'):
            xpath_main_section_base = '//' + xpath_main_section_base
        elif not xpath_main_section_base.startswith('//'):
            xpath_main_section_base = '//' + xpath_main_section_base

        try:
            print(f"{COLOR_BLUE}Waiting for main section ({main_section_selector}) to be visible (up to {initial_section_wait}s)...{COLOR_RESET}")
            WebDriverWait(self.driver, initial_section_wait).until(EC.visibility_of_element_located((By.CSS_SELECTOR, main_section_selector)))
            print(f"{COLOR_BLUE}Main section ({main_section_selector}) found and visible.{COLOR_RESET}")

            if tab_text_to_find:
                print(f"{COLOR_BLUE}Attempting to find and activate tab with text '{tab_text_to_find}' within {main_section_selector} (up to 10s)...{COLOR_RESET}")
                tab_xpath = (
                    f"{xpath_main_section_base}//a[.//span[normalize-space(text())='{tab_text_to_find}']] | "
                    f"{xpath_main_section_base}//a[normalize-space(text())='{tab_text_to_find}']"
                )
                
                try:
                    target_tab_element = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.XPATH, tab_xpath)))
                    print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' found and visible.{COLOR_RESET}")

                    if target_tab_element.get_attribute("aria-selected") != "true":
                        print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' is not active. Clicking to activate...{COLOR_RESET}")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_tab_element)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", target_tab_element)
                        
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, tab_xpath + '[@aria-selected="true"]')))
                        print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' activated.{COLOR_RESET}")
                    else:
                        print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' is already active.{COLOR_RESET}")
                    time.sleep(0.5)
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException) as e:
                    print(f"{COLOR_ORANGE}Warning: Specific tab '{tab_text_to_find}' not found or could not be activated within {main_section_selector}. Error: {type(e).__name__}: {e}. Proceeding to scrape the default visible table.{COLOR_RESET}")

            print(f"{COLOR_BLUE}Waiting for table '{table_selector}' to be visible (up to 10s)...{COLOR_RESET}")
            table = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, table_selector))
            )
            print(f"{COLOR_BLUE}Table is visible.{COLOR_RESET}")

            loading_box_selector = f'{main_section_selector} div.box-loading'
            try:
                print(f"{COLOR_BLUE}Waiting for loading box '{loading_box_selector}' to disappear (up to 5s)...{COLOR_RESET}")
                WebDriverWait(self.driver, 5).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, loading_box_selector))
                )
                print(f"{COLOR_BLUE}Loading box disappeared (or was not present).{COLOR_RESET}")
            except TimeoutException:
                print(f"{COLOR_ORANGE}Warning: Loading box '{loading_box_selector}' did not disappear within 5s. Proceeding anyway.{COLOR_RESET}")

            print(f"{COLOR_BLUE}Waiting for table body ('{table_selector} tbody') to be present (up to 10s)...{COLOR_RESET}")
            table_body_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody"))
            )
            print(f"{COLOR_BLUE}Table body is present.{COLOR_RESET}")

            max_retries = 3
            current_retry = 0
            rows_in_table = []
            while current_retry < max_retries:
                rows_in_table = table_body_element.find_elements(By.CSS_SELECTOR, "tr.table__row")
                if rows_in_table:
                    print(f"{COLOR_BLUE}Found {len(rows_in_table)} rows (tr.table__row) in table body. Content loaded.{COLOR_RESET}")
                    break
                else:
                    print(f"{COLOR_ORANGE}No tr.table__row elements found yet in {main_section_selector}. Retrying in 2 seconds... (Attempt {current_retry + 1}/{max_retries}){COLOR_RESET}")
                    time.sleep(2)
                    table_body_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody"))
                    )
                current_retry += 1
            
            if not rows_in_table:
                print(f"{COLOR_ORANGE}Warning: No visible data rows (tr.table__row) found within table {main_section_selector} after multiple retries. Table is empty or failed to load data.{COLOR_RESET}")
                return []

        except TimeoutException as e:
            screenshot_name = f"error_table_load_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"{COLOR_ORANGE}Warning: Timeout waiting for main section or table structure within {main_section_selector}. This might mean the table is empty or failed to load within the given time. Error: {type(e).__name__}: {e}. Proceeding but returning potentially empty data.{COLOR_RESET}")
            return []
        except Exception as e:
            screenshot_name = f"error_table_scrape_unexpected_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"{COLOR_RED}An unexpected error occurred during table setup for {main_section_selector}. Screenshot saved to {screenshot_name}. Error: {type(e).__name__}: {e}{COLOR_RESET}")
            return []

        current_page_num = 1
        try:
            initial_active_page_text = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, active_page_selector))).text
            current_page_num = int(initial_active_page_text)
        except (TimeoutException, ValueError):
            print(f"{COLOR_ORANGE}Could not determine initial active page number, assuming 1.{COLOR_RESET}")
            current_page_num = 1

        if current_page_num != 1:
            print(f"{COLOR_ORANGE}Table not on page 1 ({current_page_num}). Attempting to navigate back to page 1 using 'Prev' button.{COLOR_RESET}")
            
            while current_page_num > 1:
                try:
                    prev_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, prev_button_selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", prev_button)
                    time.sleep(0.2)
                    self.driver.execute_script("arguments[0].click();", prev_button)
                    
                    old_page_num_for_wait = current_page_num
                    print(f"{COLOR_BLUE}Waiting for page to change from {old_page_num_for_wait}...{COLOR_RESET}")
                    WebDriverWait(self.driver, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, active_page_selector).text != str(old_page_num_for_wait))
                    
                    new_active_page_text = self.driver.find_element(By.CSS_SELECTOR, active_page_selector).text
                    try:
                        new_page_number = int(new_active_page_text)
                        print(f"{COLOR_BLUE}Successfully moved back to page {new_page_number}.{COLOR_RESET}")
                        current_page_num = new_page_number
                        time.sleep(.2)
                    except ValueError:
                        print(f"{COLOR_ORANGE}Warning: Could not parse new active page number '{new_active_page_text}'. Ending 'Prev' navigation.{COLOR_RESET}")
                        break
                    
                except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                    print(f"{COLOR_ORANGE}Error navigating back using 'Prev' button. Error: {type(e).__name__}: {e}.{COLOR_RESET}")
                    print(f"{COLOR_ORANGE}Skipping scraping for this table as initial state cannot be guaranteed.{COLOR_RESET}")
                    return []
            
            if current_page_num != 1:
                print(f"{COLOR_ORANGE}Failed to reach page 1. Currently on page {current_page_num}. Exiting table scraping.{COLOR_RESET}")
                return []

        print(f"{COLOR_BLUE}Successfully positioned on page 1 of the table.{COLOR_RESET}")

        while True:
            print(f"{COLOR_BLUE}--- Scraping data from page {current_page_num} of {main_section_selector} ---{COLOR_RESET}")
            
            try:
                table_body = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody")))
                
                if not headers:
                    header_elements = table_body.find_elements(By.XPATH, "./preceding-sibling::thead/tr/th")
                    headers = [header_el.text for header_el in header_elements]
                    if not headers:
                        print(f"{COLOR_RED}Error: No table headers found for {table_selector}. Cannot proceed.{COLOR_RESET}")
                        break
                    print(f"{COLOR_BLUE}Headers found: {headers}{COLOR_RESET}")
                
                row_elements = table_body.find_elements(By.TAG_NAME, "tr")
                if not row_elements:
                    print(f"{COLOR_BLUE}No more rows found. Ending scraping for this table.{COLOR_RESET}")
                    break

                print(f"{COLOR_BLUE}Found {len(row_elements)} rows on page {current_page_num}.{COLOR_RESET}")
                for row in row_elements:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            col_header = headers[i]
                            extracted_data = self._extract_cell_content(cell, col_header)
                            row_data.update(extracted_data)
                                
                    page_scraped_rows_data.append(row_data)
                
                next_button_to_click = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_arrow_button_selector)))
                if next_button_to_click.get_attribute("aria-disabled") == "true":
                    print(f"{COLOR_BLUE}Next button is disabled (last page). Ending pagination.{COLOR_RESET}")
                    break

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button_to_click)
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].click();", next_button_to_click)

                old_page_num_for_wait = current_page_num
                print(f"{COLOR_BLUE}Waiting for page to change from {old_page_num_for_wait}...{COLOR_RESET}")
                WebDriverWait(self.driver, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, active_page_selector).text != str(old_page_num_for_wait))
                
                new_active_page_text = self.driver.find_element(By.CSS_SELECTOR, active_page_selector).text
                current_page_num = int(new_active_page_text)
                print(f"{COLOR_BLUE}Successfully moved to page {current_page_num}.{COLOR_RESET}")
                time.sleep(0.2)

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                print(f"{COLOR_ORANGE}No more 'Next' button found or content did not update as expected. Ending pagination for {main_section_selector}. Error: {type(e).__name__}: {e}{COLOR_RESET}")
                break
            except Exception as e:
                print(f"{COLOR_RED}An unexpected error occurred during table scraping and pagination: {type(e).__name__}: {e}{COLOR_RESET}")
                break
        
        return page_scraped_rows_data


    def _get_also_known_as(self):
        """
        Extracts the "Also Known As" value from the profile information section.
        """
        return self._get_value_from_profile_info_section("Also Known As", "div")

    def _get_profile_website(self):
        return self._get_value_from_profile_info_section("Website", "a")

    def _get_former_names(self):
        return self._get_value_from_profile_info_section("Formerly Known As", "div")

    def _get_legal_name(self):
        return self._get_value_from_profile_info_section("Legal Name", "div")

    def _scrape_contact_info(self):
        """
        Scrapes contact information (name, title, email, phone numbers)
        from the 'Primary Contact' section on the profile page.
        Returns a dictionary of individual fields, or None for missing fields.
        """
        result = {
            "contact_name": None,
            "contact_profile_link": None,
            "contact_title": None,
            "contact_email": None,
            "contact_email_link": None,
            "contact_business_phone": None,
            "contact_mobile_phone": None,
        }
        
        print(f"{COLOR_BLUE}Attempting to scrape primary contact information...{COLOR_RESET}")
        
        try:
            contact_section_xpath = "//span[normalize-space(text())='Primary Contact']/ancestor::div[contains(@class, 'grid__cell') and contains(@class, 'grid__cell_4')]"
            
            start_time_contact_section = time.time()
            contact_section_element = WebDriverWait(self.driver, 5).until( 
                EC.presence_of_element_located((By.XPATH, contact_section_xpath))
            )
            elapsed_time_contact_section = time.time() - start_time_contact_section
            print(f"{COLOR_BLUE}Primary Contact section found in {elapsed_time_contact_section:.2f} seconds.{COLOR_RESET}")

            ul_contact_info = contact_section_element.find_element(By.CSS_SELECTOR, "ul.contact-info")
            list_items = ul_contact_info.find_elements(By.TAG_NAME, "li")
            
            if not list_items:
                print(f"{COLOR_ORANGE}No list items found in primary contact info section.{COLOR_RESET}")
                return result

            if len(list_items) > 0:
                try:
                    name_element = list_items[0].find_element(By.CSS_SELECTOR, "span.entity-hover a")
                    result["contact_name"] = name_element.text.strip()
                    result["contact_profile_link"] = urljoin(self.driver.current_url, name_element.get_attribute("href"))
                except NoSuchElementException:
                    print(f"{COLOR_ORANGE}Contact name/profile link not found in the first list item.{COLOR_RESET}")

            if len(list_items) > 1:
                result["contact_title"] = list_items[1].text.strip()

            for li in list_items:
                text = li.text.strip()
                try:
                    email_element = li.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                    result["contact_email"] = email_element.text.strip()
                    continue # Skip to next li, as this one was an email
                except NoSuchElementException:
                    pass 
                
                if text.startswith("Business:"):
                    result["contact_business_phone"] = text.replace("Business:", "").strip()
                elif text.startswith("Mobile:"):
                    result["contact_mobile_phone"] = text.replace("Mobile:", "").strip()
                
            print(f"{COLOR_BLUE}Successfully scraped primary contact information.{COLOR_RESET}")
            return result

        except TimeoutException:
            print(f"{COLOR_ORANGE}Timeout waiting for primary contact information section. Skipping primary contact info.{COLOR_RESET}")
        except NoSuchElementException:
            print(f"{COLOR_ORANGE}Primary contact information section or elements within not found. Skipping primary contact info.{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error scraping primary contact information: {e}{COLOR_RESET}")
        
        return result 

    def _scrape_office_address(self):
        """
        Scrapes the office address information from the dedicated section.
        Returns a dictionary of individual fields, or None for missing fields.
        Flattens address lines into separate fields (e.g., office_address_line1).
        """
        result = {
            "office_address_line1": None,
            "office_address_line2": None,
            "office_address_line3": None, # Assuming max 3 lines for address
            "office_email": None,
            "office_phone": None
        }

        print(f"{COLOR_BLUE}Attempting to scrape office address information...{COLOR_RESET}")

        # REFINED SELECTOR: Target the ul.contact-info that is a direct child of
        # div.element-group__item, which is a direct child of a div with
        # element-group, element-group_vertical, and element-group_s classes.
        address_section_selector = "div.element-group.element-group_vertical.element-group_s > div.element-group__item > ul.contact-info"
        
        start_time_address_section = time.time()
        try:
            # Use presence_of_element_located to ensure the element is in the DOM
            ul_address_info = WebDriverWait(self.driver, 5).until( 
                EC.presence_of_element_located((By.CSS_SELECTOR, address_section_selector))
            )
            elapsed_time_address_section = time.time() - start_time_address_section
            print(f"{COLOR_BLUE}Office address section found in {elapsed_time_address_section:.2f} seconds.{COLOR_RESET}")

            list_items = ul_address_info.find_elements(By.TAG_NAME, "li")

            if not list_items:
                print(f"{COLOR_ORANGE}No list items found in office address section.{COLOR_RESET}")
                return result

            address_lines_found = []
            for li in list_items:
                text = li.text.strip()
                
                # Check for email and phone using their specific attributes/text
                try:
                    email_element = li.find_element(By.CSS_SELECTOR, "a[href^='mailto:']")
                    result["office_email"] = email_element.text.strip()
                    continue # Skip to next li, as this one was an email
                except NoSuchElementException:
                    pass 
                
                if text.startswith("Business:"):
                    result["office_phone"] = text.replace("Business:", "").strip()
                elif text.startswith("Mobile:"):
                    result["contact_mobile_phone"] = text.replace("Mobile:", "").strip()
                
            print(f"{COLOR_BLUE}Successfully scraped office address information.{COLOR_RESET}")
            return result

        except TimeoutException:
            print(f"{COLOR_ORANGE}Timeout waiting for office address information section. Skipping primary contact info.{COLOR_RESET}")
        except NoSuchElementException:
            print(f"{COLOR_ORANGE}Office address section or elements within not found. Skipping primary contact info.{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error scraping office address information: {e}{COLOR_RESET}")
        
        return result

    def _get_value_from_profile_info_section(self, label_text, value_element_tag):
        """
        A robust method to extract values (website, former names, legal name)
        from the "General Information" section using XPath, combining label text
        with the presence of the `table-list__cell` class on the value element.
        """
        value = None
        # Use a shorter, dedicated wait for quickly checking if an element exists
        # This will fail faster if the element is not found.
        quick_wait = WebDriverWait(self.driver, 2) # Set a shorter timeout, e.g., 2 seconds

        xpath_selector = (
            f"//div[contains(@class, 'table-list__cell_caption')]//label/span[normalize-space(text())='{label_text}']"
            f"/ancestor::div[contains(@class, 'table-list__cell_caption')]"
            f"/following-sibling::div[contains(@class, 'table-list__cell')]//{value_element_tag}"
        )
        
        start_time = time.time() # Record start time
        try:
            print(f"{COLOR_BLUE}Attempting to find '{label_text}' using XPath: {xpath_selector} with a quick wait...{COLOR_RESET}")
            element = quick_wait.until( # Use the quick_wait here
                EC.presence_of_element_located((By.XPATH, xpath_selector))
            )
            if value_element_tag == 'a':
                value = element.get_attribute('href')
            else:
                value = element.text.strip()
            
            end_time = time.time() # Record end time
            elapsed_time = end_time - start_time
            print(f"{COLOR_BLUE}Found '{label_text}': {value} in {elapsed_time:.2f} seconds.{COLOR_RESET}")
        except TimeoutException:
            end_time = time.time() # Record end time even on timeout
            elapsed_time = end_time - start_time
            print(f"{COLOR_ORANGE}Field '{label_text}' not found on page within quick timeout ({elapsed_time:.2f} seconds). Skipping.{COLOR_RESET}")
        except NoSuchElementException:
            end_time = time.time() # Record end time
            elapsed_time = end_time - start_time
            print(f"{COLOR_ORANGE}Field '{label_text}' element not found ({elapsed_time:.2f} seconds). Skipping.{COLOR_RESET}")
        except Exception as e:
            end_time = time.time() # Record end time
            elapsed_time = time.time() - start_time
            print(f"{COLOR_RED}Error extracting '{label_text}' ({elapsed_time:.2f} seconds): {e}{COLOR_RESET}")
        return value

    def _clean_url(self, url):
        """Removes http/https and trailing slashes from a URL, preserving www. if present."""
        if not url:
            return None
        
        # Remove http:// or https://
        cleaned_url = url.replace("http://", "").replace("https://", "")
            
        # Remove trailing slash
        if cleaned_url.endswith("/"):
            cleaned_url = cleaned_url[:-1]
            
        return cleaned_url

    def _scrape_investments_table(self, main_section_selector, table_selector, tab_text_to_find=None, initial_section_wait=10):
        page_scraped_rows_data = []
        headers = []
        
        active_page_selector = f'{main_section_selector} nav[aria-label="Pagination"] button[aria-current="page"] span.button__caption'
        next_arrow_button_selector = f'{main_section_selector} nav[aria-label="Pagination"] button.pagination__navigation-button[aria-label="Go to next page"]'
        prev_button_selector = f'{main_section_selector} nav[aria-label="Pagination"] button.pagination__navigation-button[aria-label="Go to previous page"]'

        xpath_main_section_base = main_section_selector.replace('#', '[@id=\'') + "\']"
        if xpath_main_section_base.startswith('section'):
            xpath_main_section_base = '//' + xpath_main_section_base
        elif not xpath_main_section_base.startswith('//'):
            xpath_main_section_base = '//' + xpath_main_section_base

        try:
            print(f"{COLOR_BLUE}Waiting for main section ({main_section_selector}) to be visible (up to {initial_section_wait}s)...{COLOR_RESET}")
            WebDriverWait(self.driver, initial_section_wait).until(EC.visibility_of_element_located((By.CSS_SELECTOR, main_section_selector)))
            print(f"{COLOR_BLUE}Main section ({main_section_selector}) found and visible.{COLOR_RESET}")

            if tab_text_to_find:
                print(f"{COLOR_BLUE}Attempting to find and activate tab with text '{tab_text_to_find}' within {main_section_selector} (up to 10s)...{COLOR_RESET}")
                tab_xpath = (
                    f"{xpath_main_section_base}//a[.//span[normalize-space(text())='{tab_text_to_find}']] | "
                    f"{xpath_main_section_base}//a[normalize-space(text())='{tab_text_to_find}']"
                )
                
                try:
                    target_tab_element = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.XPATH, tab_xpath)))
                    print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' found and visible.{COLOR_RESET}")

                    if target_tab_element.get_attribute("aria-selected") != "true":
                        print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' is not active. Clicking to activate...{COLOR_RESET}")
                        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", target_tab_element)
                        time.sleep(0.5)
                        self.driver.execute_script("arguments[0].click();", target_tab_element)
                        
                        WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.XPATH, tab_xpath + '[@aria-selected="true"]')))
                        print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' activated.{COLOR_RESET}")
                    else:
                        print(f"{COLOR_BLUE}Tab with text '{tab_text_to_find}' is already active.{COLOR_RESET}")
                    time.sleep(0.5)
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException) as e:
                    print(f"{COLOR_ORANGE}Warning: Specific tab '{tab_text_to_find}' not found or could not be activated within {main_section_selector}. Error: {type(e).__name__}: {e}. Proceeding to scrape the default visible table.{COLOR_RESET}")

            print(f"{COLOR_BLUE}Waiting for table '{table_selector}' to be visible (up to 10s)...{COLOR_RESET}")
            table = WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, table_selector))
            )
            print(f"{COLOR_BLUE}Table is visible.{COLOR_RESET}")

            loading_box_selector = f'{main_section_selector} div.box-loading'
            try:
                print(f"{COLOR_BLUE}Waiting for loading box '{loading_box_selector}' to disappear (up to 5s)...{COLOR_RESET}")
                WebDriverWait(self.driver, 5).until(
                    EC.invisibility_of_element_located((By.CSS_SELECTOR, loading_box_selector))
                )
                print(f"{COLOR_BLUE}Loading box disappeared (or was not present).{COLOR_RESET}")
            except TimeoutException:
                print(f"{COLOR_ORANGE}Warning: Loading box '{loading_box_selector}' did not disappear within 5s. Proceeding anyway.{COLOR_RESET}")

            print(f"{COLOR_BLUE}Waiting for table body ('{table_selector} tbody') to be present (up to 10s)...{COLOR_RESET}")
            table_body_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody"))
            )
            print(f"{COLOR_BLUE}Table body is present.{COLOR_RESET}")

            max_retries = 3
            current_retry = 0
            rows_in_table = []
            while current_retry < max_retries:
                rows_in_table = table_body_element.find_elements(By.CSS_SELECTOR, "tr.table__row")
                if rows_in_table:
                    print(f"{COLOR_BLUE}Found {len(rows_in_table)} rows (tr.table__row) in table body. Content loaded.{COLOR_RESET}")
                    break
                else:
                    print(f"{COLOR_ORANGE}No tr.table__row elements found yet in {main_section_selector}. Retrying in 2 seconds... (Attempt {current_retry + 1}/{max_retries}){COLOR_RESET}")
                    time.sleep(2)
                    table_body_element = WebDriverWait(self.driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody"))
                    )
                current_retry += 1
            
            if not rows_in_table:
                print(f"{COLOR_ORANGE}Warning: No visible data rows (tr.table__row) found within table {main_section_selector} after multiple retries. Table is empty or failed to load data.{COLOR_RESET}")
                return []

        except TimeoutException as e:
            screenshot_name = f"error_table_load_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"{COLOR_ORANGE}Warning: Timeout waiting for main section or table structure within {main_section_selector}. This might mean the table is empty or failed to load within the given time. Error: {type(e).__name__}: {e}. Proceeding but returning potentially empty data.{COLOR_RESET}")
            return []
        except Exception as e:
            screenshot_name = f"error_table_scrape_unexpected_{int(time.time())}.png"
            self.driver.save_screenshot(screenshot_name)
            print(f"{COLOR_RED}An unexpected error occurred during table setup for {main_section_selector}. Screenshot saved to {screenshot_name}. Error: {type(e).__name__}: {e}{COLOR_RESET}")
            return []

        current_page_num = 1
        try:
            initial_active_page_text = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, active_page_selector))).text
            current_page_num = int(initial_active_page_text)
        except (TimeoutException, ValueError):
            print(f"{COLOR_ORANGE}Could not determine initial active page number, assuming 1.{COLOR_RESET}")
            current_page_num = 1

        if current_page_num != 1:
            print(f"{COLOR_ORANGE}Table not on page 1 ({current_page_num}). Attempting to navigate back to page 1 using 'Prev' button.{COLOR_RESET}")
            
            while current_page_num > 1:
                try:
                    prev_button = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, prev_button_selector))
                    )
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", prev_button)
                    time.sleep(0.2)
                    self.driver.execute_script("arguments[0].click();", prev_button)
                    
                    old_page_num_for_wait = current_page_num
                    print(f"{COLOR_BLUE}Waiting for page to change from {old_page_num_for_wait}...{COLOR_RESET}")
                    WebDriverWait(self.driver, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, active_page_selector).text != str(old_page_num_for_wait))
                    
                    new_active_page_text = self.driver.find_element(By.CSS_SELECTOR, active_page_selector).text
                    try:
                        new_page_number = int(new_active_page_text)
                        print(f"{COLOR_BLUE}Successfully moved back to page {new_page_number}.{COLOR_RESET}")
                        current_page_num = new_page_number
                        time.sleep(.2)
                    except ValueError:
                        print(f"{COLOR_ORANGE}Warning: Could not parse new active page number '{new_active_page_text}'. Ending 'Prev' navigation.{COLOR_RESET}")
                        break
                    
                except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                    print(f"{COLOR_ORANGE}Error navigating back using 'Prev' button. Error: {type(e).__name__}: {e}.{COLOR_RESET}")
                    print(f"{COLOR_ORANGE}Skipping scraping for this table as initial state cannot be guaranteed.{COLOR_RESET}")
                    return []
            
            if current_page_num != 1:
                print(f"{COLOR_ORANGE}Failed to reach page 1. Currently on page {current_page_num}. Exiting table scraping.{COLOR_RESET}")
                return []

        print(f"{COLOR_BLUE}Successfully positioned on page 1 of the table.{COLOR_RESET}")

        while True:
            print(f"{COLOR_BLUE}--- Scraping data from page {current_page_num} of {main_section_selector} ---{COLOR_RESET}")
            
            try:
                table_body = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.CSS_SELECTOR, f"{table_selector} tbody")))
                
                if not headers:
                    header_elements = table_body.find_elements(By.XPATH, "./preceding-sibling::thead/tr/th")
                    headers = [header_el.text for header_el in header_elements]
                    if not headers:
                        print(f"{COLOR_RED}Error: No table headers found for {table_selector}. Cannot proceed.{COLOR_RESET}")
                        break
                    print(f"{COLOR_BLUE}Headers found: {headers}{COLOR_RESET}")
                
                row_elements = table_body.find_elements(By.TAG_NAME, "tr")
                if not row_elements:
                    print(f"{COLOR_BLUE}No more rows found. Ending scraping for this table.{COLOR_RESET}")
                    break

                print(f"{COLOR_BLUE}Found {len(row_elements)} rows on page {current_page_num}.{COLOR_RESET}")
                for row in row_elements:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    row_data = {}
                    for i, cell in enumerate(cells):
                        if i < len(headers):
                            col_header = headers[i]
                            extracted_data = self._extract_cell_content(cell, col_header)
                            row_data.update(extracted_data)
                                
                    page_scraped_rows_data.append(row_data)
                
                next_button_to_click = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.CSS_SELECTOR, next_arrow_button_selector)))
                if next_button_to_click.get_attribute("aria-disabled") == "true":
                    print(f"{COLOR_BLUE}Next button is disabled (last page). Ending pagination.{COLOR_RESET}")
                    break

                self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button_to_click)
                time.sleep(0.2)
                self.driver.execute_script("arguments[0].click();", next_button_to_click)

                old_page_num_for_wait = current_page_num
                print(f"{COLOR_BLUE}Waiting for page to change from {old_page_num_for_wait}...{COLOR_RESET}")
                WebDriverWait(self.driver, 10).until(lambda driver: driver.find_element(By.CSS_SELECTOR, active_page_selector).text != str(old_page_num_for_wait))
                
                new_active_page_text = self.driver.find_element(By.CSS_SELECTOR, active_page_selector).text
                current_page_num = int(new_active_page_text)
                print(f"{COLOR_BLUE}Successfully moved to page {current_page_num}.{COLOR_RESET}")
                time.sleep(0.2)

            except (TimeoutException, NoSuchElementException, StaleElementReferenceException, ElementClickInterceptedException) as e:
                print(f"{COLOR_ORANGE}No more 'Next' button found or content did not update as expected. Ending pagination for {main_section_selector}. Error: {type(e).__name__}: {e}{COLOR_RESET}")
                break
            except Exception as e:
                print(f"{COLOR_RED}An unexpected error occurred during table scraping and pagination: {type(e).__name__}: {e}{COLOR_RESET}")
                break
        
        return page_scraped_rows_data


    def scrape_profile_and_affiliates(self, profile_url, current_depth=0, max_depth=5):
        
        # Initialize the profile_data dictionary
        profile_data = {
            "profile_url": profile_url,
            "depth": current_depth,
            "website_link": None,
            "former_names": None,
            "also_known_as": None, # NEW FIELD
            "legal_name": None,
            "contact_name": None,
            "contact_profile_link": None,
            "contact_title": None,
            "contact_email": None,
            "contact_email_link": None,
            "contact_business_phone": None,
            "contact_mobile_phone": None,
            "office_address_line1": None,
            "office_address_line2": None,
            "office_address_line3": None,
            "office_email": None,
            "office_phone": None,
            "related_companies": [], # Unified list for affiliates and investments
            "status": "scraped" # Default status
        }

        # Ensure the profile_url is absolute before checking visited set
        if not profile_url.startswith('http'):
            profile_url = urljoin(self.base_url, profile_url) 
        
        if profile_url in self.visited_urls:
            print(f"{COLOR_BLUE}Already visited: {profile_url}. Skipping.{COLOR_RESET}")
            profile_data["status"] = "already_visited"
            return profile_data # Return a minimal structure for already visited URLs to avoid re-scraping and infinite loops
        
        if current_depth > max_depth:
            print(f"{COLOR_ORANGE}Max depth ({max_depth}) reached for {profile_url}. Skipping deeper recursion.{COLOR_RESET}")
            return None # Return None if max depth reached to stop recursion for this branch
        
        print(f"\n{COLOR_BLUE}--- Scraping Profile: {profile_url} (Depth: {current_depth}) ---{COLOR_RESET}")
        self.visited_urls.add(profile_url) # Mark as visited

        # Navigate to the profile URL once for scraping all sections
        print(f"{COLOR_BLUE}Navigating to: {profile_url}{COLOR_RESET}")
        self.driver.get(profile_url)
        # Removed hardcoded sleep, relying on waits below

        # Get additional data for the current profile page (website, former names, legal name) first
        # Wait for general info tab to be visible as a proxy for main page content load
        try:
            print(f"{COLOR_BLUE}Waiting for General Information section to be visible (up to 10s)...{COLOR_RESET}")
            WebDriverWait(self.driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, "section#general-info"))
            )
            print(f"{COLOR_BLUE}General Information section found.{COLOR_RESET}")
        except TimeoutException as e:
            print(f"{COLOR_ORANGE}Warning: General Information section not found or not visible for {profile_url}. Assuming basic profile page did not load correctly. Error: {e}. Skipping.{COLOR_RESET}")
            return profile_data # Return empty if general info doesn't load

        profile_data["website_link"] = self._clean_url(self._get_profile_website())
        profile_data["former_names"] = self._get_former_names()
        profile_data["also_known_as"] = self._get_also_known_as() # NEW: Get "Also Known As"
        profile_data["legal_name"] = self._get_legal_name()
        
        # Scrape contact information and unpack directly
        contact_details = self._scrape_contact_info()
        for key, value in contact_details.items():
            profile_data[key] = value

        # Scrape office address information and unpack directly
        office_address_details = self._scrape_office_address()
        for key, value in office_address_details.items():
            profile_data[key] = value


        # Scrape Affiliates table using the old logic (tab_selector_a_tag)
        # Use a short initial_section_wait here, as general info is loaded
        raw_affiliates_data = self._scrape_affiliate_table_old_logic(
            main_section_selector="section#affiliates",
            tab_selector_a_tag='a#undefined-affiliates\\/SUBSIDIARY', # Use the old, specific tab selector
            table_selector="section#affiliates table",
            initial_section_wait=3 # Short wait, assume not present if not there quickly
        )
        prepared_affiliates = self._prepare_related_companies_for_recursion(
            raw_affiliates_data, "Name", "Affiliate"
        )
        
        # Scrape Investments (Buy-Side) table using the new, more flexible logic (tab_text_to_find)
        # Use a short initial_section_wait here, as general info is loaded
        raw_investments_data = self._scrape_investments_table(
            main_section_selector="section#investments", 
            tab_text_to_find=None, # Scrape the default visible table in investments, no specific tab activation
            table_selector="section#investments table",
            initial_section_wait=3 # Short wait, assume not present if not there quickly
        )
        prepared_investments = self._prepare_related_companies_for_recursion(
            raw_investments_data, "Company Name", "Investment (Buy-Side)", required_deal_type="Merger/Acquisition"
        )
        
        # Combine all related companies found at this level
        all_related_companies_at_this_level = prepared_affiliates + prepared_investments
        profile_data["related_companies"] = all_related_companies_at_this_level # Assign to profile_data

        # Add a small delay to ensure all dynamic content for the profile details loads
        time.sleep(1) 

        # Now, recurse through the combined list of related companies
        if profile_data["related_companies"]:
            print(f"{COLOR_BLUE}Initiating recursive scraping for {len(profile_data['related_companies'])} related companies.{COLOR_RESET}")
            for related_company_entry in profile_data["related_companies"]:
                related_company_profile_link = related_company_entry.get('Name_link')
                if related_company_profile_link and current_depth < max_depth:
                    if "/profile/" in related_company_profile_link and related_company_profile_link.count('/') >= 4: 
                        print(f"{COLOR_BLUE}Found nested related company link: {related_company_profile_link} (Source: {related_company_entry['Source_Type']}). Recursing...{COLOR_RESET}")
                        child_profile_data = self.scrape_profile_and_affiliates(
                            related_company_profile_link, current_depth + 1, max_depth
                        )
                        
                        if child_profile_data and child_profile_data.get("status") != "already_visited": 
                            # Merge child's direct scraped data into the current related_company_entry
                            related_company_entry["website_link"] = self._clean_url(child_profile_data.get("website_link"))
                            related_company_entry["former_names"] = child_profile_data.get("former_names")
                            related_company_entry["also_known_as"] = child_profile_data.get("also_known_as") # NEW: Add to nested
                            related_company_entry["legal_name"] = child_profile_data.get("legal_name")
                            
                            for key in ["contact_name", "contact_profile_link", "contact_title", 
                                        "contact_email", "contact_email_link", "contact_business_phone", "contact_mobile_phone"]:
                                related_company_entry[key] = child_profile_data.get(key)
                            
                            for key in ["office_address_line1", "office_address_line2", "office_address_line3",
                                        "office_email", "office_phone"]:
                                related_company_entry[key] = child_profile_data.get(key)

                            # Attach the child's own related companies list to the current entry
                            related_company_entry["nested_related_companies"] = child_profile_data.get("related_companies", [])
                        else:
                            # If child was not successfully scraped or already visited, assign None/empty
                            print(f"{COLOR_ORANGE}Child profile {related_company_profile_link} not scraped or already visited.{COLOR_RESET}")
                            related_company_entry["website_link"] = None
                            related_company_entry["former_names"] = None
                            related_company_entry["also_known_as"] = None
                            related_company_entry["legal_name"] = None
                            for key in ["contact_name", "contact_profile_link", "contact_title", 
                                        "contact_email", "contact_email_link", "contact_business_phone", "contact_mobile_phone",
                                        "office_address_line1", "office_address_line2", "office_address_line3",
                                        "office_email", "office_phone"]:
                                related_company_entry[key] = None
                            related_company_entry["nested_related_companies"] = [] 
                    else:
                        print(f"{COLOR_ORANGE}Link is not a valid PitchBook profile link (or malformed): {related_company_profile_link}. Not recursing.{COLOR_RESET}")
                        related_company_entry["website_link"] = None
                        related_company_entry["former_names"] = None
                        related_company_entry["also_known_as"] = None 
                        related_company_entry["legal_name"] = None
                        for key in ["contact_name", "contact_profile_link", "contact_title", 
                                    "contact_email", "contact_email_link", "contact_business_phone", "contact_mobile_phone",
                                    "office_address_line1", "office_address_line2", "office_address_line3",
                                    "office_email", "office_phone"]:
                                related_company_entry[key] = None
                        related_company_entry["nested_related_companies"] = []
                elif not related_company_profile_link:
                    print(f"{COLOR_ORANGE}No profile link found for related company: {related_company_entry.get('Name', 'N/A')}{COLOR_RESET}")
                    related_company_entry["website_link"] = None
                    related_company_entry["former_names"] = None
                    related_company_entry["also_known_as"] = None # NEW: Add to nested
                    related_company_entry["legal_name"] = None
                    for key in ["contact_name", "contact_profile_link", "contact_title", 
                                "contact_email", "contact_email_link", "contact_business_phone", "contact_mobile_phone",
                                "office_address_line1", "office_address_line2", "office_address_line3",
                                "office_email", "office_phone"]:
                        related_company_entry[key] = None
                    related_company_entry["nested_related_companies"] = [] 
                elif current_depth >= max_depth:
                    print(f"{COLOR_ORANGE}Max depth reached for {profile_url}'s related company. Not recursing further.{COLOR_RESET}")
                    related_company_entry["website_link"] = None
                    related_company_entry["former_names"] = None
                    related_company_entry["also_known_as"] = None # NEW: Add to nested
                    related_company_entry["legal_name"] = None
                    for key in ["contact_name", "contact_profile_link", "contact_title", 
                                "contact_email", "contact_email_link", "contact_business_phone", "contact_mobile_phone",
                                "office_address_line1", "office_address_line2", "office_address_line3",
                                "office_email", "office_phone"]:
                        related_company_entry[key] = None
                    related_company_entry["nested_related_companies"] = [] 

        else:
            print(f"{COLOR_BLUE}No related companies (affiliates or investments) found or scraped from {profile_url}.{COLOR_RESET}")
            
        return profile_data


    def save_to_csv(self, data, filename):
        
        if not data:
            print(f"{COLOR_ORANGE}No data to save to CSV.{COLOR_RESET}")
            return

        flattened_data = []

        def get_company_name_for_csv(profile_data):
            return profile_data.get("root_name") or \
                   profile_data.get("legal_name") or \
                   profile_data.get("profile_url")

        def flatten_recursive(company_node, parent_name=None, parent_url=None):
            node_data = {k: v for k, v in company_node.items() if k not in ["related_companies", "nested_related_companies", "status", "depth"]}
            
            if parent_name:
                node_data["source_company_name"] = parent_name
            if parent_url:
                node_data["source_profile_url"] = parent_url
            
            # Add to flattened list
            flattened_data.append(node_data)
            
            # Recurse for related companies
            for related_company in company_node.get("related_companies", []):
                flatten_recursive(related_company, node_data.get("Name"), node_data.get("profile_url"))
            
            # Recurse for nested related companies (from recursive calls)
            for nested_related_company in company_node.get("nested_related_companies", []):
                flatten_recursive(nested_related_company, node_data.get("Name"), node_data.get("profile_url"))


        # Determine if data is a single profile or a list of profiles
        if isinstance(data, dict) and "profile_url" in data:
            flatten_recursive(data)
        elif isinstance(data, list) and data and isinstance(data[0], dict) and "profile_url" in data[0]:
            for company_profile in data:
                flatten_recursive(company_profile)
        else:
            print(f"{COLOR_ORANGE}Warning: CSV save function received data not in expected single or multiple profile format. Attempting to save as-is (may not be well-formatted).{COLOR_RESET}")
            flattened_data = data
            

        if not flattened_data:
            print(f"{COLOR_ORANGE}No flattened data to save to CSV.{COLOR_RESET}")
            return

        # Dynamically collect all possible keys from all dictionaries to ensure complete headers
        all_keys = set()
        for row in flattened_data:
            all_keys.update(row.keys())

        preferred_order_start = ["root_name", "Type", "Source_Type", "Name", "profile_url", "legal_name", "also_known_as", "website_link", "source_company_name", "source_profile_url"]
        remaining_keys = sorted(list(all_keys - set(preferred_order_start)))
        fieldnames = [key for key in preferred_order_start + remaining_keys if key in all_keys] # Ensure only existing keys are in fieldnames
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, extrasaction='ignore') # Ignore extra keys not in fieldnames
            writer.writeheader()
            writer.writerows(flattened_data)
        
        print(f"{COLOR_BLUE}Data saved to {filename}{COLOR_RESET}")
    
    def save_to_json(self, data, filename):
        """Save scraped data to JSON file"""
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(data, jsonfile, indent=2, ensure_ascii=False)
        
        print(f"{COLOR_BLUE}Data saved to {filename}{COLOR_RESET}")
    
    def close(self):
        """Close the browser"""
        print(f"{COLOR_BLUE}Closing browser...{COLOR_RESET}")
        if self.driver:
            self.driver.quit()
        print(f"{COLOR_BLUE}Browser closed.{COLOR_RESET}")

def load_companies_from_json(filepath):
    """Loads a list of companies from a JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            companies = json.load(f)
        print(f"{COLOR_BLUE}Successfully loaded {len(companies)} companies from {filepath}{COLOR_RESET}")
        return companies
    except FileNotFoundError:
        print(f"{COLOR_RED}Error: JSON file not found at {filepath}{COLOR_RESET}")
        return []
    except json.JSONDecodeError as e:
        print(f"{COLOR_RED}Error decoding JSON from {filepath}: {e}{COLOR_RESET}")
        return []
    except Exception as e:
        print(f"{COLOR_RED}An unexpected error occurred while loading JSON: {e}{COLOR_RESET}")
        return []

def main():
    login_url = "https://login-prod.morningstar.com/login?state=hKFo2SBzSDF4WXFqakpSNF9INFcxN0hjb011ZXliV1dFUUV2LaFupWxvZ2luo3RpZNkgOGxUUDJsYm1OZ09YOVJSZW5SWlphYzBycFV3bDZJSESjY2lk2SByWUMwT1V4SDRpV05jbXzPanVwQjh6UnN0dWtlZXZyUg&client=rYC0OUxH4iWNcmzOjupB8zRstukeevrR&protocol=oauth2&redirect_uri=https%3A%2F%2Fmy.pitchbook.com%2Fauth0%2Fcallback&source=bus0155&response_type=code&ext-source=bus0155"
    
    # Path to your JSON file containing company details
    json_filepath = 'selected_for_scraping.json' 

    YOUR_USERNAME = os.getenv("PITCHBOOK_USER")
    YOUR_PASSWORD = os.getenv("PITCHBOOK_PASSWORD")

    LOGIN_SUCCESS_INDICATOR = "#embedded-messaging" 

    scraper = None 
    try:
        scraper = WebScraper(headless=False) 
        
        scraper.driver.get("chrome://version")
        time.sleep(2) # Give it a moment to load

        try:
            profile_path_element = scraper.long_wait.until(
                EC.presence_of_element_located((By.XPATH, "//td[text()='Profile Path']/following-sibling::td"))
            )
            actual_profile_path = profile_path_element.text
            print(f"{COLOR_BLUE}Chrome reports actual Profile Path: {actual_profile_path}{COLOR_RESET}")
            actual_user_data_dir = os.path.dirname(actual_profile_path)
            print(f"{COLOR_BLUE}Chrome reports actual User Data Directory: {actual_user_data_dir}{COLOR_RESET}")
            
            if os.path.normpath(actual_user_data_dir) != os.path.normpath(scraper.scraper_profile_dir):
                print(f"{COLOR_ORANGE}WARNING: User Data Directory mismatch! Expected: {os.path.normpath(scraper.scraper_profile_dir)}, Actual: {os.path.normpath(actual_user_data_dir)}{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_ORANGE}Could not retrieve Chrome's actual profile path from chrome://version. Error: {e}{COLOR_RESET}")

        print(f"{COLOR_BLUE}=== Attempting full login ==={COLOR_RESET}")
        login_success = scraper.login(
            login_url=login_url,
            username=YOUR_USERNAME,  
            password=YOUR_PASSWORD,   
            username_selector="input[name='email']",
            password_selector="input[name='password']",
            login_button_selector="input[type='submit']",
            success_indicator=LOGIN_SUCCESS_INDICATOR 
        )
        
        logged_in_successfully = False 
        if login_success:
            print(f"{COLOR_BLUE}Full login successful!{COLOR_RESET}")
            logged_in_successfully = True
        else:
            print(f"{COLOR_RED}Full login failed.{COLOR_RESET}")
            logged_in_successfully = False
        
        if logged_in_successfully:
            print(f"\n{COLOR_BLUE}=== Initiating Recursive Scraping of Companies from JSON file ==={COLOR_RESET}")
            
            companies_to_scrape = load_companies_from_json(json_filepath)
            all_scraped_companies_data = [] 

            if companies_to_scrape:
                for company_info in companies_to_scrape:
                    root_company_name = company_info.get("root_company_name")
                    pitchbook_id = company_info.get("pitchbook_id")

                    if pitchbook_id:
                        profile_url = f"https://my.pitchbook.com/profile/{pitchbook_id}/company/profile"
                        print(f"\n{COLOR_BLUE}--- Scraping Root Company: {root_company_name} (ID: {pitchbook_id}) ---{COLOR_RESET}")
                        
                        scraped_tree_data = scraper.scrape_profile_and_affiliates(profile_url, max_depth=5) 
                        
                        if scraped_tree_data:
                            scraped_tree_data["root_name"] = root_company_name # Add original name for context under 'root_name'
                            all_scraped_companies_data.append(scraped_tree_data)
                        else:
                            print(f"{COLOR_ORANGE}No data scraped for {root_company_name} ({profile_url}).{COLOR_RESET}")
                    else:
                        print(f"{COLOR_ORANGE}Skipping '{root_company_name}' due to missing or null PitchBook ID.{COLOR_RESET}")
            else:
                print(f"{COLOR_ORANGE}No companies found in the JSON file to scrape or file could not be loaded.{COLOR_RESET}")


            if all_scraped_companies_data:
                print(f"\n{COLOR_BLUE}Completed scraping all companies. Saving aggregated structured data.{COLOR_RESET}")

                scraper.save_to_json(all_scraped_companies_data, 'multi_company_pitchbook_data.json')
        
                scraper.save_to_csv(all_scraped_companies_data, 'all_companies_pitchbook_related_data.csv')
                
                print(f"\n{COLOR_BLUE}--- Sample of Scraped Data (first company's top level) ---{COLOR_RESET}")
                if all_scraped_companies_data and all_scraped_companies_data[0].get("related_companies"):
                    first_company_data = all_scraped_companies_data[0]
                    print(f"\n{COLOR_BLUE}Root Company Name (from JSON): {first_company_data.get('root_name', 'N/A')}{COLOR_RESET}")
                    print(f"{COLOR_BLUE}Root Company URL: {first_company_data.get('profile_url', 'N/A')}{COLOR_RESET}")
                    
                    print(f"\n{COLOR_BLUE}--- Sample of Related Companies for {first_company_data.get('root_name')} ---{COLOR_RESET}")
                    for i, row in enumerate(first_company_data["related_companies"][:5]): 
                        print(f"{COLOR_BLUE}Item {i+1}:{COLOR_RESET}")
                        for key, value in row.items():
                            if isinstance(value, str) and len(value) > 100:
                                print(f"  {COLOR_BLUE}{key}: {value[:97]}...{COLOR_RESET}")
                            else:
                                print(f"  {COLOR_BLUE}{key}: {value}{COLOR_RESET}")
                    print(f"{COLOR_BLUE}--- End Sample ---{COLOR_RESET}")
                else:
                    print(f"{COLOR_ORANGE}No top-level related companies data found to sample for the first company.{COLOR_RESET}")

            else:
                print(f"{COLOR_ORANGE}No data scraped from any of the provided URLs.{COLOR_RESET}")
        else:
            print(f"{COLOR_RED}Failed to log in, cannot initiate recursive scraping.{COLOR_RESET}")
        
        print(f"{COLOR_BLUE}--------------------------------------------------{COLOR_RESET}")

        print(f"{COLOR_BLUE}Keeping browser open for 15 seconds for observation...{COLOR_RESET}")
        time.sleep(15) 

    except Exception as e:
        print(f"{COLOR_RED}An unexpected error occurred in main: {e}{COLOR_RESET}")
    
    finally:
        if scraper:
            print(f"{COLOR_BLUE}Ensuring browser is closed in finally block.{COLOR_RESET}")
            try:
                print(f"\n{COLOR_BLUE}--- BROWSER CONSOLE LOGS ---{COLOR_RESET}")
                for entry in scraper.driver.get_log("browser"):
                    print(f"{COLOR_BLUE}LOG: {entry}{COLOR_RESET}")
                print(f"{COLOR_BLUE}----------------------------{COLOR_RESET}")
            except Exception as log_e:
                print(f"{COLOR_ORANGE}Could not retrieve browser logs: {log_e}{COLOR_RESET}")
            scraper.close()

if __name__ == "__main__":
    main()