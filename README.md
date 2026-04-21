# LMS Assignment Reminder 
Ok so I built this because I had to submit almost 10 assignments a week at one point in time and I wasn't really able to keep track of which assignment I had to submit when , so I built this and also used task scheduler such that it runs by itself whenever I open my laptop and gives me a notification accordingl along with a text file to see which assignment is due when , so I could stay on top of all my assignments .
another thing which was confuing was that an assignment being due a thursday , 12:00 am means it's actually due wednesday , so I implemented that as well so people don't get confused.

## Overview
This project is an automated LMS Assignment Scraper built using Python and Selenium.  
It logs into the LMS portal, extracts assignment details, stores them locally, and organizes them based on urgency.

It also handles duplicate assignments by tracking unique assignment IDs.

---

## Problem
Students often miss assignments because:
- Deadlines are not clearly visible
- LMS dashboards are cluttered
- Multiple submissions create confusion

This project solves that by collecting and organizing all assignments in one place.

---

## Features

- Automated LMS login using Selenium  
- Scrapes assignments from dashboard  
- Handles duplicate assignments using assignment IDs  
- Stores data in SQLite database  
- Categorizes assignments:
  - Overdue  
  - Today  
  - This Week  
  - This Month  
  - Future  
- Extracts assignment URLs  
- Generates a text report  

---

## Tech Stack

- Python  
- Selenium  
- SQLite  
- WebDriver Manager  

---

## How It Works

1. Logs into LMS  
2. Navigates to dashboard  
3. Extracts assignment data  
4. Stores data in database  
5. Displays assignments based on urgency  

---

## How to Run

Install dependencies:
```bash
pip install selenium webdriver-manager pytz
