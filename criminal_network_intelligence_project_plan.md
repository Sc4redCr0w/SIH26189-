# AI-Powered Criminal Network Intelligence Platform
## SIH26189 — Project Specification, Phased Implementation Plan, and Architecture

> **Project goal:** Build an evidence-backed criminal-network analysis platform that ingests structured and unstructured crime/intelligence data, extracts entities and relationships, constructs a knowledge graph, performs graph/temporal/geographic analysis, and provides investigators with searchable visual intelligence and AI-assisted reports.
>
> **Reference basis:** The project follows the SIH26189 problem statement and the provided reference architecture describing knowledge-graph-powered criminal analysis followed by AI-powered intelligence synthesis.

---

# 1. Project Status Legend

Use these status markers throughout the document:

- [ ] **NOT STARTED**
- [~] **IN PROGRESS**
- [x] **DONE**

When starting a phase, change its checkbox from `[ ]` to `[~]`.
When a phase is completed, change it to `[x]`.

---

# 2. Overall Project Architecture

```text
                                      ┌──────────────────────┐
                                      │      USERS           │
                                      │                      │
                                      │ Admin / Analyst /    │
                                      │ Auditor              │
                                      └──────────┬───────────┘
                                                 │
                                                 ▼
                                      ┌──────────────────────┐
                                      │ Authentication +     │
                                      │ Role-Based Access    │
                                      └──────────┬───────────┘
                                                 │
                                                 ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         INVESTIGATOR WEB APPLICATION                         │
│                                                                              │
│ Search │ Graph Explorer │ Cases │ Evidence │ Timeline │ Map │ AI │ Reports │
└───────────────────────────────────┬──────────────────────────────────────────┘
                                    │
                                    ▼
                            ┌─────────────────┐
                            │     FastAPI     │
                            │    REST API     │
                            └────────┬────────┘
                                     │
          ┌──────────────────────────┼──────────────────────────┐
          │                          │                          │
          ▼                          ▼                          ▼
┌───────────────────┐      ┌───────────────────┐      ┌────────────────────┐
│ Data Ingestion    │      │ Investigation API │      │ AI / Analysis API │
│ + Processing      │      │ + Search          │      │                    │
└─────────┬─────────┘      └─────────┬─────────┘      └─────────┬──────────┘
          │                          │                          │
          ▼                          ▼                          ▼
┌───────────────────┐      ┌───────────────────┐      ┌────────────────────┐
│ OCR / Parsing     │      │ PostgreSQL        │      │ LLM / Agents       │
│ NER / Relations   │      │ Cases / Users /   │      │ Report Synthesis   │
│ Entity Resolution │      │ Evidence / Audit │      │ RAG / Tool Calling │
└─────────┬─────────┘      └─────────┬─────────┘      └─────────┬──────────┘
          │                          │                          │
          └──────────────────────────┼──────────────────────────┘
                                     ▼
                           ┌────────────────────┐
                           │    Neo4j Graph     │
                           │                    │
                           │ Entities + Edges   │
                           │ Evidence Links     │
                           └─────────┬──────────┘
                                     │
                                     ▼
                           ┌────────────────────┐
                           │ Graph Analytics    │
                           │                    │
                           │ Centrality         │
                           │ Communities        │
                           │ Paths              │
                           │ Network Structure  │
                           └─────────┬──────────┘
                                     │
                     ┌───────────────┼─────────────────┐
                     ▼               ▼                 ▼
               Temporal         Geographic        Pattern/
               Analysis         Analysis          Anomaly Signals
                     └───────────────┼─────────────────┘
                                     ▼
                           ┌────────────────────┐
                           │ AI Investigation   │
                           │ Assistant / Agents │
                           └─────────┬──────────┘
                                     ▼
                           ┌────────────────────┐
                           │ Intelligence       │
                           │ Report             │
                           └────────────────────┘


Every important user action
                │
                ▼
       ┌──────────────────┐
       │ Audit Log Service│
       └────────┬─────────┘
                ▼
       ┌──────────────────┐
       │ Append-oriented  │
       │ Audit Log Store  │
       └──────────────────┘
```

---

# 3. Core Design Principles

## 3.1 Evidence-first

The system should not treat an AI-generated conclusion as an original fact.

Store:

```text
Source Evidence
      ↓
Extracted Fact / Relationship
      ↓
Graph Representation
      ↓
Analytical Finding
      ↓
AI Explanation
```

Every important relationship should be traceable to its source.

## 3.2 Graph, not tree

The platform must use a general graph because criminal networks can contain:

- many-to-many relationships
- multiple paths
- cycles
- cross-community links
- different edge types

Example:

```text
A ─── B
│   /│\
│  / │ \
E ─  C  D
│
└──────── A
```

## 3.3 Observed data vs analytical inference

Keep these separate.

Example:

```text
Observed:
A called B.

Derived:
A and B communicate frequently.

Analytical:
A may have structural importance in this network.
```

The system should never silently turn an analytical signal into a legal-status declaration.

## 3.4 Human review for high-impact data changes

AI-extracted entities and relationships should be reviewable before becoming trusted graph data.

## 3.5 Role-based access control

Admin/data-management users can mutate data.
Analysts can investigate without modifying source data.
Auditors/supervisors can review history.

---

# 4. Data Model

## 4.1 Primary entity types

The initial graph should support:

```text
Person
Phone
Vehicle
Location
Organization
Case
FIR
Transaction
Event
Evidence
```

## 4.2 Example relationships

```text
PERSON ──CALLS──────────────> PERSON
PERSON ──KNOWS──────────────> PERSON
PERSON ──ASSOCIATED_WITH────> PERSON
PERSON ──OWNS───────────────> VEHICLE
PERSON ──USES───────────────> PHONE
PERSON ──VISITED────────────> LOCATION
PERSON ──WORKS_FOR──────────> ORGANIZATION
PERSON ──MENTIONED_IN───────> FIR
PERSON ──INVOLVED_IN────────> CASE
PERSON ──PRESENT_AT─────────> EVENT
PERSON ──TRANSFERRED_TO─────> PERSON
EVIDENCE ──SUPPORTS─────────> RELATIONSHIP/FACT
```

## 4.3 Edge metadata

Relationships should store, where available:

```text
source
timestamp
start_time
end_time
evidence_id
case_id
confidence
notes
created_by
created_at
```

## 4.4 Entity metadata

A person/entity record can contain:

```text
entity_id
name
aliases
entity_type
date_of_birth (when legally appropriate/available)
phone identifiers
address/location references
organization references
legal/status fields from source records
notes
created_by
created_at
updated_by
updated_at
record_state
```

---

# 5. Phased Implementation Plan

---

## Phase 0 — Project Definition and Repository Setup

### Status
[~] IN PROGRESS

### Objective

Freeze the project scope, repository structure, coding conventions, data contracts, and development environment before implementation.

### What to make

```text
project/
├── frontend/
├── backend/
├── ingestion/
├── graph/
├── ai/
├── analytics/
├── datasets/
├── docs/
├── tests/
├── docker/
└── README.md
```

### Tasks

- [ ] Create Git repository.
- [ ] Define branch strategy.
- [ ] Create frontend/backend directories.
- [ ] Create Python environment.
- [ ] Create React application.
- [ ] Create FastAPI application.
- [ ] Add environment-variable handling.
- [ ] Add `.env.example`.
- [ ] Add Docker configuration.
- [ ] Create initial README.
- [ ] Define API naming conventions.
- [ ] Define database migration strategy.
- [ ] Define issue/task tracking.

### How

Use:

```text
Frontend: React
Backend: FastAPI
Language: Python + TypeScript
Database: PostgreSQL
Graph DB: Neo4j
Containerization: Docker
Version control: Git
```

### Deliverable

A working skeleton where:

```text
React → FastAPI → health endpoint
```

works successfully.

---

# Phase 1 — Authentication, Users, and RBAC

### Status
[ ] NOT STARTED

### Objective

Create secure login and enforce the three main roles.

### Roles

#### Admin

Can:

- create entities
- edit entities
- archive/remove entities
- upload evidence
- create relationships
- approve/reject extracted data
- merge duplicates
- manage users

#### Analyst

Can:

- search
- view entities
- explore graphs
- run analysis
- view evidence
- use AI assistant
- generate reports

Cannot:

- edit core data
- delete data
- create relationships
- approve extracted data

#### Auditor/Supervisor

Can:

- inspect records
- inspect audit history
- review changes

### Architecture

```text
React Login
     ↓
FastAPI Auth API
     ↓
Password Hash Verification
     ↓
Session/JWT
     ↓
Role
 ┌───┼────┐
 ↓   ↓    ↓
Admin Analyst Auditor
```

### Tasks

- [ ] User table.
- [ ] Password hashing.
- [ ] Login endpoint.
- [ ] Logout/session invalidation.
- [ ] JWT or secure session mechanism.
- [ ] Role table/field.
- [ ] Backend authorization middleware.
- [ ] Frontend route guards.
- [ ] Admin user management screen.
- [ ] Analyst read-only restrictions.
- [ ] Auditor permissions.
- [ ] Permission-denied handling.

### Critical rule

Frontend restrictions are not sufficient.

An Analyst calling:

```http
DELETE /entities/123
```

must receive:

```http
403 Forbidden
```

from the backend.

### Deliverable

Three users with demonstrably different permissions.

---

# Phase 2 — Core Database and Knowledge Graph Schema

### Status
[ ] NOT STARTED

### Objective

Design and implement the persistent data model before ingestion and UI become complicated.

### Relational database

Use PostgreSQL for:

```text
users
roles
cases
evidence
entity_metadata
audit_logs
reports
analysis_runs
```

### Graph database

Use Neo4j for:

```text
Person
Phone
Vehicle
Location
Organization
Case
FIR
Transaction
Event
Evidence references
```

### Architecture

```text
                 FastAPI
                    │
          ┌─────────┴─────────┐
          ▼                   ▼
     PostgreSQL             Neo4j
     metadata              network
     + audit                graph
     + users
     + cases
```

### Tasks

- [ ] Design PostgreSQL schema.
- [ ] Design Neo4j node labels.
- [ ] Design relationship types.
- [ ] Design indexes.
- [ ] Add entity IDs shared between relational and graph stores.
- [ ] Implement CRUD repository layer.
- [ ] Add database migrations.
- [ ] Add Neo4j constraints/indexes.
- [ ] Create seed data.

### Deliverable

Create/read/update graph records through the backend.

---

# Phase 3 — Manual Entity Management

### Status
[ ] NOT STARTED

### Objective

Allow an authorized Admin to create and maintain entities without requiring an uploaded document.

### UI

```text
+ Add Entity
     ↓
Entity Type
     ↓
Person / Vehicle / Phone / Location / Organization / Event
     ↓
Form
     ↓
Save
```

### Example

```text
Name:
Vaibhav Suryavanshi

Type:
Person

Aliases:
...

Status:
Unknown

Notes:
...
```

After saving:

```text
(:Person {
    id: "P1024",
    name: "Vaibhav Suryavanshi"
})
```

### Tasks

- [ ] Entity creation page.
- [ ] Entity edit page.
- [ ] Entity detail page.
- [ ] Entity type selection.
- [ ] Validation rules.
- [ ] Duplicate warning.
- [ ] Backend authorization.
- [ ] Soft-delete/archive support.
- [ ] Audit event for every mutation.

### Deliverable

Admin can create:

```text
Vaibhav Suryavanshi
```

and retrieve it later.

---

# Phase 4 — Evidence and File Ingestion

### Status
[ ] NOT STARTED

### Objective

Allow Admin users to feed new source material into the system.

### Supported first inputs

```text
PDF
TXT
CSV
XLSX
Images
```

### Evidence categories

```text
FIR
Police Report
CDR
Financial Transaction
Surveillance Report
Public Social-Media Intelligence
Criminal History
Intelligence Report
Other
```

### Architecture

```text
Admin
  ↓
Upload File
  ↓
File Validation
  ↓
Object/File Storage
  ↓
Processing Queue
  ↓
Parser/OCR
  ↓
Normalized Data
```

### Tasks

- [ ] Upload UI.
- [ ] File type validation.
- [ ] File size validation.
- [ ] Evidence metadata form.
- [ ] Secure file storage.
- [ ] Processing status.
- [ ] Upload history.
- [ ] Failed processing status.
- [ ] Evidence IDs.
- [ ] Link evidence to case.

### Deliverable

Admin can upload a document/CSV and see:

```text
UPLOADED
PROCESSING
PROCESSED
FAILED
```

---

# Phase 5 — OCR, NLP, Entity Extraction, and Relationship Extraction

### Status
[ ] NOT STARTED

### Objective

Automatically extract entities and candidate relationships from unstructured evidence.

### Pipeline

```text
Document
   ↓
Text Extraction / OCR
   ↓
Text Cleaning
   ↓
Sentence Segmentation
   ↓
NER
   ↓
Entity Normalization
   ↓
Relationship Extraction
   ↓
Candidate Facts
```

### Extract

```text
PERSON
PHONE
VEHICLE
LOCATION
ORGANIZATION
DATE
CASE
EVENT
```

### Example

Source text:

```text
Vaibhav met Rahul at Location X on 12 September.
```

Candidate facts:

```text
Vaibhav
Rahul
Location X
12 September

Potential:
Vaibhav ──MET──> Rahul
Vaibhav ──PRESENT_AT──> Location X
Rahul ──PRESENT_AT──> Location X
```

### Important

Do not automatically convert every extracted relationship into a trusted fact.

Use:

```text
Extracted candidate
       ↓
Review queue
       ↓
Admin approval
       ↓
Trusted graph relationship
```

### Technology

Possible free/open-source components:

```text
PyMuPDF
Tesseract/OCR tools
spaCy
Hugging Face models
Sentence Transformers
Local LLM through Ollama
```

### Deliverable

Upload an FIR/report and receive an entity/relationship extraction preview.

---

# Phase 6 — Entity Resolution and Duplicate Detection

### Status
[ ] NOT STARTED

### Objective

Prevent duplicate people and entities from corrupting the graph.

### Example

Input:

```text
V. Suryavanshi
```

Existing entity:

```text
Vaibhav Suryavanshi
```

System:

```text
Possible match: 91%

[Merge]
[Keep Separate]
[Review]
```

### Signals

Possible matching signals:

```text
name similarity
alias similarity
phone
location
organization
case references
other available structured identifiers
```

### Architecture

```text
New Entity
    ↓
Candidate Search
    ↓
Similarity/Rules
    ↓
Possible Matches
    ↓
Human Review
    ↓
Merge or Separate
```

### Tasks

- [ ] Normalize names.
- [ ] Alias handling.
- [ ] Candidate generation.
- [ ] Similarity scoring.
- [ ] Review screen.
- [ ] Merge operation.
- [ ] Merge audit record.
- [ ] Relationship reconciliation after merge.

### Deliverable

Demonstrate duplicate detection without accidental entity merging.

---

# Phase 7 — Relationship Management

### Status
[ ] NOT STARTED

### Objective

Allow Admin users to create and manage relationships between existing entities.

### UI

```text
Source:
Vaibhav Suryavanshi

Relationship:
CALLS

Target:
Rahul Mehta

Date:
18/09/2026

Evidence:
CDR-8271

[Create Relationship]
```

### Also support graph-based creation

```text
Right-click node
      ↓
Add Relationship
      ↓
Select target
      ↓
Select relationship type
      ↓
Attach evidence
      ↓
Save
```

### Deliverable

Admin can create:

```text
Vaibhav ──CALLS──> Rahul
```

and the relationship is visible in the graph.

---

# Phase 8 — Interactive Graph Explorer

### Status
[ ] NOT STARTED

### Objective

Build the primary investigative visualization.

### Requirements

- [ ] Search.
- [ ] Zoom.
- [ ] Pan.
- [ ] Drag nodes.
- [ ] Expand neighbors.
- [ ] Collapse branches.
- [ ] Click node for details.
- [ ] Click edge for evidence.
- [ ] Multi-hop expansion.
- [ ] Relationship filters.
- [ ] Entity-type filters.
- [ ] Date filters.
- [ ] Focus selected node.
- [ ] Reset graph.
- [ ] Export graph view/image if required.

### Search example

```text
Search:
Ram Singh
```

Result:

```text
                    Person B
                       │
                       │
Person C ───────── Ram Singh ───────── Person D
                       │
                       │
                    Vehicle X
```

### Depth controls

```text
Depth 1 → direct neighbors
Depth 2 → neighbors of neighbors
Depth 3 → wider network
```

### Recommended frontend visualization

Use a graph library such as:

```text
Cytoscape.js
or
React Flow
```

Cytoscape.js is particularly suitable for network visualization.

### Deliverable

A user can search a person and visually explore a real graph containing cycles and many-to-many links.

---

# Phase 9 — Node Status, Colors, and Visual Semantics

### Status
[ ] NOT STARTED

### Objective

Make graph meaning visible without conflating analytical signals with legal status.

### Recommended node categories

```text
Red    = Confirmed legal status from source record
Orange = Under investigation / charged where explicitly recorded
Yellow = Analytical attention / notable pattern
Blue   = Relevant association
Gray   = Unknown / unresolved
```

### UI requirements

- [ ] Legend.
- [ ] Consistent colors.
- [ ] Node hover information.
- [ ] Edge labels.
- [ ] Edge styling.
- [ ] Optional node sizing based on measurable graph statistics.
- [ ] Accessible contrast.

### Important

A yellow node should mean:

```text
"Requires analytical review"
```

not:

```text
"Criminal"
```

unless the underlying source explicitly records the relevant legal status.

### Deliverable

Investigator can understand node/edge semantics without opening every node.

---

# Phase 10 — Evidence Traceability

### Status
[ ] NOT STARTED

### Objective

Make every important graph assertion explainable.

### Example

Click:

```text
Vaibhav ──CALLS──> Rahul
```

Show:

```text
Relationship:
CALLS

Date:
18/09/2026

Time:
21:32

Duration:
342 sec

Evidence:
CDR-8271

Source:
CDR import

Case:
CASE-102
```

### Tasks

- [ ] Evidence detail page.
- [ ] Relationship-to-evidence links.
- [ ] Evidence-to-entity links.
- [ ] Source metadata.
- [ ] Original document access.
- [ ] Source snippet/page reference where available.
- [ ] Evidence history.

### Deliverable

Every important relationship can answer:

> "What source supports this relationship?"

---

# Phase 11 — Graph Analytics

### Status
[ ] NOT STARTED

### Objective

Use graph algorithms to identify network structure.

The provided reference specifically describes graph analysis for communities and network roles.

### Algorithms

Start with:

```text
Degree centrality
Betweenness centrality
PageRank
Community detection
Shortest paths
Connected components
```

### Example

```text
Community A
   A ─ B
   │ / \
   C   D

Community B
   E ─ F
```

Potential outputs:

```text
Communities:
2

High-degree nodes:
B, F

Bridge candidates:
C
```

### Tasks

- [ ] Define algorithm inputs.
- [ ] Create analysis jobs.
- [ ] Store results.
- [ ] Display results on graph.
- [ ] Show explanation for each metric.
- [ ] Link findings to underlying graph.

### Deliverable

Analyst can select a network and run graph analysis.

---

# Phase 12 — Temporal Analysis

### Status
[ ] NOT STARTED

### Objective

Understand how relationships and network structure evolve over time.

### Features

- [ ] Date-range selector.
- [ ] Timeline visualization.
- [ ] Relationship appearance/disappearance.
- [ ] Activity spikes.
- [ ] Network growth.
- [ ] Community changes.
- [ ] Event/relationship time correlation.

### Example

```text
January:
A ─ B

February:
A ─ B ─ C

March:
A ─ B ─ C
    │
    D
```

### Deliverable

Analyst can view a network at different time ranges and compare changes.

---

# Phase 13 — Geographic Analysis

### Status
[ ] NOT STARTED

### Objective

Analyze relationships between entities and locations.

### Features

- [ ] Map view.
- [ ] Entity-location links.
- [ ] Location frequency.
- [ ] Date filtering.
- [ ] Case filtering.
- [ ] Community filtering.
- [ ] Timeline + map combination where useful.

### Example

```text
Person
   ↓
Location X
   ↓
Event
   ↓
Case
```

### Deliverable

Analyst can investigate where relevant activity/relationships occur geographically.

---

# Phase 14 — Suspicious/Notable Pattern Detection

### Status
[ ] NOT STARTED

### Objective

Detect measurable patterns that warrant analyst review.

### Initial signals

```text
Communication spike
New cross-community relationship
Unusual transaction sequence
Repeated relevant-location presence
Sudden network expansion
New bridge between communities
Abrupt relationship change
```

### Architecture

```text
Graph
  +
Time
  +
Location
  +
Transactions
  +
Communication
       ↓
Pattern Detection
       ↓
Analytical Signal
       ↓
Analyst Review
```

### Output

Use language such as:

```text
"Analytical signal detected"
"Requires review"
"Unusual compared with selected baseline"
```

Do not present the signal as proof of criminality.

### Deliverable

System highlights measurable network/activity changes and allows the analyst to inspect the supporting evidence.

---

# Phase 15 — Search and Investigation Workspace

### Status
[ ] NOT STARTED

### Objective

Create the main analyst workflow.

### Search types

```text
Person
Phone
Vehicle
Location
Organization
Case
FIR
Transaction
```

### Advanced filters

```text
Entity type
Relationship type
Case
Date range
Location
Status
Community
Evidence source
```

### Workspace

```text
┌──────────────────────────────────────────────────────────┐
│ Search: Ram Singh                                      │
├───────────────────────────┬──────────────────────────────┤
│                           │ Entity Details               │
│       GRAPH               │                              │
│                           │ Name                         │
│    B ─── C                │ Status                       │
│   /     /                 │ Connections                  │
│  A ─── D                  │ Cases                        │
│    \                      │                              │
│     E                     │                              │
├───────────────────────────┴──────────────────────────────┤
│ Evidence / Timeline / Analysis                           │
└──────────────────────────────────────────────────────────┘
```

### Deliverable

An analyst can investigate a case without navigating unrelated administration screens.

---

# Phase 16 — Case Management

### Status
[ ] NOT STARTED

### Objective

Group people, evidence, relationships, and reports into investigations.

### Case structure

```text
CASE-2026-001

Title:
Network Investigation

Status:
Active

Assigned:
Analyst A
Analyst B

Entities:
P1
P2
P3

Evidence:
E1
E2
E3
```

### Features

- [ ] Create case.
- [ ] Assign analysts.
- [ ] Add entities.
- [ ] Add evidence.
- [ ] Case notes.
- [ ] Case status.
- [ ] Case history.
- [ ] Saved searches.
- [ ] Saved graph views.
- [ ] Case-specific reports.

### Deliverable

A complete investigation can be reopened later with its context intact.

---

# Phase 17 — AI Investigation Assistant / RAG

### Status
[ ] NOT STARTED

### Objective

Allow analysts to ask natural-language questions over structured graph data and evidence.

### Example queries

```text
What connects Ram Singh to Person X?

Show Ram Singh's second-degree connections.

Which relationships appeared in March?

What evidence supports the connection between A and B?

Summarize the selected network.
```

### Architecture

```text
Analyst Question
      ↓
Intent / Query Processing
      ↓
Graph Query + Evidence Retrieval
      ↓
Structured Results
      ↓
LLM
      ↓
Grounded Answer
      ↓
Citations / Evidence
```

### Critical rule

The LLM should not be the source of truth.

It should reason over:

```text
Neo4j results
PostgreSQL evidence
retrieved document snippets
analysis outputs
```

### Deliverable

An analyst can ask questions and receive answers tied to actual stored evidence.

---

# Phase 18 — Multi-Agent Intelligence Synthesis

### Status
[ ] NOT STARTED

### Objective

Use specialized AI components to synthesize findings into an intelligence report.

### Architecture

```text
                         Selected Case/Group
                                  ↓
                              Orchestrator
                                  │
              ┌───────────────────┼───────────────────┐
              ↓                   ↓                   ↓
        Demographic          Temporal            Geographic
           Agent               Agent                Agent
              ↓                   ↓                   ↓
              └───────────────────┼───────────────────┘
                                  ↓
                           Network Agent
                                  ↓
                         Evidence/Source Agent
                                  ↓
                             Aggregator
                                  ↓
                          Intelligence Report
```

### Initial agents

```text
Demographic analyst
Temporal analyst
Geographic analyst
Network analyst
Evidence/source analyst
Aggregator
```

### Deliverable

Select a criminal-network community/case and generate a structured analysis report.

---

# Phase 19 — Intelligence Reports

### Status
[ ] NOT STARTED

### Objective

Convert analytical output into a human-readable report.

### Suggested structure

```text
1. Case Overview

2. Key Entities

3. Network Structure

4. Important Network Positions

5. Relationship Summary

6. Temporal Findings

7. Geographic Findings

8. Financial/Communication Findings

9. Analytical Signals

10. Supporting Evidence

11. Analyst Notes

12. System Limitations
```

### Requirements

- [ ] Report preview.
- [ ] Evidence references.
- [ ] Graph snapshot.
- [ ] Timeline snapshot.
- [ ] Map snapshot.
- [ ] Export to PDF.
- [ ] Report versioning.
- [ ] Report audit trail.

### Deliverable

An analyst can produce an investigation report that points back to the underlying evidence.

---

# Phase 20 — Audit Logging

### Status
[ ] NOT STARTED

### Objective

Record which user performed which action, when, and on what data.

### Audit events

#### Data

```text
ENTITY_CREATED
ENTITY_UPDATED
ENTITY_ARCHIVED
RELATIONSHIP_CREATED
RELATIONSHIP_UPDATED
RELATIONSHIP_ARCHIVED
EVIDENCE_UPLOADED
ENTITY_MERGED
AI_EXTRACTION_APPROVED
AI_EXTRACTION_REJECTED
```

#### Investigation

```text
SEARCH_PERFORMED
CASE_VIEWED
ENTITY_VIEWED
EVIDENCE_VIEWED
GRAPH_ANALYSIS_RUN
REPORT_GENERATED
AI_QUERY_EXECUTED
```

#### Security

```text
LOGIN_SUCCESS
LOGIN_FAILURE
LOGOUT
USER_CREATED
USER_DISABLED
ROLE_CHANGED
PERMISSION_DENIED
```

### Example

```text
Timestamp: 25-09-2026 10:18:45
User: admin01
Role: ADMIN

Action:
UPDATE_ENTITY

Entity:
Person_1842

Field:
Phone

Old:
XXXXX1234

New:
XXXXX5678

Reason:
Updated from CDR_8291
```

### Architecture

```text
Application Action
       ↓
Backend
       ↓
Audit Service
       ↓
Append-oriented Audit Store
```

### Critical rule

Normal users must never be allowed to edit audit history.

### Deliverable

Supervisor/admin can filter and inspect user activity.

---

# Phase 21 — Security Hardening

### Status
[ ] NOT STARTED

### Objective

Protect sensitive investigative data and enforce access restrictions consistently.

### Tasks

- [ ] Password hashing.
- [ ] Secure session handling.
- [ ] Backend authorization.
- [ ] Input validation.
- [ ] File validation.
- [ ] SQL injection protection.
- [ ] Secure graph query construction.
- [ ] Secrets management.
- [ ] HTTPS in deployment.
- [ ] Access control on evidence files.
- [ ] Audit logging.
- [ ] Rate limiting where appropriate.
- [ ] Backup strategy.
- [ ] Data retention policy.
- [ ] Soft-delete/versioning.

### Deliverable

Security checklist completed and tested.

---

# Phase 22 — Evaluation and Testing

### Status
[ ] NOT STARTED

### Objective

Measure whether the system actually works rather than relying on visual demo quality.

### Test categories

#### Data extraction

Measure:

```text
Entity precision
Entity recall
Relationship precision
Relationship recall
```

#### Entity resolution

Measure:

```text
Correct merge rate
False merge rate
False non-merge rate
```

#### Graph analytics

Verify known synthetic network structures.

#### Search

Check:

```text
Exact entity lookup
Alias lookup
Multi-hop traversal
Filters
```

#### Security

Test:

```text
Analyst cannot edit.
Analyst cannot delete.
Analyst cannot approve.
Unauthorized API requests return 403.
```

#### AI

Check:

```text
Answers are grounded.
Evidence references exist.
No unsupported relationship is presented as fact.
```

### Deliverable

A reproducible evaluation report.

---

# Phase 23 — Synthetic Dataset and Demonstration Scenario

### Status
[ ] NOT STARTED

### Objective

Create a realistic demonstration dataset because real police/intelligence data should not be assumed to be available.

### Suggested structure

```text
datasets/
├── persons.csv
├── phones.csv
├── vehicles.csv
├── locations.csv
├── organizations.csv
├── cases.csv
├── cdr.csv
├── transactions.csv
├── events.csv
└── reports/
    ├── FIR_001.pdf
    ├── FIR_002.pdf
    └── report_001.txt
```

### Design

Create several interconnected communities:

```text
Community A
A ─ B ─ C
 \  │  /
   D

Community B
E ─ F ─ G
 \     /
   H

Bridge:
D ─ E
```

Add:

- documents
- calls
- transactions
- vehicles
- locations
- time changes
- duplicate names
- irrelevant entities
- noisy/incomplete records

### Deliverable

A dataset that demonstrates the system's ability to discover network structure from multiple sources.

---

# Phase 24 — End-to-End Integration

### Status
[ ] NOT STARTED

### Objective

Connect every component.

### End-to-end workflow

```text
Admin logs in
      ↓
Creates case
      ↓
Uploads FIR + CDR + transaction CSV
      ↓
System parses data
      ↓
NER extracts entities
      ↓
Entity resolution proposes matches
      ↓
Admin reviews candidates
      ↓
Approved facts enter graph
      ↓
Neo4j builds network
      ↓
Graph analytics run
      ↓
Communities/centrality/path results generated
      ↓
Analyst logs in
      ↓
Searches "Ram Singh"
      ↓
Graph opens around Ram Singh
      ↓
Analyst expands network
      ↓
Views evidence behind an edge
      ↓
Runs temporal/geographic analysis
      ↓
Asks AI assistant questions
      ↓
AI retrieves graph/evidence
      ↓
Report generated
      ↓
Audit log records all relevant actions
```

### Deliverable

A full working prototype from ingestion to analysis/report.

---

# Phase 25 — Deployment

### Status
[ ] NOT STARTED

### Objective

Package and deploy the application for demonstration.

### Prototype deployment options

```text
Frontend:
Vercel / static hosting

Backend:
Render / Railway / VM / Docker host

Database:
Hosted PostgreSQL or self-hosted

Graph:
Neo4j server/container

LLM:
Local Ollama during development/demo
```

### Recommended SIH demo architecture

If local hardware is sufficient:

```text
Laptop
├── React
├── FastAPI
├── PostgreSQL
├── Neo4j
└── Ollama
```

For a hosted demo:

```text
Browser
   ↓
Frontend
   ↓
Backend
 ┌─┴───────────────┐
 ↓                 ↓
PostgreSQL       Neo4j
                     │
                     ↓
              Analysis Services
                     │
                     ↓
                  LLM/API
```

### Deliverable

One reproducible deployment procedure.

---

# 6. Final Feature Checklist

## User and Security

- [ ] Login
- [ ] Logout
- [ ] Role-based access
- [ ] Admin
- [ ] Analyst
- [ ] Auditor/Supervisor
- [ ] User management
- [ ] Backend authorization
- [ ] Audit logs
- [ ] Security hardening

## Data

- [ ] Manual entity creation
- [ ] Entity editing
- [ ] Entity archival
- [ ] Evidence upload
- [ ] FIR ingestion
- [ ] PDF processing
- [ ] OCR
- [ ] CDR ingestion
- [ ] Transaction ingestion
- [ ] Report ingestion
- [ ] Batch import
- [ ] Metadata

## AI/NLP

- [ ] NER
- [ ] Entity normalization
- [ ] Relationship extraction
- [ ] Entity resolution
- [ ] Duplicate detection
- [ ] Human review queue
- [ ] RAG
- [ ] AI investigation assistant
- [ ] Multi-agent synthesis
- [ ] Report generation

## Graph

- [ ] Neo4j graph
- [ ] Person nodes
- [ ] Phone nodes
- [ ] Vehicle nodes
- [ ] Location nodes
- [ ] Organization nodes
- [ ] Case nodes
- [ ] FIR nodes
- [ ] Transaction nodes
- [ ] Event nodes
- [ ] Evidence references
- [ ] Search
- [ ] Multi-hop expansion
- [ ] Cycles
- [ ] Relationship labels
- [ ] Relationship evidence

## Analytics

- [ ] Degree centrality
- [ ] Betweenness centrality
- [ ] PageRank
- [ ] Community detection
- [ ] Shortest path
- [ ] Connected components
- [ ] Temporal analysis
- [ ] Geographic analysis
- [ ] Pattern detection

## Investigation

- [ ] Case management
- [ ] Saved investigations
- [ ] Saved graph views
- [ ] Evidence viewer
- [ ] Timeline
- [ ] Map
- [ ] AI assistant
- [ ] Intelligence reports
- [ ] Report export

---

# 7. Minimum Viable Prototype (MVP)

Do not attempt all phases before producing a working demonstration.

The recommended MVP is:

```text
1. Authentication + roles
2. PostgreSQL + Neo4j
3. Manual entity creation
4. CSV/FIR ingestion
5. Basic NER/entity extraction
6. Manual relationship creation
7. Entity search
8. Interactive graph
9. Evidence-linked relationships
10. Community detection
11. Centrality analysis
12. Audit logging
13. Basic AI assistant
14. Demonstration report
```

MVP workflow:

```text
Admin
 ↓
Upload/Create data
 ↓
Graph generated
 ↓
Analyst
 ↓
Search "Ram Singh"
 ↓
Interactive graph
 ↓
Inspect connections
 ↓
Run analysis
 ↓
Ask AI
 ↓
Generate report
```

---

# 8. Recommended Development Order

The safest implementation order is:

```text
FOUNDATION
Phase 0
   ↓
SECURITY
Phase 1
   ↓
DATA MODEL
Phase 2
   ↓
MANUAL DATA
Phase 3
   ↓
INGESTION
Phase 4
   ↓
NLP
Phase 5
   ↓
ENTITY RESOLUTION
Phase 6
   ↓
RELATIONSHIPS
Phase 7
   ↓
GRAPH UI
Phase 8
   ↓
VISUAL SEMANTICS
Phase 9
   ↓
EVIDENCE
Phase 10
   ↓
GRAPH ANALYTICS
Phase 11
   ↓
TIME
Phase 12
   ↓
GEOGRAPHY
Phase 13
   ↓
PATTERN DETECTION
Phase 14
   ↓
INVESTIGATION WORKSPACE
Phase 15
   ↓
CASE MANAGEMENT
Phase 16
   ↓
AI/RAG
Phase 17
   ↓
MULTI-AGENT AI
Phase 18
   ↓
REPORTS
Phase 19
   ↓
AUDIT
Phase 20
   ↓
SECURITY HARDENING
Phase 21
   ↓
EVALUATION
Phase 22
   ↓
DEMO DATA
Phase 23
   ↓
INTEGRATION
Phase 24
   ↓
DEPLOYMENT
Phase 25
```

---

# 9. Current Known Gaps

The following items were not fully specified yet and must be designed during implementation:

1. **Exact Neo4j schema and constraints**
2. **Exact PostgreSQL schema**
3. **Exact relationship taxonomy**
4. **Entity-resolution algorithm**
5. **NER/relationship-extraction model selection**
6. **Synthetic dataset design**
7. **Pattern-detection definitions and thresholds**
8. **Temporal-analysis methodology**
9. **Geographic-analysis methodology**
10. **AI model selection**
11. **RAG retrieval strategy**
12. **Multi-agent orchestration design**
13. **Evidence retention/access model**
14. **Audit-log storage and immutability strategy**
15. **Deployment architecture**
16. **Evaluation dataset and metrics**
17. **Performance/scalability requirements**
18. **Backup/recovery strategy**
19. **Security threat model**
20. **Data governance and retention rules**

These should be settled before the corresponding phases are marked complete.

---

# 10. Definition of Done

The project should not be considered complete merely because the graph appears on screen.

The system is considered functionally complete when:

```text
✓ Admin can authenticate
✓ Analyst can authenticate
✓ Analyst cannot modify source data
✓ Admin can create entities
✓ Admin can import evidence
✓ System extracts entities
✓ System proposes relationships
✓ Duplicate entities can be reviewed
✓ Approved data enters the graph
✓ Search can find a person/entity
✓ Graph supports cycles and many-to-many relationships
✓ Relationships have evidence/provenance
✓ Graph analysis identifies communities/structural metrics
✓ Temporal analysis works
✓ Geographic analysis works
✓ Analytical signals can be inspected
✓ AI answers are grounded in graph/evidence data
✓ Reports reference supporting evidence
✓ Every important user action is audited
✓ Security permissions are enforced server-side
✓ Tests demonstrate the above
```

---

# 11. Target End-State

```text
                         ┌───────────────────────┐
                         │       LOGIN           │
                         └───────────┬───────────┘
                                     ↓
                           ROLE-BASED ACCESS
                                     │
                 ┌───────────────────┼───────────────────┐
                 ↓                   ↓                   ↓
               ADMIN              ANALYST             AUDITOR
                 │                   │                   │
                 ↓                   ↓                   ↓
          DATA MANAGEMENT      INVESTIGATION          AUDIT
                 │                   │                   │
                 └──────────────┬────┘                   │
                                ↓                        │
                        EVIDENCE + DATA                  │
                                ↓                        │
                    NLP / ENTITY RESOLUTION              │
                                ↓                        │
                     KNOWLEDGE GRAPH                     │
                                ↓                        │
        ┌───────────────────────┼──────────────────────┐ │
        ↓                       ↓                      ↓ │
  GRAPH ANALYSIS          TEMPORAL ANALYSIS     GEO ANALYSIS
        └───────────────────────┼──────────────────────┘
                                ↓
                       PATTERN DETECTION
                                ↓
                       AI INVESTIGATION
                                ↓
                      INTELLIGENCE REPORT
                                │
                                └──────────────→ AUDIT LOG
```

---

# 12. Project Success Criteria

The final demonstration should make this scenario possible:

```text
1. Admin logs in.

2. Admin creates:
   "Vaibhav Suryavanshi"

3. Admin uploads an FIR and CDR data.

4. System extracts:
   Vaibhav
   Rahul
   Person C
   Vehicle X
   Location Y

5. Entity resolution finds an existing matching entity.

6. Admin reviews and approves candidate relationships.

7. Graph becomes:

              Rahul
             /     \
            /       \
       Vaibhav ─── Person C
          │
          │
       Vehicle X
          │
       Location Y

8. Analyst logs in.

9. Analyst searches:
   "Vaibhav Suryavanshi"

10. The graph centers on Vaibhav.

11. Analyst expands the network.

12. Analyst clicks an edge.

13. System shows the supporting evidence.

14. Analyst runs community/centrality analysis.

15. Analyst reviews time and location patterns.

16. Analyst asks:
    "What connects Vaibhav to Person C?"

17. AI retrieves graph/evidence data and answers with source references.

18. Analyst generates a report.

19. Audit log records the relevant actions.

20. Analyst still cannot edit or delete the underlying data.
```

This is the intended end-to-end behavior of the platform.
