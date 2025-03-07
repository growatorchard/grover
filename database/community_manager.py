import sqlite3

class CommunityManager:
    def __init__(self):
        self.db_path = "senior_living.db"
        # Just store the path, don't maintain open connections or cursors at the class level
    
    def get_connection(self):
        # Create a new connection each time
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_communities(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM communities ORDER BY community_name")
            return cursor.fetchall()

    def get_community(self, community_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM communities WHERE id = ?", (community_id,))
            return cursor.fetchone()

    def get_care_areas(self, community_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM care_areas WHERE community_id = ?", (community_id,))
            return cursor.fetchall()

    def get_aliases(self, community_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM community_aliases WHERE community_id = ?", (community_id,))
            return cursor.fetchall()

    def get_floor_plans(self, care_area_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM floor_plans WHERE care_area_id = ?", (care_area_id,))
            return cursor.fetchall()

    def get_saas(self, care_area_id):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM services_activities_amenities WHERE care_area_id = ?", (care_area_id,))
            return cursor.fetchall()