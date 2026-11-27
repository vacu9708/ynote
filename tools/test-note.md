# Ynote 표 테스트
일반 문단에 **굵게**와 `inline code`를 섞었습니다.
`줄을 넘어가는 inline code: ynote --open-note "테스트" --with-a-long-option-name --and-another-one-to-wrap --past-the-right-edge-of-a-wide-note --so-that-it-goes-on-below`
`hi`
`hello`

# Bold를 켠 heading: **더 굵게 Bolder**

# 목록
- 첫 항목
- 두 번째 항목
  - 들여쓴 항목
    - 더 들여쓴 항목
- [ ] 안 한 일
- [x] 한 일

# 인용
> 인용 첫 줄
> 인용 둘째 줄에 **굵게**

# 코드 블록
```
def hello():
    print("hi")
```

---
# 표

| 이름 | 설명 | 상태 |
| --- | --- | --- |
| **굵은 이름** | 첫 줄<br>둘째 줄<br>셋째 줄 | `done` |
| 파이프 | a \| b 처럼 이스케이프한 파이프 | `x \| y` |
| 긴 셀 | 이 셀은 일부러 길게 써서 열 너비가 노트 폭에 맞게 줄어들고 줄바꿈되는지 확인하려는 문장입니다. | 빈칸 옆 |
| 빈 셀 |  | 끝 |

<details open>
<summary>펼친 expand 안의 표</summary>

| 키 | 값 |
| --- | --- |
| Tab | 다음 셀 |
| Esc | 표 밖으로 |

</details>

<details>
<summary>접힌 expand: 검색어 바나나</summary>

접힌 상태로 붙여넣어진 내용입니다. 검색에서 **바나나**를 찾으면 열려야 합니다.

| 과일 | 색 |
| --- | --- |
| 바나나 | 노랑 |

</details>

마지막 줄: 표 아래 텍스트가 제자리에 그려지는지 봅니다.
