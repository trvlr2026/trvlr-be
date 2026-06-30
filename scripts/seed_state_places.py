"""
Seed top 10 places from each Indian state/UT.

Uses state names, district names, and location_type values from locations_meta.txt
to ensure compatibility with the backend DB.

For each place:
  1. Fetch coordinates from OSM Nominatim
  2. Fetch polygon geofence from OSM
  3. Download hero image from Wikipedia
  4. Output single CSV with all details

Usage:
  python3 scripts/seed_state_places.py
  python3 scripts/seed_state_places.py --state "Karnataka"
  python3 scripts/seed_state_places.py --resume

Output:
  data/state_places_india.csv
  data/state_hero_images/<state>/<place>.jpg

Requirements:
  pip3 install requests
"""

import argparse
import csv
import json
import math
import re
import time
from pathlib import Path

import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
OUTPUT_DIR = PROJECT_ROOT / "data"
IMAGES_DIR = OUTPUT_DIR / "state_hero_images"
OUTPUT_CSV = OUTPUT_DIR / "state_places_india.csv"
META_FILE = SCRIPT_DIR / "locations_meta.txt"

HEADERS = {
    "User-Agent": "trvlr-state-places/1.0 (contact@brainybaba.com)",
}

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
WIKI_API = "https://en.wikipedia.org/w/api.php"


# ─────────────────────────────────────────────────────────────────────────────
# PARSE locations_meta.txt
# ─────────────────────────────────────────────────────────────────────────────

def parse_meta_file(meta_path: Path) -> tuple[list[str], list[str], list[str]]:
    """Parse locations_meta.txt to extract states, districts, and location_types."""
    text = meta_path.read_text(encoding="utf-8")

    sections = re.split(r"\n\s*(States|Districts|location_type)\s*\n", text)
    # sections = ['', 'States', '<states content>', 'Districts', '<districts content>', 'location_type', '<types content>']

    states = []
    districts = []
    location_types = []

    current_section = None
    for part in sections:
        stripped = part.strip()
        if stripped == "States":
            current_section = "states"
            continue
        elif stripped == "Districts":
            current_section = "districts"
            continue
        elif stripped == "location_type":
            current_section = "location_types"
            continue

        if current_section == "states":
            states = [line.strip() for line in part.strip().split("\n") if line.strip()]
        elif current_section == "districts":
            districts = [line.strip() for line in part.strip().split("\n") if line.strip()]
        elif current_section == "location_types":
            location_types = [line.strip() for line in part.strip().split("\n") if line.strip()]

    return states, districts, location_types


# Load meta data
VALID_STATES, VALID_DISTRICTS, VALID_LOCATION_TYPES = parse_meta_file(META_FILE)

# Build a lookup set for districts (lowercase -> exact name)
DISTRICT_LOOKUP = {d.lower(): d for d in VALID_DISTRICTS}


def find_district(district_hint: str) -> str:
    """Find the matching district name from meta file."""
    hint_lower = district_hint.lower()
    # Exact match
    if hint_lower in DISTRICT_LOOKUP:
        return DISTRICT_LOOKUP[hint_lower]
    # Partial match
    for key, val in DISTRICT_LOOKUP.items():
        if hint_lower in key or key in hint_lower:
            return val
    return district_hint  # Return as-is if no match


def map_location_type(category: str) -> str:
    """Map our category to a valid location_type from meta file."""
    category_mapping = {
        "Monument": "tourism:attraction",
        "Heritage": "historic:monument",
        "Pilgrimage": "tourism:place_of_worship",
        "Beach": "tourism:beach",
        "Nature": "natural:valley",
        "Hill Station": "natural:mountain",
        "Wildlife": "leisure:nature_reserve",
        "Adventure": "natural:peak",
        "Lake": "natural:lake",
        "Fort": "historic:fort",
        "Temple": "tourism:place_of_worship",
        "Cave": "natural:cave_entrance",
        "Waterfall": "natural:water",
        "Park": "leisure:park",
        "Museum": "tourism:museum",
        "Garden": "leisure:garden",
    }
    return category_mapping.get(category, "tourism:attraction")


# ─────────────────────────────────────────────────────────────────────────────
# TOP 10 PLACES PER STATE/UT
# Format: (place_name, category, district_hint)
# district_hint is used to find the correct district from meta file
# ─────────────────────────────────────────────────────────────────────────────

STATES_PLACES = {
    "Andhra Pradesh": [
        ("Tirupati Balaji Temple", "Pilgrimage", "Tirupati"),
        ("Araku Valley", "Nature", "Visakhapatnam"),
        ("Srisailam Temple", "Pilgrimage", "Nandyal"),
        ("Vijayawada Kanaka Durga Temple", "Pilgrimage", "NTR"),
        ("Lepakshi Temple", "Heritage", "Anantapuram"),
        ("Gandikota", "Nature", "YSR Kadapa"),
        ("Undavalli Caves", "Heritage", "Guntur"),
        ("Horsley Hills", "Nature", "Chittoor"),
        ("Srikalahasti Temple", "Pilgrimage", "Tirupati"),
        ("Konaseema Mangroves", "Nature", "Konaseema"),
    ],
    "Arunachal Pradesh": [
        ("Tawang Monastery", "Pilgrimage", "Tawang district"),
        ("Ziro Valley", "Nature", "Lower Subansiri"),
        ("Sela Pass", "Adventure", "Tawang district"),
        ("Namdapha National Park", "Wildlife", "Changlang"),
        ("Bomdila", "Nature", "West Kameng"),
        ("Mechuka Valley", "Nature", "Shi Yomi"),
        ("Dirang", "Nature", "West Kameng"),
        ("Pasighat", "Nature", "East Siang"),
        ("Itanagar Ganga Lake", "Nature", "Papum Pare"),
        ("Nuranang Falls", "Nature", "Tawang district"),
    ],
    "Assam": [
        ("Kaziranga National Park", "Wildlife", "Nagaon"),
        ("Kamakhya Temple", "Pilgrimage", "Kamrup Metropolitan"),
        ("Majuli Island", "Nature", "Jorhat"),
        ("Manas National Park", "Wildlife", "Baksa"),
        ("Sivasagar", "Heritage", "Sivasagar"),
        ("Haflong", "Nature", "Dima Hasao"),
        ("Pobitora Wildlife Sanctuary", "Wildlife", "Morigaon"),
        ("Hajo", "Pilgrimage", "Kamrup"),
        ("Sualkuchi", "Heritage", "Kamrup"),
        ("Dipor Bil", "Nature", "Kamrup Metropolitan"),
    ],
    "Bihar": [
        ("Bodh Gaya Mahabodhi Temple", "Pilgrimage", "Gaya"),
        ("Nalanda University Ruins", "Heritage", "Nalanda"),
        ("Rajgir", "Pilgrimage", "Nalanda"),
        ("Vaishali", "Heritage", "Vaishali"),
        ("Patna Sahib Gurudwara", "Pilgrimage", "Patna"),
        ("Vikramshila University Ruins", "Heritage", "Bhagalpur"),
        ("Pawapuri", "Pilgrimage", "Nalanda"),
        ("Barabar Caves", "Heritage", "Gaya"),
        ("Mundeshwari Temple", "Pilgrimage", "Kaimur"),
        ("Valmiki National Park", "Wildlife", "West Champaran"),
    ],
    "Chhattisgarh": [
        ("Chitrakote Falls", "Nature", "Bastar"),
        ("Barnawapara Wildlife Sanctuary", "Wildlife", "Raipur"),
        ("Tirathgarh Falls", "Nature", "Bastar"),
        ("Bhoramdeo Temple", "Heritage", "Kabirdham"),
        ("Sirpur", "Heritage", "Mahasamund"),
        ("Kanger Valley National Park", "Wildlife", "Bastar"),
        ("Mainpat", "Nature", "Surajpur"),
        ("Rajim", "Pilgrimage", "Gariaband"),
        ("Danteshwari Temple Jagdalpur", "Pilgrimage", "Bastar"),
        ("Achanakmar Wildlife Sanctuary", "Wildlife", "Bilaspur"),
    ],
    "Goa": [
        ("Basilica of Bom Jesus", "Heritage", "North Goa"),
        ("Calangute Beach", "Beach", "North Goa"),
        ("Dudhsagar Falls", "Nature", "South Goa"),
        ("Fort Aguada", "Heritage", "North Goa"),
        ("Se Cathedral", "Heritage", "North Goa"),
        ("Anjuna Beach", "Beach", "North Goa"),
        ("Palolem Beach", "Beach", "South Goa"),
        ("Chapora Fort", "Heritage", "North Goa"),
        ("Shri Mangueshi Temple", "Pilgrimage", "North Goa"),
        ("Dona Paula", "Beach", "North Goa"),
    ],
    "Gujarat": [
        ("Statue of Unity", "Monument", "Narmada"),
        ("Somnath Temple", "Pilgrimage", "Gir Somnath"),
        ("Dwarka Temple", "Pilgrimage", "Devbhumi Dwaraka"),
        ("Rann of Kutch", "Nature", "Kutch"),
        ("Gir National Park", "Wildlife", "Junagadh"),
        ("Sabarmati Ashram", "Heritage", "Ahmedabad"),
        ("Rani ki Vav Patan", "Heritage", "Patan"),
        ("Modhera Sun Temple", "Heritage", "Mahesana"),
        ("Girnar", "Pilgrimage", "Junagadh"),
        ("Lothal", "Heritage", "Ahmedabad"),
    ],
    "Haryana": [
        ("Kurukshetra", "Pilgrimage", "Kurukshetra"),
        ("Sultanpur Bird Sanctuary", "Wildlife", "Gurugram"),
        ("Pinjore Gardens", "Heritage", "Ambala"),
        ("Surajkund", "Heritage", "Faridabad"),
        ("Morni Hills", "Nature", "Ambala"),
        ("Brahma Sarovar Kurukshetra", "Pilgrimage", "Kurukshetra"),
        ("Panipat Museum", "Heritage", "Panipat"),
        ("Tilyar Lake Rohtak", "Nature", "Rohtak"),
        ("Damdama Lake", "Nature", "Gurugram"),
        ("Panchkula Cactus Garden", "Nature", "Ambala"),
    ],
    "Himachal Pradesh": [
        ("Shimla", "Nature", "Shimla"),
        ("Manali", "Nature", "Kullu"),
        ("Dharamshala", "Heritage", "Kangra"),
        ("Spiti Valley", "Adventure", "Lahaul and Spiti"),
        ("Kullu Valley", "Nature", "Kullu"),
        ("Dalhousie", "Nature", "Chamba"),
        ("Kasol", "Nature", "Kullu"),
        ("Rohtang Pass", "Adventure", "Kullu"),
        ("McLeod Ganj", "Heritage", "Kangra"),
        ("Khajjiar", "Nature", "Chamba"),
    ],
    "Jharkhand": [
        ("Baidyanath Temple Deoghar", "Pilgrimage", "Deoghar"),
        ("Hundru Falls", "Nature", "Ranchi"),
        ("Betla National Park", "Wildlife", "Latehar"),
        ("Rajrappa Temple", "Pilgrimage", "Ramgarh"),
        ("Netarhat", "Nature", "Latehar"),
        ("Jonha Falls", "Nature", "Ranchi"),
        ("Parasnath Hill", "Pilgrimage", "Giridih"),
        ("Tagore Hill Ranchi", "Heritage", "Ranchi"),
        ("Dassam Falls", "Nature", "Ranchi"),
        ("McCluskieganj", "Heritage", "Ranchi"),
    ],
    "Karnataka": [
        ("Hampi", "Heritage", "Vijayanagara"),
        ("Mysore Palace", "Heritage", "Mysuru District"),
        ("Coorg", "Nature", "Coorg"),
        ("Gokarna", "Beach", "Uttara Kannada"),
        ("Jog Falls", "Nature", "Shimoga"),
        ("Badami Caves", "Heritage", "Bagalkote"),
        ("Bandipur National Park", "Wildlife", "Chamarajanagar"),
        ("Murudeshwar Temple", "Pilgrimage", "Uttara Kannada"),
        ("Chikmagalur", "Nature", "Chikkamagaluru"),
        ("Belur and Halebidu", "Heritage", "Hassan"),
    ],
    "Kerala": [
        ("Munnar", "Nature", "Idukki"),
        ("Alleppey Backwaters", "Nature", "Alappuzha"),
        ("Kochi Fort Kochi", "Heritage", "Ernakulam"),
        ("Wayanad", "Nature", "Wayanad"),
        ("Varkala Beach", "Beach", "Thiruvananthapuram"),
        ("Periyar National Park", "Wildlife", "Idukki"),
        ("Kovalam Beach", "Beach", "Thiruvananthapuram"),
        ("Kumarakom", "Nature", "Alappuzha"),
        ("Athirappilly Falls", "Nature", "Ernakulam"),
        ("Sabarimala Temple", "Pilgrimage", "Pathanamthitta"),
    ],
    "Madhya Pradesh": [
        ("Khajuraho Temples", "Heritage", "Chhatarpur"),
        ("Sanchi Stupa", "Heritage", "Raisen"),
        ("Kanha National Park", "Wildlife", "Mandla"),
        ("Bandhavgarh National Park", "Wildlife", "Umaria"),
        ("Ujjain Mahakaleshwar", "Pilgrimage", "Ujjain"),
        ("Orchha", "Heritage", "Niwari"),
        ("Pachmarhi", "Nature", "Narmadapuram"),
        ("Gwalior Fort", "Heritage", "Gwalior"),
        ("Omkareshwar", "Pilgrimage", "Khandwa"),
        ("Bhimbetka Rock Shelters", "Heritage", "Raisen"),
    ],
    "Maharashtra": [
        ("Gateway of India Mumbai", "Monument", "Mumbai City District"),
        ("Ajanta Caves", "Heritage", "Chhatrapati Sambhajinagar District"),
        ("Ellora Caves", "Heritage", "Chhatrapati Sambhajinagar District"),
        ("Shirdi Sai Baba Temple", "Pilgrimage", "Ahilyanagar District"),
        ("Lonavala", "Nature", "Pune District"),
        ("Mahabaleshwar", "Nature", "Satara"),
        ("Shaniwar Wada Pune", "Heritage", "Pune District"),
        ("Elephanta Caves", "Heritage", "Mumbai Suburban District"),
        ("Raigad Fort", "Heritage", "Raigad"),
        ("Trimbakeshwar Temple", "Pilgrimage", "Nashik District"),
    ],
    "Manipur": [
        ("Loktak Lake", "Nature", "Bishnupur district"),
        ("Kangla Fort", "Heritage", "Imphal West"),
        ("Shree Govindajee Temple", "Pilgrimage", "Imphal East"),
        ("Dzukou Valley", "Nature", "Senapati"),
        ("Keibul Lamjao National Park", "Wildlife", "Bishnupur district"),
        ("Ukhrul", "Nature", "Ukhrul district"),
        ("Ima Keithel Women Market", "Heritage", "Imphal West"),
        ("Sendra Island", "Nature", "Bishnupur district"),
        ("Moreh", "Heritage", "Tengnoupal"),
        ("Kangchup Peak", "Adventure", "Kangpokpi district"),
    ],
    "Meghalaya": [
        ("Living Root Bridges Cherrapunji", "Nature", "East Khasi Hills"),
        ("Mawsynram", "Nature", "East Khasi Hills"),
        ("Shillong Peak", "Nature", "East Khasi Hills"),
        ("Dawki River", "Nature", "West Jaintia Hills"),
        ("Nohkalikai Falls", "Nature", "East Khasi Hills"),
        ("Elephant Falls", "Nature", "East Khasi Hills"),
        ("Mawlynnong Village", "Nature", "East Khasi Hills"),
        ("Umiam Lake", "Nature", "Ri-Bhoi"),
        ("Don Bosco Museum Shillong", "Heritage", "East Khasi Hills"),
        ("Laitlum Canyons", "Nature", "East Khasi Hills"),
    ],
    "Mizoram": [
        ("Phawngpui Blue Mountain", "Nature", "Lawngtlai"),
        ("Durtlang Hills", "Nature", "Aizawl"),
        ("Vantawng Falls", "Nature", "Saitual"),
        ("Tam Dil Lake", "Nature", "Saitual"),
        ("Reiek Heritage Village", "Heritage", "Mamit"),
        ("Champhai", "Nature", "Champhai district"),
        ("Dampa Tiger Reserve", "Wildlife", "Mamit"),
        ("Solomon Temple Aizawl", "Heritage", "Aizawl"),
        ("Hmuifang", "Nature", "Aizawl"),
        ("Tamdil Lake", "Nature", "Saitual"),
    ],
    "Nagaland": [
        ("Hornbill Festival Kisama", "Heritage", "Kohima"),
        ("Dzukou Valley", "Nature", "Kohima"),
        ("Kohima War Cemetery", "Heritage", "Kohima"),
        ("Mokokchung", "Heritage", "Mokokchung"),
        ("Tuophema Village", "Heritage", "Kohima"),
        ("Triple Falls Seithekima", "Nature", "Kohima"),
        ("Khonoma Village", "Heritage", "Kohima"),
        ("Japfu Peak", "Adventure", "Kohima"),
        ("Longwa Village", "Heritage", "Mon"),
        ("Shilloi Lake", "Nature", "Phek"),
    ],
    "Odisha": [
        ("Jagannath Temple Puri", "Pilgrimage", "Khordha"),
        ("Konark Sun Temple", "Heritage", "Khordha"),
        ("Lingaraj Temple Bhubaneswar", "Pilgrimage", "Khordha"),
        ("Chilika Lake", "Nature", "Khordha"),
        ("Dhauli Peace Pagoda", "Heritage", "Khordha"),
        ("Simlipal National Park", "Wildlife", "Mayurbhanj"),
        ("Udayagiri and Khandagiri Caves", "Heritage", "Khordha"),
        ("Puri Beach", "Beach", "Khordha"),
        ("Hirakud Dam", "Nature", "Sambalpur"),
        ("Bhitarkanika National Park", "Wildlife", "Kendrapara"),
    ],
    "Punjab": [
        ("Golden Temple Amritsar", "Pilgrimage", "Amritsar"),
        ("Jallianwala Bagh", "Heritage", "Amritsar"),
        ("Wagah Border", "Heritage", "Amritsar"),
        ("Anandpur Sahib", "Pilgrimage", "Rupnagar"),
        ("Harike Wetland", "Nature", "Firozpur"),
        ("Qila Mubarak Patiala", "Heritage", "Patiala"),
        ("Virasat-e-Khalsa Anandpur", "Heritage", "Rupnagar"),
        ("Gobindgarh Fort Amritsar", "Heritage", "Amritsar"),
        ("Sheesh Mahal Patiala", "Heritage", "Patiala"),
        ("Gurudwara Fatehgarh Sahib", "Pilgrimage", "Fatehgarh Sahib"),
    ],
    "Rajasthan": [
        ("Jaipur City Palace", "Heritage", "Jaipur"),
        ("Udaipur Lake Palace", "Heritage", "Udaipur"),
        ("Jaisalmer Fort", "Heritage", "Jaisalmer"),
        ("Jodhpur Mehrangarh Fort", "Heritage", "Jodhpur"),
        ("Pushkar Lake", "Pilgrimage", "Ajmer"),
        ("Ranthambore Fort", "Heritage", "Sawai Madhopur"),
        ("Ajmer Sharif Dargah", "Pilgrimage", "Ajmer"),
        ("Chittorgarh Fort", "Heritage", "Chittorgarh"),
        ("Sam Sand Dunes Jaisalmer", "Nature", "Jaisalmer"),
        ("Mount Abu Dilwara Temples", "Pilgrimage", "Pali"),
    ],
    "Sikkim": [
        ("Tsomgo Lake", "Nature", "Gangtok"),
        ("Nathula Pass", "Adventure", "Gangtok"),
        ("Rumtek Monastery", "Pilgrimage", "Gangtok"),
        ("Pelling", "Nature", "Gyalshing"),
        ("Gurudongmar Lake", "Nature", "Mangan"),
        ("Yumthang Valley", "Nature", "Mangan"),
        ("Gangtok MG Marg", "Heritage", "Gangtok"),
        ("Namchi Char Dham", "Pilgrimage", "Namchi"),
        ("Zuluk", "Adventure", "Pakyong"),
        ("Ravangla Buddha Park", "Pilgrimage", "Namchi"),
    ],
    "Tamil Nadu": [
        ("Meenakshi Temple Madurai", "Pilgrimage", "Madurai"),
        ("Rameswaram Temple", "Pilgrimage", "Ramanathapuram"),
        ("Ooty", "Nature", "Nilgiris"),
        ("Mahabalipuram Shore Temple", "Heritage", "Chengalpattu"),
        ("Kanyakumari", "Pilgrimage", "Kanniyakumari"),
        ("Brihadeeswarar Temple Thanjavur", "Heritage", "Thanjavur"),
        ("Kodaikanal", "Nature", "Dindigul"),
        ("Marina Beach Chennai", "Beach", "Chennai"),
        ("Mudumalai National Park", "Wildlife", "Nilgiris"),
        ("Dhanushkodi", "Nature", "Ramanathapuram"),
    ],
    "Telangana": [
        ("Charminar Hyderabad", "Monument", "Hyderabad"),
        ("Golconda Fort", "Heritage", "Hyderabad"),
        ("Ramoji Film City", "Heritage", "Ranga Reddy"),
        ("Warangal Fort", "Heritage", "Hanumakonda"),
        ("Thousand Pillar Temple", "Heritage", "Hanumakonda"),
        ("Hussain Sagar Lake", "Nature", "Hyderabad"),
        ("Nagarjuna Sagar Dam", "Nature", "Nalgonda"),
        ("Birla Mandir Hyderabad", "Pilgrimage", "Hyderabad"),
        ("Qutb Shahi Tombs", "Heritage", "Hyderabad"),
        ("Medak Cathedral", "Heritage", "Medak"),
    ],
    "Tripura": [
        ("Ujjayanta Palace", "Heritage", "West Tripura"),
        ("Neermahal Water Palace", "Heritage", "Gomati"),
        ("Unakoti", "Heritage", "Unakoti"),
        ("Sepahijala Wildlife Sanctuary", "Wildlife", "Sipahijala"),
        ("Jampui Hills", "Nature", "North Tripura"),
        ("Pilak", "Heritage", "South Tripura"),
        ("Tripura Sundari Temple", "Pilgrimage", "Gomati"),
        ("Heritage Park Agartala", "Heritage", "West Tripura"),
        ("Dumboor Lake", "Nature", "Dhalai"),
        ("Chabimura", "Heritage", "Gomati"),
    ],
    "Uttar Pradesh": [
        ("Taj Mahal Agra", "Monument", "Agra"),
        ("Varanasi Ghats", "Pilgrimage", "Varanasi"),
        ("Ayodhya Ram Mandir", "Pilgrimage", "Ayodhya"),
        ("Mathura Vrindavan", "Pilgrimage", "Mathura"),
        ("Fatehpur Sikri", "Heritage", "Agra"),
        ("Lucknow Bara Imambara", "Heritage", "Lucknow"),
        ("Sarnath", "Heritage", "Varanasi"),
        ("Agra Fort", "Heritage", "Agra"),
        ("Allahabad Triveni Sangam", "Pilgrimage", "Prayagraj"),
        ("Chitrakoot", "Pilgrimage", "Chitrakoot"),
    ],
    "Uttarakhand": [
        ("Kedarnath Temple", "Pilgrimage", "Rudraprayag"),
        ("Badrinath Temple", "Pilgrimage", "Chamoli"),
        ("Rishikesh", "Pilgrimage", "Dehradun"),
        ("Haridwar Har Ki Pauri", "Pilgrimage", "Haridwar"),
        ("Nainital", "Nature", "Nainital"),
        ("Mussoorie", "Nature", "Dehradun"),
        ("Valley of Flowers", "Nature", "Chamoli"),
        ("Jim Corbett National Park", "Wildlife", "Nainital"),
        ("Auli", "Adventure", "Chamoli"),
        ("Tungnath Temple", "Pilgrimage", "Rudraprayag"),
    ],
    "West Bengal": [
        ("Victoria Memorial Kolkata", "Monument", "Kolkata"),
        ("Darjeeling", "Nature", "Darjeeling"),
        ("Sundarbans", "Wildlife", "South 24 Parganas"),
        ("Howrah Bridge", "Monument", "Howrah"),
        ("Dakshineswar Kali Temple", "Pilgrimage", "North 24 Parganas"),
        ("Bishnupur Temples", "Heritage", "Bankura"),
        ("Shantiniketan", "Heritage", "Birbhum"),
        ("Kalimpong", "Nature", "Kalimpong"),
        ("Digha Beach", "Beach", "Purba Medinipur"),
        ("Murshidabad Hazarduari", "Heritage", "Murshidabad"),
    ],
    # ── Union Territories ──
    "Delhi": [
        ("Red Fort", "Monument", "Central Delhi"),
        ("Qutub Minar", "Monument", "South Delhi"),
        ("India Gate", "Monument", "New Delhi"),
        ("Humayun Tomb", "Heritage", "New Delhi"),
        ("Lotus Temple", "Pilgrimage", "South Delhi"),
        ("Akshardham Temple", "Pilgrimage", "East Delhi"),
        ("Jama Masjid", "Heritage", "Central Delhi"),
        ("Chandni Chowk", "Heritage", "Central Delhi"),
        ("Rashtrapati Bhavan", "Monument", "New Delhi"),
        ("Purana Qila", "Heritage", "New Delhi"),
    ],
    "Jammu and Kashmir": [
        ("Dal Lake Srinagar", "Nature", "Baramulla"),
        ("Gulmarg", "Adventure", "Baramulla"),
        ("Pahalgam", "Nature", "Anantnag"),
        ("Vaishno Devi Temple", "Pilgrimage", "Reasi district"),
        ("Sonamarg", "Nature", "Ganderbal"),
        ("Amarnath Cave Temple", "Pilgrimage", "Anantnag"),
        ("Mughal Gardens Srinagar", "Heritage", "Baramulla"),
        ("Patnitop", "Nature", "Udhampur district"),
        ("Shankaracharya Temple", "Pilgrimage", "Baramulla"),
        ("Betaab Valley", "Nature", "Anantnag"),
    ],
    "Ladakh": [
        ("Pangong Lake", "Nature", "Leh district"),
        ("Leh Palace", "Heritage", "Leh district"),
        ("Nubra Valley", "Nature", "Leh district"),
        ("Thiksey Monastery", "Pilgrimage", "Leh district"),
        ("Hemis Monastery", "Pilgrimage", "Leh district"),
        ("Khardung La Pass", "Adventure", "Leh district"),
        ("Magnetic Hill", "Nature", "Leh district"),
        ("Shanti Stupa Leh", "Heritage", "Leh district"),
        ("Tso Moriri Lake", "Nature", "Leh district"),
        ("Zanskar Valley", "Adventure", "Kargil district"),
    ],
    "Chandigarh": [
        ("Rock Garden Chandigarh", "Heritage", "Chandigarh"),
        ("Sukhna Lake", "Nature", "Chandigarh"),
        ("Rose Garden Chandigarh", "Nature", "Chandigarh"),
        ("Capitol Complex", "Heritage", "Chandigarh"),
        ("Government Museum Chandigarh", "Heritage", "Chandigarh"),
        ("Japanese Garden", "Nature", "Chandigarh"),
        ("Leisure Valley", "Nature", "Chandigarh"),
        ("Butterfly Park", "Nature", "Chandigarh"),
        ("Open Hand Monument", "Monument", "Chandigarh"),
        ("International Dolls Museum", "Heritage", "Chandigarh"),
    ],
    "Puducherry": [
        ("Auroville", "Heritage", "Puducherry"),
        ("Promenade Beach", "Beach", "Puducherry"),
        ("Sri Aurobindo Ashram", "Pilgrimage", "Puducherry"),
        ("Paradise Beach", "Beach", "Puducherry"),
        ("French Quarter", "Heritage", "Puducherry"),
        ("Manakula Vinayagar Temple", "Pilgrimage", "Puducherry"),
        ("Serenity Beach", "Beach", "Puducherry"),
        ("Botanical Garden Puducherry", "Nature", "Puducherry"),
        ("Chunnambar Boathouse", "Nature", "Puducherry"),
        ("Basilica of the Sacred Heart", "Heritage", "Puducherry"),
    ],
    "Andaman and Nicobar Islands": [
        ("Radhanagar Beach Havelock", "Beach", "South Andaman"),
        ("Cellular Jail Port Blair", "Heritage", "South Andaman"),
        ("Neil Island", "Beach", "South Andaman"),
        ("Ross Island", "Heritage", "South Andaman"),
        ("Baratang Island", "Nature", "North and Middle Andaman"),
        ("Elephant Beach", "Beach", "South Andaman"),
        ("North Bay Island", "Beach", "South Andaman"),
        ("Chidiya Tapu", "Nature", "South Andaman"),
        ("Mount Harriet", "Nature", "South Andaman"),
        ("Mahatma Gandhi Marine National Park", "Wildlife", "South Andaman"),
    ],
    "Lakshadweep": [
        ("Agatti Island", "Beach", "Lakshadweep"),
        ("Bangaram Island", "Beach", "Lakshadweep"),
        ("Kavaratti Island", "Beach", "Lakshadweep"),
        ("Minicoy Island", "Beach", "Lakshadweep"),
        ("Kalpeni Island", "Beach", "Lakshadweep"),
        ("Kadmat Island", "Beach", "Lakshadweep"),
        ("Andrott Island", "Beach", "Lakshadweep"),
        ("Marine Museum Kavaratti", "Heritage", "Lakshadweep"),
        ("Ujra Mosque Kavaratti", "Heritage", "Lakshadweep"),
        ("Lighthouse Minicoy", "Heritage", "Lakshadweep"),
    ],
    "Dadra and Nagar Haveli and Daman and Diu": [
        ("Diu Fort", "Heritage", "Diu"),
        ("Nagoa Beach Diu", "Beach", "Diu"),
        ("Naida Caves Diu", "Nature", "Diu"),
        ("Silvassa Tribal Museum", "Heritage", "Dadra and Nagar Haveli"),
        ("Vanganga Lake Garden", "Nature", "Dadra and Nagar Haveli"),
        ("St Paul Church Diu", "Heritage", "Diu"),
        ("Gangeshwar Mahadev Temple", "Pilgrimage", "Diu"),
        ("Deer Park Silvassa", "Nature", "Dadra and Nagar Haveli"),
        ("Zampa Gateway Diu", "Heritage", "Diu"),
        ("Hirwa Van Garden", "Nature", "Dadra and Nagar Haveli"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# GEOFENCE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def fetch_coordinates_and_polygon(place_name: str, state: str) -> tuple[float | None, float | None, dict | None, str]:
    """Query Nominatim for coordinates and polygon."""
    params = {
        "q": f"{place_name}, {state}, India",
        "format": "jsonv2",
        "polygon_geojson": 1,
        "limit": 1,
    }
    try:
        resp = requests.get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        results = resp.json()
        if results:
            lat = float(results[0]["lat"])
            lon = float(results[0]["lon"])
            geojson = results[0].get("geojson")
            if geojson and geojson.get("type") in ("Polygon", "MultiPolygon"):
                return lat, lon, geojson, "osm"
            else:
                return lat, lon, generate_circular_geofence(lat, lon, 500), "circular_fallback_500m"
    except (requests.RequestException, KeyError, ValueError):
        pass
    return None, None, None, "not_found"


def generate_circular_geofence(lat: float, lon: float, radius_m: int = 500, points: int = 16) -> dict:
    coords = []
    for i in range(points):
        angle = 2 * math.pi * i / points
        dlat = (radius_m * math.cos(angle)) / 111320
        dlon = (radius_m * math.sin(angle)) / (111320 * math.cos(math.radians(lat)))
        coords.append([round(lon + dlon, 6), round(lat + dlat, 6)])
    coords.append(coords[0])
    return {"type": "Polygon", "coordinates": [coords]}


# ─────────────────────────────────────────────────────────────────────────────
# HERO IMAGE FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*()]+', "", name)
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    return cleaned.lower()


def fetch_wiki_image(place_name: str, state: str) -> str | None:
    params = {
        "action": "query",
        "list": "search",
        "srsearch": f"{place_name} {state} India",
        "format": "json",
        "srlimit": 1,
    }
    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        results = resp.json().get("query", {}).get("search", [])
        if not results:
            return None
        page_title = results[0]["title"]
    except requests.RequestException:
        return None

    time.sleep(0.3)

    params = {
        "action": "query",
        "titles": page_title,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": 1200,
    }
    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        for pid, pdata in pages.items():
            if pid == "-1":
                continue
            thumb = pdata.get("thumbnail", {})
            if thumb:
                return thumb.get("source")
    except requests.RequestException:
        pass
    return None


def download_image(url: str, dest: Path) -> bool:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=30, stream=True)
        resp.raise_for_status()
        if "image" not in resp.headers.get("content-type", ""):
            return False
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        if dest.stat().st_size < 1000:
            dest.unlink()
            return False
        return True
    except requests.RequestException:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def load_existing_results() -> dict:
    if not OUTPUT_CSV.exists():
        return {}
    existing = {}
    with open(OUTPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = f"{row['state']}|{row['place_name']}"
            existing[key] = row
    return existing


def save_csv(results: list[dict]) -> None:
    if not results:
        return
    fieldnames = [
        "state", "district", "state_rank", "place_name", "category", "location_type",
        "latitude", "longitude",
        "geofence_polygon", "geofence_source",
        "image_filename",
    ]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)


def main():
    parser = argparse.ArgumentParser(description="Seed top 10 places per Indian state")
    parser.add_argument("--state", type=str, default=None, help="Process only this state")
    parser.add_argument("--resume", action="store_true", help="Skip already processed places")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Validate states match meta file
    meta_states_set = set(VALID_STATES)
    for state in STATES_PLACES:
        if state not in meta_states_set:
            print(f"WARNING: State '{state}' not found in locations_meta.txt")

    # Filter states if requested
    states_to_process = STATES_PLACES
    if args.state:
        matching = {k: v for k, v in STATES_PLACES.items() if k.lower() == args.state.lower()}
        if not matching:
            print(f"State '{args.state}' not found. Available: {', '.join(STATES_PLACES.keys())}")
            return
        states_to_process = matching

    total_places = sum(len(places) for places in states_to_process.values())

    print("=" * 60)
    print("SEED TOP 10 PLACES PER STATE — INDIA")
    print("=" * 60)
    print(f"States/UTs:        {len(states_to_process)}")
    print(f"Total places:      {total_places}")
    print(f"Meta file:         {META_FILE}")
    print(f"Valid states:      {len(VALID_STATES)}")
    print(f"Valid districts:   {len(VALID_DISTRICTS)}")
    print(f"Valid loc types:   {len(VALID_LOCATION_TYPES)}")
    print(f"Output CSV:        {OUTPUT_CSV}")
    print(f"Hero images:       {IMAGES_DIR}")
    print("=" * 60)

    existing = load_existing_results() if args.resume else {}
    if existing:
        print(f"Resuming — {len(existing)} places already processed")

    results = list(existing.values()) if args.resume else []
    processed = 0
    skipped = 0

    for state, places in states_to_process.items():
        print(f"\n{'─' * 60}")
        print(f"STATE: {state} ({len(places)} places)")
        print(f"{'─' * 60}")

        state_img_dir = IMAGES_DIR / sanitize_filename(state)
        state_img_dir.mkdir(parents=True, exist_ok=True)

        for rank, (place_name, category, district_hint) in enumerate(places, 1):
            key = f"{state}|{place_name}"

            if args.resume and key in existing:
                skipped += 1
                continue

            processed += 1
            district = find_district(district_hint)
            location_type = map_location_type(category)

            print(f"\n  [{processed}] {place_name}")
            print(f"      District: {district} | Type: {location_type}")

            # ── Coordinates + Geofence ──
            print("      Geo...", end=" ", flush=True)
            lat, lon, geojson, geo_source = fetch_coordinates_and_polygon(place_name, state)
            time.sleep(1.1)

            if lat is None:
                print("NOT FOUND")
                row = {
                    "state": state,
                    "district": district,
                    "state_rank": rank,
                    "place_name": place_name,
                    "category": category,
                    "location_type": location_type,
                    "latitude": "",
                    "longitude": "",
                    "geofence_polygon": "",
                    "geofence_source": "not_found",
                    "image_filename": "",
                }
                results.append(row)
                continue

            print(f"{geo_source} ({lat:.4f}, {lon:.4f})")

            # ── Hero Image ──
            print("      Image...", end=" ", flush=True)
            image_url = fetch_wiki_image(place_name, state)
            time.sleep(0.3)

            image_filename = ""
            if image_url and ".svg" not in image_url.lower():
                safe_name = sanitize_filename(place_name)
                ext = ".png" if ".png" in image_url.lower() else ".jpg"
                image_filename = f"{sanitize_filename(state)}/{safe_name}{ext}"
                dest = IMAGES_DIR / image_filename

                if download_image(image_url, dest):
                    size_kb = dest.stat().st_size // 1024
                    print(f"OK ({size_kb}KB)")
                else:
                    image_filename = ""
                    print("Failed")
            else:
                print("Not found")

            time.sleep(0.3)

            # ── Build Row ──
            row = {
                "state": state,
                "district": district,
                "state_rank": rank,
                "place_name": place_name,
                "category": category,
                "location_type": location_type,
                "latitude": lat,
                "longitude": lon,
                "geofence_polygon": json.dumps(geojson) if geojson else "",
                "geofence_source": geo_source,
                "image_filename": image_filename,
            }
            results.append(row)

            if processed % 10 == 0:
                save_csv(results)

    save_csv(results)

    osm_count = sum(1 for r in results if r.get("geofence_source") == "osm")
    img_count = sum(1 for r in results if r.get("image_filename"))
    coord_count = sum(1 for r in results if r.get("latitude"))

    print("\n" + "=" * 60)
    print("DONE!")
    print(f"  Total places:       {len(results)}")
    print(f"  With coordinates:   {coord_count}/{len(results)}")
    print(f"  OSM geofences:      {osm_count}/{len(results)}")
    print(f"  Images downloaded:  {img_count}/{len(results)}")
    if skipped:
        print(f"  Skipped (resume):   {skipped}")
    print(f"  CSV:                {OUTPUT_CSV}")
    print(f"  Images:             {IMAGES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
