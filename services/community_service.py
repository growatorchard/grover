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
            # Only add floor plans with actual data
            name = fp.get('name')
            bedrooms = fp.get('bedrooms')
            bathrooms = fp.get('bathrooms')
            sq_ft = fp.get('square_footage')
            
            if name:  # Only process if we have at least a name
                parts = [name]
                if bedrooms is not None or bathrooms is not None:
                    bed_bath = []
                    if bedrooms is not None:
                        bed_bath.append(f"{bedrooms} bed")
                    if bathrooms is not None:
                        bed_bath.append(f"{bathrooms} bath")
                    if bed_bath:
                        parts.append(": " + " / ".join(bed_bath))
                if sq_ft is not None:
                    parts.append(f", {sq_ft} sq ft")
                
                floor_plan_details.append("".join(parts))

        # Get services/activities/amenities
        saas = comm_manager.get_saas(care_area["id"])
        services = []
        amenities = []
        
        for saa in saas:
            saa = dict(saa)
            saa_type = saa.get("type", "").lower()
            description = saa.get("description")
            
            if description:  # Only add if description exists
                if saa_type == "service":
                    services.append(description)
                elif saa_type == "amenity":
                    amenities.append(description)
        
        # Format all amenities and services for list
        amenities_services_list = []
        if services:
            amenities_services_list.extend([f"**Service:** {s}" for s in services[:3]])
        if amenities:
            amenities_services_list.extend([f"**Amenity:** {a}" for a in amenities[:3]])
        
        # Build care area info dynamically, only including sections with data
        care_area_sections = [f"#### 🏡 **{care_area_name}**"]
        
        # Add starting price if available
        price = care_area.get('floor_plan_starting_at_price')
        billing_period = care_area.get('floor_plan_billing_period')
        if price is not None and billing_period:
            care_area_sections.append(f"- **Starting Price:** ${price} {billing_period}")
        
        # Add floor plans if available
        if floor_plan_details:
            floor_plan_text = ", ".join(floor_plan_details[:3])
            care_area_sections.append(f"- **Available Floor Plans:** {floor_plan_text}")
        
        # Add amenities and services if available
        if amenities_services_list:
            care_area_sections.append(f"- **Key Amenities & Services:** {', '.join(amenities_services_list[:5])}")
        
        # Add care area URL if available
        url = care_area.get('care_area_url')
        if url and url.strip():  # Check if URL exists and is not empty
            care_area_sections.append(f"- **Care Area URL:** [{care_area_name}]({url})")
        
        # Only add the care area if we have more than just the title
        if len(care_area_sections) > 1:
            care_area_info = "\n".join(care_area_sections) + "\n"
            detailed_care_areas.append(care_area_info)
            print(f"Added formatted care area: {care_area_name}")
        else:
            print(f"Skipped care area '{care_area_name}' due to lack of data")

    # Join all care area details with a newline
    return "\n".join(detailed_care_areas)