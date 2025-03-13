import sqlite3

def setup_database():
    conn = sqlite3.connect('/data/grover.db')
    cur = conn.cursor()

    try:
        cur.executescript(
            """
            PRAGMA foreign_keys = ON;

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                care_areas JSON NOT NULL,
                journey_stage TEXT,
                category TEXT,
                format_type TEXT,
                business_category TEXT,
                consumer_need TEXT,
                tone_of_voice TEXT,
                target_audiences JSON NOT NULL,
                topic TEXT,
                project_notes TEXT,
                is_base_project BOOLEAN DEFAULT TRUE,
                is_duplicate BOOLEAN DEFAULT FALSE,
                original_project_id INTEGER,
                changes_note TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (original_project_id) 
                    REFERENCES projects(id)
                    ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS keywords (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                keyword TEXT NOT NULL,
                search_volume INTEGER,
                search_intent TEXT,
                keyword_difficulty INTEGER,
                is_primary BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) 
                    REFERENCES projects(id)
                    ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS base_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                article_outline TEXT,
                article_length INTEGER,
                article_sections INTEGER,
                article_title TEXT,
                article_content TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS community_articles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                base_article_id INTEGER NOT NULL,
                community_id INTEGER NOT NULL,
                article_title TEXT,
                article_content TEXT,
                article_schema TEXT,
                meta_title TEXT,
                meta_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE,
                FOREIGN KEY (base_article_id) REFERENCES base_articles(id) ON DELETE CASCADE
            );
            """
        )
        conn.commit()
        print("Database setup completed successfully")

    except sqlite3.Error as e:
        print(f"An error occurred: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    setup_database()