
def report_progress(i, url_count, callback):
    callback(f"Processed {i+1}/{url_count}")

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