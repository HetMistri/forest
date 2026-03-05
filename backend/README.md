# forest

## Core API Contract

### POST /forest-metrics

Request body:

```json
{
  "polygon": [
    [73.9, 20.2],
    [73.91, 20.2],
    [73.91, 20.21],
    [73.9, 20.2]
  ]
}
```

Response body (fixed):

```json
{
  "area_km2": 3.4,
  "tree_count": 55080,
  "tree_density": 162,
  "health_score": 68,
  "risk_level": "Moderate",
  "species_distribution": {
    "teak": 58,
    "bamboo": 27,
    "mixed": 15
  }
}
```

Backend implementation entrypoint:

- `backend/api/main.py`
