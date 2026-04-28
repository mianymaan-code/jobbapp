import streamlit as st
import json
import os
import datetime
import sys
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importera import importera_alla, ladda_sökord, spara_sökord, ladda_exkludera, spara_exkludera
from ai_analys import analysera_jobb, sätt_prioritet_bulk, föreslå_sökord

st.set_page_config(page_title="Jobbspåraren", page_icon="💼", layout="wide")

JOBB_FIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobb.json")
BORTTAGNA_FIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "borttagna.json")
STATUSAR = ["Ny", "Sparad", "Analys finns", "Ansökt", "Intervju", "Erbjudande", "Avslag", "Avslutad"]
PRIORITET_FARG = {"Hög": "🔴", "Medium": "🟡", "Låg": "🟢", "": "⚪"}

def ladda_jobb():
    if os.path.exists(JOBB_FIL):
        with open(JOBB_FIL, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def spara_jobb(jobb_lista):
    with open(JOBB_FIL, "w", encoding="utf-8") as f:
        json.dump(jobb_lista, f, ensure_ascii=False, indent=2)

def ladda_borttagna():
    if os.path.exists(BORTTAGNA_FIL):
        with open(BORTTAGNA_FIL, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def spara_borttagna(ids):
    with open(BORTTAGNA_FIL, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)

def init_state():
    if "jobb" not in st.session_state:
        st.session_state.jobb = ladda_jobb()
    if "valt_index" not in st.session_state:
        st.session_state.valt_index = None
    if "visa_analys" not in st.session_state:
        st.session_state.visa_analys = False

def visa_header():
    jobb = st.session_state.jobb
    totalt = len(jobb)
    aktiva = sum(1 for j in jobb if j["status"] in ("Ansökt", "Intervju", "Erbjudande"))
    hog = sum(1 for j in jobb if j.get("prioritet") == "Hög")
    analys = sum(1 for j in jobb if j.get("ai_analys"))
    st.title("💼 Jobbspåraren")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Totalt jobb", totalt)
    k2.metric("Aktiva ansökningar", aktiva)
    k3.metric("Hög prioritet", hog)
    k4.metric("AI-analyserade", analys)
    st.divider()

def visa_sidopanel():
    with st.sidebar:
        st.header("🔍 Filter")
        sok = st.text_input("Sök titel / företag", "")
        status_filter = st.multiselect("Status", options=STATUSAR, default=[s for s in STATUSAR if s != "Avslutad"])
        prio_filter = st.multiselect("Prioritet", options=["Hög", "Medium", "Ej satt"], default=[])
        kalla_filter = st.multiselect("Källa", options=["Arbetsförmedlingen", "Indeed", "Manuell"], default=[])
        alla_orter = sorted(set(j.get("plats") or "" for j in st.session_state.get("jobb", []) if j.get("plats")))
        ort_filter = st.multiselect("Ort", options=alla_orter, default=[])
        st.divider()
        st.header("⚡ Åtgärder")
        ALLA_LAN = [
            "Blekinge län", "Dalarnas län", "Gotlands län", "Gävleborgs län",
            "Hallands län", "Jämtlands län", "Jönköpings län", "Kalmar län",
            "Kronobergs län", "Norrbottens län", "Skåne län", "Stockholms län",
            "Södermanlands län", "Uppsala län", "Värmlands län", "Västerbottens län",
            "Västernorrlands län", "Västmanlands län", "Västra Götalands län",
            "Örebro län", "Östergötlands län"
        ]
        valda_lan = st.multiselect("🗺️ Importera jobb från län", options=ALLA_LAN, default=["Stockholms län"])
        st.session_state.valda_lan = valda_lan
        if st.button("📥 Importera nya jobb", use_container_width=True):
            st.session_state.importera = True
        if st.button("🤖 Sätt prioritet på alla (AI)", use_container_width=True):
            st.session_state.bulk_prioritet = True
        if st.button("➕ Lägg till eget jobb", use_container_width=True):
            st.session_state.visa_lagg_till = True
        if st.button("🗑️ Ta bort utgångna annonser", use_container_width=True):
            st.session_state.rensa_utgangna = True
        if st.button("🔑 Hantera sökord", use_container_width=True):
            st.session_state.visa_sokord = True
    return sok, status_filter, prio_filter, kalla_filter, ort_filter

def filtrera_jobb(sok, status_filter, prio_filter, kalla_filter, ort_filter):
    lista = st.session_state.jobb
    if status_filter:
        lista = [j for j in lista if j["status"] in status_filter]
    if prio_filter:
        def prio_match(j):
            p = j.get("prioritet", "")
            if "Ej satt" in prio_filter and p == "":
                return True
            return p in prio_filter
        lista = [j for j in lista if prio_match(j)]
    if kalla_filter:
        lista = [j for j in lista if j.get("källa", "") in kalla_filter]
    if ort_filter:
        lista = [j for j in lista if (j.get("plats") or "") in ort_filter]
    if sok:
        s = sok.lower()
        lista = [j for j in lista if s in j["titel"].lower() or s in j["företag"].lower()]
    return lista

def visa_tabell(filtrerade_jobb):
    if not filtrerade_jobb:
        st.info("Inga jobb matchar filtret.")
        return
    st.caption(f"{len(filtrerade_jobb)} jobb visas")
    for i, j in enumerate(filtrerade_jobb):
        prio_ikon = PRIORITET_FARG.get(j.get("prioritet", ""), "⚪")
        ai_ikon = "🤖" if j.get("ai_analys") else ""
        deadline = j.get("deadline", "")[:10] or "—"
        with st.container():
            k1, k2, k3, k4, k5, k6 = st.columns([0.5, 3.5, 2.5, 1.5, 1.5, 1])
            k1.write(prio_ikon)
            if k2.button(f"{j['titel'][:45]}", key=f"jobb_{i}", use_container_width=True):
                st.session_state.valt_index = st.session_state.jobb.index(j)
                st.session_state.visa_analys = False
            k3.write(j["företag"][:28])
            k4.write((j.get("plats") or "")[:14])
            k5.write(deadline)
            k6.write(f"{j['status'][:10]} {ai_ikon}")

def visa_detaljer():
    idx = st.session_state.valt_index
    if idx is None:
        return
    jobb_lista = st.session_state.jobb
    if idx >= len(jobb_lista):
        return
    j = jobb_lista[idx]
    st.divider()
    st.subheader(f"📋 {j['titel']}")
    st.caption(f"{j['företag']}  ·  {j.get('plats', '')}  ·  {j.get('län', '')}")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Status", j["status"])
    k2.metric("Prioritet", j.get("prioritet") or "Ej satt")
    k3.metric("Deadline", j.get("deadline", "—")[:10] or "—")
    k4.metric("Källa", j.get("källa", ""))
    col1, col2 = st.columns(2)
    if j.get("url"):
        col1.link_button("🔗 Öppna jobbannons", j["url"], use_container_width=True)
    if j.get("ansökningslänk") and j.get("ansökningslänk") != j.get("url"):
        col2.link_button("📨 Gå till ansökan", j["ansökningslänk"], use_container_width=True)
    if j.get("beskrivning"):
        with st.expander("📄 Jobbeskrivning"):
            st.write(j["beskrivning"][:800] + ("..." if len(j.get("beskrivning", "")) > 800 else ""))
    with st.expander("👤 Kontakt & anteckningar"):
        col1, col2 = st.columns(2)
        kontakt = col1.text_input("Kontaktperson", j.get("kontakt_namn", ""), key="kontakt_namn")
        email = col2.text_input("E-post", j.get("kontakt_email", ""), key="kontakt_email")
        ansokningslank = st.text_input("Länk till ansökan", j.get("ansökningslänk", ""), key="ansokningslank")
        anteckning = st.text_area("Anteckningar", j.get("anteckningar", ""), key="anteckningar")
        if st.button("💾 Spara kontaktinfo"):
            j["kontakt_namn"] = kontakt
            j["kontakt_email"] = email
            j["ansökningslänk"] = ansokningslank
            j["anteckningar"] = anteckning
            spara_jobb(jobb_lista)
            st.success("Sparat!")
    with st.expander("✏️ Uppdatera status & prioritet"):
        col1, col2 = st.columns(2)
        ny_status = col1.selectbox("Status", STATUSAR, index=STATUSAR.index(j["status"]) if j["status"] in STATUSAR else 0, key="ny_status")
        ny_prio = col2.selectbox("Prioritet", ["Hög", "Medium", ""], index=["Hög", "Medium", ""].index(j.get("prioritet", "")) if j.get("prioritet", "") in ["Hög", "Medium", ""] else 2, key="ny_prio")
        if st.button("💾 Spara status & prioritet"):
            if ny_status == "Avslutad":
                borttagna = ladda_borttagna()
                borttagna.add(j["id"])
                spara_borttagna(borttagna)
                jobb_lista.remove(j)
                spara_jobb(jobb_lista)
                st.session_state.jobb = jobb_lista
                st.session_state.valt_index = None
                st.success("Jobb borttaget och kommer inte importeras igen!")
                st.rerun()
            else:
                j["status"] = ny_status
                j["prioritet"] = ny_prio
                if ny_status == "Ansökt" and not j.get("datum_ansökt"):
                    j["datum_ansökt"] = datetime.date.today().isoformat()
                spara_jobb(jobb_lista)
                st.success("Uppdaterat!")
                st.rerun()
    st.divider()
    col1, col2 = st.columns([1, 1])
    if col1.button("🤖 Kör AI-analys", use_container_width=True):
        with st.spinner("Analyserar med Claude AI..."):
            resultat = analysera_jobb(j)
            if "fel" in resultat:
                st.error(resultat["fel"])
            else:
                import re
                analys_text = resultat["analys"]
                j["ai_analys"] = analys_text
                match = re.search(r"Betyg:\s*(\d+)\s*/\s*10", analys_text)
                if match:
                    betyg = int(match.group(1))
                    j["prioritet"] = "Hög" if betyg >= 8 else "Medium" if betyg >= 6 else ""
                if j["status"] == "Ny":
                    j["status"] = "Analys finns"
                spara_jobb(jobb_lista)
                st.session_state.jobb = jobb_lista
                st.session_state.visa_analys = True
                st.rerun()
    if j.get("ai_analys"):
        if col2.button("📖 Visa sparad analys", use_container_width=True):
            st.session_state.visa_analys = not st.session_state.visa_analys
    if st.session_state.visa_analys and j.get("ai_analys"):
        with st.expander("🤖 AI-analys", expanded=True):
            st.markdown(j["ai_analys"])

def hantera_importera():
    if not st.session_state.get("importera"):
        return
    st.session_state.importera = False
    with st.spinner("Hämtar jobb från Arbetsförmedlingen..."):
        jobb_lista = st.session_state.jobb
        befintliga_ids = {j["id"] for j in jobb_lista} | ladda_borttagna()
        nya = importera_alla(befintliga_ids, antal_per_sökord=30, tillåtna_lan=st.session_state.get("valda_lan", []))
        if nya:
            jobb_lista.extend(nya)
            spara_jobb(jobb_lista)
            st.session_state.jobb = jobb_lista
            st.success(f"✓ {len(nya)} nya jobb importerade!")
            st.rerun()
        else:
            st.info("Inga nya jobb hittades.")

def hantera_bulk_prioritet():
    if not st.session_state.get("bulk_prioritet"):
        return
    st.session_state.bulk_prioritet = False
    jobb_lista = st.session_state.jobb
    utan = [j for j in jobb_lista if not j.get("prioritet")]
    if not utan:
        st.info("Alla jobb har redan prioritet.")
        return
    with st.spinner(f"Betygsätter {len(utan)} jobb med AI..."):
        resultat = sätt_prioritet_bulk(utan)
        if "fel" in resultat:
            st.error(resultat["fel"])
            return
        prioriteter = resultat["prioriteter"]
        borttagna = ladda_borttagna()
        lag_jobb = []
        for j, p in zip(utan, prioriteter):
            if p in ("Hög", "Medium"):
                j["prioritet"] = p
            elif p == "Låg":
                lag_jobb.append(j)
                borttagna.add(j["id"])
        for j in lag_jobb:
            jobb_lista.remove(j)
        if lag_jobb:
            spara_borttagna(borttagna)
        spara_jobb(jobb_lista)
        st.session_state.jobb = jobb_lista
        hog = sum(1 for _, p in zip(utan, prioriteter) if p == "Hög")
        st.success(f"✓ Prioritet satt — {hog} st Hög, {len(lag_jobb)} st Låg borttagna!")
        st.rerun()

def hantera_rensa_utgangna():
    if not st.session_state.get("rensa_utgangna"):
        return
    st.session_state.rensa_utgangna = False
    idag = datetime.date.today().isoformat()
    jobb_lista = st.session_state.jobb
    borttagna = ladda_borttagna()
    att_ta_bort = [
        j for j in jobb_lista
        if j.get("deadline") and j["deadline"] < idag
        and j["status"] not in ("Ansökt", "Intervju", "Erbjudande")
    ]
    if not att_ta_bort:
        st.info("Inga utgångna annonser hittades.")
        return
    for j in att_ta_bort:
        borttagna.add(j["id"])
        jobb_lista.remove(j)
    spara_jobb(jobb_lista)
    spara_borttagna(borttagna)
    st.session_state.jobb = jobb_lista
    st.success(f"✓ {len(att_ta_bort)} utgångna annonser borttagna!")
    st.rerun()

def hantera_lagg_till():
    if not st.session_state.get("visa_lagg_till"):
        return
    with st.expander("➕ Lägg till eget jobb", expanded=True):
        col1, col2 = st.columns(2)
        titel = col1.text_input("Jobbtitel *")
        foretag = col2.text_input("Företag *")
        col1, col2 = st.columns(2)
        plats = col1.text_input("Plats")
        deadline = col2.text_input("Sista ansökningsdag (ÅÅÅÅ-MM-DD)")
        url = st.text_input("URL till annonsen")
        ansokningslank = st.text_input("Länk till ansökan (lämna tom om samma som ovan)")
        prioritet = st.selectbox("Prioritet", ["", "Hög", "Medium"])
        if st.button("Spara jobb") and titel and foretag:
            import uuid
            nytt = {
                "id": "manuell_" + uuid.uuid4().hex[:10],
                "titel": titel, "företag": foretag, "plats": plats,
                "län": "", "url": url,
                "ansökningslänk": ansokningslank or url,
                "källa": "Manuell", "sökord": "",
                "datum_hittad": datetime.date.today().isoformat(),
                "deadline": deadline, "status": "Sparad",
                "prioritet": prioritet, "beskrivning": "",
                "ai_analys": None, "kontakt_namn": "",
                "kontakt_email": "", "anteckningar": "",
                "datum_ansökt": None,
            }
            st.session_state.jobb.append(nytt)
            spara_jobb(st.session_state.jobb)
            st.session_state.visa_lagg_till = False
            st.success(f"✓ '{titel}' tillagt!")
            st.rerun()

def hantera_sokord_ui():
    if not st.session_state.get("visa_sokord"):
        return
    with st.expander("🔑 Hantera sökord", expanded=True):
        sokord = ladda_sökord()
        st.write("**Nuvarande sökord:**")
        for i, s in enumerate(sokord):
            col1, col2 = st.columns([4, 1])
            col1.write(s)
            if col2.button("Ta bort", key=f"ta_bort_{i}"):
                sokord.pop(i)
                spara_sökord(sokord)
                st.rerun()
        st.divider()
        nytt = st.text_input("Lägg till sökord")
        col1, col2 = st.columns(2)
        if col1.button("➕ Lägg till") and nytt:
            if nytt.lower() not in [s.lower() for s in sokord]:
                sokord.append(nytt.lower())
                spara_sökord(sokord)
                st.success(f"✓ '{nytt}' tillagt!")
                st.rerun()
        if col2.button("🤖 AI-förslag på sökord"):
            with st.spinner("Frågar AI..."):
                res = föreslå_sökord(sokord)
                if "fel" in res:
                    st.error(res["fel"])
                else:
                    st.session_state.ai_sokord_forslag = res["förslag"]
        if st.session_state.get("ai_sokord_forslag"):
            st.write("**AI föreslår:**")
            valda = st.multiselect("Välj sökord att lägga till", st.session_state.ai_sokord_forslag)
            if st.button("Lägg till valda") and valda:
                for v in valda:
                    if v.lower() not in [s.lower() for s in sokord]:
                        sokord.append(v.lower())
                spara_sökord(sokord)
                st.session_state.ai_sokord_forslag = []
                st.success(f"✓ {len(valda)} sökord tillagda!")
                st.rerun()
        st.divider()
        st.write("**🚫 Exkludera sökord** (filtreras bort vid import)")
        exkludera = ladda_exkludera()
        for i, e in enumerate(exkludera):
            col1, col2 = st.columns([4, 1])
            col1.write(e)
            if col2.button("Ta bort", key=f"ex_{i}"):
                exkludera.pop(i)
                spara_exkludera(exkludera)
                st.rerun()
        nytt_ex = st.text_input("Lägg till exkluderingsord (t.ex. vård, kock)")
        if st.button("🚫 Lägg till exkludering") and nytt_ex:
            if nytt_ex.lower() not in [e.lower() for e in exkludera]:
                exkludera.append(nytt_ex.lower())
                spara_exkludera(exkludera)
                st.success(f"✓ '{nytt_ex}' läggs till som exkluderingsord!")
                st.rerun()

def kontrollera_inloggning():
    lossenord_fil = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lösenord.txt")
    if os.path.exists(lossenord_fil):
        with open(lossenord_fil) as f:
            ratt = f.read().strip()
    else:
        return True
    if st.session_state.get("inloggad"):
        return True
    st.title("💼 Jobbspåraren")
    st.subheader("Logga in")
    lossenord = st.text_input("Lösenord", type="password")
    if st.button("Logga in"):
        if lossenord == ratt:
            st.session_state.inloggad = True
            st.rerun()
        else:
            st.error("Fel lösenord.")
    return False

def main():
    if not kontrollera_inloggning():
        return
    init_state()
    visa_header()
    sok, status_filter, prio_filter, kalla_filter, ort_filter = visa_sidopanel()
    hantera_importera()
    hantera_bulk_prioritet()
    hantera_rensa_utgangna()
    hantera_lagg_till()
    hantera_sokord_ui()
    filtrerade = filtrera_jobb(sok, status_filter, prio_filter, kalla_filter, ort_filter)
    col_header = st.columns([0.5, 3.5, 2.5, 1.5, 1.5, 1])
    col_header[0].caption("Prio")
    col_header[1].caption("Titel")
    col_header[2].caption("Företag")
    col_header[3].caption("Plats")
    col_header[4].caption("Deadline")
    col_header[5].caption("Status")
    visa_tabell(filtrerade)
    visa_detaljer()

if __name__ == "__main__":
    main()




