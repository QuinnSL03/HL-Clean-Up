import os
import time
import json
import string 
import re 
from urllib.parse import urljoin 
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
from selenium.webdriver.chrome.options import Options

COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_RED = "\033[91m"
COLOR_ORANGE = "\033[33m"
COLOR_YELLOW = "\033[93m"
COLOR_RESET = "\033[0m"


ADD_ACCOUNT_TABLE_NAME_COLUMN_ID = "7689c" 
ADD_ACCOUNT_TABLE_PB_ID_COLUMN_ID = "YOUR_PB_ID_COLUMN_ID_HERE" # Keep this as a placeholder if you don't have it.
ADD_ACCOUNT_TABLE_WEBSITE_COLUMN_ID = "YOUR_WEBSITE_COLUMN_ID_HERE" # Keep this as a placeholder if you don't have it.
ADD_ACCOUNT_TABLE_ACCOUNT_ID_COLUMN_ID = "add30" # The new, correct ID for the Account ID column.

DETAILS_PAGE_LOAD_INDICATOR = "div[data-testid='RetoolWidget:TextWidget2'] h4"
DETAILS_PAGE_ROOT_COMPANY_NAME_SELECTOR = "div[role='gridcell'][data-column-id='e7998'] span[data-is-cell-contents='true']"
DETAILS_PAGE_PITCHBOOK_ID_SELECTOR = "div[role='gridcell'][data-column-id='49266'] span[data-is-cell-contents='true']"
CLEANUP_QUEUE_NAMES_JSON_FILE = 'cleanup_queue_names.json'

COMMON_SUFFIXES = [
    "inc", "llc", "corp", "ltd", "co", "gmbh", "as", "ag", "sarl", "nv", "sa",
    "bv", "oy", "ab", "kft", "plc", "pvt", "pte", "pty", "s.a.", "s.a.r.l.", "n.v.", "s.p.a.",
    "company", "group", "holding", "holdings", "system", "systems", "products", "solutions",
    "technologies", "technology", "inc.", "llc.", "corp.", "ltd.", "co.", "gmbh.", "as.", "ag.",
    "sarl.", "nv.", "sa.", "bv.", "oy.", "ab.", "kft.", "plc.", "pvt.", "pte.", "pty.",
    "limited", "unlimited", "and", "&"
]

SUFFIX_PATTERN = re.compile(r'\b(?:' + '|'.join(re.escape(s) for s in COMMON_SUFFIXES) + r')\b', re.IGNORECASE)

def write_companies_to_review_json(companies_for_review, output_file='companies_to_review.json'):
    """
    Writes the list of companies needing review to a JSON file.
    Appends to the file if it exists, otherwise creates a new one.
    """
    if not companies_for_review:
        print(f"{COLOR_BLUE}No companies to review. Skipping creation of '{output_file}'.{COLOR_RESET}")
        return

    try:
        # Load existing data if file exists
        existing_data = []
        if os.path.exists(output_file):
            with open(output_file, 'r', encoding='utf-8') as f:
                try:
                    existing_data = json.load(f)
                    if not isinstance(existing_data, list): # Handle cases where file is malformed
                        existing_data = []
                        print(f"{COLOR_ORANGE}Warning: '{output_file}' exists but is not a list. Overwriting.{COLOR_RESET}")
                except json.JSONDecodeError:
                    print(f"{COLOR_ORANGE}Warning: '{output_file}' exists but is invalid JSON. Overwriting.{COLOR_RESET}")
                    existing_data = []

        # Add new companies to the existing data, ensuring uniqueness if desired (not implemented for simplicity here)
        existing_data.extend(companies_for_review)

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(existing_data, f, indent=4)
        print(f"{COLOR_GREEN}Companies for review saved to '{output_file}'. Total entries: {len(existing_data)}.{COLOR_RESET}")
    except Exception as e:
        print(f"{COLOR_RED}Error saving companies for review to '{output_file}': {e}{COLOR_RESET}")

def normalize_name(name):
    if not name:
        return ""
    normalized = name.lower()
    normalized = normalized.translate(str.maketrans('', '', string.punctuation))
    normalized = SUFFIX_PATTERN.sub('', normalized)
    normalized = re.sub(r'\s+', ' ', normalized).strip()
    return normalized
def input_company_data(scraper_instance, company_details, add_account_button_selector, companies_for_review):
    """
    Inputs data for a single company node into the Retool search and add accounts fields.
    Collects and returns a list of successfully added Account IDs for this node.
    
    Args:
        scraper_instance (WebScraper): The WebScraper instance.
        company_details (dict): Dictionary containing company data (legal_name, pb_id, etc.).
        add_account_button_selector (str): Selector for the 'Add Account' button.
        companies_for_review (list): List to append companies that need manual review.
    
    Returns:
        list: A consolidated list of Account IDs added for this company node.
    """
    company_name_for_log = company_details.get('legal_name') or company_details.get('Name')
    print(f"{COLOR_BLUE}--- Inputting data for node: {company_name_for_log} (PB ID: {company_details.get('pb_id')}) ---{COLOR_RESET}")
    
    all_added_ids_for_this_node = []

    # Pitchbook ID
    if company_details.get("pb_id"):
        print(f"{COLOR_BLUE}Attempting to search/add by Pitchbook ID: {company_details['pb_id']}{COLOR_RESET}")
        if scraper_instance.enter_data_into_retool_search(company_details["pb_id"], "Pitchbook ID"):
            ids_from_pb_search = scraper_instance.check_and_add_accounts(
                add_account_button_selector=add_account_button_selector,
                source_company_details=None, # No name validation needed for PB ID search
                companies_for_review=companies_for_review
            )
            all_added_ids_for_this_node.extend(ids_from_pb_search)
        time.sleep(1) # Small pause after each attempt

    # Legal Name
    if company_details.get("legal_name"):
        print(f"{COLOR_BLUE}Attempting to search/add by Legal Name: {company_details['legal_name']}{COLOR_RESET}")
        if scraper_instance.enter_data_into_retool_search(company_details["legal_name"], "Name"): 
            ids_from_name_search = scraper_instance.check_and_add_accounts(
                add_account_button_selector=add_account_button_selector,
                source_company_details=company_details, # Pass the full details
                companies_for_review=companies_for_review
            )
            all_added_ids_for_this_node.extend(ids_from_name_search)
        time.sleep(1)

    # Former Names (if exists)
    if company_details.get("former_names"):
        print(f"{COLOR_BLUE}Attempting to search/add by Former Names: {company_details['former_names']}{COLOR_RESET}")
        if scraper_instance.enter_data_into_retool_search(company_details["former_names"], "Name"): 
            ids_from_former_name_search = scraper_instance.check_and_add_accounts(
                add_account_button_selector=add_account_button_selector,
                source_company_details=company_details, # Pass the full details
                companies_for_review=companies_for_review
            )
            all_added_ids_for_this_node.extend(ids_from_former_name_search)
        time.sleep(1)
        
    # Also Known As (if exists)
    if company_details.get("also_known_as"):
        print(f"{COLOR_BLUE}Attempting to search/add by Also Known As: {company_details['also_known_as']}{COLOR_RESET}")
        if scraper_instance.enter_data_into_retool_search(company_details["also_known_as"], "Name"): 
            ids_from_aka_search = scraper_instance.check_and_add_accounts(
                add_account_button_selector=add_account_button_selector,
                source_company_details=company_details, # Pass the full details
                companies_for_review=companies_for_review
            )
            all_added_ids_for_this_node.extend(ids_from_aka_search)
        time.sleep(1)

    # Website (if exists)
    if company_details.get("website_link"):
        print(f"{COLOR_BLUE}Attempting to search/add by Website: {company_details['website_link']}{COLOR_RESET}")
        if scraper_instance.enter_data_into_retool_search(company_details["website_link"], "Website"):
            ids_from_website_search = scraper_instance.check_and_add_accounts(
                add_account_button_selector=add_account_button_selector,
                source_company_details=None, # No name validation needed for website search
                companies_for_review=companies_for_review
            )
            all_added_ids_for_this_node.extend(ids_from_website_search)
        time.sleep(1)

    print(f"{COLOR_BLUE}Finished processing all search fields for node: {company_name_for_log}.{COLOR_RESET}")
    return list(set(all_added_ids_for_this_node)) # Return unique IDs


def process_pitchbook_hierarchy(scraper_instance, company_node, add_account_button_selector, companies_for_review, processed_nodes_set):
    """
    Recursively processes a Pitchbook company node and its affiliates,
    inputting their data into Retool and embedding the added Account IDs.
    This version uses a set to prevent re-processing of any node.

    Args:
        scraper_instance (WebScraper): The WebScraper instance.
        company_node (dict): The current company node (can be root or affiliate) from Pitchbook JSON.
        add_account_button_selector (str): Selector for the 'Add Account' button.
        companies_for_review (list): List to append companies that need manual review.
        processed_nodes_set (set): A set of unique identifiers for nodes already processed in this script run.
    """
    if not isinstance(company_node, dict):
        print(f"{COLOR_ORANGE}Warning: Skipping non-dictionary company_node in hierarchy: {company_node}{COLOR_RESET}")
        return

    # --- Gatekeeper Logic ---
    node_name = company_node.get('legal_name') or company_node.get('Name')
    # Create a unique ID for the node: prefer Pitchbook ID, fall back to normalized name.
    unique_id = company_node.get('pb_id') or normalize_name(node_name)

    if not unique_id:
        print(f"{COLOR_ORANGE}Warning: Skipping node with no usable identifier: {node_name}{COLOR_RESET}")
        return

    if unique_id in processed_nodes_set:
        print(f"{COLOR_YELLOW}Node '{node_name}' (ID: {unique_id}) has already been processed in this run. Skipping.{COLOR_RESET}")
        return

    print(f"{COLOR_BLUE}Processing node '{node_name}' (ID: {unique_id}). Adding to processed set.{COLOR_RESET}")
    processed_nodes_set.add(unique_id)
    # --- End Gatekeeper Logic ---

    # --- Input data for the current company node and get back the added IDs ---
    added_ids = input_company_data(scraper_instance, company_node, add_account_button_selector, companies_for_review)
    
    # --- Add the collected IDs to the current company node in the dictionary ---
    if 'added_account_ids' not in company_node:
        company_node['added_account_ids'] = []
    
    company_node['added_account_ids'].extend(added_ids)
    company_node['added_account_ids'] = list(set(company_node['added_account_ids'])) # Keep it unique
    
    if added_ids:
        print(f"{COLOR_GREEN}Appended Account IDs {added_ids} to node '{node_name}'.{COLOR_RESET}")

    # --- Process nested companies ---
    related_companies_list = company_node.get('related_companies')
    if related_companies_list and isinstance(related_companies_list, list):
        print(f"{COLOR_YELLOW}DEBUG: Found {len(related_companies_list)} entries in 'related_companies'. Processing them.{COLOR_RESET}")
        for related_company in related_companies_list:
            process_pitchbook_hierarchy(scraper_instance, related_company, add_account_button_selector, companies_for_review, processed_nodes_set)
    
    nested_related_companies_list = company_node.get('nested_related_companies')
    if nested_related_companies_list and isinstance(nested_related_companies_list, list):
        print(f"{COLOR_YELLOW}DEBUG: Found {len(nested_related_companies_list)} entries in 'nested_related_companies'. Processing them.{COLOR_RESET}")
        for nested_related_company in nested_related_companies_list:
            process_pitchbook_hierarchy(scraper_instance, nested_related_company, add_account_button_selector, companies_for_review, processed_nodes_set)


def are_names_similar(query_name, result_name):
    """
    Compares a search query name with a result name for similarity.
    Returns True if:
    1. Normalized query exactly matches normalized result.
    2. All significant words (length > 2) from normalized query are present in normalized result.
    """
    if not query_name or not result_name:
        return False

    normalized_query = normalize_name(query_name)
    normalized_result = normalize_name(result_name)

    # Strict equality after normalization
    if normalized_query == normalized_result:
        return True

    # Check if all significant words from query are a subset of result words
    query_words = set(word for word in normalized_query.split() if len(word) > 2)
    result_words = set(normalized_result.split())

    if query_words and query_words.issubset(result_words):
        return True
    
    return False

class WebScraper:

    # Load indicator: Wait for the first row of the details table/grid to appear.
    

    # Root Company Name selector: Targets the span within the gridcell with data-column-id="e7998"
    DETAILS_PAGE_ROOT_COMPANY_NAME_SELECTOR = "div[role='gridcell'][data-column-id='e7998'] span[data-is-cell-contents='true']"

    # Pitchbook ID selector: Targets the span within the gridcell with data-column-id="49266"
    DETAILS_PAGE_PITCHBOOK_ID_SELECTOR = "div[role='gridcell'][data-column-id='49266'] span[data-is-cell-contents='true']"
    # Updated load indicator to be an element from the name's container
   
    def __init__(self, headless=False, profile_name="default_scraper_profile"):
        """Initialize the web scraper with Chrome driver."""
        self.options = Options()

        if headless:
            self.options.add_argument('--headless')
        
        self.options.add_argument('--ignore-certificate-errors')
        self.options.add_argument('--no-sandbox')
        self.options.add_argument('--disable-dev-shm-usage')
        self.options.add_argument('--disable-gpu')
        self.options.add_argument('--window-size=1920,1080')
        
        self.scraper_profile_dir = os.path.join(os.path.expanduser("~"), "chrome_scraper_profiles", profile_name)

        if not os.path.exists(self.scraper_profile_dir):
            try:
                os.makedirs(self.scraper_profile_dir, exist_ok=True)
                print(f"{COLOR_BLUE}Created new scraper profile directory: {self.scraper_profile_dir}{COLOR_RESET}")
            except Exception as e:
                print(f"{COLOR_RED}ERROR: Could not create scraper profile directory {self.scraper_profile_dir}. Check permissions. Error: {e}{COLOR_RESET}")
                raise

        self.options.add_argument(f"--user-data-dir={self.scraper_profile_dir}")
        
        chromedriver_path = "C:/Users/QLindse25/Downloads/chromedriver-win64/chromedriver-win64/chromedriver.exe" 
        service = Service(chromedriver_path)

        self.driver = webdriver.Chrome(service=service, options=self.options)
        self.driver.maximize_window() # Maximize window to make manual login easier
        self.wait = WebDriverWait(self.driver, 10) # Default wait time
        self.logged_in = False
    def find_and_click_row_with_retry(self, scrollable_element_selector, table_id, target_index):
        """
        Robustly finds a row by its index in a lazy-loaded table, scrolling if necessary,
        and clicks it. Includes a fallback to a JavaScript click.

        Args:
            scrollable_element_selector (str): The CSS selector for the scrollable container of the table.
            table_id (str): The ID of the table to search within.
            target_index (int): The data-item-index of the row to find and click.

        Returns:
            bool: True if the row was successfully clicked, False otherwise.
        """
        max_find_attempts = 5  # Total attempts to find the row
        js_click_script = "arguments[0].click();"
        clickable_name_cell_selector = (
            f"div#{table_id} div[role='row'][data-item-index='{target_index}'] "
            f"div[role='gridcell'][data-column-id='787e6'] div[data-is-cell-contents='true'][class*='_isClickable_']"
        )

        for attempt in range(max_find_attempts):
            print(f"{COLOR_BLUE}Attempt {attempt + 1}/{max_find_attempts} to find and click row {target_index}...{COLOR_RESET}")
            try:
                # First, try to find and click the element directly (it might be visible)
                target_cell = WebDriverWait(self.driver, 5).until( # Shorter wait for direct find
                    EC.element_to_be_clickable((By.CSS_SELECTOR, clickable_name_cell_selector))
                )
                target_cell.click()
                print(f"{COLOR_GREEN}Standard click successful for row {target_index}.{COLOR_RESET}")
                return True
            except TimeoutException:
                # If not found directly, perform a scroll and search routine
                print(f"{COLOR_ORANGE}Row {target_index} not immediately visible. Starting scroll search...{COLOR_RESET}")
                scrollable_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, scrollable_element_selector)))
                
                # Scroll down a bit to trigger loading
                self.driver.execute_script("arguments[0].scrollTop += 500;", scrollable_element)
                time.sleep(1)
                
                # Try to find it again after scrolling down
                try:
                    target_cell = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, clickable_name_cell_selector)))
                    target_cell.click()
                    print(f"{COLOR_GREEN}Standard click successful for row {target_index} after scrolling.{COLOR_RESET}")
                    return True
                except TimeoutException:
                    # If still not found, scroll up to trigger loading in the other direction
                    self.driver.execute_script("arguments[0].scrollTop -= 700;", scrollable_element)
                    time.sleep(1)
                    
                    # Last attempt in this cycle with a JS click fallback
                    try:
                        element_to_force_click = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, clickable_name_cell_selector)))
                        self.driver.execute_script(js_click_script, element_to_force_click)
                        print(f"{COLOR_GREEN}JavaScript click successful for row {target_index} after scrolling.{COLOR_RESET}")
                        return True
                    except Exception as final_e:
                        print(f"{COLOR_ORANGE}Could not find row {target_index} on attempt {attempt + 1}. Error: {final_e}{COLOR_RESET}")
                        # On the last attempt, this will fall through and the function will return False

        print(f"{COLOR_RED}All {max_find_attempts} attempts failed to find and click row {target_index}.{COLOR_RESET}")
        return False

    def close(self):
        """Closes the browser."""
        if self.driver:
            self.driver.quit()
            print(f"{COLOR_BLUE}Browser closed.{COLOR_RESET}")

    def check_login_status(self, test_url, success_indicator, check_timeout=30):
        """
        Checks if the browser is already logged in by navigating to a protected page
        and looking for a success indicator.
        
        Args:
            test_url (str): A URL that requires login to access (e.g., your dashboard).
            success_indicator (str): XPath for an element that is only present
                                     when successfully logged in.
            check_timeout (int): How long to wait for the success indicator.
        Returns:
            bool: True if logged in, False otherwise.
        """
        print(f"{COLOR_BLUE}Attempting to verify existing session on: {test_url}{COLOR_RESET}")
        try:
            self.driver.get(test_url)
            print(f"{COLOR_BLUE}Current URL after navigation attempt: {self.driver.current_url}{COLOR_RESET}")
            print(f"{COLOR_BLUE}Looking for success indicator (XPath): '{success_indicator}' for up to {check_timeout} seconds...{COLOR_RESET}")
            
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, success_indicator)) 
            )
            print(f"{COLOR_GREEN}Success indicator found. Existing session appears active.{COLOR_RESET}")
            self.logged_in = True
            return True
        except TimeoutException:
            print(f"{COLOR_ORANGE}Success indicator not found on {test_url} within {check_timeout} seconds. Session may be expired or invalid.{COLOR_RESET}")
            self.logged_in = False
            return False
        except Exception as e:
            print(f"{COLOR_RED}Error during login status check: {e}{COLOR_RESET}")
            self.logged_in = False
            return False

    def wait_for_sso_login(self, login_url, success_indicator, wait_duration=180):
        """
        Navigates to the login URL and waits for the user to complete a manual SSO login.
        
        Args:
            login_url (str): The initial login page URL where the SSO button is.
            success_indicator (str): The XPath for an element that appears after successful login
                                     on the final destination page (e.g., your dashboard).
            wait_duration (int): How many seconds to wait for the user to log in.
        """
        try:
            print(f"{COLOR_BLUE}Navigating to initial login page: {login_url}{COLOR_RESET}")
            self.driver.get(login_url)
            
            print(f"\n{COLOR_YELLOW}******************************************************************{COLOR_RESET}")
            print(f"{COLOR_YELLOW}* ACTION REQUIRED: Please complete the SSO login in the browser. *{COLOR_RESET}")
            print(f"{COLOR_YELLOW}* You have {wait_duration} seconds to sign in.                           *{COLOR_RESET}")
            print(f"{COLOR_YELLOW}******************************************************************{COLOR_RESET}")
            
            # Wait for the success indicator to appear on the final dashboard page
            # This indicates the user has completed the SSO process and been redirected.
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, success_indicator))
            )
            
            print(f"\n{COLOR_GREEN}Login Successful! Success indicator found after manual SSO login.{COLOR_RESET}")
            self.logged_in = True
            return True
        
        except TimeoutException:
            print(f"{COLOR_RED}Login timed out. The success indicator was not found after {wait_duration} seconds.{COLOR_RESET}")
            print(f"{COLOR_RED}Please ensure you completed the login and were redirected to the correct page.{COLOR_RESET}")
            self.driver.save_screenshot(f"retool_sso_timeout_{int(time.time())}.png")
            print(f"{COLOR_ORANGE}Screenshot saved for debugging.{COLOR_RESET}")
            return False
        except Exception as e:
            print(f"{COLOR_RED}An unexpected error occurred while waiting for SSO login: {e}{COLOR_RESET}")
            return False

    def scrape_cleanup_queue_names(self, retool_dashboard_url, output_json_file=None):
        """
        Scrapes root company name, Pitchbook ID (by clicking into each detail page),
        and data-item-index from all entries in the Cleanup Queue table.
        This function is designed to be called by a separate script for initial data collection.
        It now uses a robust find-and-click retry mechanism.

        Args:
            retool_dashboard_url (str): The URL of the Cleanup Queue page to navigate to.
            output_json_file (str, optional): Path to a JSON file where the scraped data will be saved.
                                             If None, data is not saved to a file.

        Returns:
            list: A list of dictionaries, where each dictionary contains
                  'root_company_name', 'pitchbook_id', and 'data_item_index' for each unique entry.
        """
        print(f"{COLOR_BLUE}Starting to scrape Cleanup Queue entries for names, PIDs, and data-item-indices...{COLOR_RESET}")

        cleanup_queue_table_id = "CleanupQueueEntryTable--0" 
        scrollable_element_selector = f"div#{cleanup_queue_table_id} div._outer_1y096_2[data-testid='TableWrapper::ScrollableContainer']"

        collected_entries = {} # {data_item_index: {"root_company_name": ..., "pitchbook_id": ..., "data_item_index": ...}}
        
        # --- Initial navigation and discovery of all indices ---
        print(f"{COLOR_BLUE}Ensuring we are on Cleanup Queue page for discovery: {retool_dashboard_url}{COLOR_RESET}")
        self.driver.get(retool_dashboard_url)
        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.ID, cleanup_queue_table_id)),
                message=f"Timeout waiting for Cleanup Queue table (ID: {cleanup_queue_table_id}) to be present for discovery."
            )
            print(f"{COLOR_BLUE}Cleanup Queue table is present.{COLOR_RESET}")
            time.sleep(3) # Give some buffer for table contents to fully render.
        except Exception as e:
            print(f"{COLOR_RED}Error during initial Cleanup Queue page load or scroll for discovery: {e}{COLOR_RESET}")
            self.driver.save_screenshot(f"cleanup_queue_discovery_error_{int(time.time())}.png")
            return [] # Cannot proceed without the table

        # Discover all indices by scrolling
        discovered_indices = set()
        last_discovered_count = -1
        scroll_attempts_discovery = 0
        max_scroll_attempts_discovery = 100 # Increased scroll attempts for discovery
        
        scrollable_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, scrollable_element_selector)))
        self.driver.execute_script("arguments[0].scrollTop = 0;", scrollable_element)
        time.sleep(1)

        while scroll_attempts_discovery < max_scroll_attempts_discovery:
            current_visible_rows_elements = self.driver.find_elements(By.CSS_SELECTOR, f"div#{cleanup_queue_table_id} div[role='rowgroup'] div[role='row'][data-item-index]")
            for row_elem in current_visible_rows_elements:
                idx = row_elem.get_attribute('data-item-index')
                if idx is not None:
                    discovered_indices.add(int(idx))

            if len(discovered_indices) == last_discovered_count:
                print(f"{COLOR_BLUE}No new unique indices discovered after scroll. Assuming end of content. Total discovered: {len(discovered_indices)}.{COLOR_RESET}")
                break
            
            last_discovered_count = len(discovered_indices)
            
            self.driver.execute_script("arguments[0].scrollTop += arguments[0].clientHeight;", scrollable_element)
            time.sleep(1.5)
            scroll_attempts_discovery += 1

        sorted_discovered_indices = sorted(list(discovered_indices))
        print(f"{COLOR_GREEN}Discovered {len(sorted_discovered_indices)} unique Cleanup Queue entries for detailed scraping.{COLOR_RESET}")

        # --- Loop through each discovered index, click, scrape details, and navigate back ---
        for target_index_int in sorted_discovered_indices:
            print(f"\n{COLOR_BLUE}--- Processing entry with data-item-index='{target_index_int}' ---{COLOR_RESET}")
            try:
                # 1. Ensure we are on Cleanup Queue page before starting
                self.driver.get(retool_dashboard_url)
                WebDriverWait(self.driver, 30).until(
                    EC.presence_of_element_located((By.ID, cleanup_queue_table_id)),
                    message=f"Timeout waiting for Cleanup Queue table before processing row {target_index_int}."
                )
                time.sleep(3)

                # 2. Use the robust find and click method
                click_successful = self.find_and_click_row_with_retry(
                    scrollable_element_selector=scrollable_element_selector,
                    table_id=cleanup_queue_table_id,
                    target_index=target_index_int
                )

                if click_successful:
                    time.sleep(2) # Delay after click to allow navigation to details page

                    # 3. Scrape details (name and PB ID) from the opened details page
                    scraped_root_company_name, scraped_pitchbook_id = self.scrape_details_from_entry_page()
                    
                    if scraped_root_company_name or scraped_pitchbook_id:
                        collected_entries[target_index_int] = {
                            "root_company_name": scraped_root_company_name,
                            "pitchbook_id": scraped_pitchbook_id,
                            "data_item_index": target_index_int
                        }
                        print(f"{COLOR_GREEN}Scraped: Name='{scraped_root_company_name}', PB ID='{scraped_pitchbook_id}' for index {target_index_int}.{COLOR_RESET}")
                    else:
                        print(f"{COLOR_ORANGE}No data scraped from details page for entry {target_index_int}. Skipping.{COLOR_RESET}")
                else:
                    print(f"{COLOR_RED}Could not click row {target_index_int} after all attempts. Skipping.{COLOR_RESET}")
            except Exception as e:
                print(f"{COLOR_RED}An unexpected error occurred while processing entry {target_index_int}: {e}. Skipping.{COLOR_RESET}")
                self.driver.save_screenshot(f"scrape_details_unexpected_error_{target_index_int}_{int(time.time())}.png")

        final_scraped_data = list(collected_entries.values())
        print(f"{COLOR_GREEN}\nFinished detailed scraping of Cleanup Queue. Total unique entries with details: {len(final_scraped_data)}.{COLOR_RESET}")

        if output_json_file:
            try:
                with open(output_json_file, 'w', encoding='utf-8') as f:
                    json.dump(final_scraped_data, f, indent=4)
                print(f"{COLOR_GREEN}Scraped data saved to '{output_json_file}'.{COLOR_RESET}")
            except Exception as e:
                print(f"{COLOR_RED}Error saving scraped data to JSON file '{output_json_file}': {e}{COLOR_RESET}")

        return final_scraped_data

    def scrape_details_from_entry_page(self):
        """
        Scrapes the root company name and Pitchbook ID from the currently loaded
        details page. This function assumes the browser is already on the details page.

        Returns:
            tuple: (root_company_name, pitchbook_id) or (None, None) if not found.
        """
        print(f"{COLOR_BLUE}Scraping data from details page...{COLOR_RESET}")
        root_company_name = None
        pitchbook_id = None

        try:
            # 1. Wait for the primary content of the details page (the H4 with dynamic name) to load
            # First, wait for the element to be present.
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, DETAILS_PAGE_LOAD_INDICATOR)),
                message="Timeout waiting for details page's Root Name H4 element to be present."
            )
            
            # Then, wait for its text to contain more than just "Root: " (i.e., the actual name has loaded)
            WebDriverWait(self.driver, 30).until( # Increased this specific wait to 30s
                lambda driver: driver.find_element(By.CSS_SELECTOR, DETAILS_PAGE_LOAD_INDICATOR).text.strip() not in ["Root:", "Root: "],
                message="Timeout waiting for Root Name H4 text to load actual company name."
            )
            
            print(f"{COLOR_BLUE}Details page loaded successfully, found dynamic root name H4.{COLOR_RESET}")
            time.sleep(1) # Give a little extra time for other data to settle

            # --- Re-locate the main row element immediately before using it ---
            # This is crucial to avoid StaleElementReferenceException if the DOM re-renders.
            # Use the previous DETAILS_PAGE_LOAD_INDICATOR for the main row structure
            details_page_row_element = self.driver.find_element(By.CSS_SELECTOR, "div[role='row'][data-item-index='0']")
            # --- END ADDED ---

            # 2. Scrape Root Company Name using the specific data-column-id
            try:
                # Use the re-located details_page_row_element as the base for finding children
                name_element = WebDriverWait(details_page_row_element, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, DETAILS_PAGE_ROOT_COMPANY_NAME_SELECTOR)),
                    message="Root Company Name element not present within timeout."
                )
                root_company_name = name_element.text.strip()
                print(f"{COLOR_BLUE}Scraped Root Company Name: {root_company_name}{COLOR_RESET}")
            except TimeoutException:
                print(f"{COLOR_ORANGE}Root Company Name element not found or loaded within timeout. Setting to None.{COLOR_RESET}")
                root_company_name = None
            except NoSuchElementException:
                print(f"{COLOR_ORANGE}Root Company Name element not found on details page. Setting to None.{COLOR_RESET}")
                root_company_name = None
            except Exception as e:
                print(f"{COLOR_RED}Error scraping Root Company Name: {e}{COLOR_RESET}")
                root_company_name = None

            # 3. Scrape Pitchbook ID using the specific data-column-id
            try:
                # Use the re-located details_page_row_element as the base for finding children
                pb_id_element = WebDriverWait(details_page_row_element, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, DETAILS_PAGE_PITCHBOOK_ID_SELECTOR)),
                    message="Pitchbook ID element not present within timeout."
                )
                pitchbook_id = pb_id_element.text.strip()
                print(f"{COLOR_BLUE}Scraped Pitchbook ID: {pitchbook_id}{COLOR_RESET}")
            except TimeoutException:
                print(f"{COLOR_ORANGE}Pitchbook ID element not found or loaded within timeout. Setting to None.{COLOR_RESET}")
                pitchbook_id = None
            except NoSuchElementException:
                print(f"{COLOR_ORANGE}Pitchbook ID element not found on details page. Setting to None.{COLOR_RESET}")
                pitchbook_id = None
            except Exception as e:
                print(f"{COLOR_RED}Error scraping Pitchbook ID: {e}{COLOR_RESET}")
                pitchbook_id = None

            if not root_company_name and not pitchbook_id:
                print(f"{COLOR_ORANGE}Neither Root Company Name nor Pitchbook ID could be scraped from the details page.{COLOR_RESET}")

        except TimeoutException as te:
            print(f"{COLOR_RED}Timeout waiting for details page to load ({DETAILS_PAGE_LOAD_INDICATOR}): {te}{COLOR_RESET}")
            self.driver.save_screenshot(f"details_page_load_timeout_{int(time.time())}.png") 
        except Exception as e:
            print(f"{COLOR_RED}An unexpected error occurred while scraping details page: {e}{COLOR_RESET}")
            self.driver.save_screenshot(f"details_page_scraping_error_{int(time.time())}.png")

        return root_company_name, pitchbook_id
    
    def click_cleanup_queue_entry_by_index(self, index=0):
        """
        Locates the 'Cleanup Queue' table and clicks on the entry at the specified index.
        Assumes the table is present and visible on the current page.
        
        Args:
            index (int): The zero-based index of the entry to click (default is 0 for the first entry).
        """
        print(f"{COLOR_BLUE}Attempting to click entry {index} in Cleanup Queue table...{COLOR_RESET}")
        
        # Selector for the main Cleanup Queue table container (using data-testid for the table widget)
        table_container_selector = "div[data-testid='RetoolWidget:TableWidget2']"
        
        # Selector for the data row within that table, using the dynamic index.
        # We then look for a clickable element within that row.
        entry_clickable_cell_selector = (
            f"{table_container_selector} div[role='row'][data-row-index='{index}'] " 
            f"div[role='gridcell'] div[class*='isClickable']" 
        )
        
        try:
            # Wait for the table to be present and then for the specified clickable cell
            entry_element = self.wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, entry_clickable_cell_selector))
            )
            
            entry_element.click()
            print(f"{COLOR_GREEN}Successfully clicked entry {index} in the Cleanup Queue table.{COLOR_RESET}")
            return True
        except TimeoutException:
            print(f"{COLOR_ORANGE}Timeout waiting for Cleanup Queue entry {index} to be clickable.{COLOR_RESET}")
            return False
        except NoSuchElementException:
            print(f"{COLOR_ORANGE}Cleanup Queue entry {index} element not found.{COLOR_RESET}")
            return False
        except Exception as e:
            print(f"{COLOR_RED}Error clicking Cleanup Queue entry {index}: {e}{COLOR_RESET}")
            return False
        
    def check_and_add_accounts(self, add_account_button_selector, source_company_details=None, companies_for_review=None):
        OK_BUTTON_SELECTOR = "//button[./span[text()='OK']]" 
        """
        Validates and clicks checkboxes for accounts. Scrapes the Account ID for each checked row.
        If a name match is not 100% exact, it is logged for review and not clicked.
        
        Args:
            add_account_button_selector (str): Selector for the 'Add Account' button.
            source_company_details (dict, optional): Full details of the company being searched for.
            companies_for_review (list, optional): List to append companies that need manual review.
            
        Returns:
            list: A list of Account IDs that were successfully checked.
        """
        print(f"{COLOR_BLUE}Waiting for search results to populate the table or for empty state...{COLOR_RESET}")
        
        added_account_ids = [] # List to store the scraped Account IDs
        
        time.sleep(2) # Initial general buffer

        first_data_row_selector = "div[data-testid^='RetoolWidget:TableWidget'] div[role='row'][data-item-index='0']:not([data-is-header='true'])"
        no_results_selector = "div[data-testid='TableEmptyState::Container']"

        try:
            # Custom Expected Condition to wait for either data or no-results message
            class wait_for_data_or_no_results:
                def __init__(self, data_sel, no_results_sel):
                    self.data_selector = data_sel
                    self.no_results_selector = no_results_sel

                def __call__(self, driver):
                    try:
                        data_row_element = driver.find_element(By.CSS_SELECTOR, self.data_selector)
                        if data_row_element.is_displayed(): return "data_found"
                    except NoSuchElementException: pass
                    try:
                        no_results_element = driver.find_element(By.CSS_SELECTOR, self.no_results_selector)
                        if no_results_element.is_displayed(): return "no_results"
                    except NoSuchElementException: pass
                    return False

            table_state = WebDriverWait(self.driver, 20).until(
                wait_for_data_or_no_results(first_data_row_selector, no_results_selector),
                message="Timed out waiting for table to show data or 'No rows found' message."
            )

            if table_state == "no_results":
                print(f"{COLOR_ORANGE}No search results found. Halting this operation.{COLOR_RESET}")
                return added_account_ids # Return empty list
            
            print(f"{COLOR_BLUE}Search results detected. Processing rows...{COLOR_RESET}")
            time.sleep(3)

            table_container_id = "AddAccount--0"
            scrollable_element_selector = f"div#{table_container_id} div[data-testid='TableWrapper::ScrollableContainer']"
            
            processed_row_indices = set()
            clicked_count = 0
            
            last_number_of_rows = 0
            scroll_attempts = 0
            max_total_scroll_attempts = 50
            js_click_script = "var e=arguments[0];e&&e.click();return!0;"

            while scroll_attempts < max_total_scroll_attempts:
                current_visible_rows_elements = self.driver.find_elements(By.CSS_SELECTOR, f"div#{table_container_id} div[role='rowgroup'] div[role='row'][data-item-index]")
                
                for row_element in current_visible_rows_elements:
                    try:
                        row_index_str = row_element.get_attribute('data-item-index')
                        if row_index_str is None or row_index_str in processed_row_indices:
                            continue
                        
                        processed_row_indices.add(row_index_str)

                        if row_element.get_attribute('aria-selected') == 'false':
                            checkbox_gridcell = row_element.find_element(By.CSS_SELECTOR, "div[role='gridcell'][data-is-row-selection='true']")
                            perform_click = False

                            # If we are searching by name, we need to validate.
                            if source_company_details:
                                name_to_match = source_company_details.get("legal_name") or source_company_details.get("Name")
                                result_name_element = row_element.find_element(By.CSS_SELECTOR, f"div[role='gridcell'][data-column-id='{ADD_ACCOUNT_TABLE_NAME_COLUMN_ID}'] span[data-is-cell-contents='true']")
                                result_name = result_name_element.text.strip()
                                
                                normalized_match_name = normalize_name(name_to_match)
                                normalized_result_name = normalize_name(result_name)
                                
                                # Strict, 100% match after normalization
                                if normalized_match_name == normalized_result_name:
                                    print(f"{COLOR_GREEN}Exact name match validated: '{name_to_match}' == '{result_name}'.{COLOR_RESET}")
                                    perform_click = True
                                # Fuzzy match, but not exact. Add to review and DO NOT click.
                                elif are_names_similar(name_to_match, result_name):
                                    print(f"{COLOR_ORANGE}Fuzzy match found: '{name_to_match}' is SIMILAR to '{result_name}'. Adding to review list and SKIPPING click.{COLOR_RESET}")
                                    if companies_for_review is not None:
                                        review_entry = source_company_details.copy()
                                        review_entry['review_reason'] = f"Fuzzy match with Retool result: '{result_name}'"
                                        review_entry.pop('related_companies', None)
                                        review_entry.pop('nested_related_companies', None)
                                        companies_for_review.append(review_entry)
                                    perform_click = False
                                # No significant similarity.
                                else:
                                    perform_click = False
                            else: # Not searching by name (e.g., PB ID or Website directly), so it's a direct match.
                                perform_click = True
                                print(f"{COLOR_BLUE}Not searching by name. Selecting row {row_index_str}.{COLOR_RESET}")

                            if perform_click:
                                # Scrape the Account ID from this row *before* clicking
                                try:
                                    account_id_element = row_element.find_element(By.CSS_SELECTOR, f"div[role='gridcell'][data-column-id='{ADD_ACCOUNT_TABLE_ACCOUNT_ID_COLUMN_ID}'] a")
                                    account_id = account_id_element.text.strip()
                                    if account_id:
                                        added_account_ids.append(account_id)
                                        print(f"{COLOR_GREEN}Scraped Account ID '{account_id}' for row {row_index_str}.{COLOR_RESET}")
                                except NoSuchElementException:
                                    print(f"{COLOR_ORANGE}Could not find Account ID for row {row_index_str}. Will click but not record ID.{COLOR_RESET}")
                                
                                if self.driver.execute_script(js_click_script, checkbox_gridcell):
                                    clicked_count += 1
                                    print(f"{COLOR_GREEN}Clicked checkbox for row {row_index_str}.{COLOR_RESET}")
                                    time.sleep(0.1)
                    except StaleElementReferenceException:
                        print(f"{COLOR_ORANGE}Stale element encountered in check_and_add_accounts. Re-scanning...{COLOR_RESET}")
                        break
                    except Exception as e:
                        print(f"{COLOR_RED}Error during row processing in check_and_add_accounts: {e}{COLOR_RESET}")
                        pass # Ignore errors on individual rows and continue

                if len(processed_row_indices) == last_number_of_rows:
                    print(f"{COLOR_BLUE}No new unique rows discovered after scroll. Assuming end of content.{COLOR_RESET}")
                    break
                
                last_number_of_rows = len(processed_row_indices)
                scrollable_element = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, scrollable_element_selector)))
                self.driver.execute_script("arguments[0].scrollTop += arguments[0].clientHeight;", scrollable_element)
                time.sleep(1.5)
                scroll_attempts += 1

            print(f"{COLOR_GREEN}Finished processing all available account rows. Total clicked: {clicked_count}.{COLOR_RESET}")
            
            if clicked_count == 0:
                print(f"{COLOR_ORANGE}No accounts were selected for addition. Halting this operation.{COLOR_RESET}")
                return added_account_ids # Return any IDs that might have been scraped but not added

            time.sleep(1)

            # --- Add Account button ---
            button_script = "var b=document.querySelector(arguments[0]);if(b){b.click();return true;}return false;"
            button_clicked = False
            start_time = time.time()
            timeout = 20
            while time.time() - start_time < timeout:
                try:
                    if self.driver.execute_script(button_script, add_account_button_selector):
                        button_clicked = True
                        print(f"{COLOR_GREEN}JavaScript click successful on 'Add Account' button.{COLOR_RESET}")
                        break
                except Exception as e:
                    print(f"{COLOR_ORANGE}Error during JavaScript click attempt for button: {e}{COLOR_RESET}")
                time.sleep(0.5)

            if not button_clicked:
                print(f"{COLOR_RED}Failed to click 'Add Account' button via JavaScript after {timeout} seconds. Cannot proceed.{COLOR_RED}")
                self.driver.save_screenshot(f"CRITICAL_js_button_failed_{int(time.time())}.png")
                return added_account_ids # Return what we have so far

            time.sleep(2)

            # --- Click the "OK" confirmation button ---
            print(f"{COLOR_BLUE}Attempting to click the 'OK' confirmation button...{COLOR_RESET}")
            ok_button_script = "var b=document.evaluate(arguments[0],document,null,XPathResult.FIRST_ORDERED_NODE_TYPE,null).singleNodeValue;if(b){b.click();return true;}return false;"
            ok_button_clicked = False
            start_time_ok = time.time()
            timeout_ok = 10
            while time.time() - start_time_ok < timeout_ok:
                try:
                    if self.driver.execute_script(ok_button_script, OK_BUTTON_SELECTOR):
                        ok_button_clicked = True
                        print(f"{COLOR_GREEN}'OK' button clicked successfully.{COLOR_RESET}")
                        break
                except Exception as e:
                    print(f"{COLOR_ORANGE}Error during JavaScript click attempt for 'OK' button: {e}{COLOR_RESET}")
                time.sleep(0.5)

            if not ok_button_clicked:
                print(f"{COLOR_RED}Failed to click 'OK' button via JavaScript after {timeout_ok} seconds. Proceeding without confirmation.{COLOR_RED}")
                self.driver.save_screenshot(f"CRITICAL_js_ok_button_failed_{int(time.time())}.png")
            else:
                time.sleep(2)

            return added_account_ids

        except TimeoutException:
            print(f"{COLOR_ORANGE}No search results found (timed out waiting for data). Halting this operation.{COLOR_RESET}")
            self.driver.save_screenshot(f"retool_no_data_found_timeout_{int(time.time())}.png")
            return added_account_ids
        except Exception as e:
            print(f"{COLOR_RED}An unexpected error occurred during check and add accounts: {e}{COLOR_RESET}")
            self.driver.save_screenshot(f"retool_add_account_unexpected_error_{int(time.time())}.png")
            return added_account_ids


    def enter_data_into_retool_search(self, search_value, search_type_label):
        """
        Enters a value into the Retool search box and selects the corresponding type from the dropdown.
        This method is now self-contained for clearing and inputting, with retry logic.
        
        Args:
            search_value (str): The text to enter into the main search box.
            search_type_label (str): The visible text of the option to type into the dropdown's input.
        """
        if not search_value:
            print(f"{COLOR_BLUE}Skipping search for '{search_type_label}' as value is empty.{COLOR_RESET}")
            return False

        MAX_SEARCH_RETRIES = 3 # Max attempts for the entire search process
        SEARCH_RETRY_DELAY = 5 # Seconds to wait before retrying a failed search

        for attempt in range(1, MAX_SEARCH_RETRIES + 1):
            print(f"{COLOR_BLUE}Attempt {attempt}/{MAX_SEARCH_RETRIES}: Attempting to enter '{search_value}' for type '{search_type_label}'...{COLOR_RESET}")

            # Selectors for the main search input and the dropdown's input
            search_input_id = "Search2--0" 
            dropdown_input_id = "selectSearch--0" 
            fetching_mask_selector = "div[data-testid='FetchingMask::WidgetFetchingMask']" # Selector for the searching indicator
            
            try:
                # 1. Find the main search input element and click to ensure focus
                main_search_input_element = self.wait.until(
                    EC.element_to_be_clickable((By.ID, search_input_id))
                )
                main_search_input_element.click() # Ensure focus
                time.sleep(0.2) # Small pause

                # 2. Robustly clear the main search input field
                main_search_input_element.send_keys(Keys.CONTROL + "a")
                main_search_input_element.send_keys(Keys.DELETE)
                main_search_input_element.send_keys(Keys.RETURN) # Trigger any internal Retool clear events
                self.wait.until(EC.text_to_be_present_in_element_value((By.ID, search_input_id), ""))
                time.sleep(0.5) # Small buffer after clearing

                # 3. Find the dropdown's input field and click to ensure focus
                dropdown_input_element = self.wait.until(
                    EC.element_to_be_clickable((By.ID, dropdown_input_id))
                )
                dropdown_input_element.click() 
                time.sleep(0.2) # Give a moment for dropdown to open

                # 4. Robustly clear the dropdown input field and then type the search_type_label
                # This sequence is critical for preventing the default/revert behavior
                dropdown_input_element.send_keys(Keys.CONTROL + "a")
                dropdown_input_element.send_keys(Keys.DELETE)
                # We explicitly wait for the field to be empty before typing.
                self.wait.until(EC.text_to_be_present_in_element_value((By.ID, dropdown_input_id), ""))
                time.sleep(0.1) # Very short pause to ensure cleared state is registered

                dropdown_input_element.send_keys(search_type_label)
                dropdown_input_element.send_keys(Keys.RETURN) 
                
                # Wait for the selection to register and the dropdown input value to reflect the selection
                self.wait.until(EC.text_to_be_present_in_element_value((By.ID, dropdown_input_id), search_type_label))
                time.sleep(1) # Give generous time for the selection to register and UI to update


                # 5. Re-locate the main search input field (DOM might have changed)
                main_search_input_element = self.wait.until(
                    EC.element_to_be_clickable((By.ID, search_input_id))
                )
                
                # 6. Enter the actual search value into the main search input field using send_keys
                # This triggers auto-search events (oninput, onkeyup, etc.)
                main_search_input_element.send_keys(search_value)
                
                # 7. Send RETURN to trigger the search in Retool (after auto-search might have happened)
                main_search_input_element.send_keys(Keys.RETURN) 
                
                # --- Wait a moment for the mask to show up before waiting for it to disappear ---
                time.sleep(1.5) # Allow the fetching mask to visually appear if there's a delay

                # --- Wait for the fetching mask to become invisible ---
                print(f"{COLOR_BLUE}Waiting for search fetching mask to disappear...{COLOR_RESET}")
                self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, fetching_mask_selector)))
                print(f"{COLOR_GREEN}Search fetching mask disappeared. Search is complete.{COLOR_RESET}")

                # 8. Verify the value was actually entered in the main search input
                retried_verification = 0
                while main_search_input_element.get_attribute("value") != search_value and retried_verification < 3:
                    print(f"{COLOR_ORANGE}Verification failed for '{search_type_label}'. Retrying main input...{COLOR_RESET}")
                    main_search_input_element = self.wait.until(EC.element_to_be_clickable((By.ID, search_input_id)))
                    main_search_input_element.send_keys(Keys.CONTROL + "a") # Select all
                    main_search_input_element.send_keys(Keys.DELETE) # Delete
                    main_search_input_element.send_keys(search_value) # Re-type
                    main_search_input_element.send_keys(Keys.RETURN)
                    time.sleep(1)
                    retried_verification += 1

                if main_search_input_element.get_attribute("value") == search_value:
                    print(f"{COLOR_GREEN}Successfully entered '{search_value}' for '{search_type_label}'.{COLOR_RESET}")
                    time.sleep(1) # Reduced post-input sleep as fetching mask covers loading
                    return True # Success, exit the retry loop
                else:
                    print(f"{COLOR_RED}Failed to verify input for '{search_type_label}'. Value still incorrect. Will retry whole search.{COLOR_RED}")
                    self.driver.save_screenshot(f"retool_input_verification_failed_main_search_{search_type_label}_attempt_{attempt}_{int(time.time())}.png")
                    # No return True/False here, let the loop continue for retry
            
            except TimeoutException as e:
                print(f"{COLOR_ORANGE}Timeout during search attempt {attempt} for '{search_type_label}': {e}{COLOR_RESET}")
                self.driver.save_screenshot(f"retool_search_timeout_{search_type_label}_attempt_{attempt}_{int(time.time())}.png")
            except NoSuchElementException as e:
                print(f"{COLOR_ORANGE}Search element '{search_type_label}' not found (or dropdown option not typed correctly) on attempt {attempt}: {e}{COLOR_RESET}")
                self.driver.save_screenshot(f"retool_search_element_not_found_{search_type_label}_attempt_{attempt}_{int(time.time())}.png")
            except ElementClickInterceptedException as e:
                print(f"{COLOR_ORANGE}Click intercepted for '{search_type_label}' on attempt {attempt}: {e}{COLOR_RESET}")
                self.driver.save_screenshot(f"retool_click_intercepted_{search_type_label}_attempt_{attempt}_{int(time.time())}.png")
            except Exception as e:
                print(f"{COLOR_RED}Unexpected error entering data for '{search_type_label}' on attempt {attempt}: {e}{COLOR_RESET}")
                self.driver.save_screenshot(f"retool_unexpected_error_{search_type_label}_attempt_{attempt}_{int(time.time())}.png")
            
            # If we reach here, it means the current attempt failed. Pause and retry.
            if attempt < MAX_SEARCH_RETRIES:
                print(f"{COLOR_YELLOW}Retrying search in {SEARCH_RETRY_DELAY} seconds...{COLOR_RESET}")
                time.sleep(SEARCH_RETRY_DELAY)
            else:
                print(f"{COLOR_RED}All {MAX_SEARCH_RETRIES} attempts failed for '{search_type_label}'. Giving up.{COLOR_RESET}")

        return False # All attempts failed
    
def load_cleanup_queue_data(json_file_path):
    """Loads cleanup queue data from a JSON file."""
    try:
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        print(f"{COLOR_BLUE}Successfully loaded {len(data)} entries from Cleanup Queue JSON.{COLOR_RESET}")
        return data
    except FileNotFoundError:
        print(f"{COLOR_RED}Error: Cleanup Queue JSON file '{json_file_path}' not found.{COLOR_RESET}")
        return []
    except json.JSONDecodeError as e:
        print(f"{COLOR_RED}Error decoding JSON from '{json_file_path}': {e}{COLOR_RESET}")
        return []
    except Exception as e:
        print(f"{COLOR_RED}An unexpected error occurred while loading Cleanup Queue JSON data: {e}{COLOR_RESET}")
        return []
    
def load_company_data_from_json(json_file_path):
    """
    Loads and flattens company data from the Pitchbook JSON tree into a searchable dictionary.
    Keys will be Pitchbook IDs and normalized legal names.
    Also returns the original hierarchical data for traversal.
    """
    company_data_map = {} # New structure: {pb_id: company_data, normalized_name: company_data}
    original_full_data = [] # To store the original hierarchical list

    # Helper function to extract PB ID using regex
    def extract_pb_id_from_url(url):
        if not url:
            return None
        match = re.search(r'/profile/([A-Za-z0-9-]+)(?:/|$)', url)
        if match:
            return match.group(1)
        return None

    def process_node_and_add_to_map(node, current_depth):
        # ADDED: Check if node is a dictionary before processing
        if not isinstance(node, dict):
            print(f"{COLOR_ORANGE}Warning: Skipping non-dictionary node in Pitchbook JSON: {node}{COLOR_RESET}")
            return

        profile_url = node.get("profile_url")
        pb_id = extract_pb_id_from_url(profile_url)
        legal_name = node.get("legal_name") or node.get("Name") # Use 'Name' as fallback for affiliates

        # Create a copy of the original node to store in the map (or reference directly if modifying isn't an issue)
        company_details_for_map = {
            "profile_url": profile_url,
            "pb_id": pb_id,
            "website_link": node.get("website_link"),
            "former_names": node.get("former_names"),
            "legal_name": legal_name,
            "also_known_as": node.get("also_known_as"), # ADDED: also_known_as
            "depth": current_depth,
            "contact_name": node.get("contact_name"),
            "contact_profile_link": node.get("contact_profile_link"),
            "contact_title": node.get("contact_title"),
            "contact_email": node.get("contact_email"),
            "contact_email_link": node.get("contact_email_link"),
            "contact_business_phone": node.get("contact_business_phone"),
            "contact_mobile_phone": node.get("contact_mobile_phone"),
            "office_address_line1": node.get("office_address_line1"),
            "office_address_line2": node.get("office_address_line2"),
            "office_address_line3": node.get("office_address_line3"),
            "office_email": node.get("office_email"),
            "office_phone": node.get("office_phone")
        }

        # Add to map by Pitchbook ID
        if pb_id:
            company_data_map[pb_id] = company_details_for_map
        
        # Add to map by normalized legal name
        if legal_name:
            normalized_legal_name = normalize_name(legal_name)
            if normalized_legal_name: # Only add if normalized name is not empty
                # Prioritize PB ID match for keys, otherwise overwrite if new.
                # This ensures the map prefers unique PB IDs.
                if normalized_legal_name not in company_data_map or (company_data_map[normalized_legal_name].get("pb_id") is None and pb_id is not None):
                    company_data_map[normalized_legal_name] = company_details_for_map

        nested_affiliates_data = node.get("scraped_affiliates_table_data")
        if nested_affiliates_data:
            # ADDED: Check if nested_affiliates_data is a list before iterating
            if not isinstance(nested_affiliates_data, list):
                print(f"{COLOR_ORANGE}Warning: 'scraped_affiliates_table_data' is not a list. Skipping. Node: {node.get('legal_name')}{COLOR_RESET}")
                return

            for affiliate_row in nested_affiliates_data:
                # ADDED: Check if affiliate_row is a dictionary before processing
                if not isinstance(affiliate_row, dict):
                    print(f"{COLOR_ORANGE}Warning: Skipping non-dictionary affiliate_row: {affiliate_row}{COLOR_RESET}")
                    continue

                if 'full_affiliate_profile_data' in affiliate_row and affiliate_row['full_affiliate_profile_data']:
                    process_node_and_add_to_map(affiliate_row['full_affiliate_profile_data'], current_depth + 1)
                else:
                    # For direct affiliates, add their data to the map
                    affiliate_profile_url = affiliate_row.get("Name_link")
                    affiliate_pb_id = extract_pb_id_from_url(affiliate_profile_url)
                    affiliate_legal_name = affiliate_row.get("legal_name") or affiliate_row.get("Name")

                    affiliate_details_for_map = {
                        "profile_url": affiliate_profile_url,
                        "pb_id": affiliate_pb_id,
                        "website_link": affiliate_row.get("website_link"),
                        "former_names": affiliate_row.get("former_names"),
                        "legal_name": affiliate_legal_name,
                        "also_known_as": affiliate_row.get("also_known_as"), # ADDED: also_known_as
                        "Name": affiliate_row.get("Name"), # Keep original 'Name' for direct affiliates
                        "depth": current_depth + 1,
                        "contact_name": affiliate_row.get("contact_name"),
                        "contact_profile_link": affiliate_row.get("contact_profile_link"),
                        "contact_title": affiliate_row.get("contact_title"),
                        "contact_email": affiliate_row.get("contact_email"),
                        "contact_email_link": affiliate_row.get("contact_email_link"),
                        "contact_business_phone": affiliate_row.get("contact_business_phone"),
                        "contact_mobile_phone": affiliate_row.get("contact_mobile_phone"),
                        "office_address_line1": affiliate_row.get("office_address_line1"),
                        "office_address_line2": affiliate_row.get("office_address_line2"),
                        "office_address_line3": affiliate_row.get("office_address_line3"),
                        "office_email": affiliate_row.get("office_email"),
                        "office_phone": affiliate_row.get("office_phone")
                    }

                    if affiliate_pb_id:
                        company_data_map[affiliate_pb_id] = affiliate_details_for_map
                    if affiliate_legal_name:
                        normalized_affiliate_name = normalize_name(affiliate_legal_name)
                        if normalized_affiliate_name:
                            if normalized_affiliate_name not in company_data_map or (company_data_map[normalized_affiliate_name].get("pb_id") is None and affiliate_pb_id is not None):
                                company_data_map[normalized_affiliate_name] = affiliate_details_for_map
                    
                    if 'related_companies' in affiliate_row and affiliate_row['related_companies']:
                        # ADDED: Check if related_companies is a list before iterating
                        if isinstance(affiliate_row['related_companies'], list):
                            for deeper_affiliate in affiliate_row['related_companies']:
                                process_node_and_add_to_map(deeper_affiliate, current_depth + 2)
                        else:
                            print(f"{COLOR_ORANGE}Warning: 'related_companies' is not a list. Skipping. Affiliate: {affiliate_row.get('Name')}{COLOR_RESET}")


    try: 
        with open(json_file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # ADDED: Check if the top-level data is a list as expected
        if not isinstance(data, list):
            print(f"{COLOR_RED}Error: Top-level JSON data is not a list as expected. Cannot process.{COLOR_RED}")
            return {}, [] # Return empty map and list

        original_full_data = data # Store the original list

        for top_level_company in original_full_data:
            process_node_and_add_to_map(top_level_company, 0)
        
        print(f"{COLOR_BLUE}Successfully loaded {len(company_data_map)} searchable entries from Pitchbook JSON.{COLOR_RESET}")
    except FileNotFoundError:
        print(f"{COLOR_RED}Error: Pitchbook JSON file '{json_file_path}' not found.{COLOR_RED}")
        return {}, [] # Return empty map and list
    except json.JSONDecodeError as e:
        print(f"{COLOR_RED}Error decoding JSON from '{json_file_path}': {e}{COLOR_RED}")
        return {}, [] # Return empty map and list
    except Exception as e:
        print(f"{COLOR_RED}An unexpected error occurred while loading Pitchbook JSON data: {e}{COLOR_RED}")
        return {}, [] # Return empty map and list

    return company_data_map, original_full_data
def main():

    # The initial login URL for Retool (where you'd click "Sign in with SSO")
    RETOOL_LOGIN_URL = "https://prod.retool.hl.com/auth/login" 

    RETOOL_DASHBOARD_URL = "https://prod.retool.hl.com/apps/7a30d6e7-6466-456e-9b7e-8055c5a8e475/Data%20Ops/Data%20Ops/CleanupQueue#CurrentMergeGroupID" 
    
   
    LOGIN_SUCCESS_INDICATOR = "//h3[normalize-space(text())='Cleanup']" 
    
    CHECK_LOGIN_TIMEOUT = 30 
    
    # Path to your Pitchbook JSON file (source of all company data)
    PITCHBOOK_JSON_FILE = 'multi_company_pitchbook_data.json'

    ADD_ACCOUNT_BUTTON_SELECTOR = "div#button9--0 button"

    if RETOOL_DASHBOARD_URL == "https://prod.retool.hl.com/apps/7a30d6e7-6466-456e-9b7e-8055c5a8e475/Data%20Ops/Data%20Ops/CleanupQueue#CurrentMergeGroupID":
        print(f"{COLOR_RED}Please ensure RETOOL_DASHBOARD_URL is correctly set for your Retool instance.{COLOR_RESET}")
        print(f"{COLOR_RED}The provided value is a placeholder based on previous interaction and might need to be specific to your setup.{COLOR_RESET}")

    scraper = WebScraper(headless=False, profile_name="retool_sso_profile") 
    
    companies_for_review = []
    processed_pitchbook_nodes = set()

    try:
        print(f"{COLOR_BLUE}=== Attempting to log into Retool ==={COLOR_RESET}")
        
        if not scraper.check_login_status(RETOOL_DASHBOARD_URL, LOGIN_SUCCESS_INDICATOR, check_timeout=CHECK_LOGIN_TIMEOUT):
            logged_in_successfully = scraper.wait_for_sso_login(
                login_url=RETOOL_LOGIN_URL, 
                success_indicator=LOGIN_SUCCESS_INDICATOR 
            )
            if not logged_in_successfully:
                print(f"{COLOR_RED}Failed to log in. Exiting.{COLOR_RED}")
                return

        if scraper.logged_in:
            print(f"\n{COLOR_GREEN}Session is active. Proceeding with actions on dashboard.{COLOR_RESET}")
            

            all_pitchbook_data_map, original_pitchbook_data = load_company_data_from_json(PITCHBOOK_JSON_FILE)
            if not all_pitchbook_data_map or not original_pitchbook_data:
                print(f"{COLOR_RED}No Pitchbook data loaded or it's malformed. Cannot proceed with processing.{COLOR_RED}")
                return

            cleanup_queue_table_id = "CleanupQueueEntryTable--0" 
            scrollable_element_selector = f"div#{cleanup_queue_table_id} div._outer_1y096_2[data-testid='TableWrapper::ScrollableContainer']"
            name_column_selector_in_row = "div[role='gridcell'][data-column-id='787e6'] span[data-is-cell-contents='true']"
            pb_id_column_selector_in_row = "div[role='gridcell'][data-column-id='49266'] span[data-is-cell-contents='true']"


            print(f"{COLOR_BLUE}Navigating to Cleanup Queue page for processing: {RETOOL_DASHBOARD_URL}{COLOR_RESET}")
            scraper.driver.get(RETOOL_DASHBOARD_URL)
            try:
                WebDriverWait(scraper.driver, 30).until(
                    EC.presence_of_element_located((By.ID, cleanup_queue_table_id)),
                    message=f"Timeout waiting for Cleanup Queue table (ID: {cleanup_queue_table_id}) to be present after initial navigation."
                )
                print(f"{COLOR_BLUE}Cleanup Queue table is present.{COLOR_RESET}")
                time.sleep(5)
            except Exception as e:
                print(f"{COLOR_RED}Error during initial Cleanup Queue page load for processing: {e}{COLOR_RESET}")
                scraper.driver.save_screenshot(f"cleanup_queue_initial_processing_load_error_{int(time.time())}.png")
                return 

            processed_root_entries_count = 0
            processed_row_unique_keys = set() 
            
            scroll_attempts_processing = 0
            max_scroll_attempts_processing = 100 

            while scroll_attempts_processing < max_scroll_attempts_processing:
                initial_processed_unique_keys_count_in_pass = len(processed_row_unique_keys)
                
                scrollable_element = scraper.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, scrollable_element_selector)))
                
                current_visible_rows_elements = scraper.driver.find_elements(By.CSS_SELECTOR, f"div#{cleanup_queue_table_id} div[role='rowgroup'] div[role='row'][data-item-index]")
                
                found_and_clicked_in_this_pass = False

                for row_element in current_visible_rows_elements:
                    live_company_name = None
                    live_pitchbook_id = None
                    row_data_item_index = row_element.get_attribute('data-item-index') 

                    try:
                        name_element = row_element.find_element(By.CSS_SELECTOR, name_column_selector_in_row)
                        live_company_name = name_element.text.strip()
                        
                        try: 
                            pb_id_element = row_element.find_element(By.CSS_SELECTOR, pb_id_column_selector_in_row)
                            live_pitchbook_id = pb_id_element.text.strip()
                        except NoSuchElementException:
                            live_pitchbook_id = None 
                        
                        current_row_unique_key = f"{live_company_name}-{live_pitchbook_id}"
                        
                        if current_row_unique_key in processed_row_unique_keys:
                            continue

                        processed_row_unique_keys.add(current_row_unique_key)
                        
                        print(f"{COLOR_BLUE}Evaluating live row (Index: {row_data_item_index}): Name='{live_company_name}', PB ID='{live_pitchbook_id}'.{COLOR_RESET}")

                        matched_company_data_flat = None
                        if live_pitchbook_id and live_pitchbook_id in all_pitchbook_data_map:
                            matched_company_data_flat = all_pitchbook_data_map[live_pitchbook_id]
                            print(f"{COLOR_GREEN}Direct match found by Pitchbook ID: '{live_pitchbook_id}'. Legal Name: {matched_company_data_flat.get('legal_name')}{COLOR_RESET}")
                        elif live_company_name:
                            normalized_live_name = normalize_name(live_company_name)
                            if normalized_live_name and normalized_live_name in all_pitchbook_data_map:
                                matched_company_data_flat = all_pitchbook_data_map[normalized_live_name]
                                print(f"{COLOR_GREEN}Direct match found by Normalized Name: '{live_company_name}'. Legal Name: {matched_company_data_flat.get('legal_name')}{COLOR_RESET}")
                            else:
                                for pb_key, company_data_obj in all_pitchbook_data_map.items():
                                    if isinstance(company_data_obj, dict) and company_data_obj.get('legal_name') and \
                                    are_names_similar(live_company_name, company_data_obj.get('legal_name')):
                                        matched_company_data_flat = company_data_obj
                                        print(f"{COLOR_GREEN}Fuzzy matched by Name: '{live_company_name}' to '{company_data_obj.get('legal_name')}'.{COLOR_RESET}")
                                        break
                        
                        if matched_company_data_flat:
                            if matched_company_data_flat.get("depth") == 0:
                                print(f"{COLOR_GREEN}Match found and is a ROOT company ({matched_company_data_flat.get('legal_name')}, Depth: 0). Proceeding to click and input data.{COLOR_RESET}")

                                clickable_name_cell = row_element.find_element(By.CSS_SELECTOR, "div[role='gridcell'][data-column-id='787e6'] div[data-is-cell-contents='true'][class*='_isClickable_']")
                                clickable_name_cell.click()
                                time.sleep(2) 
                                print(f"{COLOR_GREEN}Clicked live Cleanup Queue entry: '{live_company_name}'.{COLOR_RESET}")
                            
                                full_root_company_to_process = None
                                for root_node in original_pitchbook_data:
                                    if isinstance(root_node, dict):
                                        if matched_company_data_flat.get("pb_id") and root_node.get("pb_id") == matched_company_data_flat["pb_id"]:
                                            full_root_company_to_process = root_node
                                            break
                                        elif matched_company_data_flat.get("legal_name") and normalize_name(root_node.get("legal_name")) == normalize_name(matched_company_data_flat["legal_name"]):
                                            full_root_company_to_process = root_node
                                            break

                                if full_root_company_to_process:
                                   
                                    print(f"{COLOR_BLUE}Starting recursive data input for '{full_root_company_to_process.get('legal_name')}' and its affiliates...{COLOR_RESET}")
                                    process_pitchbook_hierarchy(scraper, full_root_company_to_process, ADD_ACCOUNT_BUTTON_SELECTOR, companies_for_review, processed_pitchbook_nodes)
                                    processed_root_entries_count += 1
                                    print(f"{COLOR_BLUE}Finished recursive data input for this hierarchy.{COLOR_RESET}")
                                else:
                                    print(f"{COLOR_ORANGE}Error: Matched flat company data ({matched_company_data_flat.get('legal_name')}) not found in original hierarchical Pitchbook data. Skipping.{COLOR_RESET}")
                                
                               
                                print(f"{COLOR_BLUE}Navigating back to Cleanup Queue page for next entry: {RETOOL_DASHBOARD_URL}{COLOR_RESET}")
                                scraper.driver.get(RETOOL_DASHBOARD_URL)
                                try:
                                    WebDriverWait(scraper.driver, 30).until(
                                        EC.presence_of_element_located((By.ID, cleanup_queue_table_id)),
                                        message=f"Timeout waiting for Cleanup Queue table (ID: {cleanup_queue_table_id}) to be present after navigating back."
                                    )
                                    time.sleep(5)
                                except Exception as e:
                                    print(f"{COLOR_RED}Error navigating back to Cleanup Queue: {e}{COLOR_RESET}")
                                    scraper.driver.save_screenshot(f"cleanup_queue_navigate_back_process_error_{int(time.time())}.png")
                                    found_and_clicked_in_this_pass = False 
                                    break 
                                found_and_clicked_in_this_pass = True 
                                break 
                            else:
                                print(f"{COLOR_YELLOW}Match found ({matched_company_data_flat.get('legal_name')}), but NOT a ROOT company (Depth: {matched_company_data_flat.get('depth')}). Skipping.{COLOR_RESET}")
                        else:
                            print(f"{COLOR_ORANGE}No match found in Pitchbook data for live row (Name: '{live_company_name}', PB ID: '{live_pitchbook_id}'). Skipping.{COLOR_RESET}")

                    except StaleElementReferenceException:
                        print(f"{COLOR_ORANGE}Stale element encountered while processing live row. Re-scanning current view.{COLOR_RESET}")
                        found_and_clicked_in_this_pass = False
                        break 
                    except Exception as e:
                        print(f"{COLOR_RED}Error processing live row (Index: {row_data_item_index}, Name: '{live_company_name}', PB ID: '{live_pitchbook_id}'): {e}. Skipping.{COLOR_RESET}")
                        
                        scraper.driver.save_screenshot(f"processing_live_row_error_idx_{row_data_item_index}_{int(time.time())}.png")
                        
                        break

                if found_and_clicked_in_this_pass:
                    continue

                if len(processed_row_unique_keys) == initial_processed_unique_keys_count_in_pass:
                    current_scroll_position = scraper.driver.execute_script("return arguments[0].scrollTop;", scrollable_element)
                    scraper.driver.execute_script("arguments[0].scrollTop += arguments[0].clientHeight;", scrollable_element)
                    time.sleep(1.5)
                    new_scroll_position = scraper.driver.execute_script("return arguments[0].scrollTop;", scrollable_element)

                    if new_scroll_position == current_scroll_position:
                        print(f"{COLOR_BLUE}Reached end of scrollable content or no new entries loaded. Breaking processing loop.{COLOR_RESET}")
                        break 
                
                scroll_attempts_processing += 1
                if scroll_attempts_processing == max_scroll_attempts_processing:
                    print(f"{COLOR_ORANGE}Max scroll attempts reached in processing loop. Breaking.{COLOR_RESET}")
                    break
                    
            print(f"{COLOR_GREEN}\nFinished iterating Cleanup Queue. Total root entries processed with data input: {processed_root_entries_count}.{COLOR_RESET}")

            print(f"\n{COLOR_GREEN}All actions completed. The browser will remain open for 60 seconds for observation.{COLOR_RESET}")
            time.sleep(60)
        else:
            print(f"{COLOR_RED}Could not establish a session. Exiting.{COLOR_RED}")
            time.sleep(10)

    except Exception as e:
        print(f"{COLOR_RED}An unexpected error occurred in the main process: {e}{COLOR_RESET}")
    
    finally:
        if scraper:
            scraper.close()
            with open('processed_pitchbook_data_with_ids.json', 'w', encoding='utf-8') as f:
                json.dump(original_pitchbook_data, f, indent=4)
            print(f"{COLOR_GREEN}Modified Pitchbook data with Account IDs saved to 'processed_pitchbook_data_with_ids.json'.{COLOR_RESET}")

            if companies_for_review: 
                write_companies_to_review_json(companies_for_review)

if __name__ == "__main__":
    main()

