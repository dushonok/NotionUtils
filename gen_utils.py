
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'ConfigKeeper')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'NotionAutomator')))

from notion_config import SEASON_EVERGREEN_ID
from notion_api import get_template_colors
from utils import expand_and_shuffle

def report_progress(i, url_count, callback):
    callback(f"Processed {i+1}/{url_count}")

def reset_report_progress(url_count, callback):
    report_progress(-1, url_count, callback)

def dedup_and_trim(arr, callback=print):
    seen = set()
    result = []
    for item in arr:
        trimmed = item.strip()
        if trimmed not in seen:
            seen.add(trimmed)
            result.append(trimmed)
    if len(result) != len(arr):
        callback(f"[WARNING] [dedup_and_trim] Duplicates found and removed. Original count: {len(arr)}, New count: {len(result)}")
    return result

def get_expanded_template_colors(season_id, website_id, total_pins, callback=print):
    """
    Get and expand template colors for pins.
    
    Args:
        season_id: Season ID from the post
        website_id: Website ID
        total_pins: Total number of pins to create
        callback: Callback function for logging
        
    Returns:
        List of expanded and shuffled template colors
    """
    # Import here to avoid circular dependencies
    if not season_id:
        callback(f"[WARNING][get_expanded_template_colors] Season in the post is empty, will use the default one for template colors")
        season_id = SEASON_EVERGREEN_ID

    template_colors = get_template_colors(website_id, season_id)
    if not template_colors:
        raise ValueError("No template colors found for the specified website and season.")
    callback(f"[INFO][get_expanded_template_colors] Found {len(template_colors)} template colors")
    expanded_template_colors = expand_and_shuffle(template_colors, total_pins)
    
    return expanded_template_colors