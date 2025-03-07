def get_care_area_details(comm_manager, community_id, selected_care_areas):
    """Get detailed information about care areas and their related data.
    
    Args:
        comm_manager: Community manager instance
        community_id: ID of the community
        selected_care_areas: List of care area names to include (e.g. ["Independent Living", "Assisted Living"])
    """
    print(f"Getting detailed care area information for community ID: {community_id}")
    care_areas = comm_manager.get_care_areas(community_id)
    detailed_care_areas = []

    # If no specific care areas are selected, include all of them
    if not selected_care_areas:
        selected_care_areas = []
        print("No care areas selected, will include all")

    # Normalize the selected care areas for case-insensitive comparison
    normalized_selected_areas = [area.strip().lower() for area in selected_care_areas]
    print(f"Selected care areas: {selected_care_areas}")
    print(f"Normalized selected areas: {normalized_selected_areas}")
    
    for care_area in care_areas:
        care_area = dict(care_area)
        care_area_name = care_area.get('care_area', 'N/A')
        print(f"Examining care area: {care_area_name}")
        
        # Only include care areas that match the selected ones, or include all if none selected
        if normalized_selected_areas and care_area_name.lower() not in normalized_selected_areas:
            print(f"Skipping care area '{care_area_name}' as it's not in the selected list")
            continue
        
        print(f"Processing care area: {care_area_name}")
        
        # Get floor plan details
        floor_plans = comm_manager.get_floor_plans(care_area["id"])
        floor_plan_details = []
        for fp in floor_plans:
            fp = dict(fp)
            floor_plan_details.append(
                f"  - {fp.get('name', 'N/A')}: {fp.get('bedrooms', 'N/A')} bed / {fp.get('bathrooms', 'N/A')} bath, "
                f"{fp.get('square_footage', 'N/A')} sq ft"
            )

        # Get services/activities/amenities
        saas = comm_manager.get_saas(care_area["id"])
        services = []
        amenities = []
        
        for saa in saas:
            saa = dict(saa)
            saa_type = saa.get("type", "Other").lower()
            description = saa.get("description", "N/A")
            
            if saa_type == "service":
                services.append(description)
            elif saa_type == "amenity":
                amenities.append(description)
        
        # Format key amenities and services highlights - limit to first 5 of each
        key_services = services[:5] if services else ["None listed"]
        key_amenities = amenities[:5] if amenities else ["None listed"]
        
        # Format all amenities and services for list
        amenities_services_list = []
        if services:
            amenities_services_list.extend([f"**Service:** {s}" for s in services[:3]])
        if amenities:
            amenities_services_list.extend([f"**Amenity:** {a}" for a in amenities[:3]])
        
        # Create floor plan text
        if floor_plan_details:
            floor_plan_text = ", ".join([fp.strip().replace("  - ", "") for fp in floor_plan_details[:3]])
        else:
            floor_plan_text = "None listed"

        # New markdown-formatted care area info
        care_area_info = f"""
#### 🏡 **{care_area_name}**  
- **Starting Price:** ${care_area.get('floor_plan_starting_at_price', 'N/A')} {care_area.get('floor_plan_billing_period', 'N/A')}  
- **Available Floor Plans:** {floor_plan_text}  
- **Key Amenities & Services:** {', '.join(amenities_services_list[:5]) if amenities_services_list else 'None listed'}  
- **More Info:** [{care_area_name}]({care_area.get('care_area_url', '#')})  
"""

        detailed_care_areas.append(care_area_info)
        print(f"Added formatted care area: {care_area_name}")

    # Join all care area details with a newline
    return "\n".join(detailed_care_areas)