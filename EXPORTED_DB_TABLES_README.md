# Exported Database Tables

**Export Date:** January 2025  
**Purpose:** Demo data / offline reference / data backup

---

## Table 1: cmmc-objectives.json

Assessment objectives for each CMMC practice.

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique objective identifier |
| `practice_id` | uuid | Foreign key to cmmc_practices |
| `objective_code` | string | NIST identifier (e.g., "3.1.1[a]") |
| `objective_text` | string | Full objective description |

- **Records:** 378
- **Source Table:** `cmmc_objectives`

---

## Table 2: cmmc-practices.json

CMMC practice definitions and metadata.

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique practice identifier |
| `practice_id` | string | CMMC practice ID (e.g., "AC.L2-3.1.1") |
| `domain_code` | string | Domain abbreviation (AC, AT, AU, etc.) |
| `nist_171_id` | string | NIST SP 800-171 reference (e.g., "3.1.1") |
| `title` | string | Practice title |
| `description` | string | Official description |
| `plain_language` | string | Simplified explanation |
| `why_it_matters` | string | Business context |
| `level` | number | CMMC level (1 or 2) |
| `weight_points` | number | Scoring weight |

- **Records:** 110
- **Source Table:** `cmmc_practices`

---

## Table 3: cmmc-assessments.json

Assessment records tracking progress and certification status.

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique assessment identifier |
| `org_id` | uuid | Organization foreign key |
| `scope_id` | uuid | Optional link to scope_records |
| `level` | number | CMMC target level |
| `assessment_type` | string | "self" or "c3pao" |
| `status` | string | "draft", "in_progress", "complete" |
| `certification_status` | string | "none", "pending", "certified" |
| `computed_score` | number | Current assessment score |
| `start_date` | date | Assessment start date |
| `target_date` | date | Target completion date |
| `certified_at` | timestamp | Certification date (if any) |
| `certified_by` | uuid | Certifying user (if any) |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |

- **Records:** 6
- **Source Table:** `cmmc_assessments`

---

## Table 4: scope-records.json

Scoping wizard data for SSP generation.

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique scope record identifier |
| `org_id` | uuid | Organization foreign key |
| `cmmc_level` | number | Target CMMC level |
| `status` | string | "in_progress", "complete" |
| `current_step` | number | Wizard progress (1-5) |
| `assessment_type` | string | Type of assessment |
| `source` | string | "wizard" or "import" |
| `scope_data` | object | Nested scoping data (see below) |
| `warnings` | array | Validation warnings |
| `generated_outputs` | object | SSP/diagram generation flags |
| `created_by` | uuid | User who created record |
| `created_at` | timestamp | Record creation time |
| `updated_at` | timestamp | Last update time |

### Nested `scope_data` Structure

| Section | Contents |
|---------|----------|
| `cuiBasics` | CUI categories, description, locations |
| `boundary` | Networks, excluded systems, cloud providers, external connections |
| `assets` | Array of asset records (id, name, type, category, location, owner) |
| `keyContacts` | Array of contacts (name, title, email, phone, role) |
| `sspInputs` | System name, description, status, type, boundary |
| `diagramInputs` | Network topology, data flow, security zones |

- **Records:** 2
- **Source Table:** `scope_records`

---

## Relationships

```
cmmc_practices (1) ──► (many) cmmc_objectives
organizations  (1) ──► (many) cmmc_assessments
organizations  (1) ──► (many) scope_records
cmmc_assessments (0..1) ──► (1) scope_records
```

---

## Usage Notes

- These files are **point-in-time exports**, not live data
- For production use, query the Supabase database directly
- Use for demo mode, offline development, or data backup reference
