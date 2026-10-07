# field-scars

[English](README.md)

운영 시스템에서 실제로 데인 사고들을 에이전트 스킬로 정리했습니다. 공통점은 **실수한 순간에는 아무 오류도
나지 않는다**는 것입니다. 나중에 남의 diff, 남의 빌드, 남의 보고서에서 터집니다. 스킬마다 표준 라이브러리만 쓰는 작은
스크립트가 딸려 있어서, 교훈을 "빨간불이 들어오는 점검"으로 바꿔 줍니다.

| 플러그인 | 잡는 것 |
|---|---|
| **windows-repo-hygiene** | 줄바꿈이 뒤집혀 파일 전체가 diff 가 되는 것, 아무것도 안 바꾸고 "성공"한 스크립트 치환, 한글 `.ps1` 을 PowerShell 5.1 이 잘못 읽는 것, JSON·셸·nginx 를 깨뜨리는 BOM, 로컬에선 되고 CI 에서 깨지는 대소문자 |
| **silent-wrong-answer** | 그럴듯하지만 틀린 결과: 진짜 값 대신 기본값이 쓰임, 조인 뒤 이중 집계, 저장만 되고 아무도 안 읽는 설정, 옛 코드를 서빙하는 프로세스, 대량 적재 중 손실. 오라클 대조 도구와 함정 12종 목록 포함 |

## 설치 (Claude Code)

```
claude plugin marketplace add lani319/field-scars
claude plugin install windows-repo-hygiene@field-scars
claude plugin install silent-wrong-answer@field-scars
```

세션 안에서는 `/plugin marketplace add lani319/field-scars` 후 `/plugin`.

상황이 맞으면 스킬이 알아서 켜집니다("한 줄 고쳤는데 diff 가 파일 전체", "숫자가 이상해", "멀쩡한 줄에서
PowerShell 파싱 오류"...). 이름으로 불러도 됩니다: "이 합계에 silent-wrong-answer 적용해줘".

## Codex 등 다른 에이전트에서

저장소를 받아 `AGENTS.md` 에 스킬 파일 경로를 적습니다.

```
줄바꿈·BOM·인코딩·대소문자 문제는 plugins/windows-repo-hygiene/skills/windows-repo-hygiene/SKILL.md 를 따른다.
오류 없이 결과가 이상하면 plugins/silent-wrong-answer/skills/silent-wrong-answer/SKILL.md 를 따른다.
```

## 스크립트만 쓰기

Python 3.9+ 와 git 만 있으면 됩니다. 문제가 있으면 0 이 아닌 코드로 끝나서 pre-commit 훅·CI 에 그대로 넣을 수 있습니다.

```
python plugins/windows-repo-hygiene/skills/windows-repo-hygiene/scripts/eol_check.py --scan   # 이 저장소 위험한가?
python .../eol_check.py --staged          # 커밋 전: 줄바꿈이 뒤집힌 파일이 있나?
python .../encoding_check.py              # 추적 파일의 BOM·인코딩 문제
python .../case_check.py                  # 대소문자 충돌, 디스크 불일치, 잘못된 import 대소문자
python .../safe_replace.py edits.json     # 줄바꿈·BOM 을 지키는 전부-아니면-전무 치환

python plugins/silent-wrong-answer/skills/silent-wrong-answer/scripts/reconcile.py diff suspect.csv oracle.csv --key id
python .../reconcile.py grain detail.csv --group order_id   # 부모 값이 자식 행마다 반복되는 열
```

이 교훈이 나온 3,600개 파일 저장소에 처음 돌렸을 때: `eol_check --scan` 은 git 이 정규화하지 않는 LF 2,798개·CRLF
294개를 잡았고(`.gitattributes` 가 LFS 설정뿐이었음), `encoding_check` 는 주석에 한글이 있고 BOM 이 없는 배포
스크립트를 찾았습니다. 지금은 무해하지만, 누군가 문자열에 한글을 넣는 날 깨집니다.

## 개발

```
python -m venv .venv && .venv/Scripts/pip install -r requirements-dev.txt   # 또는 .venv/bin/pip
python tools/gate.py        # ruff + pytest (+ 설정 시 클린룸 점검)
```

## 라이선스

MIT
