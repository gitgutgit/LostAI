# 제품 이름 짓기 이론 조사 (2026-11-09)

목적: 오늘 해커톤 팀이 제품 이름과 로고를 고를 때 쓸 이론 근거와 채점표. 최종 이름은 제안하지 않는다.

열람 표기 규칙: 각 출처 뒤에 [원문 열람], [초록 열람], [2차 자료만 열람] 중 하나를 붙였다. [2차 자료만 열람]은 원 논문을 열지 못하고 다른 글의 요약만 읽었다는 뜻이라 수치와 결론을 그대로 믿지 말고 방향만 참고한다. 표시 없는 판단은 이 문서의 분석이다.

---

## 1. 결론

- **영상에서 한 번 듣고 철자로 옮길 수 있어야 한다.** 심사위원은 이름을 약 2분 영상에서 한 번 듣는다. 발음이 쉬운 이름이 다른 정보가 적은 첫 만남 구간에서 더 좋게 평가된다는 근거(Alter & Oppenheimer 2006)와, 소리 나는 대로 쓰이지 않는 이름이 라디오 테스트에 실패한다는 실무 기준이 함께 이 점을 가리킨다. 모음 생략(Snapd 류), 특이 철자, 발음 불가능한 약어(tl;dv 류)는 감점 1순위다.
- **실단어를 다른 맥락에 가져온 암시형(suggestive) 또는 임의형(arbitrary)이 해커톤 조건에 가장 맞는다.** 기술형(descriptive, 예: 회의 메모를 그대로 말하는 이름)은 곧바로 이해되지만 카테고리 안에 묻히고 상표 보호도 약하다. 완전 조어(fanciful)는 가장 강하지만 뜻을 쌓을 시간이 없는 2분 영상에서는 기억 장치가 약하다. Abercrombie 판결의 기준대로 듣는 사람이 조금의 상상으로 제품 성격에 닿는 지점이 목표다.
- **경쟁 이름 지형은 짧은 실단어, 동물이나 음식 같은 친근한 명사, .ai 접미사, 회의가 끝난 뒤를 가리키는 의미장(되돌아보기, 읽기, 요약)으로 몰려 있다.** 우리 제품의 차이는 회의 중에 문서를 쓰고, 멈추고, 방이 결정하게 한다는 점이다. 이름이 듣기 좋은 귀여운 명사 + .ai 패턴이나 사후 요약 의미장에 들어가면 차이가 사라진다.
- **이름이 AI가 판정한다는 인상을 주면 제품 원칙과 정면으로 충돌한다.** 소비자는 이름의 소리와 뜻에서 제품 속성을 자동으로, 의식 밖에서 추론한다(Yorkston & Menon 2004). 판사, 심판, 신탁, 결론을 연상시키는 이름은 AI는 선택지를 추천하지 않는다는 핵심 메시지를 영상 시작 전부터 깎는다. 이 항목은 채점표에서 별도로 본다.
- **소리 상징은 실재하지만 이름의 뜻이 분명할수록 약해지고, 인지 부하가 클 때는 그대로 작동한다.** 짧은 영상을 보는 심사위원은 부하가 큰 쪽이다. 날카로운 자음과 앞모음(k, t, i)은 빠르고 단단하고 작게, 둥근 자음과 뒷모음(b, m, o, u)은 부드럽고 크게 들린다(bouba/kiki, Klink 2000, Yorkston & Menon 2004). 멈추고 결정하게 하는 제품은 단단한 소리가 맞지만 권위적으로 들리지 않게 균형을 본다.
- **.com 확보는 해커톤 당일에는 결정 기준이 아니라 동명 앱 충돌 확인으로 대체한다.** Paul Graham(2015)은 이름의 .com이 없으면 약함의 신호라고 했고, Lexicon의 Placek는 .com이 이제 지역번호 수준이라고 반대로 말한다. 오늘 확인할 것은 같은 이름의 회의 앱이나 AI 도구가 이미 있는지다.
- **로고는 설명이 아니라 식별 표시다.** 단색으로, 아주 작은 크기에서도 재현되어야 하고(Paul Rand 1991), 형상 수를 최소로 하고 가는 선과 날카로운 모서리를 피해야 작은 크기에서 살아남는다(Apple HIG). 이름의 첫 글자나 단일 형상 하나로 16px 파비콘에서 읽히는지가 이름 후보의 실질 제약이 된다.

---

## 2. 이론 정리

### 2.1 이름 유형과 식별력 스펙트럼

- **법원의 4단계 스펙트럼.** Judge Friendly는 상표 보호 적격성 순으로 "(1) generic, (2) descriptive, (3) suggestive, and (4) arbitrary or fanciful"을 나열하고 "The lines of demarcation, however, are not always bright"라고 덧붙였다.
  - 출처: Abercrombie & Fitch Co. v. Hunting World, Inc., 537 F.2d 4 (2d Cir. 1976), Harvard 강의용 축약본 PDF, https://cyber.harvard.edu/people/tfisher/IP/1976_Abercrombie_Abridged.pdf [원문 열람, 축약본]
- **기술형과 암시형의 구분 기준.** 판결이 인용한 기준: "A term is suggestive if it requires imagination, thought and perception to reach a conclusion as to the nature of goods. A term is descriptive if it forthwith conveys an immediate idea of the ingredients, qualities or characteristics of the goods." (Stix Products v. United Merchants 1968을 판결이 인용)
  - 같은 출처 [원문 열람, 축약본]
- **유형별 득실(판결 내용).** 일반명(generic)은 2차적 의미를 입증해도 보호되지 않는다. 기술형은 2차적 의미를 입증해야 등록된다. 암시형은 입증 없이 등록된다. 임의형과 조어형은 암시형의 권리를 모두 가지며 판결은 조어형을 "words invented solely for their use as trademarks", 기존 단어를 낯선 방식으로 쓰는 것을 "arbitrary"라고 설명한다. 같은 단어도 상품에 따라 범주가 바뀐다(Safari는 사냥 의류에는 일반명, 다른 상품에는 다를 수 있음). 출처 같음 [원문 열람, 축약본]
  - 이 문서의 해석: 기술형은 즉시 이해(이득) 대신 차별성과 보호(손실)를 잃는다. 조어형은 차별성과 보호(이득) 대신 뜻을 처음부터 가르쳐야 한다(손실). 암시형과 임의형이 그 사이다.
- **Igor의 실무 분류: Functional, Invented, Experiential, Evocative.** Functional은 "The lowest common denominator of names"이며 기술형에 해당한다(Infoseek, LookSmart). Invented는 조어(Agilent, Google). Experiential은 실제 경험과 직접 연결된 다소 문자적인 이름(Netscape, Palm Pilot). Evocative는 상품이 아니라 포지셔닝을 불러내는 이름(Virgin, Apple). 가장 낮은 단계는 "least engaging, and likely to be quickly forgotten"으로 평가된다.
  - 출처: Igor International, Naming Company Names Taxonomy, https://igorinternational.com/process/naming-company-names-taxonomy.php [원문 열람]
- **Evocative의 득실(Igor).** 이득: 드물어서 차별화되고 상품보다 "bigger than the goods and services a company offers" 브랜드를 만든다. 비용: 포지셔닝과 맞지 않으면 실패하고 "the toughest type of names to get corporate approval for"이다.
  - 출처: Igor International, Evocative Product and Corporate Names, https://igorinternational.com/process/evocative-product-company-names.php [원문 열람]
  - Igor는 경쟁 이름들을 이 4분류 위에 점수(-2에서 +5)로 배치해 빈자리를 찾는 도구를 쓴다고 검색 결과에 나오지만 그 표 자체는 열지 않았다 [2차 자료만 열람].
- **Lexicon(David Placek)의 실무 원칙.** 좋은 이름은 처음에 팀을 불편하게 한다(Sonos, Azure, BlackBerry가 처음 거절되거나 비웃음을 받음). 반응이 갈리는 것이 에너지의 신호다(Andy Grove의 Pentium 일화). 합성어(PowerBook, BlackBerry, Windsurf)는 "1 + 1 = 3"의 연상을 만든다. 이름 평가는 이 이름 어떠냐가 아니라 경쟁사가 방금 이 이름으로 출시했다면 어떤 반응이냐로 묻는다(competitor test). 독특한 단어는 말해지고 입력되고 검색될 때마다 "cumulative advantage"를 준다.
  - 출처: Lenny's Newsletter, Naming expert David Placek, https://www.lennysnewsletter.com/p/naming-expert-david-placek [원문 열람, 팟캐스트 요약 글이라 대부분 요약자 문장이며 직접 인용은 일부]
  - 같은 글의 글자별 심리 효과 주장(v는 활기, b는 신뢰, z는 주목, x는 혁신)은 "scientifically proven"이라고 쓰였지만 근거 논문이 제시되지 않았다. 참고만 한다.
- Interbrand 분류는 이번 조사에서 열지 않았다.

### 2.2 인지 근거: 소리 상징, 처리 유창성, 기억

- **소리 상징은 자동으로 작동한다.** 소비자는 브랜드 이름의 음소에서 제품 속성을 추론하고 브랜드를 평가하며, 이 과정은 "uncontrollable, outside awareness and effortless", 즉 자동적이다.
  - 출처: Yorkston, E. & Menon, G. (2004). A Sound Idea: Phonetic Effects of Brand Names on Consumer Judgments. Journal of Consumer Research 31(1), 43-51. https://web.stanford.edu/class/linguist62n/yorkston.pdf [원문 열람, 초록과 연구 설계 부분]
- **Frosh와 Frish 실험.** 저자들은 뒷모음 [ä]의 Frosh가 앞모음 [i]의 Frish보다 "smoother, creamier, and richer" 아이스크림을 전달할 것으로 예측했고, 속성 지각 지수에서 이름의 주효과가 유의했다(F(1, 117) = 9.51, p < .01).
- **조절 변수(진단성).** 이름이 진짜 출시명(진단적)이라고 들으면 효과가 나타나고, 시험용 이름(비진단적)이라고 들으면 사람들이 소리 효과를 걸러내려 한다. 다만 진단성 정보를 늦게 받거나 인지 자원이 부족하면 효과가 그대로 나타난다. 출처 같음 [원문 열람]
  - 이 문서의 해석: 영상을 한 번 보는 심사위원은 부하가 큰 상황이라 이름의 소리가 걸러지지 않고 인상에 들어간다고 보는 편이 안전하다.
  - 한계: FORRT replication atlas에 이 연구의 재현 1건이 부분 재현으로 기록되어 있다는 검색 결과가 있다 [2차 자료만 열람].
- **Klink(2000): 모음과 자음의 소리 상징.** 앞모음(i, e) 이름은 뒷모음(o, u) 이름보다 작고, 가볍고, 얇게 지각되며 자음에서도 유사한 연관이 있다고 후속 문헌들이 요약한다.
  - 출처: Klink, R. R. (2000). Creating Brand Names With Meaning: The Use of Sound Symbolism. Marketing Letters 11(1), 5-20. DOI 10.1023/A:1008184423824 [2차 자료만 열람: Springer 원문과 초록 페이지는 접근 차단, Yorkston & Menon 2004 본문과 검색 결과 요약에서 내용 확인]
- **bouba/kiki.** Ramachandran & Hubbard(2001)는 95%의 사람이 둥근 도형을 bouba, 뾰족한 도형을 kiki로 고른다고 보고했다. Ćwiek 등(2022)은 25개 언어 화자 917명에게서 우연보다 높은 일치를 확인했으나 일부 언어(중국어 표준어, 터키어, 루마니아어, 알바니아어)에서는 50% 미만이었다.
  - 출처: Wikipedia, Bouba/kiki effect, https://en.wikipedia.org/wiki/Bouba/kiki_effect [2차 자료만 열람: 원 논문 Ramachandran & Hubbard 2001, Journal of Consciousness Studies 8(12), 3-34와 Ćwiek et al. 2022는 열지 않음]
  - 심사위원이 영어 화자이므로 효과가 확인된 언어권에 해당한다.
- **처리 유창성과 발음 용이성.** 사람들은 쉽게 처리되는 정보를 선호한다. 발음하기 쉬운 이름과 티커의 주식이 상장 직후 단기에 더 좋은 성과를 냈고(실험실 연구와 1990~2004 NYSE, AMEX 실제 데이터), 한 연구에서 1000달러 투자 기준 하루 뒤 112달러 차이가 났다. 티커 BAL이 BDL보다 첫 며칠 앞선다는 예가 제시되었다. 효과는 상장 직후, 즉 다른 정보가 적을 때 가장 강했고, 저자는 장기 성과의 지표가 아니라고 경고했다.
  - 출처: Alter, A. L. & Oppenheimer, D. M. (2006). Predicting short-term stock fluctuations by using processing fluency. PNAS 103(24), 9369-9372. 보도자료 EurekAlert, https://www.eurekalert.org/news-releases/735602 [초록과 보도자료 열람, 논문 본문은 미열람]
  - 이 문서의 해석: 심사위원이 우리 이름을 처음 듣는 순간은 정보가 가장 적은 구간이라 유창성 효과가 가장 클 때다.
- **기억에 남는 이름의 언어적 특성.** 480개 전국 브랜드의 23개 언어 특성을 분석한 연구로, 특이 철자, 의미 적합성(semantic appositeness), 첫소리 파열음(initial plosives, p, b, t, d, k, g), 말장난(paronomasia)이 기억과 관련되었고 그 관련은 덜 알려진 브랜드에서 더 강했다. 두 단어를 녹여 붙인 blending은 기억에 부정적이었다.
  - 출처: Lowrey, T. M., Shrum, L. J. & Dubitsky, T. M. (2003). The Relation between Brand-Name Linguistic Characteristics and Brand-Name Memory. Journal of Advertising 32(3), 7-17. DOI 10.1080/00913367.2003.10639137 [2차 자료만 열람: 블로그 요약 https://acscribbler.blogspot.com/2015/05/the-role-of-linguistic-components-of.html 과 검색 결과 요약. 요약들 사이에 어떤 변수가 유의했는지 서술이 엇갈림]
  - 주의: 특이 철자가 기억에 유리하다는 결과는 2.3의 라디오 테스트(들은 대로 쓸 수 있어야 함)와 충돌한다. 영상 한 번 노출이라는 우리 조건에서는 듣고 검색할 수 있어야 하므로 라디오 테스트를 우선한다. 또 blending의 부정 효과는 Placek의 합성어 선호와 엇갈리는데, 두 단어가 각각 온전히 들리는 합성어(BlackBerry)와 단어 일부를 잘라 녹인 혼성어는 다르게 보는 것이 합리적이다(이 문서의 해석).
- **라디오 테스트.** 이름을 한 번 들은 사람이 철자를 맞혀 찾을 수 있는지를 보는 실무 기준. Name Ninja가 Collision 컨퍼런스 참가 스타트업 도메인을 분석해 68%가 소리 나는 대로 쓰이지 않아 라디오 테스트에 실패한다고 했고, 예로 CloudKeyz, Dooing, Snapd, Atmospheir를 들었다.
  - 출처: Domain Name Wire (2015-04-28). Startup domain name fails: 68% fail radio test. https://domainnamewire.com/2015/04/28/startup-domain-name-fails-68-fail-radio-test/ [원문 열람, 업계 매체 기사이며 학술 근거 아님]

### 2.3 스타트업 실무

- **Paul Graham, Change Your Name (2015-08).** 이름의 .com이 없으면 "signals weakness"이고, 상위 20개 YC 기업 100%가 이름의 .com을 가졌지만 당시 배치는 66%만 가졌다. 이름 자체에 대해서는 "almost any word or word pair that is not an obviously bad name is a sufficiently good one"이라고 하여 이름의 우열보다 확보 가능성을 더 중시한다. 현재 이름에 대한 애착은 대체로 비합리적이라고 본다.
  - 출처: Graham, P. (2015). Change Your Name. https://www.paulgraham.com/name.html [원문 열람]
- **반대 의견(Placek).** .com은 "just an area code"이며 맞는 이름을 먼저 고르고 도메인은 접두어, .ai, 구매로 해결하라. 출처: 2.1의 Lenny's Newsletter [원문 열람]
- **YC 공식 이름 지침.** YC 공식 문서에서 라디오 테스트나 이름 기준을 정한 1차 자료는 이번 검색에서 찾지 못했다. YC 관련 근거는 위 Paul Graham 에세이로 한정한다.
- **흔한 함정(근거별 정리).**
  - 모음 생략, 특이 철자: 라디오 테스트 실패(Domain Name Wire 2015, Snapd 등).
  - 기술형 이름: 법적으로 약하고(Abercrombie) 실무적으로 가장 낮은 단계(Igor의 Functional).
  - -ly, -ify 같은 관용 접미사: 이번에 이를 직접 다룬 1차 자료는 열지 않았다. 다만 Igor가 Functional 예로 기능 접두사와 접미사 이름을 들고 있어 같은 범주로 본다.
  - 기존 앱과의 충돌: 이번 조사에서 이를 정량화한 자료는 열지 않았다. 상표 스펙트럼에서 같은 단어도 상품군이 다르면 범주가 바뀐다는 판결 원리상, 회의 소프트웨어 안에서의 동명 충돌이 핵심이다.
- **빠른 이름 시험법(근거 있는 것만).**
  - 경쟁사 테스트: 경쟁사가 방금 이 이름으로 출시했다면 반응이 어떤지 묻는다(Placek).
  - 라디오 테스트: 영상 속 발표 문장 그대로 한 번 들려주고 철자를 받아 적게 한다(Domain Name Wire 2015 기준을 이 팀 조건에 맞춘 적용).
  - 진단성 조건: 시험용 이름이라고 알려 주면 소리 효과가 걸러지므로, 실제 출시 이름이라고 소개하고 반응을 받는다(Yorkston & Menon 2004의 조절 효과를 시험 설계에 적용한 해석).

### 2.4 로고 이론

- **로고는 식별하지 설명하지 않는다.** "A logo doesn't sell (directly), it identifies." "A logo is rarely a description of a business." 의미는 연상에서 온다: "It is only by association with a product, a service, a business, or a corporation that a logo takes on any real meaning." 로고는 "reproducible in one color and in exceedingly small sizes"여야 한다. "Simplicity is difficult to achieve, yet worth the effort."
  - 출처: Rand, P. (1991). Logos, Flags, and Escutcheons. AIGA. https://paulrand.design/writing/articles/1991-logos-flags-and-escutcheons.html [원문 열람]
- **아이콘은 최소 형상, 단순 배경, 작은 크기에서 살아남는 형태.** "Embrace simplicity in your icon design." 핵심 개념 하나를 "a minimal number of shapes"로 표현하고, 세밀한 요소는 "may be hard to discern at smaller sizes". "avoid extremely thin line weights and sharp corners, because they tend to lose detail and crispness in smaller icon sizes". 텍스트는 필수일 때만 넣되 "a mnemonic like the first letter of your app's name can help people recognize your app". 다크, 틴트 등 외형이 바뀌어도 핵심 형상을 유지하라.
  - 출처: Apple, Human Interface Guidelines: App icons (변경 이력 2026-10-28), https://developer.apple.com/design/human-interface-guidelines/app-icons [원문 열람]
- **픽토그램, 워드마크, 레터마크.** 이 3분류 자체를 정의한 1차 자료는 이번에 열지 않았다. 위 두 출처에서 끌어낼 수 있는 실용 결론만 적는다(이 문서의 해석).
  - 워드마크(이름 글자 전체): 영상과 슬라이드에서 이름 기억을 직접 돕지만 16px에서는 읽히지 않는다.
  - 레터마크(첫 글자): Apple이 허용하는 첫 글자 기억 장치에 해당하며 파비콘 크기에서 가장 안전하다.
  - 픽토그램(형상 하나): Rand 기준으로 의미는 형상이 아니라 제품과의 연상에서 오므로, 2분 영상에서는 형상만으로 의미를 전달하기 어렵다. 이름과 함께 노출될 때만 효과가 있다.
  - 16px 파비콘에 대한 별도 규격 문서는 열지 않았다. 위 Apple의 작은 크기 원칙과 Rand의 단색, 극소 크기 재현 기준을 16px에 적용하는 것은 이 문서의 추론이다.

---

## 3. 경쟁 이름 지형

유형 분류와 연상은 이 문서의 분석이다(각 회사의 작명 의도 자료는 열지 않음). 유형은 2.1의 법원 스펙트럼 기준, 괄호 안은 Igor 분류.

| 이름 | 유형 | 연상되는 것 |
|---|---|---|
| Circleback | 암시형 (Experiential) | 업무 관용구 circle back, 나중에 다시 다루자. 회의 뒤 후속 조치 |
| Granola | 임의형 (Evocative) | 아침 식사, 가볍고 편안함. 회의와 직접 연결 없음 |
| Otter (Otter.ai) | 임의형 + .ai (Evocative) | 귀여운 동물, 친근함 |
| Fireflies (Fireflies.ai) | 임의형 + .ai (Evocative) | 작은 빛, 조용히 떠다니는 존재 |
| Fathom | 암시형 (Evocative) | 깊이를 재다, 헤아리다. 이해와 통찰 |
| tl;dv | 약어, 기술형에 가까운 말장난 (Functional) | tl;dr 밈 변형, 너무 길어서 안 봤다. 회의를 안 봐도 된다. 소리로 전달이 어려움 |
| Read.ai | 기술형과 암시형 경계 + .ai (Functional) | 읽다, 회의를 읽어 준다. read의 현재와 과거 발음이 갈려 들을 때 모호함 |
| Fellow | 임의형에 가까운 암시형 (Experiential) | 동료, 함께하는 사람 |
| Avoma | 조어형 (Invented) | 특정 뜻 없음, 부드러운 모음 소리 |

지형 요약(이 문서의 분석):
- 9개 중 7개가 사전에 있는 영어 실단어나 관용구이고 1~3음절이다. 조어는 Avoma 하나다.
- 동물, 음식, 자연 명사(Otter, Fireflies, Granola)와 .ai 접미사가 반복된다. 이 패턴에 하나 더 얹으면 묻힌다.
- 의미장은 듣기와 사후 처리(circle back, tl;dv, read, fathom)에 몰려 있다. 회의 중에 쓰고, 멈추고, 방이 결정하게 한다는 능동적 개입 의미장은 비어 있다.
- 소리는 대체로 부드럽고 둥근 쪽(Otter, Fellow, Avoma, Granola)이다. 조용한 조력자 이미지다.

---

## 4. 채점표

각 항목 0~2점, 합계 16점. 0은 실패, 1은 애매, 2는 충족.

| 번호 | 기준 | 2점 조건 | 근거 (2절) |
|---|---|---|---|
| 1 | 한 번 듣고 쓰기 | 영상 속 문장으로 한 번 들은 영어 화자가 철자를 맞히고, 철자를 보고 한 가지로만 읽는다 | 라디오 테스트(Domain Name Wire 2015), 처리 유창성(Alter & Oppenheimer 2006) |
| 2 | 짧고 기억 장치가 있음 | 1~2음절 또는 온전한 두 단어 합성, 첫소리 파열음이나 두운 같은 장치가 있고 단어 일부를 잘라 녹인 혼성어가 아니다 | Lowrey 외 2003 [2차 자료], Placek 합성어 원칙 |
| 3 | 식별력 위치 | 암시형 또는 임의형. 기술형(회의 메모, 요약을 그대로 말함)은 0점, 뜻 없는 조어는 1점 | Abercrombie 1976, Igor 분류 |
| 4 | 경쟁 지형과의 거리 | 3절의 패턴(귀여운 명사 + .ai, 사후 요약 의미장)에서 벗어나고, 경쟁사가 이 이름으로 출시했다고 가정해도 우리 것으로 들린다 | Igor 경쟁 배치 방식, Placek competitor test |
| 5 | 소리와 제품 성격의 정합 | 소리가 원하는 속성(명확함, 단단함, 그러나 위압적이지 않음)과 맞는다 | Yorkston & Menon 2004, Klink 2000 [2차 자료], bouba/kiki [2차 자료] |
| 6 | AI가 결정한다는 함의 없음 (제품 고유) | 이름의 뜻과 소리가 판사, 심판, 신탁, 결론, 자동 결정을 떠올리지 않고, 사람과 방이 결정하거나 AI가 멈추고 묻는 쪽을 떠올린다 | 이름에서 속성을 자동 추론한다는 Yorkston & Menon 2004, 이름이 성격을 암시한다는 Abercrombie 1976 암시형 기준 |
| 7 | 충돌과 확보 | 회의, 협업, AI 소프트웨어 안에 같은 이름의 제품이 없고, 이름의 .com 또는 이름 그대로의 대안 도메인이 가능하다 | Paul Graham 2015, Placek(도메인은 나중에 해결 가능) |
| 8 | 로고화 가능성 | 첫 글자나 단일 형상 하나로 단색, 16px에서 구분되는 표시를 만들 수 있다 | Rand 1991, Apple HIG App icons |

사용법 메모:
- 6번이 0점이면 합계와 관계없이 탈락으로 다루기를 권한다. 제품 원칙과 정면으로 충돌하기 때문이다.
- 1번은 팀원이 아닌 영어 화자에게 실제로 들려줘서 채점한다. 팀 안의 판단으로 채점하지 않는다.
- 5번은 팀 의견이 갈리기 쉽다. Placek에 따르면 반응이 갈리는 것 자체는 감점 사유가 아니다.

---

## 5. 이 제품에 주는 함의

최종 이름은 제안하지 않는다. 아래 예시 단어는 방향을 보여 주기 위한 것이며 충돌 확인과 채점을 거치지 않았다. 순위가 아니다.

**맞는 방향**
- 방이 결정한다는 의미장: 손, 거수, 방, 정족수, 바닥(the floor) 같은 회의 절차와 사람 쪽 단어. 예시 방향: show of hands, floor, quorum 계열. 우리 제품의 가장 독특한 순간(동시 손 투표)을 이름이 가리킨다. 단 quorum처럼 뜻이 어긋나는 단어는 6번이 아니라 의미 적합성에서 확인이 필요하다.
- 멈추고 묻는 의미장: 멈춤, 질문, 손을 든다 같은 동작. 예시 방향: pause, hold, raise 계열. 피치 문장의 후반부(it stops writing and makes the room decide)와 이어진다.
- 말이 문서가 되는 의미장: 셀, 장부, 기록, 펜 같은 실물. 예시 방향: ledger, cell, pen 계열. 경쟁사의 사후 요약과 달리 회의 중 문서를 쓴다는 점을 암시한다. 다만 이 방향만으로는 충돌 시 멈춘다는 차별점이 빠지므로 1번과 4번에서 다른 방향보다 불리할 수 있다.
- 출처와 되돌림 의미장: 누가 말했는지 흔적, 영수증, 되감기. 신뢰라는 이차 메시지를 준다.
- 형식 면에서는 온전한 실단어 하나 또는 두 실단어 합성이 해커톤 조건(한 번 노출, 영어 화자 심사)에 가장 맞는다. 조어는 2분 안에 뜻을 가르칠 여유가 없다.

**피할 방향**
- AI 판정 의미장: judge, verdict, arbiter, oracle, referee, umpire, decide, resolve 계열. 6번에서 0점이다. gavel처럼 의장 권한을 연상시키는 단어도 AI가 그 권한을 쥔 것으로 들릴 수 있어 위험하다.
- 사후 요약 의미장: recap, notes, summary, minutes, digest, read. 경쟁사 9곳과 같은 줄에 선다.
- 귀여운 동물, 음식 명사 + .ai: Otter, Fireflies, Granola와 같은 패턴이라 4번에서 낮다.
- 모음 생략과 특이 철자(-r 끝맺음, z 대체), 발음 불가능한 약어: 1번에서 0점이다.
- 기능 접미사(-ly, -ify, -bot)와 Meeting, Doc, Sync 같은 기술형 조합: 3번에서 0점이다.

**팀 조건에서 추가로 볼 점(이 문서의 추론, 출처 없음)**
- 영상 내레이션을 한국어 모국어 화자가 영어로 할 가능성이 있다면 r과 l, f와 p, v와 b, th 구분에 기대는 이름은 1번 점수가 실제 녹음에서 떨어질 수 있다. 후보를 팀원 목소리로 녹음해 영어 화자에게 들려주는 것이 가장 빠른 판단 밖 검증이다.
- 로고는 이름이 정해진 뒤 레터마크(첫 글자) 하나를 먼저 만들고 16px로 줄여 브라우저 탭에서 확인하는 순서가 위험이 가장 적다. 픽토그램은 영상에서 이름과 함께 나올 때만 의미가 붙는다(Rand 1991).
