#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for BLS Spanish Automation System
Tests all FastAPI endpoints and WebSocket functionality
"""

import requests
import json
import sys
import asyncio
import websockets
from datetime import datetime
from typing import Dict, Any

class BLSBackendTester:
    def __init__(self, base_url="http://localhost:8001"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.ws_url = base_url.replace('https://', 'ws://').replace('http://', 'ws://') + '/ws'
        self.tests_run = 0
        self.tests_passed = 0
        self.session = requests.Session()
        self.session.headers.update({'Content-Type': 'application/json'})

    def log_test(self, name: str, success: bool, details: str = ""):
        """Log test results"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}: PASSED {details}")
        else:
            print(f"❌ {name}: FAILED {details}")
        return success

    def test_api_endpoint(self, name: str, method: str, endpoint: str, expected_status: int = 200, data: Dict = None) -> tuple:
        """Test a single API endpoint"""
        url = f"{self.api_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = self.session.get(url, timeout=10)
            elif method.upper() == 'POST':
                response = self.session.post(url, json=data, timeout=10)
            else:
                return self.log_test(name, False, f"Unsupported method: {method}"), None

            success = response.status_code == expected_status
            details = f"(Status: {response.status_code})"
            
            if success:
                try:
                    response_data = response.json()
                    details += f" - Response keys: {list(response_data.keys()) if isinstance(response_data, dict) else 'Non-dict response'}"
                except:
                    details += " - Non-JSON response"
            else:
                details += f" - Expected: {expected_status}"
                try:
                    error_detail = response.json().get('detail', 'No detail')
                    details += f" - Error: {error_detail}"
                except:
                    details += f" - Raw response: {response.text[:100]}"

            self.log_test(name, success, details)
            return success, response.json() if success and response.content else None
            
        except requests.exceptions.RequestException as e:
            return self.log_test(name, False, f"Request failed: {str(e)}"), None
        except Exception as e:
            return self.log_test(name, False, f"Unexpected error: {str(e)}"), None

    async def test_websocket_connection(self):
        """Test WebSocket connection"""
        try:
            print(f"\n🔌 Testing WebSocket connection to: {self.ws_url}")
            
            async with websockets.connect(self.ws_url, timeout=10) as websocket:
                # Send ping message
                ping_message = json.dumps({"type": "ping"})
                await websocket.send(ping_message)
                
                # Wait for pong response
                response = await asyncio.wait_for(websocket.recv(), timeout=5)
                response_data = json.loads(response)
                
                success = response_data.get('type') == 'pong'
                self.log_test("WebSocket Connection & Ping/Pong", success, 
                            f"Response: {response_data}" if success else f"Unexpected response: {response}")
                
                return success
                
        except asyncio.TimeoutError:
            return self.log_test("WebSocket Connection", False, "Connection timeout")
        except Exception as e:
            return self.log_test("WebSocket Connection", False, f"Connection failed: {str(e)}")

    def test_system_status(self):
        """Test system status endpoint"""
        success, data = self.test_api_endpoint("System Status", "GET", "system/status")
        
        if success and data:
            # Validate response structure
            required_fields = ['status', 'total_checks', 'slots_found', 'successful_bookings', 'error_count']
            missing_fields = [field for field in required_fields if field not in data]
            
            if missing_fields:
                self.log_test("System Status Structure", False, f"Missing fields: {missing_fields}")
            else:
                self.log_test("System Status Structure", True, f"All required fields present")
                
        return success

    def test_logs_endpoint(self):
        """Test logs endpoint"""
        success, data = self.test_api_endpoint("System Logs", "GET", "logs")
        
        if success and data:
            # Validate logs structure
            if 'logs' in data and 'total_count' in data:
                self.log_test("Logs Structure", True, f"Found {data['total_count']} total logs, returned {len(data['logs'])} logs")
            else:
                self.log_test("Logs Structure", False, "Missing 'logs' or 'total_count' fields")
                
        return success

    def test_appointments_endpoint(self):
        """Test appointments endpoint"""
        success, data = self.test_api_endpoint("Available Appointments", "GET", "appointments/available")
        
        if success and data:
            # Validate appointments structure
            if 'slots' in data and 'total_count' in data:
                self.log_test("Appointments Structure", True, f"Found {data['total_count']} total slots, returned {len(data['slots'])} slots")
            else:
                self.log_test("Appointments Structure", False, "Missing 'slots' or 'total_count' fields")
                
        return success

    def test_system_controls(self):
        """Test system start/stop endpoints"""
        print(f"\n🎮 Testing System Controls...")
        
        # Test system start
        start_data = {"check_interval_minutes": 5}
        start_success, start_response = self.test_api_endpoint("System Start", "POST", "system/start", 200, start_data)
        
        if start_success:
            # Wait a moment for system to initialize
            import time
            time.sleep(2)
            
            # Check if system status changed to running
            status_success, status_data = self.test_api_endpoint("System Status After Start", "GET", "system/status")
            if status_success and status_data:
                is_running = status_data.get('status') == 'running'
                self.log_test("System Status Changed to Running", is_running, 
                            f"Status: {status_data.get('status')}")
        
        # Test system stop
        stop_success, stop_response = self.test_api_endpoint("System Stop", "POST", "system/stop", 200)
        
        if stop_success:
            # Wait a moment for system to stop
            import time
            time.sleep(2)
            
            # Check if system status changed to stopped
            status_success, status_data = self.test_api_endpoint("System Status After Stop", "GET", "system/status")
            if status_success and status_data:
                is_stopped = status_data.get('status') == 'stopped'
                self.log_test("System Status Changed to Stopped", is_stopped, 
                            f"Status: {status_data.get('status')}")
        
        return start_success and stop_success

    def test_single_check(self):
        """Test single check endpoint"""
        success, data = self.test_api_endpoint("Single Check", "POST", "test/check-once")
        
        if success and data:
            # Validate single check response
            expected_fields = ['success', 'slots_found', 'slots', 'method']
            missing_fields = [field for field in expected_fields if field not in data]
            
            if missing_fields:
                self.log_test("Single Check Structure", False, f"Missing fields: {missing_fields}")
            else:
                self.log_test("Single Check Structure", True, 
                            f"Method: {data.get('method')}, Slots found: {data.get('slots_found')}")
                
        return success

    def test_ocr_endpoint(self):
        """Test OCR endpoint"""
        # Test with mock data
        ocr_data = {
            "target": "5",
            "tiles": [
                {"base64Image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="},
                {"base64Image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=="}
            ],
            "enhanced_mode": False
        }
        
        success, data = self.test_api_endpoint("OCR Match", "POST", "ocr-match", 200, ocr_data)
        
        if success and data:
            # Validate OCR response
            expected_fields = ['target', 'matching_indices', 'processed_tiles', 'success']
            missing_fields = [field for field in expected_fields if field not in data]
            
            if missing_fields:
                self.log_test("OCR Response Structure", False, f"Missing fields: {missing_fields}")
            else:
                self.log_test("OCR Response Structure", True, 
                            f"Processed {data.get('processed_tiles')} tiles, found {len(data.get('matching_indices', []))} matches")
                
        return success

    def test_root_endpoint(self):
        """Test root API endpoint"""
        success, data = self.test_api_endpoint("Root API", "GET", "")
        
        if success and data:
            if 'message' in data and 'version' in data:
                self.log_test("Root API Structure", True, f"Message: {data.get('message')}, Version: {data.get('version')}")
            else:
                self.log_test("Root API Structure", False, "Missing 'message' or 'version' fields")
                
        return success

    async def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting BLS Backend API Testing...")
        print(f"📍 Testing against: {self.base_url}")
        print(f"🔗 API Base URL: {self.api_url}")
        print(f"🔌 WebSocket URL: {self.ws_url}")
        print("=" * 80)

        # Test basic connectivity
        print(f"\n📡 Testing Basic Connectivity...")
        self.test_root_endpoint()

        # Test core endpoints
        print(f"\n📊 Testing Core Endpoints...")
        self.test_system_status()
        self.test_logs_endpoint()
        self.test_appointments_endpoint()

        # Test system controls
        self.test_system_controls()

        # Test additional endpoints
        print(f"\n🧪 Testing Additional Endpoints...")
        self.test_single_check()
        self.test_ocr_endpoint()

        # Test WebSocket
        print(f"\n🔌 Testing WebSocket...")
        await self.test_websocket_connection()

        # Print summary
        print("\n" + "=" * 80)
        print(f"📈 TEST SUMMARY")
        print(f"Total Tests: {self.tests_run}")
        print(f"Passed: {self.tests_passed}")
        print(f"Failed: {self.tests_run - self.tests_passed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run)*100:.1f}%" if self.tests_run > 0 else "No tests run")
        
        if self.tests_passed == self.tests_run:
            print("🎉 ALL TESTS PASSED!")
            return 0
        else:
            print("⚠️  SOME TESTS FAILED!")
            return 1

async def main():
    """Main test runner"""
    tester = BLSBackendTester()
    return await tester.run_all_tests()

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Test runner failed: {str(e)}")
        sys.exit(1)