import asyncio
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from llm_setting import llm , EmailAnalysis
from prompt_set import email_system_prompt
from langchain_core.messages import SystemMessage , HumanMessage , ToolMessage
import logging


logging.basicConfig(filename='./decision_actions.log' ,
                    filemode = 'w' ,
                    level = logging.INFO ,
                    format = "%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("httpx").setLevel(logging.WARNING)


# LLM可調用工具清單描述 
tools_desc = [
    {
        "name": "check_workday_status",
        "description": "檢查日期是否為工作日。提取日期後，必須先呼叫此工具確認是否為週末或除夕或國定假日。",
        "parameters": {
            "type": "object",
            "properties": {"date_str": {"type": "string", "description": "YYYY-MM-DD"}},
            "required": ["date_str"]
        }
    },
    {
        "name": "get_calendar_events",
        "description": "查詢現有日曆行程。回傳一個列表，每個項目包含 'title', 'start', 'end'。Agent 必須自行比對這些 ISO 時間以判斷是否衝突。",
        "parameters": {"type": "object", "properties": {}}
    },
    {
        "name": "add_calendar_event",
        "description": "正式將會議寫入日曆。",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "start": {"type": "string", "description": "ISO 8601 格式"},
                "end": {"type": "string", "description": "ISO 8601 格式"}
            },
            "required": ["title", "start", "end"]
        }
    },
    {
        "name": "delete_calendar_events",
        "description": "刪除日曆行程：title 參數應填入『從 get_calendar_events 找到的舊事件 title』，用於改期時先刪後加，避免誤刪無關事件。",
        "parameters": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"]
        }
    }
]



# Agent 核心推理函數
async def run_autonomous_agent(email_content, session, llm):
    llm_with_tools = llm.bind_tools(tools_desc , parallel_tool_calls = False)
    
    messages = [SystemMessage(content = email_system_prompt) , HumanMessage(content = f"處理這封郵件：\n{email_content}")]
    executed_actions = []
    
    # 推理循環 (Reasoning Loop)
    max_iterations = 10  # 最大循環次數
    iterations = 0
    while iterations < max_iterations:
        iterations += 1
        
        # LLM 決定下一步
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        # 如果 LLM 不再需要調用工具，則產出最終結構化結果
        if not response.tool_calls:
            final_agent = llm.with_structured_output(EmailAnalysis)
            final_agent = await final_agent.ainvoke(messages)
        
            # 將過程轉為 dict 並合併進結果中
            final_agent = final_agent.model_dump()
            final_agent["executed_actions"] = executed_actions
            return final_agent
        
        
        # 執行 LLM 要求的工具調用
        for tool_call in response.tool_calls:
            t_name = tool_call["name"]
            t_args = tool_call["args"]
            
            print(f"Agent 決定行動 => 呼叫 {t_name} | 參數 {t_args}")    
            logging.info(f"Agent 決定行動 => 呼叫 {t_name} | 參數 {t_args}")
            executed_actions.append(f"Agent 決定行動 => 呼叫 {t_name} | 參數 {t_args}")
            
            # 透過 MCP Session 呼叫 server.py 裡的工具
            tool_res = await session.call_tool(t_name, arguments=t_args)
            
            # 將工具回傳結果，餵回給 LLM
            messages.append(ToolMessage(tool_call_id = tool_call["id"] , content = str(tool_res.content)))

    print("Agent 達到最大循環次數，終止推理")    
    logging.error("Agent 達到最大循環次數，終止推理")
    final_agent = llm.with_structured_output(EmailAnalysis)
    return await final_agent.ainvoke(messages)



async def process_emails():
    server_params = StdioServerParameters(command="python" , args = ["server.py"])

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            
            with open("emails.json", "r", encoding="utf-8") as f:
                emails = json.load(f)

            all_results = []
            for mail in emails:
                print(f"\n處理 => {mail['id']}-{mail['subject']}")
                logging.info(f"處理 => {mail['id']}-{mail['subject']}")
                
                result = await run_autonomous_agent(f"《信件標題》: {mail['subject']} | 《信件內容》: {mail['content']}" , session , llm)  
                
                print(f"分類結果：{result['category']} (priority={result['priority']})")
                print(f"推理結果：{result['reasoning']}")
                logging.info(f"分類結果：{result['category']} (priority={result['priority']})")
                logging.info(f"推理結果：{result['reasoning']}")
                                
                result["id"] = mail["id"]
                all_results.append(result)

            with open("agent_final_results.json", "w", encoding = "utf-8") as f:
                json.dump(all_results , f , ensure_ascii = False , indent = 2)




if __name__ == "__main__":
    asyncio.run(process_emails())