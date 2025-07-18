import streamlit as st
import pandas as pd
import dart_fss

# ✅ DART API Key 세팅
dart_api_key = '9dcbac88962a5d39c070e1f18bbd2e400c799163'
dart_fss.set_api_key(dart_api_key)

@st.cache_data
def load_corp_list():
    corp_list = dart_fss.api.filings.get_corp_code()
    return pd.DataFrame(corp_list)

df_corp_list = load_corp_list()

def get_corp_code(company_name):
    result = df_corp_list[df_corp_list['corp_name'] == company_name]
    return result['corp_code'].values[0] if not result.empty else None

@st.cache_data
def get_financial_data(corp_code, year, reprt_code='11011', fs_div='OFS'):
    data = dart_fss.api.finance.fnltt_singl_acnt_all(
        corp_code, bsns_year=year, reprt_code=reprt_code, fs_div=fs_div
    )
    df = pd.DataFrame(data['list'])
    df = df[['sj_nm', 'account_nm', 'thstrm_amount', 'frmtrm_amount']]
    df.rename(columns={'thstrm_amount': f'{year}', 'frmtrm_amount': f'{int(year)-1}'}, inplace=True)
    return df

def get_value(df, name, year):
    val = df[df['account_nm'] == name][year]
    return val.values[0] if not val.empty else None

def get_value_contains(df, keyword, year):
    val = df[df['account_nm'].str.contains(keyword, na=False)][year]
    return val.values[0] if not val.empty else None

def process_company(company_name, year='2024', fs_div='OFS'):
    corp_code = get_corp_code(company_name)
    if corp_code is None:
        st.warning(f"[경고] {company_name}의 corp_code를 찾을 수 없습니다.")
        return pd.DataFrame()

    df = get_financial_data(corp_code, year, fs_div=fs_div)

    targets = ['자산총계', '부채총계', '자본총계', '매출액', '매출원가', '매출총이익',
               '판매비와관리비', '영업이익', '영업이익(손실)', '당기순이익', '당기순이익(손실)']
    for col in [year, str(int(year)-1)]:
        df[col] = df[col].astype(str).str.replace(',', '')
        df[col] = pd.to_numeric(df[col], errors='coerce')

    fs_targets = ['자산총계', '부채총계', '자본총계']
    df_fs = df[(df['sj_nm'] == '재무상태표') & df['account_nm'].isin(fs_targets)]
    other_targets = list(set(targets) - set(fs_targets))
    df_other = df[df['account_nm'].isin(other_targets)].drop_duplicates(subset='account_nm', keep='first')
    df_filtered = pd.concat([df_fs, df_other], ignore_index=True)
    df_filtered['증감률(%)'] = ((df_filtered[year] - df_filtered[str(int(year)-1)]) / df_filtered[str(int(year)-1)] * 100).round(1)

    def safe_divide(numerator, denominator):
        return (numerator / denominator * 100) if numerator not in [None, 0] and denominator not in [None, 0] else None

    # 주요 항목 추출
    자산총계_당기 = get_value(df_filtered, '자산총계', year)
    부채총계_당기 = get_value(df_filtered, '부채총계', year)
    자본총계_당기 = get_value(df_filtered, '자본총계', year)
    매출액_당기 = get_value(df_filtered, '매출액', year)
    매출총이익_당기 = get_value(df_filtered, '매출총이익', year)
    영업이익_당기 = get_value_contains(df_filtered, '영업이익', year)
    당기순이익_당기 = get_value_contains(df_filtered, '당기순이익', year)

    자산총계_전기 = get_value(df_filtered, '자산총계', str(int(year)-1))
    부채총계_전기 = get_value(df_filtered, '부채총계', str(int(year)-1))
    자본총계_전기 = get_value(df_filtered, '자본총계', str(int(year)-1))
    매출액_전기 = get_value(df_filtered, '매출액', str(int(year)-1))
    매출총이익_전기 = get_value(df_filtered, '매출총이익', str(int(year)-1))
    영업이익_전기 = get_value_contains(df_filtered, '영업이익', str(int(year)-1))
    당기순이익_전기 = get_value_contains(df_filtered, '당기순이익', str(int(year)-1))

    df_ratios = pd.DataFrame({
        '과목': ['부채비율', '자본비율', '매출총이익률', '영업이익률', '당기순이익률'],
        year: [
            safe_divide(부채총계_당기, 자산총계_당기),
            safe_divide(자본총계_당기, 자산총계_당기),
            safe_divide(매출총이익_당기, 매출액_당기),
            safe_divide(영업이익_당기, 매출액_당기),
            safe_divide(당기순이익_당기, 매출액_당기)
        ],
        str(int(year)-1): [
            safe_divide(부채총계_전기, 자산총계_전기),
            safe_divide(자본총계_전기, 자산총계_전기),
            safe_divide(매출총이익_전기, 매출액_전기),
            safe_divide(영업이익_전기, 매출액_전기),
            safe_divide(당기순이익_전기, 매출액_전기)
        ]
    })

    df_ratios['증감률(%)'] = ((df_ratios[year] - df_ratios[str(int(year)-1)]) / df_ratios[str(int(year)-1)] * 100).round(1)

    final_df = pd.concat([
        df_filtered[['account_nm', year, str(int(year)-1), '증감률(%)']].rename(columns={'account_nm': '과목'}),
        df_ratios
    ], ignore_index=True)

    final_df['기업'] = company_name
    final_df = final_df[['기업', '과목', year, str(int(year)-1), '증감률(%)']]

    # 구분 컬럼 추가
    재무상태표 = ['자산총계', '부채총계', '자본총계']
    손익계산서 = ['매출액', '매출원가', '매출총이익', '판매비와관리비', '영업이익', '영업이익(손실)', '당기순이익', '당기순이익(손실)']
    경영분석지표 = ['부채비율', '자본비율', '매출총이익률', '영업이익률', '당기순이익률']

    def classify_subject(subject):
        if subject in 재무상태표:
            return '재무상태표'
        elif subject in 손익계산서:
            return '손익계산서'
        elif subject in 경영분석지표:
            return '경영분석지표'
        else:
            return '기타'

    final_df['구분'] = final_df['과목'].apply(classify_subject)
    final_df = final_df[final_df['구분'] != '기타'].reset_index(drop=True)

    return final_df

# ✅ 출력 포맷 함수
def format_output(df, year):
    formatted_df = df.copy()

    mask_fs_pl = formatted_df['구분'].isin(['재무상태표', '손익계산서'])
    for col in [year, str(int(year)-1)]:
        formatted_df.loc[mask_fs_pl, col] = formatted_df.loc[mask_fs_pl, col].apply(
            lambda x: f"{int(x):,}" if pd.notnull(x) else x
        )

    mask_ratios = formatted_df['구분'] == '경영분석지표'
    for col in [year, str(int(year)-1)]:
        formatted_df.loc[mask_ratios, col] = formatted_df.loc[mask_ratios, col].apply(
            lambda x: f"{x:.1f}%" if pd.notnull(x) else x
        )

    formatted_df['증감률(%)'] = formatted_df['증감률(%)'].apply(
        lambda x: f"{x:.1f}%" if pd.notnull(x) else x
    )

    return formatted_df

# ✅ Streamlit UI
st.header("상장기업 재무정보 조회")

companies_input = st.text_input("조회할 기업명 (쉼표로 구분)", value="")
year_input = st.text_input("조회 연도", value="2024")

fs_div_option = st.selectbox(
    '재무제표 구분 선택',
    options=['CFS', 'OFS'],
    index=1,
    help='CFS: 연결재무제표 / OFS: 별도재무제표'
)

if st.button("조회 실행"):
    company_list = [c.strip() for c in companies_input.split(',') if c.strip()]
    all_data = pd.DataFrame()

    for company in company_list:
        df_company = process_company(company, year=year_input, fs_div=fs_div_option)
        all_data = pd.concat([all_data, df_company], ignore_index=True)

    if not all_data.empty:
        formatted_data = format_output(all_data, year_input)

        st.success(f"✅ 조회 완료 (연도: {year_input}, fs_div: {fs_div_option})")
        st.dataframe(formatted_data, use_container_width=True)

    else:
        st.warning("❌ 데이터가 없습니다. 기업명을 확인하세요.")
