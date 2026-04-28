import requests
import datetime
import json
import os

API_URL = "https://jobsearch.api.jobtechdev.se/search"
SÖKORD = [
    "affärsutvecklare",
    "verksamhetsutvecklare",
    "coach",
    "personalansvarig",
    "administrationschef",
]

def hämta_jobb_för_sökord(sökord, antal=5, tillåtna_lan=None):
    params = {"q": sökord, "limit": antal}
    headers = {"accept": "application/json"}
    try:
        r = requests.get(API_URL, params=params, headers=headers, timeout=10)
        r.raise_for_status()
        hits = r.json().get("hits", [])
        resultat = []
        for h in hits:
            lan = (h.get("workplace_address") or {}).get("region", "") or ""
            if tillåtna_lan and not any(l.lower() in lan.lower() for l in tillåtna_lan):
                continue
            deadline_raw = h.get("application_deadline", "") or ""
            deadline = deadline_raw[:10] if deadline_raw else ""
            kontakter = h.get("application_contacts", []) or []
            kontakt_namn = kontakter[0].get("name", "") if kontakter else ""
            kontakt_email = kontakter[0].get("email", "") if kontakter else ""
            resultat.append({
                "id": h.get("id", ""),
                "titel": h.get("headline", ""),
                "företag": (h.get("employer") or {}).get("name", ""),
                "plats": (h.get("workplace_address") or {}).get("municipality", ""),
                "url": h.get("webpage_url", ""),
                "källa": "Arbetsförmedlingen",
                "sökord": sökord,
                "datum_hittad": datetime.date.today().isoformat(),
                "deadline": deadline,
                "status": "Ny",
                "kontakt_namn": kontakt_namn,
                "kontakt_email": kontakt_email,
                "anteckningar": "",
                "datum_ansökt": None,
            })
        return resultat
    except requests.RequestException as e:
        print(f"  Fel vid sökning på '{sökord}': {e}")
        return []

def importera_alla(befintliga_ids, antal_per_sökord=5, tillåtna_lan=None):
    nya = []
    for sökord in SÖKORD:
        print(f"  Söker: {sökord}...", end=" ", flush=True)
        jobb = hämta_jobb_för_sökord(sökord, antal_per_sökord, tillåtna_lan)
        nya_för_sökord = [j for j in jobb if j["id"] not in befintliga_ids]
        print(f"{len(nya_för_sökord)} nya")
        nya.extend(nya_för_sökord)
        befintliga_ids.update(j["id"] for j in nya_för_sökord)
    return nya

def ladda_sökord():
    if os.path.exists("sökord.json"):
        with open("sökord.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return SÖKORD

def spara_sökord(sökord_lista):
    with open("sökord.json", "w", encoding="utf-8") as f:
        json.dump(sökord_lista, f, ensure_ascii=False, indent=2)

def ladda_exkludera():
    if os.path.exists("exkludera.json"):
        with open("exkludera.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def spara_exkludera(lista):
    with open("exkludera.json", "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)
