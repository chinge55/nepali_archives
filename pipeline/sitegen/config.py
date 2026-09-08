"""Stable site metadata and catalogue display configuration."""

SITE_NAME = "नेपाली अभिलेख"
SITE_TAGLINE = "स्वतन्त्र, सार्वजनिक नेपाली साहित्य"
SITE_TAGLINE_EN = "A public-domain archive of Nepali literature"
SITE_URL = "https://www.nepaliarchives.org/"
REPO_URL = "https://github.com/chinge55/nepali_archives"

GENRE = {
    "mahakavya": ("महाकाव्य", "epic"),
    "khandakavya": ("खण्डकाव्य", "narrative poem"),
    "upanyas": ("उपन्यास", "novel"),
    "katha": ("कथा", "story"),
    "nibandha": ("निबन्ध", "essay"),
    "kavita": ("कविता", "poems"),
    "balkavita": ("बालकविता", "children's poems"),
    "git": ("गीत", "song"),
    "gazal": ("गजल", "ghazal"),
}

GENRE_ORDER = [
    "mahakavya",
    "khandakavya",
    "upanyas",
    "katha",
    "nibandha",
    "kavita",
    "balkavita",
    "git",
    "gazal",
]

# Authors absent from this optional display registry fall back to work metadata.
AUTHORS = {
    "devkota": ("लक्ष्मीप्रसाद देवकोटा", "Laxmi Prasad Devkota", "1909–1959"),
    "bhanubhakta_acharya": (
        "भानुभक्त आचार्य",
        "Bhanubhakta Acharya",
        "1814–1868",
    ),
    "lekhnath_paudyal": ("लेखनाथ पौड्याल", "Lekhnath Paudyal", "1885–1966"),
    "bhimnidhi_tiwari": ("भीमनिधि तिवारी", "Bhimnidhi Tiwari", "1911–1973"),
    "motiram_bhatta": ("मोतीराम भट्ट", "Motiram Bhatta", "1866–1896"),
    "gopalaprasad_rimal": ("गोपालप्रसाद रिमाल", "Gopal Prasad Rimal", "1917–1973"),
    "hriday_chandra_sinh_pradhan": ("हृदयचन्द्रसिंह प्रधान", "Hridaya Chandra Singh Pradhan", "1916–1960"),
    "baburam_acharya": ("बाबुराम आचार्य", "Baburam Acharya", "1888–1972"),
    "guruprasad_mainali": ("गुरुप्रसाद मैनाली", "Guru Prasad Mainali", "1900–1971"),
    "jagannath_upadhyay_guraganyin": ("जगन्नाथ उपाध्याय गुरागाञीं", "Jagannath Upadhyaya Guragāñī", "1900–1966"),
}

PROSE_GENRES = {"upanyas", "katha", "nibandha"}
