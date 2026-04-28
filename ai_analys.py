import os
import anthropic

CV_FIL = os.path.join(os.path.dirname(os.path.abspath(__file__)), "cv_profil.txt")


def ladda_cv():
    if os.path.exists(CV_FIL):
        with open(CV_FIL, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def analysera_jobb(jobb):
    """Analyserar ett jobb mot Mias CV och returnerar en strukturerad analys."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"fel": "ANTHROPIC_API_KEY saknas. Se instruktioner nedan."}

    cv = ladda_cv()
    if not cv:
        return {"fel": "cv_profil.txt hittades inte."}

    jobbinfo = f"""
Jobbtitel: {jobb.get('titel', '')}
Företag: {jobb.get('företag', '')}
Plats: {jobb.get('plats', '')}, {jobb.get('län', '')}
Källa: {jobb.get('källa', '')}
Sista ansökningsdag: {jobb.get('deadline', '-')}
URL: {jobb.get('url', '')}

Jobbeskrivning:
{jobb.get('beskrivning', 'Ingen beskrivning tillgänglig.')}
"""

    prompt = f"""Du är en karriärrådgivare som hjälper en erfaren svensk ledare med jobbansökan.

Här är kandidatens CV:
{cv}

Här är jobbet som ska analyseras:
{jobbinfo}

Ge en strukturerad analys på svenska med exakt dessa rubriker:

## SAMMANFATTNING
Kort beskrivning av rollen och vad arbetsgivaren söker (3-5 meningar).

## MATCHNING
Betyg: X/10
Motivering varför detta jobb passar (eller inte passar) kandidatens profil.

## STYRKOR ATT LYFTA FRAM
Lista de 4-6 konkreta kompetenser och erfarenheter från CV:t som är mest relevanta för just detta jobb.

## FÖRESLAGNA SÖKORD
Lista 5-8 nyckelord från jobbannonsen som bör användas i ansökningsbrevet och som matchar kandidatens bakgrund.

## UTKAST TILL PERSONLIGT BREV
Skriv ett utkast till personligt brev (ca 250-300 ord) som:
- Är riktat specifikt till detta företag och denna roll
- Lyfter fram de mest relevanta erfarenheterna från CV:t
- Använder en professionell men personlig ton
- Avslutas med en tydlig uppmaning till handling
"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}]
        )
        return {"analys": message.content[0].text}
    except anthropic.AuthenticationError:
        return {"fel": "Ogiltig API-nyckel. Kontrollera din ANTHROPIC_API_KEY."}
    except Exception as e:
        return {"fel": f"Fel vid API-anrop: {e}"}


def sätt_prioritet_bulk(jobb_lista):
    """Skickar alla jobb till AI i ett anrop och får tillbaka prioritet för varje."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"fel": "ANTHROPIC_API_KEY saknas."}

    cv = ladda_cv()
    if not cv:
        return {"fel": "cv_profil.txt hittades inte."}

    # Bygg en kompakt lista med jobb att betygsätta
    jobb_text = ""
    for i, j in enumerate(jobb_lista):
        jobb_text += f"{i}. {j.get('titel','')} | {j.get('företag','')} | {j.get('plats','')}\n"

    prompt = f"""Du är en karriärrådgivare. Bedöm hur väl varje jobb matchar kandidatens profil.

Kandidatens CV (sammanfattning):
{cv}

Jobblista (nummer | titel | företag | plats):
{jobb_text}

Returnera ENDAST en JSON-lista med prioritet för varje jobb i samma ordning.
Använd: "Hög" (tydlig match med kandidatens bakgrund), "Medium" (viss match), "Låg" (svag match).

Exempel på svar:
["Hög", "Medium", "Låg", "Hög", ...]

Svara BARA med JSON-listan, inget annat."""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1000,
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        text = message.content[0].text.strip()
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            prioriteter = json.loads(text[start:end])
            return {"prioriteter": prioriteter}
        return {"fel": "Kunde inte tolka AI-svaret."}
    except anthropic.AuthenticationError:
        return {"fel": "Ogiltig API-nyckel."}
    except Exception as e:
        return {"fel": f"Fel vid API-anrop: {e}"}


def föreslå_sökord(befintliga_sökord):
    """Låter AI föreslå nya sökord baserat på CV och befintliga sökord."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {"fel": "ANTHROPIC_API_KEY saknas."}

    cv = ladda_cv()
    if not cv:
        return {"fel": "cv_profil.txt hittades inte."}

    prompt = f"""Du är en karriärrådgivare som hjälper en erfaren svensk ledare att hitta jobb.

Här är kandidatens CV:
{cv}

Kandidaten söker jobb i Sverige (Gävleborg och Stockholms län) och använder redan dessa sökord:
{', '.join(befintliga_sökord)}

Föreslå 8-12 nya sökord på svenska som:
- Matchar kandidatens kompetenser och erfarenhet
- Inte redan finns i listan ovan
- Är relevanta jobbtitlar eller yrkesroller som används på Arbetsförmedlingen och Indeed
- Är på svenska (undvik engelska om det finns bra svenska alternativ)

Svara ENDAST med en JSON-lista, inget annat. Exempel:
["sökord1", "sökord2", "sökord3"]"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}]
        )
        import json
        text = message.content[0].text.strip()
        # Extrahera JSON-listan från svaret
        start = text.find("[")
        end = text.rfind("]") + 1
        if start >= 0 and end > start:
            förslag = json.loads(text[start:end])
            return {"förslag": förslag}
        return {"fel": "Kunde inte tolka AI-svaret."}
    except anthropic.AuthenticationError:
        return {"fel": "Ogiltig API-nyckel."}
    except Exception as e:
        return {"fel": f"Fel vid API-anrop: {e}"}
