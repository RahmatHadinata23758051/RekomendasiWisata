# Metadata Raw Schema Audit Report

This report documents the raw schema fields, structure variations, and data types identified in the raw Apify Google Maps Scraper payloads.

## Discovered Raw Schema Fields

The following fields are consistently or conditionally present in the raw JSON payload files located in `data/raw/apify/google_maps/`:

| Raw Field Name | Data Type | Sub-structure / Example Value | Description |
| :--- | :--- | :--- | :--- |
| `title` | `String` | `"Puncak Mas"` | Business name. |
| `subTitle` | `String` | `"Tujuan Wisata"` | Subtitle or main category. |
| `description` | `String` | `"Gubuk & dek kayu plus properti..."` | Editorial summary. |
| `price` | `String` | `null` or `"$"` | Price level indicator. |
| `categoryName` | `String` | `"Tujuan Wisata"` | Primary category. |
| `categories` | `Array` | `["Tujuan Wisata", "Taman"]` | Associated categories. |
| `address` | `String` | `"Jl. H. Hamim RJP, Sukadana Ham..."` | Full formatted address string. |
| `neighborhood` | `String` | `"Sukadana Ham"` | Neighborhood name. |
| `street` | `String` | `"Jl. H. Hamim RJP"` | Street address. |
| `city` | `String` | `"Kota Bandar Lampung"` | City name. |
| `postalCode` | `String` | `"35215"` | Postal code. |
| `state` | `String` | `"Lampung"` | State / Province. |
| `countryCode` | `String` | `"ID"` | Country code. |
| `phone` | `String` | `"+6282181155115"` | Formatted phone number. |
| `phoneUnformatted` | `String` | `"082181155115"` | Unformatted phone number. |
| `location` | `Object` | `{"lat": -5.42, "lng": 105.22}` | Coordinates object. |
| `permanentlyClosed` | `Boolean` | `false` | Status closed permanently. |
| `temporarilyClosed` | `Boolean` | `false` | Status closed temporarily. |
| `placeId` | `String` | `"ChIJW8B8_HDaQC4RCr0rInFVx0U"` | Unique Google Place ID. |
| `reviewsCount` | `Integer` | `13027` | Total count of reviews. |
| `scrapedAt` | `String` | `"2026-07-13T02:40:24.280Z"` | ISO Timestamp of scrape run. |
| `url` | `String` | `"https://www.google.com/maps..."` | Google Maps URL. |
| `imageUrl` | `String` | `"https://lh3.googleusercontent..."` | Cover image URL. |
| `openingHours` | `Array` | `[{"day": "Senin", "hours": "08.00 to 22.00"}]` | Operating hours array. |
| `additionalInfo` | `Object` | `{"Fasilitas": [{"Toilet": true}]}` | Rich facilities and attributes list. |
| `popularTimesHistogram` | `Object` | `null` or histogram map | Popular times metrics. |

## Variation Observations
1. **Language Variations**:
   - `openingHours` days are typically in Indonesian (e.g. `"Senin"`, `"Selasa"`) but can be in English.
   - `additionalInfo` keys are localized based on the scraper locale (e.g. `"Fasilitas"`, `"Toilet"`, `"Pembayaran"` or `"Amenities"`, `"Toilet"`, `"Payments"`).
2. **Missing Field Handling**:
   - Fields such as `website`, `phone`, `description` can be `null` or absent.
   - If `permanentlyClosed` or `temporarilyClosed` are absent, they default to `false`.
