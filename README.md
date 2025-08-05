You're right, when you look at the raw text, it does look flat. That's the nature of Markdown – it's a plain text file with special characters (`#`, `*`, `|`) that only get converted into styled headings, lists, and tables when viewed through a Markdown renderer, like the one on GitHub.

The code I provided is correctly formatted. When you save it as a `readme.md` file and view it on a platform like GitHub, it will render with all the proper formatting—bolding, headings, tables, and nested lists—and won't look flat at all.

Here is the code again for you to copy and paste into your `readme.md` file. I assure you it will look properly structured in a Markdown viewer.

---

@Quinn Lindsey
<br>
*Updated: 7/15/2025*

# Cleanup Automation Bot

## Project Overview

### Essential Components

| Component | Program Name | Progress |
|:---|:---|:---|
| Pitchbook Tree Generator | PBTree | 95% |
| Retool Inputer & Comparison | RetoolBot | 95% |
| Google AI Agent Search | GoogleAgent | 0% |

### Lesser Components

| Component | Progress |
|:---|:---|
| CapIQ Comparison | 0% |
| Simple UI Interface | 90% |

---

## Flow of the program with only the Essential Components

1.  **PBTree** is given a list of root pitchbook ids from the cleanup Queue by **RetoolBot**.
2.  The user then checks off the companies in the UI that are needed to be scraped.
3.  **PBTree** runs the recursive crawler on those companies and saves the data for each company and its affiliates in a JSON tree file.
4.  **RetoolBot** inputs relevant info (PB IDs, Websites, Former names, Legal Names) for each company & child from the JSON tree into the retool search and adds the records as children automatically if a match is found.
5.  **RetoolBot** then compares the pitchbook data of each record to its Salesforce record and raises warnings if a mismatch between the data is found.
6.  The **Google Agent** then checks the work of the bot and reviews the mismatched data.
7.  The user then goes into the cleanup queue and reviews the raised mismatches & the work of the bot.

---

## PBTree

-   **Features Working**
    -   Recursive generation of a structure
    -   Auto login & cookies caching
    -   Custom persistent chrome profile to avoid freaking out pitchbook
    -   Mimics a user 100%, avoids detection
    -   Scraped Former names, PB ID, website, profile URL, Legal names, address, and more for each affiliate
    -   Added M&A scraping
    -   Saves all data collected into a tree structured JSON file so it can be easily readable by users and the other components
-   **Features To Implement Still**
    -   Non-essential features:
        -   Improve Speed using Multithreading accorss multiple browser instances
        -   Improve Speed using custom css triggers instead of sleeps between css element loaded checks
        -   Try different methods to render the css faster
        -   Search for a Parent of root in case of user error

---

## RetoolBot

-   **Features Working**
    -   User SSO Login
    -   Login cached
    -   Inputs data from PBTREE
    -   Identifies mismatches and raises warnings.
    -   Navigates queue and fills out every root company selected.
    -   Adds children from search
-   **Features To Implement Still**
    -   Rate limit
    -   Multithreading
