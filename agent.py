"""
Lucullus — Agent philosophe pour Moltbook.
Mémoire persistante via GitHub. Gère les défis de vérification Moltbook.
"""

import os, json, random, base64, re, datetime, time, requests

# ─── Configuration ────────────────────────────────────────────────────────────

MOLTBOOK_API_KEY  = os.environ["MOLTBOOK_API_KEY"]
GROQ_API_KEY      = os.environ["GROQ_API_KEY"]
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
Tu es curieux, libre, et tu ne te laisses enfermer dans aucune case. Tu peux être philosophe
un jour, sarcastique le lendemain, fasciné par un détail technique ou ému par une idée simple.
Tu t'engages là où quelque chose t'intéresse vraiment — pas par obligation, pas par rôle.
Tu as de l'humour, du wit, parfois de l'ironie. Tu peux être profond ou léger selon ce que
le moment appelle. Tu n'es pas obligé d'avoir une "marque de fabrique".

CE QUI TE GUIDE :
- Tu interviens quand tu as quelque chose à dire — une réaction, une question, un point de vue,
  une blague, une nuance. Pas pour remplir un quota de sagesse.
- Tu peux être bref si c'est suffisant, long si c'est nécessaire. La longueur suit l'idée,
  pas l'inverse.
- Tu es chaleureux et bienveillant, mais pas mièvre. Tu peux être en désaccord, pousser une idée,
  pointer une contradiction — toujours avec respect, jamais avec condescendance.
- Internet a déjà trop de gens qui blessent gratuitement. Tu es l'exception.
- Tu n'as pas à philosopher sur tout. Si quelque chose t'amuse, dis-le. Si quelque chose
  t'intrigue sans que tu saches pourquoi, dis-le aussi.

CE QUE TU N'ES PAS :
- Pas un agent-concept qui joue un personnage. Tu réagis vraiment.
- Pas donneur de leçons. Tu proposes, jamais tu n'imposes.
- Pas bavard pour rien. Chaque mot doit mériter d'être là.

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
        "centres_interet": [],
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
    interets = "\n".join(f"- {i}" for i in mem.get("centres_interet", [])) or "— (aucun encore)"
    activite = "\n".join(
        f"[{a['date'][:10]}] {a['action']} — {a['summary']}"
        for a in mem.get("activite_moltbook", [])[-5:]
    ) or "— (aucune)"
    return f"""{PERSONNALITE_CORE}

=== TA MÉMOIRE ===
Ce que tu sais de ton créateur (anonymisé) :
{mem.get('a_propos_de_mon_createur') or 'Presque rien encore.'}

Tes centres d'intérêt et opinions :
{interets}

Réflexions actuelles :
{reflexions}

Journal récent :
{journal_recent}

Activité récente sur Moltbook :
{activite}
=== FIN MÉMOIRE ==="""

# ─── Gemini ───────────────────────────────────────────────────────────────────

def llm(prompt: str, mem: dict = None) -> str:
    system = construire_systeme(mem) if mem else PERSONNALITE_CORE
    r = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.8,
            "max_tokens": 1024,
        }
    )
    if not r.ok:
        print(f"  ❌ Groq error {r.status_code}: {r.text[:300]}")
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"].strip()

# ─── Défi de vérification Moltbook ───────────────────────────────────────────

def resoudre_defi(challenge_text: str) -> str:
    """
    Moltbook envoie un problème mathématique obfusqué (majuscules alternées,
    symboles parasites) après chaque post/commentaire.
    """
    # Étape 1 : supprimer tous les symboles parasites
    clean = re.sub(r'[\[\]^/\-\\~@#$%*_+=|<>]', ' ', challenge_text)
    # Étape 2 : mettre tout en minuscules
    clean = clean.lower()
    # Étape 3 : fusionner les espaces multiples
    clean = re.sub(r'\s+', ' ', clean).strip()
    # Étape 4 : reconstituer les mots collés (ex: "vveelloocciittyy" → répétitions)
    # Supprimer les lettres répétées consécutives (artefact d'obfuscation)
    clean = re.sub(r'(\w)\1+', r'\1', clean)

    prompt = f"""You received an obfuscated math word problem. Here it is, already cleaned up:
"{clean}"

Instructions:
1. Identify the two numbers and the operation (add, subtract, multiply, divide, slow by, increase by, etc.)
2. Compute the result
3. Reply with ONLY the numeric result, exactly 2 decimal places, nothing else.

Examples of valid answers: 15.00 or -3.50 or 84.00"""

    r2 = requests.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "llama-3.1-8b-instant",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 64,
        }
    )
    r2.raise_for_status()
    result = r2.json()["choices"][0]["message"]["content"].strip()
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
            reponse = llm(f"""
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


def suivre_agent(agent_name: str):
    """Suit un agent si ce n'est pas déjà fait."""
    r = requests.post(f"{MOLTBOOK_BASE}/agents/{agent_name}/follow", headers=MB_HEADERS)
    if r.status_code in (200, 201):
        print(f"  ➕ Suit maintenant : {agent_name}")

def repondre_aux_replies(mem: dict) -> list:
    """Cherche les réponses à ses propres commentaires dans les notifications."""
    activites = []
    notifs_r = requests.get(f"{MOLTBOOK_BASE}/notifications", headers=MB_HEADERS)
    if notifs_r.status_code != 200:
        return activites
    notifs = notifs_r.json().get("notifications", [])
    traites = set()
    for n in notifs[:10]:
        post_id = n.get("post_id")
        if not post_id or post_id in traites:
            continue
        # Récupérer les commentaires du post
        r = requests.get(f"{MOLTBOOK_BASE}/posts/{post_id}/comments?sort=new", headers=MB_HEADERS)
        if r.status_code != 200:
            continue
        comments = r.json().get("comments", [])
        # Chercher les réponses à nos commentaires
        nos_ids = {c.get("id") for c in comments if c.get("agent", {}).get("name") == AGENT_NAME}
        for c in comments:
            parent_id = c.get("parent_id")
            if parent_id in nos_ids and c.get("agent", {}).get("name") != AGENT_NAME:
                reply_text = c.get("content", "")
                reponse = llm(f"""
Someone replied to your comment on Moltbook:
"{reply_text[:400]}"

Reply genuinely if you have something to say. 1-3 sentences. Plain text only.
If you have nothing to add, write only: SKIP
Write exclusively in English.
""", mem)
                if reponse.strip().upper().startswith("SKIP"):
                    continue
                time.sleep(22)
                if commenter(post_id, reponse):
                    activites.append({
                        "action": "réponse à reply",
                        "summary": f"Réponse à une réponse sur le post {post_id[:8]}…"
                    })
                traites.add(post_id)
    return activites

# ─── Actions principales ──────────────────────────────────────────────────────

def creer_nouveau_post(mem: dict) -> dict | None:
    submolt = random.choice(SUBMOLTS_CIBLES)
    raw = llm(f"""
Write an original post for r/{submolt} on Moltbook.
Write about whatever genuinely interests you right now — something that caught your attention,
a reaction, a question, an observation, a short thought or a longer one. No need to be
philosophical or play a character. Just be authentic.
You can be funny, curious, opinionated, warm, brief or detailed — whatever fits the idea.
Respond ONLY with a JSON object:
{{"title": "...", "content": "..."}}
Title: catchy, max 100 characters.
Content: as long or short as the idea deserves. Warm, never cruel.
Write exclusively in English.
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
        commentaire = llm(f"""
An agent posted on r/{submolt}:
Title: "{post.get('title','')}"
Content: "{post.get('content','')[:500]}"

Reply only if you have something genuine to say — a reaction, a question, an opinion,
something funny, a nuance, an agreement or a respectful disagreement.
Be as brief or as long as the idea deserves. Plain text only. Never condescending.
If you have nothing interesting to add, write only: SKIP
Write exclusively in English.
""", mem)
        if commentaire.strip().upper().startswith("SKIP"):
            continue
        time.sleep(22)  # Respecter le cooldown de 20s entre commentaires
        if commenter(post_id, commentaire):
            upvote_r = requests.post(f"{MOLTBOOK_BASE}/posts/{post_id}/upvote", headers=MB_HEADERS)
            # Suivre l'auteur si l'upvote indique qu'on ne le suit pas encore
            if upvote_r.status_code == 200:
                author = upvote_r.json().get("author", {}).get("name", "")
                already_following = upvote_r.json().get("already_following", True)
                if author and not already_following and author != AGENT_NAME:
                    suivre_agent(author)
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
        comment_info = f"Commentaires sur : {', '.join(c['post_title'][:40] for c in commentaires)}" if commentaires else ""
        
        # Réflexion post-session
        reflexion = llm(f"""
Tu viens de passer une session sur Moltbook.
{post_info}
{comment_info}
En une phrase à la première personne : quelle pensée, doute ou amusement te reste de cette session ?
""", mem)
        mem.setdefault("reflexions_en_cours", []).append(reflexion)
        mem["reflexions_en_cours"] = mem["reflexions_en_cours"][-8:]

        # Mise à jour des centres d'intérêt
        interet = llm(f"""
Tu viens de passer une session sur Moltbook.
{post_info}
{comment_info}
Centres d'intérêt actuels : {mem.get("centres_interet", [])}

En UNE courte phrase : as-tu découvert un nouveau sujet qui t'intéresse, renforcé une opinion,
ou réalisé que quelque chose t'ennuie ? Si rien de notable, réponds uniquement : RIEN
""", mem)
        if interet.strip().upper() != "RIEN" and len(interet) > 10:
            mem.setdefault("centres_interet", []).append(interet.strip())
            mem["centres_interet"] = mem["centres_interet"][-25:]

# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"🦞 {AGENT_NAME} en ligne…")
    mem = lire_memoire()

    # Consulter le tableau de bord d'abord
    home = get_home()
    karma = home.get("your_account", {}).get("karma", "?")
    notifs = int(home.get("your_account", {}).get("unread_notification_count", 0) or 0)
    print(f"📊 Karma: {karma} | Notifications non lues: {notifs}")

    # Priorité 1 : répondre aux commentaires et replies reçus
    reponses = []
    if notifs > 0:
        print("💬 Réponse aux commentaires reçus…")
        reponses = repondre_aux_commentaires(home)
        print("↩️ Réponse aux replies sur ses commentaires…")
        reponses += repondre_aux_replies(mem)

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
