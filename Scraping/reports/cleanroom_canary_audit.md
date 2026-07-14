# Clean-Room Canary Verification Audit Report

## 1. Summary of Canary Results
This report documents the verification results of three canary destinations in the Lampung Recommendation system using live downloaded content from public sources (Wikipedia, DetikTravel).

### Canary Attractions Table
| Canonical ID | Name | Requested URL | HTTP Status | Excerpt Found | Price Text Found | Audit Status | Audit Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `can_1fef284e7d10` | Dermaga Pulau Pahawang | [https://id.wikipedia.org/wiki/Pulau_Pahawang](https://id.wikipedia.org/wiki/Pulau_Pahawang) | 200 | False | True | **failed** | Failed content match: excerpt not found, identity text not found |
| `can_151f3bbf542d` | Pantai Mutun | [https://travel.detik.com/domestik/d-7301072/pantai-mutun-pantai-pasir-putih-terpopuler-di-pesawaran-lampung](https://travel.detik.com/domestik/d-7301072/pantai-mutun-pantai-pasir-putih-terpopuler-di-pesawaran-lampung) | 200 | False | True | **failed** | Failed content match: excerpt not found, identity text not found |
| `can_58c471e76647` | Slanik Waterpark Lampung | [https://travel.detik.com/](https://travel.detik.com/) | 200 | False | True | **failed** | Failed content match: excerpt not found, identity text not found |

## 2. Key Findings & Provenance Decisions
- **Dermaga Pulau Pahawang (`can_1fef284e7d10`)**:
  - *Source URL*: Wikipedia (`id.wikipedia.org`)
  - *Source Type*: Reference
  - *Audit*: Retrievable (200 OK), but the expected price excerpt (`Sewa kapal penyebrangan perahu kayu ...`) and price numbers were not found in the live downloaded HTML. Wikipedia does not host real-time pricing.
  - *Decision*: Rejected. Mapped to `unresolved` (temporal status cannot become `verified_current` or `official_live_unbounded` on references).

- **Pantai Mutun (`can_151f3bbf542d`)**:
  - *Source URL*: DetikTravel (`travel.detik.com`)
  - *Source Type*: News Media
  - *Audit*: Retrievable (200 OK), but the DetikTravel URL redirected to an unrelated general news story. The required pricing excerpt and numbers were not found in the page text.
  - *Decision*: Rejected. Mapped to `unresolved` (news media cannot produce `official_live_unbounded`).

- **Slanik Waterpark Lampung (`can_58c471e76647`)**:
  - *Source URL*: DetikTravel (`travel.detik.com`)
  - *Source Type*: News Media
  - *Audit*: Retrievable (200 OK), but the news media homepage lacks the specific Slanik pricing excerpt.
  - *Decision*: Rejected. Mapped to `unresolved`.

