import os
import re
import time
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

# Color Constants provided by User
ColorRed     = "\033[31m"
ColorGreen   = "\033[32m"
ColorYellow  = "\033[93m"
ColorBlue    = "\033[94m"
ColorMagenta = "\033[95m"
ColorCyan    = "\033[96m"
ColorWhite   = "\033[97m"
ColorGray    = "\033[90m"
ColorPurple  = "\033[35m"
ColorOrange  = "\033[33m"
ColorBold    = "\033[1m"
ColorReset   = "\033[0m"

BASE_URL = "http://mail.mcbotmfa.club"

class TZI_Checker:
    def __init__(self):
        self.results_dir = ""
        self.valid_file = ""
        self.ongoing_file = ""
        self.dead_file = ""
        self.error_file = ""
        self.found_accounts = []
        self.total_checked = 0

    def setup_results(self):
        now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.results_dir = os.path.join("results", now)
        self.mails_dir = os.path.join(self.results_dir, "mails")
        os.makedirs(self.results_dir, exist_ok=True)
        os.makedirs(self.mails_dir, exist_ok=True)
        self.valid_file = os.path.join(self.results_dir, "VALID.txt")
        self.ongoing_file = os.path.join(self.results_dir, "ONGOING.txt")
        self.ongoing_root_file = f"ongoing-{now}.txt"
        self.ms_canceled_file = os.path.join(self.results_dir, "MS_CANCELED.txt")
        self.dead_file = os.path.join(self.results_dir, "DEAD.txt")
        self.error_file = os.path.join(self.results_dir, "ERROR.txt")

    def log_result(self, file_path, data):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(data + "\n")

    def select_folder(self):
        while True:
            os.system('cls' if os.name == 'nt' else 'clear')
            print(f"{ColorCyan}{ColorBold}TZI AML CHECKER - BY Chuborn{ColorReset}\n")
            folder = input("Paste the folder path to scan (or press Enter for current folder): ").strip().strip('"')
            if not folder:
                folder = os.getcwd()

            folder = os.path.abspath(folder)
            if os.path.isdir(folder):
                return folder

            print(f"{ColorRed}Folder not found: {folder}{ColorReset}")
            time.sleep(2)

    def find_results_folder(self, selected_folder):
        direct_results = os.path.join(selected_folder, "results")
        if os.path.isdir(direct_results):
            return direct_results

        for root, dirs, _ in os.walk(selected_folder):
            for d in dirs:
                if d.lower() == "results":
                    return os.path.join(root, d)
        return None

    def get_hanging_hit_files(self, results_folder):
        matched_files = []
        for root, _, files in os.walk(results_folder):
            for file_name in files:
                if not file_name.lower().endswith(".txt"):
                    continue
                lowered = file_name.lower()
                if "hanging" in lowered or "hit" in lowered:
                    matched_files.append(os.path.join(root, file_name))
        return matched_files

    def extract_emails_from_files(self, file_paths):
        # Regex: find email:password where email is @mcbotmfa.club or @mcckmfa.club
        pattern = r'([a-zA-Z0-9._%+-]+@(mcbotmfa\.club|mcckmfa\.club|tzick\.club)):([^\s|]+)'
        self.found_accounts = []
        seen = set()
        for file_path in file_paths:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    match = re.search(pattern, line)
                    if match:
                        record = (line, match.group(1), match.group(3))
                        if record not in seen:
                            self.found_accounts.append(record)
                            seen.add(record)
        return len(self.found_accounts)

    def check_account(self, full_line, email, password):
        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        })
        
        try:
            # Login
            r = session.get(f"{BASE_URL}/?_task=login", timeout=15)
            soup = BeautifulSoup(r.text, "html.parser")
            token_input = soup.find("input", {"name": "_token"})
            if not token_input:
                self.log_result(self.error_file, f"{full_line} | Reason: No CSRF token")
                print(f"{ColorGray}{email} -> ERROR{ColorReset}")
                return

            token = token_input["value"]
            data = {
                "_token": token,
                "_task": "login",
                "_action": "login",
                "_url": "_task=login",
                "_user": email,
                "_pass": password,
            }
            r = session.post(f"{BASE_URL}/?_task=login", data=data, allow_redirects=True, timeout=15)
            
            if not ("_task=mail" in r.url or "Inbox" in r.text):
                self.log_result(self.error_file, f"{full_line} | Reason: Login failed")
                print(f"{ColorGray}{email} -> ERROR{ColorReset}")
                return

            # Fetch Inbox
            params = {
                "_task": "mail",
                "_action": "list",
                "_mbox": "INBOX",
                "_remote": "1",
                "_refresh": "1",
                "_layout": "widescreen",
                "_page": "1"
            }
            r = session.get(f"{BASE_URL}/", params=params, timeout=15)
            
            try:
                data = r.json()
                exec_text = data.get("exec", "")
                uids = re.findall(r'this\.add_message_row\((\d+)', exec_text)
                
                if not uids:
                    self.log_result(self.error_file, f"{full_line} | Reason: No mails")
                    print(f"{ColorGray}{email} -> ERROR{ColorReset}")
                    return

                # Collect all bodies first (cleaned plain text)
                full_body_text = ""
                for uid in uids:
                    content_params = {
                        "_task": "mail",
                        "_action": "preview",
                        "_uid": uid,
                        "_mbox": "INBOX",
                        "_framed": "1"
                    }
                    cr = session.get(f"{BASE_URL}/", params=content_params, timeout=15)
                    
                    # Parse with BeautifulSoup for plain text
                    soup = BeautifulSoup(cr.text, "html.parser")
                    
                    # Extract Subject
                    subject_elem = soup.find("h2", class_="subject")
                    subject = subject_elem.get_text(strip=True).replace("Open in new window", "").strip() if subject_elem else "No Subject"
                    
                    # Extract Body
                    body_div = soup.find("div", id="message-htmlpart1") or soup.find("div", class_="rcmBody")
                    if body_div:
                        body_text = body_div.get_text(separator="\n", strip=True)
                        body_text = re.sub(r'\n{3,}', '\n\n', body_text).strip()
                    else:
                        body_text = "(No body found or empty)"
                    
                    full_body_text += f"UID: {uid} | SUBJECT: {subject}\n"
                    full_body_text += f"{body_text}\n"
                    full_body_text += "="*60 + "\n\n"

                # Save all mail content
                mail_save_path = os.path.join(self.mails_dir, f"{email}.txt")
                with open(mail_save_path, "w", encoding="utf-8") as mf:
                    mf.write(full_body_text)

                # Categorize
                if "Good news! The waiting period you started 30 days ago" in full_body_text:
                    self.log_result(self.valid_file, f"{full_line}")
                    print(f"{ColorGreen}{email} -> VALID{ColorReset}")
                elif "has been canceled." in full_body_text:
                    self.log_result(self.dead_file, f"{full_line}")
                    print(f"{ColorRed}{email} -> DEAD{ColorReset}")
                elif len(uids) == 1:
                    # Check if it's over 35 days old
                    is_old = False
                    date_elem = soup.find("td", class_="header date")
                    if date_elem:
                        date_str = date_elem.get_text(strip=True)
                        email_date = None
                        m1 = re.search(r'(\d{4})-(\d{2})-(\d{2})', date_str)
                        if m1:
                            email_date = datetime(int(m1.group(1)), int(m1.group(2)), int(m1.group(3)))
                        else:
                            m2 = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', date_str)
                            if m2:
                                email_date = datetime(int(m2.group(3)), int(m2.group(2)), int(m2.group(1)))
                        
                        if email_date:
                            delta = datetime.now() - email_date
                            if delta.days > 35:
                                is_old = True
                    
                    if is_old:
                        self.log_result(self.ms_canceled_file, f"{full_line}")
                        print(f"{ColorPurple}{email} -> MS CANCELED?{ColorReset}")
                    else:
                        self.log_result(self.ongoing_file, f"{full_line}")
                        self.log_result(self.ongoing_root_file, f"{full_line}")
                        print(f"{ColorYellow}{email} -> ONGOING{ColorReset}")
                else:
                    self.log_result(self.error_file, f"{full_line} | Reason: No specific status found")
                    print(f"{ColorGray}{email} -> ERROR{ColorReset}")

            except Exception as e:
                self.log_result(self.error_file, f"{full_line} | Reason: {str(e)}")
                print(f"{ColorGray}{email} -> ERROR{ColorReset}")

        except Exception as e:
            self.log_result(self.error_file, f"{full_line} | Reason: {str(e)}")
            print(f"{ColorGray}{email} -> ERROR{ColorReset}")

    def run(self):
        os.system('cls' if os.name == 'nt' else 'clear')
        selected_folder = self.select_folder()
        results_folder = self.find_results_folder(selected_folder)
        if not results_folder:
            print(f"{ColorRed}No 'results' folder found under: {selected_folder}{ColorReset}")
            return

        matched_files = self.get_hanging_hit_files(results_folder)
        if not matched_files:
            print(f"{ColorRed}No .txt files with 'hanging' or 'hit' in the filename were found.{ColorReset}")
            return

        count = self.extract_emails_from_files(matched_files)
        os.system('cls' if os.name == 'nt' else 'clear')
        print(f"{ColorCyan}{ColorBold}TZI AML CHECKER - BY Chuborn{ColorReset}\n")
        print(f"selected folder: {selected_folder}")
        print(f"results folder: {results_folder}")
        print(f"matched text files: {len(matched_files)}")
        print(f"found {count} aml in matched files\n")
        
        if count == 0:
            return

        self.setup_results()

        with ThreadPoolExecutor(max_workers=10) as executor:
            for full_line, email, password in self.found_accounts:
                executor.submit(self.check_account, full_line, email, password)

if __name__ == "__main__":
    checker = TZI_Checker()
    checker.run()
