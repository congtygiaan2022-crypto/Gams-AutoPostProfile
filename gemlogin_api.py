import requests
import time

def _server_reachable(base_url, timeout=2):
    """Quick check: is the browser API server reachable at all?"""
    try:
        requests.get(base_url, timeout=timeout)
        return True
    except Exception:
        return False

class GemLoginAPI:
    def __init__(self, base_url="http://localhost:1010"):
        self.base_url = base_url

    def get_profiles(self):
        # GemLogin / GenLogin standard endpoints
        endpoints = ["/profiles", "/api/profiles", "/api/v1/profiles", "/api/v2/profiles", "/api/v3/profiles"]
        success = False
        all_profiles = []
        
        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    success = True
                    if isinstance(data, list):
                        all_profiles = data
                    elif isinstance(data, dict):
                        all_profiles = data.get('data', [])
                    break
            except: continue
            
        return all_profiles if success else None

    def start_profile(self, profile_id):
        # Possible patterns: /profiles/start/{id}, /api/profiles/start/{id}, /api/v1/profiles/start/{id}
        endpoints = [f"/profiles/start/{profile_id}", f"/api/profiles/start/{profile_id}", f"/api/v1/profiles/start/{profile_id}"]

        # Quick pre-check: if server not reachable, fail fast
        if not _server_reachable(self.base_url):
            print(f"[GEM] Server not reachable at {self.base_url}. Skipping start_profile.")
            return None

        for attempt in range(3):
            for endpoint in endpoints:
                url = f"{self.base_url}{endpoint}"
                try:
                    print(f"Trying to start profile (Attempt {attempt+1}) via: {url}")
                    response = requests.get(url, timeout=3)  # Fast timeout
                    if response.status_code == 200:
                        res_data = response.json()
                        if isinstance(res_data, dict):
                            # Special case: success is False but status is 200 (Not Ready)
                            if res_data.get('success') is False:
                                msg = res_data.get('message', '').lower()
                                if 'not ready' in msg or 'running' in msg:
                                    print(f"GemLogin: Profile {profile_id} is {msg}. Attempt {attempt+1}/3...")
                                    if attempt == 0:
                                        print(f"GemLogin: Force closing profile {profile_id} before retry...")
                                        self.stop_profile(profile_id)
                                    time.sleep(5)
                                    break # Try next endpoint or next attempt
                                
                                print(f"GemLogin API Error: {res_data.get('message')}")
                                continue # Try next endpoint
                                
                            if res_data.get('success') or res_data.get('status') == 'success' or 'data' in res_data:
                                if 'success' not in res_data: res_data['success'] = True
                                if 'data' not in res_data: res_data['data'] = res_data
                                return res_data
                        return {"success": True, "data": res_data}
                except Exception as e:
                    print(f"Error starting profile via {endpoint}: {e}")
            
            if attempt < 2:
                time.sleep(2) # Gap between full endpoint cycles
                
        return None

    def stop_profile(self, profile_id):
        endpoints = [
            f"/api/profiles/close/{profile_id}",
            f"/api/v1/profiles/close/{profile_id}",
            f"/api/v1/profile/close/{profile_id}",
            f"/api/profiles/stop/{profile_id}",
            f"/profiles/stop/{profile_id}"
        ]

        # Quick pre-check: if server not reachable, skip
        if not _server_reachable(self.base_url):
            print(f"[GEM] Server not reachable at {self.base_url}. Skipping stop_profile.")
            return {"success": True, "message": "Server not reachable - skip stop"}

        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                print(f"Trying to stop profile via: {url}")
                response = requests.get(url, timeout=3)  # Fast timeout
                print(f"Stop profile status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        data = response.json()
                        if data.get('success') is True or data.get('status') == 'success':
                            return {"success": True, "message": "Profile stopped"}
                        elif data.get('success') is False:
                            msg = str(data.get('message', '')).lower()
                            if 'not running' in msg or 'not open' in msg or 'already' in msg:
                                return {"success": True, "message": "Profile already stopped"}
                            # Try next endpoint if this one explicitly failed
                            print(f"Endpoint {endpoint} returned false: {data}")
                            continue
                        return data
                    except:
                        return {"success": True, "message": "Profile stopped (non-JSON)"}
            except Exception as e:
                print(f"Error on {endpoint}: {e}")
        return {"success": False, "message": "All stop endpoints failed"}

    def find_profile_by_name(self, name):
        profiles = self.get_profiles()
        print(f"Debugging: Looking for profile '{name}'")
        print(f"Total profiles found: {len(profiles)}")
        for profile in profiles:
            p_name = profile.get('name', '').strip()
            print(f"Checking candidate: '{p_name}'")
            if p_name.lower() == name.lower().strip():
                return profile
        return None
