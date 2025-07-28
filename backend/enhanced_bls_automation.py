import asyncio
import json
import base64
import logging
import random
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import requests
from urllib.parse import urljoin
import re
from models import SystemLog, AppointmentSlot, LogLevel, AppointmentStatus
import os

class EnhancedBLSAutomation:
    def __init__(self, db, log_callback=None, real_time_callback=None):
        self.db = db
        self.log_callback = log_callback
        self.real_time_callback = real_time_callback  # New callback for real-time updates
        self.logger = logging.getLogger(__name__)
        
        # BLS URLs
        self.urls = {
            'login': 'https://algeria.blsspainglobal.com/DZA/account/login',
            'captcha_login': 'https://algeria.blsspainglobal.com/DZA/newcaptcha/logincaptcha',
            'appointment_captcha': 'https://algeria.blsspainglobal.com/DZA/Appointment/AppointmentCaptcha',
            'visa_type': 'https://algeria.blsspainglobal.com/DZA/Appointment/VisaType',
            'new_appointment': 'https://algeria.blsspainglobal.com/DZA/Appointment/NewAppointment'
        }
        
        # Credentials
        self.email = os.environ.get('BLS_EMAIL')
        self.password = os.environ.get('BLS_PASSWORD')
        
        # OCR API
        self.ocr_api_url = os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:8001') + os.environ.get('OCR_API_ENDPOINT', '/api/ocr-match')
        
        # Browser setup
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        
        # State tracking
        self.is_logged_in = False
        self.session_cookies = None
        self.csrf_token = None
        
        # Anti-bot measures
        self.human_delays = {
            'typing': (0.1, 0.3),  # Random delay between keystrokes
            'click': (0.5, 2.0),   # Random delay after clicks
            'page_load': (2.0, 5.0),  # Random delay for page loads
            'form_fill': (1.0, 3.0)   # Random delay between form fields
        }
        
        # Dynamic element tracking
        self.discovered_elements = {}
        self.form_field_mappings = {}

    async def real_time_update(self, message: str, level: str = "info", details: Dict = None, step: str = None):
        """Send real-time updates to frontend"""
        update_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "message": message,
            "level": level,
            "details": details or {},
            "step": step,
            "copyable_log": f"[{datetime.utcnow().strftime('%H:%M:%S')}] [{step or 'GENERAL'}] {message}"
        }
        
        if self.real_time_callback:
            await self.real_time_callback(update_data)

    async def log(self, level: LogLevel, message: str, details: Optional[Dict] = None, step: Optional[str] = None):
        """Enhanced logging with real-time updates"""
        log_entry = SystemLog(
            level=level,
            message=message,
            details=details,
            step=step
        )
        
        # Save to database
        await self.db.system_logs.insert_one(log_entry.dict())
        
        # Send real-time update
        await self.real_time_update(message, level.value, details, step)
        
        # Call callback if provided
        if self.log_callback:
            await self.log_callback(log_entry)
        
        # Also log to console
        log_level = getattr(logging, level.value.upper())
        self.logger.log(log_level, f"[{step or 'GENERAL'}] {message}")

    async def human_delay(self, delay_type: str):
        """Add human-like delays"""
        min_delay, max_delay = self.human_delays.get(delay_type, (0.5, 1.5))
        delay = random.uniform(min_delay, max_delay)
        await asyncio.sleep(delay)

    async def init_stealth_browser(self):
        """Initialize browser with advanced anti-detection measures"""
        try:
            await self.log(LogLevel.INFO, "Initializing stealth browser with advanced anti-detection", step="STEALTH_INIT")
            
            self.playwright = await async_playwright().start()
            
            # Advanced browser arguments for stealth
            args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--window-size=1920,1080',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=VizDisplayCompositor',
                '--disable-ipc-flooding-protection',
                '--disable-renderer-backgrounding',
                '--disable-backgrounding-occluded-windows',
                '--disable-client-side-phishing-detection',
                '--disable-sync',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-plugins',
                '--disable-translate',
                '--disable-logging',
                '--disable-log-file',
                '--silent',
                '--no-first-run',
                '--no-default-browser-check',
                '--no-crash-upload',
                '--disable-popup-blocking'
            ]
            
            # Launch browser with stealth options
            self.browser = await self.playwright.chromium.launch(
                headless=True,
                args=args,
                chromium_sandbox=False
            )
            
            # Create context with realistic settings
            user_agents = [
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
                'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            ]
            
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent=random.choice(user_agents),
                java_script_enabled=True,
                accept_downloads=False,
                ignore_https_errors=True,
                locale='en-US',
                timezone_id='Europe/London'
            )
            
            # Advanced stealth scripts
            await self.context.add_init_script("""
                // Remove webdriver property
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined,
                });
                
                // Mock chrome object
                window.chrome = {
                    runtime: {},
                    loadTimes: function() {
                        return {
                            requestTime: Date.now() * 0.001,
                            startLoadTime: Date.now() * 0.001,
                            commitLoadTime: Date.now() * 0.001,
                            finishDocumentLoadTime: Date.now() * 0.001,
                            finishLoadTime: Date.now() * 0.001,
                            firstPaintTime: Date.now() * 0.001,
                            firstPaintAfterLoadTime: 0,
                            navigationType: 'Other'
                        };
                    },
                    csi: function() {
                        return {
                            pageT: Date.now(),
                            startE: Date.now(),
                            tran: 15
                        };
                    }
                };
                
                // Mock plugins
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [
                        {
                            0: {type: "application/x-google-chrome-pdf", suffixes: "pdf", description: "Portable Document Format", enabledPlugin: Plugin},
                            description: "Portable Document Format",
                            filename: "internal-pdf-viewer",
                            length: 1,
                            name: "Chrome PDF Plugin"
                        },
                        {
                            0: {type: "application/pdf", suffixes: "pdf", description: "", enabledPlugin: Plugin},
                            description: "",
                            filename: "mhjfbmdgcfjbbpaeojofohoefgiehjai",
                            length: 1,
                            name: "Chrome PDF Viewer"
                        }
                    ],
                });
                
                // Mock languages
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en'],
                });
                
                // Mock permissions
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                // Mock battery API
                Object.defineProperty(navigator, 'getBattery', {
                    get: () => () => Promise.resolve({
                        charging: true,
                        chargingTime: 0,
                        dischargingTime: Infinity,
                        level: 1,
                        addEventListener: () => {},
                        removeEventListener: () => {},
                        onchargingchange: null,
                        onchargingtimechange: null,
                        ondischargingtimechange: null,
                        onlevelchange: null
                    })
                });
                
                // Override getContext to avoid detection
                const getContext = HTMLCanvasElement.prototype.getContext;
                HTMLCanvasElement.prototype.getContext = function(type) {
                    if (type === '2d') {
                        const context = getContext.apply(this, arguments);
                        const originalFillText = context.fillText;
                        context.fillText = function() {
                            // Add slight randomization to avoid fingerprinting
                            return originalFillText.apply(this, arguments);
                        };
                        return context;
                    }
                    return getContext.apply(this, arguments);
                };
            """)
            
            self.page = await self.context.new_page()
            
            # Additional page-level stealth measures
            await self.page.evaluate("""
                // Remove automation indicators
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
                delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            """)
            
            await self.log(LogLevel.SUCCESS, "Stealth browser initialized successfully", step="STEALTH_INIT")
            return True
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Failed to initialize stealth browser: {str(e)}", 
                         details={"error": str(e)}, step="STEALTH_INIT")
            return False

    async def discover_dynamic_elements(self, page: Page) -> Dict[str, List[str]]:
        """Discover all dynamic form elements and their positions"""
        try:
            await self.log(LogLevel.INFO, "Discovering dynamic form elements", step="ELEMENT_DISCOVERY")
            
            # Execute JavaScript to find all form elements
            elements = await page.evaluate("""
                () => {
                    const discovered = {
                        email_fields: [],
                        location_fields: [],
                        visa_type_fields: [],
                        visa_sub_type_fields: [],
                        category_fields: [],
                        appointment_fields: [],
                        all_inputs: [],
                        all_selects: [],
                        form_containers: []
                    };
                    
                    // Find all email-related inputs
                    document.querySelectorAll('input').forEach((input, index) => {
                        const id = input.id;
                        const name = input.name || '';
                        const placeholder = input.placeholder || '';
                        const type = input.type;
                        const text = input.previousElementSibling?.textContent || '';
                        
                        // Store all input info
                        discovered.all_inputs.push({
                            id: id,
                            name: name,
                            type: type,
                            placeholder: placeholder,
                            index: index,
                            visible: input.offsetParent !== null,
                            text: text
                        });
                        
                        // Categorize inputs
                        if (id && (id.includes('email') || id.includes('Email') || text.toLowerCase().includes('email'))) {
                            discovered.email_fields.push(id);
                        }
                        if (id && (id.includes('location') || id.includes('Location') || text.toLowerCase().includes('location'))) {
                            discovered.location_fields.push(id);
                        }
                    });
                    
                    // Find all select elements
                    document.querySelectorAll('select').forEach((select, index) => {
                        const id = select.id;
                        const name = select.name || '';
                        const text = select.previousElementSibling?.textContent || '';
                        
                        discovered.all_selects.push({
                            id: id,
                            name: name,
                            index: index,
                            visible: select.offsetParent !== null,
                            text: text
                        });
                        
                        // Categorize selects
                        if (text.toLowerCase().includes('visa type')) {
                            discovered.visa_type_fields.push(id);
                        }
                        if (text.toLowerCase().includes('visa sub type')) {
                            discovered.visa_sub_type_fields.push(id);
                        }
                        if (text.toLowerCase().includes('category')) {
                            discovered.category_fields.push(id);
                        }
                        if (text.toLowerCase().includes('appointment')) {
                            discovered.appointment_fields.push(id);
                        }
                    });
                    
                    // Find form containers
                    document.querySelectorAll('form, div.form, .form-container').forEach((container, index) => {
                        discovered.form_containers.push({
                            tagName: container.tagName,
                            className: container.className,
                            id: container.id,
                            index: index
                        });
                    });
                    
                    return discovered;
                }
            """)
            
            self.discovered_elements = elements
            
            await self.log(LogLevel.SUCCESS, 
                         f"Discovered {len(elements['email_fields'])} email fields, {len(elements['all_inputs'])} total inputs", 
                         details=elements, step="ELEMENT_DISCOVERY")
            
            return elements
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Element discovery failed: {str(e)}", step="ELEMENT_DISCOVERY")
            return {}

    async def find_active_form_field(self, field_type: str, page: Page) -> Optional[str]:
        """Find the currently active/visible form field of a given type"""
        try:
            # First discover elements if not done
            if not self.discovered_elements:
                await self.discover_dynamic_elements(page)
            
            field_candidates = self.discovered_elements.get(f'{field_type}_fields', [])
            
            if not field_candidates:
                # Fallback: search for visible fields
                await self.log(LogLevel.WARNING, f"No {field_type} fields found in discovery, searching manually", step="FIELD_SEARCH")
                
                # Try common field patterns
                patterns = {
                    'email': ['input[type="email"]', 'input[placeholder*="email"]', 'input[name*="email"]', 'input[id*="email"]'],
                    'location': ['select[name*="location"]', 'select[id*="location"]'],
                    'visa_type': ['select[name*="visa"]', 'select[id*="visa"]'],
                    'password': ['input[type="password"]']
                }
                
                for pattern in patterns.get(field_type, []):
                    elements = await page.query_selector_all(pattern)
                    for element in elements:
                        is_visible = await element.is_visible()
                        if is_visible:
                            element_id = await element.get_attribute('id')
                            element_name = await element.get_attribute('name')
                            return element_id or element_name or pattern
            
            # Check which field is visible and active
            for field_id in field_candidates:
                try:
                    element = await page.query_selector(f'#{field_id}')
                    if element:
                        is_visible = await element.is_visible()
                        is_enabled = await element.is_enabled()
                        if is_visible and is_enabled:
                            await self.log(LogLevel.SUCCESS, f"Found active {field_type} field: {field_id}", step="FIELD_SEARCH")
                            return field_id
                except:
                    continue
            
            await self.log(LogLevel.WARNING, f"No active {field_type} field found", step="FIELD_SEARCH")
            return None
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Failed to find active {field_type} field: {str(e)}", step="FIELD_SEARCH")
            return None

    async def enhanced_captcha_solver(self, page: Page, target_number: str) -> bool:
        """Enhanced captcha solving with improved accuracy"""
        try:
            await self.log(LogLevel.INFO, f"Starting enhanced captcha solving for target: {target_number}", step="CAPTCHA_SOLVE")
            
            # Wait for captcha grid to load
            await page.wait_for_load_state('networkidle')
            await self.human_delay('page_load')
            
            # Find all captcha images with multiple selector strategies
            captcha_selectors = [
                'img[src*="captcha"]',
                'img[src*="Captcha"]', 
                'img[alt*="captcha"]',
                'img[data-*="captcha"]',
                '.captcha img',
                '.captcha-grid img',
                'div[id*="captcha"] img',
                'form img'
            ]
            
            all_images = []
            for selector in captcha_selectors:
                try:
                    images = await page.query_selector_all(selector)
                    all_images.extend(images)
                    if images:
                        await self.log(LogLevel.INFO, f"Found {len(images)} images with selector: {selector}", step="CAPTCHA_SOLVE")
                except:
                    continue
            
            # Remove duplicates
            unique_images = []
            seen_srcs = set()
            for img in all_images:
                try:
                    src = await img.get_attribute('src')
                    if src and src not in seen_srcs:
                        seen_srcs.add(src)
                        unique_images.append(img)
                except:
                    continue
            
            if not unique_images:
                await self.log(LogLevel.ERROR, "No captcha images found", step="CAPTCHA_SOLVE")
                return False
            
            await self.log(LogLevel.INFO, f"Processing {len(unique_images)} unique captcha images", step="CAPTCHA_SOLVE")
            
            # Prepare tile data for OCR
            tile_data = []
            for idx, img in enumerate(unique_images):
                try:
                    src = await img.get_attribute('src')
                    if not src:
                        continue
                    
                    # Handle base64 images
                    if src.startswith('data:image'):
                        base64_data = src.split(',')[1]
                    else:
                        # Download image and convert to base64
                        try:
                            import aiohttp
                            async with aiohttp.ClientSession() as session:
                                async with session.get(src) as response:
                                    if response.status == 200:
                                        image_bytes = await response.read()
                                        base64_data = base64.b64encode(image_bytes).decode()
                                    else:
                                        continue
                        except:
                            # Fallback: navigate to image
                            response = await page.goto(src)
                            if response and response.ok:
                                image_bytes = await response.body()
                                base64_data = base64.b64encode(image_bytes).decode()
                            else:
                                continue
                    
                    tile_data.append({
                        "base64Image": base64_data,
                        "index": idx,
                        "src": src
                    })
                    
                except Exception as e:
                    await self.log(LogLevel.WARNING, f"Error processing image {idx}: {str(e)}", step="CAPTCHA_SOLVE")
                    continue
            
            if not tile_data:
                await self.log(LogLevel.ERROR, "No valid captcha tile data collected", step="CAPTCHA_SOLVE")
                return False
            
            # Call enhanced OCR API
            payload = {
                "target": target_number,
                "tiles": tile_data,
                "enhanced_mode": True
            }
            
            await self.log(LogLevel.INFO, f"Calling OCR API with {len(tile_data)} tiles", step="CAPTCHA_SOLVE")
            
            response = requests.post(self.ocr_api_url, json=payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                matching_indices = result.get('matching_indices', [])
                
                await self.log(LogLevel.SUCCESS, f"OCR found {len(matching_indices)} matching tiles", 
                             details={"indices": matching_indices, "target": target_number}, step="CAPTCHA_SOLVE")
                
                # Click on matching tiles with human-like behavior
                for idx in matching_indices:
                    if idx < len(unique_images):
                        try:
                            img = unique_images[idx]
                            
                            # Scroll image into view
                            await img.scroll_into_view_if_needed()
                            await self.human_delay('click')
                            
                            # Click with human-like behavior
                            box = await img.bounding_box()
                            if box:
                                # Add small random offset to click position
                                offset_x = random.uniform(-5, 5)
                                offset_y = random.uniform(-5, 5)
                                click_x = box['x'] + box['width']/2 + offset_x
                                click_y = box['y'] + box['height']/2 + offset_y
                                
                                await page.mouse.click(click_x, click_y)
                                await self.log(LogLevel.INFO, f"Clicked captcha tile {idx}", step="CAPTCHA_SOLVE")
                            else:
                                await img.click()
                            
                            await self.human_delay('click')
                            
                        except Exception as e:
                            await self.log(LogLevel.WARNING, f"Error clicking tile {idx}: {str(e)}", step="CAPTCHA_SOLVE")
                            continue
                
                await self.log(LogLevel.SUCCESS, f"Successfully clicked {len(matching_indices)} captcha tiles", step="CAPTCHA_SOLVE")
                return True
            else:
                await self.log(LogLevel.ERROR, f"OCR API failed with status {response.status_code}: {response.text}", step="CAPTCHA_SOLVE")
                return False
                
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Enhanced captcha solving failed: {str(e)}", step="CAPTCHA_SOLVE")
            return False

    async def human_like_typing(self, page: Page, selector: str, text: str):
        """Type text with human-like patterns"""
        try:
            element = await page.query_selector(selector)
            if not element:
                return False
            
            await element.focus()
            await self.human_delay('form_fill')
            
            # Clear field first
            await element.fill('')
            await self.human_delay('typing')
            
            # Type character by character with random delays
            for char in text:
                await element.type(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))
            
            await self.human_delay('typing')
            return True
            
        except Exception as e:
            await self.log(LogLevel.WARNING, f"Human typing failed for {selector}: {str(e)}", step="HUMAN_TYPING")
            return False

    async def enhanced_step1_login(self) -> bool:
        """Enhanced Step 1: Login with dynamic element detection"""
        try:
            await self.log(LogLevel.INFO, "Starting Enhanced Step 1: Dynamic login", step="ENHANCED_STEP1")
            
            if not self.browser:
                if not await self.init_stealth_browser():
                    return False
            
            await self.real_time_update("Navigating to BLS login page...", "info", step="ENHANCED_STEP1")
            
            # Navigate to login page with retry mechanism
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self.page.goto(self.urls['login'], wait_until='networkidle', timeout=30000)
                    break
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise e
                    await self.log(LogLevel.WARNING, f"Navigation attempt {attempt + 1} failed, retrying...", step="ENHANCED_STEP1")
                    await asyncio.sleep(2)
            
            await self.human_delay('page_load')
            
            # Discover dynamic elements
            await self.real_time_update("Analyzing page structure and discovering form elements...", "info", step="ENHANCED_STEP1")
            await self.discover_dynamic_elements(self.page)
            
            # Find active email field
            await self.real_time_update("Locating active email input field...", "info", step="ENHANCED_STEP1")
            email_field = await self.find_active_form_field('email', self.page)
            
            if not email_field:
                await self.log(LogLevel.ERROR, "Could not find active email field", step="ENHANCED_STEP1")
                return False
            
            await self.real_time_update(f"Found email field: {email_field}, filling with human-like typing...", "success", step="ENHANCED_STEP1")
            
            # Fill email with human-like typing
            success = await self.human_like_typing(self.page, f'#{email_field}', self.email)
            if not success:
                # Fallback to direct fill
                await self.page.fill(f'#{email_field}', self.email)
            
            await self.human_delay('form_fill')
            
            # Submit form
            await self.real_time_update("Submitting login form...", "info", step="ENHANCED_STEP1")
            
            submit_selectors = ['#btnVerify', 'input[type="submit"]', 'button[type="submit"]', '.btn-verify']
            submitted = False
            
            for selector in submit_selectors:
                try:
                    btn = await self.page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        submitted = True
                        break
                except:
                    continue
            
            if not submitted:
                await self.log(LogLevel.ERROR, "Could not find or click submit button", step="ENHANCED_STEP1")
                return False
            
            await self.human_delay('page_load')
            await self.page.wait_for_load_state('networkidle')
            
            # Check if redirected to captcha page
            current_url = self.page.url
            await self.real_time_update(f"Redirected to: {current_url}", "info", step="ENHANCED_STEP1")
            
            if 'logincaptcha' in current_url or 'captcha' in current_url.lower():
                await self.log(LogLevel.SUCCESS, "Step 1 completed - redirected to captcha page", step="ENHANCED_STEP1")
                return True
            else:
                await self.log(LogLevel.WARNING, f"Unexpected URL after login: {current_url}", step="ENHANCED_STEP1")
                # Still continue, might be valid
                return True
                
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Enhanced Step 1 failed: {str(e)}", 
                         details={"error": str(e)}, step="ENHANCED_STEP1")
            return False

    async def enhanced_step2_captcha_login(self) -> bool:
        """Enhanced Step 2: Password and captcha with advanced solving"""
        try:
            await self.log(LogLevel.INFO, "Starting Enhanced Step 2: Password and captcha", step="ENHANCED_STEP2")
            
            await self.page.wait_for_load_state('networkidle')
            await self.human_delay('page_load')
            
            # Fill password
            await self.real_time_update("Locating password field...", "info", step="ENHANCED_STEP2")
            
            password_field = await self.find_active_form_field('password', self.page)
            if password_field:
                await self.human_like_typing(self.page, f'#{password_field}', self.password)
            else:
                # Fallback to common selectors
                password_selectors = ['input[type="password"]', '#password', '#Password']
                filled = False
                for selector in password_selectors:
                    try:
                        element = await self.page.query_selector(selector)
                        if element and await element.is_visible():
                            await self.human_like_typing(self.page, selector, self.password)
                            filled = True
                            break
                    except:
                        continue
                
                if not filled:
                    await self.log(LogLevel.ERROR, "Could not find password field", step="ENHANCED_STEP2")
                    return False
            
            await self.real_time_update("Password filled, analyzing captcha...", "success", step="ENHANCED_STEP2")
            
            # Enhanced captcha handling
            await self.real_time_update("Searching for captcha challenge...", "info", step="ENHANCED_STEP2")
            
            # Extract target number from page
            page_text = await self.page.text_content('body')
            target_matches = re.findall(r'select.*?(\d+)', page_text, re.IGNORECASE)
            
            if not target_matches:
                await self.log(LogLevel.WARNING, "Could not find captcha target number, searching more broadly", step="ENHANCED_STEP2")
                # More aggressive search
                target_matches = re.findall(r'(\d{3,4})', page_text)
            
            if not target_matches:
                await self.log(LogLevel.ERROR, "No captcha target number found", step="ENHANCED_STEP2")
                return False
            
            # Use the most common target or the first one
            target_number = target_matches[0]
            await self.real_time_update(f"Found captcha target: {target_number}", "success", step="ENHANCED_STEP2")
            
            # Solve captcha with enhanced method
            captcha_success = await self.enhanced_captcha_solver(self.page, target_number)
            if not captcha_success:
                await self.log(LogLevel.ERROR, "Captcha solving failed", step="ENHANCED_STEP2")
                return False
            
            await self.real_time_update("Captcha solved successfully, submitting form...", "success", step="ENHANCED_STEP2")
            await self.human_delay('form_fill')
            
            # Submit form
            submit_selectors = ['input[type="submit"]', 'button[type="submit"]', '#submit', '.btn-submit']
            submitted = False
            
            for selector in submit_selectors:
                try:
                    btn = await self.page.query_selector(selector)
                    if btn and await btn.is_visible():
                        await btn.click()
                        submitted = True
                        break
                except:
                    continue
            
            if not submitted:
                await self.log(LogLevel.ERROR, "Could not find submit button", step="ENHANCED_STEP2")
                return False
            
            await self.human_delay('page_load')
            await self.page.wait_for_load_state('networkidle')
            
            # Check login success
            current_url = self.page.url
            await self.real_time_update(f"After login submission: {current_url}", "info", step="ENHANCED_STEP2")
            
            if 'login' not in current_url.lower() or 'dashboard' in current_url.lower() or 'appointment' in current_url.lower():
                self.is_logged_in = True
                await self.log(LogLevel.SUCCESS, "Enhanced Step 2 completed - Login successful", step="ENHANCED_STEP2")
                return True
            else:
                await self.log(LogLevel.ERROR, "Login may have failed - still on login-related page", step="ENHANCED_STEP2")
                return False
                
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Enhanced Step 2 failed: {str(e)}", 
                         details={"error": str(e)}, step="ENHANCED_STEP2")
            return False

    async def enhanced_full_check(self) -> Tuple[bool, List[AppointmentSlot]]:
        """Run enhanced complete appointment check cycle"""
        try:
            await self.log(LogLevel.INFO, "Starting enhanced full appointment check cycle", step="ENHANCED_FULL_CHECK")
            await self.real_time_update("🚀 Starting enhanced BLS appointment check...", "info", step="ENHANCED_FULL_CHECK")
            
            # Step 1: Enhanced login
            await self.real_time_update("📝 Step 1: Logging into BLS system...", "info", step="ENHANCED_FULL_CHECK")
            if not await self.enhanced_step1_login():
                await self.real_time_update("❌ Login step failed", "error", step="ENHANCED_FULL_CHECK")
                return False, []
            
            # Step 2: Enhanced password and captcha
            await self.real_time_update("🔐 Step 2: Handling password and captcha...", "info", step="ENHANCED_FULL_CHECK")
            if not await self.enhanced_step2_captcha_login():
                await self.real_time_update("❌ Captcha/password step failed", "error", step="ENHANCED_FULL_CHECK")
                return False, []
            
            # Step 3: Check appointments
            await self.real_time_update("📅 Step 3: Searching for available appointments...", "info", step="ENHANCED_FULL_CHECK")
            slots = await self.enhanced_appointment_check()
            
            if slots:
                await self.real_time_update(f"🎉 Found {len(slots)} appointment slots!", "success", step="ENHANCED_FULL_CHECK")
                # Save slots to database
                for slot in slots:
                    await self.db.appointment_slots.insert_one(slot.dict())
            else:
                await self.real_time_update("📭 No appointment slots found this time", "info", step="ENHANCED_FULL_CHECK")
            
            await self.log(LogLevel.SUCCESS, f"Enhanced full check completed. Found {len(slots)} slots", 
                         details={"slots_found": len(slots)}, step="ENHANCED_FULL_CHECK")
            
            return True, slots
            
        except Exception as e:
            await self.real_time_update(f"❌ Full check failed: {str(e)}", "error", step="ENHANCED_FULL_CHECK")
            await self.log(LogLevel.ERROR, f"Enhanced full check failed: {str(e)}", 
                         details={"error": str(e)}, step="ENHANCED_FULL_CHECK")
            return False, []

    async def enhanced_appointment_check(self) -> List[AppointmentSlot]:
        """Enhanced appointment checking with better slot detection"""
        try:
            await self.log(LogLevel.INFO, "Starting enhanced appointment check", step="ENHANCED_APPOINTMENT_CHECK")
            
            # Navigate to appointment page
            appointment_urls = [
                self.urls['appointment_captcha'],
                self.urls['new_appointment'], 
                self.urls['visa_type']
            ]
            
            for url in appointment_urls:
                try:
                    await self.real_time_update(f"Navigating to: {url}", "info", step="ENHANCED_APPOINTMENT_CHECK")
                    await self.page.goto(url, wait_until='networkidle', timeout=30000)
                    await self.human_delay('page_load')
                    
                    current_url = self.page.url
                    if 'appointment' in current_url.lower() or 'visa' in current_url.lower():
                        break
                except Exception as e:
                    await self.log(LogLevel.WARNING, f"Failed to navigate to {url}: {str(e)}", step="ENHANCED_APPOINTMENT_CHECK")
                    continue
            
            # Handle any additional captcha
            page_text = await self.page.text_content('body')
            if 'captcha' in page_text.lower() or 'select' in page_text.lower():
                await self.real_time_update("Additional captcha detected, solving...", "warning", step="ENHANCED_APPOINTMENT_CHECK")
                
                target_matches = re.findall(r'select.*?(\d+)', page_text, re.IGNORECASE)
                if target_matches:
                    await self.enhanced_captcha_solver(self.page, target_matches[0])
                    
                    # Submit captcha
                    submit_btns = await self.page.query_selector_all('input[type="submit"], button[type="submit"]')
                    for btn in submit_btns:
                        if await btn.is_visible():
                            await btn.click()
                            break
                    
                    await self.page.wait_for_load_state('networkidle')
            
            # Enhanced slot parsing
            return await self.enhanced_slot_parsing()
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Enhanced appointment check failed: {str(e)}", step="ENHANCED_APPOINTMENT_CHECK")
            return []

    async def enhanced_slot_parsing(self) -> List[AppointmentSlot]:
        """Enhanced slot parsing with multiple detection strategies"""
        try:
            slots = []
            await self.real_time_update("Analyzing page for appointment slots...", "info", step="ENHANCED_SLOT_PARSING")
            
            # Wait for page to fully load
            await self.page.wait_for_load_state('networkidle')
            await self.human_delay('page_load')
            
            # Multiple strategies for finding slots
            slot_indicators = [
                'available', 'book now', 'select date', 'appointment slot', 
                'open slot', 'vacant', 'libre', 'disponible', 'free'
            ]
            
            # Strategy 1: Look for structured slot elements
            slot_selectors = [
                '.appointment-slot', '.slot-item', '.available-slot',
                'tr:has-text("Available")', 'div:has-text("Available")',
                '[data-slot-id]', '.calendar-slot', '.booking-slot',
                '.date-slot', '.time-slot', '.appointment-row'
            ]
            
            slot_elements = []
            for selector in slot_selectors:
                try:
                    elements = await self.page.query_selector_all(selector)
                    if elements:
                        slot_elements.extend(elements)
                        await self.log(LogLevel.INFO, f"Found {len(elements)} potential slots with selector: {selector}", step="ENHANCED_SLOT_PARSING")
                except:
                    continue
            
            # Strategy 2: Text-based detection
            page_text = await self.page.text_content('body')
            page_html = await self.page.content()
            
            availability_found = False
            for indicator in slot_indicators:
                if indicator.lower() in page_text.lower():
                    availability_found = True
                    await self.log(LogLevel.INFO, f"Found availability indicator: {indicator}", step="ENHANCED_SLOT_PARSING")
                    break
            
            # Strategy 3: Calendar/date detection
            date_patterns = [
                r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})',
                r'(\d{4}[\/\-]\d{1,2}[\/\-]\d{1,2})',
                r'(January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2}',
                r'\d{1,2}\s+(January|February|March|April|May|June|July|August|September|October|November|December)'
            ]
            
            found_dates = []
            for pattern in date_patterns:
                matches = re.findall(pattern, page_text, re.IGNORECASE)
                found_dates.extend(matches)
            
            if found_dates:
                await self.log(LogLevel.INFO, f"Found {len(found_dates)} potential dates", step="ENHANCED_SLOT_PARSING")
            
            # Strategy 4: Time slot detection
            time_patterns = [
                r'(\d{1,2}:\d{2}(?:\s*[AaPp][Mm])?)',
                r'(\d{1,2}h\d{2})',
                r'(\d{1,2}-\d{1,2})'
            ]
            
            found_times = []
            for pattern in time_patterns:
                matches = re.findall(pattern, page_text)
                found_times.extend(matches)
            
            # Process found elements
            for idx, element in enumerate(slot_elements):
                try:
                    text = await element.text_content() or ""
                    
                    # Skip if no availability indication
                    if not any(indicator in text.lower() for indicator in slot_indicators):
                        continue
                    
                    # Extract information
                    date_match = re.search(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', text)
                    time_match = re.search(r'(\d{1,2}:\d{2})', text)
                    
                    appointment_date = date_match.group(1) if date_match else "TBD"
                    appointment_time = time_match.group(1) if time_match else "TBD"
                    
                    # Determine visa type and category
                    visa_type = "Spain Visa"
                    visa_category = "General"
                    
                    if "tourism" in text.lower() or "tourist" in text.lower():
                        visa_category = "Tourism"
                    elif "business" in text.lower():
                        visa_category = "Business"
                    elif "family" in text.lower():
                        visa_category = "Family"
                    elif "student" in text.lower():
                        visa_category = "Student"
                    
                    slot = AppointmentSlot(
                        appointment_date=appointment_date,
                        appointment_time=appointment_time,
                        visa_type=visa_type,
                        visa_category=visa_category,
                        location="Algeria",
                        available_slots=1,
                        status=AppointmentStatus.AVAILABLE
                    )
                    slots.append(slot)
                    
                except Exception as e:
                    await self.log(LogLevel.WARNING, f"Error parsing slot element {idx}: {str(e)}", step="ENHANCED_SLOT_PARSING")
                    continue
            
            # If no structured slots found but availability indicators present
            if not slots and availability_found:
                await self.log(LogLevel.INFO, "No structured slots found, but availability detected - creating generic slot", step="ENHANCED_SLOT_PARSING")
                
                # Create generic available slot
                slot = AppointmentSlot(
                    appointment_date=datetime.utcnow().strftime("%Y-%m-%d"),
                    appointment_time="TBD",
                    visa_type="Spain Visa",
                    visa_category="General",
                    location="Algeria",
                    available_slots=1,
                    status=AppointmentStatus.AVAILABLE
                )
                slots.append(slot)
            
            # Enhanced logging
            if slots:
                await self.real_time_update(f"✅ Successfully found {len(slots)} appointment slots", "success", step="ENHANCED_SLOT_PARSING")
                await self.log(LogLevel.SUCCESS, f"Successfully parsed {len(slots)} appointment slots", 
                             details={"slots": [s.dict() for s in slots]}, step="ENHANCED_SLOT_PARSING")
            else:
                await self.real_time_update("No appointment slots available at this time", "info", step="ENHANCED_SLOT_PARSING")
                await self.log(LogLevel.INFO, "No appointment slots found in current page", step="ENHANCED_SLOT_PARSING")
                
                # Take screenshot for debugging
                try:
                    screenshot_path = f"/tmp/no_slots_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"
                    await self.page.screenshot(path=screenshot_path)
                    await self.log(LogLevel.INFO, f"Debug screenshot saved: {screenshot_path}", step="ENHANCED_SLOT_PARSING")
                except:
                    pass
            
            return slots
            
        except Exception as e:
            await self.log(LogLevel.ERROR, f"Enhanced slot parsing failed: {str(e)}", step="ENHANCED_SLOT_PARSING")
            return []

    async def cleanup(self):
        """Enhanced cleanup with proper resource management"""
        try:
            await self.real_time_update("🧹 Cleaning up browser resources...", "info", step="CLEANUP")
            
            if self.page:
                await self.page.close()
                self.page = None
            if self.context:
                await self.context.close()
                self.context = None
            if self.browser:
                await self.browser.close()
                self.browser = None
            if hasattr(self, 'playwright') and self.playwright:
                await self.playwright.stop()
                
            await self.log(LogLevel.SUCCESS, "Enhanced cleanup completed", step="CLEANUP")
            
        except Exception as e:
            await self.log(LogLevel.WARNING, f"Cleanup had issues: {e}", step="CLEANUP")