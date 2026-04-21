# scraper_fixed_final.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from datetime import datetime, timedelta
import sqlite3
import time
import re
import pytz
import os

# ================= CONFIG =================
LMS_URL = "https://lms.ssn.edu.in"
USERNAME = ""   # <-- fill
PASSWORD = ""   # <-- fill
IST = pytz.timezone("Asia/Kolkata")
DB_NAME = "lms.db"
def clear_database():
    """Clear database - KEEP SAME WORKING LOGIC but allow duplicates"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Drop table if exists
    cur.execute("DROP TABLE IF EXISTS assignments")
    
    # Create table WITHOUT the unique constraint that blocks duplicates
    # But add assignment_id to track different submissions
    cur.execute("""
        CREATE TABLE assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            course_code TEXT,
            course_name TEXT,
            section TEXT,
            due_datetime TEXT,
            display_deadline TEXT,
            submitted INTEGER DEFAULT 0,
            url TEXT,
            assignment_id TEXT
            -- REMOVED: UNIQUE(title, course_code, due_datetime)
        )
    """)
    
    conn.commit()
    conn.close()
    print("🗑️  Database cleared (allowing duplicates)")

def dashboard_scraper():
    """SAME WORKING CODE but saves duplicates"""
    options = Options()
    options.add_argument("--start-maximized")
    options.add_argument("--disable-notifications")
    
    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )
    
    try:
        print("1. Logging in...")
        driver.get(LMS_URL)
        time.sleep(3)
        
        if "login" in driver.current_url.lower():
            driver.find_element(By.NAME, "username").send_keys(USERNAME)
            driver.find_element(By.NAME, "password").send_keys(PASSWORD + Keys.RETURN)
            time.sleep(5)
        
        print("2. Going to dashboard...")
        driver.get(f"{LMS_URL}/my/")
        time.sleep(5)
        
        print("3. Looking for 'Show more activities' button...")
        
        time.sleep(3)
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(2)
        
        try:
            show_more_button = driver.find_element(
                By.XPATH, 
                "//button[contains(text(), 'Show more activities')]"
            )
            
            if show_more_button.is_displayed():
                print("   Found button, clicking it...")
                driver.execute_script("arguments[0].scrollIntoView(true);", show_more_button)
                time.sleep(1)
                show_more_button.click()
                print("   Button clicked, waiting for content to load...")
                time.sleep(5)
            else:
                print("   Button found but not visible, scrolling more...")
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(2)
                show_more_button.click()
                time.sleep(5)
                
        except Exception as e:
            print(f"   Could not find/click button: {e}")
            print("   Continuing anyway...")
        
        print("4. Scrolling to load all content...")
        for i in range(3):
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
        
        print("5. Now extracting assignments...")
        
        try:
            timeline = driver.find_element(
                By.XPATH,
                "//div[contains(@data-region, 'timeline') or contains(@class, 'timeline')]"
            )
            all_text = timeline.text
        except:
            all_text = driver.find_element(By.TAG_NAME, "body").text
        
        # Save for debugging
        with open("dashboard_content.txt", "w", encoding="utf-8") as f:
            f.write(all_text)
        print("   💾 Saved content to 'dashboard_content.txt'")
        
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]
        print(f"   Found {len(lines)} lines of text")
        
        assignments = []
        current_date = None
        
        print("\n6. Parsing dates and assignments...")
        
        for i, line in enumerate(lines):
            date_match = re.match(r'^([A-Za-z]+,\s*\d+\s+[A-Za-z]+\s+\d{4})$', line)
            if date_match:
                current_date = date_match.group(1)
                print(f"\n   📅 Found date: {current_date}")
                continue
            
            if current_date and line and len(line) > 3:
                if (line in ["00:00", "Add submission", "Show more activities", 
                           "Timeline", "All", "Sort by dates", "Search by activity type or name"] or
                    "Assignment is due" in line or
                    "UIT" in line and "--" in line or
                    re.match(r'^\d{1,2}:\d{2}$', line)):
                    continue
                
                title = line
                
                course_info = None
                for j in range(i+1, min(i+5, len(lines))):
                    next_line = lines[j]
                    if "UIT" in next_line and "--" in next_line:
                        course_info = next_line
                        break
                
                if course_info:
                    match = re.search(r'(UIT\d+|UGA\d+)--([^-]+)--\d+--Section\s+([A-Z])', course_info)
                    if match:
                        course_code = match.group(1)
                        course_name = match.group(2).strip()
                        section = match.group(3)
                        
                        try:
                            dt = datetime.strptime(current_date, "%A, %d %B %Y")
                            dt = dt - timedelta(minutes=1)
                            due_dt = IST.localize(dt)
                            
                            assignments.append({
                                "title": title,
                                "course_code": course_code,
                                "course_name": course_name,
                                "section": section,
                                "due_datetime": due_dt.isoformat(),
                                "date_display": current_date
                            })
                            
                            print(f"   📚 Found: {course_code} - {title}")
                            print(f"     Due: {due_dt.strftime('%d %b %Y')}")
                            
                        except Exception as e:
                            print(f"   ❌ Date error: {e}")
        
        print(f"\n7. Total assignments found: {len(assignments)}")
        
        print("\n8. Finding ALL assignment URLs...")
        assignment_links = driver.find_elements(
            By.XPATH,
            "//a[contains(@href, 'mod/assign/view.php')]"
        )
        
        print(f"   Found {len(assignment_links)} assignment links")
        
        # NEW: Create a list of URLs for each title
        title_to_urls = {}
        for link in assignment_links:
            try:
                link_text = link.text.strip()
                url = link.get_attribute('href')
                
                if not link_text or link_text == "Add submission":
                    continue
                
                if link_text not in title_to_urls:
                    title_to_urls[link_text] = []
                
                if url not in title_to_urls[link_text]:
                    title_to_urls[link_text].append(url)
                    
            except:
                continue
        
        # NEW: Assign URLs to assignments (handle multiple URLs per title)
        print("\n9. Assigning URLs to assignments...")
        final_assignments = []
        
        for assign in assignments:
            title = assign["title"]
            
            if title in title_to_urls:
                # For each URL, create a separate assignment entry
                for url in title_to_urls[title]:
                    # Extract assignment ID
                    assignment_id = ""
                    if 'id=' in url:
                        assignment_id = url.split('id=')[-1].split('&')[0]
                    
                    final_assignments.append({
                        "title": assign["title"],
                        "course_code": assign["course_code"],
                        "course_name": assign["course_name"],
                        "section": assign["section"],
                        "due_datetime": assign["due_datetime"],
                        "url": url,
                        "assignment_id": assignment_id,
                        "date_display": assign["date_display"]
                    })
                    print(f"   🔗 {assign['course_code']} - {title}: ID {assignment_id}")
            else:
                # Assignment without URL
                final_assignments.append({
                    "title": assign["title"],
                    "course_code": assign["course_code"],
                    "course_name": assign["course_name"],
                    "section": assign["section"],
                    "due_datetime": assign["due_datetime"],
                    "url": "",
                    "assignment_id": "",
                    "date_display": assign["date_display"]
                })
        
        print(f"\n10. Final assignments (with URLs): {len(final_assignments)}")
        
        # Save to database - SAVE ALL including duplicates
        conn = sqlite3.connect(DB_NAME)
        cur = conn.cursor()
        
        saved = 0
        for assign in final_assignments:
            try:
                # Use assignment_id in uniqueness check if available
                if assign["assignment_id"]:
                    # Check if this specific assignment_id already exists
                    cur.execute("SELECT id FROM assignments WHERE assignment_id = ?", 
                               (assign["assignment_id"],))
                    if cur.fetchone():
                        print(f"   ⚠️  Skipping duplicate ID: {assign['assignment_id']}")
                        continue
                
                cur.execute("""
                    INSERT INTO assignments 
                    (title, course_code, course_name, section, due_datetime, display_deadline, url, assignment_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    assign["title"],
                    assign["course_code"],
                    assign["course_name"],
                    assign["section"],
                    assign["due_datetime"],
                    assign["due_datetime"],
                    assign["url"],
                    assign["assignment_id"]
                ))
                saved += 1
            except Exception as e:
                print(f"   ❌ Save error for {assign['title']}: {e}")
        
        conn.commit()
        conn.close()
        
        print(f"💾 Saved {saved} assignments to database")
        
        return final_assignments
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return []
    
    finally:
        driver.quit()

def display_results():
    """Display all assignments - SHOW DUPLICATES"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Get all assignments
    cur.execute("""
        SELECT 
            title,
            course_code,
            course_name,
            due_datetime,
            url,
            assignment_id,
            CASE 
                WHEN date(due_datetime) < date('now') THEN 'OVERDUE'
                WHEN date(due_datetime) = date('now') THEN 'TODAY'
                WHEN julianday(due_datetime) - julianday('now') <= 7 THEN 'THIS_WEEK'
                WHEN julianday(due_datetime) - julianday('now') <= 30 THEN 'THIS_MONTH'
                ELSE 'FUTURE'
            END as urgency
        FROM assignments 
        WHERE submitted = 0
        ORDER BY due_datetime, course_code, assignment_id
    """)
    
    assignments = cur.fetchall()
    conn.close()
    
    if not assignments:
        print("\n📭 No assignments found.")
        return
    
    print("\n" + "="*70)
    print("📋 ALL ASSIGNMENTS (INCLUDING DUPLICATES)")
    print("="*70)
    print(f"Total entries: {len(assignments)}\n")
    
    groups = {
        "OVERDUE": [],
        "TODAY": [],
        "THIS_WEEK": [],
        "THIS_MONTH": [],
        "FUTURE": []
    }
    
    for title, course, course_name, due_str, url, assignment_id, urgency in assignments:
        due = datetime.fromisoformat(due_str)
        days = (due - datetime.now(IST)).days
        groups[urgency].append((title, course, course_name, due, url, assignment_id, days))
    
    for group_name in ["OVERDUE", "TODAY", "THIS_WEEK", "THIS_MONTH", "FUTURE"]:
        group_assignments = groups[group_name]
        if not group_assignments:
            continue
        
        if group_name == "OVERDUE":
            print(f"\n🔴 OVERDUE ASSIGNMENTS")
        elif group_name == "TODAY":
            print(f"\n🟠 DUE TODAY")
        elif group_name == "THIS_WEEK":
            print(f"\n🟡 DUE THIS WEEK")
        elif group_name == "THIS_MONTH":
            print(f"\n🟢 DUE THIS MONTH")
        else:
            print(f"\n🔵 FUTURE ASSIGNMENTS")
        
        print("-" * 50)
        
        for title, course, course_name, due, url, assignment_id, days in sorted(group_assignments, key=lambda x: (x[3], x[1])):
            if group_name == "OVERDUE":
                print(f"🔴 {course}: {title}")
                print(f"   Was due: {due.strftime('%A, %d %b %Y at %H:%M')}")
                print(f"   📅 {abs(days)} days overdue")
            else:
                print(f"📚 {course}: {title}")
                print(f"   ⏰ Due: {due.strftime('%A, %d %b %Y at %H:%M')}")
                print(f"   📅 {days} days left")
            
            if assignment_id:
                print(f"   🔢 Assignment ID: {assignment_id}")
            if url:
                print(f"   🔗 {url}")
            print()

def save_to_text_file():
    """Save all assignments to text file"""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cur.execute("""
        SELECT title, course_code, course_name, section, due_datetime, url, assignment_id
        FROM assignments 
        WHERE submitted = 0
        ORDER BY due_datetime, assignment_id
    """)
    
    assignments = cur.fetchall()
    conn.close()
    
    if not assignments:
        return None
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"assignments_{timestamp}.txt"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("="*60 + "\n")
        f.write("SSN LMS ASSIGNMENTS (INCLUDING ALL SUBMISSIONS)\n")
        f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Total entries: {len(assignments)}\n")
        f.write("="*60 + "\n\n")
        
        by_month = {}
        for title, course, course_name, section, due_str, url, assignment_id in assignments:
            due = datetime.fromisoformat(due_str)
            month_key = due.strftime("%B %Y")
            if month_key not in by_month:
                by_month[month_key] = []
            by_month[month_key].append((title, course, course_name, section, due, url, assignment_id))
        
        for month, month_assignments in sorted(by_month.items()):
            f.write(f"\n{'='*40}\n")
            f.write(f"{month}\n")
            f.write(f"{'='*40}\n\n")
            
            for title, course, course_name, section, due, url, assignment_id in month_assignments:
                days_left = (due - datetime.now(IST)).days
                
                f.write(f"📚 {course}: {title}\n")
                f.write(f"   Course: {course_name} (Section {section})\n")
                f.write(f"   Due: {due.strftime('%A, %d %B %Y at %H:%M')}\n")
                f.write(f"   Days left: {days_left}\n")
                if assignment_id:
                    f.write(f"   Assignment ID: {assignment_id}\n")
                if url:
                    f.write(f"   URL: {url}\n")
                f.write("\n")
    
    print(f"📄 Full list saved to: {filename}")
    return filename

if __name__ == "__main__":
    print("="*70)
    print("🎓 SSN LMS - FIXED VERSION (SHOWS ALL DUPLICATES)")
    print("="*70)
    
    # Clear database
    clear_database()
    
    # Run scraper (SAME WORKING LOGIC)
    assignments = dashboard_scraper()
    
    if assignments:
        # Display results
        display_results()
        
        # Save to text file
        text_file = save_to_text_file()
        
        print(f"\n📊 Summary:")
        print(f"   Total assignment entries: {len(assignments)}")
        if text_file:
            print(f"   Saved to: {text_file}")
    else:
        print("\n❌ No assignments found.")
    
    print("\n" + "="*70)
    print("✅ Done! All assignments shown (including duplicates).")
    print("="*70)