import requests
from typing import Dict, List, Optional, Any

class CommunityClient:
    """
    Client for interacting with the Senior Living DB API
    """
    def __init__(self, base_url: str = "http://community-db:8000"):
        """
        Initialize the client with the base URL of the Senior Living DB API
        
        Args:
            base_url (str): Base URL of the Senior Living DB API
                            Default is set to the Docker service name
        """
        self.base_url = base_url.rstrip('/')
        self.api_prefix = "/api/v1"
        
    def _make_request(self, endpoint: str) -> Dict[str, Any]:
        """
        Make a GET request to the API
        
        Args:
            endpoint (str): API endpoint to request
            
        Returns:
            Dict[str, Any]: Response data
            
        Raises:
            Exception: If the request fails
        """
        url = f"{self.base_url}{self.api_prefix}{endpoint}"
        response = requests.get(url)
        
        if response.status_code == 200:
            return response.json()
        else:
            # Handle error cases
            error_msg = f"API request failed with status {response.status_code}"
            try:
                error_data = response.json()
                if "detail" in error_data:
                    error_msg = f"{error_msg}: {error_data['detail']}"
            except:
                pass
            
            raise Exception(error_msg)
    
    def get_communities(self) -> List[Dict[str, Any]]:
        """
        Get all communities
        
        Returns:
            List[Dict[str, Any]]: List of communities
        """
        response = self._make_request("/communities")
        return response["communities"]
    
    def get_community(self, community_id: int) -> Dict[str, Any]:
        """
        Get details for a specific community
        
        Args:
            community_id (int): ID of the community
            
        Returns:
            Dict[str, Any]: Community details
        """
        return self._make_request(f"/communities/{community_id}")
    
    def get_care_areas(self, community_id: int) -> List[Dict[str, Any]]:
        """
        Get all care areas for a specific community
        
        Args:
            community_id (int): ID of the community
            
        Returns:
            List[Dict[str, Any]]: List of care areas
        """
        response = self._make_request(f"/communities/{community_id}/care_areas")
        return response["care_areas"]
    
    def get_aliases(self, community_id: int) -> List[Dict[str, Any]]:
        """
        Get all aliases for a specific community
        
        Args:
            community_id (int): ID of the community
            
        Returns:
            List[Dict[str, Any]]: List of aliases
        """
        response = self._make_request(f"/communities/{community_id}/aliases")
        return response["aliases"]
    
    def get_floor_plans(self, care_area_id: int) -> List[Dict[str, Any]]:
        """
        Get all floor plans for a specific care area
        
        Args:
            care_area_id (int): ID of the care area
            
        Returns:
            List[Dict[str, Any]]: List of floor plans
        """
        response = self._make_request(f"/care_areas/{care_area_id}/floor_plans")
        return response["floor_plans"]
    
    def get_saas(self, care_area_id: int) -> List[Dict[str, Any]]:
        """
        Get all services, activities, and amenities for a specific care area
        
        Args:
            care_area_id (int): ID of the care area
            
        Returns:
            List[Dict[str, Any]]: List of services, activities, and amenities
        """
        response = self._make_request(f"/care_areas/{care_area_id}/services")
        return response["services_activities_amenities"]
    
    def get_complete_community_data(self, community_id: int) -> Dict[str, Any]:
        """
        Get all data for a specific community (including care areas, floor plans, services, etc.)
        
        Args:
            community_id (int): ID of the community
            
        Returns:
            Dict[str, Any]: Complete community data
        """
        return self._make_request(f"/community_data/{community_id}")