# Scoring System

## Overview

Every location gets a score from 1-100 that represents how notable/popular it is.
Higher score = more points awarded to users when they check in.

The score is computed from three signals:

```
score = min(100, tier_score + type_bonus + wiki_bonus)
```

---

## Signal 1: Tier Score (Wikipedia listing position)

We parse the Wikipedia "Tourism in India by state" page. The order in which places
appear implicitly reflects their importance (editors list major attractions first).

| Tier | Condition | Base Score |
|------|-----------|-----------|
| S | UNESCO World Heritage Site | 90 |
| A | First 5 places listed per state on Wikipedia | 80 |
| B | Places 6-15 listed per state | 65 |
| C | Places 16-30 listed per state | 50 |
| D | Listed on Wikipedia but beyond top 30 | 40 |
| E | Not on Wikipedia list (OSM-only locations) | Determined by type (see below) |

### Tier E — OSM-only locations (not on Wikipedia)

These are scored purely by their `location_type` field:

| location_type | Base Score |
|---------------|-----------|
| tourism:attraction | 30 |
| historic:fort | 28 |
| historic:castle | 28 |
| historic:monument | 25 |
| historic:archaeological_site | 25 |
| leisure:nature_reserve | 25 |
| natural:waterfall | 25 |
| tourism:museum | 22 |
| natural:peak | 20 |
| tourism:zoo | 20 |
| natural:cave_entrance | 18 |
| leisure:park | 18 |
| tourism:viewpoint | 15 |
| leisure:garden | 15 |
| historic:ruins | 15 |
| tourism:artwork | 12 |
| leisure:sports_centre | 10 |
| leisure:playground | 10 |
| leisure:swimming_pool | 8 |
| tourism:hotel | 5 |
| tourism:guest_house | 5 |
| unknown | 10 |

---

## Signal 2: Type Bonus (+0 to +10)

Applied on top of the tier score for Wikipedia-listed locations:

| Category | Bonus |
|----------|-------|
| UNESCO World Heritage Site | +10 |
| National Park / Tiger Reserve | +8 |
| Historic fort / palace | +6 |
| Waterfall / peak / natural wonder | +5 |
| Beach / coastal | +5 |
| Major temple / pilgrimage | +4 |
| Museum | +3 |
| Park / garden | +2 |
| Generic / uncategorized | +0 |

---

## Signal 3: Wiki Bonus

| Condition | Bonus |
|-----------|-------|
| Place has a Wikipedia article (determined by `wikipedia` tag in OSM or name match) | +5 |
| No Wikipedia article | +0 |

---

## Examples

| Place | Tier | Type Bonus | Wiki | Total |
|-------|------|-----------|------|-------|
| Hampi | S (90) | UNESCO +10 | +5 | **100** (capped) |
| Mysore Palace | A (80) | Palace +6 | +5 | **91** → capped to **100** |
| Jog Falls | B (65) | Waterfall +5 | +5 | **75** |
| Chitradurga Fort | C (50) | Fort +6 | +5 | **61** |
| Nandi Hills | C (50) | Peak +5 | +5 | **60** |
| Random local temple (OSM) | E (25) | — | +0 | **25** |
| Unnamed playground (OSM) | E (10) | — | +0 | **10** |

---

## Implementation Strategy

### Phase 1: Parse Wikipedia (one-time)

1. Fetch and parse the "Tourism in India by state" Wikipedia page
2. Extract place names per state in order of appearance
3. Store in a reference JSON/table: `{state, place_name, position, is_unesco}`

### Phase 2: Score Wikipedia-listed locations

1. For each place in the Wikipedia list, fuzzy-match against `locations.place_name`
2. Assign tier_score based on position
3. Add type_bonus based on keywords in the listing (fort, temple, national park, etc.)
4. Add wiki_bonus (+5) since they all have Wikipedia articles

### Phase 3: Score OSM-only locations

1. For all locations NOT matched to the Wikipedia list
2. Assign score based on `location_type` (Tier E table above)

### Phase 4: Write scores to DB

```sql
UPDATE locations SET score = :computed_score WHERE id = :id;
```

---

## Data Sources

| Source | What it provides | Cost |
|--------|-----------------|------|
| Wikipedia "Tourism in India by state" | Curated list of prime locations per state with implicit ranking | Free |
| OSM `location_type` field | Category for type-based scoring | Free (already in DB) |
| OSM `wikipedia` tag | Whether place has a Wikipedia article | Free (already fetched) |

---

## Score Distribution Goal

| Range | What lives here | % of locations |
|-------|----------------|---------------|
| 90-100 | UNESCO sites, top 5 per state | ~2% |
| 65-89 | Major attractions (top 15 per state) | ~5% |
| 40-64 | Notable places (Wikipedia-listed) | ~10% |
| 15-39 | Regular OSM POIs (parks, temples, viewpoints) | ~50% |
| 1-14 | Generic spots (playgrounds, pools, hotels) | ~33% |

This creates a natural reward curve where visiting iconic places feels significantly
more rewarding than checking in at a neighborhood playground.
