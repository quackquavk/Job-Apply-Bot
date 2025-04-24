import os
import json
import pickle
import time
import random
import re
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementNotInteractableException
from webdriver_manager.chrome import ChromeDriverManager
from langchain_google_genai import GoogleGenerativeAI
from langchain.prompts import PromptTemplate
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.safari.service import Service as SafariService

# Load environment variables
load_dotenv()

# Get credentials and job search parameters from .env file
LINKEDIN_EMAIL = os.getenv('LINKEDIN_EMAIL')
LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
JOB_TITLE = os.getenv('JOB_TITLE')
JOB_LOCATION = os.getenv('JOB_LOCATION')
RESUME_PATH = os.getenv('RESUME_PATH', '')  # Path to your resume file
PHONE_NUMBER = os.getenv('PHONE_NUMBER', '')  # Your phone number
USER_WEBSITE = os.getenv('USER_WEBSITE', '')  # Your personal website
MAX_APPLICATIONS = int(os.getenv('MAX_APPLICATIONS', '10'))  # Maximum number of applications to submit

# Path for storing cookies
COOKIES_FILE = 'linkedin_cookies.pkl'

# Path for application data
RESUME_DATA_FILE = 'resume_data.json'

def setup_driver():
    """Set up and return a configured Safari WebDriver"""
    safari_options = webdriver.SafariOptions()
    # Then, in the Develop menu, ensure "Allow Remote Automation" is checked.

    service = SafariService()  # No need for a separate driver manager
    driver = webdriver.Safari(service=service, options=safari_options)
    driver.maximize_window()
    return driver

def save_cookies(driver):
    """Save cookies to file after login"""
    with open(COOKIES_FILE, 'wb') as file:
        pickle.dump(driver.get_cookies(), file)
    print("Cookies saved successfully")

def load_cookies(driver):
    """Load cookies from file"""
    with open(COOKIES_FILE, 'rb') as file:
        cookies = pickle.load(file)
    for cookie in cookies:
        driver.add_cookie(cookie)
    print("Cookies loaded successfully")

def login_with_credentials(driver):
    """Login to LinkedIn using credentials from .env file"""
    driver.get("https://www.linkedin.com/login")
    
    try:
        # Wait for email field and enter email
        email_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        email_field.send_keys(LINKEDIN_EMAIL)
        
        # Enter password
        password_field = driver.find_element(By.ID, "password")
        password_field.send_keys(LINKEDIN_PASSWORD)
        
        # Click login button
        login_button = driver.find_element(By.CSS_SELECTOR, "button[type='submit']")
        login_button.click()
        
        # Wait for successful login
        WebDriverWait(driver, 10).until(
            EC.url_contains("linkedin.com/feed")
        )
        print("Successfully logged in with credentials")
        
        # Save cookies for future use
        save_cookies(driver)
        return True
    except Exception as e:
        print(f"Login failed: {e}")
        return False

def login_with_cookies(driver):
    """Attempt to login using saved cookies"""
    try:
        driver.get("https://www.linkedin.com")
        load_cookies(driver)
        driver.get("https://www.linkedin.com/feed")
        
        # Check if login was successful
        WebDriverWait(driver, 5).until(
            EC.url_contains("linkedin.com/feed")
        )
        print("Successfully logged in using cookies")
        return True
    except Exception as e:
        print(f"Cookie login failed: {e}")
        return False

def setup_llm():
    """Set up Google Gemini via LangChain"""
    llm = GoogleGenerativeAI(
        model="gemini-1.5-flash",
        google_api_key=GEMINI_API_KEY,
        temperature=0.7
    )
    return llm



def navigate_to_jobs_and_search(driver, job_title, location):
    """Navigate to LinkedIn Jobs and search using the specific input elements"""
    try:
        # Navigate to Jobs page
        print("Navigating to LinkedIn Jobs page...")
        driver.get("https://www.linkedin.com/jobs/")
        time.sleep(3)  # Give page time to fully load
        
        # Try to find the job title input field using multiple selectors
        print("Looking for job title input field...")
        job_title_input = None
        
        # Try several methods to find the job title input
        try:
            # Try finding by CSS that matches job title input
            job_title_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[aria-label='Search by title, skill, or company']"))
            )
        except:
            try:
                # Try finding by CSS class
                job_title_input = driver.find_element(By.CSS_SELECTOR, ".jobs-search-box__text-input.jobs-search-box__keyboard-text-input")
            except:
                try:
                    # Try finding by partial ID
                    inputs = driver.find_elements(By.CSS_SELECTOR, "input[id*='jobs-search-box-keyword']")
                    if inputs:
                        job_title_input = inputs[0]
                except:
                    pass
        
        if not job_title_input:
            print("Could not find job title input field")
            return False
        
        # Clear and fill the job title field
        print(f"Entering job title: {job_title}")
        job_title_input.clear()
        time.sleep(1)
        job_title_input.send_keys(job_title)
        time.sleep(1)
        
        # Find location input field
        print("Looking for location input field...")
        location_input = None
        
        try:
            # Try finding by CSS that matches location input
            location_input = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[aria-label='City, state, or zip code']"))
            )
        except:
            try:
                # Try alternative ID pattern
                inputs = driver.find_elements(By.CSS_SELECTOR, "input[id*='jobs-search-box-location']")
                if inputs:
                    location_input = inputs[0]
            except:
                pass
        
        if not location_input:
            print("Could not find location input field")
            return False
        
        # Clear and fill the location field
        print(f"Entering location: {location}")
        location_input.clear()
        time.sleep(1)
        location_input.send_keys(location)
        time.sleep(1)
        
        # Press Enter to submit the search
        print("Submitting search...")
        location_input.send_keys(Keys.RETURN)
        
        # Wait for search results to load
        print("Waiting for search results...")
        time.sleep(5)  # Initial wait for page load
        
        try:
            # Try to detect if search results have loaded by looking for common elements
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-search-results-list, .jobs-search__job-details"))
            )
            print("Job search completed successfully")
            return True
        except:
            # If specific elements aren't found, check if URL contains job search parameters
            current_url = driver.current_url
            if "keywords=" in current_url and ("location=" in current_url or "geoId=" in current_url):
                print("Job search URL detected, search appears successful")
                return True
            else:
                print("Could not confirm if job search was successful")
                return False
            
    except Exception as e:
        print(f"Error during job search: {e}")
        return False

def click_easy_apply_filter(driver):
    """Click the Easy Apply filter button"""
    try:
        print("Looking for Easy Apply filter button...")
        
        # Try multiple methods to find and click the Easy Apply filter
        try:
            # Try by ID first as provided
            easy_apply_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.ID, "searchFilter_applyWithLinkedin"))
            )
            print("Found Easy Apply filter by ID")
        except:
            try:
                # Try by aria-label
                easy_apply_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Easy Apply filter.']")
                print("Found Easy Apply filter by aria-label")
            except:
                try:
                    # Try by text content
                    buttons = driver.find_elements(By.TAG_NAME, "button")
                    for button in buttons:
                        if "Easy Apply" in button.text:
                            easy_apply_button = button
                            print("Found Easy Apply filter by text content")
                            break
                except:
                    # Try one more CSS selector approach
                    try:
                        easy_apply_button = driver.find_element(By.CSS_SELECTOR, ".artdeco-pill--choice:contains('Easy Apply')")
                        print("Found Easy Apply filter by CSS class")
                    except:
                        easy_apply_button = None
        
        if not easy_apply_button:
            print("Could not find Easy Apply filter button")
            return False
        
        # Click the Easy Apply button
        print("Clicking Easy Apply filter button...")
        driver.execute_script("arguments[0].click();", easy_apply_button)
        time.sleep(3)  # Wait for filter to apply
        
        # Check if filter is applied
        try:
            # Look for visual indication of filter being selected (is this filter selected/active?)
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "button[aria-checked='true'][aria-label='Easy Apply filter.']"))
            )
            print("Easy Apply filter was successfully applied")
            
            # Verify job listings are updated
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-search-results-list"))
            )
            print("Job listings updated with Easy Apply filter")
            return True
        except:
            print("Could not confirm if Easy Apply filter was applied")
            return False
        
    except Exception as e:
        print(f"Error clicking Easy Apply filter: {e}")
        return False

def load_resume_data():
    """Load resume data from JSON file or create if not exists"""
    try:
        if os.path.exists(RESUME_DATA_FILE):
            with open(RESUME_DATA_FILE, 'r') as file:
                return json.load(file)
        else:
            # Create a basic resume data template
            resume_data = {
                "personal_info": {
                    "name": "Your Name",
                    "email": LINKEDIN_EMAIL,
                    "phone": PHONE_NUMBER,
                    "address": "Your Address",
                    "linkedin": f"https://www.linkedin.com/in/your-profile",
                    "website": USER_WEBSITE
                },
                "education": [
                    {
                        "school": "Your University",
                        "degree": "Your Degree",
                        "field_of_study": "Your Field",
                        "start_date": "MM/YYYY",
                        "end_date": "MM/YYYY",
                        "gpa": "4.0"
                    }
                ],
                "work_experience": [
                    {
                        "company": "Your Last Company",
                        "title": "Your Title",
                        "location": "City, State",
                        "start_date": "MM/YYYY",
                        "end_date": "MM/YYYY",
                        "description": "Brief description of your role"
                    }
                ],
                "skills": ["Skill 1", "Skill 2", "Skill 3"],
                "certifications": ["Certification 1", "Certification 2"],
                "languages": ["English"],
                "questions": {
                    "years_of_experience": "3",
                    "willing_to_relocate": "Yes",
                    "willing_to_travel": "Yes",
                    "preferred_work_setting": "Hybrid",
                    "salary_expectation": "$80,000 - $100,000",
                    "preferred_start_date": "As soon as possible",
                    "visa_sponsorship_required": "No",
                    "cleared_security_clearance": "No"
                }
            }
            
            # Save template to file
            with open(RESUME_DATA_FILE, 'w') as file:
                json.dump(resume_data, file, indent=4)
            
            print(f"Created template resume data file at {RESUME_DATA_FILE}. Please update with your information.")
            return resume_data
    except Exception as e:
        print(f"Error loading resume data: {e}")
        return None

def process_job_listings(driver, llm, max_applications=10):
    """Process through the list of jobs and apply to them"""
    print("Processing job listings...")
    applied_count = 0
    jobs_viewed = 0
    applied_jobs = []
    
    # Load resume data for application responses
    resume_data = load_resume_data()
    if not resume_data:
        print("Failed to load resume data, cannot proceed with applications")
        return False
    
    try:
        # Wait for the job list to load with improved selector
        print("Waiting for job listings to load...")
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-search-results-list, .scaffold-layout__list"))
        )
        time.sleep(3)  # Additional wait to ensure full loading
        
        print("Identifying job cards...")
        # Try multiple selectors for job cards
        job_cards = []
        for selector in [
            ".job-card-container",
            ".jobs-search-results__list-item",
            "li.jobs-search-results__list-item",
            ".artdeco-list__item"
        ]:
            job_cards = driver.find_elements(By.CSS_SELECTOR, selector)
            if job_cards:
                print(f"Found {len(job_cards)} job cards using selector: {selector}")
                break
        
        if not job_cards:
            print("No job cards found. Attempting alternative approach...")
            # Try to get all job cards by their parent container
            containers = driver.find_elements(By.CSS_SELECTOR, ".jobs-search-results-list")
            if containers:
                print("Found jobs container, looking for cards within it...")
                job_cards = containers[0].find_elements(By.XPATH, "./div")
                print(f"Found {len(job_cards)} job cards using container approach")
        
        if not job_cards:
            print("Could not locate job cards. Please check LinkedIn's layout or try another search.")
            return False
        
        # Process job cards
        while applied_count < max_applications and jobs_viewed < len(job_cards):
            try:
                # Close any open modals before proceeding
                try:
                    close_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Dismiss']")
                    for button in close_buttons:
                        if button.is_displayed():
                            driver.execute_script("arguments[0].click();", button)
                            time.sleep(1)
                except:
                    pass
                
                # Get the current job card
                current_job = job_cards[jobs_viewed]
                jobs_viewed += 1
                
                print(f"Processing job {jobs_viewed}/{len(job_cards)}...")
                
                # Scroll the job card into view
                driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", current_job)
                time.sleep(1)
                
                # Click on the job card with retry mechanism
                job_clicked = False
                attempts = 0
                while not job_clicked and attempts < 3:
                    try:
                        driver.execute_script("arguments[0].click();", current_job)
                        job_clicked = True
                    except:
                        try:
                            # Alternative click method
                            action = webdriver.ActionChains(driver)
                            action.move_to_element(current_job).click().perform()
                            job_clicked = True
                        except:
                            attempts += 1
                            time.sleep(1)
                
                if not job_clicked:
                    print("Failed to click job card, skipping to next job")
                    continue
                
                # Wait for job details to load
                time.sleep(2)
                
                # Get job details
                try:
                    job_title_element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".jobs-unified-top-card__job-title, .job-details-jobs-unified-top-card__job-title"))
                    )
                    job_title = job_title_element.text.strip()
                    
                    company_element = driver.find_element(By.CSS_SELECTOR, ".jobs-unified-top-card__company-name, .job-details-jobs-unified-top-card__company-name")
                    company = company_element.text.strip()
                    
                    print(f"Viewing: {job_title} at {company}")
                except:
                    print("Could not extract job details, but continuing anyway")
                    job_title = "Unknown Position"
                    company = "Unknown Company"
                
                # Check for Easy Apply button with comprehensive selectors
                easy_apply_found = False
                for selector in [
                    ".jobs-apply-button",
                    "button[aria-label='Easy Apply']",
                    "button.jobs-apply-button",
                    ".jobs-apply-button--top-card",
                    "button[data-control-name='jobdetails_topcard_inapply']"
                ]:
                    try:
                        easy_apply_button = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        print(f"Found Easy Apply button using selector: {selector}")
                        easy_apply_found = True
                        break
                    except:
                        continue
                
                if not easy_apply_found:
                    print("No Easy Apply button found for this job, skipping")
                    continue
                
                # Click Easy Apply button
                try:
                    # Scroll to ensure button is in view
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", easy_apply_button)
                    time.sleep(1)
                    
                    # Try clicking
                    driver.execute_script("arguments[0].click();", easy_apply_button)
                    time.sleep(2)
                    
                    # Handle the application process
                    if handle_application_process(driver, llm, resume_data, job_title, company):
                        applied_count += 1
                        applied_jobs.append({"company": company, "title": job_title})
                        print(f"Successfully applied to: {job_title} at {company}")
                        print(f"Application {applied_count}/{max_applications} completed")
                        
                        # Add random delay between applications
                        delay = random.uniform(5, 10)
                        print(f"Waiting {delay:.1f} seconds before next application...")
                        time.sleep(delay)
                    else:
                        print(f"Failed to complete application for: {job_title} at {company}")
                        
                        # Try to close any open dialogs
                        try:
                            close_buttons = driver.find_elements(By.CSS_SELECTOR, "button[aria-label='Dismiss'], button[aria-label='Close']")
                            for button in close_buttons:
                                if button.is_displayed():
                                    driver.execute_script("arguments[0].click();", button)
                                    time.sleep(1)
                        except:
                            pass
                except Exception as e:
                    print(f"Error clicking Easy Apply button: {e}")
                    continue
                
                # Check if we've reached our application limit
                if applied_count >= max_applications:
                    print(f"Reached maximum applications limit ({max_applications})")
                    break
                
            except Exception as e:
                print(f"Error processing job card: {e}")
                continue
            
            # After processing each job, check if more job cards are available
            if jobs_viewed >= len(job_cards) and applied_count < max_applications:
                print("Looking for more job cards...")
                
                # Scroll down to load more jobs
                job_list_container = driver.find_element(By.CSS_SELECTOR, ".jobs-search-results-list, .scaffold-layout__list")
                driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", job_list_container)
                time.sleep(3)
                
                # Get updated job cards
                old_count = len(job_cards)
                for selector in [
                    ".job-card-container",
                    ".jobs-search-results__list-item",
                    "li.jobs-search-results__list-item",
                    ".artdeco-list__item"
                ]:
                    job_cards = driver.find_elements(By.CSS_SELECTOR, selector)
                    if len(job_cards) > old_count:
                        print(f"Found {len(job_cards) - old_count} additional job cards")
                        break
                
                if len(job_cards) <= old_count:
                    print("No more job cards found. Ending job search.")
                    break
        
        print(f"Application process completed. Applied to {applied_count} jobs.")
        
        # Save the list of jobs we applied to
        with open("applied_jobs.json", "w") as file:
            json.dump(applied_jobs, file, indent=4)
            
        return True
        
    except Exception as e:
        print(f"Error processing job listings: {e}")
        return False

def handle_application_process(driver, llm, resume_data, job_title, company):
    """Handle the LinkedIn Easy Apply application process"""
    try:
        print("Beginning application process...")
        
        # Keep track of progress through the application
        application_completed = False
        current_step = 1
        max_steps = 10  # Safety limit to prevent infinite loops
        
        while not application_completed and current_step <= max_steps:
            print(f"Processing application step {current_step}...")
            
            # Look for form fields that need to be filled
            handle_form_fields(driver, resume_data)
            
            # Look for custom questions and handle them with LLM
            handle_custom_questions(driver, llm, resume_data, job_title, company)
            
            # Look for next/submit/review buttons
            try:
                # Check for the "Submit application" button first
                submit_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Submit application']")
                print("Found submit application button - this is the final step")
                
                # Click submit
                print("Submitting application...")
                driver.execute_script("arguments[0].click();", submit_button)
                time.sleep(2)
                
                # Check for confirmation
                try:
                    confirmation = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, ".artdeco-modal__content:contains('Application submitted')"))
                    )
                    print("Application submitted successfully!")
                except:
                    # Sometimes there's a "Done" button at the end
                    try:
                        done_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Done']")
                        done_button.click()
                        print("Clicked 'Done' button, application completed")
                    except:
                        print("No confirmation found but application may have been submitted")
                
                application_completed = True
                
            except NoSuchElementException:
                # If not submit button, look for next or continue buttons
                try:
                    # Try different selectors for next/continue buttons
                    next_button = None
                    for selector in [
                        "button[aria-label='Continue to next step']", 
                        "button[aria-label='Review your application']",
                        "button[aria-label='Next']",
                        "button:contains('Next')",
                        "button:contains('Continue')",
                        "button.artdeco-button--primary"
                    ]:
                        try:
                            next_button = driver.find_element(By.CSS_SELECTOR, selector)
                            if next_button and next_button.is_displayed() and next_button.is_enabled():
                                break
                        except:
                            continue
                    
                    if next_button:
                        print("Clicking next/continue button...")
                        driver.execute_script("arguments[0].click();", next_button)
                        time.sleep(2)
                        current_step += 1
                    else:
                        # If no next button is found, we might be on the final step
                        # but couldn't find the submit button, or there's an issue
                        print("No next/continue button found, application may be stuck")
                        # Look for completion indication or errors
                        try:
                            error = driver.find_element(By.CSS_SELECTOR, ".artdeco-inline-feedback--error")
                            print(f"Error found in form: {error.text}")
                            # Try to fix errors by handling form fields again
                            handle_form_fields(driver, resume_data)
                        except:
                            # If no specific error found, try one more time
                            if current_step == max_steps:
                                print("Reached maximum steps without completing application")
                                return False
                
                except Exception as e:
                    print(f"Error finding next/continue button: {e}")
                    # If we can't find next/continue buttons, check if there's a discard button to exit
                    try:
                        discard_button = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Discard']")
                        print("Application appears stuck, discarding")
                        driver.execute_script("arguments[0].click();", discard_button)
                        # Confirm discard if needed
                        try:
                            confirm_discard = WebDriverWait(driver, 3).until(
                                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[aria-label='Discard application']"))
                            )
                            confirm_discard.click()
                        except:
                            pass
                        return False
                    except:
                        pass
        
        return application_completed
        
    except Exception as e:
        print(f"Error during application process: {e}")
        return False

def any_selected(driver, name):
    """Check if any radio button in a group is selected"""
    if not name:
        return False
    
    selected = driver.execute_script(
        "return document.querySelector('input[name=\"" + name + "\"]:checked') != null;"
    )
    return selected

def handle_form_fields(driver, resume_data):
    """Handle various form fields in the application process"""
    try:

        # Define helper functions
        def handle_select_dropdown(driver, select_element, field_identifier, resume_data):
            """
            Handle select dropdown fields in application forms
            """
            try:
                select = Select(select_element)
                
                # Get all available options
                options = [option.text.strip() for option in select.options]
                print(f"Dropdown options for {field_identifier}: {options}")
                
                # Skip if no options or already has a selection (first item might be a placeholder)
                if not options or (len(options) > 1 and select_element.get_attribute("value") and 
                                  select_element.get_attribute("value") != options[0]):
                    print(f"Dropdown already has selection or no options")
                    return
                
                # Default to select is None (will select based on content)
                option_to_select = None
                
                # Decision logic based on field identifier and resume data
                if "visa" in field_identifier or "sponsor" in field_identifier:
                    # Visa sponsorship questions
                    need_visa = resume_data["questions"]["visa_sponsorship_required"].lower()
                    for option in options:
                        if (need_visa == "yes" and "yes" in option.lower()) or \
                           (need_visa == "no" and "no" in option.lower()):
                            option_to_select = option
                            break
                
                elif "relocate" in field_identifier:
                    # Willingness to relocate
                    relocate = resume_data["questions"]["willing_to_relocate"].lower()
                    for option in options:
                        if (relocate == "yes" and "yes" in option.lower()) or \
                           (relocate == "no" and "no" in option.lower()):
                            option_to_select = option
                            break
                
                elif "travel" in field_identifier:
                    # Willingness to travel
                    travel = resume_data["questions"]["willing_to_travel"].lower()
                    for option in options:
                        if (travel == "yes" and "yes" in option.lower()) or \
                           (travel == "no" and "no" in option.lower()):
                            option_to_select = option
                            break
                
                elif "education" in field_identifier or "degree" in field_identifier:
                    # Education level matching
                    education = resume_data.get("education", {})
                    highest_degree = education.get("highest_degree", "").lower() if isinstance(education, dict) else ""
                    
                    # Priority order for degrees (highest to lowest)
                    degree_priority = {
                        "doctorate": 5, "phd": 5, "master": 4, "bachelor": 3, "associate": 2, "high school": 1
                    }
                    
                    # Find the degree option with the closest match
                    highest_priority = 0
                    for option in options:
                        option_lower = option.lower()
                        for degree_type, priority in degree_priority.items():
                            if degree_type in option_lower and priority > highest_priority:
                                if degree_type in highest_degree or priority <= get_degree_priority(highest_degree):
                                    option_to_select = option
                                    highest_priority = priority
                
                elif "work remotely" in field_identifier or "remote" in field_identifier:
                    # Remote work preference
                    preferred_setting = resume_data["questions"]["preferred_work_setting"].lower()
                    for option in options:
                        option_lower = option.lower()
                        if ("remote" in preferred_setting and "remote" in option_lower) or \
                           ("on-site" in preferred_setting and ("onsite" in option_lower or "on-site" in option_lower)) or \
                           ("hybrid" in preferred_setting and "hybrid" in option_lower):
                            option_to_select = option
                            break
                
                # For yes/no questions, default to "Yes" if no specific matching found
                if not option_to_select:
                    # Look for yes/no options
                    for option in options:
                        if option.lower() == "yes":
                            option_to_select = option
                            break
                    
                    # If no "Yes" option or if it's not a yes/no question, select first non-placeholder option
                    if not option_to_select and len(options) > 1:
                        # Skip placeholder options like "Select an option"
                        placeholders = ["select", "choose", "please"]
                        for option in options[1:]:  # Skip first option as it's often a placeholder
                            if not any(p in option.lower() for p in placeholders):
                                option_to_select = option
                                break
                
                # Make the selection if an option was determined
                if option_to_select:
                    print(f"Selecting dropdown option: {option_to_select}")
                    select.select_by_visible_text(option_to_select)
                    time.sleep(1)
                    
            except Exception as e:
                print(f"Error handling dropdown: {e}")
                
        def any_selected(driver, radio_name):
            """Check if any radio button in a group is selected"""
            if not radio_name:
                return False
                
            radio_group = driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{radio_name}']")
            return any(radio.is_selected() for radio in radio_group)
            
        def get_degree_priority(degree_str):
            """Helper function to determine degree priority"""
            degree_lower = str(degree_str).lower()
            if "doctor" in degree_lower or "phd" in degree_lower:
                return 5
            elif "master" in degree_lower:
                return 4
            elif "bachelor" in degree_lower:
                return 3
            elif "associate" in degree_lower:
                return 2
            elif "high school" in degree_lower or "high-school" in degree_lower:
                return 1
            else:
                return 0

        # First specifically look for select elements (dropdowns)
        print("Looking specifically for dropdown/select elements...")
        select_elements = driver.find_elements(By.TAG_NAME, "select")
        print(f"Found {len(select_elements)} select elements directly")
        
        # Process any found select elements
        for select_elem in select_elements:
            try:
                # Get field identifiers
                field_id = select_elem.get_attribute("id") or ""
                field_name = select_elem.get_attribute("name") or ""
                field_aria_label = select_elem.get_attribute("aria-label") or ""
                field_label_text = ""
                
                # Try to find associated label text
                try:
                    if field_id:
                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                        field_label_text = label.text.strip()
                except:
                    pass
                
                # Combined field identifier for decision making
                field_identifier = (field_id + " " + field_name + " " + field_aria_label + " " + field_label_text).lower()
                print(f"Processing select field: {field_identifier}")
                
                # Call the dropdown handler function
                handle_select_dropdown(driver, select_elem, field_identifier, resume_data)
                
            except Exception as e:
                print(f"Error processing select element: {e}")
        
        # Continue with the original field processing logic
        print("Processing all form fields...")
        input_fields = driver.find_elements(By.CSS_SELECTOR, "input:not([type='hidden']), textarea, select")
        
        for field in input_fields:
            try:
                # Skip fields that are already filled or disabled
                if not field.is_enabled() or field.get_attribute("value"):
                    continue
                
                # Get field identifiers
                field_id = field.get_attribute("id") or ""
                field_name = field.get_attribute("name") or ""
                field_type = field.get_attribute("type") or ""
                field_aria_label = field.get_attribute("aria-label") or ""
                field_label_text = ""
                
                # Try to find associated label text
                try:
                    # Get label by for attribute matching the field id
                    if field_id:
                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{field_id}']")
                        field_label_text = label.text.strip()
                except:
                    pass
                
                # If no direct label found, try to find any label nearby
                if not field_label_text:
                    try:
                        # Look for any label near the field
                        parent_elem = field.find_element(By.XPATH, "./parent::*")
                        nearby_labels = parent_elem.find_elements(By.TAG_NAME, "label")
                        if nearby_labels:
                            field_label_text = nearby_labels[0].text.strip()
                    except:
                        pass
                
                # Combined field identifier for decision making
                field_identifier = (field_id + " " + field_name + " " + field_aria_label + " " + field_label_text).lower()
                print(f"Processing field: {field_identifier}")
                
                # Get tag name directly for accurate element type detection
                field_tag_name = field.tag_name.lower()
                
                # Handle different field types
                if field_type == "file":
                    # Resume upload field
                    if "resume" in field_identifier or "cv" in field_identifier:
                        RESUME_PATH = resume_data.get("resume_path", "")
                        if RESUME_PATH:
                            print(f"Uploading resume from {RESUME_PATH}")
                            field.send_keys(os.path.abspath(RESUME_PATH))
                            time.sleep(2)
                            
                            # Look for and click any "Upload", "Proceed", "Continue" or "Next" buttons after upload
                            try:
                                # List of possible button selectors that might appear after upload
                                upload_buttons = driver.find_elements(By.XPATH, 
                                    "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'upload') or " +
                                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'proceed') or " +
                                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue') or " +
                                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next') or " +
                                    "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'confirm')]")
                                
                                # Try clicking any upload confirmation buttons
                                for button in upload_buttons:
                                    if button.is_displayed() and button.is_enabled():
                                        print("Clicking post-upload button:", button.text.strip())
                                        driver.execute_script("arguments[0].click();", button)
                                        time.sleep(2)
                                        break
                                
                                # If no text buttons were found, try icon buttons that might be next to the upload field
                                if not upload_buttons or not any(b.is_displayed() and b.is_enabled() for b in upload_buttons):
                                    # Look for buttons near the file input field
                                    parent_elem = field.find_element(By.XPATH, "./..")
                                    nearby_buttons = parent_elem.find_elements(By.XPATH, ".//button") + \
                                                   parent_elem.find_elements(By.XPATH, "..//button")
                                    
                                    for button in nearby_buttons:
                                        if button.is_displayed() and button.is_enabled():
                                            print("Clicking nearby button after upload")
                                            driver.execute_script("arguments[0].click();", button)
                                            time.sleep(2)
                                            break
                                            
                                # Also look for any "Submit" or "Save" buttons that might be used to confirm uploads
                                if not upload_buttons:
                                    submit_buttons = driver.find_elements(By.XPATH,
                                        "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit') or " +
                                        "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'save')]")
                                    
                                    for button in submit_buttons:
                                        if button.is_displayed() and button.is_enabled():
                                            print("Clicking submit/save button after upload:", button.text.strip())
                                            driver.execute_script("arguments[0].click();", button)
                                            time.sleep(2)
                                            break
                            except Exception as e:
                                print(f"Error handling post-upload buttons: {e}")
                
                elif field_type == "checkbox":
                    # Handle checkboxes - typically consent checkboxes
                    # Usually we want to check these (agree to terms, etc.)
                    if not field.is_selected() and ("agree" in field_identifier or "consent" in field_identifier):
                        driver.execute_script("arguments[0].click();", field)
                        time.sleep(0.5)
                
                elif field_type == "radio":
                    # Handle radio buttons directly in the input loop
                    try:
                        radio_id = field_id
                        radio_name = field_name
                        radio_value = field.get_attribute("value") or ""
                        radio_label_text = field_label_text
                        
                        # Combined identifier for decision making
                        radio_identifier = (radio_id + " " + radio_name + " " + radio_label_text).lower()
                        print(f"Processing radio button: {radio_identifier} with value: {radio_value}")
                        
                        # Make decisions based on the identifier and resume data
                        should_select = False
                        
                        if "visa" in radio_identifier or "sponsor" in radio_identifier:
                            # Visa sponsorship question
                            need_visa = resume_data["questions"]["visa_sponsorship_required"].lower()
                            should_select = (need_visa == "no" and ("no" in radio_label_text.lower() or radio_value.lower() == "no")) or \
                                          (need_visa == "yes" and ("yes" in radio_label_text.lower() or radio_value.lower() == "yes"))
                        
                        elif "relocate" in radio_identifier:
                            # Willingness to relocate
                            relocate = resume_data["questions"]["willing_to_relocate"].lower()
                            should_select = (relocate == "yes" and ("yes" in radio_label_text.lower() or radio_value.lower() == "yes")) or \
                                          (relocate == "no" and ("no" in radio_label_text.lower() or radio_value.lower() == "no"))
                        
                        elif "travel" in radio_identifier:
                            # Willingness to travel
                            travel = resume_data["questions"]["willing_to_travel"].lower()
                            should_select = (travel == "yes" and ("yes" in radio_label_text.lower() or radio_value.lower() == "yes")) or \
                                          (travel == "no" and ("no" in radio_label_text.lower() or radio_value.lower() == "no"))
                        
                        elif "citizenship" in radio_identifier or "authorized" in radio_identifier:
                            # Work authorization / citizenship question
                            # Usually we want to select "Yes" for "Are you authorized to work in the US?"
                            should_select = "yes" in radio_label_text.lower() or radio_value.lower() == "yes"
                        
                        elif "work remotely" in radio_identifier or "remote" in radio_identifier:
                            # Remote work preference - match with preferred work setting
                            preferred_setting = resume_data["questions"]["preferred_work_setting"].lower()
                            should_select = ("remote" in preferred_setting and "yes" in radio_label_text.lower()) or \
                                          ("on-site" in preferred_setting and "no" in radio_label_text.lower()) or \
                                          ("hybrid" in preferred_setting and "flexible" in radio_label_text.lower())
                        
                        else:
                            # For unknown radio buttons, select "Yes" options or first option if none match
                            if "yes" in radio_label_text.lower() or radio_value.lower() == "yes" or radio_value.lower() == "true":
                                should_select = True
                            elif not any_selected(driver, radio_name):
                                # If no radio in this group is selected, select this one
                                should_select = True
                        
                        # Click the radio button if it should be selected and isn't already
                        if should_select and not field.is_selected():
                            print(f"Selecting radio button: {radio_identifier}")
                            driver.execute_script("arguments[0].click();", field)
                            time.sleep(0.5)
                            
                    except Exception as e:
                        print(f"Error handling radio button in input loop: {e}")
                
                elif field_tag_name == "select":
                    # Handle dropdown fields
                    print(f"Found select/dropdown element in main loop: {field_identifier}")
                    handle_select_dropdown(driver, field, field_identifier, resume_data)
                    time.sleep(0.5)
                
                else:
                    # Text input fields
                    if "phone" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["phone"])
                    elif "email" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["email"])
                    elif "name" in field_identifier and "first" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["name"].split()[0])
                    elif "name" in field_identifier and "last" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["name"].split()[-1])
                    elif "website" in field_identifier or "portfolio" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["website"])
                    elif "salary" in field_identifier:
                        field.send_keys(resume_data["questions"]["salary_expectation"])
                    elif "address" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["address"])
                    elif "linkedin" in field_identifier:
                        field.send_keys(resume_data["personal_info"]["linkedin"])
                    else:
                        # For other text fields, leave blank as they might be optional
                        pass
                    
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Error handling form field: {e}")
        
        # Additional scan for radio buttons that might have been missed
        radio_buttons = driver.find_elements(By.CSS_SELECTOR, "input[type='radio']")
        print(f"Found {len(radio_buttons)} radio buttons in additional scan")
        
        for radio in radio_buttons:
            try:
                if not radio.is_enabled():
                    continue
                
                radio_id = radio.get_attribute("id") or ""
                radio_name = radio.get_attribute("name") or ""
                radio_value = radio.get_attribute("value") or ""
                radio_label_text = ""
                
                # Try to find associated label text
                try:
                    if radio_id:
                        label = driver.find_element(By.CSS_SELECTOR, f"label[for='{radio_id}']")
                        radio_label_text = label.text.strip()
                except:
                    # If no direct label, try to find label from parent or siblings
                    try:
                        parent = radio.find_element(By.XPATH, "./parent::*")
                        label_candidates = parent.find_elements(By.TAG_NAME, "label") + \
                                         parent.find_elements(By.TAG_NAME, "span")
                        if label_candidates:
                            radio_label_text = label_candidates[0].text.strip()
                    except:
                        pass
                
                # Check if already selected
                is_selected = radio.is_selected()
                if is_selected:
                    print(f"Radio button already selected: {radio_name} = {radio_value}")
                    continue
                
                # Combined identifier for decision making
                radio_identifier = (radio_id + " " + radio_name + " " + radio_label_text).lower()
                print(f"Additional scan - radio button: {radio_identifier} with value: {radio_value}")
                
                # Make decisions based on the identifier and resume data
                should_select = False
                
                if "visa" in radio_identifier or "sponsor" in radio_identifier:
                    # Visa sponsorship question
                    need_visa = resume_data["questions"]["visa_sponsorship_required"].lower()
                    should_select = (need_visa == "no" and ("no" in radio_label_text.lower() or "no" in radio_value.lower())) or \
                                  (need_visa == "yes" and ("yes" in radio_label_text.lower() or "yes" in radio_value.lower()))
                
                elif "relocate" in radio_identifier:
                    # Willingness to relocate
                    relocate = resume_data["questions"]["willing_to_relocate"].lower()
                    should_select = (relocate == "yes" and ("yes" in radio_label_text.lower() or "yes" in radio_value.lower())) or \
                                  (relocate == "no" and ("no" in radio_label_text.lower() or "no" in radio_value.lower()))
                
                elif "travel" in radio_identifier:
                    # Willingness to travel
                    travel = resume_data["questions"]["willing_to_travel"].lower()
                    should_select = (travel == "yes" and ("yes" in radio_label_text.lower() or "yes" in radio_value.lower())) or \
                                  (travel == "no" and ("no" in radio_label_text.lower() or "no" in radio_value.lower()))
                
                elif "citizenship" in radio_identifier or "authorized" in radio_identifier:
                    # Work authorization / citizenship question
                    # Usually we want to select "Yes" for "Are you authorized to work in the US?"
                    should_select = "yes" in radio_label_text.lower() or "yes" in radio_value.lower()
                
                elif "work remotely" in radio_identifier or "remote" in radio_identifier:
                    # Remote work preference
                    preferred_setting = resume_data["questions"]["preferred_work_setting"].lower()
                    should_select = ("remote" in preferred_setting and "yes" in radio_label_text.lower()) or \
                                  ("on-site" in preferred_setting and "no" in radio_label_text.lower()) or \
                                  ("hybrid" in preferred_setting and "flexible" in radio_label_text.lower())
                
                # If this is part of a group and none are selected, select first option or "yes" option
                elif not any_selected(driver, radio_name):
                    if "yes" in radio_label_text.lower() or "yes" in radio_value.lower():
                        should_select = True
                    elif not radio_label_text and not radio_value:
                        # If this is the first radio in a group with no clear labels, select it
                        other_radios = driver.find_elements(By.CSS_SELECTOR, f"input[name='{radio_name}']")
                        index = other_radios.index(radio) if radio in other_radios else -1
                        should_select = index == 0
                
                # Click if needed
                if should_select:
                    print(f"Selecting radio button: {radio_identifier} with value: {radio_value}")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", radio)
                    time.sleep(0.5)
                    driver.execute_script("arguments[0].click();", radio)
                    time.sleep(0.5)
                    
            except Exception as e:
                print(f"Error handling radio button in additional scan: {e}")
        
        # Final check for any "Continue" or "Next" buttons that might need to be clicked
        try:
            # Look for navigation buttons at the end of form filling
            nav_buttons = driver.find_elements(By.XPATH, 
                "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'continue') or " +
                "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'next') or " +
                "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'submit') or " +
                "contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'apply')]")
            
            for button in nav_buttons:
                if button.is_displayed() and button.is_enabled():
                    print("Clicking navigation button after form completion:", button.text.strip())
                    driver.execute_script("arguments[0].click();", button)
                    time.sleep(2)
                    break
        except Exception as e:
            print(f"Error handling navigation buttons: {e}")
                
        return True
        
    except Exception as e:
        print(f"Error in form handler: {e}")
        return False

def handle_custom_questions(driver, llm, resume_data, job_title, company):
    """Handle custom questions that require text answers using LLM with improved detection"""
    try:
        print("Scanning for custom questions in application form...")
        questions_answered = 0
        
        # Look for textareas which often contain custom questions
        textareas = driver.find_elements(By.TAG_NAME, "textarea")
        print(f"Found {len(textareas)} textarea elements")
        
        for textarea in textareas:
            try:
                # Skip if already filled or not visible/enabled
                if textarea.get_attribute("value") or not textarea.is_displayed() or not textarea.is_enabled():
                    continue
                
                # Get field identifiers
                textarea_id = textarea.get_attribute("id") or ""
                textarea_name = textarea.get_attribute("name") or ""
                textarea_placeholder = textarea.get_attribute("placeholder") or ""
                
                # Scroll to the textarea to ensure it's in view
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", textarea)
                time.sleep(0.5)
                
                question_text = ""
                
                # Method 1: Check if placeholder contains a question
                if textarea_placeholder and len(textarea_placeholder) > 10:
                    question_text = textarea_placeholder
                    print(f"Found question in placeholder: {question_text}")
                
                # Method 2: Try to find label by for attribute
                if not question_text and textarea_id:
                    try:
                        labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{textarea_id}']")
                        if labels:
                            question_text = labels[0].text.strip()
                            print(f"Found question in label: {question_text}")
                    except:
                        pass
                
                # Method 3: Try to find label in parent hierarchy (up to 3 levels)
                if not question_text:
                    try:
                        # Search for label or text in parent elements
                        parent = textarea
                        for _ in range(3):  # Check up to 3 levels up
                            parent = parent.find_element(By.XPATH, "./..")
                            
                            # Look for labels within this parent
                            labels = parent.find_elements(By.TAG_NAME, "label")
                            if labels:
                                question_text = labels[0].text.strip()
                                print(f"Found question in parent label: {question_text}")
                                break
                                
                            # Look for div with question class or role
                            question_divs = parent.find_elements(By.XPATH, ".//div[contains(@class, 'question') or contains(@class, 'label') or contains(@class, 'field-label')]")
                            if question_divs:
                                question_text = question_divs[0].text.strip()
                                print(f"Found question in div: {question_text}")
                                break
                                
                            # Look for paragraphs, spans or h elements that might contain the question
                            text_elements = parent.find_elements(By.XPATH, ".//p | .//span | .//h1 | .//h2 | .//h3 | .//h4")
                            for elem in text_elements:
                                if elem.text and len(elem.text.strip()) > 10:  # Non-empty text of reasonable length
                                    question_text = elem.text.strip()
                                    print(f"Found question in text element: {question_text}")
                                    break
                            
                            if question_text:
                                break
                    except:
                        pass
                
                # Method 4: Search preceding elements for question text
                if not question_text:
                    try:
                        preceding_elements = driver.find_elements(By.XPATH, f"//textarea[@id='{textarea_id}']/preceding::*[self::p or self::h1 or self::h2 or self::h3 or self::label or self::div][position() <= 3]")
                        for elem in preceding_elements:
                            text = elem.text.strip()
                            if text and len(text) > 10 and "?" in text:  # Looks like a question
                                question_text = text
                                print(f"Found question in preceding element: {question_text}")
                                break
                    except:
                        pass
                
                # Method 5: Look for any text with a question mark nearby
                if not question_text:
                    try:
                        # Find the closest element with a question mark
                        question_elements = driver.find_elements(By.XPATH, "//p[contains(text(), '?')] | //div[contains(text(), '?')] | //span[contains(text(), '?')] | //label[contains(text(), '?')]")
                        
                        closest_question = None
                        min_distance = float('inf')
                        
                        for question_elem in question_elements:
                            # Calculate proximity to textarea
                            textarea_rect = textarea.rect
                            question_rect = question_elem.rect
                            
                            # Simple distance calculation (can be improved)
                            distance = abs((textarea_rect['y'] + textarea_rect['height']/2) - 
                                          (question_rect['y'] + question_rect['height']/2))
                            
                            if distance < min_distance and distance < 200:  # Within reasonable proximity
                                min_distance = distance
                                closest_question = question_elem
                        
                        if closest_question:
                            question_text = closest_question.text.strip()
                            print(f"Found nearby question text: {question_text}")
                    except:
                        pass
                
                # If we found a question, generate an answer with the LLM
                if question_text:
                    # Clean up question text
                    question_text = question_text.replace('\n', ' ').strip()
                    print(f"Processing question: {question_text}")
                    
                    # Generate answer based on resume data and job details
                    answer = generate_answer_with_llm(llm, question_text, resume_data, job_title, company)
                    
                    if answer:
                        # Try to focus and clear the textarea
                        try:
                            driver.execute_script("arguments[0].focus();", textarea)
                            textarea.clear()
                            time.sleep(0.5)
                        except:
                            # If direct focus fails, try click first
                            driver.execute_script("arguments[0].click();", textarea)
                            time.sleep(0.5)
                            textarea.clear()
                        
                        print(f"Entering answer: {answer[:50]}...")
                        
                        # Try multiple methods to enter text
                        text_entry_success = False
                        
                        # Method 1: JavaScript to set value directly
                        try:
                            driver.execute_script("arguments[0].value = arguments[1];", textarea, answer)
                            # Trigger input event to make sure LinkedIn registers the change
                            driver.execute_script("""
                                var event = new Event('input', {
                                    bubbles: true,
                                    cancelable: true
                                });
                                arguments[0].dispatchEvent(event);
                            """, textarea)
                            time.sleep(1)
                            
                            # Verify text was entered
                            if textarea.get_attribute("value") == answer:
                                text_entry_success = True
                                print("Text entered successfully using JavaScript")
                        except:
                            pass
                        
                        # Method 2: Send keys if JavaScript failed
                        if not text_entry_success:
                            try:
                                # Try to enter text in chunks to avoid issues with long text
                                chunk_size = 50
                                for i in range(0, len(answer), chunk_size):
                                    chunk = answer[i:i+chunk_size]
                                    textarea.send_keys(chunk)
                                    time.sleep(0.3)
                                
                                time.sleep(1)
                                # Verify text was entered
                                entered_text = textarea.get_attribute("value")
                                if entered_text and len(entered_text) > 10:  # At least some text entered
                                    text_entry_success = True
                                    print("Text entered successfully using send_keys in chunks")
                            except:
                                pass
                        
                        # Method 3: Character by character as last resort
                        if not text_entry_success:
                            try:
                                # Try character by character with very small random delays
                                for char in answer:
                                    textarea.send_keys(char)
                                    time.sleep(random.uniform(0.01, 0.03))
                                
                                print("Text entered character by character")
                                text_entry_success = True
                            except Exception as e:
                                print(f"All text entry methods failed: {e}")
                        
                        if text_entry_success:
                            # Press Tab to move to next field
                            try:
                                textarea.send_keys(Keys.TAB)
                                questions_answered += 1
                            except:
                                pass
                else:
                    print(f"Found textarea but couldn't identify associated question. ID: {textarea_id}")
            
            except Exception as e:
                print(f"Error handling textarea: {e}")
        
        print(f"Answered {questions_answered} custom questions")
        
        # Also look for input text fields that might contain questions
        try:
            text_inputs = driver.find_elements(By.CSS_SELECTOR, "input[type='text']:not([value]), input:not([type]):not([value])")
            print(f"Found {len(text_inputs)} text input fields to check")
            
            for text_input in text_inputs:
                try:
                    # Skip if already filled or not visible
                    if text_input.get_attribute("value") or not text_input.is_displayed() or not text_input.is_enabled():
                        continue
                    
                    input_id = text_input.get_attribute("id") or ""
                    input_name = text_input.get_attribute("name") or ""
                    input_placeholder = text_input.get_attribute("placeholder") or ""
                    
                    # Skip common fields we already handle in form_fields function
                    if any(keyword in (input_id + input_name + input_placeholder).lower() for keyword in 
                           ["name", "email", "phone", "address", "website", "linkedin", "github"]):
                        continue
                    
                    # Use similar question detection logic as for textareas
                    question_text = ""
                    
                    # First check placeholder
                    if input_placeholder and len(input_placeholder) > 10:
                        question_text = input_placeholder
                    
                    # Then try to find related label
                    if not question_text and input_id:
                        try:
                            labels = driver.find_elements(By.CSS_SELECTOR, f"label[for='{input_id}']")
                            if labels:
                                question_text = labels[0].text.strip()
                        except:
                            pass
                    
                    # Search parent elements
                    if not question_text:
                        try:
                            parent = text_input
                            for _ in range(2):
                                parent = parent.find_element(By.XPATH, "./..")
                                labels = parent.find_elements(By.TAG_NAME, "label")
                                if labels:
                                    question_text = labels[0].text.strip()
                                    break
                        except:
                            pass
                    
                    if question_text and ("?" in question_text or len(question_text) > 15):
                        print(f"Found question for text input: {question_text}")
                        answer = generate_answer_with_llm(llm, question_text, resume_data, job_title, company)
                        
                        # For text inputs, we want shorter answers
                        if answer and len(answer) > 100:
                            answer = answer.split(".")[0] + "."  # Just the first sentence
                        
                        if answer:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", text_input)
                            time.sleep(0.5)
                            try:
                                text_input.clear()
                                text_input.send_keys(answer)
                                time.sleep(0.5)
                                questions_answered += 1
                            except:
                                try:
                                    driver.execute_script("arguments[0].value = arguments[1];", text_input, answer)
                                    questions_answered += 1
                                except:
                                    print("Failed to enter text in input field")
                
                except Exception as e:
                    print(f"Error handling text input: {e}")
        except Exception as e:
            print(f"Error processing text inputs: {e}")
                
        return questions_answered > 0
        
    except Exception as e:
        print(f"Error in custom question handler: {e}")
        return False
    
def handle_select_dropdown(driver, select_element, field_identifier, resume_data):
    """
    Handle select dropdown fields in application forms
    
    Args:
        driver: Selenium WebDriver instance
        select_element: The select element to interact with
        field_identifier: Combined identifier string (id, name, aria-label, label text)
        resume_data: Dictionary containing resume information
    """
    try:
        from selenium.webdriver.support.ui import Select
        select = Select(select_element)
        
        # Get all available options
        options = [option.text.strip() for option in select.options]
        print(f"Dropdown options for {field_identifier}: {options}")
        
        # Skip if no options or already has a selection (first item might be a placeholder)
        if not options or (len(options) > 1 and select_element.get_attribute("value") and 
                          select_element.get_attribute("value") != options[0]):
            print(f"Dropdown already has selection or no options")
            return
        
        # Default to select is None (will select based on content)
        option_to_select = None
        
        # Decision logic based on field identifier and resume data
        if "visa" in field_identifier or "sponsor" in field_identifier:
            # Visa sponsorship questions
            need_visa = resume_data["questions"]["visa_sponsorship_required"].lower()
            for option in options:
                if (need_visa == "yes" and "yes" in option.lower()) or \
                   (need_visa == "no" and "no" in option.lower()):
                    option_to_select = option
                    break
        
        elif "relocate" in field_identifier:
            # Willingness to relocate
            relocate = resume_data["questions"]["willing_to_relocate"].lower()
            for option in options:
                if (relocate == "yes" and "yes" in option.lower()) or \
                   (relocate == "no" and "no" in option.lower()):
                    option_to_select = option
                    break
        
        elif "travel" in field_identifier:
            # Willingness to travel
            travel = resume_data["questions"]["willing_to_travel"].lower()
            for option in options:
                if (travel == "yes" and "yes" in option.lower()) or \
                   (travel == "no" and "no" in option.lower()):
                    option_to_select = option
                    break
        
        elif "work remotely" in field_identifier or "remote" in field_identifier:
            # Remote work preference
            preferred_setting = resume_data["questions"]["preferred_work_setting"].lower()
            for option in options:
                option_lower = option.lower()
                if ("remote" in preferred_setting and "remote" in option_lower) or \
                   ("on-site" in preferred_setting and ("onsite" in option_lower or "on-site" in option_lower)) or \
                   ("hybrid" in preferred_setting and "hybrid" in option_lower):
                    option_to_select = option
                    break
        
        # For yes/no questions, default to "Yes" if no specific matching found
        if not option_to_select:
            # Look for yes/no options
            for option in options:
                if option.lower() == "yes":
                    option_to_select = option
                    break
            
            # If no "Yes" option or if it's not a yes/no question, select first non-placeholder option
            if not option_to_select and len(options) > 1:
                # Skip placeholder options like "Select an option"
                placeholders = ["select", "choose", "please"]
                for option in options:
                    if not any(p in option.lower() for p in placeholders):
                        option_to_select = option
                        break
        
        # Make the selection if an option was determined
        if option_to_select:
            print(f"Selecting dropdown option: {option_to_select}")
            select.select_by_visible_text(option_to_select)
            time.sleep(1)
            
    except Exception as e:
        print(f"Error handling dropdown: {e}")

def find_best_option_match(options, target_value):
    """
    Find the option that best matches the target value based on text similarity.
    
    Args:
        options: List of option strings to choose from
        target_value: The value we're trying to match
        
    Returns:
        Best matching option or None
    """
    target_value = target_value.lower()
    best_match = None
    highest_similarity = 0
    
    for option in options:
        option_lower = option.lower()
        
        # Exact match is best
        if option_lower == target_value:
            return option
            
        # Check if target_value is contained in option
        if target_value in option_lower or option_lower in target_value:
            similarity = len(set(target_value.split()) & set(option_lower.split())) / max(len(target_value.split()), len(option_lower.split()))
            if similarity > highest_similarity:
                highest_similarity = similarity
                best_match = option
                
    # If we found a decent match (at least 0.3 similarity)
    if highest_similarity >= 0.3:
        return best_match
        
    # Try matching individual words
    target_words = set(target_value.split())
    for option in options:
        option_words = set(option.lower().split())
        common_words = target_words & option_words
        if common_words and len(common_words) / max(len(target_words), len(option_words)) > highest_similarity:
            highest_similarity = len(common_words) / max(len(target_words), len(option_words))
            best_match = option
            
    # Return best match if above threshold
    if highest_similarity >= 0.2:
        return best_match
        
    return None

def generate_answer_with_llm(llm, question, resume_data, job_title, company):
    """Generate an appropriate answer to a custom question using the LLM with improved error handling"""
    try:
        print(f"Generating answer for question: {question}")
        
        # Check if question is empty or too short
        if not question or len(question) < 5:
            print("Question text too short, skipping LLM generation")
            return ""
            
        # Extract skills and experience from resume data for use in the prompt
        skills = ", ".join(resume_data["skills"][:5]) if "skills" in resume_data else ""
        experience_summary = ""
        if "work_experience" in resume_data and resume_data["work_experience"]:
            latest_job = resume_data["work_experience"][0]
            experience_summary = f"{latest_job.get('title', '')} at {latest_job.get('company', '')} - {latest_job.get('description', '')}"
        
        # Build a more focused prompt template
        prompt_template = PromptTemplate(
            input_variables=["question", "job_title", "company", "skills", "experience", "profile"],
            template="""
            You are helping a job applicant answer a question on a LinkedIn job application form.
            
            JOB: {job_title} at {company}
            
            QUESTION: {question}
            
            APPLICANT INFO:
            - Skills: {skills}
            - Recent Experience: {experience}
            - Additional Profile Info: {profile}
            
            Write a concise, professional response that directly answers the question. 
            Make it specific to the job position and highlight relevant skills or experience.
            Keep it under 100 words, using first-person perspective.Just write the very short answer directly, and if the answer is numbers then answer in digits.
            Don't start with phrases like "As a [job title]" or "Based on my experience" - just answer directly.
            Only output the answer text with no quotation marks or additional commentary.
            """
        )
        
        # Extract a compact profile summary for the prompt
        profile_summary = f"Education: {resume_data['education'][0]['degree'] if 'education' in resume_data and resume_data['education'] else 'Not specified'}, "
        profile_summary += f"Years of experience: {resume_data['questions'].get('years_of_experience', 'Not specified')}, "
        profile_summary += f"Willing to relocate: {resume_data['questions'].get('willing_to_relocate', 'Not specified')}"
        
        # Format the prompt with our data
        formatted_prompt = prompt_template.format(
            question=question,
            job_title=job_title,
            company=company,
            skills=skills,
            experience=experience_summary,
            profile=profile_summary
        )
        print(formatted_prompt)
        
        # Generate the answer with timeout handling
        try:
            response = llm.invoke(formatted_prompt)
            answer = response.strip()
            
            # Handle common edge cases
            if "As an AI assistant" in answer or "As an AI language model" in answer:
                answer = answer.split("\n", 1)[1] if "\n" in answer else ""
            
            # Remove any quotation marks around the answer
            answer = answer.strip('"\'')
            
            print(f"Generated answer: {answer[:100]}...")
            return answer
        except Exception as e:
            print(f"LLM timeout or error: {e}")
            # Fall through to backup answers
        
    except Exception as e:
        print(f"Error generating answer with LLM: {e}")
    
    # Enhanced fallback answers for common questions - more tailored to the job
    # These will be used if the LLM fails
    
    # Extract key resume info for fallbacks
    skills_list = resume_data.get('skills', ['problem-solving', 'communication', 'teamwork'])
    top_skills = ', '.join(skills_list[:3])
    experience_years = resume_data.get('questions', {}).get('years_of_experience', '3+')
    
    # Pattern match the question for better fallbacks
    question_lower = question.lower()
    
    if any(phrase in question_lower for phrase in ["tell us about yourself", "introduce yourself", "background"]):
        return f"I'm a dedicated professional with {experience_years} years of experience and expertise in {top_skills}. Throughout my career, I've focused on delivering excellent results while continuously expanding my skill set. I'm particularly interested in this {job_title} role at {company} as it aligns with my professional goals and strengths."
    
    elif any(phrase in question_lower for phrase in ["why do you want to work", "why are you interested", "why join"]):
        return f"I'm drawn to {company} because of its reputation for innovation and impact in the industry. The {job_title} position particularly excites me as it leverages my skills in {top_skills}. I believe my background would allow me to contribute effectively while growing professionally in this role."
    
    elif any(phrase in question_lower for phrase in ["salary", "compensation", "pay", "expected"]):
        return resume_data.get('questions', {}).get('salary_expectation', "My salary expectations are flexible and based on the total compensation package, but I'm looking in the range typical for this role considering my experience level.")
    
    elif any(phrase in question_lower for phrase in ["start", "when can you start", "availability"]):
        return resume_data.get('questions', {}).get('preferred_start_date', "I can be available to start within two weeks after receiving an offer, though I'm flexible and can adjust based on your needs.")
    
    elif any(phrase in question_lower for phrase in ["strength", "greatest strength"]):
        return f"My greatest strength is my ability to {skills_list[0] if skills_list else 'quickly adapt to new challenges'}. This has enabled me to consistently deliver results in previous roles, particularly when working on complex projects requiring {skills_list[1] if len(skills_list) > 1 else 'attention to detail'}."
    
    elif any(phrase in question_lower for phrase in ["weakness", "area for improvement"]):
        return "I tend to be very detail-oriented, which sometimes means I spend extra time ensuring everything is perfect. I've learned to balance this by setting clear timelines and checkpoints to ensure I maintain both quality and efficiency."
    
    elif any(phrase in question_lower for phrase in ["challenge", "difficult situation", "overcome"]):
        return f"In a previous role, I faced a significant challenge when working on a time-sensitive project with changing requirements. By maintaining clear communication with stakeholders and leveraging my skills in {top_skills}, I was able to adapt quickly and deliver successfully despite the obstacles."
    
    elif any(phrase in question_lower for phrase in ["remote", "work from home", "hybrid"]):
        preferred_setting = resume_data.get('questions', {}).get('preferred_work_setting', 'flexible')
        return f"I'm comfortable working in a {preferred_setting} environment. I have experience collaborating effectively both remotely and on-site, and value maintaining strong communication and productivity regardless of the work setting."
    
    elif any(phrase in question_lower for phrase in ["relocate", "relocation", "move"]):
        willing = resume_data.get('questions', {}).get('willing_to_relocate', 'Yes')
        return f"{'I am willing to relocate for the right opportunity.' if willing.lower() == 'yes' else 'I prefer positions in my current location, but am open to discussing options for exceptional opportunities.'}"
    
    elif any(phrase in question_lower for phrase in ["visa", "sponsorship", "work authorization"]):
        need_visa = resume_data.get('questions', {}).get('visa_sponsorship_required', 'No')
        return f"{'I am authorized to work in the United States without sponsorship.' if need_visa.lower() == 'no' else 'I would require visa sponsorship to work in the United States.'}"
    
    # Generic fallback for other questions
    return f"Based on my {experience_years} years of experience with {top_skills}, I believe I would be able to make strong contributions to this {job_title} role. I'm excited about the opportunity to bring my skills to {company} and help achieve your team's goals."

def main():
    """Main function to run the automation"""
    print("Starting LinkedIn Job Application Bot")
    print("-------------------------------------")
    
    # Set up the WebDriver
    driver = setup_driver()
    
    # Set up LLM
    llm = setup_llm()
    
    try:
        # Try to login with cookies first
        logged_in = False
        if os.path.exists(COOKIES_FILE):
            logged_in = login_with_cookies(driver)
        
        # If cookie login failed, try credentials
        if not logged_in:
            logged_in = login_with_credentials(driver)
            
        if not logged_in:
            print("Failed to login to LinkedIn. Exiting.")
            driver.quit()
            return
        
        # Navigate to jobs page and search
        if not navigate_to_jobs_and_search(driver, JOB_TITLE, JOB_LOCATION):
            print("Failed to search for jobs. Exiting.")
            driver.quit()
            return
        
        # Apply Easy Apply filter
        if not click_easy_apply_filter(driver):
            print("Warning: Could not apply Easy Apply filter. Continuing anyway.")
        
        # Process job listings and apply
        process_job_listings(driver, llm, MAX_APPLICATIONS)
        
        print("Job application process completed.")
        
    except Exception as e:
        print(f"Error in main process: {e}")
    finally:
        # Add a delay before closing so you can see the final state
        time.sleep(5)
        driver.quit()

if __name__ == "__main__":
    main()

