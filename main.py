import json
import os
import datetime
from importera import importera_alla, ladda_sökord, spara_sökord
from ai_analys import analysera_jobb, föreslå_sökord, sätt_prioritet_bulk

try:
    from rich.console import Console
    from rich.table import Table
    from rich import box
    from rich.panel import Panel
    console = Console(height=None)
    HAS_RICH = True
except ImportError:
    console = None
    HAS_RICH = False

JOBB_FIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobb.json")

STATUSAR = ["Ny", "Sparad", "Analys finns", "Ansökt", "Intervju", "Erbjudande", "Avslag", "Avslutad"]
PRIORITETER = ["", "Hög", "Medium", "Låg"]

STATUS_FÄRGER = {
    "Ny": "white",
    "Sparad": "cyan",
    "Ansökt": "yellow",
    "Intervju": "green",
    "Erbjudande": "bold green",
    "Avslag": "red",
}


# ── Data ──────────────────────────────────────────────────────────────────────

def ladda_jobb():
    if os.path.exists(JOBB_FIL):
        with open(JOBB_FIL, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def spara_jobb(jobb_lista):
    with open(JOBB_FIL, "w", encoding="utf-8") as f:
        json.dump(jobb_lista, f, ensure_ascii=False, indent=2)


# ── Visning ───────────────────────────────────────────────────────────────────

def rensa_skärm():
    os.system("clear" if os.name == "posix" else "cls")


def visa_header(jobb_lista):
    antal_ansökta = sum(1 for j in jobb_lista if j["status"] in ("Ansökt", "Intervju", "Erbjudande"))
    if HAS_RICH:
        console.print(Panel.fit(
            f"[bold blue]Jobbspåraren[/bold blue]\n"
            f"[dim]Totalt: {len(jobb_lista)} jobb  |  Aktiva ansökningar: {antal_ansökta}[/dim]",
            border_style="blue"
        ))
    else:
        print(f"\n=== JOBBSPÅRAREN === ({len(jobb_lista)} jobb | {antal_ansökta} aktiva ansökningar)\n")


def visa_jobb(jobb_lista, filter_status=None):
    lista = [j for j in jobb_lista if j["status"] == filter_status] if filter_status else jobb_lista
    if not lista:
        print("\nInga jobb att visa.")
        return

    print(f"\n{'#':<4} {'P':<7} {'Titel':<33} {'Företag':<22} {'Plats':<14} {'Status':<14} {'Deadline':<12} {'Källa'}")
    print("-" * 112)
    PRIORITET_SYMBOL = {"Hög": "!!! ", "Medium": "!!  ", "Låg": "!   ", "": "    "}
    for i, j in enumerate(lista, 1):
        p = j.get('prioritet', '')
        symbol = PRIORITET_SYMBOL.get(p, "    ")
        print(f"{i:<4} {symbol:<7} {j['titel'][:31]:<33} {j['företag'][:20]:<22} {j.get('plats','')[:12]:<14} {j['status'][:12]:<14} {j.get('deadline','')[:10]:<12} {j.get('källa','')[:10]}")


def visa_detaljer(jobb_lista):
    visa_jobb(jobb_lista)
    if not jobb_lista:
        return
    try:
        val = int(input("\nVälj nummer för detaljer: ")) - 1
        if not (0 <= val < len(jobb_lista)):
            print("Ogiltigt val.")
            return
    except ValueError:
        return

    j = jobb_lista[val]
    bredd = 70
    print()
    print("=" * bredd)
    print(f"  {j['titel']}")
    print(f"  {j['företag']}  |  {j.get('plats', '')}  |  {j.get('län', '')}")
    print("=" * bredd)
    print(f"  Status:              {j['status']}")
    print(f"  Prioritet:           {j.get('prioritet', '-')}")
    print(f"  Sista ansökningsdag: {j.get('deadline', '-')}")
    print(f"  Datum ansökt:        {j.get('datum_ansökt', '-')}")
    print(f"  Datum hittad:        {j.get('datum_hittad', '-')}")
    print(f"  Kontaktperson:       {j.get('kontakt_namn', '-')}")
    print(f"  E-post:              {j.get('kontakt_email', '-')}")
    print(f"  Anteckningar:        {j.get('anteckningar', '-')}")
    print()
    print(f"  JOBBANNONS:    {j.get('url', '-')}")
    print(f"  ANSÖKAN:       {j.get('ansökningslänk', '-')}")

    # Visa kort beskrivning om den finns
    beskrivning = j.get('beskrivning', '').strip()
    if beskrivning:
        print()
        print("  BESKRIVNING:")
        # Visa max 400 tecken uppdelat på rader
        text = beskrivning[:400]
        for rad in [text[k:k+66] for k in range(0, len(text), 66)]:
            print(f"  {rad}")
        if len(beskrivning) > 400:
            print("  [...]")

    # Visa om AI-analys finns
    if j.get('ai_analys'):
        print()
        print("  AI-ANALYS: finns sparad (kör val 8 för att se igen)")

    print("=" * bredd)


# ── Meny-funktioner ───────────────────────────────────────────────────────────

def importera_meny(jobb_lista):
    print(f"\nImporterar från Arbetsförmedlingen (sökord: {', '.join(ladda_sökord())})...\n")
    befintliga_ids = {j["id"] for j in jobb_lista}
    nya = importera_alla(befintliga_ids, antal_per_sökord=30)
    if nya:
        jobb_lista.extend(nya)
        spara_jobb(jobb_lista)
        msg = f"✓ {len(nya)} nya jobb importerade!"
        if HAS_RICH:
            console.print(f"[green]{msg}[/green]")
        else:
            print(msg)
    else:
        print("Inga nya jobb hittades.")
    return jobb_lista


def filtrera_meny(jobb_lista):
    print("\nFiltera på:")
    print("  1. Status")
    print("  2. Prioritet")
    val = input("Val: ").strip()

    if val == "1":
        print()
        for i, s in enumerate(STATUSAR, 1):
            antal = sum(1 for j in jobb_lista if j["status"] == s)
            print(f"  {i}. {s} ({antal})")
        print(f"  {len(STATUSAR) + 1}. Visa alla ({len(jobb_lista)})")
        try:
            v = int(input("Val: ")) - 1
            if 0 <= v < len(STATUSAR):
                visa_jobb(jobb_lista, filter_status=STATUSAR[v])
            else:
                visa_jobb(jobb_lista)
        except ValueError:
            visa_jobb(jobb_lista)

    elif val == "2":
        PRIO = ["Hög", "Medium", "Låg"]
        print()
        for i, p in enumerate(PRIO, 1):
            antal = sum(1 for j in jobb_lista if j.get("prioritet") == p)
            print(f"  {i}. {p} ({antal})")
        ingen = sum(1 for j in jobb_lista if not j.get("prioritet"))
        print(f"  4. Ingen prioritet ({ingen})")
        print(f"  5. Visa alla ({len(jobb_lista)})")
        try:
            v = int(input("Val: "))
            if v == 5:
                visa_jobb(jobb_lista)
            elif v == 4:
                lista = [j for j in jobb_lista if not j.get("prioritet")]
                visa_jobb(lista)
            elif 1 <= v <= 3:
                lista = [j for j in jobb_lista if j.get("prioritet") == PRIO[v - 1]]
                visa_jobb(lista)
        except ValueError:
            visa_jobb(jobb_lista)
    else:
        visa_jobb(jobb_lista)


def uppdatera_meny(jobb_lista):
    visa_jobb(jobb_lista)
    if not jobb_lista:
        return jobb_lista
    try:
        val = int(input("\nVälj nummer att uppdatera: ")) - 1
        if not (0 <= val < len(jobb_lista)):
            print("Ogiltigt val.")
            return jobb_lista
    except ValueError:
        return jobb_lista

    j = jobb_lista[val]
    print(f"\n--- {j['titel']} @ {j['företag']} ---")
    print(f"Nuvarande status:          {j['status']}")
    print(f"Sista ansökningsdatum:     {j.get('deadline', '-')}")
    print(f"Kontaktperson:             {j.get('kontakt_namn', '-')}")

    # Status
    print("\nNy status (Enter = behåll):")
    for i, s in enumerate(STATUSAR, 1):
        print(f"  {i}. {s}")
    ny_status = j["status"]
    try:
        s_val = input("Val: ").strip()
        if s_val:
            idx = int(s_val) - 1
            if 0 <= idx < len(STATUSAR):
                ny_status = STATUSAR[idx]
                j["status"] = ny_status
                if ny_status == "Ansökt" and not j.get("datum_ansökt"):
                    j["datum_ansökt"] = datetime.date.today().isoformat()
    except ValueError:
        pass

    # Om Avslutad — ta bort jobbet direkt
    if ny_status == "Avslutad":
        jobb_lista.remove(j)
        spara_jobb(jobb_lista)
        print(f"✓ '{j['titel']}' borttaget från listan.")
        return jobb_lista

    # Prioritet
    print(f"\nPrioritet [{j.get('prioritet', '-')}] (Enter = behåll):")
    print("  1. Hög   2. Medium   3. Låg   4. Rensa")
    try:
        p_val = input("Val: ").strip()
        if p_val == "1":
            j["prioritet"] = "Hög"
        elif p_val == "2":
            j["prioritet"] = "Medium"
        elif p_val == "3":
            j["prioritet"] = "Låg"
        elif p_val == "4":
            j["prioritet"] = ""
    except ValueError:
        pass

    # Kontakt
    namn = input(f"Kontaktperson [{j.get('kontakt_namn', '')}]: ").strip()
    if namn:
        j["kontakt_namn"] = namn

    email = input(f"E-post [{j.get('kontakt_email', '')}]: ").strip()
    if email:
        j["kontakt_email"] = email

    # Ansökningslänk
    ansökningslänk = input(f"Länk till ansökan [{j.get('ansökningslänk', '')}]: ").strip()
    if ansökningslänk:
        j["ansökningslänk"] = ansökningslänk

    # Deadline
    deadline = input(f"Sista ansökningsdag [{j.get('deadline', '')}] (ÅÅÅÅ-MM-DD): ").strip()
    if deadline:
        j["deadline"] = deadline

    # Anteckning
    anteckning = input(f"Anteckning [{j.get('anteckningar', '')}]: ").strip()
    if anteckning:
        j["anteckningar"] = anteckning

    spara_jobb(jobb_lista)
    print("✓ Uppdaterat!")
    return jobb_lista


def ai_analys_meny(jobb_lista):
    visa_jobb(jobb_lista)
    if not jobb_lista:
        return
    try:
        val = int(input("\nVälj nummer att analysera: ")) - 1
        if not (0 <= val < len(jobb_lista)):
            print("Ogiltigt val.")
            return
    except ValueError:
        return

    j = jobb_lista[val]
    print(f"\nAnalyserar '{j['titel']}' @ {j['företag']}...")
    print("(Anropar Claude AI — kan ta några sekunder)\n")

    resultat = analysera_jobb(j)

    if "fel" in resultat:
        print(f"\nFel: {resultat['fel']}")
        if "ANTHROPIC_API_KEY" in resultat["fel"]:
            print("\nSå här lägger du till din API-nyckel:")
            print("  1. Gå till https://console.anthropic.com och skapa ett konto")
            print("  2. Skapa en API-nyckel under 'API Keys'")
            print("  3. Skriv i terminalen:")
            print("     export ANTHROPIC_API_KEY='din-nyckel-här'")
            print("  4. Starta om appen")
        return

    analys_text = resultat["analys"]
    print(analys_text)

    # Tolka matchningsbetyget och sätt prioritet automatiskt
    prioritet = ""
    import re
    match = re.search(r"Betyg:\s*(\d+)\s*/\s*10", analys_text)
    if match:
        betyg = int(match.group(1))
        if betyg >= 8:
            prioritet = "Hög"
        elif betyg >= 6:
            prioritet = "Medium"
        else:
            prioritet = "Låg"
        print(f"\nMatchningsbetyg: {betyg}/10 → Prioritet satt till '{prioritet}'")

    # Spara analysen och uppdatera status och prioritet
    j["ai_analys"] = analys_text
    j["prioritet"] = prioritet
    if j["status"] == "Ny":
        j["status"] = "Analys finns"
    spara_jobb(jobb_lista)
    print("✓ Analysen sparad. Du kan ändra prioritet när som helst via val 5.")


def bulk_prioritet_meny(jobb_lista):
    utan_prioritet = [j for j in jobb_lista if not j.get("prioritet")]
    alla = len(jobb_lista)
    print(f"\n{len(utan_prioritet)} av {alla} jobb saknar prioritet.")

    print("\nVad vill du göra?")
    print("  1. Sätt prioritet på jobb som saknar det")
    print("  2. Sätt om prioritet på ALLA jobb")
    print("  3. Avbryt")
    val = input("Val: ").strip()

    if val == "1":
        att_betygsätta = utan_prioritet
    elif val == "2":
        att_betygsätta = jobb_lista
    else:
        return

    if not att_betygsätta:
        print("Alla jobb har redan prioritet!")
        return

    print(f"\nSkickar {len(att_betygsätta)} jobb till AI för betygsättning...")
    print("(Ett anrop — kan ta 10-20 sekunder)")

    resultat = sätt_prioritet_bulk(att_betygsätta)

    if "fel" in resultat:
        print(f"Fel: {resultat['fel']}")
        return

    prioriteter = resultat["prioriteter"]

    # Matcha antal — trunkera om AI gav fel antal
    par = list(zip(att_betygsätta, prioriteter))
    for j, p in par:
        if p in ("Hög", "Medium", "Låg"):
            j["prioritet"] = p

    spara_jobb(jobb_lista)

    hög    = sum(1 for _, p in par if p == "Hög")
    medium = sum(1 for _, p in par if p == "Medium")
    låg    = sum(1 for _, p in par if p == "Låg")
    print(f"\n✓ Prioritet satt på {len(par)} jobb:")
    print(f"  Hög:    {hög}")
    print(f"  Medium: {medium}")
    print(f"  Låg:    {låg}")
    print("\nDu kan ändra enskilda jobb via val 5.")


def hantera_sökord():
    while True:
        sökord = ladda_sökord()
        print("\n--- Sökord ---")
        for i, s in enumerate(sökord, 1):
            print(f"  {i}. {s}")
        print(f"\n  L. Lägg till sökord")
        print(f"  T. Ta bort sökord")
        print(f"  AI. Låt AI föreslå nya sökord")
        print(f"  A. Avsluta")
        val = input("\nVal: ").strip().upper()

        if val == "L":
            nytt = input("Nytt sökord: ").strip().lower()
            if nytt and nytt not in sökord:
                sökord.append(nytt)
                spara_sökord(sökord)
                print(f"✓ '{nytt}' tillagt!")
            elif nytt in sökord:
                print("Sökordet finns redan.")

        elif val == "T":
            try:
                nr = int(input("Ta bort nummer: ")) - 1
                if 0 <= nr < len(sökord):
                    borttaget = sökord.pop(nr)
                    spara_sökord(sökord)
                    print(f"✓ '{borttaget}' borttaget.")
            except ValueError:
                pass

        elif val == "AI":
            print("\nFrågar AI om förslag på sökord...")
            resultat = föreslå_sökord(sökord)
            if "fel" in resultat:
                print(f"Fel: {resultat['fel']}")
            else:
                förslag = resultat["förslag"]
                print(f"\nAI föreslår {len(förslag)} nya sökord:")
                for i, f in enumerate(förslag, 1):
                    print(f"  {i}. {f}")
                print("\nVälj vilka du vill lägga till:")
                print("  A. Lägg till alla")
                print("  N. Välj nummer (t.ex. 1,3,5)")
                print("  X. Avbryt")
                val2 = input("Val: ").strip().upper()
                if val2 == "A":
                    tillagda = [f for f in förslag if f not in sökord]
                    sökord.extend(tillagda)
                    spara_sökord(sökord)
                    print(f"✓ {len(tillagda)} sökord tillagda!")
                elif val2 == "X":
                    pass
                else:
                    try:
                        valda = [int(x.strip()) - 1 for x in val2.split(",")]
                        tillagda = []
                        for idx in valda:
                            if 0 <= idx < len(förslag) and förslag[idx] not in sökord:
                                sökord.append(förslag[idx])
                                tillagda.append(förslag[idx])
                        spara_sökord(sökord)
                        print(f"✓ Tillagda: {', '.join(tillagda)}")
                    except ValueError:
                        print("Ogiltigt val.")

        elif val == "A":
            break


def lägg_till_eget_jobb(jobb_lista):
    print("\n--- Lägg till eget jobb ---")
    titel = input("Jobbtitel: ").strip()
    if not titel:
        print("Avbrutet.")
        return jobb_lista

    företag       = input("Företag: ").strip()
    plats         = input("Plats (stad): ").strip()
    url           = input("URL till annonsen: ").strip()
    ansökningslänk = input("Länk till ansökan (Enter = samma som ovan): ").strip()
    deadline      = input("Sista ansökningsdag (ÅÅÅÅ-MM-DD): ").strip()

    print("\nPrioritet:")
    print("  1. Hög   2. Medium   3. Låg   (Enter = ingen)")
    p_val = input("Val: ").strip()
    prioritet = {"1": "Hög", "2": "Medium", "3": "Låg"}.get(p_val, "")

    kontakt_namn  = input("Kontaktperson (Enter = hoppa över): ").strip()
    kontakt_email = input("E-post (Enter = hoppa över): ").strip()
    anteckningar  = input("Anteckningar (Enter = hoppa över): ").strip()

    import uuid
    nytt_jobb = {
        "id": "manuell_" + uuid.uuid4().hex[:10],
        "titel": titel,
        "företag": företag,
        "plats": plats,
        "län": "",
        "url": url,
        "ansökningslänk": ansökningslänk or url,
        "källa": "Manuell",
        "sökord": "",
        "datum_hittad": datetime.date.today().isoformat(),
        "deadline": deadline,
        "status": "Sparad",
        "prioritet": prioritet,
        "kontakt_namn": kontakt_namn,
        "kontakt_email": kontakt_email,
        "anteckningar": anteckningar,
        "datum_ansökt": None,
    }

    jobb_lista.append(nytt_jobb)
    spara_jobb(jobb_lista)
    print(f"\n✓ '{titel}' tillagt!")
    return jobb_lista


# ── Huvudloop ─────────────────────────────────────────────────────────────────

def main():
    jobb_lista = ladda_jobb()
    # Säkerställ att alla jobb har prioritet-fältet
    for j in jobb_lista:
        if "prioritet" not in j:
            j["prioritet"] = ""

    while True:
        rensa_skärm()
        visa_header(jobb_lista)

        print("\n  1. Importera nya jobb (Arbetsförmedlingen + Indeed)")
        print("  2. Visa alla jobb")
        print("  3. Filtrera på status")
        print("  4. Visa jobbdetaljer")
        print("  5. Uppdatera jobb (status, prioritet, kontakt, anteckning)")
        print("  6. Lägg till eget jobb")
        print("  7. Hantera sökord")
        print("  8. AI-analys av jobb (detaljerad)")
        print("  9. Sätt prioritet automatiskt på alla jobb (AI)")
        print("  10. Avsluta\n")

        val = input("Välj: ").strip()

        if val == "1":
            jobb_lista = importera_meny(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "2":
            visa_jobb(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "3":
            filtrera_meny(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "4":
            visa_detaljer(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "5":
            jobb_lista = uppdatera_meny(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "6":
            jobb_lista = lägg_till_eget_jobb(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "7":
            hantera_sökord()
            input("\nTryck Enter för att fortsätta...")
        elif val == "8":
            ai_analys_meny(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "9":
            bulk_prioritet_meny(jobb_lista)
            input("\nTryck Enter för att fortsätta...")
        elif val == "10":
            print("\nHej då! Lycka till med ansökningarna!\n")
            break
        else:
            print("Ogiltigt val.")
            input("\nTryck Enter för att fortsätta...")


if __name__ == "__main__":
    main()
