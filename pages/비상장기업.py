import streamlit as st
import pandas as pd
import warnings
import requests
from bs4 import BeautifulSoup
import re

warnings.filterwarnings("ignore", category=FutureWarning)

urls = {
    '알레르망': 'https://dart.fss.or.kr/report/viewer.do?rcpNo=20250328001262&dcmNo=10472660&eleId=3&offset=12057&length=408022&dtd=dart4.xsd',
    '이브자리': 'https://dart.fss.or.kr/report/viewer.do?rcpNo=20250411001174&dcmNo=10583850&eleId=3&offset=11312&length=339476&dtd=dart4.xsd'
}

def clean_df(df):
    df.columns = df.columns.map(lambda x: str(x).replace(" ", ""))
    for col in df.select_dtypes(include=['object']).columns:
        df[col] = df[col].map(lambda x: str(x).replace(" ", "") if isinstance(x, str) else x)
    return df

def clean_subject(series):
    def process(text):
        if not isinstance(text, str):
            return text
        text = re.sub(r'\([^)]*주석[^)]*\)', '', text)
        text = text.replace(" ", "").strip()
        text = re.sub(r'[^가-힣0-9]', '', text)
        return text
    return series.map(process)

def clean_targets(targets):
    return [re.sub(r'[^가-힣0-9]', '', s.replace(" ", "").strip()) for s in targets]

def find_period_columns(df):
    col_map = {str(col).replace(" ", ""): col for col in df.columns}
    col_25, col_24 = None, None
    for col_key in col_map:
        if '당' in col_key and '기' in col_key:
            col_25 = col_map[col_key]
        if '전' in col_key and '기' in col_key:
            col_24 = col_map[col_key]
    return col_25, col_24

def find_table_containing(tables, targets):
    targets_clean = clean_targets(targets)
    for i, table in enumerate(tables):
        df = clean_df(table)
        first_col = df.columns[0]
        if first_col in ['과목', '구분']:
            df[first_col] = clean_subject(df[first_col])
            if df[first_col].isin(targets_clean).any():
                return df
    return None

def calculate_growth(current, previous):
    try:
        current = float(current)
        previous = float(previous)
        return round(((current - previous) / previous) * 100, 1) if previous != 0 else None
    except:
        return None

def calculate_ratios(df):
    ratios = []
    try:
        assets_25 = df.loc[df['과목'] == '자산총계', '당기'].values[0]
        liabilities_25 = df.loc[df['과목'] == '부채총계', '당기'].values[0]
        equity_25 = df.loc[df['과목'] == '자본총계', '당기'].values[0]
        sales_25 = df.loc[df['과목'] == '매출액', '당기'].values[0]
        gross_profit_25 = df.loc[df['과목'] == '매출총이익', '당기'].values[0]
        operating_profit_25 = df.loc[df['과목'] == '영업이익', '당기'].values[0]
        net_profit_25 = df.loc[df['과목'] == '당기순이익', '당기'].values[0]

        assets_24 = df.loc[df['과목'] == '자산총계', '전기'].values[0]
        liabilities_24 = df.loc[df['과목'] == '부채총계', '전기'].values[0]
        equity_24 = df.loc[df['과목'] == '자본총계', '전기'].values[0]
        sales_24 = df.loc[df['과목'] == '매출액', '전기'].values[0]
        gross_profit_24 = df.loc[df['과목'] == '매출총이익', '전기'].values[0]
        operating_profit_24 = df.loc[df['과목'] == '영업이익', '전기'].values[0]
        net_profit_24 = df.loc[df['과목'] == '당기순이익', '전기'].values[0]

        ratios.append(['경영분석지표', '부채비율',
            (liabilities_25 / assets_25 * 100) if (liabilities_25 is not None and assets_25 not in [0, None]) else None,
            (liabilities_24 / assets_24 * 100) if (liabilities_24 is not None and assets_24 not in [0, None]) else None,
            None])

        ratios.append(['경영분석지표', '자본비율',
            (equity_25 / assets_25 * 100) if (equity_25 is not None and assets_25 not in [0, None]) else None,
            (equity_24 / assets_24 * 100) if (equity_24 is not None and assets_24 not in [0, None]) else None,
            None])

        ratios.append(['경영분석지표', '매출총이익률',
            (gross_profit_25 / sales_25 * 100) if (gross_profit_25 is not None and sales_25 not in [0, None]) else None,
            (gross_profit_24 / sales_24 * 100) if (gross_profit_24 is not None and sales_24 not in [0, None]) else None,
            None])

        ratios.append(['경영분석지표', '영업이익률',
            (operating_profit_25 / sales_25 * 100) if (operating_profit_25 is not None and sales_25 not in [0, None]) else None,
            (operating_profit_24 / sales_24 * 100) if (operating_profit_24 is not None and sales_24 not in [0, None]) else None,
            None])

        ratios.append(['경영분석지표', '당기순이익률',
            (net_profit_25 / sales_25 * 100) if (net_profit_25 is not None and sales_25 not in [0, None]) else None,
            (net_profit_24 / sales_24 * 100) if (net_profit_24 is not None and sales_24 not in [0, None]) else None,
            None])

        df_ratios = pd.DataFrame(ratios, columns=['구분', '과목', '당기', '전기', '증감률(%)'])
        df_ratios['증감률(%)'] = df_ratios.apply(lambda row: calculate_growth(row['당기'], row['전기']), axis=1)

        return df_ratios
    except:
        return pd.DataFrame(columns=['구분', '과목', '당기', '전기', '증감률(%)'])

def extract_data(url, company_name):
    response = requests.get(url)
    response.encoding = "utf-8"
    soup = BeautifulSoup(response.text, "html.parser")
    tables = pd.read_html(str(soup), flavor="bs4")

    targets_balance = ['자산총계', '부채총계', '자본총계']
    targets_pl = ['매출액', '매출원가', '매출총이익', '판매비와관리비', '영업이익', '당기순이익']

    df_balance = find_table_containing(tables, targets_balance)
    df_balance_filtered = pd.DataFrame(columns=['구분', '과목', '당기', '전기'])
    if df_balance is not None:
        df_balance['과목'] = clean_subject(df_balance['과목'])
        col_25, col_24 = find_period_columns(df_balance)
        df_balance_filtered = df_balance[df_balance['과목'].isin(clean_targets(targets_balance))]
        df_balance_filtered = df_balance_filtered[['과목', col_25, col_24]]
        df_balance_filtered.rename(columns={col_25: '당기', col_24: '전기'}, inplace=True)
        df_balance_filtered['구분'] = '재무상태표'

    df_pl = find_table_containing(tables, targets_pl)
    df_pl_filtered = pd.DataFrame(columns=['구분', '과목', '당기', '전기'])
    if df_pl is not None:
        df_pl['과목'] = clean_subject(df_pl['과목'])
        col_25, col_24 = find_period_columns(df_pl)
        df_pl_filtered = df_pl[df_pl['과목'].isin(clean_targets(targets_pl))]
        df_pl_filtered = df_pl_filtered[['과목', col_25, col_24]]
        df_pl_filtered.rename(columns={col_25: '당기', col_24: '전기'}, inplace=True)
        df_pl_filtered['구분'] = '손익계산서'

    combined_result = pd.concat([df_balance_filtered, df_pl_filtered], ignore_index=True)
    combined_result[['당기', '전기']] = combined_result[['당기', '전기']].apply(pd.to_numeric, errors='coerce')
    combined_result['증감률(%)'] = combined_result.apply(lambda row: calculate_growth(row['당기'], row['전기']), axis=1)

    ratios_df = calculate_ratios(combined_result)
    combined_result = pd.concat([combined_result, ratios_df], ignore_index=True)
    combined_result.insert(0, '기업', company_name)

    return combined_result



# 포맷팅 함수
def format_output(df):
    formatted_df = df.copy()

    mask_fs_pl = formatted_df['구분'].isin(['재무상태표', '손익계산서'])
    for col in ['당기', '전기']:
        formatted_df.loc[mask_fs_pl, col] = formatted_df.loc[mask_fs_pl, col].apply(
            lambda x: f"{int(x):,}" if pd.notnull(x) else x
        )

    mask_ratios = formatted_df['구분'] == '경영분석지표'
    for col in ['당기', '전기']:
        formatted_df.loc[mask_ratios, col] = formatted_df.loc[mask_ratios, col].apply(
            lambda x: f"{x:.1f}%" if pd.notnull(x) else x
        )

    formatted_df['증감률(%)'] = formatted_df['증감률(%)'].apply(
        lambda x: f"{x:.1f}%" if pd.notnull(x) else x
    )

    return formatted_df


# 데이터 수집
all_data = pd.DataFrame()
for company, url in urls.items():
    df_company = extract_data(url, company)
    all_data = pd.concat([all_data, df_company], ignore_index=True)

# 포맷 적용
all_data = all_data[['기업', '구분', '과목', '당기', '전기', '증감률(%)']]
formatted_data = format_output(all_data)
st.subheader("알레르망, 이브자리 재무정보")
st.dataframe(formatted_data, use_container_width=True)

# Streamlit
st.subheader("기업명 및 DART URL 입력")

user_input = st.text_area("기업명과 URL을 입력하세요 (기업명, URL 순서, 줄바꿈으로 구분)", height=200)

if st.button("조회 실행"):
    urls = {}
    lines = user_input.strip().split('\n')
    for line in lines:
        if ',' in line:
            company, url = line.split(',', 1)
            urls[company.strip()] = url.strip()

    st.write("입력된 URL 목록:", urls)

    # 데이터 수집
    all_data = pd.DataFrame()
    for company, url in urls.items():
        df_company = extract_data(url, company)
        all_data = pd.concat([all_data, df_company], ignore_index=True)

    if not all_data.empty:
        all_data = all_data[['기업', '구분', '과목', '당기', '전기', '증감률(%)']]
        formatted_data = format_output(all_data)
        st.dataframe(formatted_data, use_container_width=True)
    else:
        st.warning("❌ 데이터가 없습니다. 기업명과 URL을 다시 확인하세요.")

