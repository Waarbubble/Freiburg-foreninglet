import requests
from bs4 import BeautifulSoup
import getpass
import sys
import os
from dotenv import load_dotenv
from urllib.parse import urljoin

class BifrostClient:
    BASE_URL = "https://bifrost.foreninglet.dk"
    LOGIN_URL = f"{BASE_URL}/memberportal/login"
    FRONTPAGE_URL = f"{BASE_URL}/memberportal/frontpage"
    PROFILE_URL = f"{BASE_URL}/memberportal/masterdata#" # Common path
    EVENTS_URL = f"{BASE_URL}/memberportal/memberactivities"
    MEMBER_URLS = [f"{BASE_URL}/memberportal/subscribe/index/97990", f"{BASE_URL}/memberportal/subscribe/index/97991"]
    AUTOMATIC_PAYMENT_URL = f"{BASE_URL}/memberportal/recurring"
    ALL_AVAILABLE_EVENTS_URL = f"{BASE_URL}/memberportal/enrollment"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })

    def login(self, email, password):
        print(f"Connecting to login page...")
        try:
            # 1. Get the login page to setup session and find club_id
            response = self.session.get(self.LOGIN_URL)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            # Find club_id
            club_id_input = soup.find('input', {'name': 'club_id'})
            club_id = club_id_input['value'] if club_id_input else '3322' # Fallback
            print(f"Using club_id: {club_id}")

            # 2. Perform AJAX lookup
            lookup_url = f"{self.BASE_URL}/memberportal/login/lookupmembers"
            print(f"Looking up member at {lookup_url}...")
            
            payload = {
                'username': email,
                'password': password,
                'change_account_enabled': '0',
                'remember_me': '0', # or '1'
                'club_id': club_id
            }
            
            headers = {
                'Referer': self.LOGIN_URL,
                'X-Requested-With': 'XMLHttpRequest',
                'Origin': self.BASE_URL
            }
            
            lookup_resp = self.session.post(lookup_url, data=payload, headers=headers)
            lookup_resp.raise_for_status()
            
            # The response is a JSON list of members
            # If empty -> login failed
            if lookup_resp.text.strip() == "[]":
                print("Login failed: No member found (invalid credentials).")
                return False
            
            try:
                members = lookup_resp.json()
            except Exception as e:
                print(f"Failed to parse lookup response: {lookup_resp.text[:100]}...")
                return False

            if not members:
                print("Login failed: Empty member list.")
                return False
            
            # Select first member
            member = members[0]
            print(f"Found member: {member.get('member_full_name', 'Unknown')} (ID: {member.get('member_id')})")
            
            # 3. Perform actual login (doLoginPost)
            post_url = member.get('post_url')
            if not post_url:
                 # Fallback based on HTML form action default
                 post_url = f"{self.BASE_URL}/memberportal/login/dologin"

            # In case post_url is relative
            if not post_url.startswith('http'):
                post_url = urljoin(self.LOGIN_URL, post_url)

            login_payload = {
                'username': member.get('username'),
                'key_1': member.get('key_1'),
                'key_2': member.get('key_2'),
                'club_id': member.get('club_id'),
                'member_id': member.get('member_id')
            }
            
            print(f"Completing login via {post_url}...")
            
            # Standard form submission headers
            login_headers = {
                'Referer': self.LOGIN_URL,
                'Origin': self.BASE_URL,
                'User-Agent': self.session.headers['User-Agent']
            }

            login_resp = self.session.post(post_url, data=login_payload, headers=login_headers)
            
            if login_resp.history:
                pass # Redirects happened

            login_resp.raise_for_status()
            
            # Check success (redirect or content)
            if any(x in login_resp.url for x in ["frontpage", "dashboard"]):
                print("Login successful (redirected).")
                return True
            
            if "Log ud" in login_resp.text or "Min profil" in login_resp.text:
                 print("Login successful.")
                 return True

            print("Login completed (status check lenient)...")
            return True

        except Exception as e:
            print(f"Login error: {e}")
            return False

    def fetch_user_info(self):
        print("Fetching profile information...")
        info = {}
        try:
            # Try to fetch Frontpage first to find profile link
            fp_response = self.session.get(self.FRONTPAGE_URL)
            soup = BeautifulSoup(fp_response.text, 'html.parser')
            
            # Look for "Min profil" link
            target_url = self.FRONTPAGE_URL # Default fall back
            
            profile_link = soup.find('a', string=lambda t: t and ("Min profil" in t or "My profile" in t))
            if profile_link:
                 target_url = urljoin(self.FRONTPAGE_URL, profile_link['href'])
                 print(f"Found profile link: {target_url}")
            else:
                 # Try known common paths if link not found
                 target_url = self.PROFILE_URL
                 print(f"Trying common profile path: {target_url}")

            # Fetch profile page
            prof_response = self.session.get(target_url)
            if prof_response.status_code == 200:
                p_soup = BeautifulSoup(prof_response.text, 'html.parser')
                
                # Check for table or list of info
                # Often profile data is in DL/DT/DD or Table
                
                # Method 1: Look for DL lists
                for dt in p_soup.find_all('dt'):
                    key = dt.get_text(strip=True)
                    dd = dt.find_next_sibling('dd')
                    if dd:
                        val = dd.get_text(strip=True)
                        info[key] = val

                # Method 2: Look for form inputs that are populated (often profile is editable)
                if not info:
                    for input_tag in p_soup.find_all('input'):
                        val = input_tag.get('value')
                        name = input_tag.get('name')
                        if val and isinstance(val, str) and len(val) > 1 and input_tag.get('type') not in ['hidden', 'submit', 'password']:
                            # Try to find label
                            lbl_text = name
                            if input_tag.get('id'):
                                label = p_soup.find('label', {'for': input_tag.get('id')})
                                if label:
                                    lbl_text = label.get_text(strip=True)
                            
                            info[lbl_text] = val

                # Method 3: Look for generic text like "Navn: XXX"
                # If still empty, maybe just print Welcome message
                if not info:
                    welcome_msg = soup.find(string=lambda text: text and "Velkommen" in text)
                    if welcome_msg:
                        info['Welcome Message'] = welcome_msg.strip()
            
            if not info:
                print("Could not parse profile structure explicitly.")

            return info

        except Exception as e:
                print(f"Error fetching info: {e}")
                return {}

    def fetch_enrolled_events(self):
        print(f"Fetching enrolled events from {self.EVENTS_URL}...")
        try:
            response = self.session.get(self.EVENTS_URL)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            enrolled_events = []
            
            # Find the specific table for enrolled activities
            table = soup.find('table', id='enrolled-activities-table')
            
            if table:
                # Find the tbody - if it exists, otherwise just search inside table
                tbody = table.find('tbody')
                row_container = tbody if tbody else table
                
                rows = row_container.find_all('tr')
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 3:
                        # Column 0: ID (link text)
                        event_id_elem = cols[0].find('a')
                        event_id = event_id_elem.get_text(strip=True) if event_id_elem else cols[0].get_text(strip=True)
                        
                        # Column 1: Name (link text)
                        name_elem = cols[1].find('a')
                        name = name_elem.get_text(strip=True) if name_elem else cols[1].get_text(strip=True)
                        
                        # Column 2: Date
                        # The date cell contains hidden spans for sorting. We want the visible text.
                        # One span has style="white-space: nowrap;" which contains the visible date text.
                        date_cell = cols[2]
                        visible_date = ""
                        
                        # Try to find the visible span first
                        visible_span = date_cell.find('span', style=lambda value: value and 'white-space' in value)
                        if visible_span:
                            # Remove the hidden sort key inside it if it exists
                            hidden_inner = visible_span.find('span', style=lambda value: value and 'display: none' in value)
                            if hidden_inner:
                                # Get text only from the parent excluding the hidden child effectively
                                full_text = visible_span.get_text(strip=True)
                                hidden_text = hidden_inner.get_text(strip=True)
                                visible_date = full_text.replace(hidden_text, "").strip()
                            else:
                                visible_date = visible_span.get_text(strip=True)
                        else:
                            # Fallback: get text excluding the top-level hidden span
                            # We can just get all text and clean it up, or ignore the first hidden span
                            # Simplest valid fallback for now:
                            visible_date = date_cell.get_text(" ", strip=True) 

                        enrolled_events.append({
                            "id": event_id,
                            "name": name,
                            "date": visible_date
                        })
            
            return enrolled_events

        except Exception as e:
            print(f"Error fetching events: {e}")
            return []

    def fetch_memberships(self):
        print("Fetching membership subscriptions...")
        memberships = []
        for url in self.MEMBER_URLS:
            try:
                # print(f"Checking subscription at {url}...")
                response = self.session.get(url)
                response.raise_for_status()
                soup = BeautifulSoup(response.text, 'html.parser')
                
                name = "Unknown Subscription"

                # Strategy 1: Look for specific form legend or header in the main content area
                # Often in these systems, the subscription name is in a legend or a specific div
                main_content = soup.find('div', id='content') or soup.find('div', class_='container')
                if main_content:
                     header = main_content.find(['h1', 'h2', 'h3', 'legend'])
                     if header:
                         name = header.get_text(strip=True)

                # Strategy 2: Fallback to any header if main content search failed
                if name == "Unknown Subscription":
                    header = soup.find(['h1', 'h2', 'h3'])
                    if header:
                        name = header.get_text(strip=True)

                # Strategy 3: Check for bootstrap card headers
                if name == "Unknown Subscription":
                     card_header = soup.find(class_=['card-header', 'panel-heading'])
                     if card_header:
                         name = card_header.get_text(strip=True)

                # Strategy 4: Page Title
                if name == "Unknown Subscription" and soup.title:
                    name = soup.title.get_text(strip=True).replace(" - ForeningLet", "")

                # Check for "Du er tilmeldt"
                is_paid = "Du er tilmeldt" in response.text
                
                memberships.append({
                    "name": name,
                    "paid": is_paid,
                    "url": url
                })
            except Exception as e:
                print(f"Error fetching membership {url}: {e}")
        
        return memberships

    def fetch_upcoming_freiburg_events(self):
        print(f"Fetching upcoming Freiburg events from {self.ALL_AVAILABLE_EVENTS_URL}...")
        try:
            response = self.session.get(self.ALL_AVAILABLE_EVENTS_URL)
            response.raise_for_status()
            
            # Check for redirects (e.g. back to login)
            if response.url != self.ALL_AVAILABLE_EVENTS_URL:
                 print(f"WARNING: Redirected to {response.url}")

            # DEBUG: Save raw HTML
            with open("debug_enrollment.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            print("DEBUG: Saved raw HTML to debug_enrollment.html")

            soup = BeautifulSoup(response.text, 'html.parser')

            # DEBUG: Check if Freiburg is mentioned anywhere
            if "Freiburg" in response.text:
                print("DEBUG: The string 'Freiburg' was found in the raw HTML.")
            else:
                print("DEBUG: The string 'Freiburg' was NOT found in the raw HTML.")

            events = []
            
            # Strategy: Search through candidate headers (class=activity-name OR any h3/h4/h5)
            # This is more robust than looking for just one tag type
            raw_candidates = soup.find_all(class_='activity-name') + soup.find_all(['h3', 'h4', 'h5'])
            
            # Deduplicate elements
            candidates = []
            seen_elements = set()
            for tag in raw_candidates:
                if tag not in seen_elements:
                    candidates.append(tag)
                    seen_elements.add(tag)

            print(f"DEBUG: Checking {len(candidates)} candidate elements.")
            
            for header in candidates:
                title = header.get_text(strip=True)
                
                # Filter: Must contain Freiburg
                if "freiburg" not in title.lower():
                    continue

                # 1. URL Resolution
                link_elem = header.find('a')
                # If not in header, check parent container for a link (e.g., "Tilmeld" button)
                container = header.find_parent(class_=['row', 'list-group-item']) or header.parent

                # Filter: Discard if registration deadline is exceeded
                if container and "Tilmeldingsfrist er overskredet" in container.get_text():
                    continue

                if not link_elem and container:
                     link_elem = container.find('a')
                
                href = link_elem.get('href') if link_elem else ""

                # 2. Date Resolution
                date_str = "See details"
                
                # Attempt 1: Look for explicit date/time class in the container
                if container:
                    date_elem = container.find(class_=lambda c: c and ('date' in c or 'time' in c))
                    if date_elem:
                        date_str = date_elem.get_text(" ", strip=True)

                # Attempt 2: Look for previous sibling element (often date is to the left)
                if date_str == "See details":
                    # Current element might be wrapped in a column or just be a sibling
                    current_block = header.find_parent(class_=lambda x: x and 'col' in x) or header
                    prev_sib = current_block.find_previous_sibling()
                    if prev_sib:
                        date_str = prev_sib.get_text(" ", strip=True)
                
                # Attempt 3: If still nothing, take all text from container except title
                if (date_str == "See details" or not date_str) and container:
                     full_text = container.get_text(" ", strip=True)
                     # Remove the title text to hopefully leave the date
                     clean_text = full_text.replace(title, "").strip()
                     # Heuristic: Dates aren't usually massive, so if it's short, use it
                     if len(clean_text) > 0 and len(clean_text) < 100:
                         date_str = clean_text
                
                events.append({
                    "title": title,
                    "date": date_str,
                    "url": urljoin(self.ALL_AVAILABLE_EVENTS_URL, href) if href else ""
                })

            # Strategy B: Tables (Fallback)
            if not events:
                tables = soup.find_all('table')
                if tables:
                    print(f"DEBUG: Checking {len(tables)} tables as fallback.")
                    for table in tables:
                        for row in table.find_all('tr'):
                            cols = row.find_all('td')
                            if not cols: continue
                            
                            # Simple text check
                            row_text = row.get_text(" ", strip=True)
                            if "freiburg" in row_text.lower():
                                link = row.find('a')
                                title = link.get_text(strip=True) if link else cols[0].get_text(strip=True)
                                events.append({
                                    "title": title,
                                    "date": cols[1].get_text(strip=True) if len(cols) > 1 else "Unknown",
                                    "url": urljoin(self.ALL_AVAILABLE_EVENTS_URL, link.get('href')) if link else ""
                                })

            print(f"Found {len(events)} events matching 'Freiburg'")
            return events

        except Exception as e:
            print(f"Error fetching filtered events: {e}")
            return []


def main():
    print("--- Bifrost (ForeningLet) User Info Fetcher ---")
    
    load_dotenv()
    email = os.getenv("EMAIL")
    password = os.getenv("PASSWORD")

    if len(sys.argv) == 3:
        email = sys.argv[1]
        password = sys.argv[2]
    
    if not email:
        email = input("Email: ")
    if not password:
        password = getpass.getpass("Password: ")

    client = BifrostClient()
    if client.login(email, password):
        data = client.fetch_user_info()
        """print("\n--- User Information ---")
        if data:
            for k, v in data.items():
                print(f"{k}: {v}")
        else:
            print("No detailed information found.")
            
        print("\n--- Enrolled Events ---")
        events = client.fetch_enrolled_events()
        if events:
            for i, event in enumerate(events, 1):
                print(f"Event {i}:")
                for k, v in event.items():
                    print(f"  {k}: {v}")
                print("-" * 20)
        else:
            print("No enrolled events found.")

        print("\n--- Membership Subscriptions ---")
        memberships = client.fetch_memberships()
        if memberships:
            for sub in memberships:
                status = "PAID (Tilmeldt)" if sub['paid'] else "Not Enrolled"
                print(f"{sub['name']}: {status}") 
        else:
            print("No membership info found.")"""

        print("\n--- Upcoming Freiburg Events ---")
        freiburg_events = client.fetch_upcoming_freiburg_events()
        print("")
        if freiburg_events:
            for event in freiburg_events:
                print(f"Title: {event['title']}")
                print(f"Date: {event['date']}")
                print(f"URL: {event['url']}")
                print("-" * 20)
        else:
            print("No upcoming Freiburg events found.")
    else:
        print("Login failed or cancelled.")

if __name__ == "__main__":
    main()
