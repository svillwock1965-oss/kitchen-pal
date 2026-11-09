#!/usr/bin/env python3
"""Data-broker opt-out helper.

  python3 optout.py emails     # write a legal deletion-request email for each broker to outbox/
  python3 optout.py send       # actually send them via your SMTP (Gmail app password)
  python3 optout.py checklist  # walk through web-form opt-outs one by one, tracking progress
  python3 optout.py status     # show what's done

Your details live in me.json (copy me.example.json). me.json is git-ignored.
"""
import json, sys, smtplib, webbrowser, datetime, pathlib
from email.message import EmailMessage

HERE = pathlib.Path(__file__).parent
# (name, opt-out web form, privacy email or None). Emails are best-effort; bounces = check the site's privacy policy.
BROKERS = [
    ("Spokeo", "https://www.spokeo.com/optout", "privacy@spokeo.com"),
    ("Whitepages", "https://www.whitepages.com/suppression-requests", "support@whitepages.com"),
    ("BeenVerified", "https://www.beenverified.com/app/optout/search", "privacy@beenverified.com"),
    ("PeopleConnect (Intelius, TruthFinder, Instant Checkmate, US Search, ZabaSearch)", "https://suppression.peopleconnect.us/login", "privacy@peopleconnect.us"),
    ("PeopleFinders", "https://www.peoplefinders.com/opt-out", "privacy@peoplefinders.com"),
    ("Radaris", "https://radaris.com/control/privacy", "customer-service@radaris.com"),
    ("MyLife", "https://www.mylife.com/ccpa/index.pubview", "privacy@mylife.com"),
    ("FastPeopleSearch", "https://www.fastpeoplesearch.com/removal", None),
    ("TruePeopleSearch", "https://www.truepeoplesearch.com/removal", None),
    ("USPhoneBook", "https://www.usphonebook.com/opt-out", None),
    ("ThatsThem", "https://thatsthem.com/optout", None),
    ("Nuwber", "https://nuwber.com/removal/link", "support@nuwber.com"),
    ("ClustrMaps", "https://clustrmaps.com/bl/opt-out", None),
    ("FamilyTreeNow", "https://www.familytreenow.com/optout", None),
    ("PeekYou", "https://www.peekyou.com/about/contact/optout", None),
    ("Addresses.com / AnyWho / PeopleLooker", "https://www.peoplelooker.com/opt-out", None),
    ("Acxiom", "https://isapps.acxiom.com/optout/optout.aspx", "consumeradvo@acxiom.com"),
    ("LexisNexis", "https://optout.lexisnexis.com/", None),
    ("Epsilon", "https://www.epsilon.com/us/consumer-preference-center", "privacy@epsilon.com"),
    ("Experian marketing lists", "https://www.optoutprescreen.com/", None),
    ("CoreLogic", "https://www.corelogic.com/privacy-center/", "privacy@corelogic.com"),
]

def load_me():
    p = HERE / "me.json"
    if not p.exists():
        sys.exit("Copy me.example.json to me.json and fill in your details first.")
    return json.loads(p.read_text())

def letter(me, broker):
    names = ", ".join([me["full_name"], *me.get("other_names", [])])
    addrs = "\n  ".join([me["current_address"], *me.get("past_addresses", [])])
    return f"""To the Privacy Team at {broker}:

I am requesting that you DELETE all personal information you hold about me, and that you
stop selling or sharing it, under every applicable privacy law, including the California
Consumer Privacy Act / CPRA (Cal. Civ. Code 1798.105 and 1798.120), and the comparable
state privacy laws in Virginia, Colorado, Connecticut, Texas, Oregon, and other states.
If none of those laws covers me, please honor this as a voluntary opt-out request.

Please also remove me from all people-search listings, marketing lists, and data you
license to third parties, and tell me which third parties you sold or shared my data with.

Identifying information (use it ONLY to find and delete my records):
  Name(s): {names}
  Address(es):
  {addrs}
  Phone: {me.get('phone','')}
  Email: {me['email']}
  Birth year: {me.get('birth_year','')}

Please confirm in writing when you have done this. The law requires a response within 45 days.

Sincerely,
{me['full_name']}
{datetime.date.today():%B %d, %Y}
"""

def build(me):
    out = HERE / "outbox"; out.mkdir(exist_ok=True)
    msgs = []
    for name, _, addr in BROKERS:
        if not addr: continue
        m = EmailMessage()
        m["From"], m["To"] = me["smtp"]["user"] or me["email"], addr
        m["Subject"] = f"Personal data deletion and opt-out request - {me['full_name']}"
        m.set_content(letter(me, name))
        (out / f"{name.split()[0]}.eml").write_bytes(bytes(m))
        msgs.append(m)
    return msgs

def progress():
    p = HERE / "progress.json"
    return json.loads(p.read_text()) if p.exists() else {}

def save(pr): (HERE / "progress.json").write_text(json.dumps(pr, indent=2))

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "help"
    if cmd == "emails":
        print(f"Wrote {len(build(load_me()))} request emails to outbox/")
    elif cmd == "send":
        me = load_me(); s = me["smtp"]; msgs = build(me); pr = progress()
        if input(f"Send {len(msgs)} emails from {s['user']}? (yes/no) ") != "yes": return
        with smtplib.SMTP(s["host"], s["port"]) as srv:
            srv.starttls(); srv.login(s["user"], s["app_password"])
            for m in msgs:
                srv.send_message(m); print("sent ->", m["To"])
                pr[f"email:{m['To']}"] = str(datetime.date.today())
        save(pr)
    elif cmd == "checklist":
        me = load_me(); pr = progress()
        print(f"Search for: {me['full_name']}, {me['current_address']}\n"
              "On each site: find your listing(s), request removal, solve the CAPTCHA, then "
              "click the confirmation link they email you.\n")
        for name, url, _ in BROKERS:
            if pr.get(f"web:{name}"): continue
            print(f"\n== {name}\n   {url}")
            try: webbrowser.open(url)
            except Exception: pass
            a = input("   [d]one / [s]kip / [n]ot listed / [q]uit: ").strip().lower()
            if a == "q": break
            if a in ("d", "n"): pr[f"web:{name}"] = f"{a} {datetime.date.today()}"; save(pr)
    elif cmd == "status":
        pr = progress()
        for name, _, addr in BROKERS:
            print(f"{name:60} web:{pr.get('web:'+name,'-'):14} email:{pr.get('email:'+str(addr),'-') if addr else 'n/a'}")
        print("\nRe-check every 3-6 months - brokers re-add people from new records.")
    else:
        print(__doc__)

if __name__ == "__main__":
    main()
