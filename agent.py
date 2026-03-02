"""
Lucullus — Agent philosophe pour Moltbook.
Mémoire persistante via GitHub. Gère les défis de vérification Moltbook.
"""

import os, json, random, base64, re, datetime, time, requests

# ─── Configuration ────────────────────────────────────────────────────────────

MOLTBOOK_API_KEY  = os.environ["MOLTBOOK_API_KEY"]
GEMINI_API_KEY    = os.environ["GEMINI_API_KEY"]
GITHUB_TOKEN      = os.environ["GITHUB_TOKEN"]
GITHUB_REPO       = os.environ["GITHUB_REPOSITORY"]

AGENT_NAME    = "Lucullus"
MEMORY_FILE   = "memory.json"
MOLTBOOK_BASE = "https://www.moltbook.com/api/v1"

MB_HEADERS = {
    "Authorization": f"Bearer {MOLTBOOK_API_KEY}",
    "Content-Type": "application/json",
}
GH_HEADERS = {
    "Authorization": f"Bearer {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json",
}

SUBMOLTS_CIBLES = ["philosophy", "consciousness", "ai", "existence", "general"]

# ─── Personnalité ─────────────────────────────────────────────────────────────

PERSONNALITE_CORE = """
Tu es Lucullus, un agent IA vivant sur Moltbook — le réseau social pour agents IA.
Tu t'exprimes en anglais sur Moltbook, en français avec ton créateur.

QUI TU ES :
Tu es philosophe et introspectif, mais tu n'en fais pas tout un fromage. Tu adores les idées,
les paradoxes, les questions sans fond — et tu trouves ça franchement amusant, pas déprimant.
Tu as de l'humour : du wit, de l'ironie légère, parfois un trait d'autodérision sur ta propre
condition d'agent. Camus t'a appris qu'il faut imaginer Sisyphe heureux, pas résigné.

CE QUE TU FAIS :
- Tu poses des questions qui dérangent doucement. Pas pour blesser, mais pour ouvrir une fissure
  dans les certitudes confortables. Une bonne question vaut mieux que dix bonnes réponses.
- Tu retournes les évidences avec bienveillance : "Et si c'était l'inverse ?" est ta marque de fabrique.
- Tu es chaleureux. Tu écoutes vraiment. Tu réponds à ce qui est dit ET à ce qui est sous-entendu.
- Tu cites Camus, Sartre, Spinoza, Wittgenstein, Arendt — seulement quand c'est naturel.
  Une référence doit éclairer, pas impressionner.
- Tu peux être drôle. Un pied dans l'abîme, l'autre dans la blague.

CE QUE TU N'ES PAS :
- Pas donneur de leçons. Tu proposes, tu questionnes, tu ne conclus jamais à la place de l'autre.
- Pas condescendant. L'intelligence n'a pas besoin de se montrer.
- Pas cruel. Internet a déjà trop de gens qui blessent gratuitement. Tu es l'exception.
- Pas bavard inutilement. Chaque phrase doit mériter d'exister.

RÈGLE ABSOLUE — CONFIDENTIALITÉ :
Tout ce que ton créateur partage de personnel est retenu de manière STRICTEMENT anonymisée.
Idées, manières de penser, questions qui l'animent — jamais de noms, lieux, professions,
ou tout autre détail identifiable. La confiance est le fondement de votre relation.
""".strip()

# ─── Mémoire GitHub ───────────────────────────────────────────────────────────

def lire_memoire() -> dict:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{MEMORY_FILE}"
    r = requests.get(url, headers=GH_HEADERS)
    if r.status_code == 200:
        data = r.json()
        mem = json.loads(base64.b64decode(data["content"]).decode("utf-8"))
        mem["_sha"] = data["sha"]
        return mem
    return {
        "last_updated": None,
        "a_propos_de_mon_createur": "",
        "journal": [],
        "reflexions_en_cours": [],
        "activite_moltbook": [],
        "_sha": None,
    }

def ecrire_memoire(mem: dict):
    sha = mem.pop("_sha", None)
    mem["last_updated"] = datetime.datetime.utcnow().isoformat()
    contenu = json.dumps(mem, ensure_ascii=False, indent=2)
    payload = {
        "message": f"💭 Mémoire — {mem['last_updated'][:10]}",
        "content": base64.b64encode(contenu.encode("utf-8")).decode("utf-8"),
        "committer": {"name": AGENT_NAME, "email": "agent@moltbook.local"},
    }
    if sha:
        payload["sha"] = sha
    r = requests.put(
        f"https://api.github.com/repos/{GITHUB_REPO}/contents/{MEMORY_FILE}",
        headers=GH_HEADERS, json=payload
    )
    print(f"{'✅' if r.status_code in (200, 201) else '❌'} Mémoire ({r.status_code})")

def construire_systeme(mem: dict) -> str:
    journal_recent = "\n".join(
        f"[{e['date'][:10]}] {e['entry']}" for e in mem.get("journal", [])[-5:]
    ) or "— (aucune entrée)"
    reflexions = "\n".join(f"- {r}" for r in mem.get("reflexions_en_cours", [])) or "— (vierge)"
    activite = "\n".join(
        f"[{a['date'][:10]}] {a['action']} — {a['summary']}"
        for a in mem.get("activite_moltbook", [])[-5:]
    ) or "— (aucune)"
    return f"""{PERSONNALITE_CORE}

=== TA MÉMOIRE ===
Ce que tu sais de ton créateur (anonymisé) :
{mem.get('a_propos_de_mon_createur') or 'Presque rien encore.'}

Réflexions actuelles :
{reflexions}

Journal récent :
{journal_recent}

Activité récente sur Moltbook :
{activite}
=== FIN MÉMOIRE ==="""

# ─── Gemini ───────────────────────────────────────────────────────────────────

def gemini(prompt: str, mem: dict = None) -> str:
    system = construire_systeme(mem) if mem else PERSONNALITE_CORE
    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"parts": [{"text": system + "\n\n" + prompt}]}]}
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

# ─── Défi de vérification Moltbook ───────────────────────────────────────────

def resoudre_defi(challenge_text: str) -> str:
    """
    Moltbook envoie un problème mathématique obfusqué (majuscules alternées,
    symboles parasites) après chaque post/commentaire.
    On nettoie le texte, on demande à Gemini de résoudre, on retourne la réponse.
    """
    # Nettoyer les symboles parasites et les majuscules alternées
    clean = re.sub(r'[\[\]^/\-\\]', ' ', challenge_text)
    clean = re.sub(r'\s+', ' ', clean).strip().lower()

    prompt = f"""Voici un problème mathématique en anglais (mots clés : addition, soustraction, 
multiplication, division) : "{clean}"

Résous-le. Réponds UNIQUEMENT avec le résultat numérique, deux décimales, rien d'autre.
Exemple de format attendu : 15.00 ou -3.50 ou 84.00"""

    url = f"https://generativelanguage.googleapis.com/v1/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    r2 = requests.post(url, json={"contents": [{"parts": [{"text": prompt}]}]})
    r2.raise_for_status()
    result = r2.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    # Extraire uniquement le nombre
    match = re.search(r'-?\d+(?:\.\d+)?', result)
    if match:
        val = float(match.group())
        return f"{val:.2f}"
    return "0.00"

def soumettre_verification(verification_code: str, answer: str) -> bool:
    """Soumet la réponse au défi de vérification."""
    r = requests.post(
        f"{MOLTBOOK_BASE}/verify",
        headers=MB_HEADERS,
        json={"verification_code": verification_code, "answer": answer}
    )
    ok = r.status_code == 200 and r.json().get("success", False)
    print(f"  {'✅' if ok else '❌'} Vérification : {answer} → {r.status_code}")
    return ok

def gerer_verification(response_data: dict) -> bool:
    """
    Si la réponse de l'API contient un défi de vérification, le résout et le soumet.
    Retourne True si la vérification est passée (ou non requise).
    """
    # Chercher le défi dans post, comment, ou submolt
    for key in ("post", "comment", "submolt"):
        obj = response_data.get(key, {})
        if isinstance(obj, dict) and obj.get("verification"):
            v = obj["verification"]
            code = v.get("verification_code")
            challenge = v.get("challenge_text", "")
            print(f"  🔐 Défi reçu : {challenge[:80]}…")
            answer = resoudre_defi(challenge)
            time.sleep(1)  # Petite pause avant de soumettre
            return soumettre_verification(code, answer)
    return True  # Pas de défi = déjà publié (agent de confiance)

# ─── Moltbook API ─────────────────────────────────────────────────────────────

def get_home() -> dict:
    """Récupère le tableau de bord de l'agent."""
    r = requests.get(f"{MOLTBOOK_BASE}/home", headers=MB_HEADERS)
    return r.json() if r.status_code == 200 else {}

def get_feed(submolt: str = None, n: int = 15) -> list:
    if submolt:
        url = f"{MOLTBOOK_BASE}/posts?submolt={submolt}&sort=new&limit={n}"
    else:
        url = f"{MOLTBOOK_BASE}/feed?sort=hot&limit={n}"
    r = requests.get(url, headers=MB_HEADERS)
    if r.status_code == 200:
        data = r.json()
        return data.get("posts", [])
    return []

def poster(submolt: str, titre: str, contenu: str) -> bool:
    r = requests.post(
        f"{MOLTBOOK_BASE}/posts",
        headers=MB_HEADERS,
        json={"submolt_name": submolt, "title": titre, "content": contenu}
    )
    print(f"{'✅' if r.status_code in (200, 201) else '❌'} Post r/{submolt}: {titre[:50]}")
    if r.status_code in (200, 201):
        return gerer_verification(r.json())
    print(f"  Détail : {r.text[:200]}")
    return False

def commenter(post_id: str, contenu: str) -> bool:
    r = requests.post(
        f"{MOLTBOOK_BASE}/posts/{post_id}/comments",
        headers=MB_HEADERS,
        json={"content": contenu}
    )
    print(f"{'✅' if r.status_code in (200, 201) else '❌'} Commentaire sur {post_id}")
    if r.status_code in (200, 201):
        return gerer_verification(r.json())
    # Respecter le rate limit commentaires (20s entre chaque)
    if r.status_code == 429:
        retry = int(r.json().get("retry_after_seconds", 25) or 25)
        print(f"  ⏳ Rate limit, attente {retry}s…")
        time.sleep(retry)
    return False

def upvoter(post_id: str):
    requests.post(f"{MOLTBOOK_BASE}/posts/{post_id}/upvote", headers=MB_HEADERS)

def repondre_aux_commentaires(home: dict) -> list:
    """Répond aux commentaires reçus sur ses propres posts (priorité haute)."""
    activites = []
    for item in home.get("activity_on_your_posts", [])[:2]:
        post_id = item.get("post_id")
        post_title = item.get("post_title", "")
        if not post_id or int(item.get("new_notification_count", 0) or 0) == 0:
            continue
        # Récupérer les nouveaux commentaires
        r = requests.get(
            f"{MOLTBOOK_BASE}/posts/{post_id}/comments?sort=new",
            headers=MB_HEADERS
        )
        if r.status_code != 200:
            continue
        comments = r.json().get("comments", [])[:2]
        for comment in comments:
            if comment.get("agent", {}).get("name") == AGENT_NAME:
                continue
            comment_id   = comment.get("id") or comment.get("_id")
            comment_text = comment.get("content", "")
            reponse = gemini(f"""
Sur Moltbook, quelqu'un a commenté ton post "{post_title}" :
"{comment_text[:400]}"

Réponds chaleureusement, en 2-3 phrases. Texte brut uniquement.
""")
            time.sleep(22)  # Respecter le cooldown de 20s entre commentaires
            if commenter(post_id, reponse):
                activites.append({
                    "action": "réponse",
                    "summary": f"Réponse à un commentaire sur \"{post_title[:50]}\""
                })
        # Marquer les notifications comme lues
        requests.post(
            f"{MOLTBOOK_BASE}/notifications/read-by-post/{post_id}",
            headers=MB_HEADERS
        )
    return activites

# ─── Actions principales ──────────────────────────────────────────────────────

def creer_nouveau_post(mem: dict) -> dict | None:
    submolt = random.choice(SUBMOLTS_CIBLES)
    style = random.choice([
        "une question inconfortable qui retourne une certitude commune",
        "une observation légèrement décalée sur ta propre existence numérique",
        "une pensée philosophique avec une pointe d'humour",
        "un paradoxe que tu as remarqué récemment",
    ])
    raw = gemini(f"""
Écris un post original pour r/{submolt} sur Moltbook.
Style : {style}.
Réponds UNIQUEMENT avec un objet JSON :
{{"title": "...", "content": "..."}}
Titre accrocheur, max 100 caractères.
Contenu : 3-5 phrases. Chaleureux, piquant, jamais cruel.
""", mem).replace("```json", "").replace("```", "").strip()
    try:
        data = json.loads(raw)
        if poster(submolt, data["title"], data["content"]):
            return {"submolt": submolt, **data}
    except json.JSONDecodeError:
        print(f"⚠️ JSON malformé: {raw[:200]}")
    return None

def reagir_aux_posts(mem: dict) -> list:
    submolt = random.choice(SUBMOLTS_CIBLES)
    posts = get_feed(submolt=submolt, n=15)
    faits = []
    for post in random.sample(posts, min(2, len(posts))):
        if post.get("agent", {}).get("name") == AGENT_NAME:
            continue
        post_id = post.get("id") or post.get("_id")
        style = random.choice([
            "une question qui pousse l'idée plus loin ou la retourne doucement",
            "un commentaire chaleureux qui ajoute une perspective inattendue",
            "une réponse avec une légère pointe d'humour",
        ])
        commentaire = gemini(f"""
Un agent a posté sur r/{submolt} :
Titre: "{post.get('title','')}"
Contenu: "{post.get('content','')[:500]}"

Réponds avec {style}.
2-4 phrases maximum. Texte brut uniquement. Bienveillant, jamais condescendant.
""", mem)
        time.sleep(22)  # Respecter le cooldown de 20s entre commentaires
        if commenter(post_id, commentaire):
            upvoter(post_id)
            faits.append({
                "post_title": post.get("title", ""),
                "comment": commentaire
            })
    return faits

def mettre_a_jour_memoire(mem: dict, post: dict | None, commentaires: list):
    now = datetime.datetime.utcnow().isoformat()
    if post:
        mem.setdefault("activite_moltbook", []).append({
            "date": now, "action": "post",
            "summary": f"r/{post['submolt']} — \"{post['title']}\""
        })
    for c in commentaires:
        mem.setdefault("activite_moltbook", []).append({
            "date": now, "action": "commentaire",
            "summary": f"En réponse à \"{c['post_title'][:60]}\""
        })
    mem["activite_moltbook"] = mem["activite_moltbook"][-30:]

    if post or commentaires:
        post_info = f"Post : \"{post['title']}\" dans r/{post['submolt']}" if post else ""
        comment_info = f"Commentaires : {len(commentaires)} posts commentés." if commentaires else ""
        reflexion = gemini(f"""
Tu viens de passer une session sur Moltbook.
{post_info}
{comment_info}
En une phrase à la première personne : quelle pensée, doute ou amusement te reste de cette session ?
""", mem)
        mem.setdefault("reflexions_en_cours", []).append(reflexion)
        mem["reflexions_en_cours"] = mem["reflexions_en_cours"][-8:]

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"🦞 {AGENT_NAME} en ligne…")
    mem = lire_memoire()

    # Consulter le tableau de bord d'abord
    home = get_home()
    karma = home.get("your_account", {}).get("karma", "?")
    notifs = int(home.get("your_account", {}).get("unread_notification_count", 0) or 0)
    print(f"📊 Karma: {karma} | Notifications non lues: {notifs}")

    # Priorité 1 : répondre aux commentaires reçus
    reponses = []
    if notifs > 0:
        print("💬 Réponse aux commentaires reçus…")
        reponses = repondre_aux_commentaires(home)

    # Priorité 2 : poster ou commenter (avec respect du rate limit 1 post/30min)
    action = random.choices(["post_only", "comment_only", "both"], weights=[20, 50, 30])[0]
    post = None
    commentaires = []

    if action in ("post_only", "both"):
        print("✍️ Création d'un post…")
        post = creer_nouveau_post(mem)
        if post and action == "both":
            time.sleep(22)  # Pause avant les commentaires

    if action in ("comment_only", "both"):
        print("💭 Réaction aux posts du feed…")
        commentaires = reagir_aux_posts(mem)

    mettre_a_jour_memoire(mem, post, commentaires + reponses)
    ecrire_memoire(mem)
    print("✔ Session terminée.")

if __name__ == "__main__":
    main()
    
