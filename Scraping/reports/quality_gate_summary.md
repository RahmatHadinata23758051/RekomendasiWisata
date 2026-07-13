# Manual Quality Gate Audit Summary (Strict Deduplication & Relationship Constraints)
 
Generated on: 2026-07-13 13:27:38 UTC
 
## 1. Quality Gate Sampling Statistics
 
We extracted a manual validation sample size of **350** canonical attractions from the total canonical dataset of **4178** records (**3130** verified, **1048** candidates).
 
### Sampling Breakdown by Rule:
* **Rule 1 (Lowest Confidence Master Verified)**: Selected **50** records
* **Rule 2 (Regional Samples - Max 30/region)**:
  - *Bandar Lampung*: 30
  - *Pesawaran*: 30
  - *Tanggamus*: 30
* **Rule 3 (Category Samples - Max 30/category)**:
  - *Taman*: 30
  - *Rumah wisata*: 0
  - *Area Mendaki*: 30
  - *Tujuan Wisata*: 30
* **Rule 4 (Cross-Source Matches)**: Selected **23** records
* **Rule 5 (Parent-Child Candidates)**: Selected **108** records
* **Rule 6 (Large Clusters > 3 members)**: Selected **0** records
 
---
 
## 2. Comparison Dashboard: Before vs. After Strict Dedup & Relationships
 
Below is a comparison of clustering metrics before and after the strict matching and deduplication fixes:
 
| Metric | Before Fix (Initial Phase 3) | After Fix (Strict Rules) | Explanation / Status |
| :--- | :---: | :---: | :--- |
| **Total Raw Records** | 2012 | 2012 | Unchanged raw inputs |
| **Unique Normalized Source Records** | - | 4207 | Unique `source_record_id`s processed |
| **Duplicate Source Records** | 0 | 0 | Duplicate raw entries removed before clustering |
| **Unique Google Place IDs** | - | 4538 | Valid Google place IDs |
| **Verified Master Canonical** | 1016 | 3130 | Restructured master verified list |
| **Candidates (Manual Review)** | 240 | 1048 | Restructured candidate review list |
| **Total Canonical Attractions** | 1256 | 4178 | Clean places count (false-merges resolved) |
| **Large Clusters (> 3 members)** | 35 | 0 | Overlap resolved by separating Google place IDs |
| **Parent-Child Candidates** | 32 | 108 | Forbidden categories & administrative bounds excluded |

---

## 3. Cross-Source Match Verification

A total of **23** cross-source matches were mapped between OSM and Apify Google Maps:

| Canonical ID | Attraction Name | Region | Source Count | Conf. | Reason |
| :--- | :--- | :--- | :---: | :---: | :--- |
| `can_853a11bd5794` | Pulau Legundi | Kabupaten Pesawaran | 2 | 0.8 | Nama mengandung keyword wisata 'pulau' |
| `can_c4ca3400d56f` | Taman Andan Jejama | Kabupaten Pesawaran | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_a83c1c5c27a1` | Puncak Mas | Kota Bandar Lampung | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_1ec31e0e3248` | Lungsir (Taman Kota) | Kota Bandar Lampung | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_c27810efcd16` | GUNUNG KUNYIT | Kota Bandar Lampung | 2 | 0.9 | Kategori tambahan 'Tujuan Wisata' disetujui |
| `can_82067ed7cf9d` | Pantai Tiska | Kota Bandar Lampung | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_7a9334b27cd0` | Taman Kupu - kupu Gita Persada | bandar_lampung | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_c1bc4c579979` | Pantai Pasir Putih Lampung | Kabupaten Lampung Selatan | 2 | 1.0 | Kategori utama 'Pantai' disetujui |
| `can_845b99f05d46` | Bukit Sebesi | Kabupaten Lampung Selatan | 2 | 1.0 | Kategori utama 'Area Mendaki' disetujui |
| `can_fef02f56f107` | Menara Siger Lampung | Kabupaten Lampung Selatan | 2 | 0.9 | Kategori tambahan 'Tujuan Wisata' disetujui |
| `can_a1260500e511` | Danau Gunung Rajabasa | Kabupaten Lampung Selatan | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_ffab7f8e7a0e` | Pantai Aruna | lampung_selatan | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_6af587d9b6e7` | Pantai matahari | Kabupaten Way Kanan | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_a824d6390a30` | Taman Merdeka Kota Metro | Kota Metro | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_3f896a629afa` | Kolam Renang Tirta Garden | Kabupaten Tulang Bawang | 2 | 0.9 | Kategori tambahan 'Taman Rekreasi Air' disetujui |
| `can_164bf848907b` | TAMAN MERAH PUTIH | Kabupaten Tulang Bawang | 2 | 0.9 | Kategori 'Taman' disetujui dengan sinyal: high_reviews:38 |
| `can_c2d094e3ef65` | Tugu Rato Nago Besanding | Kabupaten Tulang Bawang | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_7132d82ced94` | Tugu Empat Marga | Kabupaten Tulang Bawang | 2 | 0.9 | Kategori 'Taman' disetujui dengan sinyal: high_reviews:576 |
| `can_e2386ad849b6` | Rumah Baduy | Kabupaten Tulang Bawang | 2 | 1.0 | Kategori utama 'Tujuan Wisata' disetujui |
| `can_a3377ed6007d` | Monumen Latsitarda Nusantara | Kota Metro | 2 | 0.5 | Kategori 'Historic=Monument' tidak terklasifikasi secara otomatis |
| `can_62808000187d` | Samber Park | Kota Metro | 2 | 0.5 | Kategori 'Leisure=Park' tidak terklasifikasi secara otomatis |
| `can_6bd808f24afc` | Tugu Gajah | Kabupaten Tulang Bawang | 2 | 0.5 | Kategori 'Historic=Memorial' tidak terklasifikasi secara otomatis |
| `can_1d8adb263ba4` | Tugu Kuning | Kabupaten Tulang Bawang | 2 | 0.5 | Kategori 'Historic=Memorial' tidak terklasifikasi secara otomatis |

---

## 4. Parent-Child Relationship Validation

A total of **108** parent-child hierarchical relations were discovered (e.g. sub-areas inside tourist hubs):

| Child ID | Child Name | Parent ID | Parent Name | Relationship | Region |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `can_70bfb5652427` | Dermaga Pulau Pahawang | `can_2f1e94eb24ec` | Pahawang Hill | supporting_facility | Kabupaten Pesawaran |
| `can_21928a3ca9de` | Puncak Bukit Cendana Pesawaran | `can_fe10d68d03bf` | Cendana Hill | part_of | Kabupaten Pesawaran |
| `can_407c465cf042` | Bukit Lantana Harapan Jaya | `can_3d0f6440180a` | Bukit lantana hill | part_of | Kabupaten Pesawaran |
| `can_ce75c5fe5798` | Cendana Mountain Bike Park | `can_fe10d68d03bf` | Cendana Hill | part_of | Kabupaten Pesawaran |
| `can_7af367afd628` | Sea WALKER KAISAR 77 PAHAWANG | `can_72917b91abc9` | Pahawang | part_of | Kabupaten Pesawaran |
| `can_f604d891a913` | Bumi pahawang | `can_368c5de894ed` | Pahawang Lampung | part_of | Kabupaten Pesawaran |
| `can_0f60852f3c11` | Transportasi Wisata Pulau Pahawang | `can_368c5de894ed` | Pahawang Lampung | supporting_facility | Kabupaten Pesawaran |
| `can_30eaefdc41b3` | Tugu Andan Jejama | `can_c4ca3400d56f` | Taman Andan Jejama | part_of | Kabupaten Pesawaran |
| `can_6eb1da7f1da3` | Air Terjun Kembar Congkanan | `can_c9b025286915` | Air Terjun Congkanan | part_of | Kabupaten Pesawaran |
| `can_4ad7ab41cb4e` | Spot garuda pahawang | `can_a7cf142969c4` | Pulau Pahawang | part_of | Kabupaten Pringsewu |
| `can_d07c4583a3c3` | mahitam water sport | `can_a8372c17cf4a` | Pulau Mahitam | part_of | Kabupaten Pesawaran |
| `can_ed8fc5d7db0f` | Pemandian Way Bekhak Sukaraja Gunung Alip | `can_7fae442aebe1` | Wisata Way Bekhak | part_of | Kabupaten Tanggamus |
| `can_ee5ff556f388` | Mata Air Way Bekhak 1 | `can_7fae442aebe1` | Wisata Way Bekhak | part_of | Kabupaten Tanggamus |
| `can_39a2af1abeff` | Mata Air Sumberagung1 | `can_52cc19be8eb4` | Wisata mata air | part_of | Kabupaten Tanggamus |
| `can_4f1bfa421215` | Wisata Mata Air Gunung Batu | `can_52cc19be8eb4` | Wisata mata air | part_of | Kabupaten Tanggamus |
| `can_ce5ba0fb04fc` | Sumber Mata Air Gunung Batu Margoyoso | `can_52cc19be8eb4` | Wisata mata air | part_of | Kabupaten Tanggamus |
| `can_314f5e9fd57e` | PARKIRAN WISATA MATA AIR GUNUNG BATU | `can_52cc19be8eb4` | Wisata mata air | supporting_facility | Kabupaten Tanggamus |
| `can_21b9dc99890c` | Tempat parkir wisata mata air gunung batu margoyoso | `can_52cc19be8eb4` | Wisata mata air | supporting_facility | Kabupaten Tanggamus |
| `can_06a8860a98bf` | Ganong mata air | `can_52cc19be8eb4` | Wisata mata air | part_of | Kabupaten Tanggamus |
| `can_a18590c2c3ef` | Air Terjun Lembah Pelangi Ulu Belu | `can_16a84b2157c9` | Ulu belu | part_of | Kabupaten Tanggamus |
| `can_177c6c51d925` | Puncak Danau Datarajan Ulu Belu | `can_489adbb1874d` | Danau Datarajan Ulu Belu | part_of | Kabupaten Tanggamus |
| `can_826c830eabfd` | Pantai Cemara Beach & Camp Digul | `can_b93b4d46f388` | Pantai digul | part_of | Kabupaten Tanggamus |
| `can_27755fab1d65` | PANTAI KAKHANG BETUAH | `can_c8fd3e10382c` | PANTAI KARANG BETUAH | part_of | Kabupaten Tanggamus |
| `can_c056aa1c2f94` | WISATA KAKHANG BUTUAH | `can_c8fd3e10382c` | PANTAI KARANG BETUAH | part_of | Kabupaten Tanggamus |
| `can_766f1d9f9503` | Water Park Lembah Hijau | `can_e84e0ea3bf6e` | Lembah Hijau | part_of | Kota Bandar Lampung |
| `can_9d76158a16fb` | WaterBoom Bumi Kedaton | `can_0ad2418d63a8` | Bumi Kedaton | part_of | Kota Bandar Lampung |
| `can_ed7f9c6ccdc4` | Kawasan Wisata Sumur Putri | `can_b2c7612518ee` | Wisata Bendungan Sumur Putri | part_of | Kota Bandar Lampung |
| `can_0c2deb114fc2` | Water Park Citra Garden | `can_28b6929cc728` | Citra park | part_of | Kota Bandar Lampung |
| `can_888a2fed8be4` | Gunung Kunyit Beach View | `can_ccc3429daa80` | Pantai Gunung Kunyit | part_of | Kota Bandar Lampung |
| `can_80029d4ae3b3` | PANTAI BERENANG GUNUNG KUNYIT | `can_ccc3429daa80` | Pantai Gunung Kunyit | part_of | Kota Bandar Lampung |
| `can_b0ebb1ca0267` | Dermaga Pulau Pasaran | `can_2ec50156ee10` | Pulau Pasaran | supporting_facility | Kota Bandar Lampung |
| `can_aa9d73e70104` | Waterpark Lampung Walk (Kolam Renang) | `can_7f41ce785335` | Lampung Walk | part_of | Kota Bandar Lampung |
| `can_ec7cf36a981f` | The Hidden Valley Bukit AsLan | `can_552f46f415b2` | Bukit AsLan | part_of | Kota Bandar Lampung |
| `can_7ce6b3eb2c5d` | Taman Citra Garden | `can_28b6929cc728` | Citra park | part_of | Kota Bandar Lampung |
| `can_196eb6893fde` | The Lookout Bukit AsLan | `can_552f46f415b2` | Bukit AsLan | part_of | Kota Bandar Lampung |
| `can_ad4b0475b43f` | Gapura Taman Dipangga | `can_64a16e717f69` | Taman Dipangga | supporting_facility | Kota Bandar Lampung |
| `can_4631509873a3` | AsLan Grind | `can_552f46f415b2` | Bukit AsLan | part_of | Kota Bandar Lampung |
| `can_12d8825d0909` | Samar Scout Camp | `can_cc6f835b357a` | Samar Scout Park | part_of | Kota Bandar Lampung |
| `can_e9be3090afa2` | Wisata alam taman pemancingan embung korpri. | `can_cb9dde06484c` | Embung Korpri | part_of | Kota Bandar Lampung |
| `can_db97bb85aeb9` | MARTADINATA HILLS | `can_08949ca78fa3` | BUKIT MARTADINATA | part_of | Kota Bandar Lampung |
| `can_bae008dad41f` | Embung A Rusa Unila | `can_441f94bd6544` | Embung Rusun Unila | part_of | Kota Bandar Lampung |
| `can_5a738d61ac3f` | Wisata Panas Bumi, Kawah Keramikan | `can_3e4f17692bd2` | keramikan | part_of | Kabupaten Lampung Barat |
| `can_309109cc8168` | MT Seminung, 1881 Mdpl | `can_09eab61857c4` | Gunung Seminung | part_of | Kabupaten Lampung Barat |
| `can_532feffd7ed7` | Puncak gunung seminung | `can_09eab61857c4` | Gunung Seminung | part_of | Kabupaten Lampung Barat |
| `can_cf58eaceddcb` | Taman Mangrove Sebalang | `can_6c74802a455b` | Pantai Sebalang | part_of | Kabupaten Lampung Selatan |
| `can_980bd89665b5` | Pantai terjun karya tunggal | `can_337f2f6145c1` | Air Terjun karya tunggal | part_of | Kabupaten Lampung Selatan |
| `can_f6c8a95c001d` | Sebalang Sky | `can_cc5b07aa8b21` | Pantai Sebalang | part_of | Kabupaten Lampung Selatan |
| `can_64dd7b48addf` | SunShine Sebalang 2 | `can_cc5b07aa8b21` | Pantai Sebalang | part_of | Kabupaten Lampung Selatan |
| `can_c1bc4c579979` | Pantai Pasir Putih Lampung | `can_7bcbf31788c6` | PANTAI PULAU PASIR BEACH | part_of | Kabupaten Lampung Selatan |
| `can_728d55111f91` | Pantai Kedu Kalianda | `can_659be032d2f6` | PANTAI KEDU | part_of | Kabupaten Lampung Selatan |
| `can_c5aa5e50b300` | Monumen Titik Nol Sumatera | `can_ed9359e93b2f` | Monumen | part_of | Kabupaten Lampung Selatan |
| `can_b7f060291e76` | wisata WBK (Way Benteng Kedagaan) | `can_24b78c6de8d2` | Benteng Kedagaan | part_of | Kabupaten Lampung Selatan |
| `can_11b96d806fd8` | Cagar Alam Krakatau | `can_53307eeec0d9` | Gunung Anak Krakatau | part_of | Kabupaten Lampung Selatan |
| `can_d1cf2f044b51` | Gn. Anak Krakatau | `can_cfab21205975` | Krakatau | part_of | Kabupaten Lampung Selatan |
| `can_53307eeec0d9` | Gunung Anak Krakatau | `can_11b96d806fd8` | Cagar Alam Krakatau | part_of | Kabupaten Lampung Selatan |
| `can_4eb52d1d5169` | Pantai Indah Belebuk | `can_5c4dde9e5bf5` | PANTAI BELEBUK | part_of | Kabupaten Lampung Selatan |
| `can_f705e4bf0d9c` | Pantai Ketang Kalianda | `can_d7d82aec61d9` | Pantai Ketang | part_of | Kabupaten Lampung Selatan |
| `can_919b45c35e31` | Pantai Minatara 741 | `can_eb6317412c0f` | Pantai Minatara | part_of | Kabupaten Lampung Selatan |
| `can_fcc216e31506` | Pantai Marina Kalianda | `can_85b87787980e` | Bukit Marina | part_of | Kabupaten Lampung Selatan |
| `can_ec955508a2bd` | Kolam Renang Perahu Layar | `can_5d2895007176` | Taman wisata perahu layar | part_of | Kabupaten Lampung Selatan |
| `can_1f304164e9fa` | Djayataruna Stable & ATV | `can_aaa94594d2d1` | TAMAN DJAYATARUNA | part_of | Kabupaten Lampung Selatan |
| `can_12ff021283fa` | Pasir wisata pasir putih | `can_4f64108d7958` | Pantai Pasir Putih | part_of | Kabupaten Lampung Selatan |
| `can_f864d43fd3cc` | Pantai Kedu Sinar Laut | `can_659be032d2f6` | PANTAI KEDU | part_of | Kabupaten Lampung Selatan |
| `can_1fb1c511c506` | BakPao Muli Pantai Rio by The Beach | `can_5560bbd41770` | Rio by the Beach | part_of | Kabupaten Lampung Selatan |
| `can_8d375cc9cb1f` | Warung ARA PANTAI SEBALANG TARAHAN | `can_64f46326a2b7` | Pantai Sebalang | part_of | Kabupaten Lampung Selatan |
| `can_a52291d6c394` | Tanjung BEO Wanawisata Nirwana Resort | `can_c80155cbe239` | Tanjung Beo Wanawisata | part_of | Kabupaten Lampung Selatan |
| `can_9fad5fbafeef` | Pantai Laguna Helau | `can_cee540673e7c` | Laguna Beach | part_of | Kabupaten Lampung Selatan |
| `can_a464728f5a36` | Pantai Balam Kerbang Dalam | `can_9716942de720` | PANTAI KERBANG DALAM | part_of | Kabupaten Pesisir Barat |
| `can_d4fc4735c51f` | labuhan agung bangun jaya rumput hijau | `can_7e43cd9d85ce` | Pantai Rumput Hijau | part_of | Kabupaten Lampung Barat |
| `can_ba1f39445aa6` | Pantai Mandiri Sejati | `can_674a3310683d` | Mandiri Beach | part_of | Kabupaten Pesisir Barat |
| `can_ac9542293833` | Taman Wisata Mangrove Pandan Alas | `can_8ae92ca66d1c` | Wisata Mangrove | part_of | Kabupaten Lampung Timur |
| `can_15ce9fe4cc29` | Danau Way Jepara | `can_c4a086126838` | Danau Jepara | part_of | Kabupaten Lampung Timur |
| `can_b1b50e6ade51` | Kantor P.U. IRIGASI Way Curup | `can_1452f8759a48` | Taman Wisata Way Curup | supporting_facility | Kabupaten Lampung Timur |
| `can_f4594b00305f` | Kali Jodoh Embung Nibung | `can_f0398006417a` | Embung Nibung | part_of | Kabupaten Lampung Timur |
| `can_ae95dfc8a347` | Ekowisata Sekar Bahari Mangrove | `can_e8b6a18ad91f` | Wisata mangrove | part_of | Kabupaten Lampung Timur |
| `can_ddc5b32a3358` | Lapangan BRAJAHARJOSARI | `can_9637870b388f` | Pasar Braja Harjosari | part_of | Kabupaten Lampung Timur |
| `can_293085f0a3b3` | EMBUNG ALBARET | `can_7ddab2d24437` | Bendungan ALBARET | part_of | Kabupaten Mesuji |
| `can_d2a5833be885` | Gedung Serba Guna Taman Kehati | `can_77e1a6639a59` | taman kehati | part_of | Kabupaten Mesuji |
| `can_568466310410` | Taman edukasi dunia mini metro | `can_fcd82d5999c4` | Taman edukasi dunia mini | part_of | Kota Metro |
| `can_9d7add241ed0` | Kolam renang palem indah | `can_29e2667ea7e8` | Taman Palem Indah | part_of | Kota Metro |
| `can_4bc67db7d6aa` | Taman berwarna pingled 2 satoe | `can_8692c6df0122` | Taman berwarna pingled 21 | part_of | Kota Metro |
| `can_8e00b4d0ae6c` | Pesona Ratu Banyu | `can_f62c53b46c9c` | Wisata Ratu Banyu | part_of | Kabupaten Pringsewu |
| `can_dfff89960232` | Wisata Ndoro Putri (view jembatan way sekampung) | `can_5d670d763313` | Jembatan Way Sekampung Lampung | part_of | Kabupaten Pringsewu |
| `can_077dc38b92d3` | Pelangi Alam Mesir | `can_e0fad3cf3475` | Wisata Alam Mesir | part_of | Kabupaten Tulang Bawang |
| `can_22faa9c0e490` | Kebun Melon KWT sumber Makmur | `can_5374ecfac07e` | KWT SUMBER MAKMUR | part_of | Kabupaten Tulang Bawang |
| `can_4c62e61290d5` | TUGU RUSA UNIT 6 | `can_d9a16d0a44f2` | Taman Unit 6 | part_of | Kabupaten Tulang Bawang |
| `can_6b48ec836685` | Tugu Pahlawan | `can_5f60267e67d0` | Taman Pahlawan | part_of | Kota Bandar Lampung |
| `can_2d3fce863547` | Satwa Wahana & Wisata Bumi Kedaton | `can_0ad2418d63a8` | Bumi Kedaton | part_of | Kota Bandar Lampung |
| `can_a0aaeb7fda40` | PKOR Way Halim | `can_e0dcdc276e60` | Taman PKOR | part_of | Kota Bandar Lampung |
| `can_9da03a9ac30d` | Water Park Rizky | `can_142b17bd8cbe` | WaterPark RIZKY | part_of | Kabupaten Way Kanan |
| `can_70fbe85ed607` | Taman megalitik batu bedil | `can_03b7171937f6` | Situs Batu Bedil | part_of | Kabupaten Tanggamus |
| `can_5ad8fc6842b4` | Camping Ground GIGI HIU by BAGASFEKA | `can_aa342a79126c` | Pantai Gigi Hiu | part_of | Kabupaten Tanggamus |
| `can_cedc500a3de0` | Gn. Kunyit | `can_c27810efcd16` | GUNUNG KUNYIT | part_of | Kota Bandar Lampung |
| `can_a983eab09d09` | Gn. Balau | `can_03cb6fd424e4` | Gunung balau | part_of | Kota Bandar Lampung |
| `can_0ae829cf1954` | Gedung Sumpah Pemuda (PKOR) | `can_e0dcdc276e60` | Taman PKOR | part_of | Kota Bandar Lampung |
| `can_350b9b6775ff` | Gn. Seminung | `can_09eab61857c4` | Gunung Seminung | part_of | Kabupaten Lampung Barat |
| `can_fa2170c8a72a` | WAY BELERANG SIMPUR KECAPI | `can_4851c4908302` | sumber air panas way belerang | part_of | Kabupaten Lampung Selatan |
| `can_785cf174cc74` | Pemandian Air Panas di Laut, Kalianda | `can_c3038b1551ba` | Air Panas di Pantai Kalianda | part_of | Kabupaten Lampung Selatan |
| `can_c19a5d1dcdd9` | Sertung National Park | `can_7a97f39c1957` | Pulau Sertung | part_of | Kabupaten Lampung Selatan |
| `can_eddd80f62a3f` | Masjid Pemandian Air Panas | `can_6a242d174088` | Pemandian Air Panas | part_of | Kabupaten Lampung Selatan |
| `can_eed901ecf3b8` | Simpang Pantai Pasir Putih | `can_c1bc4c579979` | Pantai Pasir Putih Lampung | part_of | Kabupaten Lampung Selatan |
| `can_f9b6a0b172d3` | Pantai Batu rame ketang | `can_d7d82aec61d9` | Pantai Ketang | part_of | Kabupaten Lampung Selatan |
| `can_f28fd1a89fc9` | Pulau Anak Krakatau | `can_cfab21205975` | Krakatau | part_of | Kabupaten Lampung Selatan |
| `can_b9b550654ecd` | Pantai mandiri family keday | `can_674a3310683d` | Mandiri Beach | part_of | Kabupaten Pesisir Barat |
| `can_0b0ac1c947a0` | Musholla Pasar Taman Negeri | `can_9567efc78322` | Pasar Taman Negeri | part_of | Kabupaten Lampung Timur |
| `can_008e68946f87` | Pemandian kali Nangan | `can_019307aff9e1` | PEMANDIAN AIR NANGAN | part_of | Kabupaten Way Kanan |
| `can_ce60cd149ca6` | TPU SAMBER | `can_62808000187d` | Samber Park | part_of | Kota Metro |
| `can_99fcc10b6d7c` | Waterboom Metro Garden | `can_c83568b17545` | Metro garden | part_of | Kota Metro |

---

## 5. Large Clusters (> 3 Members)

Below are the canonical attraction profiles created from combining more than 3 raw records:

| Canonical ID | Attraction Name | Region | Source Count | Mapped Sources |
| :--- | :--- | :--- | :---: | :--- |
