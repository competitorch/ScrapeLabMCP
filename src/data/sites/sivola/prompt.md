# Sivola — Itinerary Page Extraction

## Page Structure
Sivola itinerary pages (`sivola.it/viaggi/{slug}`) are server-side rendered (SSR). No JavaScript needed — httpx fast-path works perfectly (scrape_level=1).

## What to Extract

### Tour Info (top of page)
- **Tour name**: H1 heading, e.g. "Thailandia Summer zaino in spalla"
- **Duration**: "14 giorni" — number before "giorni"
- **Base price**: First price shown, e.g. "3090 €"
- **Age range**: "18-40" or "18-45" or "Libero"
- **Tags**: City, Trekking, Chill, On the road, Cultura, Natura, etc.
- **Description**: "Il viaggio in breve" section

### Departures (bottom of page)
Each departure has:
- **Date**: Day + month abbreviation (e.g. "31 mag", "06 giu")
- **Duration**: Always "14gg" (or similar)
- **Departure city**: Milano, Roma, Venezia, etc.
- **Coordinator**: Link to `/coordinatori/{slug}`
- **Price breakdown**: Acconto (deposit) + Saldo (balance) + Totale
- **Availability status**:
  - "Ultimi posti!" = almost sold out
  - "Ultimi N posti" = N spots left (extract the number)
  - No status = "Disponibile"
  - In calendar: "Disponibile", "Ultimi Posti", "Sold out", "In arrivo"

### Calendar Section
The calendar shows months with departure days highlighted. Each departure day shows:
- Status icon (Disponibile/Sold out/Ultimi Posti/In arrivo)
- Price

### Itinerary (day by day)
Each day has:
- Day number
- Title
- Subtitle
- Description

## Parsing Strategy
1. The departure LIST at the bottom is the most reliable data source
2. Each departure block starts with `**DD** mmm  Ngg` pattern in markdown
3. Price is in the "Totale" line
4. City follows the duration
5. Coordinator is the link to `/coordinatori/`
6. Status keywords: "Ultimi posti!", "Ultimi N posti"

## Output
Use the travel schema. Key fields per departure:
- departureDate (ISO format, year from calendar context)
- price (total, integer)
- deposit (acconto, integer)
- departureCity
- coordinator (slug)
- status: "available" | "last_spots" | "sold_out" | "coming_soon"
- spotsLeft (number if mentioned, null otherwise)
