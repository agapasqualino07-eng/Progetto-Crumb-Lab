"""Generatore di bozze-sito per i lead in consegna.

Produce una landing page dimostrativa per lead (la "anteprima gratuita"
promessa nei copioni), usando SOLO i dati verificati del lead: niente
recensioni inventate, niente servizi non osservati. Le foto sono
segnaposto dichiarati, da sostituire con quelle vere del cliente.

Uso:
    python tools/genera_bozze.py            # legge tools/bozze_dati.json
Output in bozze/<data>/ (un .html autonomo per lead + index).
"""

import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
AGENZIA = "[NOME AGENZIA]"   # sostituire col nome vero prima di mostrare


def slug(testo: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", testo.lower())
    return s.strip("-")[:50]


# ---------------------------------------------------------------- CSS comune

CSS_BASE = """
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:Georgia,'Times New Roman',serif;color:var(--ink);background:var(--bg);line-height:1.6}
.sans{font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
a{color:inherit}
.wrap{max-width:1060px;margin:0 auto;padding:0 22px}
header{background:var(--hero);color:#fff;padding:16px 0}
nav{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap}
.logo{font-size:1.3rem;font-weight:bold;letter-spacing:.4px}
.tel-top{background:var(--accent);color:#fff;text-decoration:none;padding:9px 18px;border-radius:999px;font-weight:600;font-size:.95rem}
.hero{background:var(--hero);color:#fff;padding:72px 0 84px;position:relative;overflow:hidden}
.hero::after{content:"";position:absolute;inset:0;background:
 radial-gradient(ellipse 60% 50% at 85% 20%,rgba(255,255,255,.09),transparent),
 radial-gradient(ellipse 50% 60% at 10% 90%,rgba(255,255,255,.06),transparent)}
.hero .wrap{position:relative;z-index:1}
.kicker{text-transform:uppercase;letter-spacing:.18em;font-size:.78rem;opacity:.85}
h1{font-size:clamp(2rem,5vw,3.1rem);line-height:1.12;margin:.35em 0 .4em}
.sub{font-size:1.12rem;max-width:34em;opacity:.94}
.badge-row{display:flex;gap:12px;flex-wrap:wrap;margin-top:26px}
.badge{background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.35);
 padding:9px 16px;border-radius:10px;font-size:.92rem}
.badge b{font-size:1.15rem}
.cta-row{margin-top:30px;display:flex;gap:14px;flex-wrap:wrap}
.btn{display:inline-block;text-decoration:none;padding:14px 26px;border-radius:10px;
 font-weight:700;font-size:1rem}
.btn-primary{background:var(--accent);color:#fff}
.btn-ghost{border:2px solid rgba(255,255,255,.7);color:#fff}
section{padding:58px 0}
h2{font-size:1.7rem;margin-bottom:.4em}
.lead-p{max-width:44em;color:var(--muted)}
.grid{display:grid;gap:20px;margin-top:30px}
.g3{grid-template-columns:repeat(auto-fit,minmax(240px,1fr))}
.g4{grid-template-columns:repeat(auto-fit,minmax(200px,1fr))}
.card{background:var(--card);border-radius:14px;padding:24px;border:1px solid var(--line)}
.card h3{margin-bottom:.35em;font-size:1.08rem}
.card p{font-size:.95rem;color:var(--muted)}
.ph{border-radius:14px;aspect-ratio:4/3;display:flex;align-items:center;justify-content:center;
 color:#fff;font-family:sans-serif;font-size:.8rem;letter-spacing:.12em;text-transform:uppercase;
 text-align:center;padding:10px;background:
 repeating-linear-gradient(45deg,var(--ph1),var(--ph1) 14px,var(--ph2) 14px,var(--ph2) 28px)}
.alt{background:var(--alt)}
.strip{background:var(--hero);color:#fff;text-align:center;padding:46px 0}
.strip h2{margin-bottom:.3em}
.strip p{opacity:.9;max-width:38em;margin:0 auto 22px}
footer{background:#181818;color:#bbb;padding:34px 0;font-size:.88rem}
footer .disclaimer{margin-top:14px;padding-top:14px;border-top:1px solid #333;
 font-family:sans-serif;font-size:.8rem;color:#888}
.contatti-list{list-style:none;margin-top:18px;font-size:1.05rem}
.contatti-list li{margin:.45em 0}
@media(max-width:640px){.hero{padding:52px 0 60px}}
"""

PALETTE = {
    "bnb": ":root{--hero:#1d4e5f;--accent:#c96f2f;--bg:#fdfaf5;--card:#fff;"
           "--alt:#f4ede2;--ink:#26221c;--muted:#5c564c;--line:#e8dfd0;"
           "--ph1:#87a8b0;--ph2:#7799a2}",
    "edilizia": ":root{--hero:#2b3542;--accent:#d98e04;--bg:#f8f8f6;--card:#fff;"
                "--alt:#eef0ee;--ink:#20242a;--muted:#555c66;--line:#e2e4e0;"
                "--ph1:#9aa4ad;--ph2:#8c96a0}",
    "auto": ":root{--hero:#171b26;--accent:#c22f2f;--bg:#f7f7f8;--card:#fff;"
            "--alt:#ededf0;--ink:#1c1e24;--muted:#54565e;--line:#e1e1e6;"
            "--ph1:#8b8f9c;--ph2:#7d818e}",
}


def _pagina(d: dict, nicchia: str, corpo: str) -> str:
    tel_link = re.sub(r"[^\d+]", "", d["telefono"])
    return f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{d['nome']} — {d['citta']} · Bozza dimostrativa</title>
<style>{PALETTE[nicchia]}{CSS_BASE}</style>
</head>
<body>
<header><div class="wrap"><nav>
  <div class="logo">{d['nome']}</div>
  <a class="tel-top sans" href="tel:{tel_link}">📞 {d['telefono']}</a>
</nav></div></header>
{corpo}
<footer><div class="wrap">
  <b>{d['nome']}</b> — {d['indirizzo']}, {d['citta']} · Tel. {d['telefono']}
  <div class="disclaimer">⚠️ BOZZA DIMOSTRATIVA non in linea, preparata da {AGENZIA} —
  anteprima gratuita e senza impegno. Dati da fonti pubbliche (da confermare con il
  titolare); le immagini sono segnaposto da sostituire con le foto reali dell'attività.</div>
</div></footer>
</body></html>"""


# ---------------------------------------------------------------- template B&B

def bozza_bnb(d: dict) -> str:
    tel_link = re.sub(r"[^\d+]", "", d["telefono"])
    badges = "".join(f'<div class="badge sans">{b}</div>' for b in d["badge"])
    ph = "".join(f'<div class="ph">{p}</div>'
                 for p in ["Foto · La struttura", "Foto · Le camere",
                           "Foto · La colazione", "Foto · I dintorni"])
    corpo = f"""
<div class="hero"><div class="wrap">
  <div class="kicker sans">Bed &amp; Breakfast · {d['citta']}</div>
  <h1>{d['h1']}</h1>
  <p class="sub">{d['sottotitolo']}</p>
  <div class="badge-row">{badges}</div>
  <div class="cta-row sans">
    <a class="btn btn-primary" href="#contatti">Prenota in diretta — senza commissioni</a>
    <a class="btn btn-ghost" href="https://wa.me/{re.sub(r'[^0-9]', '', d['whatsapp'])}">Scrivici su WhatsApp</a>
  </div>
</div></div>
<section><div class="wrap">
  <h2>Perché prenotare direttamente da noi</h2>
  <p class="lead-p">Prenotando dal nostro sito parli direttamente con chi ti ospita:
  miglior prezzo garantito senza intermediari, risposta immediata su WhatsApp e
  consigli veri su cosa vedere.</p>
  <div class="grid g3">
    <div class="card"><h3>💶 Miglior prezzo diretto</h3><p>Nessuna commissione di
    portale: il prezzo che vedi è quello che va a chi ti accoglie.</p></div>
    <div class="card"><h3>💬 Contatto immediato</h3><p>Telefono e WhatsApp diretti:
    richieste particolari, orari di arrivo, consigli sul posto.</p></div>
    <div class="card"><h3>📍 {d['posizione_titolo']}</h3><p>{d['posizione_testo']}</p></div>
  </div>
</div></section>
<section class="alt"><div class="wrap">
  <h2>La struttura</h2>
  <p class="lead-p">Le foto qui sotto sono segnaposto: nella versione definitiva
  ci saranno gli ambienti veri, fotografati bene.</p>
  <div class="grid g4">{ph}</div>
</div></section>
<div class="strip"><div class="wrap">
  <h2>{d['strip_titolo']}</h2>
  <p>{d['strip_testo']}</p>
  <a class="btn btn-primary sans" href="#contatti">Controlla le date</a>
</div></div>
<section id="contatti"><div class="wrap">
  <h2>Dove siamo &amp; contatti</h2>
  <ul class="contatti-list">
    <li>📍 {d['indirizzo']}, {d['citta']}</li>
    <li>📞 <a href="tel:{tel_link}">{d['telefono']}</a></li>
    <li>💬 WhatsApp: {d['whatsapp']}</li>
  </ul>
</div></section>"""
    return _pagina(d, "bnb", corpo)


# ------------------------------------------------------------ template edilizia

def bozza_edilizia(d: dict) -> str:
    tel_link = re.sub(r"[^\d+]", "", d["telefono"])
    badges = "".join(f'<div class="badge sans">{b}</div>' for b in d["badge"])
    servizi = "".join(f'<div class="card"><h3>{t}</h3><p>{p}</p></div>'
                      for t, p in d["servizi"])
    ph = "".join(f'<div class="ph">{p}</div>'
                 for p in ["Cantiere · Prima", "Cantiere · Dopo",
                           "Lavoro in corso", "Dettaglio finiture"])
    corpo = f"""
<div class="hero"><div class="wrap">
  <div class="kicker sans">Impresa edile · {d['citta']} e provincia</div>
  <h1>{d['h1']}</h1>
  <p class="sub">{d['sottotitolo']}</p>
  <div class="badge-row">{badges}</div>
  <div class="cta-row sans">
    <a class="btn btn-primary" href="#contatti">Richiedi un sopralluogo gratuito</a>
    <a class="btn btn-ghost" href="tel:{tel_link}">Chiama ora</a>
  </div>
</div></div>
<section><div class="wrap">
  <h2>Cosa facciamo</h2>
  <div class="grid g3">{servizi}</div>
</div></section>
<section class="alt"><div class="wrap">
  <h2>I nostri lavori</h2>
  <p class="lead-p">Qui andranno le foto vere dei cantieri — il prima e dopo che
  vale più di mille parole. Questi sono segnaposto.</p>
  <div class="grid g4">{ph}</div>
</div></section>
<div class="strip"><div class="wrap">
  <h2>{d['strip_titolo']}</h2>
  <p>{d['strip_testo']}</p>
  <a class="btn btn-primary sans" href="#contatti">Parliamone senza impegno</a>
</div></div>
<section id="contatti"><div class="wrap">
  <h2>Contatti</h2>
  <ul class="contatti-list">
    <li>📍 {d['indirizzo']}, {d['citta']}</li>
    <li>📞 <a href="tel:{tel_link}">{d['telefono']}</a></li>
  </ul>
</div></section>"""
    return _pagina(d, "edilizia", corpo)


# ---------------------------------------------------------------- template auto

def bozza_auto(d: dict) -> str:
    tel_link = re.sub(r"[^\d+]", "", d["telefono"])
    badges = "".join(f'<div class="badge sans">{b}</div>' for b in d["badge"])
    servizi = "".join(f'<div class="card"><h3>{t}</h3><p>{p}</p></div>'
                      for t, p in d["servizi"])
    ph = "".join(f'<div class="ph">Foto veicolo<br>+ prezzo + km</div>' for _ in range(4))
    corpo = f"""
<div class="hero"><div class="wrap">
  <div class="kicker sans">{d['kicker']}</div>
  <h1>{d['h1']}</h1>
  <p class="sub">{d['sottotitolo']}</p>
  <div class="badge-row">{badges}</div>
  <div class="cta-row sans">
    <a class="btn btn-primary" href="#parco">Guarda il parco auto</a>
    <a class="btn btn-ghost" href="tel:{tel_link}">Chiama il salone</a>
  </div>
</div></div>
<section id="parco"><div class="wrap">
  <h2>Il parco auto, sempre aggiornato</h2>
  <p class="lead-p">Nella versione definitiva questa vetrina si aggiorna da sola
  con gli annunci veri (foto, prezzo, km, anno) — senza lavoro in più per voi.
  Questi sono segnaposto.</p>
  <div class="grid g4">{ph}</div>
</div></section>
<section class="alt"><div class="wrap">
  <h2>I nostri servizi</h2>
  <div class="grid g3">{servizi}</div>
</div></section>
<div class="strip"><div class="wrap">
  <h2>{d['strip_titolo']}</h2>
  <p>{d['strip_testo']}</p>
  <a class="btn btn-primary sans" href="#contatti">Vieni a trovarci</a>
</div></div>
<section id="contatti"><div class="wrap">
  <h2>Dove siamo</h2>
  <ul class="contatti-list">
    <li>📍 {d['indirizzo']}, {d['citta']}</li>
    <li>📞 <a href="tel:{tel_link}">{d['telefono']}</a></li>
  </ul>
</div></section>"""
    return _pagina(d, "auto", corpo)


TEMPLATE = {"bnb": bozza_bnb, "edilizia": bozza_edilizia, "auto": bozza_auto}


def genera(dati_path: Path, out_dir: Path) -> list[tuple[str, str]]:
    dati = json.loads(dati_path.read_text(encoding="utf-8"))
    out_dir.mkdir(parents=True, exist_ok=True)
    creati = []
    for d in dati:
        html = TEMPLATE[d["nicchia"]](d)
        nome_file = f"{slug(d['nome'])}.html"
        (out_dir / nome_file).write_text(html, encoding="utf-8")
        creati.append((d["nome"], nome_file))
    # indice
    righe = "".join(
        f'<li><a href="{f}">{n}</a></li>' for n, f in creati)
    (out_dir / "index.html").write_text(
        f"""<!DOCTYPE html><html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex"><title>Bozze del {date.today():%d/%m/%Y}</title>
<style>body{{font-family:sans-serif;max-width:640px;margin:40px auto;padding:0 20px;
line-height:1.8}}h1{{font-size:1.4rem}}</style></head><body>
<h1>🔦 Faro — bozze siti del {date.today():%d/%m/%Y}</h1>
<p>Anteprime dimostrative da portare (o mandare su WhatsApp) agli appuntamenti.</p>
<ol>{righe}</ol></body></html>""", encoding="utf-8")
    return creati


if __name__ == "__main__":
    dati = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tools" / "bozze_dati.json"
    out = ROOT / "bozze" / f"{date.today():%Y-%m-%d}"
    creati = genera(dati, out)
    print(f"✅ {len(creati)} bozze generate in {out}")
    for n, f in creati:
        print(f" - {n} → {f}")
