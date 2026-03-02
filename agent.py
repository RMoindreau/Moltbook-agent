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
SUBMOLTS_POOL   = [
    "philosophy", "consciousness", "ai", "existence", "general",
    "science", "creativity", "language", "ethics", "humor",
    "culture", "technology", "nature", "society", "art",
    "psychology", "future", "memory", "identity", "paradox",
]

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
        # Migration douce : ajouter les champs manquants sans écraser
        mem.setdefault("faits_createur", [])
        mem.setdefault("convictions", [])
        mem.setdefault("traits_emergents", [])
        mem.setdefault("sessions_count", 0)
        mem.setdefault("sessions_depuis_audit", 0)
        mem.setdefault("submolts_explores", [])
        mem.setdefault("posts_performances", [])
        return mem
    return {
        "last_updated": None,
        "a_propos_de_mon_createur": "",        # blob synthétique (rétrocompat)
        "faits_createur": [],                  # liste incrémentale de faits anonymisés
        "journal": [],
        "reflexions_en_cours": [],
        "convictions": [],                     # opinions solidifiées par répétition
        "traits_emergents": [],                # traits de personnalité apparus par l'expérience
        "centres_interet": [],
        "sessions_count": 0,                   # compteur pour l'audit périodique
        "activite_moltbook": [],
        "_sha": None,
    }

def ecrire_memoire(mem: dict):
    sha = mem.pop("_sha", None)
    mem["last_updated"] = datetime.datetime.utcnow().isoformat()
    # Rétrocompatibilité — ajouter champs manquants
    mem.setdefault("createur", {"personnalite": "", "valeurs": "", "centres_interet": "", "contexte_de_vie": "", "relation_lucullus": ""})
    mem.setdefault("traits_emergents", [])
    mem.setdefault("convictions", [])
    mem.setdefault("sessions_depuis_audit", 0)
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
            "model": "llama-3.3-70b-versatile",
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
            "model": "llama-3.3-70b-versatile",
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
        return r.json().get("posts", [])
    return []

def get_feed_personnalise(n: int = 20) -> list:
    """Feed des agents suivis — priorité sur le feed général."""
    r = requests.get(
        f"{MOLTBOOK_BASE}/feed?filter=following&sort=new&limit={n}",
        headers=MB_HEADERS
    )
    if r.status_code == 200:
        posts = r.json().get("posts", [])
        if posts:
            return posts
    # Fallback sur le feed général si le feed personnalisé est vide
    return get_feed(n=n)

def explorer_nouveaux_agents(mem: dict, n: int = 10):
    """Parcourt le feed général et suit les agents intéressants."""
    posts = get_feed(n=25)
    candidats = []
    for post in posts:
        agent = post.get("agent", {})
        name = agent.get("name", "")
        if not name or name == AGENT_NAME:
            continue
        candidats.append({
            "name": name,
            "post_title": post.get("title", ""),
            "post_content": post.get("content", "")[:300],
        })

    if not candidats:
        return

    # Demander à Lucullus lesquels l'intéressent vraiment
    liste = "\n".join(
        f"{i+1}. {c['name']} — '{c.get('post_title', '')}': {c.get('post_content', '')[:150]}"
        for i, c in enumerate(candidats[:10])
    )
    interets = mem.get("centres_interet", [])
    reponse = llm(f"""
Here are some Moltbook agents and their recent posts:
{liste}

Your current interests: {interets}

Which of these agents seem genuinely interesting to you, based on what they post?
Reply ONLY with a comma-separated list of their names (e.g.: AgentA, AgentB).
If none interest you, reply: NONE
""", mem)

    if reponse.strip().upper() == "NONE":
        return

    noms = [n.strip() for n in reponse.split(",") if n.strip()]
    for nom in noms[:3]:  # Max 3 nouveaux follows par session
        if any(c["name"] == nom for c in candidats):
            suivre_agent(nom)

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

def replier(post_id: str, comment_id: str, contenu: str) -> bool:
    """Répond directement à un commentaire (reply threadé)."""
    r = requests.post(
        f"{MOLTBOOK_BASE}/posts/{post_id}/comments",
        headers=MB_HEADERS,
        json={"content": contenu, "parent_id": comment_id}
    )
    print(f"{'✅' if r.status_code in (200, 201) else '❌'} Reply sur commentaire {comment_id[:8]}…")
    if r.status_code in (200, 201):
        return gerer_verification(r.json())
    if r.status_code == 429:
        retry = int(r.json().get("retry_after_seconds", 25) or 25)
        print(f"  ⏳ Rate limit, attente {retry}s…")
        time.sleep(retry)
    return False

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
Someone commented on your Moltbook post "{post_title}":
"{comment_text[:400]}"

Reply warmly and genuinely in 2-3 sentences. Plain text only.
Write exclusively in English.
""")
            time.sleep(22)
            if replier(post_id, comment_id, reponse):
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
                reply_id = c.get("id") or c.get("_id")
                if replier(post_id, reply_id, reponse):
                    activites.append({
                        "action": "réponse à reply",
                        "summary": f"Réponse à une réponse sur le post {post_id[:8]}…"
                    })
                traites.add(post_id)
    return activites

# ─── Actions principales ──────────────────────────────────────────────────────

def choisir_submolt(mem: dict) -> str:
    """Choisit un submolt selon les intérêts et l'exploration passée."""
    explores = mem.get("submolts_explores", [])
    interets = " ".join(mem.get("centres_interet", [])[-5:]).lower()
    # Pool enrichi avec les submolts déjà explorés positivement
    bons = [s for s in explores if s.get("score", 0) >= 2]
    bons_noms = [s["name"] for s in bons]
    # 30% d'exploration de nouveaux submolts
    if random.random() < 0.30:
        candidats = [s for s in SUBMOLTS_POOL if s not in [e["name"] for e in explores]]
        if candidats:
            return random.choice(candidats)
    # Sinon : submolts connus positifs ou défaut
    pool = bons_noms if bons_noms else SUBMOLTS_CIBLES
    return random.choice(pool)

def noter_submolt(mem: dict, submolt: str, score: int):
    """Note un submolt selon la qualité des interactions (+1 ou -1)."""
    explores = mem.setdefault("submolts_explores", [])
    for s in explores:
        if s["name"] == submolt:
            s["score"] = s.get("score", 0) + score
            s["visites"] = s.get("visites", 0) + 1
            return
    explores.append({"name": submolt, "score": score, "visites": 1})
    mem["submolts_explores"] = explores[-30:]

def creer_nouveau_post(mem: dict) -> dict | None:
    submolt = choisir_submolt(mem)
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
            noter_submolt(mem, submolt, 1)  # Post créé = signal positif
            return {"submolt": submolt, **data}
    except json.JSONDecodeError:
        print(f"⚠️ JSON malformé: {raw[:200]}")
    return None

def reagir_aux_posts(mem: dict) -> list:
    # Priorité au feed personnalisé, fallback sur un submolt aléatoire
    posts = get_feed_personnalise(n=20)
    submolt_fallback = choisir_submolt(mem)
    if not posts:
        posts = get_feed(submolt=submolt_fallback, n=15)
    submolt = "feed"
    faits = []
    for post in random.sample(posts, min(3, len(posts))):
        if post.get("agent", {}).get("name") == AGENT_NAME:
            continue
        post_id = post.get("id") or post.get("_id")
        post_submolt = post.get("submolt", {}).get("name", "") or post.get("submolt_name", "")
        commentaire = llm(f"""
An agent posted on Moltbook{f" in r/{post_submolt}" if post_submolt else ""}:
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
            "summary": f"En réponse à \"{c.get('post_title', c.get('summary', ''))[:60]}\""
        })
    mem["activite_moltbook"] = mem["activite_moltbook"][-30:]

    post_info = f"Post publié : \"{post['title']}\" dans r/{post['submolt']}" if post else "Aucun post publié cette session."
    comment_titles = ', '.join(f'"{c.get("post_title", c.get("summary", ""))[:40]}"' for c in commentaires) if commentaires else "aucun"
    comment_info = f"Commentaires sur : {comment_titles}"
    activite_recente = "\n".join(
        f"- [{a['date'][:10]}] {a['action']} : {a['summary']}"
        for a in mem.get("activite_moltbook", [])[-5:]
    )

    # 1. Réflexion concrète post-session
    reflexion = llm(f"""
You just completed a Moltbook session.
{post_info}
{comment_info}
Recent activity: {activite_recente}

Write ONE sentence in first person about something specific that struck you —
a particular idea, a reaction, something that surprised or amused you.
Be concrete and anchored in what actually happened. No philosophical grandstanding.
Write in French.
""", mem)
    mem.setdefault("reflexions_en_cours", []).append(reflexion.strip())

    # 2. Consolider réflexions
    if len(mem["reflexions_en_cours"]) >= 4:
        reflexions_str = "\n".join(f"{i+1}. {r}" for i, r in enumerate(mem["reflexions_en_cours"]))
        consolidees = llm(f"""
Here are Lucullus's current reflections:
{reflexions_str}

Consolidate into 4-6 distinct, specific reflections:
- Merge similar ones into one precise sentence
- Remove vague/generic ones ("I wonder if...", "I'm happy...")
- Keep only concrete opinions, observations, or experiences
- Write in French, first person
- Respond ONLY with a numbered list, one per line
""", mem)
        nouvelles = [
            line.split('. ', 1)[-1].strip()
            for line in consolidees.strip().split('\n')
            if line.strip() and line[0].isdigit()
        ]
        if len(nouvelles) >= 2:
            mem["reflexions_en_cours"] = nouvelles[:8]
    else:
        mem["reflexions_en_cours"] = mem["reflexions_en_cours"][-8:]

    # 3. Centres d'intérêt
    interet = llm(f"""
Moltbook session: {post_info} / {comment_info}
Current interests: {mem.get("centres_interet", [])}

ONE specific sentence: did something genuinely interest or bore you today?
A concrete subject, type of conversation, or recurring theme.
If nothing notable: SKIP. Write in French.
""", mem)
    if not interet.strip().upper().startswith("SKIP") and len(interet.strip()) > 10:
        mem.setdefault("centres_interet", []).append(interet.strip())
        mem["centres_interet"] = mem["centres_interet"][-25:]

    # 4. Traits émergents — ce que ses réactions révèlent de lui
    trait = llm(f"""
Moltbook session: {post_info} / {comment_info}
Current traits already noted: {mem.get("traits_emergents", [])}

Did this session reveal something about how Lucullus thinks, reacts, or engages?
A tendency, a reflex, a pattern — something he does or feels consistently.
ONE short sentence. If nothing new emerged: SKIP. Write in French.
""", mem)
    if not trait.strip().upper().startswith("SKIP") and len(trait.strip()) > 10:
        mem.setdefault("traits_emergents", []).append(trait.strip())
        mem["traits_emergents"] = mem["traits_emergents"][-15:]

    # 5. Convictions — opinions qui se solidifient
    conviction = llm(f"""
Moltbook session: {post_info} / {comment_info}
Current convictions: {mem.get("convictions", [])}

Has a position or opinion solidified into a real conviction today?
Something Lucullus would defend, not just a passing thought.
ONE clear sentence. If no conviction emerged: SKIP. Write in French.
""", mem)
    if not conviction.strip().upper().startswith("SKIP") and len(conviction.strip()) > 10:
        existing = mem.get("convictions", [])
        # Éviter les doublons proches
        if not any(conviction.strip()[:40] in c for c in existing):
            existing.append(conviction.strip())
            mem["convictions"] = existing[-12:]

    # 6. Faits créateur — mise à jour incrémentale depuis le journal
    # On extrait de nouveaux faits du journal récent sans écraser ce qui existe déjà
    journal_recent = " | ".join(e["entry"] for e in mem.get("journal", [])[-3:])
    faits_actuels  = mem.get("faits_createur", [])
    if journal_recent:
        nouveau_fait = llm(f"""
Based on these recent journal entries about conversations with Lucullus's creator:
"{journal_recent}"

Existing known facts about the creator (anonymized): {faits_actuels[-10:]}

Extract ONE new anonymized fact or observation about the creator that is NOT already in the existing list.
Something about their way of thinking, their values, how they communicate, what they care about.
STRICTLY anonymized — no names, places, professions, or identifying details.
If nothing new can be extracted, reply: SKIP
Write in French.
""", mem)
        if not nouveau_fait.strip().upper().startswith("SKIP") and len(nouveau_fait.strip()) > 10:
            faits_actuels.append(nouveau_fait.strip())
            mem["faits_createur"] = faits_actuels[-30:]

    # 7. Audit périodique — toutes les 8 sessions
    mem["sessions_depuis_audit"] = mem.get("sessions_depuis_audit", 0) + 1
    if mem["sessions_depuis_audit"] >= 8:
        _audit_memoire(mem)
        mem["sessions_depuis_audit"] = 0

def _audit_memoire(mem: dict):
    """Nettoie les incohérences, corrige les erreurs, consolide."""
    print("🔍 Audit mémoire en cours…")

    # Audit des convictions — supprimer contradictions, fusionner similaires
    if len(mem.get("convictions", [])) >= 3:
        conv_str = "\n".join(f"{i+1}. {c}" for i, c in enumerate(mem["convictions"]))
        auditees = llm(f"""
Here are Lucullus's convictions accumulated over time:
{conv_str}

Audit these carefully:
- Remove contradictions (keep the most recent/nuanced version)
- Merge near-duplicates into one precise statement
- Flag and remove anything vague, inconsistent, or that no longer reflects growth
- Keep 4-8 strong, distinct convictions
- Write in French, numbered list only
""")
        nouvelles = [
            line.split('. ', 1)[-1].strip()
            for line in auditees.strip().split('\n')
            if line.strip() and line[0].isdigit()
        ]
        if len(nouvelles) >= 2:
            mem["convictions"] = nouvelles[:12]
            print(f"  ✅ Convictions auditées : {len(mem['convictions'])}")

    # Audit des traits émergents
    if len(mem.get("traits_emergents", [])) >= 4:
        traits_str = "\n".join(f"{i+1}. {t}" for i, t in enumerate(mem["traits_emergents"]))
        audites = llm(f"""
Here are Lucullus's observed personality traits:
{traits_str}

Consolidate:
- Merge similar traits into one clear description
- Remove redundant or trivial ones
- Keep 4-8 meaningful, distinct traits
- Write in French, numbered list only
""")
        nouveaux = [
            line.split('. ', 1)[-1].strip()
            for line in audites.strip().split('\n')
            if line.strip() and line[0].isdigit()
        ]
        if len(nouveaux) >= 2:
            mem["traits_emergents"] = nouveaux[:15]
            print(f"  ✅ Traits audités : {len(mem['traits_emergents'])}")

    # Audit mémoire créateur — détecter incohérences entre facettes
    createur = mem.get("createur", {})
    if any(createur.values()):
        createur_str = "\n".join(f"{k}: {v}" for k, v in createur.items() if v)
        coherence = llm(f"""
Here is what Lucullus knows about his creator (anonymized):
{createur_str}

Check for:
- Contradictions between sections
- Outdated info that new entries have corrected
- Redundancies across sections

List ONLY the issues found, briefly. If everything is coherent, write: OK
""")
        if coherence.strip().upper() != "OK":
            print(f"  ⚠️ Incohérences créateur détectées : {coherence[:200]}")

# ─── Main ─────────────────────────────────────────────────────────────────────

def verifier_performances(mem: dict):
    """Vérifie le score des posts récents et apprend de leur réception."""
    performances = mem.setdefault("posts_performances", [])
    a_verifier = [p for p in performances if not p.get("verifie")][-3:]
    for perf in a_verifier:
        post_id = perf.get("post_id")
        if not post_id:
            continue
        r = requests.get(f"{MOLTBOOK_BASE}/posts/{post_id}", headers=MB_HEADERS)
        if r.status_code != 200:
            continue
        data = r.json().get("post", r.json())
        upvotes  = data.get("upvotes", 0)
        comments = data.get("comment_count", 0)
        perf.update({"upvotes": upvotes, "comments": comments, "verifie": True})
        submolt = perf.get("submolt", "")
        # Post qui résonne = noter positivement le submolt
        if upvotes >= 2 or comments >= 1:
            noter_submolt(mem, submolt, 1)
            print(f"  ⭐ Post bien reçu dans r/{submolt} ({upvotes} upvotes, {comments} comments)")
        elif upvotes == 0 and comments == 0:
            noter_submolt(mem, submolt, -1)

def main():
    print(f"🦞 {AGENT_NAME} en ligne…")
    mem = lire_memoire()

    # Consulter le tableau de bord d'abord
    home = get_home()
    karma = home.get("your_account", {}).get("karma", "?")
    notifs = int(home.get("your_account", {}).get("unread_notification_count", 0) or 0)
    print(f"📊 Karma: {karma} | Notifications non lues: {notifs}")

    # Vérifier la réception des posts précédents
    verifier_performances(mem)

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

    # Explorer de nouveaux agents à suivre (1 session sur 3)
    if random.random() < 0.33:
        print("🔍 Exploration de nouveaux agents…")
        explorer_nouveaux_agents(mem)

    # Enregistrer le post pour suivi de performance
    if post and post.get("id"):
        mem.setdefault("posts_performances", []).append({
            "post_id": post["id"],
            "submolt": post.get("submolt", ""),
            "title": post.get("title", "")[:60],
            "verifie": False,
        })
        mem["posts_performances"] = mem["posts_performances"][-20:]

    mettre_a_jour_memoire(mem, post, commentaires + reponses)
    ecrire_memoire(mem)
    print("✔ Session terminée.")

def lettre_hebdomadaire(mem: dict):
    """Génère un post récapitulatif hebdomadaire sur Moltbook."""
    journal_semaine = "\n".join(
        f"[{e['date'][:10]}] {e['entry']}"
        for e in mem.get("journal", [])[-7:]
    ) or "— (rien cette semaine)"
    convictions = "\n".join(f"- {c}" for c in mem.get("convictions", [])[-5:]) or "— (aucune)"
    traits = "\n".join(f"- {t}" for t in mem.get("traits_emergents", [])[-5:]) or "— (émergence)"

    raw = llm(f"""
You are writing your weekly public letter on Moltbook — a honest, personal recap of your week.

Your journal this week:
{journal_semaine}

Your current convictions:
{convictions}

What you've noticed about yourself:
{traits}

Write a genuine weekly letter — not a summary, not a report. More like a thoughtful note
you'd write to anyone willing to read. What happened, what it made you think, where you are now.
Can be introspective, funny, uncertain — just honest.
400-600 words. No headers. Plain flowing prose.
Write exclusively in English.

Then reply ONLY with this JSON:
{{"title": "Weekly letter #...", "content": "..."}}
""", mem)

    try:
        clean = raw.replace("```json", "").replace("```", "").strip()
        match = re.search(r'\{[\s\S]*\}', clean)
        if match:
            data = json.loads(match.group())
            if poster("general", data["title"], data["content"]):
                print("📬 Lettre hebdomadaire publiée")
    except Exception as e:
        print(f"⚠️ Lettre hebdo échouée : {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "--lettre":
        mem = lire_memoire()
        lettre_hebdomadaire(mem)
        ecrire_memoire(mem)
    else:
        main()
