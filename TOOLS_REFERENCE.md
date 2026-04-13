# Crimson Desert Unpacker — 도구 및 데이터 레퍼런스

## 목차

- [1. 구현된 기능 요약](#1-구현된-기능-요약)
- [2. Python 스크립트 설명 및 사용법](#2-python-스크립트-설명-및-사용법)
- [3. CSV 데이터 파일 설명](#3-csv-데이터-파일-설명)

---

## 1. 구현된 기능 요약

### 1.1 PAZ 아카이브 추출 (Core)

- **PAMT 인덱스 파싱**: `.pamt` 파일에서 파일 목록, 오프셋, 크기, 플래그 추출
- **ChaCha20 복호화**: 파일명 기반 키 유도(Bob Jenkins hashlittle) + ChaCha20 스트림 암호 복호화
- **LZ4 블록 압축 해제**: PAMT 메타데이터의 compression_type=2 기반 자동 해제
- **DDS 내부 LZ4 해제**: DDS 헤더의 `reserved[0]` 필드를 감지하여 픽셀 데이터 내부 LZ4 자동 해제 (멀티밉맵 지원)
- **paloc 로컬라이제이션 복호화**: `.paloc` 파일 자동 복호화 + LZ4 해제 (0019~0032 다국어 데이터)
- **리팩킹**: 수정된 파일을 원본 PAZ에 정확한 크기로 재패킹 (NTFS 타임스탬프 보존)

### 1.2 게임 데이터 파싱

- **PABGB/PABGH 파서**: 게임 바이너리 데이터 테이블 파싱 (거점, NPC, 웨이포인트 등)
- **PARC palevel 파서**: 월드 씬 오브젝트 배치 데이터에서 자원 노드 좌표 휴리스틱 추출

### 1.3 맵 데이터 추출

- **자원 노드 좌표 추출**: 19,748개 palevel 파일에서 광물/채집물 월드 좌표 일괄 추출
- **거점/POI 좌표 추출**: factionnode에서 1,126개 마을/거점 좌표 + 타입 분류 + 지역 분류
- **아이콘 매핑**: `uimaptextureinfo` + `cd_icon_map_*.xml` 스프라이트 아틀라스 → 거점/자원 타입별 아이콘 매핑
- **로컬라이제이션**: 14개 언어 paloc 추출, 116,400개 영한 번역 매핑

### 1.4 GUI (C# / Avalonia)

- 폴더 단위 PAMT 로딩 및 트리뷰 탐색 (레이지 로딩, 페이지네이션)
- 검색, 전체/선택/검색결과 추출
- DDS 내부 LZ4 자동 해제 포함

---

## 2. Python 스크립트 설명 및 사용법

### 2.1 `paz_parse.py` — PAMT 인덱스 파서

PAMT 인덱스 파일을 파싱하여 PAZ 아카이브의 파일 목록을 조회합니다.

```bash
# 아카이브 내용 조회
python paz_parse.py /path/to/0.pamt --paz-dir /path/to/0003

# 특정 파일 필터링
python paz_parse.py /path/to/0.pamt --filter "*.xml"

# 통계 표시
python paz_parse.py /path/to/0.pamt --stats
```

**출력**: 파일 경로, 압축/원본 크기, PAZ 인덱스, 오프셋, 암호화/압축 상태

---

### 2.2 `paz_unpack.py` — PAZ 아카이브 추출기

PAZ 아카이브에서 파일을 추출하며, 자동으로 복호화(ChaCha20), LZ4 해제, DDS 내부 LZ4 해제, paloc 복호화를 수행합니다.

```bash
# 전체 추출
python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 -o output/

# XML 파일만 추출
python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 -o output/ --filter "*.xml"

# 로컬라이제이션 파일 추출 (0019=한국어, 0020=영어)
python paz_unpack.py /path/to/0019/0.pamt --paz-dir /path/to/0019 -o output/

# 드라이런 (추출하지 않고 목록만)
python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 --dry-run

# 상세 로그
python paz_unpack.py /path/to/0.pamt --paz-dir /path/to/0003 -o output/ -v
```

**지원 포맷**:
| 파일 타입 | 처리 |
|---|---|
| `.xml` (암호화 폴더) | ChaCha20 복호화 → LZ4 해제 |
| `.paloc` | ChaCha20 복호화 → LZ4 해제 |
| `.dds` (내부 LZ4) | DDS 헤더 감지 → 밉맵별 LZ4 해제 |
| 기타 | LZ4 해제 (플래그 기반) |

---

### 2.3 `paz_crypto.py` — 암호화/압축 라이브러리

ChaCha20 암/복호화, Bob Jenkins hashlittle 해시, LZ4 압축/해제를 제공합니다.

```python
from paz_crypto import decrypt, encrypt, lz4_decompress, lz4_compress, derive_key_iv

# 복호화
plaintext = decrypt(ciphertext, "filename.xml")

# 키 유도
key, iv = derive_key_iv("filename.xml")

# LZ4 해제
decompressed = lz4_decompress(compressed_data, original_size)
```

**의존성**: `cryptography`, `lz4`

---

### 2.4 `paz_repack.py` — PAZ 리패커

수정된 파일을 원본 PAZ 아카이브에 재패킹합니다. 정확한 크기 매칭, NTFS 타임스탬프 보존을 수행합니다.

```bash
# 수정된 XML 리팩
python paz_repack.py modified.xml --pamt 0.pamt --paz-dir ./0003 --entry "technique/rendererconfiguration.xml"

# 별도 파일로 출력
python paz_repack.py modified.xml --pamt 0.pamt --paz-dir ./0003 --entry "path/to/file" --output repacked.bin
```

---

### 2.5 `pabg_parse.py` — PABGB 게임 데이터 파서

`.pabgb`(데이터) + `.pabgh`(인덱스) 파일 쌍을 파싱하여 레코드 이름과 XYZ 월드 좌표를 추출합니다.

```bash
# 단일 파일 파싱
python pabg_parse.py /path/to/factionnode.pabgb

# 디렉토리 내 전체 파싱
python pabg_parse.py /path/to/gamedata/ --all

# CSV 내보내기
python pabg_parse.py /path/to/gamedata/ --all --csv output.csv

# 이름 필터링
python pabg_parse.py /path/to/gamedata/ --all --filter "Village"
```

**PABGB 포맷**:
- `.pabgh`: `uint16 count` + count × `(uint16 type_id, uint16 flags, uint32 offset)`
- `.pabgb`: 각 오프셋에 `uint16 type, uint16 pad, uint32 name_len, char[name_len], null, float32 X, float32 Y, float32 Z, ...`

---

### 2.6 `palevel_extract.py` — PARC palevel 자원 노드 추출기

`.palevel` 파일(PARC 포맷)에서 자원 오브젝트의 월드 배치 좌표를 휴리스틱으로 추출합니다.

```bash
# 단일 파일
python palevel_extract.py /path/to/sector_-16_14.palevel

# 전체 leveldata 스캔 (광물만)
python palevel_extract.py /path/to/leveldata/ --all --filter "mine" --csv mines.csv

# 채집물 추출
python palevel_extract.py /path/to/leveldata/ --all --filter "collect" --csv collect.csv

# 전체 자원 추출 (필터 없음)
python palevel_extract.py /path/to/leveldata/ --all --filter "" --csv all.csv

# 상세 로그
python palevel_extract.py /path/to/leveldata/ --all --filter "mine" -v
```

**자원 타입 자동 분류**: gold, iron, silver, copper, diamond, ruby, bismuth, bluestone, redstone, whitestone, greenstone, coal, tin, salt, sulfur, mercury, chaya, ensete, kudzu, dulse, amaranth, taro, chlorella, jijeongta, collect, herb, fish, wood, farm, rubber 등

---

### 2.7 `build_icon_mapping.py` — 아이콘 매핑 테이블 생성기

`cd_icon_map_*.xml` 스프라이트 아틀라스 정의 파일을 파싱하여 거점/자원 타입 → 아이콘 스프라이트 매핑 테이블을 생성합니다.

```bash
python build_icon_mapping.py
```

**사전 조건**: `cd_icon_map_00.xml` ~ `cd_icon_map_05.xml`이 `C:/Users/denni/AppData/Local/Temp/cd_ui2/ui/`에 추출되어 있어야 합니다.

**출력**: `icon_mapping.csv` — 83개 타입 × 아이콘 스프라이트 좌표 매핑

---

### 2.8 `test_all.py` — 테스트 스위트

PAMT 파싱, 키 유도, ChaCha20, LZ4, 리팩 라운드트립 등 전체 테스트를 수행합니다.

```bash
python test_all.py
```

---

## 3. CSV 데이터 파일 설명

### 3.1 핵심 데이터 (맵에 직접 사용)

| 파일 | 행 수 | 크기 | 설명 | 컬럼 |
|---|---|---|---|---|
| **`factionnode_translated.csv`** | 1,126 | 98 KB | 거점/POI (지역+타입 분류, 영한 번역 포함) | name, region, type, en_name, kr_name, x, y, z |
| **`mine_placements_clean.csv`** | 5,958 | 878 KB | 광물 노드 (장식물 제거, 14종 분류) | sector, resource_type, resource, x, y, z, resource_full |
| **`gathering_placements.csv`** | 372 | 38 KB | 채집물 (버섯/과일/특수 세분화) | sector, category, subtype, resource, x, y, z |
| **`icon_mapping.csv`** | 83 | 7 KB | 타입→아이콘 스프라이트 매핑 | map_type, icon_name, dds_file, rect_x, rect_y, rect_w, rect_h, exists |
| **`localization_en_kr.csv`** | 116,400 | 15.6 MB | 영어↔한국어 전체 번역 | string_id, english, korean |

### 3.2 보조 데이터

| 파일 | 행 수 | 크기 | 설명 |
|---|---|---|---|
| `gamedata_coords.csv` | 25,437 | 2.4 MB | PABGB 전체 좌표 데이터 (actionpoint, factionnode, waypoint 등 통합) |
| `factionnode_classified.csv` | 1,126 | 73 KB | 거점 분류 (번역 없는 버전) |
| `localization_kor.csv` | 10,264 | 612 KB | 한국어 로컬라이제이션 (단일 언어, 초기 파서 버전) |
| `all_resources.csv` | 28,918 | 4.3 MB | 모든 자원 통합 (광물+채집+약초+낚시 등, 정제 전) |
| `all_palevel_resources.csv` | 768,329 | 102 MB | palevel 전체 스캔 결과 (필터 없음, 자연물/장식물 포함) |

### 3.3 자원 타입별 개별 CSV

| 파일 | 행 수 | 설명 |
|---|---|---|
| `mine_placements.csv` | 12,382 | 광물 전체 (정제 전, 장식물 포함) |
| `collect_placements.csv` | 14,037 | 채집 오브젝트 전체 (바위 12,853개 포함) |
| `herb_placements.csv` | 1,602 | 약초 관련 (대부분 장식물) |
| `fish_placements.csv` | 752 | 낚시 관련 (대부분 장식물, 실제 낚시포인트는 gamedata_coords.csv의 Fishing 엔트리) |
| `sulfur_placements.csv` | 42 | 유황 |
| `mercury_placements.csv` | 107 | 수은 |
| `lumber_placements.csv` | 73 | 벌목 |
| `rubber_placements.csv` | 5 | 고무 |
| `herb_kudzu.csv` | 387 | 칡 (환경 장애물) |
| `herb_*.csv` (나머지) | 0 | 추출 결과 없음 (palevel에서 매칭 안 됨) |
| `crop_placements.csv` | 0 | 추출 결과 없음 |

### 3.4 거점 타입 분류 기준 (`factionnode_translated.csv`)

| type | 설명 | 예시 |
|---|---|---|
| village | 마을 | ArboriaVillage → 아보리아 마을 |
| castle | 성 | HernandCastle → 에르난드 성 |
| fort | 요새 | FortHellwood → 헬우드 요새 |
| camp | 캠프/야영지 | GreymaneCamp → 회색갈기 캠프 |
| rest_area | 휴식 구역 | RestArea_0005 |
| cave | 동굴 | Region_Cave_0020 |
| ruins | 유적/폐허 | RockshardValleyRuins |
| tower | 망루/탑 | DrakefallWatchtower |
| gate | 성문/관문 | HernandEastGate → 에르난드 동문 |
| beacon | 봉화대 | BellanorBeacon → 벨라노르 봉화대 |
| farm | 농장 | RustleleafFarm |
| ranch | 목장 | SaddlewindRanch → 새들윈드 말목장 |
| trade | 교역소 | GoldleafTradepost |
| market | 시장 | JoyfairMarketplace |
| harbor | 항구/부두 | PortDelesyia |
| shrine | 사원/성당 | CalphadeChurch |
| outpost | 전초기지 | WindcrestOutpost → 윈드크레스트 전초기지 |
| mine | 광산 | WolfFang_Mine |
| workshop | 공방/공장 | ArboriaCraftshop → 아보리아 공방 |
| manor | 영지/저택 | AzerianManor |
| abyss_node | 심연 노드 | Abyssone_0001 |
| monster_lair | 몬스터 소굴 | HyenaDen |
| landmark | 지형 랜드마크 | Ashen_Crevasse |
| tomb | 무덤 | TombOfPeace |
| military | 군사시설 | CalphadeArtilery |
| shipwreck | 난파선 | Shipwreck_0001 |
| poi | 일반 관심지점 | Tashkalp, Varnia |

### 3.5 광물 타입 분류 기준 (`mine_placements_clean.csv`)

| resource_type | 한국어 | 개수 |
|---|---|---|
| iron | 철광석 | 1,329 |
| silver | 은광석 | 1,050 |
| ruby | 루비 | 1,007 |
| gold | 금광석 | 847 |
| copper | 구리광석 | 591 |
| bismuth | 비스무트 | 417 |
| whitestone | 백석 | 266 |
| greenstone | 녹석 | 173 |
| stone | 돌 | 80 |
| bluestone | 청석 (Azurite) | 72 |
| diamond | 다이아몬드 | 71 |
| redstone | 적석 | 29 |
| sulfur | 유황 | 1 |

### 3.6 채집물 타입 분류 기준 (`gathering_placements.csv`)

| category | subtype | 한국어 | 개수 |
|---|---|---|---|
| mushroom | shiitake | 표고버섯 | 224 |
| mushroom | matsutake | 송이버섯 | 46 |
| mushroom | hericium | 노루궁뎅이 | 2 |
| fruit | apple | 사과 | 27 |
| fruit | peach | 복숭아 | 26 |
| fruit | opuntia | 선인장 열매 | 16 |
| fruit | orange | 오렌지 | 6 |
| abyss_item | spiderweb | 거미줄 | 22 |
| unique | seockcheong | 석청 | 2 |
| unique | unique_002 | 특수 채집물 | 1 |
| vegetable | carrot | 당근 | 2 |
