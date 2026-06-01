import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger("db_helper")
logger.setLevel(logging.INFO)
if not logger.handlers:
    # Set up console logging
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    logger.addHandler(ch)

DB_PATH = "system.db"

class DatabaseHelper:
    """ Singleton pattern or simple wrapper for SQLite thread-safe access """
    
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def get_connection(self):
        # Using timeout ensures thread-safety under moderate concurrency
        return sqlite3.connect(self.db_path, timeout=10.0)

    def execute_query(self, query, params=(), fetch=False, fetch_all=True):
        """ Standard method for SELECT queries. """
        try:
            with self.get_connection() as conn:
                conn.row_factory = sqlite3.Row  # Returns dict-like objects
                cursor = conn.cursor()
                cursor.execute(query, params)
                if fetch:
                    if fetch_all:
                        return [dict(row) for row in cursor.fetchall()]
                    else:
                        row = cursor.fetchone()
                        return dict(row) if row else None
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            logger.error(f"DB Error on query {query}: {e}")
            return None

    def executemany(self, query, params_list):
        """ Batch insert for efficiency """
        if not params_list:
             return 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.executemany(query, params_list)
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            logger.error(f"DB Error on executemany {query}: {e}")
            return 0
            
    # ------ Facebook Posts (logs.json replacement) ------
    
    def add_fb_post_log(self, timestamp, video, status, link):
        """ Add a log entry, prevent duplicates via UNIQUE constraint or ignore """
        query = """
            INSERT OR IGNORE INTO fb_posts (timestamp, video, status, link)
            VALUES (?, ?, ?, ?)
        """
        # Note: If we want to strictly enforce duplicates, we rely on the schema's UNIQUE(link, video, timestamp).
        self.execute_query(query, (timestamp, video, status, link))
        
    def get_fb_logs(self, link):
        """ Get logs for a specific Nick link """
        query = "SELECT * FROM fb_posts WHERE link = ? ORDER BY timestamp DESC"
        return self.execute_query(query, (link,), fetch=True, fetch_all=True)
        
    def get_daily_success_count(self, link, date_str):
        """ Returns the number of successful uploaded videos today """
        query = """
            SELECT COUNT(*) as cnt FROM fb_posts 
            WHERE link = ? AND timestamp LIKE ? AND status IN ("Success", "Uploaded", "Uploaded (No Comment)")
        """
        res = self.execute_query(query, (link, f"{date_str}%"), fetch=True, fetch_all=False)
        return res['cnt'] if res else 0

    # ------ TikTok Downloads ------
    def add_tiktok_download(self, timestamp, title, url, file_path, status):
        query = """
            INSERT OR IGNORE INTO tiktok_downloads (timestamp, title, url, file_path, status)
            VALUES (?, ?, ?, ?, ?)
        """
        self.execute_query(query, (timestamp, title, url, file_path, status))
        
    def check_tiktok_exists(self, url):
        query = "SELECT 1 FROM tiktok_downloads WHERE url = ?"
        res = self.execute_query(query, (url,), fetch=True, fetch_all=False)
        return True if res else False
        
    # ------ YouTube Downloads ------
    def add_youtube_download(self, timestamp, title, url, file_path, status):
        query = """
            INSERT OR IGNORE INTO youtube_downloads (timestamp, title, url, file_path, status)
            VALUES (?, ?, ?, ?, ?)
        """
        self.execute_query(query, (timestamp, title, url, file_path, status))
        
    def check_youtube_exists(self, url):
        query = "SELECT 1 FROM youtube_downloads WHERE url = ?"
        res = self.execute_query(query, (url,), fetch=True, fetch_all=False)
        return True if res else False

    # ------ Comment History ------
    def add_comment_history(self, nick_link, video, post_link, timestamp=None):
        if timestamp is None:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        query = """
            INSERT OR IGNORE INTO comment_history (nick_link, video, post_link, timestamp)
            VALUES (?, ?, ?, ?)
        """
        self.execute_query(query, (nick_link, video, post_link, timestamp))

    def has_commented(self, nick_link, video):
        query = "SELECT 1 FROM comment_history WHERE nick_link = ? AND video = ?"
        res = self.execute_query(query, (nick_link, video), fetch=True, fetch_all=False)
        return True if res else False
        
    def get_comment_history(self, nick_link):
        query = "SELECT * FROM comment_history WHERE nick_link = ? ORDER BY timestamp DESC"
        return self.execute_query(query, (nick_link,), fetch=True, fetch_all=True)

# Global Instance
db = DatabaseHelper()
