# Wypad — wymagania (uzgodnione 25.09.2026)

## Cel
Raz dziennie wyszukać i pokazać okazyjne (tanie, last minute, promocyjne) loty z Polski do atrakcyjnych miast Europy na city break. Do każdego lotu dobrać nocleg według tych samych kryteriów dla 2 dorosłych na cały pobyt.

## Twarde wymagania (z briefu)
1. Każda propozycja zawiera **pełną cenę lotu i noclegu** oraz informację, **jaki bagaż jest w cenie**.
2. Z każdej propozycji da się **przejść do zakupu lotu i noclegu** z wyświetlonymi parametrami (daty, lotniska, 2 dorosłych).
3. Każdą propozycję da się **udostępnić do konsultacji**, a odbiorca otwiera ją bez logowania.
4. Aplikacja jest **atrakcyjna wizualnie** i ma **bardzo dobry UX**.
5. **Bez własnego serwera.** Artur ma iCloud+ i Google AI Pro.
6. Przed budową: **research źródeł** danych (→ `docs/RESEARCH.md`).

## Decyzje Artura (odpowiedzi na pytania)
| Obszar | Decyzja |
|---|---|
| Lotniska wylotu | Poznań (POZ) priorytetowo + Wrocław (WRO), Bydgoszcz (BZG), Szczecin (SZZ), Łódź (LCJ). Oferty z POZ oznaczone i premiowane w sortowaniu |
| Długość wyjazdu | Dowolne dni tygodnia, 2–4 noce. Filtr „tylko weekendy” w aplikacji |
| Horyzont | Wyloty do 8 tygodni naprzód. Wyloty w ciągu 21 dni oznaczone „last minute” |
| Bagaż | Warianty ceny: sam plecak / walizka kabinowa 10 kg / plecak + walizka rejestrowana 20 kg na 2 os. **Domyślnie 10 kg na osobę** |
| Nocleg | Prywatna łazienka, ocena gości ≥ 8/10, blisko centrum. Hotel lub apartament |
| Budżet | Domyślny próg 2500 zł łącznie za 2 osoby (loty + bagaż + nocleg), suwak w aplikacji |
| Hosting | GitHub Actions (codzienne wyszukiwanie) + GitHub Pages (aplikacja). Artur zakłada konto |
| Powiadomienia | Push na telefon (ntfy) **oraz** poranny e-mail |

## Założenia przyjęte bez pytania (do zmiany na prośbę)
- Tylko loty bez przesiadek.
- Ceny w PLN.
- Interfejs po polsku, mobile-first, instalowalny na iPhonie („Do ekranu początkowego”).
- Dojazd na lotnisko i z lotniska do centrum **nie** jest wliczany w cenę. Pokazujemy orientacyjną podpowiedź dojazdu.
- Kierunki: kuratorowana lista miast city-breakowych (`pipeline/wypad/destinations.py`). Kurorty plażowe (Kanary, wyspy greckie, Cypr, Antalya) pominięte.
