import json
import os
from db_helper import db

class Database:
    def __init__(self, file_path="database.json"):
        self.file_path = file_path
        self.data = self.load()

    def save_logs(self):
        pass # Deprecated in favor of db_helper

    def load(self):
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
                # MIGRATION: Migration logic for logs removed, now handled by migrate_all.py

                
                # ... existing migrations ...
                if 'comment_template' not in data:
                    data['comment_template'] = ""
                if 'auto_delete_videos' not in data:
                    data['auto_delete_videos'] = False
                if 'nicks' in data:
                    for i, page in enumerate(data['nicks']):
                        if 'min_videos' not in page:
                            page['min_videos'] = 1
                        if 'max_videos' not in page:
                            page['max_videos'] = 10
                        if 'name' not in page:
                            page['name'] = ""
                        # Ensure STT is present and correct
                        page['stt'] = i + 1
                # Scheduling settings
                if 'loop_mode' not in data:
                    data['loop_mode'] = 'once'
                if 'loop_count' not in data:
                    data['loop_count'] = 1
                if 'rest_min' not in data:
                    data['rest_min'] = 30
                if 'rest_max' not in data:
                    data['rest_max'] = 60
                if 'time_start' not in data:
                    data['time_start'] = '00:00'
                if 'time_end' not in data:
                    data['time_end'] = '23:59'
                # Theme setting
                if 'theme' not in data:
                    data['theme'] = 'dark'
                
                if 'browsers' not in data:
                    data['browsers'] = []
                
                if 'skip_commented' not in data:
                    data['skip_commented'] = True
                
                # Check for both default Slots
                has_gem = any(b['id'] == 'gemlogin_default' for b in data['browsers'])
                has_gpm = any(b['id'] == 'gpmlogin_default' for b in data['browsers'])
                
                if not has_gem:
                    data['browsers'].append({
                        "id": "gemlogin_default",
                        "name": "GemLogin",
                        "type": "gemlogin",
                        "api_url": "http://localhost:54321"
                    })
                if not has_gpm:
                    data['browsers'].insert(1 if has_gem else 0, {
                        "id": "gpmlogin_default",
                        "name": "GPM Login",
                        "type": "gpmlogin",
                        "api_url": "http://localhost:5555"
                    })
                
                if 'run_mode' not in data:
                    data['run_mode'] = 'post_and_comment'
                
                if 'max_parallel_workers' not in data:
                    data['max_parallel_workers'] = 1
                
                if 'comment_strategies' not in data:
                    data['comment_strategies'] = {
                        "home_scroll": True,
                        "feed_grid": True,
                        "published_panel": True,
                        "published_inline": True,
                        "insight_overview": True,
                        "insight_content": True
                    }
                
                if 'browsers' not in data:
                    data['browsers'] = [
                        {
                            "id": "gemlogin_default",
                            "name": "GemLogin Default",
                            "type": "gemlogin",
                            "api_url": "http://localhost:1010"
                        }
                    ]
                
                if 'groups' not in data:
                    data['groups'] = []
                
                for page in data.get('nicks', []):
                    if 'group_id' not in page:
                        page['group_id'] = ""
                    if 'browser_id' not in page:
                        page['browser_id'] = "gemlogin_default"
                    if 'profile_id' not in page:
                        page['profile_id'] = ""
                    if 'profile_name' not in page:
                        page['profile_name'] = ""
                    if 'enabled' not in page:
                        page['enabled'] = True
                
                return data

        return {"nicks": [], "comment_template": "", "auto_delete_videos": False, 
                "loop_mode": "once", "loop_count": 1, "rest_min": 30, "rest_max": 60,
                "time_start": "00:00", "time_end": "23:59", "theme": "dark", "run_mode": "post_and_comment",
                "max_parallel_workers": 1, "groups": [],
                "browsers": [
                    {
                        "id": "gemlogin_default",
                        "name": "GemLogin",
                        "type": "gemlogin",
                        "api_url": "http://localhost:54321"
                    },
                    {
                        "id": "gpmlogin_default",
                        "name": "GPM Login",
                        "type": "gpmlogin",
                        "api_url": "http://localhost:5555"
                    }
                ],
                "global_folders": [], "global_min_videos": 1, "global_max_videos": 1}

    def reload(self):
        """ Reload all data from disk to ensure we have the latest config """
        self.data = self.load()
        return self.data

    def save(self):
        # Update STT before saving to ensure sequence is correct
        if 'nicks' in self.data:
            for i, page in enumerate(self.data['nicks']):
                page['stt'] = i + 1
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=4, ensure_ascii=False)

    def set_comment_template(self, text):
        self.data['comment_template'] = text
        self.save()

    def get_comment_template(self):
        return self.data.get('comment_template', "")

    def set_auto_delete_videos(self, enabled):
        self.data['auto_delete_videos'] = enabled
        self.save()

    def get_auto_delete_videos(self):
        return self.data.get('auto_delete_videos', False)

    def get_scheduling_config(self):
        return {
            'loop_mode': self.data.get('loop_mode', 'once'),
            'loop_count': self.data.get('loop_count', 1),
            'rest_min': self.data.get('rest_min', 30),
            'rest_max': self.data.get('rest_max', 60),
            'time_start': self.data.get('time_start', '00:00'),
            'time_end': self.data.get('time_end', '23:59')
        }

    def set_scheduling_config(self, loop_mode, loop_count, rest_min, rest_max, time_start, time_end):
        self.data['loop_mode'] = loop_mode
        self.data['loop_count'] = loop_count
        self.data['rest_min'] = rest_min
        self.data['rest_max'] = rest_max
        self.data['time_start'] = time_start
        self.data['time_end'] = time_end
        self.save()

    def get_theme(self):
        return self.data.get('theme', 'dark')

    def set_theme(self, theme):
        self.data['theme'] = theme
        self.save()

    def get_run_mode(self):
        return self.data.get('run_mode', 'post_and_comment')

    def set_run_mode(self, mode):
        self.data['run_mode'] = mode
        self.save()

    def get_max_parallel_workers(self):
        return self.data.get('max_parallel_workers', 1)

    def set_max_parallel_workers(self, count):
        self.data['max_parallel_workers'] = count
        self.save()

    def get_skip_commented(self):
        return self.data.get('skip_commented', True)

    def set_skip_commented(self, val):
        self.data['skip_commented'] = val
        self.save()

    def add_nick(self, link):
        # No 'logs' field needed anymore
        new_stt = len(self.data['nicks']) + 1
        self.data['nicks'].append({
            "stt": new_stt,
            "link": link, 
            "name": "", 
            "folders": [], 
            "min_videos": 1, 
            "max_videos": 10,
            "browser_id": "gemlogin_default",
            "profile_id": "",
            "profile_name": "",
            "group_id": "",
            "enabled": True
        })
        self.save()

    def update_nick_name(self, index, name):
        if 0 <= index < len(self.data['nicks']):
            self.data['nicks'][index]['name'] = name
            self.save()

    def update_video_limits(self, page_index, min_videos, max_videos):
        if 0 <= page_index < len(self.data['nicks']):
            self.data['nicks'][page_index]['min_videos'] = min_videos
            self.data['nicks'][page_index]['max_videos'] = max_videos
            self.save()

    def add_log(self, page_index, video_name, status, post_link=""):
        if 0 <= page_index < len(self.data['nicks']):
            import datetime
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            link = self.data['nicks'][page_index]['link']
            
            db.add_fb_post_log(timestamp, video_name, status, link)

    def log_upload(self, nick_link, video_name, status, post_link=""):
        """Log an upload by page link (for use in page_worker subprocesses)."""
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.add_fb_post_log(timestamp, video_name, status, nick_link)

    def get_logs(self, link):
        return db.get_fb_logs(link)

    def remove_nick(self, index):
        if 0 <= index < len(self.data['nicks']):
            self.data['nicks'].pop(index)
            self.save()

    def add_folder(self, page_index, folder_path):
        if 0 <= page_index < len(self.data['nicks']):
            if folder_path not in self.data['nicks'][page_index]['folders']:
                self.data['nicks'][page_index]['folders'].append(folder_path)
                self.save()

    def remove_folder(self, page_index, folder_index):
        if 0 <= page_index < len(self.data['nicks']):
            if 0 <= folder_index < len(self.data['nicks'][page_index]['folders']):
                self.data['nicks'][page_index]['folders'].pop(folder_index)
                self.save()

    def update_link(self, index, new_link):
        if 0 <= index < len(self.data['nicks']):
            self.data['nicks'][index]['link'] = new_link
            self.save()

    def clear_all(self):
        self.data['nicks'] = []
        self.save()

    def get_nicks(self):
        return self.data['nicks']

    def get_global_folders(self):
        return self.data.get('global_folders', [])

    def add_global_folder(self, folder_path):
        if 'global_folders' not in self.data:
            self.data['global_folders'] = []
        if folder_path not in self.data['global_folders']:
            self.data['global_folders'].append(folder_path)
            self.save()

    def remove_global_folder(self, index):
        if 'global_folders' in self.data and 0 <= index < len(self.data['global_folders']):
            self.data['global_folders'].pop(index)
            self.save()

    def get_comment_strategies(self):
        return self.data.get('comment_strategies', {
            "home_scroll": True,
            "feed_grid": True,
            "published_panel": True,
            "published_inline": True,
            "insight_overview": True,
            "insight_content": True
        })

    def set_comment_strategies(self, strategies):
        self.data['comment_strategies'] = strategies
        self.save()

    # --- Comment History (New Feature) ---
    def load_comment_history(self):
        pass # Deprecated in favor of db_helper

    def save_comment_history(self):
        pass # Deprecated in favor of db_helper

    def add_comment_history(self, nick_link, video_name, post_link):
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.add_comment_history(nick_link, video_name, post_link, timestamp)

    def has_commented(self, nick_link, video_name):
        return db.has_commented(nick_link, video_name)

    def get_comment_history(self, nick_link):
        return db.get_comment_history(nick_link)

    def get_video_count(self, folder_path):
        """ Count valid videos in a folder """
        if not os.path.exists(folder_path):
            return 0
        try:
            valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
            return len([f for f in os.listdir(folder_path) if f.lower().endswith(valid_extensions)])
        except:
            return 0

    def auto_map_folders(self, base_dir=None):
        """ 
        Automatically find folders in base_dir that match Nick Cá Nhân names.
        Matches if folder name contains page name or vice versa.
        """
        if not base_dir:
            # Default to the common path seen in database.json
            base_dir = r"G:\Documentss\Antigravity_Gams_Youtubedownload\downloads"
        
        if not os.path.exists(base_dir):
            return 0, []

        try:
            subdirs = [os.path.join(base_dir, d) for d in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, d))]
        except:
            return 0, []

        mapped_count = 0
        results = []

        # Common synonyms for better matching
        synonyms = {
            'film': 'phim',
            'phim': 'film',
            'kids': 'tre em',
            'music': 'nhac',
            'animal': 'dong vat'
        }

        for i, page in enumerate(self.data.get('nicks', [])):
            name = page.get('name', '').strip().lower()
            if not name: continue
            
            # If already has folders, skip
            if page.get('folders'): continue
            
            # Get words for the page name
            page_words = set(name.replace('-', ' ').replace('+', ' ').split())
            
            best_match = None
            max_overlap = 0

            for subdir in subdirs:
                dirname = os.path.basename(subdir).lower().replace('short', '').strip()
                dir_words = set(dirname.replace('-', ' ').replace('+', ' ').split())
                
                # Check for direct containment first (very common)
                if name in dirname or dirname in name:
                    best_match = subdir
                    break
                
                # Word overlap logic
                overlap = len(page_words.intersection(dir_words))
                
                # Synonym check
                for p_word in page_words:
                    if p_word in synonyms and synonyms[p_word] in dir_words:
                        overlap += 1
                
                if overlap > max_overlap and overlap >= 1:
                    max_overlap = overlap
                    best_match = subdir
            
            if best_match:
                if best_match not in page['folders']:
                    page['folders'].append(best_match)
                    mapped_count += 1
                    results.append(f"Mapped '{page.get('name')}' -> '{os.path.basename(best_match)}'")
        
        if mapped_count > 0:
            self.save()
        
        return mapped_count, results

    def select_video(self, page_index, folders, min_videos, max_videos):
        if not folders: return None
        
        # Check daily limit
        import datetime
        today = datetime.datetime.now().strftime("%Y-%m-%d")
        nick_link = self.data['nicks'][page_index]['link']
        today_success = db.get_daily_success_count(nick_link, today)
        if today_success >= int(max_videos):
            return None # Met daily limit

        
        # Find available videos
        valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        all_videos = []
        for folder in folders:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(valid_extensions):
                        full_path = os.path.join(folder, f)
                        all_videos.append(full_path)
        
        if not all_videos: return None
        
        # Pick random
        import random
        return random.choice(all_videos)

    def select_video_for_comment(self, page_index, folders, skip_existing=True):
        if not folders: return None
        
        nick_link = self.data['nicks'][page_index]['link']
        valid_extensions = ('.mp4', '.mov', '.avi', '.mkv', '.webm')
        all_videos = []
        
        for folder in folders:
            if os.path.exists(folder):
                for f in os.listdir(folder):
                    if f.lower().endswith(valid_extensions):
                        full_path = os.path.join(folder, f)
                        
                        # Filter if skip enabled
                        if skip_existing:
                            if self.has_commented(nick_link, f):
                                continue
                        
                        all_videos.append(full_path)
        
        if not all_videos: return None
        
        # Pick random valid video
        import random
        return random.choice(all_videos)
    def get_global_video_limits(self):
        return self.data.get('global_min_videos', 1), self.data.get('global_max_videos', 1)

    def set_global_video_limits(self, min_val, max_val):
        self.data['global_min_videos'] = min_val
        self.data['global_max_videos'] = max_val
        self.save()

    # --- Browser Management ---
    def get_browsers(self):
        return self.data.get('browsers', [])

    def add_browser(self, name, b_type, api_url):
        import uuid
        new_id = str(uuid.uuid4())
        self.data['browsers'].append({
            "id": new_id,
            "name": name,
            "type": b_type,
            "api_url": api_url
        })
        self.save()
        return new_id

    def update_browser(self, b_id, name, b_type, api_url):
        for b in self.data.get('browsers', []):
            if b['id'] == b_id:
                b['name'] = name
                b['type'] = b_type
                b['api_url'] = api_url
                self.save()
                return True
        return False

    def remove_browser(self, b_id):
        # Don't allow removing the last browser or a default one if needed, 
        # but here we'll just filter it out.
        self.data['browsers'] = [b for b in self.data.get('browsers', []) if b['id'] != b_id]
        # Re-assign pages that used this browser to the first available browser or default
        default_id = self.data['browsers'][0]['id'] if self.data['browsers'] else "gemlogin_default"
        for page in self.data.get('nicks', []):
            if page.get('browser_id') == b_id:
                page['browser_id'] = default_id
        self.save()

    def update_page_browser(self, page_index, browser_id):
        if 0 <= page_index < len(self.data['nicks']):
            self.data['nicks'][page_index]['browser_id'] = browser_id
            self.save()

    def update_page_profile(self, page_index, profile_id, profile_name):
        if 0 <= page_index < len(self.data['nicks']):
            self.data['nicks'][page_index]['profile_id'] = profile_id
            self.data['nicks'][page_index]['profile_name'] = profile_name
            self.save()

    def update_page_enabled(self, page_index, enabled):
        if 0 <= page_index < len(self.data['nicks']):
            self.data['nicks'][page_index]['enabled'] = enabled
            self.save()

    def get_browser_by_id(self, b_id):
        for b in self.data.get('browsers', []):
            if b['id'] == b_id:
                return b
        return None

    # --- Group Management ---
    def get_groups(self):
        return self.data.get('groups', [])

    def add_group(self, name, browser_id=None, profile_id="", profile_name=""):
        import uuid
        new_id = str(uuid.uuid4())
        self.data['groups'].append({
            "id": new_id,
            "name": name,
            "browser_id": browser_id or "gemlogin_default",
            "profile_id": profile_id,
            "profile_name": profile_name
        })
        self.save()
        return new_id

    def update_group(self, group_id, name, browser_id, profile_id="", profile_name=""):
        updated = False
        for g in self.data.get('groups', []):
            if g['id'] == group_id:
                g['name'] = name
                g['browser_id'] = browser_id
                g['profile_id'] = profile_id
                g['profile_name'] = profile_name
                updated = True
                break
        
        if updated:
            # Sync all nicks in this group to the new settings
            for page in self.data.get('nicks', []):
                if page.get('group_id') == group_id:
                    page['browser_id'] = browser_id
                    page['profile_id'] = profile_id
                    page['profile_name'] = profile_name
            self.save()
        return updated

    def remove_group(self, group_id):
        self.data['groups'] = [g for g in self.data.get('groups', []) if g['id'] != group_id]
        # Clear group_id for pages
        for page in self.data.get('nicks', []):
            if page.get('group_id') == group_id:
                page['group_id'] = ""
        self.save()

    def update_page_group(self, page_index, group_id):
        if 0 <= page_index < len(self.data['nicks']):
            page = self.data['nicks'][page_index]
            page['group_id'] = group_id
            
            # Sync browser and profile if group has one
            if group_id:
                for g in self.data.get('groups', []):
                    if g['id'] == group_id:
                        page['browser_id'] = g.get('browser_id', page.get('browser_id'))
                        page['profile_id'] = g.get('profile_id', page.get('profile_id'))
                        page['profile_name'] = g.get('profile_name', page.get('profile_name'))
                        break
            self.save()

    def update_pages_group_bulk(self, page_indices, group_id):
        """ Assign multiple pages to a group and sync browsers/profiles """
        groups = self.get_groups()
        target_group = next((g for g in groups if g['id'] == group_id), None)
        
        for idx in page_indices:
            if 0 <= idx < len(self.data['nicks']):
                page = self.data['nicks'][idx]
                page['group_id'] = group_id
                if target_group:
                    page['browser_id'] = target_group.get('browser_id', page.get('browser_id'))
                    page['profile_id'] = target_group.get('profile_id', page.get('profile_id'))
                    page['profile_name'] = target_group.get('profile_name', page.get('profile_name'))
        self.save()

    def resolve_page_browser_id(self, page_index):
        """ Returns the browser_id for a page, using group setting if available """
        if 0 <= page_index < len(self.data['nicks']):
            page = self.data['nicks'][page_index]
            g_id = page.get('group_id')
            if g_id:
                for g in self.data.get('groups', []):
                    if g['id'] == g_id:
                        return g.get('browser_id') or page.get('browser_id', 'gemlogin_default')
            return page.get('browser_id', 'gemlogin_default')
        return "gemlogin_default"
