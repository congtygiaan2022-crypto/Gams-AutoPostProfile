import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "system.db"

def init_db(db_path=None):
    if db_path is None:
        db_path = DB_PATH
    logger.info(f"Initializing database at {db_path}...")
    
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        
        # Table: fb_posts
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fb_posts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                video TEXT,
                status TEXT NOT NULL,
                link TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(link, video, timestamp)
            )
        ''')
        
        # Table: youtube_downloads
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS youtube_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                title TEXT,
                url TEXT NOT NULL,
                file_path TEXT,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url)
            )
        ''')
        
        # Table: tiktok_downloads
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tiktok_downloads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                title TEXT,
                url TEXT NOT NULL,
                file_path TEXT,
                status TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(url)
            )
        ''')
        
        # Table: comment_history
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS comment_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nick_link TEXT NOT NULL,
                video TEXT NOT NULL,
                post_link TEXT,
                timestamp TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(nick_link, video)
            )
        ''')
        
        # Indexes for fast querying
        logger.info("Creating indexes...")
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_posts_status_time ON fb_posts(status, timestamp);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_fb_posts_link ON fb_posts(link);')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_comment_history_link_video ON comment_history(nick_link, video);')
        
        conn.commit()
    
    logger.info("Database initialization complete.")

if __name__ == "__main__":
    init_db()
