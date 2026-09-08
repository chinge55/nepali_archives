"""Reader introductions kept separate from the preserved literary text."""

from .config import GENRE


GENRE_INTROS = {
    "mahakavya": "धेरै सर्ग वा काण्डमा फैलिएको कथालाई पद्यमा प्रस्तुत गर्ने विस्तृत काव्य।",
    "khandakavya": "कुनै पात्र, घटना वा कथाको एउटा पक्षमा केन्द्रित कथात्मक काव्य।",
    "upanyas": "पात्र, परिवेश र घटनाक्रमलाई विस्तार गर्दै अघि बढ्ने लामो गद्य कथा।",
    "katha": "सीमित पात्र र घटनामार्फत जीवनको कुनै अनुभव वा अवस्थालाई प्रस्तुत गर्ने गद्य रचना।",
    "nibandha": "कुनै विषयमा लेखकका विचार, अनुभव वा अनुभूति प्रस्तुत गर्ने गद्य रचना।",
    "kavita": "लय, बिम्ब र शब्दको संयोजनबाट भावना, विचार र अनुभव व्यक्त गर्ने रचना।",
    "balkavita": "बालपाठकका लागि रचिएका लयात्मक कविता; खेल, प्रकृति र बालअनुभवका विविध स्वर।",
    "git": "गाउन मिल्ने लयमा भावना र अनुभव व्यक्त गर्ने रचना।",
    "bhajan": "भक्ति, प्रार्थना वा आध्यात्मिक चिन्तन व्यक्त गर्ने गेय रचना।",
    "gazal": "शेरहरूको संरचनामा प्रेम, जीवन र समाजका अनुभूति व्यक्त गर्ने काव्यरूप।",
}


def work_intro(meta, collections=()):
    """Use a reviewed summary, otherwise state only known catalogue facts."""
    summary = (meta.get("summary") or "").strip()
    if summary:
        return summary
    genre = (meta.get("genre") or [""])[0]
    label = GENRE.get(genre, ("रचना", ""))[0]
    author = meta["author"]["name"]
    if collections:
        names = " र ".join(f"‘{name}’" for name in collections)
        return f"{author}को {label}; {names} सङ्ग्रहमा समावेश।"
    return f"{author}को {label}।"
