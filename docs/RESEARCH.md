# Research źródeł danych i hostingu (25.09.2026)

Przed budową sprawdziłem 3 obszary: źródła lotów, źródła noclegów oraz hosting i automatyzację bez serwera. Każdy obszar badał osobny agent, z testami na żywo. Oznaczenia:

- **[Z] zweryfikowane:** żywe zapytanie albo sprawdzenie w przeglądarce 25.09.2026, z komputera Artura (domowe IP).
- **[C] tylko czytane:** dokumentacja, artykuły, repozytoria.

**Test z serwerów GitHuba (26.09.2026):** Ryanair 81/81 zapytań o ceny, trivago 18/18 wyszukiwań, Wizz Air 29/30 zapytań (1 × HTTP 503), Open-Meteo: prognoza działa, archiwum przekracza limit czasu (dlatego klimat liczony lokalnie).

## Decyzje w skrócie

| Obszar | Wybór | Dlaczego | Rezerwa |
|---|---|---|---|
| Loty | **Ryanair** `farfnd/v4/roundTripFares`, `adultPaxCount=2` | Z POZ lata głównie Ryanair (41 tras). Jedno zapytanie na trasę daje wszystkie kombinacje dat z godzinami i numerami lotów. Cena jest **łączna za 2 osoby** i dotyczy tylko lotów z 2 miejscami w tej cenie. Bez klucza. [Z] | Kiwi.com MCP (wszyscy przewoźnicy, także Wizz) |
| Bagaż | **Szacunek:** środek oficjalnego cennika przewoźnika (Ryanair / Wizz Air) × kurs EUR z NBP | Dokładne ceny (taryfy Regular i Plus przez `FareOptions`) wymagają zapytania o dostępność z `ToUs=AGREED`, czyli akceptacji regulaminu w imieniu Artura. **Artur się nie zgodził.** | `FareOptions` po ewentualnej zgodzie |
| Noclegi | **trivago MCP**, 3 warianty zapytania na termin | Bez klucza. Cena za cały pobyt dla 2 osób w PLN, ocena, gwiazdki, współrzędne, zdjęcie i link z datami i 2 dorosłymi. [Z] | SerpApi Google Hotels (250 wyszukiwań/mies. za darmo, klucz) |
| Linki do zakupu | ryanair.com (trasa, daty, 2 dorosłych), trivago (oferta w pokazanej cenie), Booking.com (wyszukanie obiektu z datami i 2 dorosłymi) | Wszystkie formaty sprawdzone w przeglądarce. [Z] | Google Flights (link `tfs`) jako porównanie |
| Loty, dodatek | **Wizz Air** (rozkład `search/timetable`) | Dodane 26.09.2026 na prośbę Artura: ok. 20 tras do naszych miast, głównie z Wrocławia. Ceny za osobę bez gwarancji 2 miejsc; brak godzin przylotu (szacujemy z odległości i stref czasowych). [Z] | Awaria Wizz nie blokuje ofert Ryanaira |
| Pogoda | Open-Meteo | Darmowe, bez klucza. Prognoza do ~2 tygodni, dalej średnia miesięczna z 3 ostatnich pełnych lat. Archiwum Open-Meteo prawie zawsze przekraczało limit czasu z serwerów GitHuba, więc klimat 86 miast jest policzony raz i zapisany w `state/climate.json`. [Z] | — |
| Hosting | **GitHub Actions + GitHub Pages** (publiczne repo) | 0 zł, codzienny cron, sekrety, własna domena HTTPS (warunek PWA), publiczne linki do ofert. [C] | Mac + launchd (gdy GitHub będzie blokowany przez źródła); Cloud Run z kredytów Google AI Pro |
| Powiadomienia | ntfy (push) + e-mail SMTP (Gmail albo iCloud Mail) | Wybór Artura; żadne nie wymaga serwera. | Telegram, Pushover |

**Czy iCloud+ albo Google AI Pro rozwiązują hosting? Nie.** iCloud+ nie ma hostingu ani uruchamiania kodu. Google AI Pro daje 10 $/mies. kredytów Google Cloud, które mogą pokryć rezerwowy wariant (Cloud Run + Cloud Scheduler), ale to nie jest gotowy hosting. „Zaplanowane działania” w Gemini dają tylko powiadomienie w aplikacji: bez danych, linków i aplikacji. [C]

## 1. Loty

| Źródło | Co daje | Koszt / dostęp | Status | Decyzja |
|---|---|---|---|---|
| Ryanair `farfnd` (roundTripFares, oneWayFares) | Kombinacje dat, godziny, nr lotów, cena za N osób (`adultPaxCount`) | Bez klucza, nieoficjalne | [Z] działa. Ceny z pamięci podręcznej sprzed 0,1–7 h | **Główne źródło** |
| Ryanair `availability` + `FareOptions` | Dokładne loty, liczba wolnych miejsc, ceny pakietów z bagażem | Bez klucza, ale `availability` wymaga `ToUs=AGREED` | [Z] działa (4 zapytania w researchu) | **Nieużywane** (decyzja Artura) |
| Wizz Air | Mapa tras i rozkład z cenami za osobę | Wersję API trzeba odczytać z HTML strony. Pełna wyszukiwarka zwraca 429 (blokada botów) | [Z] Z POZ zimą tylko Londyn-Luton, Bazylea, Kutaisi; z WRO 26 tras | **Dodane 26.09 na prośbę Artura** (patrz niżej) |
| Kiwi.com MCP (`mcp.kiwi.com`) | Wszyscy przewoźnicy, cena za 2 osoby z bagażem, link do rezerwacji | Bez klucza | [Z] działa. Ceny o 2% taniej do 28% drożej niż bezpośrednio. Zdarzają się loty „open-jaw” | Rezerwa |
| Kiwi Tequila API | Dawny standard | Tylko na zaproszenie od maja 2024 | [C] | Odpada |
| Amadeus Self-Service | GDS, bez tanich linii | Wyłączone 17.07.2026 | [Z] brak DNS | Odpada |
| Travelpayouts / Aviasales | Ceny z cache innych użytkowników (48 h – 7 dni) | Token po rejestracji | [C] słabe pokrycie tanich linii | Odpada |
| SerpApi Google Flights | Ceny Google, parametr bagażu | 250 zapytań/mies. za darmo | [C] | Niepotrzebne |
| Google Flights (scraping, `fast-flights`) | — | — | [Z] z polskiego IP wpada na stronę zgód i się wysypuje | Odpada |
| fly4free.pl RSS (`/tanie-loty/z-poznania/feed/`) | Kuratorowane okazje z Poznania | Darmowe | [Z] działa, tagi miast | Opcjonalny dodatek na przyszłość (brak noclegów) |
| azair.eu | — | — | [Z] wyniki sprzed wielu miesięcy | Odpada |

Ważne szczegóły z testów:
- `adultPaxCount=2` zmienia wynik. Przykład: POZ→BCN dla 1 osoby najtaniej 121 zł (26.10), dla 2 osób najtaniej 656,90 zł łącznie (30.10), bo na 26.10 nie było 2 miejsc w tej cenie. [Z]
- `summary.tripDurationDays` to czas zaokrąglony w górę, a nie liczba nocy. Noce liczymy sami z dat. [Z]
- Link Google Flights w formacie `?q=` otwierał się z **3 dorosłymi** zamiast 2. Używamy formatu `tfs`, a test sprawdza zgodność bajt w bajt ze zweryfikowanym linkiem. [Z]

### Cennik bagażu Ryanair (EUR za osobę za lot, przy rezerwacji; strona EN, 25.09.2026) [Z]
| Pozycja | Zakres | Szacunek w aplikacji |
|---|---|---|
| Priority i 2 bagaże kabinowe (walizka 10 kg) | 12,49–36 € | środek: 24,25 € |
| Walizka rejestrowana 20 kg | 21,49–59,99 € | środek: 40,74 € |

Kontrola sensowności (tylko Ryanair; dla Wizz Air nie mamy danych do takiej kontroli, więc jego szacunek może odbiegać bardziej): zweryfikowane ceny taryfy Regular (miejsce + Priority + 10 kg) na trasach z POZ to 94–116 zł za osobę za lot, a środek cennika to ~106 zł. Szacunek jest więc realistyczny, ale **to szacunek** i aplikacja zawsze tak go opisuje.

## 2. Noclegi

| Źródło | Cena za pobyt, 2 os. | Link z datami | Dostęp | Status | Decyzja |
|---|---|---|---|---|---|
| **trivago MCP** | tak, PLN | tak (trivago → serwis z ofertą) | bez klucza | [Z] działa; 25 obiektów na zapytanie, ~5 s | **Główne** |
| Booking.com (linki) | pokazuje Booking | tak | bez klucza | [Z] linki z datami, 2 dorosłymi i filtrami działają | **Linki w aplikacji** |
| Booking.com (API, scraping) | — | — | API tylko dla partnerów z umową; scraping zablokowany (AWS WAF) i zakazany w regulaminie | [Z] | Odpada |
| SerpApi Google Hotels | tak (z podatkami wg zasad Google) | przez szczegóły obiektu | klucz; 250/mies. za darmo | [C] | Rezerwa |
| Xotelo | za noc, bez podatków, bez PLN | nie | bez klucza | [Z] | Odpada |
| LiteAPI | tak | własny serwis rezerwacyjny | karta kredytowa | [C] | Odpada |
| Airbnb (nieoficjalnie) | tak | tak | regulamin zakazuje botów | [Z] | Odpada |
| Amadeus Hotels, Hotellook | — | — | wyłączone | [Z] | Odpada |
| Apify (scraper Booking) | tak | tak | ~15 $/mies. przy naszej skali; regulamin Booking | [C] | Odpada |

Co wiemy o trivago z testów [Z]:
- **Zgodność ceny z Booking.com:** w próbie z 1 obiektem (Rzym) cena z trivago zgadzała się z ceną na Booking.com („Zawiera opłaty i podatki”).
- **Ocena gości to własna średnia trivago.** Przykład: 8,9 na trivago wobec 8,5 na Booking.com. W aplikacji podpisujemy ją „ocena trivago”.
- **Wyniki nie są posortowane po cenie i nie obejmują absolutnie najtańszych ofert w mieście.** Przykład z Rzymu: na Booking.com najtaniej 731 zł, na trivago 912 zł. Dlatego pytamy 3 razy (bez filtra, hotele 2–3★, obiekty z kuchnią) i sami wybieramy najtańszy obiekt spełniający kryteria.
- **trivago nie mówi, czy łazienka jest prywatna.** Wykluczamy więc hostele i obiekty poniżej 2★, poza apartamentami. Typ obiektu bierzemy z linku trivago (np. `…/lm/hostel-schronisko-…`), bo gwiazdki bywają mylące: hostel „The Bristol Wing” miał w danych 4★. Aplikacja nigdzie nie obiecuje prywatnej łazienki.
- **Podatek miejski:** w sprawdzonych ofertach Booking był wliczony, ale centrum pomocy trivago mówi „zwykle bez podatków”. Dlatego piszemy „cena łączna wg trivago”, a nie „cena z podatkami”.

## 3. Hosting i automatyzacja bez serwera [C, na podstawie oficjalnych stron]

| Opcja | Koszt | Harmonogram | PWA + publiczne linki | Ograniczenia | Ocena |
|---|---|---|---|---|---|
| **GitHub Actions + Pages (publiczne repo)** | 0 zł | cron „best effort”: bywa spóźniony o godziny albo pominięty (zgłoszenia od 26.08.2026) | tak | Wyłączenie crona po 60 dniach bez aktywności. Codzienny commit z danymi to aktywność, ale nie jest to udokumentowane. Kod publiczny | **Wybrane** |
| Prywatne repo + Cloudflare Pages | 0 zł | jak wyżej | tak | 2000 min Actions/mies. | Rezerwa, jeśli prywatność |
| Google Apps Script | 0 zł | dzienny wyzwalacz | **nie** (iframe, baner, brak PWA) | 6 min na uruchomienie | Odpada |
| Cloud Run + Cloud Scheduler (kredyty AI Pro) | ~0 zł z kredytów | punktualny | przez Firebase Hosting | konto rozliczeniowe z kartą | Rezerwa |
| Cloudflare Workers (darmowy) | 0 zł | cron | tak | 10 ms CPU, 50 zapytań na uruchomienie | Za mało |
| Netlify / Vercel (darmowe) | 0 zł | — | tak | Netlify: kredyty nie starczą na codzienne wdrożenia; Vercel: 300 s | Odpada |
| Artefakty / rutyny Claude | — | — | artefakt nie pobiera zewnętrznego JSON | wersja poglądowa, limity | Odpada |
| iCloud+ / Skróty Apple | — | automatyzacja na telefonie | brak hostingu | — | Odpada |

Jak omijamy znane pułapki:
- **Spóźniony cron:** 2 terminy dziennie (06:23 i 08:53 latem, 05:23 i 07:53 zimą). Drugi przebieg nic nie robi, jeśli dzisiejsze okazje są już opublikowane. Jeśli dane z dziś są w repo, a nie udała się tylko publikacja, wyszukiwanie jest pomijane i ponawiana jest tylko publikacja.
- **Każda publikacja zastępuje całą stronę:** strony udostępnionych ofert z ostatnich 60 dni są w repozytorium i idą w każdej publikacji, więc wczorajszy link nie zwraca 404.
- **Blokada IP GitHuba przez źródła (także częściowa):** gdy więcej niż połowa zapytań do Ryanaira albo do trivago się nie uda, wyszukiwanie kończy się błędem i nie nadpisuje danych. Aplikacja pokazuje baner „dane nieaktualne”, a GitHub wysyła e-mail o błędzie. Rozwiązanie awaryjne: uruchamianie na Macu (launchd) i publikacja przez GitHub.

## 4. Zasady i ryzyka prawne (szara strefa)
- **Ryanair:** `robots.txt` blokuje `/api`, a regulamin zakazuje scrapingu w celach komercyjnych. Wypad to osobisty, niekomercyjny użytek o małej skali (~90 zapytań dziennie), ale formalnie jest to szara strefa.
- **Wizz Air:** regulamin strony zakazuje robotów i scrapingu, a wyszukiwarka jest chroniona (Kasada). Używamy tylko rozkładu (~50 zapytań dziennie); jeśli Wizz go zablokuje, oferty Ryanaira publikują się dalej.
- **trivago:** serwer MCP nie ma opublikowanych zasad ani limitów. Regulamin serwisu (§5.5) zakazuje automatycznych wywołań stron. Skala: ~55 zapytań dziennie.
- **Booking.com, Airbnb:** tylko linki; nic nie pobieramy.
- **Nie akceptujemy żadnych regulaminów w imieniu Artura** (bez `ToUs=AGREED`).

## 5. Uzupełnienie 26.09.2026: Wizz Air — co wyszło przy wdrożeniu [Z]
- **Okno dat:** rozkład przyjmuje najwyżej ~38 dni na zapytanie (41+ dni → HTTP 400 „InvalidProtocol”). 8 tygodni dzielimy więc na 2 okna po 30 dni.
- **Ochrona przed CSRF:** pierwsze zapytanie w sesji ustawia ciasteczko `RequestVerificationToken`. Każde kolejne bez nagłówka `X-RequestVerificationToken` z jego wartością dostaje HTTP 400 „InvalidProtocol”. Tak robi też sama strona Wizz.
- **`priceType: checkPrice`** oznacza cenę 0, czyli nieznaną. Takie dni pomijamy, podobnie jak dni z kilkoma lotami, bo rozkład nie mówi, którego lotu dotyczy cena.
- **Bagaż Wizz:** WIZZ Priority 13–57,50 € za osobę za lot; walizka 20 kg 0–112,50 € (w szczycie 15.12–10.01: 2–122 €). Szacunek to środek zakresu.
- **Link do rezerwacji:** `wizzair.com/pl-pl/booking/select-flight/{z}/{do}/{wylot}/{powrót}/2/0/0/null`. Automatyczna przeglądarka nie przeszła ochrony Kasada, ale **Artur sprawdził go ręcznie 26.09** na ofercie Wrocław–Kiszyniów 15–19.11:
  - trasa, daty i „2 pasażerów” ustawione;
  - koszyk Wizz: 296 zł za 2 osoby, dokładnie tyle, ile pokazuje aplikacja;
  - **opłata administracyjna jest wliczona w cenę z rozkładu** (79 zł = 44 zł bilet + 35 zł opłaty za osobę);
  - szacowane przyloty: tam ~18:45 wobec 18:40, powrót ~15:10 wobec 15:10 (numery lotów W4 4000 / W4 3999).
