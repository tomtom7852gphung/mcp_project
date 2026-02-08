from fastmcp import FastMCP
from typing import List, Dict, Optional
import json
from pathlib import Path
import pandas as pd
from dateutil import parser
from datetime import datetime, timedelta


GOV_CALENDAR = pd.read_csv('./calendar_2026_process.csv' , index_col = 0)
GOV_CALENDAR['Date'] = GOV_CALENDAR.index.astype(str)
GOV_CALENDAR['Date'] = GOV_CALENDAR['Date'].apply(lambda x: parser.parse(x).date())
HOLIDAY = GOV_CALENDAR['Date'].tolist()


CALENDAR_FILE = Path("calendar.json")
mcp = FastMCP("calendar-mcp")

# 輔助函式 
def load_calendar() -> List[Dict]:
    if not CALENDAR_FILE.exists():
        return []
    with open(CALENDAR_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_calendar(data: List[Dict]):
    with open(CALENDAR_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def is_valid_working_day(date_str):
    """
    2027年之後暫無公布政府行政機關辦公日曆表，暫以是否為週末當作判斷工作日依據
    """
    if not date_str:
        return False , "無日期資訊"
    try:
        dt = parser.parse(date_str).date()
        if dt.year == 2026:
            if dt in HOLIDAY:
                holidayCategory = GOV_CALENDAR.loc[GOV_CALENDAR['Date'] == dt , 'holidayCategory'].iloc[0]
                return False , holidayCategory
            return True, "工作日可安排。"
        elif dt.year > 2026: 
            if dt.weekday() >= 5:
                return False, "週末"
            else:
                return True, "工作日可安排。"
        
    except Exception as e:
        return False , f"日期解析錯誤: {e}"    




# MCP Tools 定義
@mcp.tool()
def get_calendar_events() -> List[Dict]:
    """
    查詢所有已安排的行程
    在處理任何會議邀約前，Agent 必須呼叫此工具來檢查時間是否與現有行程(start/end)衝突
    """
    return load_calendar()


@mcp.tool()
def add_calendar_event(title: str, start: str, end: str) -> Dict:
    """
    新增日曆事件。
    Args:
        title: 事件標題 (如: EM002 洽談會議)
        start: 開始時間 (ISO 8601, 如: 2026-01-20T14:00:00)
        end: 結束時間 (ISO 8601)。若郵件未提供結束時間，請 Agent 根據內容推估會議時長
    """
    events = load_calendar()
    
    event = {"title": title,
             "start": start,
             "end": end}
    
    events.append(event)
    save_calendar(events)
    return {"status": "success", "message": f"已成功寫入行程: {title}"}



@mcp.tool()
def delete_calendar_events(title: str) -> Dict:
    """
    根據關鍵字刪除日曆事件
    用於『取消會議』或『更改時間 (EM013)』。只要標題包含關鍵字即會被刪除
    """
    events = load_calendar()
    before = len(events)
    # 使用關鍵字匹配，提高 Agent 刪除行程的容錯率
    new_events = [e for e in events if title not in e["title"]]
    save_calendar(new_events)
    return {"status": "success", "deleted_count": before - len(new_events)}


@mcp.tool()
def check_workday_status(date_str: str) -> str:
    """
    檢查特定日期是否為工作日
    Agent 在提取郵件日期後，必須先呼叫此工具確認該日是否為週末或除夕
    """
    is_work , reason = is_valid_working_day(date_str)
    return "OK" if is_work else f"FAIL: {reason}"



if __name__ == "__main__":
    mcp.run()
 