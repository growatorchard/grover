import sqlite3

class CommunityManager:
    def __init__(self):
        self.conn = sqlite3.connect("senior_living.db", check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def get_communities(self):
        self.cursor.execute("SELECT * FROM communities ORDER BY community_name")
        return self.cursor.fetchall()

    def get_community(self, community_id):
        self.cursor.execute("SELECT * FROM communities WHERE id = ?", (community_id,))
        return self.cursor.fetchone()

    def get_care_areas(self, community_id):
        self.cursor.execute("SELECT * FROM care_areas WHERE community_id = ?", (community_id,))
        return self.cursor.fetchall()

    def get_aliases(self, community_id):
        self.cursor.execute("SELECT * FROM community_aliases WHERE community_id = ?", (community_id,))
        return self.cursor.fetchall()

    def get_floor_plans(self, care_area_id):
        self.cursor.execute("SELECT * FROM floor_plans WHERE care_area_id = ?", (care_area_id,))
        return self.cursor.fetchall()

    def get_saas(self, care_area_id):
        self.cursor.execute("SELECT * FROM services_activities_amenities WHERE care_area_id = ?", (care_area_id,))
        return self.cursor.fetchall() 