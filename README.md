@Quinn Lindsey
@7/15/2025

Cleanup Automation Bot

Project Overview

Essential Components            Program Name        Progress
1. Pitchbook Tree Generator     (PBTree)            (95%)
2. Retool Inputer & Comparison  (RetoolBot)         (95%)
4. Google AI Agent Search       (GoogleAgent)       (0%)

Lesser Components
4. CapIQ Comparison                                 (0%)
5. Simple UI Interface                              (90%)

Flow of the program with only the Essential Components:
1. PBTree is given a list of root pitchbook ids from the cleanup Queue by RetoolBot.

2. User then checks off the companies in the UI that are needed to be scraped.

2. PBTree runs the recursive crawler on those companies and saves the data for each company and it's affialtes in a JSON tree file.

3. RetoolBot inputs relevant info (PB IDs, Websites, Former names, Legal Names) for each company & child from the JSON tree into the retool search and adds the records as children automatically if a match is found.

4. RetoolBot then compares the pitchbook data of each records to it's salesforce record and raises warnings if a mismatch between the data is found.

5. Google Agent then checks the work of the bot and reviews the mismatched data.

5. User then goes into the cleanup queue and reviews the raised mismatches & the work of the bot.


PBTree
├── Features Working
│   ├── Recursive generation of a structure
│   ├── Auto login & cookies caching
│   ├── Custom persistent chrome profile to avoid freaking out pitchbook
│   ├── Mimics a user 100%, avoids detection
│   ├── Scraped Former names, PB ID, website, profile URL, Legal names, address, and more for each affiliate
│   ├── Added M&A scraping
│   └── Saves all data collected into a tree structured JSON file so it can be easily readable by users and the other components
└── Features To Implement Still
    └── Non-essential features:
        ├── Improve Speed using Multithreading accorss multiple browser instances
        ├── Improve Speed using custom css triggers instead of sleeps between css element loaded checks
        ├── Try different methods to render the css faster 
        └── Search for a Parent of root in case of user error


RetoolBot
├── Features Working
│   ├── User SSO Login
│   ├── Login cached
│   ├── Inputs data from PBTREE
│   ├── Identifies mismatches and raises warnings.
│   ├── Navigates queue and fills out every root company selected.
│   └── Adds children from search
└── Features To Implement Still
    ├── Rate limit 
    └── Multithreading




















