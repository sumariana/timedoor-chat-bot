PROPERTY_ALIASES: dict[str, list[str]] = {
    "name": ["Name", "Project Name", "Nama", "Nama Project"],
    "status": ["Status", "Project Status", "State"],
    "pm": ["PM", "Project Manager", "PIC", "Person in Charge", "Penanggung Jawab"],
    "platform": ["Platform", "Platforms", "Target Platform"],
    "framework": ["Framework", "Tech Stack", "Stack", "Technologies", "Teknologi"],
    "language": ["Language", "Programming Language", "Bahasa Pemrograman"],
    "category": ["Category", "Kategori", "Type", "Project Type"],
    "start_date": ["Start Date", "Tanggal Mulai", "Date Started", "Kick Off"],
    "end_date": ["End Date", "Tanggal Selesai", "Due Date", "Deadline"],
    "app_store_url": ["App Store URL", "App Store", "iOS URL", "Apple Store"],
    "play_store_url": ["Play Store URL", "Play Store", "Android URL", "Google Play"],
    "firebase_status": ["Firebase Status", "Firebase"],
    "sentry": ["Sentry", "Sentry Status"],
    "maintenance_status": ["Maintenance Status", "Maintenance", "Status Maintenance"],
    "design_link": ["Design Link", "Figma", "Design", "UI Design", "Figma Link"],
    "drive_link": ["Drive Link", "Google Drive", "Drive", "GDrive"],
}


def normalize_properties(raw_properties: dict) -> dict:
    normalized: dict = {}
    folded = {str(key).casefold(): value for key, value in raw_properties.items()}
    for canonical, aliases in PROPERTY_ALIASES.items():
        for alias in aliases:
            if alias.casefold() in folded:
                normalized[canonical] = folded[alias.casefold()]
                break
    return normalized
