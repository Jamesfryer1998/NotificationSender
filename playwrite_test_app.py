from playwright.sync_api import sync_playwright
import time
import random
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def human_delay(min_seconds=1, max_seconds=3):
    """Add random delay to mimic human behavior"""
    delay = random.uniform(min_seconds * 0.5, max_seconds * 0.5)  # Reduced by 50%
    time.sleep(delay)

def send_finish_email(num_messages_sent, start_time, end_time):
    """Send completion email with stats"""
    try:
        # Get email settings from environment
        mail_server = os.getenv('MAIL_SERVER')
        mail_port = int(os.getenv('MAIL_PORT', 587))
        mail_username = os.getenv('MAIL_USERNAME')
        mail_password = os.getenv('MAIL_PASSWORD')
        mail_use_tls = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
        
        if not all([mail_server, mail_username, mail_password]):
            print("Email settings not configured properly in .env file")
            return
        
        # Calculate duration
        duration = end_time - start_time
        total_seconds = int(duration.total_seconds())
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        duration_str = f"{hours}h {minutes}m {seconds}s"
        
        # Create email
        msg = MIMEMultipart()
        msg['From'] = mail_username
        msg['To'] = mail_username  # Send to self
        msg['Subject'] = f"{num_messages_sent} Message sending Complete"
        
        body = f"""
Instagram Messaging Campaign Complete

Summary:
- Messages sent: {num_messages_sent}
- Total duration: {duration_str}
- Start time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}
- End time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}

Campaign completed successfully.
        """
        
        msg.attach(MIMEText(body, 'plain'))
        
        # Send email
        server = smtplib.SMTP(mail_server, mail_port)
        if mail_use_tls:
            server.starttls()
        server.login(mail_username, mail_password)
        server.send_message(msg)
        server.quit()
        
        print("Completion email sent successfully!")
        
    except Exception as e:
        print(f"Error sending email: {e}")

# The message to send
MESSAGE = """Hey! 
We just launched our platform that connects brands and creators for collaborations - thought you might be interested. It's completely free to join!

Takes 2 minutes to sign up: https://www.collablab.net

Let me know what you think!"""

with sync_playwright() as p:
    # Record start time
    start_time = datetime.now()
    messages_sent_count = 0
    
    # Launch browser (set headless=False to see what's happening)
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    
    # Navigate to Instagram
    page.goto("https://www.instagram.com/")
    
    # Wait a moment for the page to load
    page.wait_for_load_state("networkidle")
    human_delay(2, 4)  # Random delay after page load
    
    # Step 1: Handle cookies popup
    try:
        # Look for cookie denial/decline buttons
        cookie_buttons = [
            'button:has-text("Decline optional cookies")',
            'button:has-text("Decline")',
            'button:has-text("Only allow essential cookies")',
            'button:has-text("Reject all")',
            '[data-cookiebanner="accept_only_essential_button"]',
            'button[data-testid="cookie-policy-manage-dialog-decline-button"]'
        ]
        
        cookie_handled = False
        for selector in cookie_buttons:
            try:
                cookie_button = page.wait_for_selector(selector, timeout=3000)
                human_delay(0.1, 0.5)  # Delay before clicking
                cookie_button.click()
                print(f"Declined cookies successfully using: {selector}")
                cookie_handled = True
                break
            except:
                continue
        
        if not cookie_handled:
            print("No cookie popup found or couldn't decline")
            
    except Exception as e:
        print(f"Error handling cookies: {e}")
    
    human_delay(0.5, 2)  # Wait after cookie handling
    
    # Step 2: Login
    try:
        # Get credentials from environment variables
        username = os.getenv('INSTA_USERNAME')
        password = os.getenv('INSTA_PASSWORD')
        
        if not username or not password:
            raise ValueError("Please set INSTA_USERNAME and INSTA_PASSWORD in your .env file")
        
        # Fill username with human-like typing
        username_field = page.wait_for_selector('input[name="username"]', timeout=10000)
        human_delay(0.5, 1.2)  # Delay before typing
        
        # Type username character by character with random delays
        for char in username:
            username_field.type(char)
            time.sleep(random.uniform(0.05, 0.15))  # Random typing speed
        
        print("Filled username")
        human_delay(0.8, 1.5)  # Delay between username and password
        
        # Fill password with human-like typing
        password_field = page.wait_for_selector('input[name="password"]', timeout=5000)
        human_delay(0.3, 0.8)  # Brief delay before typing password
        
        # Type password character by character
        for char in password:
            password_field.type(char)
            time.sleep(random.uniform(0.05, 0.15))  # Random typing speed
        
        print("Filled password")
        human_delay(1, 2.5)  # Delay before clicking login
        
        # Click login button
        login_button = page.wait_for_selector('button[type="submit"]', timeout=5000)
        login_button.click()
        print("Clicked login button")
        
        # Wait for login to complete (wait for page to redirect or load)
        try:
            # Wait for either the home feed or a "Save Login Info" dialog
            page.wait_for_selector('[data-testid="login-page"]', state='detached', timeout=15000)
            print("Login successful!")
        except:
            print("Login may have completed or there might be additional prompts")
        
        human_delay(1, 2)  # Reduced delay after login
        
        # Handle "Save Login Info" popup if it appears
        try:
            not_now_button = page.wait_for_selector('button:has-text("Not Now")', timeout=3000)
            human_delay(0.3, 0.8)  # Faster popup handling
            not_now_button.click()
            print("Dismissed save login info popup")
        except:
            pass
        
        human_delay(0.5, 1)  # Reduced delay between popups
        
        # Handle "Turn on Notifications" popup if it appears
        try:
            not_now_button = page.wait_for_selector('button:has-text("Not Now")', timeout=3000)
            human_delay(0.3, 0.8)  # Faster popup handling
            not_now_button.click()
            print("Dismissed notifications popup")
        except:
            pass
            
    except Exception as e:
        print(f"Error during login: {e}")
        page.screenshot(path="login_error.png")
    
    human_delay(0.5, 1.5)  # Much faster wait before going to profile
    
    # Step 3: Go to profile
    try:
        # Look for profile button/link
        profile_selectors = [
            '[aria-label="Profile"]',
            'a[href*="/'+username+'/"]',
            'svg[aria-label="Profile"]',
            '[data-testid="mobile-nav-profile"]'
        ]
        
        profile_clicked = False
        for selector in profile_selectors:
            try:
                profile_button = page.wait_for_selector(selector, timeout=5000)
                human_delay(0.3, 0.8)  # Faster profile click
                profile_button.click()
                print("Clicked profile button!")
                profile_clicked = True
                break
            except:
                continue
        
        if not profile_clicked:
            print("Could not find profile button")
            page.screenshot(path="profile_error.png")
            raise Exception("Profile button not found")
            
    except Exception as e:
        print(f"Error going to profile: {e}")
    
    human_delay(1, 2)  # Faster wait for profile page to load
    
    # Main loop - repeat the process
    people_processed = 0
    max_people = 50  # Set a limit to prevent infinite loop
    
    while people_processed < max_people:
        print(f"\n--- Processing person #{people_processed + 1} ---")
        
        # Step 4: Click on "Following"
        try:
            # Look for following button/link
            following_selectors = [
                'a[href*="/following/"]',
                'button:has-text("following")',
                'a:has-text("following")',
                '[data-testid="following-link"]'
            ]
            
            following_clicked = False
            for selector in following_selectors:
                try:
                    following_button = page.wait_for_selector(selector, timeout=8000)
                    human_delay(0.8, 1.5)
                    following_button.click()
                    print("Clicked following button!")
                    following_clicked = True
                    break
                except:
                    continue
            
            if not following_clicked:
                print("Could not find following button")
                page.screenshot(path="following_error.png")
                break
                
        except Exception as e:
            print(f"Error clicking following: {e}")
            break
        
        human_delay(1, 2)  # Reduced wait for following list to load (50% reduction)
        
        # Step 5: Click on the first person in the following list
        try:
            # Wait for the following dialog/modal to appear and load
            page.wait_for_selector('[role="dialog"]', timeout=3000)  # Reduced from 10000
            
            # Wait for the list to be populated with users (ensure content is loaded)
            page.wait_for_selector('[role="dialog"] a[href*="/"]', timeout=2000)  # Reduced from 8000
            human_delay(0.2, 0.5)  # Minimal wait for list to stabilize
            
            # Find the first profile link in the following list
            first_profile_selectors = [
                '[role="dialog"] a[href*="/"][href$="/"]',
                '[role="dialog"] a[tabindex="0"]:first-child',
                '[role="dialog"] div[role="button"]:first-child a',
                '[role="dialog"] a:first-of-type[href*="/"]'
            ]
            
            first_person_clicked = False
            for selector in first_profile_selectors:
                try:
                    first_person = page.wait_for_selector(selector, timeout=1000)  # Reduced from 3000
                    
                    human_delay(0.2, 0.4)  # Much faster click timing
                    first_person.click()
                    print("Clicked on first person")
                    first_person_clicked = True
                    break
                except:
                    continue
            
            if not first_person_clicked:
                print("Could not find first person in following list")
                page.screenshot(path="first_person_error.png")
                # Close dialog and continue to next iteration
                try:
                    close_button = page.wait_for_selector('[role="dialog"] button[aria-label="Close"]', timeout=3000)
                    close_button.click()
                except:
                    page.keyboard.press('Escape')
                continue
            
        except Exception as e:
            print(f"Error clicking first person: {e}")
            page.screenshot(path="profile_selection_error.png")
            break
        
        human_delay(0.5, 1)  # Much faster wait for profile to load
        
        # Get the username from the profile page (left of Following button)
        target_username = None
        try:
            username_selectors = [
                'header h2',
                'header h1', 
                'section h1',
                'section h2',
                'div:has(button:has-text("Following")) h1',
                'div:has(button:has-text("Following")) h2'
            ]
            
            for selector in username_selectors:
                try:
                    username_element = page.wait_for_selector(selector, timeout=1500)  # Reduced timeout
                    target_username = username_element.inner_text().strip()
                    if target_username and not target_username.isspace():
                        print(f"Found username: {target_username}")
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"Error getting username: {e}")
        
        # Step 6: Try to send message (if message button is available)
        message_sent = False
        message_button_found = False
        try:
            # Look for message button - specifically in the profile header area, next to Following button
            message_selectors = [
                'header button:has-text("Message")',
                'section button:has-text("Message")',
                'div:has(button:has-text("Following")) + div button:has-text("Message")',
                'button:has-text("Message"):near(button:has-text("Following"))',
                'div[role="button"]:has-text("Message"):near(button:has-text("Following"))',
                'button[type="button"]:has-text("Message")',
                'header div[role="button"]:has-text("Message")'
            ]
            
            for selector in message_selectors:
                try:
                    message_button = page.wait_for_selector(selector, timeout=2000)  # Reduced timeout
                    message_button_found = True
                    human_delay(0.3, 0.6)  # Much faster
                    message_button.click()
                    print("Clicked message button!")
                    
                    # Wait for message input to appear
                    human_delay(1, 1.5)  # Reduced wait time
                    
                    # Handle notifications popup if it appears
                    try:
                        not_now_button = page.wait_for_selector('button:has-text("Not now")', timeout=2000)  # Reduced timeout
                        human_delay(0.2, 0.4)  # Much faster
                        not_now_button.click()
                        print("Dismissed notifications popup")
                    except:
                        print("No notifications popup found")
                    
                    human_delay(0.5, 1)  # Reduced wait after handling popup
                    
                    # Find message input field and type message
                    message_input_selectors = [
                        'textarea[placeholder*="message"]',
                        'div[contenteditable="true"]',
                        'textarea[aria-label*="message"]',
                        'input[placeholder*="message"]'
                    ]
                    
                    for input_selector in message_input_selectors:
                        try:
                            message_input = page.wait_for_selector(input_selector, timeout=3000)  # Reduced timeout
                            human_delay(0.3, 0.6)  # Much faster
                            
                            # Paste the entire message at once
                            message_input.fill(MESSAGE)
                            
                            print("Pasted message!")
                            human_delay(0.5, 1)  # Reduced wait
                            
                            # Send message by pressing Enter
                            message_input.press('Enter')
                            print("Sent message by pressing Enter!")
                            message_sent = True
                            messages_sent_count += 1  # Increment counter
                            break
                        except:
                            continue
                    break
                except:
                    continue
            
            if not message_button_found:
                print("No message button found - user doesn't allow messages. Skipping to unfollow.")
            elif not message_sent:
                print("Message button found but couldn't send message")
                
        except Exception as e:
            print(f"Error with messaging: {e}")
        
        # Step 7: Go to the user's profile and unfollow (whether message was sent or not)
        if message_sent:
            human_delay(1, 2)  # Reduced wait after sending message
        
        try:
            # Navigate directly to the user's profile page
            if target_username:
                profile_url = f"https://www.instagram.com/{target_username}/"
                page.goto(profile_url)
                human_delay(0.5, 1)  # Faster navigation wait
                print(f"Navigated to {target_username}'s profile")
                
                # Click the Following button to bring up options
                following_button_selectors = [
                    'button:has-text("Following")',
                    'div[role="button"]:has-text("Following")',
                    'header button:has-text("Following")',
                    '[aria-label="Following"]'
                ]
                
                following_clicked = False
                for selector in following_button_selectors:
                    try:
                        following_btn = page.wait_for_selector(selector, timeout=3000)  # Reduced timeout
                        human_delay(0.2, 0.4)  # Much faster
                        following_btn.click()
                        print("Clicked Following button!")
                        following_clicked = True
                        break
                    except:
                        continue
                
                if following_clicked:
                    human_delay(0.3, 0.6)  # Faster wait for options to appear
                    
                    # Click Unfollow option
                    unfollow_selectors = [
                        'button:has-text("Unfollow")',
                        'div[role="button"]:has-text("Unfollow")',
                        '[data-testid="unfollow-button"]'
                    ]
                    
                    for selector in unfollow_selectors:
                        try:
                            unfollow_btn = page.wait_for_selector(selector, timeout=2000)  # Reduced timeout
                            human_delay(0.2, 0.4)  # Much faster
                            unfollow_btn.click()
                            print("Clicked Unfollow!")
                            break
                        except:
                            continue
                else:
                    print("Could not find Following button")
            else:
                print("No target username available for unfollowing")
                
        except Exception as e:
            print(f"Error during unfollow process: {e}")
        
        # Step 8: Go back to your profile
        try:
            # Go back to your profile
            page.goto(f"https://www.instagram.com/{username}/")
            human_delay(0.5, 1)  # Faster return to profile
            print("Returned to profile")
        except Exception as e:
            print(f"Error returning to profile: {e}")
            break
        
        people_processed += 1
        print(f"Completed processing person #{people_processed}")
        
        # Add a delay between people to be more human-like
        if people_processed < max_people:
            human_delay(1, 2)
    
    print(f"\nProcessed {people_processed} people total")
    print(f"Messages sent: {messages_sent_count}")
    
    # Record end time and send completion email
    end_time = datetime.now()
    send_finish_email(messages_sent_count, start_time, end_time)
    
    # Close browser
    browser.close()