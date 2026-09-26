# Wypad

Codziennie rano automat szuka tanich city breaków z Poznania i okolic: lot w obie strony + bagaż + nocleg dla 2 osób, w jednej cenie. Wyniki trafiają do aplikacji (PWA), którą można zainstalować na iPhonie. Do tego push na telefon (ntfy) i e-mail.

- **Aplikacja:** `site/`. Statyczna strona (HTML/CSS/JS, bez budowania), hostowana za darmo na GitHub Pages.
- **Wyszukiwanie:** `pipeline/`. Python, uruchamiany raz dziennie przez GitHub Actions (`.github/workflows/daily.yml`).
- **Research źródeł i decyzje:** `docs/RESEARCH.md`. **Wymagania:** `docs/WYMAGANIA.md`.

Koszt: 0 zł. Źródła danych (Ryanair, trivago, Open-Meteo) nie wymagają kluczy API.

## Jak to działa

```
06:23  GitHub Actions (cron; zapasowy termin 08:53; zimą 05:23 i 07:53)
   │   1. Ryanair: trasy z POZ, WRO, BZG, SZZ, LCJ → wszystkie terminy 2–4 noce w ciągu 8 tygodni
   │   2. wybór ~18 najlepszych kandydatów (cena/noc/os., zniżka vs typowa cena trasy, czas na miejscu, POZ)
   │   3. trivago: nocleg na dokładnie te daty dla 2 dorosłych (ocena ≥ 8, zwykle ≤ 3 km od centrum, bez hosteli)
   │   4. bagaż: szacunek z oficjalnego cennika Ryanair × kurs EUR z NBP; pogoda: Open-Meteo
   │   5. zapis: site/data/deals.json + archiwum dnia + strony do udostępniania site/d/<data>/<id>.html
   ├─► commit do repozytorium (historia cen w state/)
   ├─► publikacja na GitHub Pages
   └─► push ntfy + e-mail z najlepszymi okazjami
```

## Uruchomienie (jednorazowo, ok. 15 minut)

### 1. Konto i repozytorium na GitHubie
1. Załóż darmowe konto na https://github.com/signup.
2. Utwórz **publiczne** repozytorium, np. `wypad` (GitHub Pages w darmowym planie działa tylko dla repozytoriów publicznych). W repozytorium nie ma żadnych haseł: sekrety trzymasz w ustawieniach GitHuba.
3. Wgraj zawartość tego folderu do repozytorium (np. przez GitHub Desktop albo `git push`).

### 2. GitHub Pages
**Settings → Pages → Build and deployment → Source: GitHub Actions.**

Adres aplikacji: `https://<twój-login>.github.io/wypad/`.

### 3. Sekrety (powiadomienia)
**Settings → Secrets and variables → Actions → New repository secret:**

| Sekret | Wartość | Po co |
|---|---|---|
| `NTFY_TOPIC` | losowa, trudna do zgadnięcia nazwa, np. `wypad-7f3k9q2m` | push na telefon |
| `SMTP_USER` | Twój adres Gmail | nadawca e-maila |
| `SMTP_PASSWORD` | **hasło aplikacji** Gmail (16 znaków, nie zwykłe hasło) | logowanie do SMTP |
| `MAIL_TO` | adres(y) odbiorców, po przecinku | odbiorca e-maila |
| `SMTP_HOST`, `SMTP_PORT` | *opcjonalnie*: `smtp.mail.me.com` i `587` dla iCloud Mail | gdy wysyłasz z iCloud zamiast z Gmaila |

- **ntfy:** zainstaluj aplikację *ntfy* (App Store / Google Play) i zasubskrybuj temat o nazwie z `NTFY_TOPIC`. Temat na ntfy.sh jest publiczny dla każdego, kto zna nazwę, dlatego nazwa ma być losowa. Treść powiadomień to tylko ceny i kierunki.
- **Hasło aplikacji Gmail:** konto Google → Bezpieczeństwo → Weryfikacja dwuetapowa (musi być włączona) → Hasła do aplikacji → utwórz „Wypad”. Skopiuj 16 znaków do `SMTP_PASSWORD`.
- **Albo iCloud Mail:** appleid.apple.com → Logowanie i bezpieczeństwo → Hasła dla aplikacji → utwórz „Wypad”. `SMTP_USER` = adres @icloud.com, `SMTP_HOST` = `smtp.mail.me.com`, `SMTP_PORT` = `587`.

Każdy kanał jest opcjonalny: bez sekretu po prostu się nie wysyła.

### 4. Pierwsze uruchomienie
**Actions → Codzienne okazje → Run workflow**, zaznacz **„Szukaj od nowa”** i uruchom. Bez tego przebieg w dniu, w którym repozytorium ma już dzisiejsze dane, tylko je opublikuje i niczego nie przetestuje. Po ~10 minutach aplikacja pokaże świeże okazje, a Ty dostaniesz powiadomienia. To zarazem test, czy Ryanair i trivago odpowiadają serwerom GitHuba. Potem całość działa sama codziennie rano.

### 5. iPhone
Otwórz adres aplikacji w Safari → **Udostępnij → Do ekranu początkowego**.

## Zmiana ustawień
**Nowe miasto?** Dopisz je w `pipeline/wypad/destinations.py`, a potem u siebie uruchom `.venv/bin/python -m wypad climate --state ../state` (w katalogu `pipeline`) i zrób commit `state/climate.json`. Średni klimat miast liczymy lokalnie, bo archiwum pogody nie odpowiada serwerom GitHuba.

Parametry wyszukiwania są w `pipeline/wypad/config.py`: lotniska, liczba nocy, horyzont, domyślny budżet i bagaż, minimalna ocena noclegu, maksymalna odległość od centrum, liczba wyszukiwań noclegów dziennie. Lista kierunków i dojazdy z lotnisk: `pipeline/wypad/destinations.py`. Godzina uruchomienia: `cron` w `.github/workflows/daily.yml` (czas UTC).

## Praca lokalna
```bash
cd pipeline
python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q                                   # testy
.venv/bin/python -m wypad search --site ../site --state ../state # prawdziwe wyszukiwanie (~10 min)
cd ../site && python3 -m http.server 8765                       # podgląd: http://localhost:8765
```

## Ograniczenia (świadome)
- **Ryanair i trivago to nieoficjalne dostępy** do danych, z których korzystają ich własne strony. Mogą się zmienić bez ostrzeżenia. Wtedy wyszukiwanie kończy się błędem, wczorajsze okazje zostają w aplikacji z informacją, że dane są nieaktualne, a GitHub wysyła e-mail o nieudanym uruchomieniu.
- **Loty: tylko Ryanair.** To zdecydowanie największy przewoźnik z POZ/WRO/BZG/SZZ (z Poznania 41 tras). Wizz Air lata z POZ zimą tylko do Londynu-Luton, Bazylei i Kutaisi, a jego wyszukiwarka blokuje automaty. Szczegóły w `docs/RESEARCH.md`.
- **Pierwszy test z serwerów GitHuba dopiero przed nami.** Źródła sprawdzałem z Twojego domowego łącza. Jeśli Ryanair albo trivago zablokują GitHuba, rozwiązaniem awaryjnym jest uruchamianie wyszukiwania na Macu (launchd) i publikacja przez GitHub.
- **Cena bagażu to szacunek:** środek oficjalnego cennika Ryanair przeliczony po kursie NBP. Dokładne ceny wymagałyby akceptacji regulaminu Ryanaira w Twoim imieniu (`ToUs=AGREED`), na co nie było zgody. Aplikacja zawsze oznacza bagaż jako szacunek.
- **Nocleg:** trivago nie zwraca absolutnie najtańszej oferty w mieście, tylko najlepszą z maks. 75 obiektów z 3 zapytań. Nie potwierdza też prywatnej łazienki, dlatego wykluczamy hostele (po typie obiektu z trivago i po nazwie) oraz obiekty poniżej 2★ (poza apartamentami). Nocleg jest zwykle do 3 km od centrum; gdy tak blisko nic nie spełnia kryteriów, do 5 km. Odległość zawsze widać przy ofercie. Cena to „cena łączna wg trivago”; ewentualna opłata miejscowa bywa pobierana na miejscu.
