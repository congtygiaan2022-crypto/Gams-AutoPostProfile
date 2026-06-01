import requests
import time

def _server_reachable(base_url, timeout=2):
    """Quick check: is the browser API server reachable at all?"""
    try:
        # Just try connecting - 200 or any response = reachable
        requests.get(base_url, timeout=timeout)
        return True
    except Exception:
        return False

class GPMLoginAPI:
    def __init__(self, base_url="http://localhost:5555"):
        self.base_url = base_url

    def get_profiles(self):
        # Default GPM API for profiles
        # Trying various common endpoints for GPM Login V2 and V3
        endpoints = ["/api/v3/profiles", "/api/v2/profiles", "/api/v1/profiles", "/profiles"]
        success = False
        all_profiles = []
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    success = True
                    print(f"DEBUG: GPM Profiles loaded successfully via {endpoint}")
                    
                    if isinstance(data, list):
                        all_profiles = data
                    elif isinstance(data, dict):
                        # Try common fields
                        found = False
                        for field in ['data', 'profiles', 'results', 'data_list', 'list']:
                            res = data.get(field)
                            if isinstance(res, list):
                                all_profiles = res
                                found = True
                                break
                            if isinstance(res, dict) and 'data' in res and isinstance(res['data'], list):
                                all_profiles = res['data']
                                found = True
                                break
                        
                        if not found and ('id' in data or 'profile_id' in data) and ('name' in data or 'title' in data):
                            all_profiles = [data]
                    break
            except: continue
            
        return all_profiles if success else None

    def start_profile(self, profile_id, force_retry=True):
        """
        Starts a profile. Handles cases where API returns non-JSON 'GPM-Login' string
        or 'ALREADY_OPEN' JSON error.
        """
        # Quick pre-check: if server is not reachable, fail fast
        if not _server_reachable(self.base_url):
            print(f"[GPM] Server not reachable at {self.base_url}. Skipping start_profile.")
            return None

        endpoints = [
            f"/api/v3/profiles/start/{profile_id}",
            f"/api/v2/profiles/start/{profile_id}",
            f"/api/v1/profiles/start/{profile_id}", 
            f"/profiles/start/{profile_id}"
        ]
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to start profile via: {url}")
                response = requests.get(url, timeout=3)  # Fast timeout
                body = response.text
                print(f"Start profile status: {response.status_code}, body: {body}")
                
                if response.status_code == 200:
                    # 1. Try JSON decode first
                    try:
                        res_data = response.json()
                        if isinstance(res_data, dict):
                            # Handle ALREADY_OPEN or similar errors by force-closing
                            if res_data.get('success') is False:
                                msg = res_data.get('message', '').upper()
                                if ("ALREADY" in msg or "RUNNING" in msg or "OPEN" in msg) and force_retry:
                                    print(f"[GPM] Profile {profile_id} is already open. Force closing and retrying.... Force closing and retrying.... Force closing and retrying...")
                                    self.stop_profile(profile_id)
                                    time.sleep(2)
                                    # Retry without force_retry to avoid infinite loop
                                    return self.start_profile(profile_id, force_retry=False)
                            
                            # Standard success path
                            data_block = res_data.get('data', res_data)
                            debug = (data_block.get('selenium_remote_debug_address') or 
                                     data_block.get('remote_debugging_address') or 
                                     data_block.get('remote_debug_address') or
                                     data_block.get('selenium_debug_address') or
                                     data_block.get('debug_address'))
                            
                            if debug:
                                res_data['data'] = res_data.get('data', {})
                                res_data['data']['selenium_remote_debug_address'] = debug
                                if 'driver_path' in data_block:
                                    res_data['data']['driver_path'] = data_block['driver_path']
                                return {"success": True, "data": res_data['data']}
                            
                        # If JSON success but no debug, maybe it's just a status?
                        if res_data.get('success') is True:
                             # Continue to fallback search
                             pass
                        else:
                             continue # Try next endpoint

                    except Exception:
                        # 2. JSON failed. Check for 'GPM-Login' or other success strings
                        if "GPM-Login" in body or (len(body) < 50 and response.status_code == 200):
                            print(f"[GPM] API returned success. Waiting for profile metadata...")
                            # Fallback: Find in profile list to get debug address
                            for retry_p in range(10): 
                                time.sleep(1) # Faster polling
                                all_p = self.get_profiles()
                                if all_p:
                                    for p in all_p:
                                        p_id = p.get('id', p.get('profile_id', p.get('_id')))
                                        if p_id == profile_id:
                                            debug = (p.get('selenium_remote_debug_address') or 
                                                     p.get('remote_debugging_address') or 
                                                     p.get('remote_debug_address') or 
                                                     p.get('selenium_debug_address') or
                                                     p.get('debug_address'))
                                            
                                            port = p.get('port') or p.get('selenium_port') or p.get('debug_port')
                                            if not debug and port:
                                                debug = f"127.0.0.1:{port}"
                                                
                                            if debug:
                                                print(f"[GPM] Found debug address: {debug}")
                                                return {"success": True, "data": {"selenium_remote_debug_address": debug, "driver_path": p.get('driver_path') or p.get('browser_path', '')}}
                                            else:
                                                print(f"[GPM] Profile found ({p_id}) but no debug info yet (Attempt {retry_p+1}/10)")
                                                # If we are stuck with missing info, try force restarting once more if it's the first time
                                                if retry_p == 4 and force_retry:
                                                    print(f"[GPM] Still missing info. Force restarting...")
                                                    self.stop_profile(profile_id)
                                                    time.sleep(2)
                                                    return self.start_profile(profile_id, force_retry=False)
                                                break
                        
                        print(f"JSON decode failed for {endpoint} or fallback failed.")
                        continue
            except Exception as e:
                print(f"Error starting profile via {endpoint}: {e}")
        return None

    def stop_profile(self, profile_id):
        # Quick pre-check: if server is not reachable, skip all endpoints
        if not _server_reachable(self.base_url):
            print(f"[GPM] Server not reachable at {self.base_url}. Skipping stop_profile.")
            return {"success": True, "message": "Server not reachable - skip stop"}

        # Support multiple API versions for stopping nicks
        endpoints = [
            f"/api/v3/profiles/close/{profile_id}",
            f"/api/v2/profile/close/{profile_id}",
            f"/api/v2/profiles/close/{profile_id}",
            f"/api/v3/profiles/stop/{profile_id}",
            f"/api/v2/profiles/stop/{profile_id}",
            f"/api/v1/profiles/stop/{profile_id}",
            f"/profiles/stop/{profile_id}"
        ]
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to stop profile via: {url}")
                response = requests.get(url, timeout=3)  # Fast timeout
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('success') is True:
                            return {"success": True, "message": "Profile stopped"}
                        elif data.get('success') is False:
                            msg = str(data.get('message', '')).lower()
                            if 'not running' in msg or 'not open' in msg or 'already' in msg:
                                return {"success": True, "message": "Profile already stopped"}
                            # If it's false for another reason, we might want to try the next endpoint
                            print(f"Endpoint {endpoint} returned false: {data}")
                            continue
                    except:
                        # If it's not JSON but returned 200, it might have succeeded
                        if "GPM" in response.text or len(response.text) < 50:
                            return {"success": True, "message": "Profile stopped (non-JSON response)"}
            except Exception as e:
                print(f"Error on {endpoint}: {e}")
        return {"success": False, "message": "All stop endpoints failed"}

    def find_profile_by_name(self, name):
        profiles = self.get_profiles()
        for profile in profiles:
            p_name = profile.get('name', profile.get('title', '')).strip()
            if p_name.lower() == name.lower().strip():
                return profile
        return None
