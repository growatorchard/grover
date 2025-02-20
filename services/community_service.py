import json

def get_care_area_details(comm_manager, community_id):
    """Get detailed information about care areas and their related data."""
    care_areas = comm_manager.get_care_areas(community_id)
    detailed_care_areas = []
    for care_area in care_areas:
        care_area = dict(care_area)
        floor_plans = comm_manager.get_floor_plans(care_area["id"])
        floor_plan_details = []
        for fp in floor_plans:
            fp = dict(fp)
            floor_plan_details.append(
                f"- {fp.get('name', 'N/A')}: {fp.get('bedrooms', 'N/A')} bed/{fp.get('bathrooms', 'N/A')} bath, {fp.get('square_footage', 'N/A')} sq ft"
            )
        saas = comm_manager.get_saas(care_area["id"])
        saa_by_type = {}
        for saa in saas:
            saa = dict(saa)
            saa_type = saa.get("type", "Other")
            if saa_type not in saa_by_type:
                saa_by_type[saa_type] = []
            saa_by_type[saa_type].append(saa.get("description", ""))
        care_area_info = f"""
Care Area: {care_area.get('care_area', 'N/A')}
Description: {care_area.get('general_floor_plan_description', 'N/A')}
Starting Price: ${care_area.get('floor_plan_starting_at_price', 'N/A')} {care_area.get('floor_plan_billing_period', 'N/A')}
Care Area URL: {care_area.get('care_area_url', 'N/A')}

Available Floor Plans:
{chr(10).join(floor_plan_details) if floor_plan_details else 'None'}
"""
        if saa_by_type:
            care_area_info += "\nServices/Activities/Amenities:\n"
            for saa_type, descriptions in saa_by_type.items():
                care_area_info += f"{saa_type.title()}:\n"
                care_area_info += "\n".join(f"- {desc}" for desc in descriptions) + "\n"
        detailed_care_areas.append(care_area_info)
    return "\n\n".join(detailed_care_areas) 