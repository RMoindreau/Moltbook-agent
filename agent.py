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
        f"{i+1}. {c['name']} — '{c['post_title']}': {c['post_content'][:150]}"
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
a reaction, a question, an observation, a short thought or a longer one. No ne